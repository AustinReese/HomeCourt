"""Snakes slithering across the 64x32 panel.

Each snake follows a drifting sine track: the body samples the same track the
head is riding, so the segments trail the head instead of sliding sideways as
a block.

Frames are composited sparsely. Only the pixels a snake actually touches are
ever visited, and the finished frame goes out as one SetImage call. A dense
numpy buffer was the obvious approach and measured ~5.5x slower on the Pi —
numpy's per-call overhead swamps the work at 64x32.
"""

import math
import random
from math import sqrt
from time import sleep, time

from PIL import Image

from samplebase import SampleBase

MATRIX_WIDTH = 64
MATRIX_HEIGHT = 32

TARGET_FPS = 60.0

# Pixels per second, picked per snake so they don't travel in lockstep.
SPEEDS = {
    'slow': (5.0, 10.0),
    'medium': (11.0, 19.0),
    'fast': (22.0, 36.0),
}
DEFAULT_SPEED = 'medium'

COUNTS = {'few': 2, 'some': 4, 'many': 7}
DEFAULT_COUNT = 'some'

# Bold primaries: anything desaturated turns to mud on the panel.
PALETTE = [
    (255, 45, 30),    # red
    (255, 180, 0),    # yellow
    (35, 205, 75),    # green
    (45, 115, 255),   # blue
    (0, 205, 225),    # cyan
    (225, 65, 205),   # magenta
]

# How much of the previous frame survives when trails are on.
TRAIL_DECAY = 0.72
# Below this total brightness a trailing pixel is dropped instead of decaying
# forever in the accumulator.
TRAIL_CUTOFF = 3.0

HEAD_RADIUS = 1.5
BODY_RADIUS = 1.15
TAIL_BRIGHTNESS = 0.18
HEAD_WHITEN = 0.45


class SparseFrame():
    """An RGB frame that only tracks the pixels something has drawn into."""

    def __init__(self):
        self.pixels = bytearray(MATRIX_WIDTH * MATRIX_HEIGHT * 3)
        # flat pixel index -> [r, g, b] as floats, so overlapping snakes add.
        self.lit = {}

    def clear(self, decay=0.0):
        pixels = self.pixels
        if decay:
            faded = []
            for index, value in self.lit.items():
                red = value[0] * decay
                green = value[1] * decay
                blue = value[2] * decay
                if red + green + blue < TRAIL_CUTOFF:
                    faded.append(index)
                    offset = index * 3
                    pixels[offset] = 0
                    pixels[offset + 1] = 0
                    pixels[offset + 2] = 0
                else:
                    value[0] = red
                    value[1] = green
                    value[2] = blue
            for index in faded:
                del self.lit[index]
        else:
            for index in self.lit:
                offset = index * 3
                pixels[offset] = 0
                pixels[offset + 1] = 0
                pixels[offset + 2] = 0
            self.lit.clear()

    def to_image(self):
        pixels = self.pixels
        for index, value in self.lit.items():
            offset = index * 3
            red, green, blue = value
            pixels[offset] = 255 if red > 255.0 else int(red)
            pixels[offset + 1] = 255 if green > 255.0 else int(green)
            pixels[offset + 2] = 255 if blue > 255.0 else int(blue)
        return Image.frombytes('RGB', (MATRIX_WIDTH, MATRIX_HEIGHT), bytes(pixels))


