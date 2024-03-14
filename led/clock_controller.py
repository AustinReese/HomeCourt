from PIL import ImageColor
from time import sleep
from datetime import datetime, timezone
from samplebase import SampleBase
from rgbmatrix import graphics


class Clock(SampleBase):
    def __init__(self, clock_options, *args, **kwargs):
        super(Clock, self).__init__(*args, **kwargs)
        self.clock_options = clock_options

    def run(self):
        offscreen_canvas = self.matrix.CreateFrameCanvas()

        font = graphics.Font()
        font.LoadFont("/opt/rpi-rgb-led-matrix/fonts/9x18.bdf")

        white = graphics.Color(255, 255, 255)

        if self.clock_options['clock_hour_format'] == '24hr':
            while True:
                time = datetime.now().strftime('%H:%M')
                graphics.DrawText(offscreen_canvas, font, 9, 20, white, time)
                offscreen_canvas = self.matrix.SwapOnVSync(offscreen_canvas)
                offscreen_canvas.Clear()
        elif self.clock_options['clock_hour_format'] == '12hr':
            while True:
                time = datetime.now().strftime("%I:%M%p")
                graphics.DrawText(offscreen_canvas, font, 0, 20, white, time)
                offscreen_canvas = self.matrix.SwapOnVSync(offscreen_canvas)
                offscreen_canvas.Clear()
        else:
            while True:
                graphics.DrawText(offscreen_canvas, font, 0, 10, white, 'error')
                offscreen_canvas = self.matrix.SwapOnVSync(offscreen_canvas)
                offscreen_canvas.Clear()



def run_clock(clock_options):
    print(clock_options)
    clock = Clock(clock_options)
    if (not clock.process()):
        clock.print_help()



            # graphics.DrawText(offscreen_canvas, font, 15, 14, white, time) for month date
            # graphics.DrawText(offscreen_canvas, font, 15, 29, white, time)