#!/usr/bin/env python3
"""Compositing an overlay tile onto what is under it, for any level.

THE ENGINE HAS NO MASKED TILE PATH AND IS NOT GETTING ONE (CLAUDE.md
7.3): a masked cell is 1,338-2,007 T against a copy's 669, and a
scrolling frame has 3,548. So an overlay and the tile it stands on are
composited ONCE, here, at build time, and the map cell points at the
result. A map cell is a finished tile and nothing is drawn over
anything at run time.

THIS FILE IS make_city_map.py's OWN BAKE, LIFTED VERBATIM so that a
second environment could use it. The City was the only level with
overlays in it for as long as the City was the only level; the cave's
ladder, its crystals, its beams and its lamps are nine more, and the
station's lasers six (7.3's table). What says the lift changed nothing
is that citytiles.bin, city_baked.json and tileflags_level1_city.bin
all still come out byte for byte, which tools/test_format.py checks on
the emulator and the editor's own OverlayBaker reproduces in C#.

The pixels come from the artist's own sheet, quantised against
src/palette.asm exactly as tools/aseprite2spans.py does it, and go out
in the COLUMN-MAJOR order the tile blitters read.
"""
import json
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, HERE)


def name_of(names, extra, index):
    """A tile's name, baked or not, for the report and the flags."""
    return names[index] if index < len(names) else extra[index - len(names)]


def bake_overlays(art, sheet_stem, names, BAKED):
    """Composite every (overlay, background) pair into a new tile.

    Returns (extra tile bytes, extra names). The pixels come from the
    artist's own sheet, quantised against src/palette.asm exactly as
    tools/aseprite2spans.py does it, and go out in the same
    COLUMN-MAJOR order the tile blitters read (see encode_tiles there).
    An overlay's pen 0 is the transparent one (CLAUDE.md 7.3); every
    other pen wins over what is underneath.
    """
    import cpclib
    from aseprite2spans import game_palette
    sheet = Image.open(os.path.join(
        art, f"{sheet_stem}.png")).convert("RGBA")
    js = json.load(open(os.path.join(art, f"{sheet_stem}.json")))
    frames = js["frames"]
    if isinstance(frames, dict):
        frames = [frames[k] for k in frames]
    palette = game_palette(os.path.join(ROOT, "src", "palette.asm"))

    w, h = frames[0]["frame"]["w"], frames[0]["frame"]["h"]
    cache = {}

    def pens_of(i):
        """An original tile's pens, or a baked one's - AND A BAKED ONE
        CAN BE UNDER ANOTHER. The lamp's pole hangs under its head and
        the tank's cells sit on top of the roof props, so a pair can
        name a tile that is itself a pair. Every baked index is higher
        than the two it was made from, so resolving in index order
        terminates."""
        if i in cache:
            return cache[i]
        if i < len(names):
            b = frames[i]["frame"]
            crop = sheet.crop((b["x"], b["y"],
                               b["x"] + b["w"], b["y"] + b["h"]))
            cache[i] = cpclib.quantise(crop, palette)
        else:
            over, under = next(k for k, v in BAKED.items() if v == i)
            top, bottom = pens_of(over), pens_of(under)
            cache[i] = [[top[y][x] or bottom[y][x] for x in range(w)]
                        for y in range(h)]
        return cache[i]

    def encode(pens):
        out = bytearray()
        for col in range(w // 4):               # 4 pixels a character
            for y in range(h):
                for x in (col * 4, col * 4 + 2):
                    out.append(cpclib.encode_pixels(pens[y][x], pens[y][x + 1]))
        return bytes(out)

    # AND A PAIR THAT COMPOSITES TO THE OVERLAY ITSELF IS NOT BAKED.
    # Where the background is black in every pixel the overlay's
    # transparent pen 0 already comes out black, so the composite is
    # byte for byte the tile the artist drew and a copy of it would be
    # 64 bytes of bank for nothing. This is the one place that question
    # is ANSWERED rather than assumed, and the answer was a surprise:
    # `far_fill` is not all black (4 lit pixels of 128), so the three
    # roof props on it are baked like everything else and only
    # `tank_10` is dropped.
    blob, extra, remap, same = bytearray(), [], {}, {}
    for (over, under), index in sorted(BAKED.items(), key=lambda kv: kv[1]):
        bytes_ = encode(pens_of(index))
        if bytes_ == encode(pens_of(over)):
            remap[index] = over
            same[index] = name_of(names, extra, under)
            continue
        remap[index] = len(names) + len(extra)
        extra.append(f"{names[over]}_on_{name_of(names, extra, under)}")
        blob += bytes_
    return bytes(blob), extra, remap, same


