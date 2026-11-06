from json import loads
from PIL import ImageColor
from time import sleep, monotonic
from datetime import datetime, timedelta, timezone
import requests
import threading
from samplebase import SampleBase
from rgbmatrix import graphics

from led_text import FONT_DIR, FONTS, layout_card
from nfl_data import AlertTracker, SCOREBOARD_URL, parse_scoreboard

# ESPN's edge blocks browser-like User-Agents on site.api.espn.com (403), so leave
# requests' default UA in place. Do not spoof a browser here.
REQUEST_TIMEOUT = 15

# ESPN caches the scoreboard for 2s, so polling faster than this buys nothing.
# Poll fast while any game is on or about to start, slowly otherwise.
LIVE_POLL_SECONDS = 5
IDLE_POLL_SECONDS = 60
ERROR_RETRY_SECONDS = 15
KICKOFF_WINDOW = timedelta(minutes=15)

GAME_SECONDS = 5
ALERT_BLINKS = 4
ALERT_SCORE_SECONDS = 6
ALERT_CARD_SECONDS = 6

# Stat card lines, top to bottom: name in white, then light tints that stay
# readable but tell the lines apart
STAT_LINE_COLORS = [(255, 255, 255), (255, 215, 110), (130, 205, 255), (150, 255, 150)]

CURRENT_GAMES = []
CURRENT_GAMES_LOCK = threading.Lock()

# Tracks the last update cycle so the display can show "Error" or "No Games"
# instead of blinking "Loading..." forever. One of: loading, ok, empty, error.
FETCH_STATUS = "loading"

# Alerts (scores, close finishes, finals) jump the queue ahead of the game rotation
ALERTS_ENABLED = False
ALERTS = []
ALERTS_LOCK = threading.Lock()


def find_game(game_id):
    with CURRENT_GAMES_LOCK:
        return next((game for game in CURRENT_GAMES if game.id == game_id), None)


def poll_seconds(games):
    soon = datetime.now(timezone.utc) + KICKOFF_WINDOW
    if any(game.status in ("live", "halftime") or (game.status == "upcoming" and game.start <= soon) for game in games):
        return LIVE_POLL_SECONDS
    return IDLE_POLL_SECONDS


class GameUpdateThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.daemon=True


    def fetch_json(self, session, url):
        # raise_for_status keeps a blocked/erroring endpoint from surfacing as a
        # confusing JSONDecodeError on the HTML error page it returns
        response = session.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return loads(response.text)


    def run(self):
        global CURRENT_GAMES
        global FETCH_STATUS
        global ALERTS

        session = requests.Session()
        tracker = AlertTracker(lambda url: self.fetch_json(session, url))

        while True:
            try:
                scoreboard = self.fetch_json(session, SCOREBOARD_URL)
                games = parse_scoreboard(scoreboard)

                # Events returned but none of them parsed means the cycle failed; surface
                # it on the display rather than sitting on "Loading..." forever. An empty
                # schedule (offseason) is not an error.
                if not games and scoreboard.get("events"):
                    raise RuntimeError(f"no games parsed from {len(scoreboard['events'])} events")

                # Publish scores before working out alerts, so the board never waits
                # on the extra play-by-play lookups
                with CURRENT_GAMES_LOCK:
                    CURRENT_GAMES = games
                FETCH_STATUS = "ok" if games else "empty"

                if ALERTS_ENABLED:
                    new_alerts = tracker.update(games)
                    if new_alerts:
                        with ALERTS_LOCK:
                            ALERTS = ALERTS + new_alerts

                sleep(poll_seconds(games))

            except Exception as e:
                print("ERROR", flush=True)
                print(e, flush=True)
                FETCH_STATUS = "error"
                # A fresh session drops any connection left in a bad state
                session = requests.Session()
                sleep(ERROR_RETRY_SECONDS)
                print("ONWARDS", flush=True)


