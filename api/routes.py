import logging
from flask import request, jsonify
from json import dumps
from services import getDisplayOptionsHelper, submitTemperatureReport, fetchLatestTemperatureReport, fetchAllTemperatures, getTemperatureNodes, getWizBulbList, getWizBulbStatus
from zmq_utils import zmqExchange
from controllers import wiz_controller

api_log = logging.getLogger('api')
temp_log = logging.getLogger('temperature')
wiz_log = logging.getLogger('wiz')

def init_routes(app):
    @app.route('/getDisplayOptions', methods=['GET'])
    def getDisplayOptions():
        return {"result": getDisplayOptionsHelper()}

    @app.route('/submitApplicationOptions', methods=['POST'])
    def submitApplicationOptions():
        try:
            api_log.info(f"submitApplicationOptions: {request.json}")
            zmqExchange(dumps(request.json))
            return {'result': 'success'}
        except Exception as e:
            api_log.error(f"submitApplicationOptions error: {e}")
            return {"result": f"error"}

    @app.route('/postTemperatureReport', methods=['POST'])
    def postTemperatureReport():
        try:
            data = request.json
            temp_log.info(f"RECEIVED report from '{data.get('deviceName', 'UNKNOWN')}' — "
                          f"dhtTemp={data.get('dhtTemp')} dsTemp={data.get('dsTemp')} "
                          f"humidity={data.get('humidity')} vcc={data.get('vcc')} "
                          f"remote_addr={request.remote_addr}")
            submitTemperatureReport(data)
            temp_log.info(f"STORED report from '{data.get('deviceName', 'UNKNOWN')}'")
            return {'result': 'success'}
        except Exception as e:
            temp_log.error(f"postTemperatureReport error: {e} — payload={request.json}")
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
            api_log.error(f"getTemperatureReport error: {e}")
            return {"result": f"error"}

    @app.route('/getAllTemperatures', methods=['POST'])
    def getAllTemperatures():
        try:
            api_log.info(f"getAllTemperatures: {request.json}")
            return {'result': fetchAllTemperatures(request.json["number_of_days"])}
        except Exception as e:
            api_log.error(f"getAllTemperatures error: {e}")
            return {"result": f"error"}

    @app.route('/getWizBulbs', methods=['GET'])
    def getWizBulbs():
        try:
            return {'result': getWizBulbList()}
        except Exception as e:
            wiz_log.error(f"getWizBulbs error: {e}")
            return {"result": f"error"}

    @app.route('/getWizBulbStatus', methods=['POST'])
    def getWizBulbStatusRoute():
        try:
            bulb_data = request.json
            wiz_log.info(f"getWizBulbStatus: {bulb_data.get('name')}")
            status = getWizBulbStatus(bulb_data)
            wiz_log.info(f"getWizBulbStatus result: {bulb_data.get('name')} — {'online' if status else 'offline'}")
            return {'result': status}
        except Exception as e:
            wiz_log.error(f"getWizBulbStatus error: {e}")
            return {"result": f"error"}

    @app.route('/setWizBulbs', methods=['POST'])
    def setWizBulbs():
        try:
            data = request.json
            wiz_log.info(f"setWizBulbs: {data.get('name')} status={data.get('status')} "
                         f"{'temp=' + str(data.get('temp')) if 'temp' in data else 'color=' + str(data.get('color'))}")
            wiz_controller.setBulbStatus(data)
            return {'result': 'probably good'}
        except Exception as e:
            wiz_log.error(f"setWizBulbs error: {e}")
            return {"result": f"error"}

