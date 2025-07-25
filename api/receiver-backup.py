# This code lives on pi-receiver, don't want to lose it AGAIN

import serial
import logging
import requests

logging.basicConfig(filename='/home/winner/log.txt', level=logging.INFO, format='%(asctime)s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

ser = serial.Serial('/dev/serial0', 9600, timeout=1)
known_devices = ["basement", "1st floor", "upstairs"]

try:
    while True:
        if ser.in_waiting > 0:
            line = ser.readline().decode('utf-8').rstrip()
            if line:
                if line[-1] != '&':
                    logging.info(f"Ignoring malformed message: {line}")
                    continue
                data = line.split('|')
                if len(data) != 5:
                    logging.info(f"Ignoring too much data: {data}")
                    continue
                if data[0] not in known_devices:
                    logging.info(f"Ignoring unknown device: {data}")
                    continue
                req_body = {
                    "deviceName": data[0],
                    "humidity": data[2],
                    "dhtTemp": data[1],
                    "dsTemp": data[3],
                    "vcc": data[4].replace('&', '')
                }

                requests.post("http://192.168.0.105:8080/postTemperatureReport", json=req_body).text
                

except Exception as e:
    print("Exiting...")
finally:
    ser.close()
