## HomeCourt

This project powers my home IOT setup. It integrates with homemade temperature sensors, Wiz smart bulbs, and an Adafruit LED sign.

The project is dependant on my local infastructure and won't function properly without it. The LED relies on an install script and python module for Raspberry Pi, the software cannot be installed in a container and no suitable mock modules exist.

You may run the frontend, api, & database using `docker-compose build && docker-compose up` to test certain functionality.

### NFL scoreboard

Polls ESPN's scoreboard every 5 seconds while games are on (once a minute otherwise) and cycles through the week's games. With "Enable Live Updates" on, alerts interrupt the rotation as soon as they're known:

- **Scores**: flashes the score type and team, then shows that game's score. Touchdowns follow with the in-game stats of the scorer, plus the passer on a passing touchdown. Other scores show the play.
- **Close games**: when the team with the ball is tied or trailing by 7 or fewer with under 3:00 left in the 4th (or in overtime). Shows the score, then the down, distance, field position, clock, and timeouts. Once per drive; a leading team running out the clock never triggers it.
- **Finals**: when a game ends, the result and final score.

Alert text is white for readability, except that stat lines get light tints so they're easy to tell apart. Team colors stay on the scores. Text layout for the 64x32 panel is in `led/led_text.py`; ESPN parsing and alert rules are in `led/nfl_data.py`, which can be run without LED hardware.

### Snakes

Snakes cross the panel from both sides, each riding two sine waves — a short one for
the slither and a long shallow one that makes the whole path wander, because a single
sine looks machined. The body samples the same track behind the head, so segments
trail rather than sliding as a block. Thickness stays constant until the last fifth
tapers; tapering the whole body reads as a tadpole. Bodies are banded, which is what
makes a 2px line read as a snake.

Each snake reserves the band of rows it will sweep, so no two ever cross or share a
track. New snakes are packed flush against one end of a free gap — centring them
splits the gap into two halves too small to reuse. The lane budget scales with the
requested count, so few snakes slither wide and many run tighter.

Two scenes. **Desert** is dim rippled sand with desert-snake colors, and trails are
grooves pressed into the sand that fade over a few seconds. **Neon** is bold primaries
on black, where trails are the glow of the frames just gone. The sand is deliberately
dark: a bright background washes the snakes out on a panel this size.

Frames composite sparsely — the background is memcpy'd in whole and only the pixels a
snake covers are alpha-blended on top. A dense numpy buffer was the obvious approach
and measured ~5.5x slower on the Pi, because at 64x32 numpy's per-call overhead costs
more than the whole pure-Python inner loop.

### LED control UI

The Lights-style card UI at `pi-ui/src/app/display-selector`. A power switch replaces the old
"Off" entry in the dropdown, displays are tiles rather than a `mat-select`, dropdown options
render as segmented pills and checkboxes as toggles. Changes apply on tap (debounced), so
there's no Apply button. On load the UI asks `/getCurrentDisplay` what the sign is actually
showing instead of guessing.

Displays and their options come from the database, so adding one means a row in `display`,
rows in `display_option`, and — for dropdowns — a `<displayKey>_selection` table. `init.sql`
only runs for a database created from scratch; `db/migrations/` carries the same change for
the Pi's long-lived postgres.

### Pi setup

OS-level config (watchdog, Wi-Fi fixes, health check) lives in `ops/`. See `ops/README.md`.
