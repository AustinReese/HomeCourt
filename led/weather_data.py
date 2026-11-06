"""National Weather Service data for the 55419 weather display. No rgbmatrix
import, so the feed can be exercised off the Pi.

Three NWS endpoints, each with its own refresh rate, because they change at very
different speeds and one of them is big:

  * the KMSP observation       -- what it is doing right now, updated ~hourly
  * the gridpoint forecast     -- named periods with highs, lows and a sky icon
  * the raw gridpoint          -- the only place with snowfall and precipitation
                                  *amounts*, and a 200KB payload for them

Everything is normalised to Fahrenheit and inches here; the renderer converts to
Celsius if asked. Fahrenheit is the internal unit only because the period
forecast is already published in it, so the common case stays exact.
"""

import re
from datetime import datetime, timedelta, timezone
from json import loads
from time import monotonic

# 55419 is south Minneapolis. The grid cell and station are what
# api.weather.gov/points/44.9075,-93.2850 resolves to; they are hard-coded
# rather than looked up so the display has one less thing to fail at boot.
ZIP_CODE = "55419"
PLACE = "MSP"
STATION = "KMSP"
GRID_OFFICE, GRID_X, GRID_Y = "MPX", 108, 69

OBSERVATION_URL = f"https://api.weather.gov/stations/{STATION}/observations/latest"
FORECAST_URL = f"https://api.weather.gov/gridpoints/{GRID_OFFICE}/{GRID_X},{GRID_Y}/forecast"
GRID_URL = f"https://api.weather.gov/gridpoints/{GRID_OFFICE}/{GRID_X},{GRID_Y}"

# NWS asks automated clients to identify themselves and rejects some generic
# agents. A product name is enough; do not put a real address here.
USER_AGENT = "HomeCourt-LED/1.0 (raspberry pi led matrix)"

# Refresh rates. The observation is the only thing a person watching the panel
# would notice going stale. The raw gridpoint is 200KB for two numbers, so it
# gets the longest leash.
OBSERVATION_SECONDS = 300
FORECAST_SECONDS = 900
GRID_SECONDS = 1800

# An observation this old is not "now" any more. KMSP reports about hourly, so
# allow a couple of missed cycles before saying so.
OBSERVATION_STALE_SECONDS = 3 * 3600

MM_PER_INCH = 25.4

# Sky conditions the renderer draws, in the order a forecast should be read by:
# if a period is both cloudy and snowing, it is a snow icon. Keyed by the code
# in an NWS icon URL.
SKY_PRIORITY = [
    "storm", "blizzard", "snow", "sleet", "rain", "fog", "haze",
    "cloudy", "partly", "clear",
]
SKY_CODES = {
    "skc": "clear", "few": "clear", "nskc": "clear", "nfew": "clear",
    "sct": "partly", "bkn": "partly",
    "ovc": "cloudy",
    "wind_skc": "clear", "wind_few": "clear", "wind_sct": "partly",
    "wind_bkn": "partly", "wind_ovc": "cloudy",
    "rain": "rain", "rain_showers": "rain", "rain_showers_hi": "rain",
    "rain_sleet": "sleet", "rain_snow": "sleet", "rain_fzra": "sleet",
    "snow_fzra": "sleet", "snow_sleet": "sleet", "fzra": "sleet", "sleet": "sleet",
    "snow": "snow", "blizzard": "blizzard",
    "tsra": "storm", "tsra_sct": "storm", "tsra_hi": "storm",
    "tornado": "storm", "hurricane": "storm", "tropical_storm": "storm",
    "fog": "fog", "dust": "haze", "smoke": "haze", "haze": "haze",
    "hot": "clear", "cold": "clear", "skc_hot": "clear",
}

_DURATION = re.compile(r"^P(?:(\d+)W)?(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:[\d.]+S)?)?$")
_ICON_PATH = re.compile(r"/icons/land/(day|night)/(.+?)(?:\?|$)")


