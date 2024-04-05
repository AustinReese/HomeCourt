import threading
from datetime import datetime, timezone
from samplebase import SampleBase
from rgbmatrix import graphics
from json import loads
from PIL import ImageColor
from time import sleep
from requests_html import HTMLSession

from dotenv import load_dotenv
from os import environ

load_dotenv()

CURRENT_GAMES = []
CURRENT_GAMES_LOCK = threading.Lock()

class Game():
    def __init__(self, h_team, a_team, h_score, a_score, h_color, a_color, display_clock, quarter, day, time, status):
        self.h_team = h_team
        self.a_team = a_team
        self.h_score = h_score
        self.a_score = a_score
        self.h_color = h_color
        self.a_color = a_color
        self.display_clock = display_clock
        self.quarter = quarter
        self.day = day
        self.time = time
        self.status = status

    def __str__(self):
        if self.status == "live":
            return f"{self.h_team:9}{self.h_score}\n{self.a_team:9}{self.a_score}\n{self.display_clock:9}{self.quarter}"
        elif self.status == "final":
            return f"{self.h_team:9}{self.h_score}\n{self.a_team:9}{self.a_score}\n{self.day:9}F"
        else:
            return f"{self.h_team:9}{self.day}\n{self.a_team:9}{self.time}"


class GameUpdateThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.daemon = True
        self.quarter_lookup = {0: "Pre", 1: "1st", 2: "2nd", 3: "3rd", 4: "4th", 5: "OT"}

    def run(self):
        global CURRENT_GAMES
        global CURRENT_GAMES_LOCK

        session = HTMLSession()
        while True:

            temp_games = []
            page_request = session.get(environ['nba_url'])
            games_dict = loads(page_request.content)
            for game_info in games_dict['events']:
                # Fetch game info json, assign home and away
                team_one = game_info["competitions"][0]["competitors"][0]
                team_two = game_info["competitions"][0]["competitors"][1]
                h_team_info = team_one if team_one['homeAway'] == 'home' else team_two
                a_team_info = team_one if team_one['homeAway'] == 'away' else team_two

                # Fetch home team info
                h_team_abbr = h_team_info["team"]["abbreviation"]
                h_team_color = '#' + h_team_info["team"]["color"]
                h_color_tuple = ImageColor.getcolor(h_team_color, "RGB")

                # Make sure color is light enough to be visible on LED
                if sum(h_color_tuple) < 25:
                    h_team_color = '#' + h_team_info["team"]["alternateColor"]
                    h_color_tuple = ImageColor.getcolor(h_team_color, "RGB")
                    if sum(h_color_tuple) < 25:
                        h_team_color = "#ffffff"

                # Fetch away team info
                a_team_abbr = a_team_info["team"]["abbreviation"]
                a_team_color = '#' + a_team_info["team"]["color"]
                a_color_tuple = ImageColor.getcolor(a_team_color, "RGB")

                # Make sure color is light enough to be visible on LED
                if sum(a_color_tuple) < 25:
                    a_team_color = '#' + a_team_info["team"]["alternateColor"]
                    a_color_tuple = ImageColor.getcolor(a_team_color, "RGB")
                    if sum(a_color_tuple) < 25:
                        a_team_color = "#ffffff"

                # Fetch game details
                game_status = game_info["competitions"][0]["status"]
                display_clock = game_status["displayClock"]
                quarter = self.quarter_lookup[game_status["period"]]

                game_datetime_utc = datetime.strptime(game_info["competitions"][0]["date"], "%Y-%m-%dT%H:%MZ")
                game_datetime_local = game_datetime_utc.replace(tzinfo=timezone.utc).astimezone(tz=None)
                day = f"{game_datetime_local.month}/{game_datetime_local.day}"
                time = f"{game_datetime_local.hour if game_datetime_local.hour <= 12 else game_datetime_local.hour % 12}:{game_datetime_local.minute if len(str(game_datetime_local.minute)) == 2 else '0' + str(game_datetime_local.minute)}"

                status = "live"
                if game_status["type"]["state"].lower() == "pre":
                    status = "upcoming"
                elif game_status["type"]["completed"] is True:
                    status = "final"
                elif game_status["type"]["name"] == "STATUS_HALFTIME":
                    status = "halftime"
                if status != "upcoming":
                    h_team_score = h_team_info["score"]
                    a_team_score = a_team_info["score"]
                else:
                    h_team_score = ""
                    a_team_score = ""

                game_to_add = Game(h_team_abbr, a_team_abbr, h_team_score, a_team_score, h_team_color, a_team_color,
                                   display_clock, quarter, day, time, status)
                print(game_to_add)
                print()

                temp_games.append(game_to_add)

            with CURRENT_GAMES_LOCK:
                CURRENT_GAMES = temp_games

            sleep(30)



