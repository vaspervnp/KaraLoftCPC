#!/usr/bin/env python3
"""Generate a PLACEHOLDER tile sheet and level map for the City level.

Scaffolding, like the sprite generator: it exists so the scrolling engine
has real data to move. Replace assets/placeholder with drawn tiles and a
designed map; the formats are what matter.

Tile sheet: 16 tiles of 16x16 in one row.
Map: MAP_W x MAP_H bytes of tile indices, row major, top row first.
"""
import os
from PIL import Image, ImageDraw

TW = TH = 16
TILES = 16
MAP_W, MAP_H = 64, 16
# Both dimensions are powers of two so the renderer wraps the map with an
# AND instead of a divide. 12 of the 16 tile rows fill the 192-scanline
# play area; the rest is below ground, which is what the cave level will
# scroll down into.

SKY, STAR, ROOF, BRICK, WINDOW, LEDGE, PIPE, RUBBLE = range(8)

PAL = {
    "sky":    (0, 2, 107),
    "dark":   (0, 2, 1),
    "star":   (255, 243, 249),
    "roof":   (108, 2, 1),
    "brick":  (105, 2, 104),
    "mortar": (0, 2, 1),
    "glass":  (12, 123, 244),
    "lit":    (243, 243, 13),
    "metal":  (110, 125, 107),
}


def tile_sky(d):
    d.rectangle([0, 0, TW - 1, TH - 1], fill=PAL["sky"])


def tile_star(d):
    tile_sky(d)
    for x, y in ((3, 4), (11, 9), (7, 13)):
        d.point((x, y), fill=PAL["star"])


def tile_roof(d):
    d.rectangle([0, 0, TW - 1, TH - 1], fill=PAL["brick"])
    d.rectangle([0, 0, TW - 1, 3], fill=PAL["roof"])


def tile_brick(d):
    d.rectangle([0, 0, TW - 1, TH - 1], fill=PAL["brick"])
    for y in range(0, TH, 4):
        d.line([0, y, TW - 1, y], fill=PAL["mortar"])
    for y in range(0, TH, 8):
        d.line([7, y, 7, y + 3], fill=PAL["mortar"])
        d.line([15, y + 4, 15, y + 7], fill=PAL["mortar"])


def tile_window(d):
    tile_brick(d)
    d.rectangle([3, 3, 12, 12], fill=PAL["glass"])
    d.rectangle([5, 5, 10, 10], fill=PAL["lit"])


def tile_ledge(d):
    d.rectangle([0, 0, TW - 1, TH - 1], fill=PAL["sky"])
    d.rectangle([0, 0, TW - 1, 5], fill=PAL["metal"])
    d.line([0, 6, TW - 1, 6], fill=PAL["dark"])


def tile_pipe(d):
    d.rectangle([0, 0, TW - 1, TH - 1], fill=PAL["brick"])
    d.rectangle([5, 0, 10, TH - 1], fill=PAL["metal"])
    d.line([5, 0, 5, TH - 1], fill=PAL["dark"])


def tile_rubble(d):
    d.rectangle([0, 0, TW - 1, TH - 1], fill=PAL["dark"])
    for x, y in ((2, 11), (6, 9), (10, 12), (13, 10), (4, 14)):
        d.rectangle([x, y, x + 2, y + 2], fill=PAL["brick"])


DRAWERS = [tile_sky, tile_star, tile_roof, tile_brick, tile_window,
           tile_ledge, tile_pipe, tile_rubble]


def build_sheet(path):
    sheet = Image.new("RGB", (TW * TILES, TH), PAL["sky"])
    for i in range(TILES):
        tile = Image.new("RGB", (TW, TH), PAL["sky"])
        DRAWERS[i % len(DRAWERS)](ImageDraw.Draw(tile))
        sheet.paste(tile, (i * TW, 0))
    sheet.save(path)
    return sheet


def build_map(path):
    grid = [[SKY] * MAP_W for _ in range(MAP_H)]
    sky_rows = 12
    for x in range(MAP_W):
        if (x * 7) % 11 == 0:
            grid[1][x] = STAR
        # ONE continuous rooftop, not a varied skyline. A tile is 16 pixels
        # and she walks 2 a frame, so any step up in the roof line is a wall
        # that stops her dead - and a player who cannot walk is a camera
        # that cannot scroll, which makes every scrolling test vacuous
        # without failing it. The variety lives in the windows and pipes
        # below the roof and in the ledges above it, neither of which is
        # in her way. Replace this whole file with a designed level; the
        # runway is a property the scroll tests need, not the game.
        height = 6
        top = sky_rows - height
        grid[top][x] = ROOF
        for y in range(top + 1, sky_rows):
            grid[y][x] = WINDOW if ((x % 3) == 1 and (y - top) % 2 == 0) else BRICK
        if x % 13 == 6:
            for y in range(top + 1, sky_rows):
                grid[y][x] = PIPE
        for y in range(sky_rows, MAP_H):          # below street level
            grid[y][x] = RUBBLE if (x + y) % 5 == 0 else BRICK
    for x in range(8, MAP_W, 17):          # a few ledges to jump to
        for dx in range(3):
            if x + dx < MAP_W:
                grid[4][x + dx] = LEDGE
    blob = bytes(b for row in grid for b in row)
    open(path, "wb").write(blob)
    return blob


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(here, "..", "assets", "placeholder")
    sheet = build_sheet(os.path.join(out, "city_tiles.png"))
    blob = build_map(os.path.join(out, "city_map.bin"))
    print(f"-> city_tiles.png  {sheet.width}x{sheet.height}, {TILES} tiles")
    print(f"-> city_map.bin    {MAP_W}x{MAP_H} = {len(blob)} bytes")


if __name__ == "__main__":
    main()
