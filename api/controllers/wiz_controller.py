import logging
from dotenv import load_dotenv
from os import environ
from time import sleep
from json import loads
import socket

load_dotenv()

log = logging.getLogger('wiz')

class WizBulb():
    def __init__(self, name, ip_addr):
        self.name = name
        self.ip_addr = ip_addr
        self._create_socket()

    def _create_socket(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(5)
        self.sock.connect((self.ip_addr, 38899))

    def close(self):
        try:
            self.sock.close()
        except Exception:
            pass
        
    def turn_on(self):
        try:
            success = False
            tries = 0
            while success == False:
                self.sock.sendall(b'{"id":1,"method":"setState","params":{"state":true}}')
                data = self.sock.recv(1024)
                result = loads(data.decode())['result']
                if result['success'] == True:
                    success = True
                else:
                    log.warning(f"{self.name} turn_on retry {tries}: {data}")
                    tries += 1
                    if tries >= 3:
                        log.error(f"{self.name} turn_on failed after 3 tries")
                        return
                    sleep(1)

            log.info(f"{self.name} turned on")

        except socket.timeout as e:
            log.warning(f"{self.name} ({self.ip_addr}) turn_on timeout: {e}")

        except Exception as e:
            log.error(f"{self.name} turn_on error: {e}")
            raise(e)

    def turn_off(self):
        try:
            success = False
            tries = 0
            while success == False:
                self.sock.sendall(b'{"id":1,"method":"setState","params":{"state":false}}')
                data = self.sock.recv(1024)
                result = loads(data.decode())['result']
                if result['success'] == True:
                    success = True
                else:
                    log.warning(f"{self.name} turn_off retry {tries}: {data}")
                    tries += 1
                    if tries >= 3:
                        log.error(f"{self.name} turn_off failed after 3 tries")
                        return
                    sleep(1)

            log.info(f"{self.name} turned off")

        except socket.timeout as e:
            log.warning(f"{self.name} ({self.ip_addr}) turn_off timeout: {e}")

        except Exception as e:
            log.error(f"{self.name} turn_off error: {e}")
            raise(e)

            

    def change_color_and_brightness(self, r, g, b, brightness):
        try:
            success = False
            tries = 0
            r = r if r != 0 else 1
            g = g if g != 0 else 1
            b = b if b != 0 else 1

            if int(brightness) < 10:
                brightness = 10
            elif int(brightness) > 100:
                brightness = 100
            while success == False:
                self.sock.sendall(f'{{"id":1,"method":"setState","params":{{"r":{r},"g":{g},"b":{b},"dimming": {brightness}}}}}'.encode())
                data = self.sock.recv(1024)
                result = loads(data.decode())['result']
                if result['success'] == True:
                    success = True
                else:
                    log.warning(f"{self.name} color retry {tries}: {data}")
                    tries += 1
                    if tries >= 3:
                        log.error(f"{self.name} color change failed after 3 tries")
                        return
                    sleep(1)

            log.info(f"{self.name} color set to rgb({r},{g},{b}) brightness={brightness}")

        except socket.timeout as e:
            log.warning(f"{self.name} ({self.ip_addr}) color change timeout: {e}")

        except Exception as e:
            log.error(f"{self.name} color change error: {e}")
            raise(e)


    def set_color_temp(self, temp, brightness):
        try:
            success = False
            tries = 0
            if int(brightness) < 10:
                brightness = 10
            elif int(brightness) > 100:
                brightness = 100
            while success == False:
                self.sock.sendall(f'{{"id":1,"method":"setState","params":{{"temp":{temp},"dimming":{brightness}}}}}'.encode())
                data = self.sock.recv(1024)
                result = loads(data.decode())['result']
                if result['success'] == True:
                    success = True
                else:
                    log.warning(f"{self.name} temp retry {tries}: {data}")
                    tries += 1
                    if tries >= 3:
                        log.error(f"{self.name} temp change failed after 3 tries")
                        return
                    sleep(1)
            log.info(f"{self.name} temp set to {temp}K brightness={brightness}")
        except socket.timeout as e:
            log.warning(f"{self.name} ({self.ip_addr}) temp change timeout: {e}")
        except Exception as e:
            log.error(f"{self.name} temp change error: {e}")
            raise(e)

    def get_status(self, _retry=True):
        try:
            success = False
            tries = 0
            while success == False:
                self.sock.sendall(b'{"method":"getPilot","params":{}}')
                data = self.sock.recv(1024)

                result = loads(data.decode())['result']

                if 'state' in result:
                    success = True
                else:
                    log.warning(f"{self.name} get_status retry {tries}: {data}")
                    tries += 1
                    if tries >= 3:
                        log.error(f"{self.name} get_status failed after 3 tries")
                        return
                    sleep(.25)

            bulb_data = {
                "name": self.name,
                "status": result['state'],
                "ip": self.ip_addr,
                "brightness": result.get('dimming', 100),
            }

            if 'temp' in result:
                bulb_data["temp"] = result['temp']
            elif 'r' in result:
                bulb_data["r"] = result['r']
                bulb_data["g"] = result['g']
                bulb_data["b"] = result['b']
            else:
                bulb_data["r"] = 50
                bulb_data["g"] = 50
                bulb_data["b"] = 50

            return bulb_data

        except socket.timeout as e:
            if _retry:
                log.info(f"{self.name} ({self.ip_addr}) timed out, retrying...")
                self.sock.close()
                self._create_socket()
                return self.get_status(_retry=False)
            log.warning(f"{self.name} ({self.ip_addr}) offline: {e}")

        except Exception as e:
            log.error(f"{self.name} get_status error: {e}")
            raise(e)

def setBulbStatus(bulb_data):
    bulb = WizBulb(bulb_data['name'], bulb_data['ip'])
    try:
        if bulb_data['status'] == True:
            if 'temp' in bulb_data:
                bulb.set_color_temp(bulb_data['temp'], bulb_data['brightness'])
            else:
                bulb.change_color_and_brightness(bulb_data['color'][0], bulb_data['color'][1], bulb_data['color'][2], bulb_data['brightness'])
        elif bulb_data['status'] == False:
            bulb.turn_off()
        else:
            return 'bad status error'
    finally:
        bulb.close()

def getBulbStatus(bulb_data):
    bulb = WizBulb(bulb_data['name'], bulb_data['ip'])
    try:
        return bulb.get_status()
    finally:
        bulb.close()

    

# if __name__ == '__main__':
#     main()