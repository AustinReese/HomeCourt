"""Runs the silent film on the panel.

Everything interesting is in film_reel.py, which has no rgbmatrix import and
can be watched off the Pi. This file only owns the hardware: make a frame, put
it on the panel, wait out the rest of the frame.
"""

from time import sleep, time

from samplebase import SampleBase

import film_reel


class SilentFilm(SampleBase):
    def __init__(self, film_options, *args, **kwargs):
        super(SilentFilm, self).__init__(*args, **kwargs)
        self.film_options = film_options or {}

    def run(self):
        projector = film_reel.Projector(self.film_options)
        print("silent film: %s, %s tint, %s print, %d frames at %g fps (%.0fs)"
              % (self.film_options.get('film_speed', film_reel.DEFAULT_SPEED),
                 projector.tint,
                 'worn' if projector.worn else 'restored',
                 film_reel.REEL_FRAMES, projector.fps,
                 film_reel.REEL_FRAMES / projector.fps), flush=True)

        canvas = self.matrix.CreateFrameCanvas()
        # A projector runs at a fixed speed. Unlike an animation there is no
        # dt to chase: a frame is a frame, and the speed setting is the crank.
        budget = 1.0 / projector.fps
        while True:
            started = time()
            canvas.SetImage(projector.next_image())
            canvas = self.matrix.SwapOnVSync(canvas)
            spare = budget - (time() - started)
            if spare > 0:
                sleep(spare)


def run_film(film_options):
    print(film_options, flush=True)
    film = SilentFilm(film_options)
    if not film.process():
        film.parser.print_help()
