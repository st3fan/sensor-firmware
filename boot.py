# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/

#
# boot.py - Stefan Arentz, September 2020
#
# This is a very simplistic firmware for the ESP32 with a DHT22 (AM2302)
# connected to GPIO4. It will take a temperature measurement every
# _INTERVAL seconds and then send a packet to the server at
# _SERVER_ADDR/_SERVER_PORT.
#
# Tested on a cheap NodeMCU (ESP32-WROOM) clone.
#
# Send to the board using:
#
#  ampy -d 1 -p /dev/cu.usbserial-0001 -b 115200 put boot.py
#
# Change _WIFI_NETWORK and _WIFI_PASSWORD to match yours.
#


import dht
import ntptime
import machine
import ubinascii
import network
import utime
import usocket
import ujson
import uos

from config import INTERVAL, WIFI_NETWORK, WIFI_PASSWORD, SERVER_ADDR, SERVER_PORT


_SENSOR_PIN = 4
_BUTTON_PIN = 5


# Connect to the given Wi-Fi network. Returns True if the connection is good.
# Waits for 10 seconds before giving up.

def connect(wifi_network, wifi_password):
    nic = network.WLAN(network.STA_IF)
    if nic.isconnected():
        return True
    print('[*] Connecting to <%s>' % wifi_network)
    nic.active(True)
    nic.connect(wifi_network, wifi_password)
    for i in range(20):
        print('[*] Checking Wi-Fi connection status ...')
        utime.sleep(0.5)
        if nic.isconnected():
            print('[*] Connected as ', nic.ifconfig())
            return True

# Send a temperature measurement to the server at the given address (ip/port
# tuple). Since this is UDP, we send the packet three times. On a home network
# this will probably have a very low failure rate.

def send_measurement(sensor, address):
    sensor.measure()
    temperature = sensor.temperature()
    humidity = sensor.humidity()

    print(temperature, humidity)

    measurement_id = uos.urandom(16)
    for i in range(3):
        s = usocket.socket(usocket.AF_INET, usocket.SOCK_DGRAM)
        s.sendto(ujson.dumps({
            "sensor_id": ubinascii.hexlify(machine.unique_id()),
            "sensor_type": "ESP32/DHT22",
            "sensor_time": utime.time(),
            "measurement_id": ubinascii.hexlify(measurement_id),
            "measurement_data": {
                "temperature": temperature,
                "humidity": humidity,
            }
        }), address)
        utime.sleep(0.1)


def main():
    sensor = dht.DHT22(machine.Pin(_SENSOR_PIN))

    # If this is a cold start then grab the time through NTP and immediately
    # send a measurement. We use the time to schedule every 5 minutes even.

    if machine.reset_cause() == machine.PWRON_RESET:
        print("[*] Welcome from PWRON_RESET")
        if connect(WIFI_NETWORK, WIFI_PASSWORD):
            ntptime.settime()
            print("[*] The time is now ", utime.localtime())
            send_measurement(sensor, (SERVER_ADDR, SERVER_PORT))
            machine.deepsleep(INTERVAL * 1000)

    # If this is a wake up from the deep sleep timer, we just connect to the
    # network and measure.

    if machine.reset_cause() == machine.DEEPSLEEP_RESET:
        print("[*] Welcome from DEEPSLEEP_RESET")
        if connect(WIFI_NETWORK, WIFI_PASSWORD):
            send_measurement(sensor, (SERVER_ADDR, SERVER_PORT))
            machine.deepsleep(INTERVAL * 1000)


# Main program - if the test button is down, do not run the main program and
# just drop straight into the REPL. This is a lifesaver during development when
# it is difficult to connect to the REPL or to flash the program because of the
# deep sleep we do. (Connect _BUTTON_PIN to GND either directly or via a push
# button)

if __name__ == "__main__":
    button = machine.Pin(_BUTTON_PIN, machine.Pin.IN, machine.Pin.PULL_UP)
    if button.value():
        main()

