#!/usr/bin/env python3
"""The HUD's art, as raw Mode 0 bytes the engine copies.

WHY THE HUD IS A BAR AND NOT THE ARTIST'S WHOLE STRIP. The mockup in
assets/sprites/common/mockup_hud.png is a full-width 16-line band -
heart, health, ammo, coins, key, oxygen - and a band like that has to
stay still while the CRTC scrolls the picture underneath it. On this
machine that means a raster split, and a raster split on a 6845 is not
a mid-frame write to R12/R13: the address latch is only reloaded from
those registers at vertical total (and, on a UM6845R, during the
scanlines of character row 0). It is `rupture' - reprogramming R4 so
the CRTC restarts a frame mid-screen - and rupture needs one precisely
timed write in the FIRST character row of each part. Neither of those
rows has an interrupt in it, so each costs a counted delay: measured
against the 6845 the firmware leaves behind, 4,588 T to reach display
line 0 from tick 2 and 4,096 more to reach line 16. ~8,700 T of a frame
with 3,548 spare (CLAUDE.md 9).

So the HUD is what the frame can pay for: a six-cell health bar at the
top left, 24x8 Mode 0 pixels, copied into place whenever the view moves
- 96 bytes, and that IS the cost, because anything screen-fixed on a
hardware-scrolled display has to be rewritten every time the start
address changes.

The cells are the artist's own: hud_bars' health_full and health_empty,
4x8 pixels each, quantised against src/palette.asm like every other
asset (CLAUDE.md 7.1) rather than against their own image.

AND THE ROUNDS SHE IS CARRYING ARE THE ARTIST'S BULLET, ONE OF THE
THREE IN hud_icons' `ammo'. The mockup draws the ammo as that icon and
a two-digit number; what the engine shows is the fourteen rounds in her
two magazines as fourteen of the bullets themselves, emptying from the
left (CLAUDE.md 7.8). There is no bar cell for it in the art - the
sheet has health and oxygen - so the pip is cut out of the icon rather
than drawn here: the bullet is one pixel wide with an orange tip and a
yellow body, which is exactly the two-pixel pitch a Mode 0 byte holds.

A SPENT ROUND IS THE SAME SILHOUETTE IN THE DARK, which is the
convention the bars already use: health_full is (255,0,0) over a
(128,0,0) foot and health_empty is that same dark red. (128,128,0)
quantises to pen 12 against the bullet's pen 11, so a spent round is
the dark of its own colour and not a hole in the row.
"""
import json
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cpclib                                                   # noqa: E402
from aseprite2spans import game_palette                         # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
ART = os.path.join(ROOT, "assets", "sprites", "common")

CELLS = ("health_full", "health_empty")

# One round is 1 pixel of bullet and 1 of gap, so a 4-pixel cell holds
# TWO of them and fourteen rounds are seven CRTC characters. The three
# images are all the states a cell can be in, because the rounds empty
# from the left: both spent, the left one spent, neither.
PIP_DARK = (128, 128, 0)


def cell_bytes(sheet, box, palette):
    """One 4x8 cell, LINE-MAJOR: two bytes a line, eight lines.

    Line-major and not column-major (which is what the TILES are stored
    in - CLAUDE.md 9) because the HUD is copied a whole line at a time
    into consecutive screen bytes, where a tile blitter paints a
    character column two bytes a raster.
    """
    pens = cpclib.quantise(sheet.crop(
        (box["x"], box["y"], box["x"] + box["w"], box["y"] + box["h"])),
        palette)
    assert box["w"] == 4 and box["h"] == 8, box
    out = bytearray()
    for y in range(8):
        for x in (0, 2):
            out.append(cpclib.encode_pixels(pens[y][x], pens[y][x + 1]))
    return bytes(out)


def bullet_column(icon, box):
    """The artist's own bullet, as (r,g,b) per line, top to bottom.

    hud_icons' `ammo' is three of them at x = 1, 3 and 5 over lines 4-9,
    with a grey shelf under the group at line 11 which has no room in an
    8-line cell. Read off the sheet rather than written down here, so a
    re-drawn icon re-draws the HUD.
    """
    px = icon.crop((box["x"], box["y"], box["x"] + box["w"],
                    box["y"] + box["h"])).convert("RGB")
    xs = [x for x in range(px.width)
          if any(px.getpixel((x, y)) != (0, 0, 0) for y in range(px.height))]
    x = xs[0]                                   # the leftmost of the three
    lines = [px.getpixel((x, y)) for y in range(px.height)]
    lines = [c for c in lines if c != (0, 0, 0)]
    assert 4 <= len(lines) <= 8, lines          # the shelf is not part of it
    return lines


