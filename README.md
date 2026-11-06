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

### Pi setup

OS-level config (watchdog, Wi-Fi fixes, health check) lives in `ops/`. See `ops/README.md`.
