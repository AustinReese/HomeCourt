import requests
import threading
from json import loads
from time import sleep
from dotenv import load_dotenv
from os import environ
from datetime import datetime

load_dotenv()

FLIGHTS = []
FLIGHTS_LOCK = threading.Lock()

class FlightUpdateThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.daemon = True
        self.recently_seen = {}

    def run(self):
        global FLIGHTS
        while True:
            res = requests.get('http://192.168.0.2/skyaware/data/aircraft.json')
            flight_data = loads(res.text)["aircraft"]
            for flight in flight_data:
                if flight['hex'] in self.recently_seen:
                    continue

                if 'flight' not in flight:
                    continue

                if flight['flight'] == 'TEST1234' or flight['flight'].strip() == '':
                    continue
                
                flight_dict = {
                    'flight': flight['flight'],
                    'hex': flight['hex']
                }
                
                if 'gs' in flight:
                    flight_dict['gs'] = flight['gs']
                                
                self.recently_seen[flight['hex']] = datetime.now()

                with FLIGHTS_LOCK:
                    FLIGHTS.append(flight_dict)
            

            self.recently_seen = {k: v for k, v in self.recently_seen.items() if (datetime.now() - v).seconds <= 3600}
            print(len(self.recently_seen))
            sleep(30)

def getActiveFlights():
    global FLIGHTS

    while True:
        with FLIGHTS_LOCK:
            flights_copy = FLIGHTS.copy()

        api_key = environ['api_key']
        res = requests.get('http://192.168.0.2/skyaware/data/aircraft.json')
        for flight in flights_copy:

            headers = {"x-apikey": api_key}
            
            res = requests.get(f"https://aeroapi.flightaware.com/aeroapi/flights/{flight['flight'].strip()}?ident_type=fa_flight_id", headers=headers)
            flight_data = loads(res.text)

            if 'flights' not in flight_data or len(flight_data['flights']) == 0:
                print("FLIGHTS NOT FOUND")
                print(flight)
                print(flight_data)
                continue
            
            flight_data = flight_data['flights']

            type = flight_data[0]['type']
            flight_name = flight['flight'].strip()
            origin_city = flight_data[0]['origin']['city']
            origin_iata = flight_data[0]['origin']['code_iata']
            if flight_data[0]['destination']:
                destination_city = flight_data[0]['destination']['city']
                destination_iata = flight_data[0]['destination']['code_iata']
            route_distance = flight_data[0]['route_distance']
            plane_hex = flight['hex']
            flight2 = flight['flight']
            ground_speed = None
            if 'gs' in flight:
                speed = flight['gs']
            
            print(flight, flight2, ground_speed)
            
            
            
            # print(f"{flight['flight'].strip()} ({flight_data[0]['type']}): {flight_data[0]['origin']['city']} ({flight_data[0]['origin']['code_iata']}) to " +
            #     f"{flight_data[0]['destination']['city']} ({flight_data[0]['destination']['code_iata']}), {flight_data[0]['route_distance']} miles")
            
            # sleep(6.66)

            # grab flight_number, use it to create route_seen variable for database. 
            # fa_flight_id is a unique identifier

if __name__ == "__main__":
    flightUpdateThread = FlightUpdateThread()
    flightUpdateThread.start()

    getActiveFlights()