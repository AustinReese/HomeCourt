from dotenv import load_dotenv
from os import environ
from time import sleep
from json import loads
import socket

load_dotenv()

class WizBulb():
    def __init__(self, ip_addr):
        self.ip_addr = ip_addr
        self.sock = socket.socket(socket.AF_INET,
                    socket.SOCK_DGRAM)
        self.sock.connect((self.ip_addr, 38899))
        
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
                    print("Error:", data)
                    tries += 1
                    if tries >= 10:
                        break
                    sleep(3)

        except Exception as e:
            print(e)
            print(e.with_traceback())

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
                    print("Error:", data)
                    tries += 1
                    if tries >= 10:
                        break
                    sleep(3)

        except Exception as e:
            print(e)
            

    def change_color_and_brightness(self, r, g, b, brightness):
        try:
            success = False
            tries = 0
            while success == False:
                self.sock.sendall(f'{{"id":1,"method":"setState","params":{{"r":{r},"g":{g},"b":{b},"dimming": {brightness}}}}}'.encode())
                data = self.sock.recv(1024)
                result = loads(data.decode())['result']
                if result['success'] == True:
                    success = True
                else:
                    print("Error:", data)
                    tries += 1
                    if tries >= 10:
                        break
                    sleep(3)

        except Exception as e:
            raise(e)


def main():
    bulbs = {}
    for env_var_key, env_var_value in environ.items():
        if env_var_key[:3] == 'wiz':
            bulbs[env_var_key] = WizBulb(env_var_value)
    
    while True:
        for _, bulb in bulbs.items():
            bulb.change_color_and_brightness(255, 60, 60, 100)
            bulb.turn_on()
            sleep(5)
            bulb.turn_off()
            sleep(5)

if __name__ == '__main__':
    main()