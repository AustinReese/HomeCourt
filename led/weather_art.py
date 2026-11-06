"""The 55419 weather panel. No rgbmatrix import, so the layout can be rendered
and looked at off the Pi.

The 64x32 panel is 2048 LEDs and the forecast wants to say five things at once,
so the space is split the way a weather page is: one hero and one strip.

    rows 0-17   a 16x16 animated sky icon, the current temperature as large as
                it will go, and today's high, low and headline figure
    rows 18-31  four more days, each with a high, a low and a bar whose length
                is the chance of precipitation and whose colour is what kind

Two rules from the rest of led/ shape the drawing. Text is never anti-aliased --
every glyph here is a hand-set bitmap, because a blurred 3px digit is an
unreadable one. Everything that moves is splatted at fractional coordinates, so
a snowflake crossing the icon drifts instead of stepping. The static two thirds
of the panel are drawn once into a base buffer and only the icon is repainted
per frame, which keeps a 20fps weather display near zero CPU.
"""

import math

MATRIX_WIDTH = 64
MATRIX_HEIGHT = 32
BUFFER_SIZE = MATRIX_WIDTH * MATRIX_HEIGHT * 3

# --- Layout ------------------------------------------------------------------
#
# The panel splits left and right rather than top and bottom. A forecast is a
# list of days, and a list reads down a column; laying the days out sideways
# gave each one 15px, which is not enough for two temperatures when both are
# below zero -- an ordinary Minneapolis January, not a corner case. As rows
# they get the full 32px.

LEFT_WIDTH = 30             # current conditions
GAP = 2                     # black, in place of a rule: cheaper and cleaner
RIGHT_X = LEFT_WIDTH + GAP  # the forecast rows
RIGHT_WIDTH = MATRIX_WIDTH - RIGHT_X

ICON_X, ICON_Y, ICON_SIZE = 0, 0, 16

# Today's precipitation sits beside the icon, in the strip of left-hand panel
# the icon does not use.
HEADLINE_X = ICON_SIZE + 1
HEADLINE_Y = 5
HEADLINE_WIDTH = LEFT_WIDTH - HEADLINE_X

# The current temperature takes the bottom half of the left panel, as large as
# the panel will carry.
TEMP_LEFT, TEMP_RIGHT = 0, LEFT_WIDTH - 1
TEMP_TOP = 16

# Five forecast rows: today and the four days after it. Five rows of six is
# thirty of the thirty-two available, leaving a pixel of margin top and bottom.
ROW_TOP = 1
ROW_PITCH = 6
ROW_COUNT = 5
BAR_OFFSET = 5              # the row's last pixel line is its bar
TEMP_GAP = 2                # between a high and a low, squeezed to 1 if needed

# --- Palette -----------------------------------------------------------------
# Bold and bright: on a black panel anything desaturated reads as a fault.

HIGH_COLOR = (255, 170, 40)         # amber, used for every high on the panel
LOW_COLOR = (90, 170, 255)          # steel blue, likewise for every low
LABEL_COLOR = (165, 170, 185)
DIM_COLOR = (95, 100, 115)
RULE_COLOR = (26, 26, 32)
TRACK_COLOR = (38, 38, 46)
ERROR_COLOR = (220, 40, 30)
WHITE = (255, 255, 255)

# The colour of a precipitation bar says what is falling.
PRECIP_COLORS = {
    "rain": (60, 140, 255),
    "snow": (235, 245, 255),
    "blizzard": (235, 245, 255),
    "sleet": (185, 150, 255),
    "storm": (255, 205, 60),
    "fog": (120, 130, 150),
    "haze": (150, 140, 120),
}
DEFAULT_PRECIP_COLOR = (60, 140, 255)

# The current temperature is coloured by what it is: a Minneapolis January and a
# Minneapolis July should not be the same shade of white. Stops are (degF, rgb)
# and are interpolated, so the hero drifts through the year.
TEMP_RAMP = [
    (-20, (120, 180, 255)),
    (10, (165, 210, 255)),
    (32, (225, 240, 255)),
    (45, (255, 255, 255)),
    (62, (255, 244, 190)),
    (75, (255, 205, 95)),
    (88, (255, 150, 55)),
    (100, (255, 85, 45)),
]


