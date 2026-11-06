"""ESPN NFL data for the scoreboard: parses the scoreboard feed and turns successive
snapshots into alerts. No rgbmatrix import, so it can be exercised off the Pi."""
import re
from datetime import datetime, timezone
from time import monotonic

from PIL import ImageColor

# One request returns every game this week with scores, clock, and situation.
# ESPN caches it for 2s.
SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
SUMMARY_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event={event_id}"
# The core API is the only place that says who played which role in a play
PLAY_URL = "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/events/{event_id}/competitions/{event_id}/plays/{play_id}"

# Close game: the team with the ball is tied or trailing by at most a touchdown
# plus two, with the game clock nearly out (or in overtime)
CLOSE_GAME_SECONDS = 180
CLOSE_GAME_MAX_DEFICIT = 7

# How long a score change may go unmatched by the play-by-play feed before we stop looking
SCORE_PENDING_SECONDS = 180

# Alerts that can't be shown by then are stale. A close-game situation goes out of
# date fast; scores and finals stay worth showing a while.
CLOSE_GAME_ALERT_TTL = 60
SCORE_ALERT_TTL = 600

QUARTERS = {0: "Pre", 1: "1st", 2: "2nd", 3: "3rd", 4: "4th", 5: "OT"}
SCORE_TITLES = {"touchdown": "TOUCHDOWN", "field-goal": "FIELD GOAL", "safety": "SAFETY"}
NAME_SUFFIXES = {"JR.", "JR", "SR.", "SR", "II", "III", "IV", "V"}


def _visible_color(color, fallback):
    """Team colors too dark to show up on the LEDs fall back to the alternate, then grey."""
    for candidate in (color, fallback):
        if candidate and sum(ImageColor.getcolor('#' + candidate, "RGB")) >= 25:
            return '#' + candidate
    return "#a0a0a0"


