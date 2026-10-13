"""Cut the drawing hand out of the reference picture -> assets/hand_pencil.png (transparent background).

    python tools/make_hand.py [source.jpg]

The forearm in the picture is open at the bottom; it is cut straight across at ARM_CUT and the scene
continues it off the frame (see app/sketch.py, draw_hand). The PNG keeps the source size so coordinates match;
keep HAND_TIP / ARM_CUT / ARM_DIR in app/sketch.py in sync if the source changes.
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'assets', 'hand_reference.jpg')
OUT = os.path.join(ROOT, 'assets', 'hand_pencil.png')
ARM_CUT = ((995, 820), (842, 925))      # outer edge point, inner edge point, straight across the forearm
ARM_DIR = (0.65, 0.76)                  # forearm direction (towards the elbow)
PENCIL = [(210, 421), (304, 404), (928, 476), (922, 546), (300, 468)]   # its end is open in the drawing
DARK, PAPER = 150, 232                  # line threshold, lightest anti-aliasing kept outside the hand


def main():
    src = Image.open(SRC).convert('RGB')
    grey = np.asarray(src.convert('L')).astype(np.float32)
    h, w = grey.shape
    (ox, oy), (ix, iy) = ARM_CUT
    dx, dy = ARM_DIR
    # walls: the drawing's lines plus the cut, and everything past the cut
    walls = Image.fromarray(np.where(grey < DARK, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(walls)
    d.line([(ox + dy * 12, oy - dx * 12), (ix - dy * 12, iy + dx * 12)], fill=0, width=5)
    d.polygon([(ox, oy), (ox + dx * 3000, oy + dy * 3000), (ix + dx * 3000, iy + dy * 3000), (ix, iy)], fill=0)
    ImageDraw.floodfill(walls, (2, 2), 128)
    outside = np.asarray(walls) == 128
    pencil = Image.new('L', (w, h), 0)
    ImageDraw.Draw(pencil).polygon(PENCIL, fill=255)
    outside &= ~(np.asarray(pencil) > 0)
    nx, ny = dy, -dx                    # across the arm, pointing to the outer edge
    past = Image.new('L', (w, h), 0)
    ImageDraw.Draw(past).polygon([(ox + nx * 20, oy + ny * 20), (ox + nx * 20 + dx * 3000, oy + ny * 20 + dy * 3000),
                                  (ix - nx * 20 + dx * 3000, iy - ny * 20 + dy * 3000), (ix - nx * 20, iy - ny * 20)],
                                 fill=255)
    past = np.asarray(past) > 0

    rgb = np.asarray(src).astype(np.float32)
    alpha = np.ones((h, w), np.float32)
    # outside the hand only the ink stays, as anti-aliased black
    ink = np.clip((PAPER - grey) / (PAPER - 40), 0, 1)
    alpha[outside] = ink[outside]
    rgb[outside] = 20
    alpha[past] = 0
    # inside the hand: pure white skin, keep the drawn lines and the pencil's grey
    inside = ~outside & ~past
    rgb[inside & (grey > 238)] = 255
    out = np.dstack([rgb, alpha * 255]).clip(0, 255).astype(np.uint8)
    im = Image.fromarray(out, 'RGBA')
    print('hand area px:', int(inside.sum()), 'bbox:', im.getbbox())     # kept uncropped: same coords as SRC
    im.save(OUT)
    print('saved', OUT, im.size)


if __name__ == '__main__':
    main()
