"""Snakes slithering across the 64x32 panel.

A snake rides a path made of two parts: a slither (a sine or a triangle wave,
depending on the snake) and a wander, which is smooth random value noise
rather than another sine, so no two crossings trace the same shape. The body
samples that path behind the head, so segments trail rather than sliding as
a block.

Snakes never overlap. Each reserves the band of lanes it will sweep, and new
ones are packed flush against one end of a free gap.

Snakes cross either left-right or top-bottom, and the panel alternates
between the two in waves. The two cannot be mixed: a snake crossing the full
width sweeps every column and one crossing the full height sweeps every row,
so any horizontal/vertical pair on the panel at once is guaranteed to cross.
Alternating keeps the no-overlap guarantee exact rather than approximate.

Frames composite sparsely. The background is memcpy'd in whole and only the
pixels a snake covers are blended on top. A dense numpy buffer was the
obvious approach and measured ~5.5x slower on the Pi — numpy's per-call
overhead swamps the work at 64x32.
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
    'slow': (4.0, 11.0),
    'medium': (9.0, 21.0),
    'fast': (19.0, 40.0),
}
DEFAULT_SPEED = 'medium'

COUNTS = {'few': 2, 'some': 4, 'many': 6}
DEFAULT_COUNT = 'some'

DEFAULT_SCENE = 'neon'

# Body geometry. The body holds one thickness for most of its length and only
# the last stretch tapers — tapering the whole body reads as a tadpole, not a
# snake. The head is barely wider than the neck for the same reason.
HEAD_RADIUS = 1.6
BODY_RADIUS = 1.4
TAIL_RADIUS = 0.85
TAIL_FRACTION = 0.22      # share of the body that tapers
TAIL_FADE = 0.45          # how much the very tip dims
HEAD_LIGHTEN = 0.12

HORIZONTAL, VERTICAL = 'h', 'v'
# A vertical crossing is only 32px, so those snakes are shorter and their
# waves tighter, or they would never fit on the panel at once.
BODY_SEGMENTS = {HORIZONTAL: (18, 26), VERTICAL: (12, 18)}
SLITHER_LENGTH = {HORIZONTAL: (9.0, 22.0), VERTICAL: (7.0, 16.0)}
NOISE_STEP = {HORIZONTAL: (7.0, 16.0), VERTICAL: (5.0, 11.0)}

# The body is drawn from a trail of past head positions rather than from the
# path equation, so that when a snake steers the body follows it round
# instead of the whole shape sliding sideways. A point every TRAIL_STEP
# pixels is fine enough to interpolate between and keeps the trail short.
TRAIL_STEP = 0.6

# Dodging. Snakes steer away from each other rather than being confined to
# reserved lanes, which is what lets horizontal and vertical snakes share the
# panel and lets the paths stay wide.
AVOID_RADIUS = 8.5       # start giving way at this distance
AVOID_STRENGTH = 55.0    # lane px/s of push at point blank
MAX_STEER = 22.0         # cap on how fast a snake can slide aside
LOOK_AHEAD = 6.0         # probe this far up the track as well as at the head
HEAD_ON_NUDGE = 0.45     # break the tie when something is dead ahead
EDGE_MARGIN = 0.5        # keep the body this far inside the panel

# Steering sideways cannot clear a crossing snake: a snake running the full
# width is a wall across every column, so one crossing it has to dodge in
# time rather than in space. The snake with the lower right of way slows or
# stops until the other has gone by. Only one of any pair ever yields, so
# they cannot deadlock nose to nose.
BRAKE_AHEAD = 9.5        # start slowing when something is this far up track
BRAKE_STOP = 2.8         # fully stopped inside this
BRAKE_WIDTH = 3.4        # how far off the track still counts as in the way
BRAKE_EASE = 7.0         # how quickly braking eases in and out

# Arrivals. Snakes trickle in at irregular intervals rather than appearing as
# a batch; without this the whole panel fills and empties in lockstep.
SPAWN_GAP = (0.3, 2.0)        # quiet time between one arrival and the next
SPAWN_RETRY = (0.4, 1.2)      # when no room at the edge, look again after this
ENTRY_STAGGER = (0.0, 1.0)    # extra hold-off before a snake reaches the edge
ENTRY_CLEARANCE = 6.0         # keep this much room around a new snake's entry


# (body, band) pairs. Banding is what makes a 2px-wide line read as a snake
# rather than a worm.
NEON_SNAKES = [
    ((255, 25, 15),  (105, 5, 3)),      # red
    ((255, 205, 0),  (105, 80, 0)),     # amber
    ((10, 255, 60),  (0, 100, 22)),     # green
    ((20, 110, 255), (5, 40, 110)),     # blue
    ((0, 240, 255),  (0, 95, 105)),     # cyan
    ((255, 30, 225), (105, 8, 92)),     # magenta
    ((170, 50, 255), (68, 15, 105)),    # violet
]
DESERT_SNAKES = [
    ((205, 165, 100), (105, 68, 35)),   # diamondback
    ((228, 202, 152), (155, 125, 80)),  # sidewinder, pale
    ((168, 158, 78),  (85, 75, 35)),    # olive
    ((216, 112, 55),  (105, 52, 26)),   # red racer
]

SAND_BASE = (38, 26, 12)
SAND_RIPPLE = 0.16        # depth of the dune ripples
SAND_GRAIN = 0.07         # per-pixel noise

# Tracks pressed into the sand. Decayed on a tick rather than every frame:
# a slow fade looks identical at 10Hz and costs a tenth as much.
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
                # Normalise: overlapping segments push alpha past 1.
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


def _triangle(turns):
    """A -1..1 triangle wave. Sharper corners than a sine, so it zigzags."""
    phase = turns - math.floor(turns)
    return 4.0 * abs(phase - 0.5) - 1.0


class Snake():
    """One snake, wandering from one edge to the other and giving way to others."""

    def __init__(self, axis, speed_range, colors, start_delay, lane_center):
        self.axis = axis
        self.horizontal = axis == HORIZONTAL
        self.travel_span = MATRIX_WIDTH if self.horizontal else MATRIX_HEIGHT
        self.lane_span = MATRIX_HEIGHT if self.horizontal else MATRIX_WIDTH

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
        self.length = random.randint(*BODY_SEGMENTS[axis])
        self.spacing = random.uniform(1.4, 1.65)
        self.body_len = self.length * self.spacing
        self.taper_start = int(self.length * (1.0 - TAIL_FRACTION))

        # Slither: a sine for some snakes, a triangle for others.
        self.zigzag = random.random() < 0.45
        self.amplitude = random.uniform(1.6, 4.0)
        self.wavelength = random.uniform(*SLITHER_LENGTH[axis])
        self.phase = random.uniform(0.0, 1.0)
        self.phase_drift = random.uniform(-0.4, 0.4)

        # Wander: smooth random noise, not a second sine, so the route never
        # repeats and the snake really does rove around.
        self.wander = random.uniform(0.9, 2.6)
        self.noise_step = random.uniform(*NOISE_STEP[axis])
        self.noise_seed = random.randrange(1 << 30)

        # Snakes surge rather than holding one speed.
        self.surge_rate = random.uniform(0.25, 1.1)
        self.surge_phase = random.uniform(0.0, 2 * math.pi)
        self.surge_depth = random.uniform(0.10, 0.35)

        self.reach = self.amplitude + self.wander + BODY_RADIUS + EDGE_MARGIN
        self.lane_center = self._clamp_lane(lane_center)
        # Which way it prefers to swerve when something is dead ahead.
        self.dodge_bias = random.choice((-1.0, 1.0))
        # Right of way. The lower of any pair is the one that gives way, so a
        # conflict always has exactly one yielder.
        self.priority = random.random()
        self.brake = 1.0
        self.points = []

        offscreen = self.body_len + 2.0 + start_delay * self.speed
        self.travel = (-offscreen if self.direction > 0
                       else self.travel_span + offscreen)

        self.trail = []
        self.max_trail = int(self.body_len / TRAIL_STEP) + 4
        self._seed_trail()

    # ---- placement ----

    def _clamp_lane(self, lane):
        low = self.reach
        high = self.lane_span - 1.0 - self.reach
        if high < low:
            return (self.lane_span - 1.0) / 2.0
        return min(max(lane, low), high)

    def hold_off(self, seconds):
        """Park the snake this many seconds of travel short of the panel."""
        offscreen = self.body_len + 2.0 + max(0.0, seconds) * self.speed
        self.travel = (-offscreen if self.direction > 0
                       else self.travel_span + offscreen)
        self._seed_trail()

    def wait_at_edge(self, seconds):
        """Park the snake just off-panel, seconds of travel from showing."""
        gap = 2.0 + max(0.0, seconds) * self.speed
        self.travel = -gap if self.direction > 0 else self.travel_span + gap
        self._seed_trail()

    def has_entered(self):
        if self.direction > 0:
            return self.travel > -2.0
        return self.travel < self.travel_span + 2.0

    def is_finished(self):
        if self.direction > 0:
            return self.travel - self.body_len > self.travel_span + 1
        return self.travel + self.body_len < -1

    # ---- path ----

    def _control(self, cell):
        value = (cell * 374761393 + self.noise_seed) & 0xFFFFFFFF
        value = ((value ^ (value >> 13)) * 1274126177) & 0xFFFFFFFF
        return ((value ^ (value >> 16)) & 0xFFFF) / 32767.5 - 1.0

    def _noise(self, travel):
        """Smooth 1D value noise in -1..1, deterministic for this snake."""
        position = travel / self.noise_step
        cell = math.floor(position)
        blend = position - cell
        low = self._control(cell)
        high = self._control(cell + 1)
        blend = blend * blend * (3.0 - 2.0 * blend)
        return low + (high - low) * blend

    def _lane_at(self, travel):
        turns = travel / self.wavelength + self.phase
        slither = _triangle(turns) if self.zigzag else math.sin(2 * math.pi * turns)
        lane = (self.lane_center + self.amplitude * slither
                + self.wander * self._noise(travel))
        return min(max(lane, EDGE_MARGIN), self.lane_span - 1.0 - EDGE_MARGIN)

    def _point(self, travel):
        lane = self._lane_at(travel)
        return (travel, lane) if self.horizontal else (lane, travel)

    def head(self):
        return self._point(self.travel)

    def _seed_trail(self):
        """Lay down a body behind the head so a new snake is not a bare dot."""
        self.trail = []
        steps = int(self.body_len / TRAIL_STEP) + 2
        for i in range(steps, 0, -1):
            self.trail.append(self._point(self.travel - self.direction * i * TRAIL_STEP))

    # ---- motion ----

    def steer(self, others, dt):
        """Slide aside from, and give way to, nearby snakes."""
        head_x, head_y = self.head()
        horizontal = self.horizontal
        if horizontal:
            ahead_x, ahead_y = head_x + self.direction * LOOK_AHEAD, head_y
        else:
            ahead_x, ahead_y = head_x, head_y + self.direction * LOOK_AHEAD

        push = 0.0
        wanted_brake = 1.0
        for other in others:
            yields_to_other = self.priority < other.priority
            for hazard_x, hazard_y in other.points:
                # Signed offset across the track, and distance up the track.
                if horizontal:
                    across = head_y - hazard_y
                    along = (hazard_x - head_x) * self.direction
                else:
                    across = head_x - hazard_x
                    along = (hazard_y - head_y) * self.direction

                if yields_to_other and 0.0 < along < BRAKE_AHEAD \
                        and abs(across) < BRAKE_WIDTH:
                    room = ((along - BRAKE_STOP) / (BRAKE_AHEAD - BRAKE_STOP))
                    wanted_brake = min(wanted_brake, max(0.0, room))

                for probe_x, probe_y in ((head_x, head_y), (ahead_x, ahead_y)):
                    dx = probe_x - hazard_x
                    dy = probe_y - hazard_y
                    gap2 = dx * dx + dy * dy
                    if gap2 > AVOID_RADIUS * AVOID_RADIUS or gap2 < 1e-9:
                        continue
                    gap = sqrt(gap2)
                    sideways = dy if horizontal else dx
                    weight = (1.0 - gap / AVOID_RADIUS) ** 2
                    if abs(sideways) < HEAD_ON_NUDGE:
                        # Dead ahead, so there is no side to favour. Commit to
                        # this snake's preferred side rather than stalling.
                        push += self.dodge_bias * weight * AVOID_STRENGTH
                    else:
                        push += (sideways / gap) * weight * AVOID_STRENGTH

        if push > MAX_STEER:
            push = MAX_STEER
        elif push < -MAX_STEER:
            push = -MAX_STEER
        self.lane_center = self._clamp_lane(self.lane_center + push * dt)

        ease = min(1.0, dt * BRAKE_EASE)
        self.brake += (wanted_brake - self.brake) * ease

    def advance(self, dt):
        self.surge_phase += self.surge_rate * dt
        speed = (self.speed * self.brake
                 * (1.0 + self.surge_depth * math.sin(self.surge_phase)))
        self.travel += self.direction * speed * dt
        self.phase += self.phase_drift * dt

        head_x, head_y = self.head()
        if self.trail:
            last_x, last_y = self.trail[-1]
            if (head_x - last_x) ** 2 + (head_y - last_y) ** 2 < TRAIL_STEP * TRAIL_STEP:
                return
        self.trail.append((head_x, head_y))
        if len(self.trail) > self.max_trail:
            del self.trail[0:len(self.trail) - self.max_trail]

    # ---- drawing ----

    def _appearance(self, index):
        if index == 0:
            return self.head_color, HEAD_RADIUS, 1.0
        color = (self.band_color if (index // self.band_width) % 2
                 else self.body_color)
        if index < self.taper_start:
            return color, BODY_RADIUS, 1.0
        taper_span = max(1, self.length - self.taper_start)
        t = (index - self.taper_start + 1) / taper_span
        return (color,
                BODY_RADIUS - (BODY_RADIUS - TAIL_RADIUS) * t,
                1.0 - TAIL_FADE * t)

    def segments(self):
        """Head first: (x, y, color, radius, intensity).

        Walks back down the trail of past head positions, emitting a segment
        every `spacing` pixels of travelled distance. One pass over the trail
        covers the whole body.
        """
        head_x, head_y = self.head()
        on_panel = -2.0 <= (head_x if self.horizontal else head_y) <= self.travel_span + 2.0
        if on_panel:
            color, radius, intensity = self._appearance(0)
            yield head_x, head_y, color, radius, intensity

        trail = self.trail
        index = len(trail) - 1
        walked = 0.0
        next_segment = 1
        prev_x, prev_y = head_x, head_y
        spacing = self.spacing
        while next_segment < self.length and index >= 0:
            point_x, point_y = trail[index]
            step = sqrt((point_x - prev_x) ** 2 + (point_y - prev_y) ** 2)
            if step > 1e-9:
                while next_segment < self.length and walked + step >= next_segment * spacing:
                    along = (next_segment * spacing - walked) / step
                    seg_x = prev_x + (point_x - prev_x) * along
                    seg_y = prev_y + (point_y - prev_y) * along
                    travel_at = seg_x if self.horizontal else seg_y
                    if -2.0 <= travel_at <= self.travel_span + 2.0:
                        color, radius, intensity = self._appearance(next_segment)
                        yield seg_x, seg_y, color, radius, intensity
                    next_segment += 1
                walked += step
                prev_x, prev_y = point_x, point_y
            index -= 1

    def hazard_points(self, stride=3):
        """A thinned set of body points, for other snakes to steer around."""
        points = [self.head()]
        trail = self.trail
        for i in range(len(trail) - 1, -1, -stride):
            points.append(trail[i])
        return points


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
    for i, (x, y, color, radius, intensity) in enumerate(snake.segments()):
        splat(frame, x, y, color, intensity, radius)
        if leave_tracks and i:
            # One pressed pixel per segment is enough: the segments overlap,
            # so the groove comes out continuous and snake-width anyway.
            px = int(x + 0.5)
            py = int(y + 0.5)
            if 0 <= px < MATRIX_WIDTH and 0 <= py < MATRIX_HEIGHT:
                scene.press_track(py * MATRIX_WIDTH + px, intensity)


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
        self.next_spawn = 0.0

    def describe(self):
        return (f"snakes: scene={self.scene.name} count={self.count} "
                f"speed={self.speed_range} trails={self.trails}")

    def pick_colors(self):
        """Prefer a color no snake currently on the panel is wearing."""
        in_use = {snake.body_color for snake in self.snakes}
        free = [c for c in self.scene.palette if c[0] not in in_use]
        return random.choice(free or self.scene.palette)

    def add_snake(self, start_delay):
        """Bring a snake on, at whichever entry point is clearest right now.

        Snakes keep themselves apart by steering once they are moving; this
        only has to avoid dropping one straight on top of another.
        """
        colors = self.pick_colors()
        occupied = [point for snake in self.snakes for point in snake.hazard_points()]
        best = None
        best_clearance = -1.0
        for _ in range(12):
            axis = random.choice((HORIZONTAL, VERTICAL))
            lane_span = MATRIX_HEIGHT if axis == HORIZONTAL else MATRIX_WIDTH
            candidate = Snake(axis, self.speed_range, colors, start_delay,
                              random.uniform(0.0, lane_span - 1.0))
            entry_x, entry_y = candidate._point(
                0.0 if candidate.direction > 0 else candidate.travel_span - 1.0)
            clearance = min((sqrt((entry_x - ox) ** 2 + (entry_y - oy) ** 2)
                             for ox, oy in occupied), default=999.0)
            if clearance > best_clearance:
                best, best_clearance = candidate, clearance
            if clearance >= ENTRY_CLEARANCE:
                break
        if best is None or best_clearance < BODY_RADIUS * 2.0:
            return None
        self.snakes.append(best)
        return best

    def step(self, dt):
        self.frame.clear(self.glow_decay)
        self.snakes = [snake for snake in self.snakes if not snake.is_finished()]

        self.next_spawn -= dt
        # The quiet gaps are meant to vary the flow, not to empty the sign,
        # so a dark panel skips the wait entirely.
        dark = not any(snake.has_entered() for snake in self.snakes)
        if dark:
            self.next_spawn = 0.0
        if self.next_spawn <= 0.0 and len(self.snakes) < self.count:
            snake = self.add_snake(random.uniform(*ENTRY_STAGGER))
            if snake is not None:
                if dark:
                    # Start at the edge so it slides straight in rather than
                    # spending its body length off-panel.
                    snake.wait_at_edge(0.0)
                self.next_spawn = random.uniform(*SPAWN_GAP)
            else:
                self.next_spawn = random.uniform(*SPAWN_RETRY)

        # Steer against last frame's positions, so every snake reacts to the
        # same picture and no one gets to move out of the way first.
        for snake in self.snakes:
            snake.points = snake.hazard_points()
        for i, snake in enumerate(self.snakes):
            snake.steer(self.snakes[:i] + self.snakes[i + 1:], dt)

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
