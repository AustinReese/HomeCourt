"""Snakes slithering across the 64x32 panel.

Each snake follows a drifting sine track: the body samples the same track the
head is riding, so the segments trail the head instead of sliding sideways as
a block.

Frames are composited sparsely. The background is memcpy'd in whole and only
the pixels a snake actually covers are blended on top. A dense numpy buffer
was the obvious approach and measured ~5.5x slower on the Pi — numpy's
per-call overhead swamps the work at 64x32.
"""

import math
import random
from math import sqrt
from time import sleep, time

from PIL import Image

from samplebase import SampleBase

MATRIX_WIDTH = 64
MATRIX_HEIGHT = 32
BUFFER_SIZE = MATRIX_WIDTH * MATRIX_HEIGHT * 3

TARGET_FPS = 40.0

# Pixels per second, picked per snake so they don't travel in lockstep.
SPEEDS = {
    'slow': (5.0, 10.0),
    'medium': (11.0, 19.0),
    'fast': (22.0, 36.0),
}
DEFAULT_SPEED = 'medium'

COUNTS = {'few': 2, 'some': 4, 'many': 6}
DEFAULT_COUNT = 'some'

# Snakes reserve the band of rows they will sweep, so none of them cross or
# share a track. When the panel fills up a new snake retries with a flatter
# wave before giving up and waiting for a gap.
SPAWN_RETRY_SECONDS = 0.4
LANE_GAP = 0.4
# A snake narrower than this has no room left to slither, so the gap is
# treated as full rather than squeezing a straight line into it.
MIN_REACH = 2.5

DEFAULT_SCENE = 'desert'

# Body geometry. The body holds one thickness for most of its length and only
# the last stretch tapers — tapering the whole body reads as a tadpole, not a
# snake. The head is barely wider than the neck for the same reason.
HEAD_RADIUS = 1.6
BODY_RADIUS = 1.4
TAIL_RADIUS = 0.85
TAIL_FRACTION = 0.22      # share of the body that tapers
TAIL_FADE = 0.45          # how much the very tip dims
HEAD_LIGHTEN = 0.12

# (body, band) pairs. Banding is what makes a 2px-wide line read as a snake
# rather than a worm.
DESERT_SNAKES = [
    ((205, 165, 100), (105, 68, 35)),   # diamondback
    ((228, 202, 152), (155, 125, 80)),  # sidewinder, pale
    ((168, 158, 78),  (85, 75, 35)),    # olive
    ((216, 112, 55),  (105, 52, 26)),   # red racer
]
NEON_SNAKES = [
    ((255, 45, 30),  (110, 18, 12)),
    ((255, 180, 0),  (110, 76, 0)),
    ((35, 205, 75),  (14, 85, 30)),
    ((45, 115, 255), (18, 48, 110)),
    ((0, 205, 225),  (0, 85, 95)),
    ((225, 65, 205), (95, 26, 85)),
]

SAND_BASE = (38, 26, 12)
SAND_RIPPLE = 0.16        # depth of the dune ripples
SAND_GRAIN = 0.07         # per-pixel noise

# Tracks pressed into the sand. Decayed on a tick rather than every frame:
# a slow fade looks identical at 10Hz and costs a sixth as much.
TRACK_DARKEN = 0.45
TRACK_DECAY = 0.955
TRACK_TICK_SECONDS = 0.1
TRACK_CUTOFF = 0.02

# Glow left behind in the neon scene.
GLOW_DECAY = 0.72
GLOW_CUTOFF = 0.012


def build_sand(seed=None):
    """A dim warm ground with dune ripples and grain, as a ready-to-blit buffer."""
    rng = random.Random(seed)
    buf = bytearray(BUFFER_SIZE)
    red, green, blue = SAND_BASE
    for y in range(MATRIX_HEIGHT):
        # Very slight vertical gradient so the panel has some depth.
        depth = 1.0 + 0.10 * (0.5 - y / (MATRIX_HEIGHT - 1.0))
        for x in range(MATRIX_WIDTH):
            ripple = (math.sin(x * 0.17 + y * 0.34) * 0.6
                      + math.sin(x * 0.07 - y * 0.19) * 0.4)
            shade = depth * (1.0 + SAND_RIPPLE * ripple
                             + rng.uniform(-SAND_GRAIN, SAND_GRAIN))
            offset = (y * MATRIX_WIDTH + x) * 3
            value = red * shade
            buf[offset] = 255 if value > 255.0 else int(value)
            value = green * shade
            buf[offset + 1] = 255 if value > 255.0 else int(value)
            value = blue * shade
            buf[offset + 2] = 255 if value > 255.0 else int(value)
    return buf