class NBAScoreboard(SampleBase):
    def __init__(self, *args, **kwargs):
        super(NBAScoreboard, self).__init__(*args, **kwargs)

    def run(self):
        global CURRENT_GAMES
        global CURRENT_GAMES_LOCK

        offscreen_canvas = self.matrix.CreateFrameCanvas()

        font7x13 = graphics.Font()
        font7x13.LoadFont("/opt/rpi-rgb-led-matrix/fonts/7x13.bdf")

        font4x6 = graphics.Font()
        font4x6.LoadFont("/opt/rpi-rgb-led-matrix/fonts/4x6.bdf")

        light_grey = graphics.Color(160, 160, 160)

        while len(CURRENT_GAMES) == 0:
            graphics.DrawText(offscreen_canvas, font7x13, 0, 21, light_grey, "Loading...")
            offscreen_canvas = self.matrix.SwapOnVSync(offscreen_canvas)
            sleep(.5)
            offscreen_canvas.Clear()
            offscreen_canvas = self.matrix.SwapOnVSync(offscreen_canvas)
            sleep(.5)

        while True:

            with CURRENT_GAMES_LOCK:
                current_games_copy = CURRENT_GAMES
            for game in current_games_copy:

                offscreen_canvas.Clear()

                a_score_len = 7 * len(game.a_score)
                a_score_offset = 64 - a_score_len
                a_color_tuple = ImageColor.getcolor(game.a_color, "RGB")
                a_color = graphics.Color(a_color_tuple[0], a_color_tuple[1], a_color_tuple[2])
                graphics.DrawText(offscreen_canvas, font7x13, 0, 10, a_color, game.a_team)
                graphics.DrawText(offscreen_canvas, font7x13, a_score_offset, 10, a_color, game.a_score)

                h_score_len = 7 * len(game.h_score)
                h_score_offset = 64 - h_score_len
                h_color_tuple = ImageColor.getcolor(game.h_color, "RGB")
                h_color = graphics.Color(h_color_tuple[0], h_color_tuple[1], h_color_tuple[2])
                graphics.DrawText(offscreen_canvas, font7x13, 0, 21, h_color, game.h_team)
                graphics.DrawText(offscreen_canvas, font7x13, h_score_offset, 21, h_color, game.h_score)

                if game.status == "final":
                    graphics.DrawText(offscreen_canvas, font7x13, 0, 32, light_grey, game.day)
                    graphics.DrawText(offscreen_canvas, font7x13, 57, 32, light_grey, "F")
                elif game.status == "live":
                    graphics.DrawText(offscreen_canvas, font7x13, 0, 32, light_grey, game.display_clock)
                    if game.quarter != "OT":
                        graphics.DrawText(offscreen_canvas, font7x13, 43, 32, light_grey, game.quarter)
                    else:
                        graphics.DrawText(offscreen_canvas, font7x13, 50, 32, light_grey, game.quarter)
                elif game.status == "halftime":
                    graphics.DrawText(offscreen_canvas, font7x13, 0, 32, light_grey, "Half")
                elif game.status == "upcoming":
                    game_day_offset = 64 - (len(game.day) * 7)
                    graphics.DrawText(offscreen_canvas, font7x13, game_day_offset, 10, light_grey, game.day)
                    game_time_offset = 64 - (len(game.time) * 7)
                    graphics.DrawText(offscreen_canvas, font7x13, game_time_offset, 21, light_grey, game.time)


                offscreen_canvas = self.matrix.SwapOnVSync(offscreen_canvas)
                sleep(5)


# Main function
def run_nba_scoreboard(nba_scoreboard_options):
    game_update_thread = GameUpdateThread()
    game_update_thread.start()

    nba_scoreboard = NBAScoreboard(nba_scoreboard_options)
    
    if (not nba_scoreboard.process()):
        nba_scoreboard.print_help()
