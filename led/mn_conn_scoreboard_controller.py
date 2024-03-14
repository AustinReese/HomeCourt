import threading
from lxml import html
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from pyvirtualdisplay import Display
from time import sleep
from samplebase import SampleBase
from rgbmatrix import graphics
from dotenv import load_dotenv
from os import environ

load_dotenv()

GAMES = []
GAMES_LOCK = threading.Lock()

class UpdateScoresThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.daemon = True

    def run(self):
        global GAMES
        global GAMES_LOCK

        self.display = Display(visible=0, size=(800, 600))
        self.display.start()

        service = Service(executable_path='/bin/chromedriver')

        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument('--no-sandbox')

        self.driver = webdriver.Chrome(service=service, options=chrome_options)

        league_url = environ['league_url']

        while True:

            self.driver.get(league_url)
            source_code = self.driver.find_element("xpath", "//*").get_attribute("outerHTML")
            game_trees = html.fromstring(source_code).xpath("//div[@class='teamNav']//ul//li//a")

            assert len(game_trees) == 6

            tmp_games = []

            for game_tree in game_trees:
                team_trees = game_tree.xpath("./div//em")
                score_trees = game_tree.xpath("./div//span")

                assert len(team_trees) == 2
                assert len(score_trees) == 2

                team_one_object = {
                    "teamName": team_trees[0].text,
                    "score": score_trees[0].text
                }
                team_two_object = {
                    "teamName": team_trees[1].text,
                    "score": score_trees[1].text
                }
                tmp_games.append([team_one_object, team_two_object])
            
            with GAMES_LOCK:
                GAMES = tmp_games

            sleep(30)


class MNConnScoreboard(SampleBase):
    def __init__(self, *args, **kwargs):
        super(MNConnScoreboard, self).__init__(*args, **kwargs)


    def run(self):
        global GAMES
        global GAMES_LOCK

        offscreen_canvas = self.matrix.CreateFrameCanvas()

        font7x13 = graphics.Font()
        font7x13.LoadFont("/opt/rpi-rgb-led-matrix/fonts/7x13.bdf")

        font5x8 = graphics.Font()
        font5x8.LoadFont("/opt/rpi-rgb-led-matrix/fonts/5x8.bdf")

        font4x6 = graphics.Font()
        font4x6.LoadFont("/opt/rpi-rgb-led-matrix/fonts/4x6.bdf")

        light_grey = graphics.Color(160, 160, 160)

        while len(GAMES) == 0:
            graphics.DrawText(offscreen_canvas, font7x13, 0, 21, light_grey, "Loading...")
            offscreen_canvas = self.matrix.SwapOnVSync(offscreen_canvas)
            sleep(.5)
            offscreen_canvas.Clear()
            offscreen_canvas = self.matrix.SwapOnVSync(offscreen_canvas)
            sleep(.5)
        
        while True:
            for game in GAMES:
                offscreen_canvas.Clear()
                graphics.DrawText(offscreen_canvas, font5x8, 0, 7, light_grey, game[0]['teamName'])
                graphics.DrawText(offscreen_canvas, font5x8, 0, 15, light_grey, game[0]['score'])
                graphics.DrawText(offscreen_canvas, font5x8, 0, 23, light_grey, game[1]['teamName'])
                graphics.DrawText(offscreen_canvas, font5x8, 0, 31, light_grey, game[1]['score'])

                offscreen_canvas = self.matrix.SwapOnVSync(offscreen_canvas)

                sleep(15)
            sleep(30)

def run_mn_conn_scoreboard(mn_conn_scoreboard_options):
    update_scores_thread = UpdateScoresThread()
    update_scores_thread.start()

    mn_conn_scoreboard = MNConnScoreboard()
    if (not mn_conn_scoreboard.process()):
        mn_conn_scoreboard.print_help()

