import zmq
from config import environ


def zmqExchange(message, timeout_ms=None):
    """Send a message to the LED controller and return its reply.

    timeout_ms bounds the wait so a stopped pi-led.service can't hang a Flask
    worker forever; without it the REQ socket blocks indefinitely.
    """
    if environ['container'] == 'false':
        context = zmq.Context()
        socket = context.socket(zmq.REQ)
        if timeout_ms is not None:
            socket.setsockopt(zmq.RCVTIMEO, timeout_ms)
            socket.setsockopt(zmq.SNDTIMEO, timeout_ms)
            socket.setsockopt(zmq.LINGER, 0)
        socket.connect(f"tcp://{environ['led_host']}:5556")
        try:
            socket.send(message.encode())
            response = socket.recv().decode()
        finally:
            socket.close()
        return response
    else:
        print(message)
        return