class NFLScoreboard(SampleBase):
    def __init__(self, nfl_scoreboard_options, *args, **kwargs):
        super(NFLScoreboard, self).__init__(*args, **kwargs)
        self.nfl_scoreboard_options = nfl_scoreboard_options


    def blink_status(self, font, light_grey, red):
        """Blink one cycle of why no games are on screen."""
        if FETCH_STATUS == "error":
            message, message_color = "Error", red
        elif FETCH_STATUS == "empty":
            message, message_color = "No Games", light_grey
        else:
            message, message_color = "Loading...", light_grey

        # Clear first: the two buffers alternate, so a shorter message would
        # otherwise leave pixels behind from the previous one
        self.canvas.Clear()
        graphics.DrawText(self.canvas, font, 0, 21, message_color, message)
        self.canvas = self.matrix.SwapOnVSync(self.canvas)
        sleep(.5)
        self.canvas.Clear()
        self.canvas = self.matrix.SwapOnVSync(self.canvas)
        sleep(.5)


    def wait(self, seconds, interruptible):
        """Sleep, returning False early if an alert arrives and we may be interrupted."""
        deadline = monotonic() + seconds
        while monotonic() < deadline:
            if interruptible and ALERTS:
                return False
            sleep(.1)
        return True


    def draw_game(self, game):
        # Bottom line sits on row 31: at 32 the clock's colon lost its lower dot
        self.canvas.Clear()
        font = self.fonts["7x13"]

        a_color = graphics.Color(*ImageColor.getcolor(game.a_color, "RGB"))
        h_color = graphics.Color(*ImageColor.getcolor(game.h_color, "RGB"))
        # A trailing dash marks the team with the ball
        a_team = game.a_team + ("-" if game.possession_id == game.a_team_id else "")
        h_team = game.h_team + ("-" if game.possession_id == game.h_team_id else "")

        graphics.DrawText(self.canvas, font, 0, 10, a_color, a_team)
        graphics.DrawText(self.canvas, font, 64 - 7 * len(game.a_score), 10, a_color, game.a_score)
        graphics.DrawText(self.canvas, font, 0, 21, h_color, h_team)
        graphics.DrawText(self.canvas, font, 64 - 7 * len(game.h_score), 21, h_color, game.h_score)

        if game.status == "final":
            final = "F/OT" if game.period >= 5 else "F"
            graphics.DrawText(self.canvas, font, 0, 31, self.light_grey, game.day)
            graphics.DrawText(self.canvas, font, 64 - 7 * len(final), 31, self.light_grey, final)
        elif game.status == "live":
            graphics.DrawText(self.canvas, font, 0, 31, self.light_grey, game.display_clock)
            graphics.DrawText(self.canvas, font, 64 - 7 * len(game.quarter), 31, self.light_grey, game.quarter)
        elif game.status == "halftime":
            graphics.DrawText(self.canvas, font, 0, 31, self.light_grey, "Half")
        elif game.status == "postponed":
            graphics.DrawText(self.canvas, font, 0, 31, self.light_grey, "PPD")
        elif game.status == "upcoming":
            graphics.DrawText(self.canvas, font, 64 - 7 * len(game.day), 10, self.light_grey, game.day)
            graphics.DrawText(self.canvas, font, 64 - 7 * len(game.time), 21, self.light_grey, game.time)

        self.canvas = self.matrix.SwapOnVSync(self.canvas)


    def show_game(self, game_id, seconds, interruptible):
        """Show one game, redrawing every second so score and clock changes land as
        soon as they're fetched. Returns False if cut short by an alert."""
        deadline = monotonic() + seconds
        while monotonic() < deadline:
            game = find_game(game_id)
            if game is None:
                return True
            self.draw_game(game)
            if not self.wait(min(1, deadline - monotonic()), interruptible):
                return False
        return True


    def draw_card(self, card, line_colors=None):
        self.canvas.Clear()
        for n, (font, x, y, text) in enumerate(layout_card(card)):
            color = line_colors[n % len(line_colors)] if line_colors else self.white
            graphics.DrawText(self.canvas, self.fonts[font.name], x, y, color, text)
        self.canvas = self.matrix.SwapOnVSync(self.canvas)


    def play_alert(self, alert):
        # Alerts are white so they read on any panel; team colors stay on the scores
        for i in range(ALERT_BLINKS):
            self.draw_card(alert.flash)
            sleep(.5)
            self.canvas.Clear()
            self.canvas = self.matrix.SwapOnVSync(self.canvas)
            sleep(.25)

        self.show_game(alert.game_id, ALERT_SCORE_SECONDS, interruptible=False)

        for card in alert.cards:
            self.draw_card(card, self.stat_line_colors if alert.stat_cards else None)
            sleep(ALERT_CARD_SECONDS)


    def play_pending_alerts(self):
        global ALERTS
        while True:
            with ALERTS_LOCK:
                if not ALERTS:
                    return
                alert, ALERTS = ALERTS[0], ALERTS[1:]
            if monotonic() > alert.expires:
                print(f"Dropping stale alert: {alert}", flush=True)
                continue
            self.play_alert(alert)


    def run(self):
        self.canvas = self.matrix.CreateFrameCanvas()

        self.fonts = {}
        for spec in FONTS:
            self.fonts[spec.name] = graphics.Font()
            self.fonts[spec.name].LoadFont(f"{FONT_DIR}/{spec.name}.bdf")

        self.light_grey = graphics.Color(160, 160, 160)
        self.white = graphics.Color(255, 255, 255)
        self.stat_line_colors = [graphics.Color(*rgb) for rgb in STAT_LINE_COLORS]
        red = graphics.Color(200, 0, 0)

        while True:
            with CURRENT_GAMES_LOCK:
                game_ids = [game.id for game in CURRENT_GAMES]

            # Nothing to cycle through: blink the status rather than spinning the
            # loop with no sleep in it
            if not game_ids:
                self.blink_status(self.fonts["7x13"], self.light_grey, red)
                continue

            for game_id in game_ids:
                self.play_pending_alerts()
                self.show_game(game_id, GAME_SECONDS, interruptible=True)


# Main function
def run_nfl_scoreboard(nfl_scoreboard_options):
    global ALERTS_ENABLED
    ALERTS_ENABLED = nfl_scoreboard_options.get('nfl_live_updates', False)

    game_update_thread = GameUpdateThread()
    game_update_thread.start()

    nfl_scoreboard = NFLScoreboard(nfl_scoreboard_options)

    if (not nfl_scoreboard.process()):
        nfl_scoreboard.print_help()