def c_to_f(celsius):
    return celsius * 9.0 / 5.0 + 32.0


def f_to_c(fahrenheit):
    return (fahrenheit - 32.0) * 5.0 / 9.0


def _value(block):
    """NWS wraps every measurement as {'value': x, 'unitCode': ...}."""
    return (block or {}).get("value")


def _temp_f(block):
    """A measurement block holding a temperature, whatever unit it came in."""
    value = _value(block)
    if value is None:
        return None
    return c_to_f(value) if "degC" in (block or {}).get("unitCode", "") else value


def parse_iso(text):
    """NWS timestamps, which carry an explicit offset (sometimes as 'Z')."""
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def parse_duration(text):
    match = _DURATION.match(text)
    if not match:
        raise ValueError(f"unparseable duration {text}")
    weeks, days, hours, minutes = (int(g or 0) for g in match.groups())
    return timedelta(weeks=weeks, days=days, hours=hours, minutes=minutes)


def parse_sky(icon_url, text=""):
    """The sky condition to draw, from an NWS icon URL.

    A URL looks like /icons/land/day/bkn/rain,60?size=medium: one or two
    conditions, each possibly carrying a chance. Both are considered and the
    more significant one wins, so a mostly-cloudy-with-snow period draws snow.
    """
    match = _ICON_PATH.search(icon_url or "")
    if not match:
        # Some stations report no icon at all; the words are a usable fallback
        return _sky_from_text(text), "night" not in (icon_url or "")
    is_day = match.group(1) == "day"
    found = []
    for part in match.group(2).split("/"):
        code = part.split(",")[0].strip().lower()
        if code in SKY_CODES:
            found.append(SKY_CODES[code])
    if not found:
        return _sky_from_text(text), is_day
    return min(found, key=SKY_PRIORITY.index), is_day


def _sky_from_text(text):
    words = (text or "").lower()
    for needle, sky in (
            ("thunder", "storm"), ("blizzard", "blizzard"), ("snow", "snow"),
            ("flurr", "snow"), ("sleet", "sleet"), ("freezing", "sleet"),
            ("ice", "sleet"), ("rain", "rain"), ("shower", "rain"),
            ("drizzle", "rain"), ("fog", "fog"), ("mist", "fog"),
            ("haze", "haze"), ("smoke", "haze"), ("overcast", "cloudy"),
            ("cloudy", "partly"), ("clouds", "partly"), ("clear", "clear"),
            ("sunny", "clear"), ("fair", "clear")):
        if needle in words:
            return sky
    return "clear"


def day_label(date):
    return ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")[date.weekday()]


class Day():
    """One calendar day of forecast, as the strip and the hero band need it."""

    def __init__(self, date):
        self.date = date
        self.label = day_label(date)
        self.high = None
        self.low = None
        self.pop = 0            # percent chance of any precipitation
        self.snow = 0.0         # inches
        self.precip = 0.0       # inches of liquid
        self.sky = "clear"
        self.text = ""

    @property
    def wintry(self):
        """Whether the day's precipitation is worth drawing as snow."""
        return self.sky in ("snow", "blizzard", "sleet") or self.snow >= 0.1

    def __str__(self):
        amount = f" {self.snow:.1f}in snow" if self.snow else (f" {self.precip:.2f}in" if self.precip else "")
        return (f"{self.label} {self.date} {self.high}/{self.low} "
                f"{self.sky} {self.pop}%{amount}")


class Weather():
    """Everything the panel draws, in Fahrenheit and inches."""

    def __init__(self):
        self.place = PLACE
        self.temp = None
        self.feels_like = None
        self.sky = "clear"
        self.is_day = True
        self.text = ""
        self.observed = None
        self.today = None
        self.days = []          # tomorrow onwards
        self.hours = []         # (label, temp, sky, pop) from the next hours

    @property
    def stale(self):
        if self.observed is None:
            return True
        age = datetime.now(timezone.utc) - self.observed
        return age.total_seconds() > OBSERVATION_STALE_SECONDS

    def __str__(self):
        return (f"{self.place} {self.temp}F {self.sky}"
                f"{' (stale)' if self.stale else ''} | today {self.today} | "
                + " | ".join(str(d) for d in self.days))


