"""A silent film for the 64x32 panel. No rgbmatrix import, so the reel can be
rendered and watched off the Pi.

The whole picture is drawn into a single-channel luminance buffer -- it is a
black and white film -- and only tinted on the way out, which is how tinted
prints were actually made: develop in silver, then dye the finished stock.

Two things shape the rendering:

  * Scenes are a lit screen with dark figures on it, not glowing figures on
    black. A projector throws light through the clear parts of the frame, so
    the sky is bright and everything in front of it is a silhouette. Title
    cards invert this, because an intertitle really is a black card with the
    lettering cut out of it. Damage follows the same physics: a scratch has
    lost its emulsion and passes more light (bright), a hair in the gate
    blocks it (dark).

  * Drawing is sparse pure Python, one shape at a time; every effect that
    touches all 2048 pixels (vignette, grain, fade, iris, tint) is a single
    whole-image PIL op. That is the opposite of the lesson in
    snake_controller.py, and for the opposite reason: numpy lost there because
    a frame was dozens of tiny array calls, each paying ~20us of overhead.
    Here each pass is one C loop over the full frame, so the overhead is paid
    once and the per-pixel work is free.

Everything is spelled in film frames, not seconds. The projector speed sets
how long a frame lasts, so cranking slower makes a longer, more languid film,
exactly as it did in a nickelodeon.
"""

import math
import random

MATRIX_WIDTH = 64
MATRIX_HEIGHT = 32
PIXELS = MATRIX_WIDTH * MATRIX_HEIGHT

# Projector speeds, in frames per second. Silent stock was shot and shown
# anywhere from 14 to 20; 24 only arrived with sound, which is why real silent
# footage looks hurried on modern equipment.
SPEEDS = {'silent': 16.0, 'crank': 11.0, 'talkie': 24.0}
DEFAULT_SPEED = 'silent'

# Tints as (highlight, shadow) RGB. The shadow colour is what a fully exposed
# black area dyes to, the highlight what clear film passes. Interpolating
# between them beats scaling one colour: real tinted prints are warm in the
# whites and cool in the blacks.
TINTS = {
    'sepia':  ((255, 214, 150), (18, 6, 0)),
    'silver': ((255, 253, 246), (4, 6, 10)),
    'night':  ((186, 222, 255), (0, 4, 20)),
}
DEFAULT_TINT = 'sepia'


# --- Title-card typeface ----------------------------------------------------
# Proportional caps, five rows tall, inked with '#'. Proportional because an
# intertitle is set type, and because a fixed 4px cell cannot hold an M or a W
# without turning them into the same blob.

_GLYPHS = {
    'A': ('.##.', '#..#', '####', '#..#', '#..#'),
    'B': ('###.', '#..#', '###.', '#..#', '###.'),
    'C': ('.###', '#...', '#...', '#...', '.###'),
    'D': ('###.', '#..#', '#..#', '#..#', '###.'),
    'E': ('####', '#...', '###.', '#...', '####'),
    'F': ('####', '#...', '###.', '#...', '#...'),
    'G': ('.###', '#...', '#.##', '#..#', '.###'),
    'H': ('#..#', '#..#', '####', '#..#', '#..#'),
    'I': ('###', '.#.', '.#.', '.#.', '###'),
    'J': ('..##', '...#', '...#', '#..#', '.##.'),
    'K': ('#..#', '#.#.', '##..', '#.#.', '#..#'),
    'L': ('#...', '#...', '#...', '#...', '####'),
    'M': ('#...#', '##.##', '#.#.#', '#...#', '#...#'),
    'N': ('#..#', '##.#', '#.##', '#..#', '#..#'),
    'O': ('.##.', '#..#', '#..#', '#..#', '.##.'),
    'P': ('###.', '#..#', '###.', '#...', '#...'),
    'Q': ('.##.', '#..#', '#..#', '#.#.', '.#.#'),
    'R': ('###.', '#..#', '###.', '#.#.', '#..#'),
    'S': ('.###', '#...', '.##.', '...#', '###.'),
    'T': ('#####', '..#..', '..#..', '..#..', '..#..'),
    'U': ('#..#', '#..#', '#..#', '#..#', '.##.'),
    'V': ('#...#', '#...#', '#...#', '.#.#.', '..#..'),
    'W': ('#...#', '#...#', '#.#.#', '##.##', '#...#'),
    'X': ('#...#', '.#.#.', '..#..', '.#.#.', '#...#'),
    'Y': ('#...#', '.#.#.', '..#..', '..#..', '..#..'),
    'Z': ('####', '...#', '.##.', '#...', '####'),
    '0': ('.##.', '#..#', '#..#', '#..#', '.##.'),
    '1': ('.#.', '##.', '.#.', '.#.', '###'),
    '2': ('###.', '...#', '.##.', '#...', '####'),
    '3': ('###.', '...#', '.##.', '...#', '###.'),
    '4': ('#..#', '#..#', '####', '...#', '...#'),
    '5': ('####', '#...', '###.', '...#', '###.'),
    '6': ('.##.', '#...', '###.', '#..#', '.##.'),
    '7': ('####', '...#', '..#.', '.#..', '.#..'),
    '8': ('.##.', '#..#', '.##.', '#..#', '.##.'),
    '9': ('.##.', '#..#', '.###', '...#', '.##.'),
    '.': ('.', '.', '.', '.', '#'),
    ',': ('..', '..', '..', '.#', '#.'),
    '!': ('#', '#', '#', '.', '#'),
    '?': ('###.', '...#', '.##.', '....', '..#.'),
    "'": ('#', '#', '.', '.', '.'),
    '-': ('...', '...', '###', '...', '...'),
    ':': ('.', '#', '.', '#', '.'),
    ' ': ('..', '..', '..', '..', '..'),
}

GLYPH_ROWS = 5
# One blank column between glyphs, two between words at scale 1.
_TRACKING = 1


def glyph_width(char):
    rows = _GLYPHS.get(char)
    return len(rows[0]) if rows else 4


def text_width(text, scale=1):
    """Width in pixels, with no trailing tracking."""
    if not text:
        return 0
    total = sum((glyph_width(c) + _TRACKING) for c in text.upper())
    return total * scale - _TRACKING * scale



# --- The frame ---------------------------------------------------------------

