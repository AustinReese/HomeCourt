import sys
sys.path.append('/home/winner/HomeCourt/api/controllers')

import wiz_controller
import psycopg2
from time import sleep

def getConn():
    return psycopg2.connect(
        database="postgres",
        user="postgres"
        )

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

def main():
    while True:
        print(getWizBulbsStatus())
        sleep(3600)

if __name__ == "__main__":
    main()