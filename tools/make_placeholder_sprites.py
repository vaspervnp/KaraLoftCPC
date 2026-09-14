#!/usr/bin/env python3
"""Generate a PLACEHOLDER Kara Loft sprite sheet.

This is scaffolding, not art. It exists so the Module 2 exporter has real
input to be tested against end to end. Replace assets/placeholder with
hand-drawn frames when they exist; nothing downstream needs to change.

4 frames of 16x48: idle, run A, run B, run C.
"""
import os
from PIL import Image

W, H, FRAMES = 16, 48, 4

CLEAR = (0, 0, 0, 0)
HAIR = (108, 2, 1, 255)        # red
SKIN = (243, 125, 13, 255)     # orange
JACKET = (0, 2, 107, 255)      # blue
TROUSER = (12, 2, 244, 255)    # bright blue
BOOT = (0, 2, 1, 255)          # black
GUN = (110, 125, 107, 255)     # white


def box(px, x0, y0, x1, y1, col):
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            if 0 <= x < W and 0 <= y < H:
                px[x, y] = col


def draw_frame(img, n):
    px = img.load()
    box(px, 4, 2, 11, 6, HAIR)        # hair
    box(px, 5, 7, 10, 11, SKIN)       # face
    box(px, 3, 5, 4, 12, HAIR)        # hair falling left
    box(px, 11, 5, 12, 12, HAIR)      # ... and right
    box(px, 4, 12, 11, 27, JACKET)    # torso

    swing = (0, 1, 0, -1)[n]          # arms counter-swing with the legs
    box(px, 2, 13 + swing, 3, 22 + swing, JACKET)
    box(px, 12, 13 - swing, 13, 22 - swing, JACKET)
    box(px, 2, 23 + swing, 3, 24 + swing, SKIN)
    box(px, 12, 23 - swing, 13, 24 - swing, SKIN)
    box(px, 1, 24 + swing, 3, 25 + swing, GUN)      # dual pistols
    box(px, 12, 24 - swing, 14, 25 - swing, GUN)

    if n == 0:                                       # idle: feet together
        box(px, 5, 28, 7, 44, TROUSER)
        box(px, 8, 28, 10, 44, TROUSER)
        box(px, 4, 45, 7, 47, BOOT)
        box(px, 8, 45, 11, 47, BOOT)
    else:                                            # running: legs scissor
        lead = (0, 2, 0, -2)[n]
        box(px, 5 - lead, 28, 7 - lead, 43, TROUSER)
        box(px, 8 + lead, 28, 10 + lead, 43, TROUSER)
        box(px, 4 - lead, 44, 7 - lead, 46, BOOT)
        box(px, 8 + lead, 44, 11 + lead, 46, BOOT)


def main():
    sheet = Image.new("RGBA", (W * FRAMES, H), CLEAR)
    for n in range(FRAMES):
        frame = Image.new("RGBA", (W, H), CLEAR)
        draw_frame(frame, n)
        sheet.paste(frame, (n * W, 0))
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(here, "..", "assets", "placeholder", "kara_sheet.png")
    sheet.save(out)
    print(f"-> {os.path.normpath(out)}  {sheet.width}x{sheet.height}, {FRAMES} frames")


if __name__ == "__main__":
    main()
