from flask import Flask, request, jsonify
from flask_cors import CORS
from json import dumps
from controllers import wiz_controller
import datetime
import psycopg2
import zmq

from dotenv import load_dotenv
from os import environ

load_dotenv()

app = Flask(__name__)
app.secret_key = "LOOSEJUICE"
CORS(app)

def zmqExchange(message):
    if environ['container'] == 'false':
        context = zmq.Context()
        socket = context.socket(zmq.REQ)
        socket.connect(f"tcp://{environ['led_host']}:5556")
        socket.send(message.encode())
        response = socket.recv().decode()
        socket.close()
        return response
    else:
        print(message)
        return

def getConn():
    if environ['container'] == 'false':
        return psycopg2.connect(
            database="postgres",
            user="postgres"
            )
    else:
        return psycopg2.connect(
            host='postgres',
            database="postgres",
            user="postgres"
            )


def getDisplayOptionsHelper():
    conn = getConn()
    curs = conn.cursor()
    curs.execute("select displayKey from display")
    displays = curs.fetchall()
    all_display_options = {}
    for display in [x[0] for x in displays]:
        curs.execute("select displayOptionKey, displayOptionName, formType from display_option where displayKey = %s;", (display,))
        display_option_values = curs.fetchall()
        display_option_list = []
        for display_option in display_option_values:
            curs.execute(f"select selectionKey, selectionText from {display}_selection")
            selection_values = curs.fetchall()
            selection_list = []
            for selection_value in selection_values:
                selections_dict = {
                    'selectionKey': selection_value[0],
                    'selectionText': selection_value[1]
                }
                selection_list.append(selections_dict)
            display_option_dict = {
                'displayOptionKey': display_option[0],
                'displayOptionName': display_option[1],
                'formType': display_option[2],
                'displayOptionSelections': selection_list
            }
            display_option_list.append(display_option_dict)
        all_display_options[display] = display_option_list

    curs.close()
    conn.close()
    return all_display_options

def submitTemperatureReport(report):
    insert_object = [(report['deviceName']),
                      (report['humidity']),
                      (report['dhtTemp']),
                      (report['dsTemp']),
                      (report['vcc']),
                      (datetime.datetime.now())]
    conn = getConn()
    curs = conn.cursor()
    curs.execute("insert into temperature_report (deviceName, humidity, dhtTemp, dsTemp, vcc, reportTimestamp)\
                  values (%s, %s, %s, %s, %s, %s)", insert_object)
    conn.commit()
    curs.close()
    conn.close()

def fetchLatestTemperatureReport(deviceName):
    conn = getConn()
    curs = conn.cursor()
    curs.execute("SELECT devicename,humidity,dhttemp,dstemp,vcc,reporttimestamp \
                FROM temperature_report tr1\
                WHERE devicename = %s\
                AND reporttimestamp = (SELECT MAX(reporttimestamp) FROM temperature_report WHERE devicename = %s)\
                ORDER BY reporttimestamp;", (deviceName, deviceName))
    report = curs.fetchall()
    curs.close()
    conn.close()
    temperature = round((float(report[0][2]) + float(report[0][3])) / 2, 2)
    temperatureReportObject = {
        'Device Name': report[0][0],
        'Humidity': report[0][1],
        'Temperature': temperature,
        'Battery': report[0][4],
        'Last Seen': report[0][5],
    }
    return temperatureReportObject

def getTemperatureNodes():
    conn = getConn()
    curs = conn.cursor()
    curs.execute("SELECT DISTINCT devicename FROM temperature_report")
    devices = curs.fetchall()
    curs.close()
    conn.close()
    return [x[0] for x in devices]
    
def getWizBulbsStatus():
    conn = getConn()
    curs = conn.cursor()
    curs.execute("SELECT bulb_name, ip FROM wiz_bulb WHERE is_enabled = true ORDER BY bulb_name")
    devices = curs.fetchall()
    curs.close()
    conn.close()
    device_list = []
    for device in devices:
        bulb_object = {"name": device[0], "ip": device[1]}
        device_list.append(wiz_controller.getBulbStatus(bulb_object))
    return device_list


@app.route('/getDisplayOptions', methods=['GET'])
def getDisplayOptions():
    return {"result": getDisplayOptionsHelper()}
        

@app.route('/submitApplicationOptions', methods=['POST'])
def submitApplicationOptions():
    try:
        zmqExchange(dumps(request.json))
        return {'result': 'success'}
    except Exception as e:
        print(e)
        return {"result": f"error"}
    

@app.route('/postTemperatureReport', methods=['POST'])
def postTemperatureReport():
    try:
        submitTemperatureReport(request.json)
        return {'result': 'success'}
    except Exception as e:
        print(e)
        return {"result": f"error"}

@app.route('/getTemperatureReport', methods=['GET'])
def getTemperatureReport():
    try:

        temperature_nodes = getTemperatureNodes()

        reports = []
        for node in temperature_nodes:
            reports.append(fetchLatestTemperatureReport(node))
        return {'result': reports}
    except Exception as e:
        print(e)
        return {"result": f"error"}

@app.route('/getWizBulbs', methods=['GET'])
def getWizBulbs():
    try:
        bulbs = getWizBulbsStatus()
        return {'result': bulbs}
    except Exception as e:
        print(e)
        return {"result": f"error"}

@app.route('/setWizBulbs', methods=['POST'])
def setWizBulbs():
    try:
        wiz_controller.setBulbStatus(request.json)
    
        return {'result': 'probably good'}
    except Exception as e:
        return {"result": f"error"}


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080, debug=True) 
