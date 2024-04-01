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
                print(result)
                if result['success'] == True:
                    success = True
                else:
                    print("Error:", data)
                    tries += 1
                    if tries >= 3:
                        print('failure')
                    sleep(1)
        
            print('success')
        except Exception as e:
            print(e)
            print('error')

            

    def change_color_and_brightness(self, r, g, b, brightness):
        try:
            if any(not x for x in (r, g, b, brightness)):
                print("Bad valued passed:", r, g, b, brightness)
                print('error')

            success = False
            tries = 0
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
                    print("Error:", data)
                    tries += 1
                    if tries >= 3:
                        print('failure')
                    sleep(1)
        
            print('success')

        except Exception as e:
            raise(e)
            print('error')


def setBulbStatus(bulb_data):


    bulb = WizBulb(bulb_data['ip'])



    if bulb_data['status'] == True:
        bulb.change_color_and_brightness(bulb_data['color'][0], bulb_data['color'][1], bulb_data['color'][2], bulb_data['brightness'])
    elif bulb_data['status'] == False:
        bulb.turn_off()
    else:
        return 'bad status error'

    

# if __name__ == '__main__':
#     main()