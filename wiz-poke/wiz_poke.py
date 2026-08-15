import sys
sys.path.append('/home/winner/HomeCourt/api/controllers')

import logging
from logging.handlers import RotatingFileHandler
import os
import wiz_controller
import psycopg2
from time import sleep
from datetime import datetime

POLL_INTERVAL = 60
LOG_DIR = '/home/winner/HomeCourt/logs'
os.makedirs(LOG_DIR, exist_ok=True)

formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
handler = RotatingFileHandler(
    os.path.join(LOG_DIR, 'wiz-poke.log'),
    maxBytes=5*1024*1024, backupCount=3
)
handler.setFormatter(formatter)
log = logging.getLogger('wiz-poke')
log.setLevel(logging.INFO)
log.addHandler(handler)

def getConn():
    return psycopg2.connect(
        database="postgres",
        user="postgres"
    )

def getEnabledBulbs():
    conn = getConn()
    curs = conn.cursor()
    curs.execute("SELECT bulb_name, ip FROM wiz_bulb WHERE is_enabled = true ORDER BY bulb_name")
    devices = curs.fetchall()
    curs.close()
    conn.close()
    return [{"name": d[0], "ip": d[1]} for d in devices]

def pokeBulbs():
    bulbs = getEnabledBulbs()
    for bulb in bulbs:
        try:
            status = wiz_controller.getBulbStatus(bulb)
            if status:
                log.info(f"{bulb['name']}: online")
            else:
                log.warning(f"{bulb['name']}: offline (no response)")
        except Exception as e:
            log.error(f"{bulb['name']}: error - {e}")

def main():
    log.info(f"wiz-poke started, polling every {POLL_INTERVAL}s")
    while True:
        try:
            pokeBulbs()
        except Exception as e:
            log.error(f"poll error: {e}")
        sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