def _local_start(date_text):
    for fmt in ("%Y-%m-%dT%H:%MZ", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(date_text, fmt).replace(tzinfo=timezone.utc).astimezone(tz=None)
        except ValueError:
            pass
    raise ValueError(f"unrecognized date {date_text}")


class Game():
    def __init__(self, event):
        competition = event["competitions"][0]
        home = next(c for c in competition["competitors"] if c["homeAway"] == "home")
        away = next(c for c in competition["competitors"] if c["homeAway"] == "away")
        status = event.get("status") or competition["status"]
        situation = competition.get("situation") or {}

        self.id = event["id"]
        self.h_team_id = home["team"]["id"]
        self.a_team_id = away["team"]["id"]
        self.h_team = home["team"]["abbreviation"]
        self.a_team = away["team"]["abbreviation"]
        self.h_color = _visible_color(home["team"].get("color"), home["team"].get("alternateColor"))
        self.a_color = _visible_color(away["team"].get("color"), away["team"].get("alternateColor"))

        state = status["type"]["state"]
        if state == "pre":
            self.status = "upcoming"
        elif status["type"]["completed"]:
            self.status = "final"
        elif state == "post":
            # Postponed, canceled, or suspended
            self.status = "postponed"
        elif status["type"]["name"] == "STATUS_HALFTIME":
            self.status = "halftime"
        else:
            self.status = "live"

        self.h_points = int(home.get("score") or 0)
        self.a_points = int(away.get("score") or 0)
        started = self.status not in ("upcoming", "postponed")
        self.h_score = str(self.h_points) if started else ""
        self.a_score = str(self.a_points) if started else ""

        self.period = status.get("period", 0)
        self.quarter = QUARTERS.get(self.period, f"{self.period - 4}OT")
        self.display_clock = status.get("displayClock", "")
        self.clock_seconds = float(status.get("clock") or 0)

        self.start = _local_start(event["date"])
        self.day = f"{self.start.month}/{self.start.day}"
        self.time = f"{self.start.hour % 12 or 12}:{self.start.minute:02d}"

        # ESPN drops "possession" between some plays; callers treat None as unknown
        self.possession_id = situation.get("possession") if self.status == "live" else None
        self.down_distance = situation.get("shortDownDistanceText", "")
        self.yard_line = situation.get("possessionText", "")
        self.h_timeouts = situation.get("homeTimeouts")
        self.a_timeouts = situation.get("awayTimeouts")

    def side(self, team_id):
        """(abbr, points, timeouts, opponent points) for one team."""
        if team_id == self.h_team_id:
            return self.h_team, self.h_points, self.h_timeouts, self.a_points
        return self.a_team, self.a_points, self.a_timeouts, self.h_points

    def __str__(self):
        return f"{self.a_team} {self.a_score} @ {self.h_team} {self.h_score} ({self.status} {self.display_clock} {self.quarter})"


def parse_scoreboard(scoreboard):
    games = []
    for event in scoreboard.get("events", []):
        # One unparseable game shouldn't blank out the whole board
        try:
            games.append(Game(event))
        except Exception as e:
            print(f"Skipping game {event.get('id')}: {e}", flush=True)
    return games


class Alert():
    def __init__(self, game_id, flash, cards=(), ttl=SCORE_ALERT_TTL, stat_cards=False):
        self.game_id = game_id
        # Lines blinked first, then the game's score, then each card in turn.
        # A card is a list of lines or a string of free text (see led_text.layout_card).
        self.flash = flash
        self.cards = list(cards)
        self.expires = monotonic() + ttl
        # Player stat cards tint each line so the lines are easy to tell apart
        self.stat_cards = stat_cards

    def __str__(self):
        return f"{' '.join(self.flash)} {self.cards}"


def short_name(display_name):
    """'Baker Mayfield' -> 'B.MAYFIELD', 'Chris Godwin Jr.' -> 'C.GODWIN'."""
    parts = [p for p in display_name.upper().split() if p not in NAME_SUFFIXES]
    if len(parts) < 2:
        return " ".join(parts)
    return f"{parts[0][0]}.{' '.join(parts[1:])}"


def boxscore_players(summary):
    """athlete id -> {"name": display name, <category>: {label: value}}"""
    players = {}
    for team in summary.get("boxscore", {}).get("players", []):
        for category in team.get("statistics", []):
            labels = category.get("labels", [])
            for entry in category.get("athletes", []):
                athlete = entry["athlete"]
                player = players.setdefault(athlete["id"], {"name": athlete["displayName"]})
                player[category["name"]] = dict(zip(labels, entry.get("stats", [])))
    return players


# In-game stat lines per role, at most 16 characters so they fit the small font
ROLE_STAT_LINES = {
    "passing": lambda s: [f"{s['C/ATT']} {s['YDS']} YDS", f"{s['TD']} TD {s['INT']} INT"],
    "rushing": lambda s: [f"{s['CAR']} CAR {s['YDS']} YDS", f"{s['TD']} TD {s['AVG']} AVG"],
    "receiving": lambda s: [f"{s['REC']} REC {s['YDS']} YDS", f"{s['TD']} TD LNG {s['LONG']}"],
}
# Defensive and return scorers: whichever of these they have, in this order
OTHER_STAT_LINES = [
    ("interceptions", lambda s: f"{s['INT']} INT {s['YDS']} YDS"),
    ("kickReturns", lambda s: f"{s['NO']} KR {s['YDS']} YDS"),
    ("puntReturns", lambda s: f"{s['NO']} PR {s['YDS']} YDS"),
    ("fumbles", lambda s: f"{s['REC']} FUM REC"),
    ("defensive", lambda s: f"{s['TOT']} TKL {s['SACKS']} SACK"),
]
ROLE_PLAY_WORDS = {"passing": "TD PASS", "rushing": "TD RUN", "receiving": "TD REC"}
# Return/defensive touchdowns, matched against the play type ("Interception Return Touchdown")
RETURN_PLAY_WORDS = [("Blocked", "BLK TD"), ("Interception", "INT TD"), ("Kickoff", "KR TD"),
                     ("Punt", "PR TD"), ("Fumble", "FUM TD")]


def _all_zero(line):
    numbers = re.findall(r"\d+(?:\.\d+)?", line)
    return bool(numbers) and all(float(n) == 0 for n in numbers)


def player_card(player, role, yards, play_type=""):
    play_words = ROLE_PLAY_WORDS.get(role) or next((words for key, words in RETURN_PLAY_WORDS if key in play_type), "TD")
    play_line = play_words if yards is None else f"{yards} YD {play_words}"
    if role in ROLE_STAT_LINES and role in player:
        stat_lines = ROLE_STAT_LINES[role](player[role])
    else:
        # "0 TKL 0 SACK" says nothing about a defender who just scored
        stat_lines = [line(player[name]) for name, line in OTHER_STAT_LINES if name in player]
        stat_lines = [line for line in stat_lines if not _all_zero(line)][:2]
    return [short_name(player["name"]), play_line] + stat_lines


def _play_total(play):
    return int(play.get("awayScore") or 0) + int(play.get("homeScore") or 0)


class GameState():
    """What the tracker remembers about one game between scoreboard polls."""
    def __init__(self, game):
        self.status = game.status
        # Points already accounted for by alerts (or present when we first saw the game)
        self.scored_total = game.a_points + game.h_points
        self.pending_since = None
        self.alerted_plays = set()
        self.possession_id = game.possession_id
        self.drive = 0
        self.close_alerted_drive = None


class AlertTracker():
    """Compares each scoreboard snapshot with the last one and returns new alerts:
    scores (with player stats on touchdowns), close finishes, and final scores."""
    def __init__(self, fetch_json):
        self.fetch_json = fetch_json
        self.states = {}

    def update(self, games):
        alerts = []
        for game in games:
            state = self.states.get(game.id)
            if state is None:
                # First sighting: what's already on the board isn't news, but a close
                # finish in progress still is
                state = self.states[game.id] = GameState(game)
                alerts += self.close_game_alerts(game, state)
                continue
            # Each kind is independent, so one failing lookup can't suppress the others
            for check in (self.scoring_alerts, self.final_alerts, self.close_game_alerts):
                try:
                    alerts += check(game, state)
                except Exception as e:
                    print(f"{check.__name__} failed for {game}: {e}", flush=True)
            state.status = game.status

        # Forget games that dropped off the scoreboard (the week rolled over)
        current_ids = {game.id for game in games}
        for game_id in list(self.states):
            if game_id not in current_ids:
                del self.states[game_id]
        return alerts

    def scoring_alerts(self, game, state):
        total = game.a_points + game.h_points
        if total == state.scored_total:
            return []
        if total < state.scored_total:
            # Score corrected downward (overturned play); nothing to announce
            state.scored_total = total
            state.pending_since = None
            return []

        now = monotonic()
        if state.pending_since is None:
            state.pending_since = now

        # The scoreboard moved; the play-by-play feed says what happened. A play
        # counts as new if it isn't announced yet and lands above the points we've
        # already accounted for, which skips plays from before we started watching.
        summary = self.fetch_json(SUMMARY_URL.format(event_id=game.id))
        plays = summary.get("scoringPlays", [])
        alerts = []
        for play in plays:
            if play["id"] in state.alerted_plays or _play_total(play) <= state.scored_total:
                continue
            state.alerted_plays.add(play["id"])
            alerts.append(self.score_alert(game, play, summary))

        # Settled once the feed has caught up to the scoreboard (an extra point just
        # updates the touchdown's play). Until then, look again next poll.
        caught_up = max((_play_total(p) for p in plays), default=0) >= total
        if caught_up or now - state.pending_since > SCORE_PENDING_SECONDS:
            state.scored_total = total
            state.pending_since = None
        return alerts

    def score_alert(self, game, play, summary):
        scoring_type = play.get("scoringType", {})
        title = SCORE_TITLES.get(scoring_type.get("name"), scoring_type.get("displayName", "SCORE").upper())
        team = play.get("team", {}).get("abbreviation", "")
        cards = []
        if scoring_type.get("name") == "touchdown":
            try:
                cards = self.touchdown_cards(game, play, summary)
            except Exception as e:
                print(f"Touchdown stats failed for {game}: {e}", flush=True)
        stat_cards = bool(cards)
        # No player stats (or not a touchdown): describe the play instead
        if not cards:
            cards = [play.get("text", "")]
        print(f"{title} {team}: {play.get('text')}", flush=True)
        return Alert(game.id, [title, team], cards, stat_cards=stat_cards)

    def touchdown_cards(self, game, play, summary):
        play_detail = self.fetch_json(PLAY_URL.format(event_id=game.id, play_id=play["id"]))
        roles = {}
        for participant in play_detail.get("participants", []):
            athlete_id = re.search(r"/athletes/(\d+)", participant["athlete"]["$ref"]).group(1)
            roles.setdefault(participant["type"], athlete_id)

        scorer = roles.get("scorer")
        if scorer is None:
            return []
        # Passing touchdowns show the receiver and the passer. A defensive score can
        # also list a "passer" (the QB who fumbled), so only pair them on a catch.
        if scorer == roles.get("receiver") and "passer" in roles:
            involved = [(scorer, "receiving"), (roles["passer"], "passing")]
        elif scorer == roles.get("rusher"):
            involved = [(scorer, "rushing")]
        else:
            involved = [(scorer, None)]

        players = boxscore_players(summary)
        yards = play_detail.get("statYardage")
        play_type = play_detail.get("type", {}).get("text", "")
        return [player_card(players[athlete_id], role, yards, play_type)
                for athlete_id, role in involved if athlete_id in players]

    def final_alerts(self, game, state):
        if game.status != "final" or state.status not in ("live", "halftime"):
            return []
        if game.a_points == game.h_points:
            result = "TIE"
        else:
            result = f"{game.a_team if game.a_points > game.h_points else game.h_team} WINS"
        print(f"FINAL {game}", flush=True)
        return [Alert(game.id, ["FINAL/OT" if game.period >= 5 else "FINAL", result])]

    def close_game_alerts(self, game, state):
        # A possession change starts a new drive. Each drive alerts at most once,
        # whether it starts inside the window or the clock runs into it mid-drive.
        if game.possession_id and game.possession_id != state.possession_id:
            state.possession_id = game.possession_id
            state.drive += 1
        if state.close_alerted_drive == state.drive or not is_close_game(game):
            return []
        state.close_alerted_drive = state.drive

        team, points, timeouts, opponent_points = game.side(game.possession_id)
        deficit = opponent_points - points
        score_line = "TIED" if deficit == 0 else f"DOWN {deficit}"
        down_line = f"{game.down_distance.upper().replace(' & ', '&')} {game.yard_line}".strip()
        clock_line = f"{game.display_clock} {game.quarter.upper()}"
        if timeouts is not None:
            clock_line += f" {timeouts} TO"
        print(f"CLOSE GAME {game}: {team} ball, {score_line}, {down_line}", flush=True)
        return [Alert(game.id, ["CLOSE GAME"], [[f"{team} BALL", score_line, down_line, clock_line]],
                      ttl=CLOSE_GAME_ALERT_TTL)]


def is_close_game(game):
    """The team with the ball can take the lead on this drive, and there's little or no
    time to answer. A leading team running out the clock never counts."""
    if game.status != "live" or not game.possession_id or game.clock_seconds <= 0:
        return False
    if not (game.period >= 5 or (game.period == 4 and game.clock_seconds <= CLOSE_GAME_SECONDS)):
        return False
    _, points, _, opponent_points = game.side(game.possession_id)
    return 0 <= opponent_points - points <= CLOSE_GAME_MAX_DEFICIT
