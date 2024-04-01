from samplebase import SampleBase

class Off(SampleBase):
    def __init__(self, *args, **kwargs):
        super(Off, self).__init__(*args, **kwargs)

    def run(self):
        offscreen_canvas = self.matrix.CreateFrameCanvas()
        offscreen_canvas = self.matrix.SwapOnVSync(offscreen_canvas)
        offscreen_canvas.Clear()


def run_off():
    off = Off()
    if (not off.process()):
        clock.print_help()

