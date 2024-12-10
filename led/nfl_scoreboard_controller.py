from json import loads
from PIL import ImageColor
from time import sleep
from datetime import datetime, timezone
from requests_html import HTMLSession
import threading
from samplebase import SampleBase
from rgbmatrix import graphics

from dotenv import load_dotenv
from os import environ

load_dotenv()

CURRENT_GAMES = []
CURRENT_GAMES_LOCK = threading.Lock()

SCORING_EVENTS_ENABLED = False
SCORING_EVENTS = []
SCORING_EVENTS_LOCK = threading.Lock()


class Game():
    def __init__(self, h_team, a_team, h_score, a_score, h_color, a_color, h_alt_color, a_alt_color, display_clock, quarter, day, time, status, scoring_plays = []):
        self.h_team = h_team
        self.a_team = a_team
        self.h_score = h_score
        self.a_score = a_score
        self.h_color = h_color
        self.a_color = a_color
        self.h_alt_color = h_alt_color
        self.a_alt_color = a_alt_color
        self.display_clock = display_clock
        self.quarter = quarter
        self.day = day
        self.time = time
        self.status = status
        self.scoring_plays = scoring_plays

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
        self.daemon=True
        self.quarter_lookup = {0: "Pre", 1: "1st", 2: "2nd", 3: "3rd", 4: "4th", 5: "OT"}


    def run(self):
        global CURRENT_GAMES
        global CURRENT_GAMES_LOCK
        global SCORING_EVENTS
        global SCORING_EVENTS_LOCK
        global SCORING_EVENTS_ENABLED

        session = HTMLSession()
        nfl_url = environ["nfl_url"]

        while True:
            try:
                temp_games = []
                temp_scoring_events = []
                # Fetch all current games
                game_refs = loads(session.get(f"{nfl_url}/events").text)

                for game_ref in game_refs["items"]:
                    # Fetch game info json, assign home and away
                    game_info = loads(session.get(game_ref["$ref"]).text)
                    team_one = game_info["competitions"][0]["competitors"][0]
                    team_two = game_info["competitions"][0]["competitors"][1]
                    h_team = team_one if team_one['homeAway'] == 'home' else team_two
                    a_team = team_one if team_one['homeAway'] == 'away' else team_two

                    # Fetch home team info
                    h_team_info = loads(session.get(h_team["team"]["$ref"]).text)
                    h_team_abbr = h_team_info["abbreviation"]
                    h_team_color = '#' + h_team_info["color"]
                    h_team_alt_color = '#' + h_team_info["alternateColor"]
                    h_color_tuple = ImageColor.getcolor(h_team_color, "RGB")
                    h_team_alt_color_tuple = ImageColor.getcolor(h_team_alt_color, "RGB")

                    # Make sure color is light enough to be visible on LED
                    if sum(h_color_tuple) < 25:
                        h_team_color = '#' + h_team_info["alternateColor"]
                        h_color_tuple = ImageColor.getcolor(h_team_color, "RGB")
                        if sum(h_color_tuple) < 25:
                            h_team_color = "#a0a0a0"
                    
                    if sum(h_team_alt_color_tuple) < 25:
                        h_team_alt_color = "#a0a0a0"

                    # Fetch away team info
                    a_team_info = loads(session.get(a_team["team"]["$ref"]).text)
                    a_team_abbr = a_team_info["abbreviation"]
                    a_team_color = '#' + a_team_info["color"]
                    a_team_alt_color = '#' + a_team_info["alternateColor"]
                    a_color_tuple = ImageColor.getcolor(a_team_color, "RGB")
                    a_team_alt_color_tuple = ImageColor.getcolor(a_team_alt_color, "RGB")

                    # Make sure color is light enough to be visible on LED
                    if sum(a_color_tuple) < 25:
                        a_team_color = '#' + a_team_info["alternateColor"]
                        a_color_tuple = ImageColor.getcolor(a_team_color, "RGB")
                        if sum(a_color_tuple) < 25:
                            a_team_color = "#a0a0a0"

                    if sum(a_team_alt_color_tuple) < 25:
                        a_team_alt_color = "#a0a0a0"

                    # Fetch game details
                    game_status = loads(session.get(game_info["competitions"][0]["status"]["$ref"]).text)
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

                    # Fetch game scores if necessary
                    if status != "upcoming":
                        h_team_score = loads(session.get(h_team["score"]["$ref"]).text)["displayValue"]
                        a_team_score = loads(session.get(a_team["score"]["$ref"]).text)["displayValue"]
                    else:
                        h_team_score = ""
                        a_team_score = ""

                    # Add possession arrow if necessary
                    if status == "live":
                        game_drives = loads(session.get(game_info["competitions"][0]["drives"]["$ref"]).text)
                        team_with_possession_info = loads(session.get(game_drives["items"][-1]["team"]["$ref"]).text)
                        if a_team_abbr == team_with_possession_info["abbreviation"]:
                            a_team_abbr = a_team_abbr + "-"
                        elif h_team_abbr == team_with_possession_info["abbreviation"]:
                            h_team_abbr = h_team_abbr + "-"


                    game_to_add = Game(h_team_abbr, a_team_abbr, h_team_score, a_team_score, h_team_color, a_team_color,
                                        h_team_alt_color, a_team_alt_color, display_clock, quarter, day, time, status, )
                    
                    
                    # Live updates block
                    if SCORING_EVENTS_ENABLED == True:
                        game_id = game_info['id'] 
                        play_by_play = loads(session.get(f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event={game_id}").text)
                        if 'scoringPlays' in play_by_play:
                            scoring_plays = play_by_play['scoringPlays']
                        else:
                            scoring_plays = []
                        game_to_add.scoring_plays = scoring_plays

                        previous_game_object = [x for x in CURRENT_GAMES if x.h_team.replace('-', '') == game_to_add.h_team.replace('-', '')]
                        
                        if len(previous_game_object) == 1:
                            
                            previous_game_object = previous_game_object[0]
                            
                            if previous_game_object.status == 'live' and len(game_to_add.scoring_plays) > len(previous_game_object.scoring_plays):
                            # for debug
                            # if previous_game_object.status != 'live':
                                latest_scoring_play = scoring_plays[len(scoring_plays) - 1]
                                scoring_team_abbr = latest_scoring_play['team']['abbreviation'].upper()
                                if game_to_add.h_team.replace('-', '') == scoring_team_abbr:
                                    scoring_team = game_to_add.h_team.replace('-', '')
                                    scoring_team_color = game_to_add.h_color
                                    scoring_team_alt_color = game_to_add.h_alt_color
                                elif game_to_add.a_team.replace('-', '') == scoring_team_abbr:
                                    scoring_team = game_to_add.a_team.replace('-', '')
                                    scoring_team_color = game_to_add.a_color
                                    scoring_team_alt_color = game_to_add.a_alt_color
                                else:
                                    print("WHAT!?!?!?!")

                                temp_scoring_events.append((latest_scoring_play['scoringType']['displayName'], latest_scoring_play['text'], scoring_team, scoring_team_color, scoring_team_alt_color))
                                print(latest_scoring_play['scoringType']['displayName'], latest_scoring_play['text'])

                    temp_games.append(game_to_add)

                with CURRENT_GAMES_LOCK:
                    CURRENT_GAMES = temp_games

                with SCORING_EVENTS_LOCK:
                    SCORING_EVENTS = SCORING_EVENTS + temp_scoring_events

                sleep(30)

            except Exception as e:
                print("ERROR")
                print(e)
                sleep(15)
                print("ONWARDS")


class NFLScoreboard(SampleBase):
    def __init__(self, nfl_scoreboard_options, *args, **kwargs):
        super(NFLScoreboard, self).__init__(*args, **kwargs)
        self.nfl_scoreboard_options = nfl_scoreboard_options


    def run(self):
        global CURRENT_GAMES
        global CURRENT_GAMES_LOCK
        global SCORING_EVENTS
        global SCORING_EVENTS_ENABLED
        global SCORING_EVENTS_LOCK

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
            
            if SCORING_EVENTS_ENABLED == True:
                with SCORING_EVENTS_LOCK:
                    scoring_events_copy = SCORING_EVENTS
                    SCORING_EVENTS = []
                
                for scoring_event in scoring_events_copy:

                    offscreen_canvas.Clear()
                                        
                    font_width = 4
                    font_height = 6
                    chars_per_row = int(64 / font_width)
                    row_count = int(32 / font_height)

                    words_to_display = scoring_event[1].split()

                    scoring_team_color_tuple = ImageColor.getcolor(scoring_event[3], "RGB")
                    scoring_team_color = graphics.Color(scoring_team_color_tuple[0], scoring_team_color_tuple[1], scoring_team_color_tuple[2])

                    scoring_team_alt_color_tuple = ImageColor.getcolor(scoring_event[4], "RGB")
                    scoring_team_alt_color = graphics.Color(scoring_team_alt_color_tuple[0], scoring_team_alt_color_tuple[1], scoring_team_alt_color_tuple[2])

                    for i in range(5):
                        graphics.DrawText(offscreen_canvas, font7x13, 0, 12, scoring_team_alt_color, scoring_event[0])
                        graphics.DrawText(offscreen_canvas, font7x13, 0, 30, scoring_team_color, scoring_event[2])

                        offscreen_canvas = self.matrix.SwapOnVSync(offscreen_canvas)
                        sleep(.5)
                        offscreen_canvas.Clear()
                        offscreen_canvas = self.matrix.SwapOnVSync(offscreen_canvas)
                        sleep(.5)
                    
                    offscreen_canvas.Clear()
                    offscreen_canvas = self.matrix.SwapOnVSync(offscreen_canvas)

                    for row_number in range(row_count):
                        row_string = ''
                        row_filled = False

                        while row_filled == False and len(words_to_display) > 0:
                            if len(row_string + words_to_display[0]) > chars_per_row:
                                row_filled = True
                                continue
                            row_string += f'{words_to_display[0]} '
                            del words_to_display[0]
                        
                        row_string = row_string.strip()
                        print(row_string)
                        graphics.DrawText(offscreen_canvas, font4x6, 0, 5 + (row_number * font_height), scoring_team_color, row_string)
                    offscreen_canvas = self.matrix.SwapOnVSync(offscreen_canvas)
                    sleep(15)


# Main function
def run_nfl_scoreboard(nfl_scoreboard_options):
    global SCORING_EVENTS_ENABLED
    SCORING_EVENTS_ENABLED = nfl_scoreboard_options['nfl_live_updates']

    game_update_thread = GameUpdateThread()
    game_update_thread.start()
    
    nfl_scoreboard = NFLScoreboard(nfl_scoreboard_options)

    if (not nfl_scoreboard.process()):
        nfl_scoreboard.print_help()