def ramp_color(temp):
    """Interpolate TEMP_RAMP. Missing temperatures come out white."""
    if temp is None:
        return WHITE
    if temp <= TEMP_RAMP[0][0]:
        return TEMP_RAMP[0][1]
    if temp >= TEMP_RAMP[-1][0]:
        return TEMP_RAMP[-1][1]
    for (t0, c0), (t1, c1) in zip(TEMP_RAMP, TEMP_RAMP[1:]):
        if t0 <= temp <= t1:
            f = (temp - t0) / float(t1 - t0)
            return tuple(int(round(a + (b - a) * f)) for a, b in zip(c0, c1))
    return WHITE


# --- Type --------------------------------------------------------------------
# Three sizes, all hand-set, all inked with '#'.
#
# BIG is fixed width on purpose: a proportional '1' would make the whole
# temperature jump sideways every time it passed through 1x degrees.

BIG_WIDTH, BIG_HEIGHT = 10, 15

BIG = {
    '0': ('..######..',
          '.########.',
          '###....###',
          '##......##',
          '##......##',
          '##......##',
          '##......##',
          '##......##',
          '##......##',
          '##......##',
          '##......##',
          '##......##',
          '###....###',
          '.########.',
          '..######..'),
    '1': ('....###...',
          '..#####...',
          '.######...',
          '...####...',
          '...####...',
          '...####...',
          '...####...',
          '...####...',
          '...####...',
          '...####...',
          '...####...',
          '...####...',
          '...####...',
          '.########.',
          '.########.'),
    '2': ('..######..',
          '.########.',
          '###....###',
          '##......##',
          '........##',
          '.......###',
          '......###.',
          '.....###..',
          '....###...',
          '...###....',
          '..###.....',
          '.###......',
          '##########',
          '##########',
          '##########'),
    '3': ('.#######..',
          '.########.',
          '##.....###',
          '.......###',
          '......###.',
          '....####..',
          '....####..',
          '......###.',
          '.......###',
          '........##',
          '##......##',
          '##......##',
          '###....###',
          '.########.',
          '..######..'),
    '4': ('......###.',
          '.....####.',
          '....#####.',
          '...##.###.',
          '..###.###.',
          '.###..###.',
          '###...###.',
          '##....###.',
          '##########',
          '##########',
          '......###.',
          '......###.',
          '......###.',
          '......###.',
          '......###.'),
    '5': ('##########',
          '##########',
          '###.......',
          '###.......',
          '###.......',
          '########..',
          '#########.',
          '##.....###',
          '........##',
          '........##',
          '##......##',
          '##......##',
          '###....###',
          '.########.',
          '..######..'),
    '6': ('...#####..',
          '..######..',
          '.###......',
          '###.......',
          '##........',
          '##.#####..',
          '##########',
          '###....###',
          '##......##',
          '##......##',
          '##......##',
          '##......##',
          '###....###',
          '.########.',
          '..######..'),
    '7': ('##########',
          '##########',
          '##########',
          '.......###',
          '......###.',
          '......###.',
          '.....###..',
          '.....###..',
          '....###...',
          '....###...',
          '...###....',
          '...###....',
          '..###.....',
          '..###.....',
          '.###......'),
    '8': ('..######..',
          '.########.',
          '###....###',
          '##......##',
          '##......##',
          '###....###',
          '.########.',
          '.########.',
          '###....###',
          '##......##',
          '##......##',
          '##......##',
          '###....###',
          '.########.',
          '..######..'),
    '9': ('..######..',
          '.########.',
          '###....###',
          '##......##',
          '##......##',
          '##......##',
          '###....###',
          '.########.',
          '..########',
          '........##',
          '........##',
          '........##',
          '.......###',
          '..#######.',
          '..######..'),
    # Narrow, and vertically centred rather than sitting on the baseline.
    '-': ('......',
          '......',
          '......',
          '......',
          '......',
          '......',
          '######',
          '######',
          '######',
          '......',
          '......',
          '......',
          '......',
          '......',
          '......'),
    # A degree sign hangs from the top of the figures, not the middle.
    'o': ('.##.',
          '#..#',
          '#..#',
          '.##.',
          '....',
          '....',
          '....',
          '....',
          '....',
          '....',
          '....',
          '....',
          '....',
          '....',
          '....'),
}

