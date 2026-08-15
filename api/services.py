import datetime
import logging
import math
from db_utils import getConn
from controllers import wiz_controller

temp_log = logging.getLogger('temperature')

def _safe_value(val):
    try:
        f = float(val)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None

def _safe_avg_temp(dht, ds):
    dht_val = _safe_value(dht)
    ds_val = _safe_value(ds)
    if dht_val is not None and ds_val is not None:
        return round((dht_val + ds_val) / 2, 2)
    elif dht_val is not None:
        return round(dht_val, 2)
    elif ds_val is not None:
        return round(ds_val, 2)
    return None

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
    temp_log.debug(f"DB insert OK for '{report['deviceName']}' — "
                   f"dht={report.get('dhtTemp')} ds={report.get('dsTemp')} "
                   f"humidity={report.get('humidity')} vcc={report.get('vcc')}")
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
    temperature = _safe_avg_temp(report[0][2], report[0][3])
    humidity = _safe_value(report[0][1])
    temperatureReportObject = {
        'Device Name': report[0][0],
        'Humidity': humidity,
        'Temperature': temperature,
        'Battery': report[0][4],
        'Last Seen': report[0][5],
    }
    return temperatureReportObject

def fetchAllTemperatures(numberOfDays):
    targetDatetime = datetime.datetime.now() - datetime.timedelta(days=numberOfDays)
    targetTimestamp = targetDatetime.strftime('%Y-%m-%d %H:%M:%S')
    conn = getConn()
    curs = conn.cursor()
    nodes = getTemperatureNodes()
    returnObject = {}
    for node in nodes:
        returnObject[node] = {"x": [], "y": [], "type": "scatter"}
        curs.execute("SELECT dhttemp,dstemp,reporttimestamp \
                    FROM temperature_report tr1\
                    WHERE reporttimestamp > %s\
                    AND devicename = %s;", (targetTimestamp, node))
        report = curs.fetchall()
        for res in report:
            temperature = _safe_avg_temp(res[0], res[1])
            returnObject[node]["y"].append(temperature)
            returnObject[node]["x"].append(res[2])
    curs.close()
    conn.close()
    return returnObject

def getTemperatureNodes():
    conn = getConn()
    curs = conn.cursor()
    curs.execute("SELECT DISTINCT devicename FROM temperature_report")
    devices = curs.fetchall()
    curs.close()
    conn.close()
    return [x[0] for x in devices]

def getWizBulbList():
    conn = getConn()
    curs = conn.cursor()
    curs.execute("SELECT bulb_name, ip FROM wiz_bulb WHERE is_enabled = true ORDER BY bulb_name")
    devices = curs.fetchall()
    curs.close()
    conn.close()
    return [{"name": d[0], "ip": d[1]} for d in devices]

def getWizBulbStatus(bulb_data):
    return wiz_controller.getBulbStatus(bulb_data)