import requests
from json import loads
from time import sleep
from dotenv import load_dotenv
from os import environ

load_dotenv()

def getActiveFlights():
    while True:
        api_key = environ['api_key']
        res = requests.get('http://192.168.0.2/skyaware/data/aircraft.json')
        flights = loads(res.text)["aircraft"]
        for flight in flights:
            if 'flight' not in flight:
                continue
            
            if flight['flight'] == 'TEST1234' or flight['flight'].strip() == '':
                continue

            headers = {"x-apikey": api_key}
            
            res = requests.get(f"https://aeroapi.flightaware.com/aeroapi/flights/{flight['flight'].strip()}?ident_type=fa_flight_id", headers=headers)
            flight_data = loads(res.text)
            if 'flights' not in flight_data:
                print(flight)
                print(flight_data)
                continue

            #print(flight_data)
            
            flight_data = flight_data['flights']


            print(f"{flight['flight'].strip()} ({flight_data[0]['type']}): {flight_data[0]['origin']['city']} ({flight_data[0]['origin']['code_iata']}) to " +
                f"{flight_data[0]['destination']['city']} ({flight_data[0]['destination']['code_iata']}), {flight_data[0]['route_distance']} miles")
            sleep(6.66)

            # grab flight_number, use it to create route_seen variable for database. 
            # fa_flight_id is a unique identifier

getActiveFlights()