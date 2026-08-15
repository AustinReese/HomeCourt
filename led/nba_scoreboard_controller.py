import threading
from datetime import datetime, timezone
from samplebase import SampleBase
from rgbmatrix import graphics
from json import loads
from PIL import ImageColor
from time import sleep
import requests

from dotenv import load_dotenv
from os import environ

load_dotenv()

# ESPN's edge blocks browser-like User-Agents on site.api.espn.com (403), so leave
# requests' default UA in place. Do not spoof a browser here.
REQUEST_TIMEOUT = 15

CURRENT_GAMES = []
CURRENT_GAMES_LOCK = threading.Lock()

# Tracks the last update cycle so the display can show "Error" or "No Games"
# instead of blinking "Loading..." forever. One of: loading, ok, empty, error.
FETCH_STATUS = "loading"

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

    def fetch_json(self, session, url):
        # raise_for_status keeps a blocked/erroring endpoint from surfacing as a
        # confusing JSONDecodeError on the HTML error page it returns
        response = session.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return loads(response.text)

    def run(self):
        global CURRENT_GAMES
        global CURRENT_GAMES_LOCK
        global FETCH_STATUS

        while True:
            try:
                session = requests.Session()

                temp_games = []
                games_dict = self.fetch_json(session, environ['nba_url'])

                for game_info in games_dict['events']:
                    # One unparseable game shouldn't blank out the whole board
                    try:
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
                        # Unknown/extra periods (2OT and beyond) shouldn't drop the game
                        quarter = self.quarter_lookup.get(game_status["period"], "OT")

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

                        temp_games.append(game_to_add)

                    except Exception as e:
                        print(f"Skipping game {game_info.get('id')}: {e}", flush=True)

                # Events returned but none of them parsed means the cycle failed; surface
                # it on the display rather than sitting on "Loading..." forever. An empty
                # schedule (offseason) is not an error.
                if not temp_games and games_dict['events']:
                    raise RuntimeError(f"no games parsed from {len(games_dict['events'])} events")

                with CURRENT_GAMES_LOCK:
                    CURRENT_GAMES = temp_games

                FETCH_STATUS = "ok" if temp_games else "empty"

                sleep(30)

            except Exception as e:
                print("ERROR", flush=True)
                print(e, flush=True)
                FETCH_STATUS = "error"
                sleep(15)
                print("ONWARDS", flush=True)



class NBAScoreboard(SampleBase):
    def __init__(self, *args, **kwargs):
        super(NBAScoreboard, self).__init__(*args, **kwargs)

    def blink_status(self, offscreen_canvas, font, light_grey, red):
        """Blink one cycle of why no games are on screen. Returns the next canvas."""
        if FETCH_STATUS == "error":
            message, message_color = "Error", red
        elif FETCH_STATUS == "empty":
            message, message_color = "No Games", light_grey
        else:
            message, message_color = "Loading...", light_grey

        # Clear first: the two buffers alternate, so a shorter message would
        # otherwise leave pixels behind from the previous one
        offscreen_canvas.Clear()
        graphics.DrawText(offscreen_canvas, font, 0, 21, message_color, message)
        offscreen_canvas = self.matrix.SwapOnVSync(offscreen_canvas)
        sleep(.5)
        offscreen_canvas.Clear()
        offscreen_canvas = self.matrix.SwapOnVSync(offscreen_canvas)
        sleep(.5)
        return offscreen_canvas

    def run(self):
        global CURRENT_GAMES
        global CURRENT_GAMES_LOCK
        global FETCH_STATUS

        offscreen_canvas = self.matrix.CreateFrameCanvas()

        font7x13 = graphics.Font()
        font7x13.LoadFont("/opt/rpi-rgb-led-matrix/fonts/7x13.bdf")

        font4x6 = graphics.Font()
        font4x6.LoadFont("/opt/rpi-rgb-led-matrix/fonts/4x6.bdf")

        light_grey = graphics.Color(160, 160, 160)
        red = graphics.Color(200, 0, 0)

        # Wait for the first batch of games, reporting why nothing is showing yet
        while len(CURRENT_GAMES) == 0:
            offscreen_canvas = self.blink_status(offscreen_canvas, font7x13, light_grey, red)

        while True:

            with CURRENT_GAMES_LOCK:
                current_games_copy = CURRENT_GAMES

            # Nothing to cycle through: blink the status rather than spinning the
            # loop with no sleep in it
            if not current_games_copy:
                offscreen_canvas = self.blink_status(offscreen_canvas, font7x13, light_grey, red)
                continue

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
