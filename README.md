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

### Silent Film

About a minute of film, on a loop. What's in it is best found out on the panel.

The look comes from treating the panel as a screen being projected onto rather than a
lamp being switched on: a scene is a lit frame with dark figures on it, and a title card
is a black card with the lettering cut out of it, which is what an intertitle really is.
Damage follows the same physics — a scratch has lost its emulsion and passes more light,
a hair in the gate blocks it. The picture is drawn in a single-channel luminance buffer
and only tinted on the way out, which is how tinted prints were made: develop in silver,
then dye the finished stock.

Options are projector speed (silent stock ran at about 16 frames a second, so "Modern" is
the setting that looks wrong), tint, and **Restored Print**, which turns off the grain,
flicker, scratches and gate weave. It's off by default, because the wear is half the point.

Drawing is sparse pure Python; every pass that touches all 2048 pixels — vignette, grain,
fade, iris, tint — is one whole-image PIL call. That's the opposite of the lesson in
`snake_controller.py`, for the opposite reason: numpy lost there because a frame was dozens
of tiny array calls each paying its own overhead, while here each pass is a single C loop
over the full frame. A frame costs well under a millisecond of Python.

The reel and everything in it is `led/film_reel.py`, which has no `rgbmatrix` import, so
the film can be rendered and watched off the Pi; `led/film_controller.py` only owns the
panel.

### Weather

The forecast for 55419, from the National Weather Service. No API key, because
NWS does not use them -- it wants a `User-Agent` that names the client instead.

Three endpoints on three clocks, because they change at very different speeds
and one of them is large: the KMSP observation every 5 minutes, the period
forecast every 15, and the raw gridpoint every 30. That last one is 200KB and is
fetched only because it is the one place NWS publishes snowfall and
precipitation *amounts* rather than chances. It also rescues today's high after
the afternoon is over, when the period forecast has dropped it but a person
looking at the panel still expects to see it.

The panel splits left and right rather than top and bottom. A forecast is a list
of days and a list reads down a column; the first attempt laid the days out
sideways and gave each one 15px, which is not enough to hold two temperatures
when both are below zero -- an ordinary Minneapolis January, not a corner case.
As rows they get the full 32px, and the figures are placed before the day name,
which gives up its third letter when they need the room: `MO -18 -12` says more
than `MON` and a clipped number. The minus sign is 2px wide for the same reason.

Under each row is a one-pixel line: as long as the chance of precipitation,
coloured by what kind, and drawn only when there is a chance to report. There is
no track behind it, because five permanent grey lines buy a scale nobody needs
when the bars already start at the same x. Today's *amount* -- `3.4"` of snow,
`.42"` of rain -- sits beside the sky icon, where the left panel has pixels the
icon does not use.

The current temperature is coloured by what it is, interpolated along a ramp
from icy blue through white to red, so a January panel and a July panel do not
look the same.

The 16x16 sky icon is the only thing that moves. Clouds are built upward from a
flat base line rather than outward from a centre -- round off the underside and
the shape stops reading as a cloud and starts reading as a blob -- and
everything falling or drifting is splatted at fractional coordinates so it
drifts instead of stepping. Text never is: every glyph here is a hand-set
bitmap, since a blurred 3px digit is an unreadable one. The static two thirds of
the panel are drawn once into a base buffer that each frame copies, and the
icon cell is clipped while it repaints, so a snowflake cannot smear across a
forecast that is never redrawn.

`led/weather_data.py` (the feeds) and `led/weather_art.py` (the layout and the
icon) have no `rgbmatrix` import, so both can be rendered and checked off the
Pi; `led/weather_controller.py` only owns the panel.

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
