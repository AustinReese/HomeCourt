"""Fits text onto the 64x32 matrix. No rgbmatrix import, so layouts can be checked off the Pi."""

MATRIX_WIDTH = 64
MATRIX_HEIGHT = 32
FONT_DIR = "/opt/rpi-rgb-led-matrix/fonts"


class FontSpec():
    def __init__(self, name, width, ascent, descent):
        self.name = name
        self.width = width
        self.ascent = ascent
        self.height = ascent + descent

    def chars_per_line(self):
        return MATRIX_WIDTH // self.width


# Fixed-width BDF fonts shipped with rpi-rgb-led-matrix, largest first. Metrics
# are FONT_ASCENT/FONT_DESCENT from the .bdf files.
FONTS = [
    FontSpec("7x13", 7, 11, 2),
    FontSpec("6x10", 6, 8, 2),
    FontSpec("5x7", 5, 6, 1),
    FontSpec("4x6", 4, 5, 1),
]


def _block_height(fonts, gap):
    return sum(f.height for f in fonts) + gap * (len(fonts) - 1)


def _place(lines, fonts):
    """Center the lines on the matrix. Returns [(font, x, baseline_y, text)]."""
    gap = 1 if _block_height(fonts, 1) <= MATRIX_HEIGHT else 0
    top = (MATRIX_HEIGHT - _block_height(fonts, gap)) // 2
    placed = []
    for line, font in zip(lines, fonts):
        text = line[:font.chars_per_line()]
        x = (MATRIX_WIDTH - len(text) * font.width) // 2
        placed.append((font, x, top + font.ascent, text))
        top += font.height + gap
    return placed


def layout_lines(lines):
    """Give each line the largest font that fits its width, then shrink the biggest
    lines until the block fits the matrix height. Lines that still don't fit at
    the smallest font are dropped from the bottom, and over-long lines are cut."""
    lines = [line for line in lines if line]
    smallest = len(FONTS) - 1
    font_index = []
    for line in lines:
        fitting = [i for i, f in enumerate(FONTS) if len(line) * f.width <= MATRIX_WIDTH]
        font_index.append(fitting[0] if fitting else smallest)

    while lines and _block_height([FONTS[i] for i in font_index], 0) > MATRIX_HEIGHT:
        biggest = min(range(len(font_index)), key=lambda n: font_index[n])
        if font_index[biggest] == smallest:
            lines, font_index = lines[:-1], font_index[:-1]
        else:
            font_index[biggest] += 1

    return _place(lines, [FONTS[i] for i in font_index])


def wrap_words(text, width):
    """Greedy word wrap; words longer than a line are split."""
    lines = []
    current = ""
    for word in text.split():
        while len(word) > width:
            if current:
                lines.append(current)
                current = ""
            lines.append(word[:width])
            word = word[width:]
        if not current:
            current = word
        elif len(current) + 1 + len(word) <= width:
            current += " " + word
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def layout_paragraph(text):
    """Wrap free text with the largest font that fits it all, else the smallest font
    showing as much as fits."""
    for font in FONTS:
        lines = wrap_words(text, font.chars_per_line())
        if _block_height([font] * len(lines), 0) <= MATRIX_HEIGHT:
            return _place(lines, [font] * len(lines))
    font = FONTS[-1]
    lines = wrap_words(text, font.chars_per_line())[:MATRIX_HEIGHT // font.height]
    return _place(lines, [font] * len(lines))


def layout_card(card):
    """A card is either a list of lines or a string of free text."""
    if isinstance(card, str):
        return layout_paragraph(card)
    return layout_lines(card)
