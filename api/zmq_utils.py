import zmq
from config import environ

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