class Scene():
    """Background, palette, and what a snake leaves behind it."""

    def __init__(self, name):
        self.name = name
        self.desert = name == 'desert'
        self.palette = DESERT_SNAKES if self.desert else NEON_SNAKES
        self.ground = build_sand() if self.desert else bytearray(BUFFER_SIZE)
        # What actually gets blitted each frame: the ground plus any tracks.
        self.background = bytearray(self.ground)
        self.tracks = {}
        self._since_tick = 0.0

    def press_track(self, index, strength):
        current = self.tracks.get(index)
        if current is None or strength > current:
            self.tracks[index] = strength

    def age_tracks(self, dt):
        """Fade the tracks and rebuild the background they darken."""
        if not self.desert:
            return
        self._since_tick += dt
        if self._since_tick < TRACK_TICK_SECONDS:
            return
        self._since_tick = 0.0

        self.background[:] = self.ground
        ground = self.ground
        background = self.background
        faded = []
        for index, strength in self.tracks.items():
            strength *= TRACK_DECAY
            if strength < TRACK_CUTOFF:
                faded.append(index)
                continue
            self.tracks[index] = strength
            offset = index * 3
            keep = 1.0 - TRACK_DARKEN * strength
            background[offset] = int(ground[offset] * keep)
            background[offset + 1] = int(ground[offset + 1] * keep)
            background[offset + 2] = int(ground[offset + 2] * keep)
        for index in faded:
            del self.tracks[index]


class Frame():
    """Sparse RGB frame: blit the background, blend only what a snake covers."""

    def __init__(self):
        self.pixels = bytearray(BUFFER_SIZE)
        # flat pixel index -> [r, g, b, alpha], premultiplied.
        self.lit = {}

    def clear(self, decay=0.0):
        if not decay:
            self.lit.clear()
            return
        faded = []
        for index, value in self.lit.items():
            alpha = value[3] * decay
            if alpha < GLOW_CUTOFF:
                faded.append(index)
            else:
                value[0] *= decay
                value[1] *= decay
                value[2] *= decay
                value[3] = alpha
        for index in faded:
            del self.lit[index]

    def to_image(self, background):
        # One memcpy restores the whole panel, so there is no dirty-pixel
        # bookkeeping to get wrong.
        pixels = self.pixels
        pixels[:] = background
        for index, value in self.lit.items():
            offset = index * 3
            alpha = value[3]
            if alpha >= 1.0:
                # Normalise: overlapping segments can push alpha past 1.
                scale = 1.0 / alpha
                red = value[0] * scale
                green = value[1] * scale
                blue = value[2] * scale
            else:
                keep = 1.0 - alpha
                red = value[0] + pixels[offset] * keep
                green = value[1] + pixels[offset + 1] * keep
                blue = value[2] + pixels[offset + 2] * keep
            pixels[offset] = 255 if red > 255.0 else int(red)
            pixels[offset + 1] = 255 if green > 255.0 else int(green)
            pixels[offset + 2] = 255 if blue > 255.0 else int(blue)
        return Image.frombytes('RGB', (MATRIX_WIDTH, MATRIX_HEIGHT), bytes(pixels))