class Snake():
    """One snake, riding a sine track from one edge to the other."""

    def __init__(self, speed_range, color, start_delay):
        self.direction = random.choice((-1, 1))
        self.speed = random.uniform(*speed_range)
        self.color = color
        self.length = random.randint(8, 15)
        self.spacing = random.uniform(1.0, 1.35)
        self.body_len = self.length * self.spacing

        self.wavelength = random.uniform(15.0, 28.0)
        self.amplitude = random.uniform(1.5, 4.0)
        self.phase = random.uniform(0.0, 2 * math.pi)
        # Drifting the phase keeps the track itself moving, so the body
        # undulates instead of tracing one frozen curve.
        self.phase_drift = random.uniform(-2.2, 2.2)

        margin = self.amplitude + 1.0
        self.y_base = random.uniform(margin, MATRIX_HEIGHT - 1 - margin)

        # Hold the snake off-screen for start_delay seconds so entries are
        # staggered by time, not by a fixed distance that a slow snake would
        # take forever to cover.
        offscreen = self.body_len + 2.0 + start_delay * self.speed
        self.x = -offscreen if self.direction > 0 else MATRIX_WIDTH + offscreen

    def advance(self, dt):
        self.x += self.direction * self.speed * dt
        self.phase += self.phase_drift * dt

    def is_finished(self):
        if self.direction > 0:
            return self.x - self.body_len > MATRIX_WIDTH + 1
        return self.x + self.body_len < -1

    def y_at(self, x):
        return self.y_base + self.amplitude * math.sin(
            2 * math.pi * x / self.wavelength + self.phase)

    def segments(self):
        """Head first: (x, y, taper) with taper 0.0 at the head, 1.0 at the tail."""
        last = max(self.length - 1, 1)
        for i in range(self.length):
            x = self.x - self.direction * i * self.spacing
            yield x, self.y_at(x), i / last


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
            weight = (1.0 - distance * inv_radius) * intensity
            index = row + px
            value = lit.get(index)
            if value is None:
                lit[index] = [red * weight, green * weight, blue * weight]
            else:
                value[0] += red * weight
                value[1] += green * weight
                value[2] += blue * weight


def draw_snake(frame, snake):
    red, green, blue = snake.color
    # Wash the head toward white so it reads as a head, not just a brighter
    # body segment.
    head_color = (red + (255 - red) * HEAD_WHITEN,
                  green + (255 - green) * HEAD_WHITEN,
                  blue + (255 - blue) * HEAD_WHITEN)
    for x, y, taper in snake.segments():
        if x < -2 or x > MATRIX_WIDTH + 1:
            continue
        brightness = 1.0 - (1.0 - TAIL_BRIGHTNESS) * taper
        if taper == 0.0:
            splat(frame, x, y, head_color, brightness, HEAD_RADIUS)
        else:
            splat(frame, x, y, (red, green, blue), brightness, BODY_RADIUS)


def _option(options, key, table, default):
    value = options.get(key)
    return table[value] if value in table else table[default]


class Snakes(SampleBase):
    def __init__(self, snake_options, *args, **kwargs):
        super(Snakes, self).__init__(*args, **kwargs)
        self.snake_options = snake_options or {}

    def run(self):
        options = self.snake_options
        speed_range = _option(options, 'snake_speed', SPEEDS, DEFAULT_SPEED)
        count = _option(options, 'snake_count', COUNTS, DEFAULT_COUNT)
        decay = TRAIL_DECAY if options.get('snake_trails') else 0.0
        print(f"snakes: count={count} speed={speed_range} trails={bool(decay)}",
              flush=True)

        canvas = self.matrix.CreateFrameCanvas()
        frame = SparseFrame()

        colors = random.sample(PALETTE, min(count, len(PALETTE)))
        while len(colors) < count:
            colors.append(random.choice(PALETTE))
        # Spread the first entries out so they don't all arrive together.
        snakes = [Snake(speed_range, colors[i], random.uniform(0.0, 3.0))
                  for i in range(count)]

        frame_budget = 1.0 / TARGET_FPS
        last = time()
        while True:
            now = time()
            # Cap dt so a scheduling hiccup teleports nothing across the panel.
            dt = min(now - last, 0.1)
            last = now

            frame.clear(decay)
            for i, snake in enumerate(snakes):
                snake.advance(dt)
                if snake.is_finished():
                    snake = Snake(speed_range, random.choice(PALETTE),
                                  random.uniform(0.3, 2.5))
                    snakes[i] = snake
                draw_snake(frame, snake)

            canvas.SetImage(frame.to_image())
            canvas = self.matrix.SwapOnVSync(canvas)

            spare = frame_budget - (time() - now)
            if spare > 0:
                sleep(spare)


def run_snake(snake_options):
    print(snake_options, flush=True)
    snakes = Snakes(snake_options)
    if not snakes.process():
        snakes.print_help()
