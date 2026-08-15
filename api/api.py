import logging
from logging.handlers import RotatingFileHandler
import os
from flask import Flask
from flask_cors import CORS
from routes import init_routes

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

def setup_logging():
    formatter = logging.Formatter('[%(asctime)s] %(name)s %(levelname)s: %(message)s')

    api_handler = RotatingFileHandler(
        os.path.join(LOG_DIR, 'api.log'),
        maxBytes=5*1024*1024, backupCount=3
    )
    api_handler.setFormatter(formatter)

    temp_handler = RotatingFileHandler(
        os.path.join(LOG_DIR, 'temperature.log'),
        maxBytes=5*1024*1024, backupCount=5
    )
    temp_handler.setFormatter(formatter)

    wiz_handler = RotatingFileHandler(
        os.path.join(LOG_DIR, 'wiz.log'),
        maxBytes=5*1024*1024, backupCount=3
    )
    wiz_handler.setFormatter(formatter)

    api_logger = logging.getLogger('api')
    api_logger.setLevel(logging.INFO)
    api_logger.addHandler(api_handler)

    temp_logger = logging.getLogger('temperature')
    temp_logger.setLevel(logging.DEBUG)
    temp_logger.addHandler(temp_handler)

    wiz_logger = logging.getLogger('wiz')
    wiz_logger.setLevel(logging.INFO)
    wiz_logger.addHandler(wiz_handler)

setup_logging()

app = Flask(__name__)
app.secret_key = "LOOSEJUICE"
CORS(app)

init_routes(app)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080, debug=False)