def _grid_series(properties, name):
    """[(start, end, value)] for one raw-gridpoint time series."""
    block = properties.get(name) or {}
    series = []
    for entry in block.get("values", []):
        try:
            start_text, duration_text = entry["validTime"].split("/")
            start = parse_iso(start_text)
            series.append((start, start + parse_duration(duration_text), entry["value"]))
        except Exception:
            continue
    is_metric = "degC" in block.get("uom", "")
    return series, is_metric


def _accumulate_by_date(series, per_mm, tz):
    """Sum an amount series into local dates, splitting intervals that cross
    midnight in proportion to the hours falling either side."""
    totals = {}
    for start, end, value in series:
        if not value:
            continue
        span = (end - start).total_seconds()
        if span <= 0:
            continue
        # Walk the local days the interval touches
        cursor = start
        while cursor < end:
            local = cursor.astimezone(tz)
            midnight = (local + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0)
            chunk_end = min(end, midnight.astimezone(timezone.utc))
            share = (chunk_end - cursor).total_seconds() / span
            totals[local.date()] = totals.get(local.date(), 0.0) + value * share * per_mm
            cursor = chunk_end
    return totals


def _extremes_by_date(series, is_metric, tz, pick):
    out = {}
    for start, _end, value in series:
        if value is None:
            continue
        temp = c_to_f(value) if is_metric else value
        date = start.astimezone(tz).date()
        out[date] = temp if date not in out else pick(out[date], temp)
    return out


def build_weather(observation, forecast, grid, now=None, tz=None):
    """Turn the three NWS payloads into one Weather. Any of them may be None;
    whatever is missing is simply absent from the result."""
    tz = tz or datetime.now().astimezone().tzinfo
    now = now or datetime.now(tz)
    today_date = now.astimezone(tz).date()
    weather = Weather()

    if observation:
        properties = observation.get("properties", {})
        weather.temp = _temp_f(properties.get("temperature"))
        # Whichever of wind chill / heat index the hour actually has
        weather.feels_like = (_temp_f(properties.get("windChill"))
                              or _temp_f(properties.get("heatIndex")))
        weather.text = properties.get("textDescription") or ""
        weather.sky, weather.is_day = parse_sky(properties.get("icon"), weather.text)
        if properties.get("timestamp"):
            weather.observed = parse_iso(properties["timestamp"])

    days = {}

    def day_for(date):
        if date not in days:
            days[date] = Day(date)
        return days[date]

    if forecast:
        for period in forecast.get("properties", {}).get("periods", []):
            try:
                start = parse_iso(period["startTime"]).astimezone(tz)
                day = day_for(start.date())
                temp = period["temperature"]
                if period.get("temperatureUnit") == "C":
                    temp = c_to_f(temp)
                if period.get("isDaytime"):
                    day.high = round(temp)
                    # The daytime sky is the day's sky; a clear night after a
                    # snowy afternoon should still read as snow on the strip.
                    day.sky, _ = parse_sky(period.get("icon"), period.get("shortForecast"))
                    day.text = period.get("shortForecast") or ""
                else:
                    day.low = round(temp)
                    if day.high is None:
                        # Today, past sunset: no daytime period is left, so the
                        # night's sky is all there is to go on.
                        day.sky, _ = parse_sky(period.get("icon"), period.get("shortForecast"))
                        day.text = day.text or period.get("shortForecast") or ""
                day.pop = max(day.pop, _value(period.get("probabilityOfPrecipitation")) or 0)
            except Exception as error:
                print(f"weather: skipping period {period.get('number')}: {error}", flush=True)

    if grid:
        properties = grid.get("properties", {})
        snow_series, _ = _grid_series(properties, "snowfallAmount")
        rain_series, _ = _grid_series(properties, "quantitativePrecipitation")
        for date, inches in _accumulate_by_date(snow_series, 1 / MM_PER_INCH, tz).items():
            day_for(date).snow = inches
        for date, inches in _accumulate_by_date(rain_series, 1 / MM_PER_INCH, tz).items():
            day_for(date).precip = inches

        # Today's high is gone from the period forecast once the afternoon is
        # over, but the raw grid still reports it, which is what a person
        # looking at the panel in the evening expects to see.
        highs, metric = _grid_series(properties, "maxTemperature")
        lows, _ = _grid_series(properties, "minTemperature")
        for date, temp in _extremes_by_date(highs, metric, tz, max).items():
            day = day_for(date)
            if day.high is None:
                day.high = round(temp)
        for date, temp in _extremes_by_date(lows, metric, tz, min).items():
            day = day_for(date)
            if day.low is None:
                day.low = round(temp)

    weather.today = days.get(today_date) or Day(today_date)
    weather.days = [days[d] for d in sorted(days) if d > today_date]
    return weather