# 3x5, for everything in a 15px column. Zero keeps a gap in the middle so it
# cannot be read as an eight.
TINY = {
    '0': ('###', '#.#', '#.#', '#.#', '###'),
    '1': ('.#.', '##.', '.#.', '.#.', '###'),
    '2': ('##.', '..#', '.#.', '#..', '###'),
    '3': ('##.', '..#', '.#.', '..#', '##.'),
    '4': ('#.#', '#.#', '###', '..#', '..#'),
    '5': ('###', '#..', '##.', '..#', '##.'),
    '6': ('.##', '#..', '###', '#.#', '###'),
    '7': ('###', '..#', '.#.', '.#.', '.#.'),
    '8': ('###', '#.#', '###', '#.#', '###'),
    '9': ('###', '#.#', '###', '..#', '##.'),
    'A': ('.#.', '#.#', '###', '#.#', '#.#'),
    'P': ('###', '#.#', '###', '#..', '#..'),
    '%': ('#.#', '..#', '.#.', '#..', '#.#'),
    # Two pixels, not three: a day row has to hold '-18' and '-12' at once.
    '-': ('..', '..', '##', '..', '..'),
    '.': ('.', '.', '.', '.', '#'),
    '"': ('#.#', '#.#', '...', '...', '...'),
    '+': ('...', '.#.', '###', '.#.', '...'),
}
TINY_HEIGHT = 5

# Proportional five-row caps for the day names. Only the letters MON..SUN needs
# are here; a 3px-wide M is indistinguishable from an H, which is why the day
# labels get a proportional face and the numbers do not. (film_reel.py has its
# own copy of shapes like these -- the two displays are kept independent on
# purpose, so neither can break the other's layout.)
CAPS = {
    'A': ('.##.', '#..#', '####', '#..#', '#..#'),
    'D': ('###.', '#..#', '#..#', '#..#', '###.'),
    'E': ('####', '#...', '###.', '#...', '####'),
    'F': ('####', '#...', '###.', '#...', '#...'),
    'H': ('#..#', '#..#', '####', '#..#', '#..#'),
    'I': ('###', '.#.', '.#.', '.#.', '###'),
    'M': ('#...#', '##.##', '#.#.#', '#...#', '#...#'),
    'N': ('#..#', '##.#', '#.##', '#..#', '#..#'),
    'O': ('.##.', '#..#', '#..#', '#..#', '.##.'),
    'R': ('###.', '#..#', '###.', '#.#.', '#..#'),
    'S': ('.###', '#...', '.##.', '...#', '###.'),
    'T': ('#####', '..#..', '..#..', '..#..', '..#..'),
    'U': ('#..#', '#..#', '#..#', '#..#', '.##.'),
    'W': ('#...#', '#...#', '#.#.#', '##.##', '#...#'),
    'C': ('.###', '#...', '#...', '#...', '.###'),
    'G': ('.###', '#...', '#.##', '#..#', '.###'),
    'L': ('#...', '#...', '#...', '#...', '####'),
    'P': ('###.', '#..#', '###.', '#...', '#...'),
    'B': ('###.', '#..#', '###.', '#..#', '###.'),
    'K': ('#..#', '#.#.', '##..', '#.#.', '#..#'),
    'Y': ('#...#', '.#.#.', '..#..', '..#..', '..#..'),
    'X': ('#...#', '.#.#.', '..#..', '.#.#.', '#...#'),
    '!': ('#', '#', '#', '.', '#'),
    '?': ('###.', '...#', '.##.', '....', '..#.'),
    '.': ('.', '.', '.', '.', '#'),
    ' ': ('..', '..', '..', '..', '..'),
}
CAPS_HEIGHT = 5

# 5x5 marks. The arrows carry a stem so they still read as direction at this
# size, where a bare triangle just looks like a wedge of noise.
MARKS = {
    'up': ('..#..', '.###.', '#####', '..#..', '..#..'),
    'down': ('..#..', '..#..', '#####', '.###.', '..#..'),
    'snow': ('..#..', '#.#.#', '.###.', '#.#.#', '..#..'),
    'drop': ('..#..', '..#..', '.###.', '#####', '.###.'),
    # A double tilde, read as "about": this is the feels-like row.
    'about': ('.....', '.##.#', '#..#.', '.##.#', '#..#.'),
}
MARK_HEIGHT = 5


def glyph_width(table, char):
    rows = table.get(char)
    return len(rows[0]) if rows else 0


def text_width(table, text, tracking=1):
    """Width of a string in a proportional table, with no trailing tracking."""
    chars = [c for c in text if c in table]
    if not chars:
        return 0
    return sum(glyph_width(table, c) + tracking for c in chars) - tracking


# --- The frame ---------------------------------------------------------------