class Frame():
    """One film frame as a luminance bytearray. 0 is fully exposed (black),
    255 is clear stock (brightest the lamp goes)."""

    def __init__(self):
        self.buf = bytearray(PIXELS)

    def fill(self, value):
        self.buf[:] = bytes((value,)) * PIXELS

    def row(self, y, value, x0=0, x1=MATRIX_WIDTH - 1):
        """Horizontal run, clipped. Slice assignment keeps this in C."""
        if y < 0 or y >= MATRIX_HEIGHT:
            return
        x0 = 0 if x0 < 0 else x0
        x1 = MATRIX_WIDTH - 1 if x1 >= MATRIX_WIDTH else x1
        if x1 < x0:
            return
        start = y * MATRIX_WIDTH + x0
        self.buf[start:start + (x1 - x0 + 1)] = bytes((value,)) * (x1 - x0 + 1)

    def column(self, x, value, y0=0, y1=MATRIX_HEIGHT - 1):
        if x < 0 or x >= MATRIX_WIDTH:
            return
        y0 = 0 if y0 < 0 else y0
        y1 = MATRIX_HEIGHT - 1 if y1 >= MATRIX_HEIGHT else y1
        buf = self.buf
        for y in range(y0, y1 + 1):
            buf[y * MATRIX_WIDTH + x] = value

    def rect(self, x0, y0, x1, y1, value):
        for y in range(y0, y1 + 1):
            self.row(y, value, x0, x1)

    def px(self, x, y, value):
        if 0 <= x < MATRIX_WIDTH and 0 <= y < MATRIX_HEIGHT:
            self.buf[y * MATRIX_WIDTH + x] = value

    def light(self, x, y, value):
        """Raise a pixel toward `value`, never lower it. Light adds."""
        if 0 <= x < MATRIX_WIDTH and 0 <= y < MATRIX_HEIGHT:
            index = y * MATRIX_WIDTH + x
            if self.buf[index] < value:
                self.buf[index] = value

    def disc(self, cx, cy, radius, value):
        """Filled circle at a fractional centre, one row-run per scanline."""
        if radius <= 0:
            return
        top = int(math.floor(cy - radius))
        bottom = int(math.ceil(cy + radius))
        r2 = radius * radius
        for y in range(max(0, top), min(MATRIX_HEIGHT - 1, bottom) + 1):
            dy = y - cy
            span2 = r2 - dy * dy
            if span2 <= 0:
                continue
            span = math.sqrt(span2)
            # Clip inward rather than rounding outward: rounding both ends out
            # adds a pixel each side and a small disc comes out square.
            self.row(y, value, int(math.ceil(cx - span)), int(math.floor(cx + span)))

    def ring(self, cx, cy, radius, value):
        steps = max(8, int(radius * 7))
        for i in range(steps):
            angle = 2 * math.pi * i / steps
            self.px(int(round(cx + radius * math.cos(angle))),
                    int(round(cy + radius * math.sin(angle))), value)

    def sprite(self, art, x, y, value, flip=False, scale=1):
        """Stamp string art. '.' and ' ' are transparent, anything else inks.
        `scale` is how a shot cuts in closer without a second drawing."""
        for row_index, row in enumerate(art):
            width = len(row)
            for col, cell in enumerate(row):
                if cell == '.' or cell == ' ':
                    continue
                col = width - 1 - col if flip else col
                if scale == 1:
                    self.px(x + col, y + row_index, value)
                else:
                    self.rect(x + col * scale, y + row_index * scale,
                              x + col * scale + scale - 1,
                              y + row_index * scale + scale - 1, value)

    def text(self, text, x, y, value, scale=1):
        """Draw at top-left (x, y). Returns the x just past the last glyph."""
        for char in text.upper():
            art = _GLYPHS.get(char)
            width = glyph_width(char)
            if art is not None and char != ' ':
                if scale == 1:
                    self.sprite(art, x, y, value)
                else:
                    for row_index, row in enumerate(art):
                        for col, cell in enumerate(row):
                            if cell == '#':
                                self.rect(x + col * scale, y + row_index * scale,
                                          x + col * scale + scale - 1,
                                          y + row_index * scale + scale - 1, value)
            x += (width + _TRACKING) * scale
        return x - _TRACKING * scale

    def centered(self, text, y, value, scale=1):
        self.text(text, (MATRIX_WIDTH - text_width(text, scale)) // 2, y, value, scale)

    def shift_rows(self, dy, fill_value):
        """Slip the film in the gate. Vacated rows get the frame line."""
        if not dy:
            return
        buf = self.buf
        offset = abs(dy) * MATRIX_WIDTH
        if dy > 0:
            buf[offset:] = buf[:PIXELS - offset]
            buf[:offset] = bytes((fill_value,)) * offset
        else:
            buf[:PIXELS - offset] = buf[offset:]
            buf[PIXELS - offset:] = bytes((fill_value,)) * offset


# --- Exposure levels ---------------------------------------------------------
# Scenes are a lit screen with dark actors on it. Silhouettes sit just above
# zero rather than at it, so the panel still shows shape inside a figure.

SKY_TOP = 92
SKY_HORIZON = 204
HILLS = 80
GROUND = 66
BALLAST = 82
RAIL = 200
TIE = 44
DARK = 3
SMOKE = 26
LAMP = 255
GLOW = 170
ROPE = 170
INK = 235          # lettering on a title card
CARD = 4           # the card itself: black stock, not quite nothing

HORIZON = 16
RAIL_FAR = 21
RAIL_NEAR = 24
STAND_Y = 20       # feet of anyone standing behind the track
FRONT_Y = 31       # feet of anyone in the foreground, in front of the track


# --- The set -----------------------------------------------------------------

_HILL_PROFILE = (18, 17, 17, 16, 16, 15, 15, 16, 17, 17, 16, 15, 14, 14, 15, 16,
                 17, 17, 18, 17, 16, 16, 15, 15, 14, 15, 16, 17, 17, 16, 16, 15,
                 15, 16, 16, 17, 17, 17, 16, 15, 15, 14, 14, 15, 16, 16, 17, 17,
                 16, 16, 15, 15, 16, 17, 17, 16, 16, 15, 14, 14, 15, 16, 17, 17)


def draw_sky(frame, lamp=True):
    """Dawn gradient: brightest at the horizon, which is where the eye expects
    the light to come from and keeps the top of the panel from glaring."""
    for y in range(0, HORIZON):
        t = y / float(HORIZON - 1)
        frame.row(y, int(SKY_TOP + (SKY_HORIZON - SKY_TOP) * t * t))
    if lamp:
        # Low sun, or a low moon under the night tint. Same disc either way:
        # silent films shot day-for-night and let the dye do the talking.
        frame.disc(12, 4, 2.6, 226)
        frame.disc(12, 4, 1.4, 248)
    # Cloud bars, a shade off the sky behind them.
    frame.row(2, SKY_TOP + 20, 34, 52)
    frame.row(3, SKY_TOP + 13, 38, 48)
    frame.row(7, SKY_TOP + 26, 20, 40)
    frame.row(8, SKY_TOP + 18, 24, 36)


def draw_ground(frame):
    for x in range(MATRIX_WIDTH):
        frame.column(x, HILLS, _HILL_PROFILE[x], HORIZON)
    frame.rect(0, HORIZON + 1, MATRIX_WIDTH - 1, MATRIX_HEIGHT - 1, GROUND)
    frame.rect(0, RAIL_FAR - 2, MATRIX_WIDTH - 1, RAIL_NEAR + 2, BALLAST)


def draw_track(frame, shimmer=0):
    """Rails in perspective-free elevation: two bright lines with ties under
    them. `shimmer` lifts the steel as a headlight finds it."""
    for x in range(0, MATRIX_WIDTH, 4):
        frame.rect(x, RAIL_FAR - 1, x + 1, RAIL_NEAR + 1, TIE)
    value = min(255, RAIL + shimmer)
    frame.row(RAIL_FAR, value)
    frame.row(RAIL_NEAR, value)


POLE = ('#', '#', '#', '#', '#', '#', '#', '#', '#')


def draw_poles(frame, offset=0):
    """Telegraph poles along the line. Nothing says 'railroad' faster."""
    for base in (7, 29, 51, 73):
        x = base - offset
        if -3 <= x < MATRIX_WIDTH + 3:
            frame.sprite(POLE, x, HORIZON - 9, DARK)
            frame.row(HORIZON - 9, DARK, x - 2, x + 2)
            frame.row(HORIZON - 7, DARK, x - 2, x + 2)


def set_trackside(frame, lamp=True, shimmer=0, poles=0):
    draw_sky(frame, lamp)
    draw_poles(frame, poles)
    draw_ground(frame)
    draw_track(frame, shimmer)


# --- The players -------------------------------------------------------------

# Lady Maude is a bell: narrow at the shoulders, wide at the hem. Without
# that flare she and Silas were the same dark lump in a wide shot, and the
# only way to tell them apart was his hat.
MAUDE = (
    '..###...',
    '..####..',
    '...##...',
    '..####..',
    '.#####..',
    '..####..',
    '..####..',
    '.######.',
    '.######.',
    '########',
)

MAUDE_PLEADING = (
    '..###...',
    '..####..',
    '#..##...',
    '######..',
    '.#####..',
    '..####..',
    '..####..',
    '.######.',
    '.######.',
    '########',
)

MAUDE_BOUND = (
    '.##..........',
    '####...######',
    '#############',
    '####...######',
    '.##.....#####',
)

SILAS = (
    '..###..',
    '..###..',
    '#######',
    '..###..',
    '...#...',
    '.#####.',
    '#######',
    '#######',
    '.#####.',
    '..#.#..',
    '..#.#..',
)

SILAS_DOFFED = (
    '.......',
    '.......',
    '..###..',
    '..###..',
    '#..#...',
    '.#####.',
    '#######',
    '#######',
    '.#####.',
    '..#.#..',
    '..#.#..',
)

SILAS_GLOAT = (
    '..###..',
    '..###..',
    '#######',
    '..###..',
    '...#...',
    '.#####.',
    '###.###',
    '##...##',
    '.#####.',
    '.##.##.',
    '.#...#.',
)

TOP_HAT = (
    '.###.',
    '.###.',
    '#####',
)

HERO = (
    '.####.',
    '..##..',
    '.####.',
    '######',
    '.####.',
    '.####.',
    '.####.',
    '..##..',
    '.#..#.',
    '.#..#.',
)

HERO_RUN = (
    '.####.',
    '..##..',
    '.####.',
    '.#####',
    '.####.',
    '.####.',
    '.####.',
    '..##..',
    '#...##',
    '#.....',
)

HERO_CARRY = (
    '.####......',
    '..##.......',
    '.####.###..',
    '###########',
    '.####..####',
    '.####...##.',
    '.####......',
    '..##.......',
    '.#..#......',
    '#...#......',
)

COUPLE = (
    '.##..##.',
    '####.###',
    '.##..##.',
    '########',
    '.######.',
    '.######.',
    '.######.',
    '.##.###.',
    '.#..###.',
    '.#..####',
)


def draw_road(frame):
    """A dusty crossing road along the bottom. It is there for contrast: the
    foreground needs a pale surface or anything silhouetted against it
    disappears into the ground."""
    frame.rect(0, 28, MATRIX_WIDTH - 1, MATRIX_HEIGHT - 1, 96)
    frame.row(27, 70)
    for x in range(2, MATRIX_WIDTH, 9):
        frame.px(x, 30, 76)
        frame.px(x + 4, 29, 118)


# --- Rolling stock -----------------------------------------------------------

def draw_loco(frame, front_x, rail_y, scale=1.0, cars=0, lamp=True):
    """A locomotive facing left, measured from the cowcatcher tip. Drawn from
    rectangles rather than string art so the same engine can be a speck on the
    horizon and a wall of iron, which is the whole trick of the approach."""
    def u(value):
        return int(round(value * scale))

    x = int(round(front_x))
    chassis = rail_y - u(4)
    boiler_top = rail_y - u(12)

    # Wheels first; everything else covers them.
    for wheel in (5, 11, 16):
        frame.disc(x + u(wheel), rail_y - u(2), max(1.0, 2.2 * scale), DARK)
    frame.rect(x + u(1), chassis, x + u(26), rail_y - u(2), DARK)
    # Cowcatcher: a wedge, so it reads as a front even at a few pixels.
    for step in range(u(4) + 1):
        frame.column(x - u(3) + step, DARK, rail_y - u(1) - step, rail_y - u(1))
    frame.rect(x + u(1), boiler_top, x + u(18), chassis, DARK)
    frame.rect(x + u(4), rail_y - u(16), x + u(7), boiler_top, DARK)      # stack
    frame.rect(x + u(3), rail_y - u(17), x + u(8), rail_y - u(16), DARK)  # stack lip
    frame.rect(x + u(11), rail_y - u(14), x + u(13), boiler_top, DARK)    # steam dome
    frame.rect(x + u(18), rail_y - u(17), x + u(27), chassis, DARK)       # cab
    if scale > 0.55:
        # The cab window is a hole in the silhouette, so the firebox light
        # comes through it.
        frame.rect(x + u(20), rail_y - u(15), x + u(24), rail_y - u(11), 168)
        frame.rect(x + u(2), rail_y - u(10), x + u(3), rail_y - u(9), 96)
    if cars:
        back = x + u(28)
        for car in range(cars):
            left = back + car * u(22)
            frame.rect(left, rail_y - u(14), left + u(20), rail_y - u(3), DARK)
            for window in range(3):
                wx = left + u(3) + window * u(6)
                frame.rect(wx, rail_y - u(12), wx + u(2), rail_y - u(9), 150)
    if lamp:
        radius = max(1.0, 2.0 * scale)
        frame.disc(x + u(2), rail_y - u(13), radius + 1.6, GLOW)
        frame.disc(x + u(2), rail_y - u(13), radius, LAMP)
        # The beam: a taper thrown ahead down the line. Light only adds, so it
        # brightens the rails it crosses instead of greying out the sky.
        for step in range(u(20)):
            spread = step // 6
            value = max(70, 210 - step * 7)
            for dy in range(-spread, spread + 1):
                frame.light(x - u(1) - step, rail_y - u(13) + dy + (step >> 3), value)


def draw_loco_close(frame, grow):
    """The cut-in on the engine: head on, with the rails running away under it.
    `grow` runs 0 -> 1 across the cross-cut. Converging rails do the work here
    -- without them a dark mass in the middle of the frame is just a box."""
    vanish = 12
    for side in (-1, 1):
        for y in range(vanish, MATRIX_HEIGHT):
            reach = (y - vanish) / float(MATRIX_HEIGHT - 1 - vanish)
            x = int(32 + side * (1.5 + reach * 36))
            frame.light(x, y, RAIL)
            frame.light(x + side, y, RAIL - 50)

    half = 7.0 + 23.0 * grow
    crown = 17.0 - 14.0 * grow
    middle = crown + half * 0.75
    stack = max(1, int(half * 0.2))
    frame.rect(32 - stack, int(crown - half * 0.55), 32 + stack, int(crown + 2), DARK)
    frame.disc(32, middle, half, DARK)
    frame.rect(int(32 - half), int(middle), int(32 + half), MATRIX_HEIGHT - 1, DARK)
    lamp = max(1.2, half * 0.26)
    frame.disc(32, middle - half * 0.2, lamp + 2.0 + grow * 2.0, GLOW)
    frame.disc(32, middle - half * 0.2, lamp, LAMP)


def draw_smoke(frame, stack_x, stack_y, phase, drift=1.4, count=6, spacing=4):
    """Deterministic puffs: every shot is a pure function of its frame index,
    so nothing has to be carried between frames."""
    for puff in range(count):
        age = phase + puff * spacing
        x = stack_x + age * drift
        y = stack_y - age * 0.55
        radius = 1.0 + age * 0.14
        if y + radius < 0 or x - radius > MATRIX_WIDTH or x + radius < 0:
            continue
        # Puffs thin out as they rise: the sky shows through an old one.
        value = min(SKY_HORIZON - 6, SMOKE + int(age * 2.6))
        frame.disc(x, y, radius, value)


# --- The motor car -----------------------------------------------------------

def draw_car(frame, x, base_y, travelled, driver=True):
    """A runabout, seen from the side. Spoked wheels are rings rather than
    discs so the road shows through them as they turn, and the body is one
    unbroken mass from wheel to wheel -- drawn any thinner, the silhouette
    reads as an animal with four legs."""
    x = int(round(x))
    frame.rect(x + 1, base_y - 8, x + 18, base_y - 4, DARK)      # chassis
    frame.rect(x + 11, base_y - 10, x + 18, base_y - 8, DARK)    # bonnet
    frame.rect(x + 3, base_y - 12, x + 10, base_y - 8, DARK)     # body
    frame.rect(x + 2, base_y - 14, x + 6, base_y - 12, DARK)     # folded top
    frame.px(x + 19, base_y - 10, LAMP)                          # acetylene lamp
    frame.px(x + 19, base_y - 9, GLOW)
    if driver:
        frame.disc(x + 9, base_y - 14, 1.3, DARK)
        frame.row(base_y - 15, DARK, x + 7, x + 11)              # motoring cap
    for centre in (x + 5, x + 15):
        frame.ring(centre, base_y - 3, 2.6, DARK)
        for spoke in range(3):
            angle = travelled * 0.9 + spoke * math.pi / 3
            dx = math.cos(angle) * 2.6
            dy = math.sin(angle) * 2.6
            for step in range(1, 6):
                frame.px(int(round(centre + dx * step / 5.0)),
                         int(round(base_y - 3 + dy * step / 5.0)), DARK)


def draw_dust(frame, x, base_y, phase, count=5):
    """Dust kicked up behind the car. Dust catches the light; smoke blocks it."""
    for puff in range(count):
        age = phase + puff * 3
        radius = 1.0 + age * 0.22
        frame.disc(x - age * 1.1, base_y - 2 - age * 0.25, radius,
                   max(60, 150 - age * 7))


SILAS_CROUCH = (
    '..###..',
    '..###..',
    '#######',
    '..###..',
    '.#####.',
    '#######',
    '##...##',
)

MAUDE_STRUGGLE = (
    '.##.....##...',
    '####...######',
    '#############',
    '####...######',
    '.##.....#####',
)


# --- Intertitles -------------------------------------------------------------

def card(frame, lines, scale=1, border=True, ink=INK):
    """A title card: black stock with the lettering cut out of it, which is why
    the ink is the bright part here and the dark part everywhere else."""
    frame.fill(CARD)
    if border:
        frame.row(1, 120, 2, MATRIX_WIDTH - 3)
        frame.row(MATRIX_HEIGHT - 2, 120, 2, MATRIX_WIDTH - 3)
        frame.column(1, 120, 2, MATRIX_HEIGHT - 3)
        frame.column(MATRIX_WIDTH - 2, 120, 2, MATRIX_HEIGHT - 3)
        for corner_x, corner_y in ((1, 1), (MATRIX_WIDTH - 2, 1),
                                   (1, MATRIX_HEIGHT - 2),
                                   (MATRIX_WIDTH - 2, MATRIX_HEIGHT - 2)):
            frame.px(corner_x, corner_y, INK)
    line_step = (GLYPH_ROWS + 2) * scale
    block = line_step * len(lines) - 2 * scale
    y = (MATRIX_HEIGHT - block) // 2
    for line in lines:
        if line:
            frame.centered(line, y, ink, scale)
        y += line_step


def shot_leader(frame, i, n):
    """Academy leader. Every projectionist's countdown, and it tells anyone
    watching that what follows is meant to be a film."""
    frame.fill(CARD)
    count = 3 - i * 3 // n
    frame.ring(32, 16, 13.0, 90)
    frame.ring(32, 16, 12.0, 60)
    sweep = (i % (n // 3)) / float(n // 3) * 2 * math.pi - math.pi / 2
    for step in range(1, 13):
        frame.px(int(round(32 + math.cos(sweep) * step)),
                 int(round(16 + math.sin(sweep) * step)), 150)
    frame.centered(str(count), 8, INK, 3)


def shot_title(frame, i, n):
    frame.fill(CARD)
    frame.centered('THE', 2, 150)
    frame.centered('LAST', 8, INK, 2)
    frame.centered('TRAIN', 20, INK, 2)


def shot_credits(frame, i, n):
    card(frame, ['A HOMECOURT', 'PICTURE', 'IN FOUR ACTS'])


def shot_cast(frame, i, n):
    card(frame, ['THE PLAYERS', 'LADY MAUDE', 'SILAS BLACK', 'OUR HERO'],
         border=False)
    frame.row(8, 90, 14, 49)


def _card_shot(lines):
    """A shot that is nothing but a title card."""
    def draw(frame, i, n):
        card(frame, lines)
    return draw


def shot_the_end(frame, i, n):
    frame.fill(CARD)
    frame.centered('THE', 4, INK, 2)
    frame.centered('END', 17, INK, 2)
    frame.row(15, 110, 22, 41)


# --- Direction ---------------------------------------------------------------
# Beats are fractions of a shot, so a shot can be lengthened or shortened in
# one place without re-timing everything inside it.

def _beat(i, n, start, end):
    """Position within a beat as 0.0 -> 1.0, or None if the shot isn't there."""
    first = start * n
    last = end * n
    if i < first or i >= last:
        return None
    return (i - first) / float(last - first)


def _lerp(a, b, t):
    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
    return a + (b - a) * t


def _step(i, period=6):
    """Walking bob: half a period up, half down."""
    return 1 if (i // (period // 2)) % 2 else 0


# --- Act One: the proposal ---------------------------------------------------

def scene_proposal(frame, i, n):
    maude_x = 38

    # Dialogue cards cut in hard, with no fade. That is how they were cut.
    if _beat(i, n, 0.36, 0.48) is not None:
        card(frame, ['MARRY ME,', 'LADY MAUDE!'])
        return
    if _beat(i, n, 0.56, 0.66) is not None:
        card(frame, ['NEVER,', 'SIR!'])
        return

    set_trackside(frame)
    draw_road(frame)

    t = _beat(i, n, 0.0, 0.28)
    if t is not None:                                   # he comes up the line
        frame.sprite(MAUDE, maude_x, STAND_Y - 9, DARK, flip=True)
        frame.sprite(SILAS, int(_lerp(-9, 26, t)), STAND_Y - 10 - _step(i), DARK)
        return

    t = _beat(i, n, 0.28, 0.36)
    if t is not None:                                   # hat off, a deep bow
        frame.sprite(MAUDE, maude_x, STAND_Y - 9, DARK, flip=True)
        frame.sprite(SILAS_DOFFED, 26, STAND_Y - 10, DARK)
        frame.sprite(TOP_HAT, 22, STAND_Y - 7, DARK)
        return

    t = _beat(i, n, 0.48, 0.56)
    if t is not None:                                   # she turns her back
        frame.sprite(MAUDE, maude_x, STAND_Y - 9, DARK)
        frame.sprite(SILAS_DOFFED, 26, STAND_Y - 10, DARK)
        frame.sprite(TOP_HAT, 22, STAND_Y - 7, DARK)
        return

    t = _beat(i, n, 0.66, 0.74)
    if t is not None:                                   # he will not be told
        frame.sprite(MAUDE_PLEADING, maude_x, STAND_Y - 9, DARK)
        frame.sprite(SILAS, int(_lerp(26, 31, t)), STAND_Y - 10, DARK)
        return

    t = _beat(i, n, 0.74, 0.82)
    if t is not None:                                   # the slap
        frame.sprite(MAUDE_PLEADING, maude_x, STAND_Y - 9, DARK, flip=True)
        frame.sprite(SILAS_DOFFED, 31, STAND_Y - 10, DARK)
        flight = t * 10.0
        frame.sprite(TOP_HAT, int(33 - flight * 1.6),
                     int(STAND_Y - 13 - flight * 1.9 + flight * flight * 0.22), DARK)
        return

    t = _beat(i, n, 0.82, 0.93)
    if t is not None:                                   # she leaves, he fumes
        frame.sprite(MAUDE, int(_lerp(maude_x, 68, t)), STAND_Y - 9 - _step(i), DARK)
        frame.sprite(SILAS_GLOAT if i % 4 < 2 else SILAS_DOFFED, 31, STAND_Y - 10, DARK)
        return

    # Alone with the railway line. An idea arrives, and the rails catch it.
    frame.sprite(SILAS_DOFFED, 31, STAND_Y - 10, DARK, flip=True)
    frame.light(28, RAIL_FAR, 255)
    frame.light(21, RAIL_NEAR, 255)


# --- Act Two: the deed -------------------------------------------------------

BOUND_X = 33


def _ropes(frame, count, x=BOUND_X):
    for rope in range(count):
        frame.column(x + 3 + rope * 4, ROPE, RAIL_FAR - 1, RAIL_NEAR + 1)


def scene_deed(frame, i, n):
    set_trackside(frame)
    draw_road(frame)

    t = _beat(i, n, 0.0, 0.30)
    if t is not None:                                   # dragged to the line
        x = int(_lerp(-10, 26, t))
        frame.sprite(SILAS, x, STAND_Y - 10 - _step(i, 4), DARK)
        frame.sprite(MAUDE_PLEADING, x + 7, STAND_Y - 9, DARK, flip=True)
        return

    t = _beat(i, n, 0.30, 0.40)
    if t is not None:                                   # down onto the rails
        frame.sprite(SILAS, 26, STAND_Y - 10, DARK)
        frame.sprite(MAUDE_PLEADING, 33, int(_lerp(STAND_Y - 9, STAND_Y + 1, t)), DARK, flip=True)
        return

    t = _beat(i, n, 0.40, 0.66)
    if t is not None:                                   # the lashings, one by one
        frame.sprite(MAUDE_STRUGGLE if i % 6 < 3 else MAUDE_BOUND, BOUND_X, RAIL_FAR - 1, DARK)
        _ropes(frame, min(3, int(t * 3.4)))
        frame.sprite(SILAS_CROUCH, 26, STAND_Y - 6 - _step(i, 4), DARK)
        return

    if _beat(i, n, 0.66, 0.76) is not None:
        card(frame, ['THE 8:15 WILL', 'SETTLE THE', 'MATTER!'])
        return

    t = _beat(i, n, 0.76, 0.88)
    if t is not None:                                   # a hearty laugh
        frame.sprite(MAUDE_STRUGGLE if i % 6 < 3 else MAUDE_BOUND, BOUND_X, RAIL_FAR - 1, DARK)
        _ropes(frame, 3)
        frame.sprite(SILAS_GLOAT, 20, STAND_Y - 10 - _step(i, 4), DARK)
        return

    t = _beat(i, n, 0.88, 1.0)                          # and away he goes
    frame.sprite(MAUDE_STRUGGLE if i % 6 < 3 else MAUDE_BOUND, BOUND_X, RAIL_FAR - 1, DARK)
    _ropes(frame, 3)
    frame.sprite(SILAS, int(_lerp(20, -12, t)), STAND_Y - 10 - _step(i), DARK)


HERO_CROUCH = (
    '.####.',
    '..##..',
    '.####.',
    '######',
    '######',
    '##..##',
)


# --- Act Three: the 8:15 -----------------------------------------------------

def _bound_maude(frame, i, ropes=3):
    frame.sprite(MAUDE_STRUGGLE if i % 6 < 3 else MAUDE_BOUND, BOUND_X, RAIL_FAR - 1, DARK)
    _ropes(frame, ropes)


def backdrop_close(frame):
    """Backdrop for a cut-in. No track furniture: the camera is too close for
    any of it to be in shot."""
    draw_sky(frame, lamp=False)
    frame.rect(0, HORIZON + 1, MATRIX_WIDTH - 1, MATRIX_HEIGHT - 1, GROUND)


MAUDE_CLOSE = (
    '......####..............................',
    '.....######.............................',
    '.....######.............................',
    '......####..............................',
    '.......##...............................',
    '....##########..........................',
    '...############.........................',
    '...##############.......................',
    '....###################.................',
    '.....#########################..........',
    '......###############################...',
    '.......##############################...',
    '.........############################...',
    '............#########################...',
)


def shot_close_maude(frame, i):
    """The cut-in on Lady Maude. Drawn at this size rather than stamped from
    the wide shot at double scale: scaling the small sprite turned the gap
    between her bodice and her skirt into a six-pixel hole, and the shot read
    as a row of bars instead of a person. Nothing else is in this frame --
    sleepers crossing her only put her back behind bars."""
    frame.fill(BALLAST)
    frame.rect(0, 2, MATRIX_WIDTH - 1, 4, RAIL)
    frame.rect(0, 27, MATRIX_WIDTH - 1, 29, RAIL)
    frame.row(5, BALLAST - 18)
    frame.row(26, BALLAST - 18)
    x = 12
    frame.sprite(MAUDE_CLOSE, x, 8 if i % 4 < 2 else 9, DARK)
    for rope in (14, 28):
        frame.column(x + rope, ROPE, 2, 29)
        frame.column(x + rope + 1, ROPE - 60, 2, 29)


CROSS_CUTS = ((13, 0), (11, 1), (9, 0), (8, 1), (6, 0), (5, 1), (4, 0), (4, 1))


def scene_approach(frame, i, n):
    t = _beat(i, n, 0.0, 0.16)
    if t is not None:                                   # a speck down the line
        set_trackside(frame)
        draw_road(frame)
        _bound_maude(frame, i)
        if t > 0.45:
            frame.light(63, RAIL_FAR - 3, 255)
            frame.light(62, RAIL_FAR - 3, 190)
        return

    t = _beat(i, n, 0.16, 0.38)
    if t is not None:                                   # and it is coming on
        set_trackside(frame, shimmer=int(t * 44))
        draw_road(frame)
        scale = _lerp(0.14, 0.34, t)
        front = _lerp(76, 58, t)
        draw_loco(frame, front, RAIL_NEAR, scale)
        draw_smoke(frame, front + 6 * scale, RAIL_NEAR - 18 * scale, i % 9,
                   drift=0.9, count=5, spacing=5)
        _bound_maude(frame, i)
        return

    t = _beat(i, n, 0.38, 0.76)
    if t is not None:
        # Cross-cutting, the trick Griffith built this whole genre on: two
        # places at once, and the cuts get shorter as the gap closes.
        local = i - int(0.38 * n)
        edge = 0
        for index, (length, which) in enumerate(CROSS_CUTS):
            edge += length
            if local < edge or index == len(CROSS_CUTS) - 1:
                if which:
                    shot_close_maude(frame, i)
                else:
                    backdrop_close(frame)
                    grow = _lerp(0.22, 0.95, index / float(len(CROSS_CUTS) - 1))
                    draw_loco_close(frame, grow)
                    draw_smoke(frame, 32, 2, i % 7, drift=1.8, count=4, spacing=3)
                return
        return

    t = _beat(i, n, 0.76, 1.0)                          # back out wide, closing
    set_trackside(frame, lamp=False, shimmer=int(_lerp(50, 90, t)))
    draw_road(frame)
    front = _lerp(60, 52, t)
    draw_loco(frame, front, RAIL_NEAR, _lerp(0.36, 0.56, t))
    draw_smoke(frame, front + 4, RAIL_NEAR - 9, i % 7, drift=1.2, count=5, spacing=4)
    _bound_maude(frame, i)


# --- Act Four: our hero ------------------------------------------------------

CAR_PARK_X = 2


def scene_rescue(frame, i, n):
    shimmer = int(_lerp(60, 120, i / float(n)))
    set_trackside(frame, lamp=False, shimmer=shimmer)
    draw_road(frame)

    # The engine runs through the whole act, somewhere down the line, and is
    # always drawn before anyone standing in front of the track.
    train = _beat(i, n, 0.0, 0.58)
    if train is not None:
        # The engine has to be *in shot* while the rescue happens, or there is
        # no clock running. Its nose clears the right edge immediately and it
        # grows from there.
        scale = _lerp(0.40, 0.95, train)
        front = _lerp(63, 50, train * train)
        draw_loco(frame, front, RAIL_NEAR, scale)
        draw_smoke(frame, front + 6, RAIL_NEAR - 16 * scale, i % 7,
                   drift=1.3, count=5, spacing=4)
    else:
        train = _beat(i, n, 0.58, 0.84)
        if train is not None:                           # and through it comes
            front = _lerp(50, -88, train)
            draw_loco(frame, front, RAIL_NEAR, 1.0, cars=2)
            draw_smoke(frame, front + 8, RAIL_NEAR - 17, i % 5,
                       drift=2.6, count=7, spacing=3)
        else:
            draw_smoke(frame, -10, RAIL_NEAR - 16, i % 11, drift=2.2, count=6, spacing=5)

    t = _beat(i, n, 0.0, 0.16)
    if t is not None:                                   # a motor car, flat out
        x = _lerp(-30, CAR_PARK_X, 1.0 - (1.0 - t) ** 2)
        draw_dust(frame, x, 31, i % 4, count=5)
        draw_car(frame, x, 31 - _step(i, 4), i * 3.0)
        _bound_maude(frame, i)
        return

    t = _beat(i, n, 0.16, 0.24)
    if t is not None:                                   # brakes, and a cloud
        draw_dust(frame, CAR_PARK_X - 2, 31, int(t * 9), count=7)
        draw_car(frame, CAR_PARK_X, 31, 18.0)
        _bound_maude(frame, i)
        return

    draw_car(frame, CAR_PARK_X, 31, 18.0, driver=False)

    t = _beat(i, n, 0.24, 0.36)
    if t is not None:                                   # up the embankment
        _bound_maude(frame, i)
        frame.sprite(HERO_RUN if i % 4 < 2 else HERO, int(_lerp(16, 30, t)),
                     int(_lerp(31, 26, t)) - 9, DARK)
        return

    t = _beat(i, n, 0.36, 0.48)
    if t is not None:                                   # the knots
        _bound_maude(frame, i, ropes=max(0, 3 - int(t * 3.6)))
        frame.sprite(HERO_CROUCH, 28, 26 - 5 - _step(i, 4), DARK)
        return

    t = _beat(i, n, 0.48, 0.58)
    if t is not None:                                   # clear of the line
        frame.sprite(HERO_CARRY, int(_lerp(30, 24, t)), int(_lerp(26, 31, t)) - 9,
                     DARK, flip=True)
        return

    frame.sprite(COUPLE, 24, FRONT_Y - 9, DARK)


# --- The reel ----------------------------------------------------------------

class Shot():
    """One continuous take, with its transitions. Lengths are in film frames,
    so projector speed decides how long a shot lasts."""

    def __init__(self, frames, draw, fade_in=0, fade_out=0,
                 iris_in=0, iris_out=0, iris_at=(32, 16)):
        self.frames = frames
        self.draw = draw
        self.fade_in = fade_in
        self.fade_out = fade_out
        self.iris_in = iris_in
        self.iris_out = iris_out
        self.iris_at = iris_at


REEL = (
    Shot(21, shot_leader),
    Shot(46, shot_title, fade_in=8, fade_out=6),
    Shot(34, shot_credits, fade_in=5, fade_out=5),
    Shot(42, shot_cast, fade_in=5, fade_out=5),

    Shot(30, _card_shot(['ACT ONE', 'A VILE', 'PROPOSAL']), fade_in=5, fade_out=4),
    Shot(150, scene_proposal, iris_in=12, fade_out=6),

    Shot(30, _card_shot(['ACT TWO', 'A DASTARDLY', 'DEED']), fade_in=5, fade_out=4),
    Shot(150, scene_deed, fade_in=6, fade_out=6),

    Shot(30, _card_shot(['ACT THREE', 'THE 8:15', 'APPROACHES']), fade_in=5, fade_out=4),
    Shot(165, scene_approach, fade_in=6),
    Shot(26, _card_shot(['HEAVEN HELP', 'HER!'])),

    Shot(30, _card_shot(['ACT FOUR', 'OUR HERO', 'RIDES!']), fade_in=5, fade_out=4),
    Shot(190, scene_rescue, fade_in=6, iris_out=16, iris_at=(28, 26)),

    Shot(50, shot_the_end, fade_in=6, fade_out=14),
)

REEL_FRAMES = sum(shot.frames for shot in REEL)


# --- The projector -----------------------------------------------------------

GRAIN_FRAMES = 12
GRAIN_AMPLITUDE = 7
VIGNETTE_DEPTH = 0.34


def _build_vignette():
    """Lens falloff. More than anything else, this is what makes the panel read
    as something being projected onto, rather than a lamp being switched on."""
    buf = bytearray(PIXELS)
    cx = (MATRIX_WIDTH - 1) / 2.0
    cy = (MATRIX_HEIGHT - 1) / 2.0
    longest = math.sqrt(cx * cx + cy * cy)
    index = 0
    for y in range(MATRIX_HEIGHT):
        dy = (y - cy) / longest
        for x in range(MATRIX_WIDTH):
            dx = (x - cx) / longest
            radius = math.sqrt(dx * dx + dy * dy)
            buf[index] = int(255 * (1.0 - VIGNETTE_DEPTH * radius ** 2.4))
            index += 1
    return bytes(buf)


class Projector():
    """Runs the reel: one frame per call, tinted and worn, ready for the panel.

    Everything here is a whole-frame pass, so each one is a single PIL call
    over 2048 pixels rather than a Python loop.
    """

    def __init__(self, options=None, seed=None):
        from PIL import Image, ImageChops
        self._Image = Image
        self._ImageChops = ImageChops

        options = options or {}
        speed = options.get('film_speed')
        self.fps = SPEEDS.get(speed, SPEEDS[DEFAULT_SPEED])
        tint = options.get('film_tint')
        self.tint = tint if tint in TINTS else DEFAULT_TINT
        # A restored print is the clean scan: no grain, no scratches, no gate
        # weave. Off by default, because the wear is the point.
        self.worn = not options.get('film_restored')

        self.random = random.Random(seed)
        self.frame = Frame()
        self.shot_index = 0
        self.position = 0
        self.frames_shown = 0

        self._luts = {}
        self._iris_masks = {}
        self._gain = 1.0
        self._judder = 0
        self._scratch = None
        self._vignette = Image.frombytes('L', (MATRIX_WIDTH, MATRIX_HEIGHT),
                                         _build_vignette())
        self._grain = [
            Image.frombytes('L', (MATRIX_WIDTH, MATRIX_HEIGHT),
                            bytes(self.random.randrange(2 * GRAIN_AMPLITUDE + 1)
                                  for _ in range(PIXELS)))
            for _ in range(GRAIN_FRAMES)]

    # -- lookup tables --------------------------------------------------------

    def _lut(self, gain):
        """Tint plus exposure in one 3x256 table, cached per quantised gain.
        Dyeing the finished print is exactly how tinted stock was made."""
        key = int(gain * 48)
        table = self._luts.get(key)
        if table is None:
            gain = key / 48.0
            high, low = TINTS[self.tint]
            table = []
            for channel in range(3):
                base = low[channel]
                span = high[channel] - base
                column = []
                for value in range(256):
                    lit = value * gain
                    lit = 255.0 if lit > 255.0 else lit
                    column.append(int(base + span * lit / 255.0))
                table.append(column)
            self._luts[key] = table
        return table

    def _iris(self, centre, radius):
        # Keyed on the centre too: the iris does not always close on the
        # middle of the frame.
        key = (centre, radius)
        mask = self._iris_masks.get(key)
        if mask is None:
            cut = Frame()
            cut.disc(centre[0], centre[1], radius, 255)
            mask = self._Image.frombytes('L', (MATRIX_WIDTH, MATRIX_HEIGHT),
                                         bytes(cut.buf))
            self._iris_masks[key] = mask
        return mask

    # -- wear -----------------------------------------------------------------

    def _wear(self, frame):
        """Damage drawn into the frame itself: a scratch has lost its emulsion
        and passes more light, a hair in the gate blocks it."""
        rng = self.random
        if self._judder:
            self._judder -= 1
            frame.shift_rows(self._jump, 0)
        elif rng.random() < 0.022:
            self._jump = rng.choice((-2, -1, 1, 2))
            self._judder = rng.randint(1, 2)

        if self._scratch is None:
            if rng.random() < 0.06:
                self._scratch = [rng.randrange(MATRIX_WIDTH), rng.randint(1, 5)]
        if self._scratch is not None:
            x, life = self._scratch
            x = max(0, min(MATRIX_WIDTH - 1, x + rng.choice((-1, 0, 0, 1))))
            top = rng.randrange(0, 8)
            for y in range(top, MATRIX_HEIGHT - rng.randrange(0, 6)):
                frame.light(x, y, 214)
            life -= 1
            self._scratch = None if life <= 0 else [x, life]

        for _ in range(rng.randrange(0, 4)):
            frame.px(rng.randrange(MATRIX_WIDTH), rng.randrange(MATRIX_HEIGHT), 0)
        if rng.random() < 0.05:                          # a hair in the gate
            x = rng.randrange(MATRIX_WIDTH - 3)
            y = rng.randrange(MATRIX_HEIGHT - 2)
            frame.px(x, y, 0)
            frame.px(x + 1, y + 1, 0)
            frame.px(x + 2, y + 1, 0)

    # -- one frame ------------------------------------------------------------

    def next_image(self):
        shot = REEL[self.shot_index]
        position = self.position
        length = shot.frames

        shot.draw(self.frame, position, length)

        gain = 1.0
        if shot.fade_in and position < shot.fade_in:
            gain *= (position + 1) / float(shot.fade_in + 1)
        remaining = length - position - 1
        if shot.fade_out and remaining < shot.fade_out:
            gain *= (remaining + 1) / float(shot.fade_out + 1)

        if self.worn:
            # Lamp flicker as a random walk, pulled gently back to normal.
            self._gain += self.random.uniform(-0.05, 0.05)
            self._gain = max(0.84, min(1.10, self._gain * 0.82 + 0.18))
            gain *= self._gain
            self._wear(self.frame)
            # The cue dot, punched into the corner to warn of a reel change.
            if self.shot_index == len(REEL) - 1 and remaining < 4:
                self.frame.disc(58, 4, 2.2, 250)

        image = self._Image.frombytes('L', (MATRIX_WIDTH, MATRIX_HEIGHT),
                                      bytes(self.frame.buf))
        image = self._ImageChops.multiply(image, self._vignette)
        if self.worn:
            image = self._ImageChops.add(
                image, self._grain[self.frames_shown % GRAIN_FRAMES],
                1.0, -GRAIN_AMPLITUDE)

        radius = None
        if shot.iris_in and position < shot.iris_in:
            radius = _lerp(2, 46, (position + 1) / float(shot.iris_in))
        elif shot.iris_out and remaining < shot.iris_out:
            radius = _lerp(2, 46, (remaining + 1) / float(shot.iris_out))
        if radius is not None:
            image = self._ImageChops.multiply(
                image, self._iris(shot.iris_at, int(radius)))

        table = self._lut(gain)
        image = self._Image.merge('RGB', tuple(image.point(column) for column in table))

        self.position += 1
        self.frames_shown += 1
        if self.position >= length:
            self.position = 0
            self.shot_index = (self.shot_index + 1) % len(REEL)
        return image