class Snake():
    """One snake, riding a wandering sine track from one edge to the other."""

    def __init__(self, speed_range, colors, start_delay, max_reach):
        self.direction = random.choice((-1, 1))
        self.speed = random.uniform(*speed_range)
        self.body_color, self.band_color = colors
        # A few snakes are plain rather than banded, for variety.
        if random.random() < 0.2:
            self.band_color = self.body_color
        self.head_color = tuple(c + (255 - c) * HEAD_LIGHTEN for c in self.body_color)
        self.band_width = random.choice((2, 3))

        # Long and loosely spaced: segments still overlap at BODY_RADIUS, so
        # the body stays solid while costing far fewer splats than packing
        # them one pixel apart.
        self.length = random.randint(18, 26)
        self.spacing = random.uniform(1.4, 1.65)
        self.body_len = self.length * self.spacing
        self.taper_start = int(self.length * (1.0 - TAIL_FRACTION))

        # Two waves: a short one for the slither, and a long shallow one that
        # makes the whole path wander. One sine alone looks machined.
        self.amplitude = random.uniform(1.4, 3.2)
        self.wavelength = random.uniform(16.0, 30.0)
        self.phase = random.uniform(0.0, 2 * math.pi)
        self.wander = random.uniform(0.7, 2.0)
        self.wander_length = random.uniform(55.0, 120.0)
        self.wander_phase = random.uniform(0.0, 2 * math.pi)
        # Shrink both waves to whatever vertical room the lane actually has.
        room = max_reach - BODY_RADIUS - 0.5
        wave = self.amplitude + self.wander
        if wave > room:
            scale = max(room, 0.0) / wave
            self.amplitude *= scale
            self.wander *= scale
        # Drifting the phase keeps the track itself moving, so the body
        # undulates instead of tracing one frozen curve.
        self.phase_drift = random.uniform(-2.2, 2.2)

        # Snakes surge rather than holding one speed.
        self.surge_rate = random.uniform(0.35, 0.9)
        self.surge_phase = random.uniform(0.0, 2 * math.pi)
        self.surge_depth = random.uniform(0.08, 0.22)

        self.reach = self.amplitude + self.wander + BODY_RADIUS + 0.5
        self.y_base = MATRIX_HEIGHT / 2.0

        # Hold the snake off-screen for start_delay seconds so entries are
        # staggered by time, not by a fixed distance that a slow snake would
        # take forever to cover.
        offscreen = self.body_len + 2.0 + start_delay * self.speed
        self.x = -offscreen if self.direction > 0 else MATRIX_WIDTH + offscreen

    def place(self, y_base):
        self.y_base = y_base

    def span(self):
        """The rows this snake will sweep, used to keep snakes off each other."""
        return (self.y_base - self.reach - LANE_GAP,
                self.y_base + self.reach + LANE_GAP)

    def advance(self, dt):
        self.surge_phase += self.surge_rate * dt
        speed = self.speed * (1.0 + self.surge_depth * math.sin(self.surge_phase))
        self.x += self.direction * speed * dt
        self.phase += self.phase_drift * dt

    def is_finished(self):
        if self.direction > 0:
            return self.x - self.body_len > MATRIX_WIDTH + 1
        return self.x + self.body_len < -1

    def y_at(self, x):
        return (self.y_base
                + self.amplitude * math.sin(2 * math.pi * x / self.wavelength
                                            + self.phase)
                + self.wander * math.sin(2 * math.pi * x / self.wander_length
                                         + self.wander_phase))

    def segments(self):
        """Head first: (x, y, color, radius, intensity)."""
        taper_start = self.taper_start
        taper_span = max(1, self.length - taper_start)
        for i in range(self.length):
            x = self.x - self.direction * i * self.spacing
            y = self.y_at(x)
            if i == 0:
                yield x, y, self.head_color, HEAD_RADIUS, 1.0
            elif i < taper_start:
                color = (self.band_color if (i // self.band_width) % 2
                         else self.body_color)
                yield x, y, color, BODY_RADIUS, 1.0
            else:
                t = (i - taper_start + 1) / taper_span
                color = (self.band_color if (i // self.band_width) % 2
                         else self.body_color)
                yield (x, y, color,
                       BODY_RADIUS - (BODY_RADIUS - TAIL_RADIUS) * t,
                       1.0 - TAIL_FADE * t)


def splat(frame, x, y, color, intensity, radius):
    """Add a soft round dot at a fractional position.

    Sub-pixel placement is what keeps the motion smooth; snapping segments to
    whole pixels makes them stutter badly at this size.
    """
    if intensity <= 0.0:
        return
    x_lo = max(0, int(math.floor(x - radius)))
    x_hi = min(MATRIX_WIDTH - 1, int(math.ceil(x + radius)))
    y_lo = max(0, int(math.floor(y - radius)))
    y_hi = min(MATRIX_HEIGHT - 1, int(math.ceil(y + radius)))
    if x_hi < x_lo or y_hi < y_lo:
        return

    red, green, blue = color
    inv_radius = 1.0 / radius
    lit = frame.lit
    for py in range(y_lo, y_hi + 1):
        dy = py - y
        dy2 = dy * dy
        row = py * MATRIX_WIDTH
        for px in range(x_lo, x_hi + 1):
            dx = px - x
            distance = sqrt(dx * dx + dy2)
            if distance >= radius:
                continue
            alpha = (1.0 - distance * inv_radius) * intensity
            index = row + px
            value = lit.get(index)
            if value is None:
                lit[index] = [red * alpha, green * alpha, blue * alpha, alpha]
            else:
                value[0] += red * alpha
                value[1] += green * alpha
                value[2] += blue * alpha
                value[3] += alpha


def draw_snake(frame, scene, snake, leave_tracks):
    width = MATRIX_WIDTH
    for i, (x, y, color, radius, intensity) in enumerate(snake.segments()):
        if x < -2 or x > width + 1:
            continue
        splat(frame, x, y, color, intensity, radius)
        if leave_tracks and i:
            # One pressed pixel per segment is enough: the segments overlap,
            # so the groove comes out continuous and snake-width anyway.
            px = int(x + 0.5)
            py = int(y + 0.5)
            if 0 <= px < width and 0 <= py < MATRIX_HEIGHT:
                scene.press_track(py * width + px, intensity)


def _option(options, key, table, default):
    value = options.get(key)
    return table[value] if value in table else table[default]


class SnakeWorld():
    """Everything but the panel, so it can be previewed off the Pi."""

    def __init__(self, options):
        options = options or {}
        scene_name = options.get('snake_scene')
        if scene_name not in ('desert', 'neon'):
            scene_name = DEFAULT_SCENE
        self.scene = Scene(scene_name)
        self.speed_range = _option(options, 'snake_speed', SPEEDS, DEFAULT_SPEED)
        self.count = _option(options, 'snake_count', COUNTS, DEFAULT_COUNT)
        self.trails = bool(options.get('snake_trails'))
        # In the desert a trail is a groove pressed into the sand; in neon it
        # is the glow of the frames just gone.
        self.leave_tracks = self.trails and self.scene.desert
        self.glow_decay = GLOW_DECAY if (self.trails and not self.scene.desert) else 0.0

        self.frame = Frame()
        self.snakes = []
        self.retry_in = 0.0
        # Share the panel out by the requested count, otherwise the first
        # snake takes a huge lane and nothing else fits. Fewer snakes
        # therefore slither wider, more snakes run tighter.
        # free_gaps works over rows 0..MATRIX_HEIGHT-1, so budget against that
        # span, less a hair so rounding can't lose the last lane.
        lane = (MATRIX_HEIGHT - 1.0) / self.count
        self.lane_reach = max(MIN_REACH, lane / 2.0 - LANE_GAP - 0.05)
        # Stagger the opening entries; after that each gap is refilled as it
        # appears.
        for _ in range(self.count):
            self.add_snake(random.uniform(0.0, 2.0))

    def describe(self):
        return (f"snakes: scene={self.scene.name} count={self.count} "
                f"speed={self.speed_range} trails={self.trails}")

    def pick_colors(self):
        """Prefer a color no snake currently on the panel is wearing."""
        in_use = {snake.body_color for snake in self.snakes}
        free = [c for c in self.scene.palette if c[0] not in in_use]
        return random.choice(free or self.scene.palette)

    def free_gaps(self):
        """Bands of rows no active snake has reserved."""
        gaps = []
        cursor = 0.0
        for low, high in sorted(snake.span() for snake in self.snakes):
            if low > cursor:
                gaps.append((cursor, low))
            cursor = max(cursor, high)
        bottom = MATRIX_HEIGHT - 1.0
        if cursor < bottom:
            gaps.append((cursor, bottom))
        return gaps

    def add_snake(self, start_delay):
        """Drop a snake into the roomiest free band, or report none is free."""
        gaps = sorted(self.free_gaps(), key=lambda g: g[1] - g[0], reverse=True)
        for low, high in gaps:
            max_reach = (high - low) / 2.0 - LANE_GAP
            if max_reach < MIN_REACH:
                # Gaps are sorted widest first, so nothing after this fits.
                break
            snake = Snake(self.speed_range, self.pick_colors(), start_delay,
                          min(max_reach, self.lane_reach))
            # Pack flush against one end of the gap. Centring the snake would
            # split the gap into two halves too small to reuse, which is why
            # the panel used to stop at three snakes however many were asked
            # for. The snake's own reach can come out under the cap, so place
            # it from that rather than from the cap.
            if random.random() < 0.5:
                snake.place(low + snake.reach + LANE_GAP)
            else:
                snake.place(high - snake.reach - LANE_GAP)
            self.snakes.append(snake)
            return True
        return False

    def step(self, dt):
        self.frame.clear(self.glow_decay)

        self.snakes = [snake for snake in self.snakes if not snake.is_finished()]
        self.retry_in -= dt
        if len(self.snakes) < self.count and self.retry_in <= 0.0:
            if not self.add_snake(random.uniform(0.1, 1.4)):
                # No clear band right now; look again shortly.
                self.retry_in = SPAWN_RETRY_SECONDS

        for snake in self.snakes:
            snake.advance(dt)
            draw_snake(self.frame, self.scene, snake, self.leave_tracks)

        self.scene.age_tracks(dt)
        return self.frame.to_image(self.scene.background)


class Snakes(SampleBase):
    def __init__(self, snake_options, *args, **kwargs):
        super(Snakes, self).__init__(*args, **kwargs)
        self.snake_options = snake_options

    def run(self):
        world = SnakeWorld(self.snake_options)
        print(world.describe(), flush=True)

        canvas = self.matrix.CreateFrameCanvas()
        frame_budget = 1.0 / TARGET_FPS
        last = time()
        while True:
            now = time()
            # Cap dt so a scheduling hiccup teleports nothing across the panel.
            dt = min(now - last, 0.1)
            last = now

            canvas.SetImage(world.step(dt))
            canvas = self.matrix.SwapOnVSync(canvas)

            spare = frame_budget - (time() - now)
            if spare > 0:
                sleep(spare)


def run_snake(snake_options):
    print(snake_options, flush=True)
    snakes = Snakes(snake_options)
    if not snakes.process():
        snakes.print_help()