def pip_cell(lines, left, right, palette):
    """A 4x8 cell with a round at x=0 and x=2, live or spent.

    The bullet sits on lines 1..6 like the bars' own content, so the
    ammo and the health line up across the bottom row.
    """
    img = Image.new("RGBA", (4, 8), (0, 0, 0, 255))
    for i, colour in enumerate(lines):
        y = 1 + i
        if y >= 7:
            break
        if left is not None:
            img.putpixel((0, y), (left if left != "live" else colour) + (255,))
        if right is not None:
            img.putpixel((2, y), (right if right != "live" else colour) + (255,))
    pens = cpclib.quantise(img, palette)
    out = bytearray()
    for y in range(8):
        for x in (0, 2):
            out.append(cpclib.encode_pixels(pens[y][x], pens[y][x + 1]))
    return bytes(out)


def main():
    js = json.load(open(os.path.join(ART, "hud_bars_cpc_mode0_sheet.json")))
    frames = js["frames"]
    if isinstance(frames, dict):
        frames = [frames[k] for k in frames]
    tags = {t["name"]: t["from"] for t in js["meta"]["frameTags"]}
    sheet = Image.open(os.path.join(
        ART, "hud_bars_cpc_mode0_sheet.png")).convert("RGBA")
    palette = game_palette(os.path.join(ROOT, "src", "palette.asm"))

    out = [f"; generated by tools/make_hud.py - do not edit",
           f"; the artist's hud_bars, 4x8 a cell, two bytes a line"]
    for name in CELLS:
        b = cell_bytes(sheet, frames[tags[name]]["frame"], palette)
        label = "HUD_CELL_" + name.split("_")[1].upper()
        out.append(f"{label}:")
        for y in range(8):
            out.append(f"                db &{b[y*2]:02X},&{b[y*2+1]:02X}")
    # ---- the rounds, out of the ammo icon -------------------------
    ijs = json.load(open(os.path.join(ART, "hud_icons_cpc_mode0_sheet.json")))
    iframes = ijs["frames"]
    if isinstance(iframes, dict):
        iframes = [iframes[k] for k in iframes]
    itags = {t["name"]: t["from"] for t in ijs["meta"]["frameTags"]}
    icon = Image.open(os.path.join(
        ART, "hud_icons_cpc_mode0_sheet.png")).convert("RGBA")
    bullet = bullet_column(icon, iframes[itags["ammo"]]["frame"])
    out.append("; and the rounds: the ammo icon's own bullet, two to a cell")
    for label, left, right in (("HUD_PIP_FULL", "live", "live"),
                               ("HUD_PIP_HALF", PIP_DARK, "live"),
                               ("HUD_PIP_EMPTY", PIP_DARK, PIP_DARK)):
        b = pip_cell(bullet, left, right, palette)
        out.append(f"{label}:")
        for y in range(8):
            out.append(f"                db &{b[y*2]:02X},&{b[y*2+1]:02X}")

    # ---- and the digits, for the spare magazines ------------------
    djs = json.load(open(os.path.join(ART, "hud_digits_cpc_mode0_sheet.json")))
    dframes = djs["frames"]
    if isinstance(dframes, dict):
        dframes = [dframes[k] for k in dframes]
    dtags = {t["name"]: t["from"] for t in djs["meta"]["frameTags"]}
    dsheet = Image.open(os.path.join(
        ART, "hud_digits_cpc_mode0_sheet.png")).convert("RGBA")
    out.append("; and the artist's digits, 0-9, sixteen bytes each - how")
    out.append("; many magazines the reserve is worth (CLAUDE.md 7.8)")
    out.append("HUD_DIGITS:")
    for d in range(10):
        b = cell_bytes(dsheet, dframes[dtags[f"d{d}"]]["frame"], palette)
        out.append(f"                ; {d}")
        for y in range(8):
            out.append(f"                db &{b[y*2]:02X},&{b[y*2+1]:02X}")

    path = os.path.join(ROOT, "build", "hud_art.inc")
    open(path, "w").write("\n".join(out) + "\n")
    lit = sum(1 for name in CELLS[:1]
              for v in cell_bytes(sheet, frames[tags[name]]["frame"], palette)
              if v)
    print(f"-> hud_art.inc    {len(CELLS) + 3 + 10} cells of 16 bytes, "
          f"full has {lit} non-zero bytes of 16, the bullet is "
          f"{len(bullet)} lines")


if __name__ == "__main__":
    main()
