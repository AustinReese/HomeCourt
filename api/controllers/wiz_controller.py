from dotenv import load_dotenv
from os import environ
from time import sleep
from json import loads
import socket

load_dotenv()

class WizBulb():
    def __init__(self, name, ip_addr):
        self.name = name
        self.ip_addr = ip_addr
        self.sock = socket.socket(socket.AF_INET,
                    socket.SOCK_DGRAM)
        self.sock.settimeout(5)
        self.sock.connect((self.ip_addr, 38899))
        
    def turn_on(self):
        try:
            success = False
            tries = 0
            while success == False:
                self.sock.sendall(b'{"id":1,"method":"setState","params":{"state":true}}')
                data = self.sock.recv(1024)
                print(data)
                result = loads(data.decode())['result']
                if result['success'] == True:
                    success = True
                else:
                    print("Error:", data)
                    tries += 1
                    if tries >= 3:
                        print('failure')
                    sleep(1)
            
            print('success')

        except socket.timeout as e:
            print(f"{self.name} ({self.ip_addr}) appears to be offline:")
            print(e)

        except Exception as e:
            print(e)
            print('error')

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
                    if tries >= 3:
                        print('failure')
                    sleep(1)
        
            print('success')

        except socket.timeout as e:
            print(f"{self.name} ({self.ip_addr}) appears to be offline:")
            print(e)

        except Exception as e:
            print(e)
            print('error')

            

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
                print(r, g, b)
                self.sock.sendall(f'{{"id":1,"method":"setState","params":{{"r":{r},"g":{g},"b":{b},"dimming": {brightness}}}}}'.encode())
                data = self.sock.recv(1024)
                result = loads(data.decode())['result']
                if result['success'] == True:
                    success = True
                else:
                    print("Error:", data)
                    tries += 1
                    if tries >= 3:
                        print('failure')
                    sleep(1)
        
            print('success')
        
        except socket.timeout as e:
            print(f"{self.name} ({self.ip_addr}) appears to be offline:")
            print(e)

        except Exception as e:
            raise(e)
            print('error')


    def get_status(self):
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
                    print("Error:", data)
                    tries += 1
                    if tries >= 3:
                        print('failure')
                        return
                    sleep(.25)

            if 'r' not in result:
                result['r'] = 50
                result['g'] = 50
                result['b'] = 50
            
            bulb_data = {
                "name": self.name,
                "status": result['state'],
                "ip": self.ip_addr,
                "r": result['r'],
                "g": result['g'],
                "b": result['b'],
                "brightness":  result['dimming'],
            }
            
            return bulb_data
        
        except socket.timeout as e:
            print(f"{self.name} ({self.ip_addr}) appears to be offline:")
            print(e)
        
        except Exception as e:
            raise(e)
            print('error')

def setBulbStatus(bulb_data):
    bulb = WizBulb(bulb_data['name'], bulb_data['ip'])

    if bulb_data['status'] == True:
        bulb.change_color_and_brightness(bulb_data['color'][0], bulb_data['color'][1], bulb_data['color'][2], bulb_data['brightness'])
    elif bulb_data['status'] == False:
        bulb.turn_off()
    else:
        return 'bad status error'

def getBulbStatus(bulb_data):
    bulb = WizBulb(bulb_data['name'], bulb_data['ip'])

    return bulb.get_status()

    

# if __name__ == '__main__':
#     main()