import threading
import multiprocessing
import zmq
from time import sleep
from json import loads
from clock_controller import run_clock
from mn_conn_scoreboard_controller import run_mn_conn_scoreboard
from nba_scoreboard_controller import run_nba_scoreboard
from nfl_scoreboard_controller import run_nfl_scoreboard
from test_controller import run_test
from off_controller import run_off


global CURRENT_APP
global APPS
#CURRENT_APP = {'display': 'nfl', 'nfl_live_updates': True}
#CURRENT_APP = {'display': 'nba', 'nba_live_updates': True}
#CURRENT_APP = {'display': 'mnconn'}
CURRENT_APP = {'display': 'off'}

CURRENT_APP_LOCK = threading.Lock()

class EventListener(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.daemon = True


    def run(self):
        global CURRENT_APP
        global CURRENT_APP_LOCK

        print("Listening.....")
        context = zmq.Context()
        socket = context.socket(zmq.REP)
        socket.bind("tcp://*:5556")
        while True:
            try:
                message = loads(socket.recv().decode())
                print(message)
                with CURRENT_APP_LOCK:
                    CURRENT_APP = message
                socket.send(b"Success")
            except Exception as e:
                print(e)
                socket.send(b"Error")



class LEDController():
    def __init__(self):
        self.current_controller = None
        self.monitor_controller_events()

    def set_controller(self):
        global CURRENT_APP
        try:
            print(self.current_controller)
            if self.current_controller != None:
                print("Killing existing thread")
                self.current_controller.terminate()
                self.current_controller.join()
                self.current_controller.close()
            if CURRENT_APP['display'] == "off":
                self.current_controller = multiprocessing.Process(target=run_off, args=())
                self.current_controller.start()
            elif CURRENT_APP['display'] == "test":
                self.current_controller = multiprocessing.Process(target=run_test, args=(CURRENT_APP,))
                self.current_controller.start()
            elif CURRENT_APP['display'] == "nfl":
                self.current_controller = multiprocessing.Process(target=run_nfl_scoreboard, args=(CURRENT_APP,))
                self.current_controller.start()
            elif CURRENT_APP['display'] == "nba":
                self.current_controller = multiprocessing.Process(target=run_nba_scoreboard, args=(CURRENT_APP,))
                self.current_controller.start()
            elif CURRENT_APP['display'] == "clock":
                self.current_controller = multiprocessing.Process(target=run_clock, args=(CURRENT_APP,))
                self.current_controller.start()
            elif CURRENT_APP['display'] == "mnconn":
                self.current_controller = multiprocessing.Process(target=run_mn_conn_scoreboard, args=(CURRENT_APP,))
                self.current_controller.start()
            print(f"App switched to {CURRENT_APP['display']} : {self.current_controller}")
        except Exception as e:
            print(e)

    def monitor_controller_events(self):
        global CURRENT_APP
        global CURRENT_APP_LOCK
        last_current_app = ""
        while True:
            if last_current_app != CURRENT_APP:
                with CURRENT_APP_LOCK:
                    self.set_controller()
                    last_current_app = CURRENT_APP
            else:
                sleep(.2)


def main():
    listener = EventListener()
    listener.start()
    controller = LEDController()


if __name__ == "__main__":
    main()
