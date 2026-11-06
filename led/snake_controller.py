"""Snakes slithering across the 64x32 panel.

Each snake follows a sine track across the panel: the body samples the same
track the head is riding, so the segments trail the head instead of sliding
sideways as a block. Frames are composited in a numpy buffer and pushed with
one SetImage call, which is far cheaper than per-pixel SetPixel from Python.
"""

import math
import random
from time import sleep, time

import numpy as np
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

HEAD_RADIUS = 1.5
BODY_RADIUS = 1.15
TAIL_BRIGHTNESS = 0.18


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


def splat(buf, x, y, color, intensity, radius):
    """Add a soft round dot at a fractional position.

    Sub-pixel placement is what keeps the motion smooth; snapping segments to
    whole pixels makes them stutter badly at these sizes.
    """
    if intensity <= 0.0:
        return
    x_lo = max(0, int(math.floor(x - radius)))
    x_hi = min(MATRIX_WIDTH - 1, int(math.ceil(x + radius)))
    y_lo = max(0, int(math.floor(y - radius)))
    y_hi = min(MATRIX_HEIGHT - 1, int(math.ceil(y + radius)))
    for px in range(x_lo, x_hi + 1):
        dx = px - x
        for py in range(y_lo, y_hi + 1):
            dy = py - y
            distance = math.sqrt(dx * dx + dy * dy)
            if distance >= radius:
                continue
            weight = (1.0 - distance / radius) * intensity
            pixel = buf[py, px]
            pixel[0] += color[0] * weight
            pixel[1] += color[1] * weight
            pixel[2] += color[2] * weight


def draw_snake(buf, snake):
    red, green, blue = snake.color
    for x, y, taper in snake.segments():
        if x < -2 or x > MATRIX_WIDTH + 1:
            continue
        brightness = 1.0 - (1.0 - TAIL_BRIGHTNESS) * taper
        if taper == 0.0:
            # Wash the head toward white so it reads as a head, not just a
            # brighter body segment.
            color = (red + (255 - red) * 0.45,
                     green + (255 - green) * 0.45,
                     blue + (255 - blue) * 0.45)
            splat(buf, x, y, color, brightness, HEAD_RADIUS)
        else:
            splat(buf, x, y, (red, green, blue), brightness, BODY_RADIUS)


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
        trails = bool(options.get('snake_trails'))
        print(f"snakes: count={count} speed={speed_range} trails={trails}", flush=True)

        canvas = self.matrix.CreateFrameCanvas()
        buf = np.zeros((MATRIX_HEIGHT, MATRIX_WIDTH, 3), dtype=np.float32)
        frame = np.zeros((MATRIX_HEIGHT, MATRIX_WIDTH, 3), dtype=np.uint8)

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

            if trails:
                buf *= TRAIL_DECAY
            else:
                buf.fill(0.0)

            for i, snake in enumerate(snakes):
                snake.advance(dt)
                if snake.is_finished():
                    snake = Snake(speed_range, random.choice(PALETTE),
                                  random.uniform(0.3, 2.5))
                    snakes[i] = snake
                draw_snake(buf, snake)

            np.clip(buf, 0.0, 255.0, out=buf)
            np.copyto(frame, buf, casting='unsafe')
            canvas.SetImage(Image.fromarray(frame))
            canvas = self.matrix.SwapOnVSync(canvas)

            spare = frame_budget - (time() - now)
            if spare > 0:
                sleep(spare)


def run_snake(snake_options):
    print(snake_options, flush=True)
    snakes = Snakes(snake_options)
    if not snakes.process():
        snakes.print_help()