class Canvas():
    """A 64x32 RGB bytearray with the few drawing operations this panel needs.

    Text is written at whole pixels and shapes at fractional ones: see the
    module docstring for why the two are treated differently.
    """

    def __init__(self, source=None):
        self.buf = bytearray(source) if source is not None else bytearray(BUFFER_SIZE)
        # (x0, y0, x1, y1) half-open, or None for the whole panel. The icon
        # painters draw splats that reach past their cell; clipping lets them
        # do that without smearing the forecast, which is never redrawn.
        self.clip = None

    def copy(self):
        return Canvas(self.buf)

    def _inside(self, x, y):
        if not (0 <= x < MATRIX_WIDTH and 0 <= y < MATRIX_HEIGHT):
            return False
        if self.clip is None:
            return True
        x0, y0, x1, y1 = self.clip
        return x0 <= x < x1 and y0 <= y < y1

    def pixel(self, x, y, color):
        if self._inside(x, y):
            i = (y * MATRIX_WIDTH + x) * 3
            self.buf[i:i + 3] = bytes(color)

    def blend(self, x, y, color, alpha):
        """Mix colour into a pixel. Used by every moving thing on the panel."""
        if alpha <= 0 or not self._inside(x, y):
            return
        if alpha >= 1:
            return self.pixel(x, y, color)
        i = (y * MATRIX_WIDTH + x) * 3
        buf = self.buf
        for n in range(3):
            under = buf[i + n]
            buf[i + n] = int(under + (color[n] - under) * alpha)

    def rect(self, x, y, width, height, color):
        """Filled rectangle. Row slices keep the fill in C."""
        x0, y0 = max(0, x), max(0, y)
        x1 = min(MATRIX_WIDTH, x + width)
        y1 = min(MATRIX_HEIGHT, y + height)
        if self.clip is not None:
            cx0, cy0, cx1, cy1 = self.clip
            x0, y0 = max(x0, cx0), max(y0, cy0)
            x1, y1 = min(x1, cx1), min(y1, cy1)
        if x1 <= x0 or y1 <= y0:
            return
        row = bytes(color) * (x1 - x0)
        for row_y in range(y0, y1):
            i = (row_y * MATRIX_WIDTH + x0) * 3
            self.buf[i:i + (x1 - x0) * 3] = row

    def splat(self, x, y, color, radius=1.0, intensity=1.0):
        """Light the LEDs around a fractional point in proportion to how close
        each one is to it. This buys position, not resolution: a flake can sit
        half a pixel further left, it cannot be half a pixel wide."""
        left, top = int(x - radius), int(y - radius)
        for py in range(top, int(y + radius) + 1):
            for px in range(left, int(x + radius) + 1):
                dx, dy = px - x, py - y
                distance = (dx * dx + dy * dy) ** 0.5
                if distance < radius:
                    self.blend(px, py, color, (1 - distance / radius) * intensity)

    def disc(self, cx, cy, radius, color, intensity=1.0):
        """A soft-edged filled circle: solid inside, splatted on the rim, which
        is what keeps a 5px cloud from looking like a staircase."""
        for py in range(int(cy - radius) - 1, int(cy + radius) + 2):
            for px in range(int(cx - radius) - 1, int(cx + radius) + 2):
                distance = ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5
                coverage = radius + 0.5 - distance
                if coverage > 0:
                    self.blend(px, py, color, min(1.0, coverage) * intensity)

    def glyph(self, table, char, x, y, color):
        """Draw one bitmap glyph, returning its width."""
        rows = table.get(char)
        if rows is None:
            return 0
        for row_y, row in enumerate(rows):
            for row_x, ink in enumerate(row):
                if ink == '#':
                    self.pixel(x + row_x, y + row_y, color)
        return len(rows[0])

    def text(self, table, text, x, y, color, tracking=1):
        """Draw a string left to right, returning the width used."""
        cursor = x
        for char in text:
            width = self.glyph(table, char, cursor, y, color)
            if width:
                cursor += width + tracking
        return max(0, cursor - x - tracking)

    def centered(self, table, text, x, width, y, color, tracking=1):
        span = text_width(table, text, tracking)
        return self.text(table, text, x + (width - span) // 2, y, color, tracking)

    def to_bytes(self):
        return bytes(self.buf)


# --- The sky icon ------------------------------------------------------------
# One 16x16 cell, repainted every frame. Each painter takes a phase in seconds,
# so motion is paced by the wall clock and survives a dropped frame.

SUN_COLOR = (255, 196, 48)
SUN_CORE = (255, 240, 170)
MOON_COLOR = (226, 236, 255)
CLOUD_LIGHT = (198, 208, 226)
CLOUD_MID = (124, 134, 155)
CLOUD_DARK = (84, 92, 112)
CLOUD_STORM = (58, 62, 78)
RAIN_COLOR = (80, 160, 255)
SNOW_COLOR = (245, 250, 255)
SLEET_COLOR = (196, 168, 255)
BOLT_COLOR = (255, 232, 90)
FOG_COLOR = (150, 160, 182)
HAZE_COLOR = (198, 178, 134)

# Drawn rather than splatted: a bolt is all hard angles, and softening it just
# makes a yellow smudge.
BOLT = ('...##',
        '..##.',
        '.####',
        '..##.',
        '.##..',
        '##...')


def _hrun(canvas, x0, x1, y, color, intensity=1.0):
    """A horizontal run between fractional ends, so a band can slide smoothly
    instead of jumping a pixel at a time."""
    for x in range(int(math.floor(x0)), int(math.ceil(x1)) + 1):
        coverage = min(x + 1.0, x1) - max(float(x), x0)
        if coverage > 0:
            canvas.blend(x, y, color, min(1.0, coverage) * intensity)


def _sun(canvas, cx, cy, radius, phase, color=SUN_COLOR, rays=True):
    """A disc with eight rays that breathe. The pulse is slow and shallow: a
    sun that throbs looks like a warning light."""
    pulse = 0.5 + 0.5 * math.sin(phase * 1.4)
    if rays:
        for n in range(8):
            angle = n * math.pi / 4 + phase * 0.25
            length = radius + 1.7 + pulse * 1.0
            canvas.splat(cx + math.cos(angle) * length,
                         cy + math.sin(angle) * length,
                         color, radius=1.3, intensity=0.45 + 0.4 * pulse)
    canvas.disc(cx, cy, radius, color)
    canvas.disc(cx, cy, radius - 1.5, SUN_CORE, intensity=0.8)


def _moon(canvas, cx, cy, radius, phase, stars=True):
    """A lit disc with a shadow disc taken back out of it, which is how the
    real thing works and is what keeps the horns sharp at this size."""
    canvas.disc(cx, cy, radius, MOON_COLOR)
    canvas.disc(cx + radius * 0.78, cy - radius * 0.30, radius * 0.95, (0, 0, 0))
    if not stars:
        return
    for n, (sx, sy) in enumerate(((1.5, 12.0), (13.0, 2.5), (14.0, 10.5))):
        twinkle = 0.3 + 0.7 * (0.5 + 0.5 * math.sin(phase * 1.9 + n * 2.1))
        canvas.splat(sx, sy, MOON_COLOR, radius=1.2, intensity=twinkle * 0.85)


def _cloud(canvas, cx, base, scale, color, intensity=1.0):
    """Three lumps standing on a level base.

    Built upward from the base line rather than outward from a centre, because
    a cloud is defined by its flat underside -- round it off and the shape
    stops reading as a cloud and starts reading as a blob.
    """
    for dx, radius in ((-2.2, 2.0), (0.3, 2.75), (2.5, 1.85)):
        r = radius * scale
        canvas.disc(cx + dx * scale, base - r + 0.4, r, color, intensity)
    for y in range(int(base - 1.7 * scale), int(base) + 1):
        _hrun(canvas, cx - 4.0 * scale, cx + 4.2 * scale, y, color, intensity)


def _falling(canvas, phase, color, count, speed, drift, top, bottom,
             size=1.1, streak=0.0):
    """Precipitation under a cloud.

    Each particle keeps its own column and its own offset into the cycle, so
    the fall looks scattered without a random generator whose state would have
    to be stored somewhere and would flicker on every redraw.
    """
    span = bottom - top
    for n in range(count):
        x = 1.8 + (n * 4.9) % 12.4
        cycle = (phase * speed + n * 0.37) % 1.0
        y = top + cycle * span
        wobble = math.sin(phase * 2.3 + n * 1.7) * drift
        # Fade out at the bottom so nothing stops dead at the edge of the cell
        fade = 1.0 if cycle < 0.8 else (1.0 - cycle) / 0.2
        canvas.splat(x + wobble, y, color, radius=size, intensity=fade)
        if streak:
            canvas.splat(x + wobble, y - streak, color, radius=size * 0.8,
                         intensity=0.55 * fade)


def _bands(canvas, phase, color, rows, speed):
    """Fog and haze: horizontal bars sliding at their own speeds. Each row
    moves a little faster than the one above it, which is the whole trick --
    equal speeds read as a texture, unequal ones read as drifting air."""
    for n, y in enumerate(rows):
        offset = (phase * speed * (1.0 + n * 0.3)) % 22.0 - 6.0
        for step in range(2):
            x0 = offset + step * 11.0
            _hrun(canvas, x0, x0 + 6.5, y, color, 0.85 - n * 0.08)


def paint_icon(canvas, sky, is_day, phase):
    """Paint the 16x16 sky cell. The caller clips to the cell, so a painter can
    reach past the edge without smearing the panel."""
    x0, y0 = ICON_X, ICON_Y
    cx, cy = x0 + 7.5, y0 + 7.5

    if sky == "clear":
        if is_day:
            _sun(canvas, cx, cy, 4.0, phase)
        else:
            _moon(canvas, cx + 0.5, cy - 0.5, 4.2, phase)

    elif sky == "partly":
        drift = math.sin(phase * 0.5) * 0.7
        if is_day:
            _sun(canvas, x0 + 4.8, y0 + 4.6, 3.2, phase)
        else:
            _moon(canvas, x0 + 4.4, y0 + 4.2, 3.2, phase, stars=False)
        _cloud(canvas, x0 + 8.6 + drift, y0 + 13.5, 1.1, CLOUD_LIGHT)

    elif sky == "cloudy":
        # A dim cloud behind a bright one: at this size overlapping two clouds
        # of the same value just makes one larger cloud.
        _cloud(canvas, x0 + 5.5 + math.sin(phase * 0.33) * 1.2, y0 + 7.5,
               0.8, CLOUD_DARK)
        _cloud(canvas, x0 + 8.5 - math.sin(phase * 0.47) * 1.0, y0 + 13.5,
               1.15, CLOUD_LIGHT)

    elif sky in ("rain", "sleet", "snow", "blizzard"):
        heavy = sky == "blizzard"
        _cloud(canvas, x0 + 7.6 + math.sin(phase * 0.4) * 0.7, y0 + 8.5, 1.2,
               CLOUD_DARK if sky == "rain" else CLOUD_LIGHT)
        if sky == "rain":
            _falling(canvas, phase, RAIN_COLOR, 5, 1.6, 0.12,
                     y0 + 9.5, y0 + 15.5, size=1.0, streak=1.1)
        elif sky == "sleet":
            _falling(canvas, phase, SLEET_COLOR, 5, 1.3, 0.55,
                     y0 + 9.5, y0 + 15.5, size=0.85, streak=0.7)
        else:
            _falling(canvas, phase, SNOW_COLOR, 7 if heavy else 5,
                     1.5 if heavy else 0.7, 1.6 if heavy else 1.1,
                     y0 + 9.5, y0 + 15.5, size=0.9)
        if heavy:
            # Wind, as streaks blowing across the fall
            for n in range(3):
                y = y0 + 10 + n * 2
                x = (phase * 15.0 + n * 7.0) % 26.0 - 6.0
                _hrun(canvas, x, x + 4.5, y, SNOW_COLOR, 0.35)

    elif sky == "storm":
        _cloud(canvas, x0 + 7.6, y0 + 8.5, 1.25, CLOUD_STORM)
        _cloud(canvas, x0 + 7.2, y0 + 7.0, 1.0, CLOUD_DARK)
        _falling(canvas, phase, RAIN_COLOR, 3, 1.9, 0.1,
                 y0 + 10.0, y0 + 15.5, size=0.9, streak=1.0)
        # Two quick strikes a few seconds apart, the way real lightning goes
        beat = phase % 3.4
        flash = 1.0 if beat < 0.11 else (0.8 if 0.24 < beat < 0.33 else 0.0)
        if flash:
            for row_y, row in enumerate(BOLT):
                for row_x, ink in enumerate(row):
                    if ink == '#':
                        canvas.blend(x0 + 5 + row_x, y0 + 9 + row_y,
                                     BOLT_COLOR, flash)

    elif sky == "fog":
        _bands(canvas, phase, FOG_COLOR, (y0 + 3, y0 + 6, y0 + 9, y0 + 12), 2.0)

    elif sky == "haze":
        if is_day:
            _sun(canvas, cx, y0 + 5.0, 3.2, phase, color=HAZE_COLOR, rays=False)
        _bands(canvas, phase, HAZE_COLOR, (y0 + 8, y0 + 11, y0 + 14), 1.5)

    else:
        _cloud(canvas, x0 + 7.5, y0 + 12.0, 1.2, CLOUD_LIGHT)


# --- Figures ------------------------------------------------------------------

def format_temp(fahrenheit, units="f"):
    """A temperature as it is written on the panel: whole degrees, no sign for
    positives, '--' when it is missing."""
    if fahrenheit is None:
        return "--"
    value = fahrenheit if units == "f" else (fahrenheit - 32.0) * 5.0 / 9.0
    return str(int(round(value)))


def format_inches(inches):
    """Precipitation the way a forecast says it: tenths once there is an inch to
    talk about, hundredths below that, and never a leading zero -- the panel has
    no pixels to spend on one."""
    if inches >= 10:
        return f'{int(round(inches))}"'
    if inches >= 1:
        return f'{inches:.1f}"'
    return f'{inches:.2f}"'.lstrip("0")


def precip_color(day):
    """What is falling, as a colour. Snow wins over the sky when the forecast
    puts any real amount of it down, because that is the thing worth seeing."""
    if day.wintry:
        return PRECIP_COLORS["snow"]
    return PRECIP_COLORS.get(day.sky, DEFAULT_PRECIP_COLOR)


# --- The left panel: what it is doing now -------------------------------------

def _draw_big_temp(canvas, text, color):
    """The current temperature, centred across the left panel and as large as
    the glyphs go. The degree sign is dropped when the figures need the room:
    a digit is information, a degree mark is decoration."""
    sequence = list(text)
    span = sum(glyph_width(BIG, c) + 1 for c in sequence) - 1
    band = TEMP_RIGHT - TEMP_LEFT + 1
    if span + 2 + glyph_width(BIG, 'o') <= band:
        sequence.append('o')
        span += 2 + glyph_width(BIG, 'o')
    x = TEMP_LEFT + (band - span) // 2
    for char in sequence:
        if char == 'o':
            x += 1          # the degree sign is set loose from the figures
        x += canvas.glyph(BIG, char, x, TEMP_TOP, color) + 1


def _headline(today):
    """The figure beside the sky icon: how much is falling today, or failing
    that how likely it is to. Blank on a dry day, which is most of them, and a
    blank strip beside the icon looks deliberate where a zero would not."""
    if today is None:
        return "", LABEL_COLOR
    if today.snow >= 0.1:
        return format_inches(today.snow), PRECIP_COLORS["snow"]
    if today.precip >= 0.01:
        return format_inches(today.precip), PRECIP_COLORS["rain"]
    if today.pop >= 20:
        return f"{int(today.pop)}%", PRECIP_COLORS["rain"]
    return "", LABEL_COLOR


def _draw_now(canvas, weather, units):
    # A stale reading is not "now", so the icon stops claiming to know the sky
    paint_icon(canvas, weather.sky if not weather.stale else "cloudy",
               weather.is_day, 0.0)

    text, color = _headline(weather.today)
    if text:
        canvas.centered(TINY, text, HEADLINE_X, HEADLINE_WIDTH, HEADLINE_Y, color)

    _draw_big_temp(canvas, format_temp(weather.temp, units), ramp_color(weather.temp))

    if weather.stale:
        # Too old to call current. Say so rather than lie quietly.
        canvas.rect(TEMP_LEFT, MATRIX_HEIGHT - 1, 3, 1, ERROR_COLOR)


# --- The right panel: the days ------------------------------------------------

def _draw_bar(canvas, y, fraction, color):
    """A row's precipitation bar: one pixel line under the figures, as long as
    the chance and coloured by what kind.

    There is no track behind it. A dry forecast is the common case, and five
    permanent grey lines across the panel read as clutter in exchange for a
    scale nobody needs: the bars all start at the same x, so their lengths
    compare against each other without one. A lit line on a black panel
    carries this at a single pixel, and a thicker bar would cost a whole day.
    """
    filled = int(round(max(0.0, min(1.0, fraction)) * RIGHT_WIDTH))
    if fraction > 0 and filled == 0:
        filled = 1          # a slight chance should not round away to nothing
    if filled:
        canvas.rect(RIGHT_X, y, filled, 1, color)


def _draw_row(canvas, y, label_long, label_short, high, low, fraction, color,
              label_color=LABEL_COLOR):
    """One forecast row: a name on the left, a high and a low on the right, a
    bar underneath.

    The figures are placed first and the name takes what is left, giving up its
    third letter when the temperatures need the room. That is the right way
    round: 'MO -18 -12' says more than 'MON' and a clipped number.
    """
    gap = TEMP_GAP
    width = text_width(TINY, high) + gap + text_width(TINY, low)
    if width + text_width(CAPS, label_short) + 1 > RIGHT_WIDTH:
        gap = 1
        width -= 1

    x = MATRIX_WIDTH - width
    canvas.text(TINY, high, x, y, HIGH_COLOR)
    canvas.text(TINY, low, x + text_width(TINY, high) + gap, y, LOW_COLOR)

    room = x - RIGHT_X - 1
    label = label_long if text_width(CAPS, label_long) <= room else label_short
    if text_width(CAPS, label) <= room:
        canvas.text(CAPS, label, RIGHT_X, y, label_color)

    _draw_bar(canvas, y + BAR_OFFSET, fraction, color)


def _draw_days(canvas, weather, units):
    """Today first, then as many of the following days as there are rows."""
    days = ([weather.today] if weather.today else []) + list(weather.days)
    for n in range(ROW_COUNT):
        if n >= len(days):
            break
        day = days[n]
        y = ROW_TOP + n * ROW_PITCH
        _draw_row(canvas, y, day.label, day.label[:2],
                  format_temp(day.high, units), format_temp(day.low, units),
                  day.pop / 100.0, precip_color(day),
                  # Today's name is brightest: it is the row the big
                  # temperature on the left belongs to.
                  WHITE if n == 0 else LABEL_COLOR)


def _draw_hours(canvas, weather, units):
    """The same rows, counting in hours instead of days."""
    for n, (label, temp, sky, pop) in enumerate(weather.hours[:ROW_COUNT]):
        y = ROW_TOP + n * ROW_PITCH
        value = format_temp(temp, units)
        x = MATRIX_WIDTH - text_width(TINY, value)
        canvas.text(TINY, value, x, y, ramp_color(temp))
        canvas.text(TINY, label, RIGHT_X, y, WHITE if n == 0 else LABEL_COLOR)
        _draw_bar(canvas, y + BAR_OFFSET, pop / 100.0,
                  PRECIP_COLORS.get(sky, DEFAULT_PRECIP_COLOR))


def render_weather(weather, units="f", outlook="days"):
    """The whole panel except the moving part of the icon."""
    canvas = Canvas()
    _draw_now(canvas, weather, units)
    if outlook == "hourly" and weather.hours:
        _draw_hours(canvas, weather, units)
    else:
        _draw_days(canvas, weather, units)
    return canvas


def render_message(lines, color=LABEL_COLOR):
    """A centred card, for before the first forecast arrives and after a fetch
    has failed."""
    canvas = Canvas()
    block = len(lines) * (CAPS_HEIGHT + 2) - 2
    y = (MATRIX_HEIGHT - block) // 2
    for line in lines:
        canvas.centered(CAPS, line, 0, MATRIX_WIDTH, y, color)
        y += CAPS_HEIGHT + 2
    return canvas


# --- The panel ---------------------------------------------------------------

class Panel():
    """Holds the drawn forecast so each frame only has to repaint the sky icon.

    Everything but the 16x16 icon is unchanged between fetches, so it is drawn
    once into a base buffer that every frame starts from. That is what keeps a
    20fps weather display off the CPU: a frame is a 6KB bytearray copy plus one
    small animated cell.
    """

    def __init__(self, units="f", outlook="days"):
        self.units = units
        self.outlook = outlook
        self.weather = None
        self.base = render_message(["WEATHER", "55419"])
        self.sky = None
        self.is_day = True

    def set_weather(self, weather):
        self.weather = weather
        if weather is None:
            return
        self.base = render_weather(weather, self.units, self.outlook)
        self.sky = weather.sky if not weather.stale else "cloudy"
        self.is_day = weather.is_day

    def set_error(self, message="NO DATA"):
        """Only shown while there has never been a forecast to show instead; a
        stale one beats an error card."""
        if self.weather is None:
            self.base = render_message([message], ERROR_COLOR)
            self.sky = None

    def frame(self, phase):
        """One frame as RGB bytes, ready for the matrix."""
        if self.sky is None:
            return self.base.to_bytes()
        canvas = self.base.copy()
        canvas.clip = (ICON_X, ICON_Y, ICON_X + ICON_SIZE, ICON_Y + ICON_SIZE)
        # Clear the cell first: the base holds a still icon so that a single
        # frame looks right on its own, and the two must not composite.
        canvas.rect(ICON_X, ICON_Y, ICON_SIZE, ICON_SIZE, (0, 0, 0))
        paint_icon(canvas, self.sky, self.is_day, phase)
        canvas.clip = None
        return canvas.to_bytes()