def build_hours(hourly, now=None, tz=None, count=8):
    """[(label, temp_f, sky, pop)] for the next few hours, for the hourly strip."""
    tz = tz or datetime.now().astimezone().tzinfo
    now = now or datetime.now(tz)
    hours = []
    for period in (hourly or {}).get("properties", {}).get("periods", []):
        try:
            start = parse_iso(period["startTime"]).astimezone(tz)
            if start + timedelta(hours=1) <= now:
                continue
            temp = period["temperature"]
            if period.get("temperatureUnit") == "C":
                temp = c_to_f(temp)
            sky, _ = parse_sky(period.get("icon"), period.get("shortForecast"))
            hour = start.hour % 12 or 12
            label = f"{hour}{'A' if start.hour < 12 else 'P'}"
            pop = _value(period.get("probabilityOfPrecipitation")) or 0
            hours.append((label, round(temp), sky, pop))
        except Exception:
            continue
        if len(hours) >= count:
            break
    return hours


class WeatherSource():
    """Polls the three endpoints on their own clocks and keeps the last good
    payload of each, so one failing endpoint does not blank the panel.

    `fetch_json` is injected to keep requests out of this module.
    """

    HOURLY_URL = FORECAST_URL + "/hourly"

    def __init__(self, fetch_json, want_hourly=False):
        self.fetch_json = fetch_json
        self.want_hourly = want_hourly
        self.payloads = {}
        self.fetched_at = {}
        self.failures = 0

    def _due(self, name, url, interval):
        last = self.fetched_at.get(name)
        if last is not None and monotonic() - last < interval:
            return False
        try:
            self.payloads[name] = self.fetch_json(url)
            self.fetched_at[name] = monotonic()
            return True
        except Exception as error:
            print(f"weather: {name} fetch failed: {error}", flush=True)
            # Retry on the next poll rather than waiting out the full interval,
            # but do not hammer: the caller's poll interval is the floor.
            self.failures += 1
            return False

    def poll(self):
        """Fetch whatever is due and return a Weather, or None if nothing has
        ever been fetched successfully."""
        before = self.failures
        self._due("observation", OBSERVATION_URL, OBSERVATION_SECONDS)
        self._due("forecast", FORECAST_URL, FORECAST_SECONDS)
        self._due("grid", GRID_URL, GRID_SECONDS)
        if self.want_hourly:
            self._due("hourly", self.HOURLY_URL, FORECAST_SECONDS)

        if not self.payloads:
            return None
        weather = build_weather(self.payloads.get("observation"),
                                self.payloads.get("forecast"),
                                self.payloads.get("grid"))
        if self.want_hourly:
            weather.hours = build_hours(self.payloads.get("hourly"))
        weather.degraded = self.failures > before
        return weather
