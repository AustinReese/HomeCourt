"""Runs the 55419 weather panel.

Everything interesting is split between weather_data.py (the NWS feeds) and
weather_art.py (the layout and the sky icon), neither of which imports
rgbmatrix, so both can be exercised off the Pi. This file only owns the
hardware and the clock: fetch on one thread, draw on the other.
"""

import threading
from json import loads
from time import monotonic, sleep

import requests

from samplebase import SampleBase

import weather_art
import weather_data

REQUEST_TIMEOUT = 15

# How often the poll thread wakes. WeatherSource decides which endpoints are
# actually due, so this is the floor on a retry, not the fetch rate.
POLL_SECONDS = 60
ERROR_RETRY_SECONDS = 30

# Only the sky icon moves, so the panel does not need a high frame rate; 20fps
# is smooth for drifting cloud and falling snow and leaves the Pi alone.
TARGET_FPS = 20

CURRENT = {"weather": None, "error": False}
CURRENT_LOCK = threading.Lock()


class WeatherUpdateThread(threading.Thread):
    def __init__(self, want_hourly):
        threading.Thread.__init__(self)
        self.daemon = True
        self.want_hourly = want_hourly

    def fetch_json(self, session, url):
        # raise_for_status keeps a blocked endpoint from surfacing as a
        # confusing JSONDecodeError on the HTML error page it returns
        response = session.get(url, timeout=REQUEST_TIMEOUT,
                               headers={"User-Agent": weather_data.USER_AGENT,
                                        "Accept": "application/geo+json"})
        response.raise_for_status()
        return loads(response.text)

    def run(self):
        session = requests.Session()
        source = weather_data.WeatherSource(
            lambda url: self.fetch_json(session, url), self.want_hourly)

        while True:
            try:
                weather = source.poll()
                with CURRENT_LOCK:
                    CURRENT["weather"] = weather
                    CURRENT["error"] = weather is None
                if weather is not None:
                    print(f"weather: {weather}", flush=True)
                sleep(POLL_SECONDS)
            except Exception as error:
                print(f"weather: poll failed: {error}", flush=True)
                with CURRENT_LOCK:
                    CURRENT["error"] = CURRENT["weather"] is None
                # A fresh session drops any connection left in a bad state
                session = requests.Session()
                sleep(ERROR_RETRY_SECONDS)


class WeatherDisplay(SampleBase):
    def __init__(self, weather_options, *args, **kwargs):
        super(WeatherDisplay, self).__init__(*args, **kwargs)
        self.weather_options = weather_options or {}

    def run(self):
        units = "c" if self.weather_options.get("weather_units") == "celsius" else "f"
        outlook = self.weather_options.get("weather_outlook", "days")
        panel = weather_art.Panel(units=units, outlook=outlook)
        print(f"weather: {weather_data.PLACE} {weather_data.ZIP_CODE}, "
              f"{'Celsius' if units == 'c' else 'Fahrenheit'}, {outlook}", flush=True)

        from PIL import Image

        canvas = self.matrix.CreateFrameCanvas()
        budget = 1.0 / TARGET_FPS
        seen = None
        started = monotonic()

        while True:
            frame_start = monotonic()

            with CURRENT_LOCK:
                weather, error = CURRENT["weather"], CURRENT["error"]
            # Rebuilding the static two thirds of the panel is only worth doing
            # when the forecast has actually changed underneath it.
            if weather is not seen:
                seen = weather
                panel.set_weather(weather)
            if error:
                panel.set_error()

            image = Image.frombytes(
                "RGB", (weather_art.MATRIX_WIDTH, weather_art.MATRIX_HEIGHT),
                panel.frame(monotonic() - started))
            canvas.SetImage(image)
            canvas = self.matrix.SwapOnVSync(canvas)

            spare = budget - (monotonic() - frame_start)
            if spare > 0:
                sleep(spare)


def run_weather(weather_options):
    print(weather_options, flush=True)
    update_thread = WeatherUpdateThread(
        (weather_options or {}).get("weather_outlook") == "hourly")
    update_thread.start()

    display = WeatherDisplay(weather_options)
    if not display.process():
        display.parser.print_help()
