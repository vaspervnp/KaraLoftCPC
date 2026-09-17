#!/usr/bin/env python3
"""level_<n>.lvl - the binary the EDITOR will write, written here first.

docs/editor.md 9.2 fixes the format and CLAUDE.md 11 explains the order:
the editor's whole output is this file, so if it is written before the
engine reads the format, the first thing that tests the format is a web
application and a disagreement then costs a change on both sides. This
tool is the reference implementation - the same bytes, by hand, against
a level the engine already plays on real hardware.

    0  2  magic "LV"           9  1  tileset id
    2  1  format version      10  1  entity count
    3  1  level id            11  1  link count
    4  1  flags               12  1  region count
    5  2  width in tiles      13  8  u16 offsets: map, entities,
    7  2  height in tiles            links, regions

The map is one byte a tile, row-major. An entity is the eight bytes
src/entity.asm already lays out in RAM (kind, x u16, y u16, flags, p0,
p1), so the loader is an LDIR and not a conversion. Links and regions
are counted and their offsets are real; the City has none of either.

THE TILE FLAGS ARE A SEPARATE FILE, because they belong to the TILESET
and not to the level: tileflags_<level>.bin, one byte a tile, in the
artist's frame order. src/collide.asm takes the format's own bit order
so that file IS the engine's table.
"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
BUILD = os.path.join(ROOT, "build")

MAGIC = b"LV"
VERSION = 1
HEADER = 21

SCROLL_H, SCROLL_V = 0, 1               # flags bits 0-1
UNDERWATER, MAP_RLE = 4, 8              # bits 2 and 3


def pack(level_id, tileset_id, width, height, map_bytes, entities,
         flags=SCROLL_H, links=b"", regions=b""):
    """The bytes, and nothing about where they came from."""
    if len(map_bytes) != width * height:
        raise SystemExit(f"map is {len(map_bytes)} bytes, not "
                         f"{width}x{height} = {width * height}")
    if len(entities) % 8:
        raise SystemExit("an entity is eight bytes")
    n_ent = len(entities) // 8
    off_map = HEADER
    off_ent = off_map + len(map_bytes)
    off_link = off_ent + len(entities)
    off_region = off_link + len(links)
    head = (MAGIC + bytes([VERSION, level_id, flags])
            + struct.pack("<HH", width, height)
            + bytes([tileset_id, n_ent, len(links) // 4, len(regions) // 7])
            + struct.pack("<HHHH", off_map, off_ent, off_link, off_region))
    if len(head) != HEADER:
        raise SystemExit(f"header is {len(head)} bytes, not {HEADER}")
    return head + map_bytes + entities + links + regions


def read(blob):
    """The independent reader the golden test compares against."""
    if blob[:2] != MAGIC:
        raise ValueError("not a level: bad magic")
    ver, level_id, flags = blob[2], blob[3], blob[4]
    width, height = struct.unpack_from("<HH", blob, 5)
    tileset, n_ent, n_link, n_region = blob[9:13]
    off_map, off_ent, off_link, off_region = struct.unpack_from("<HHHH", blob, 13)
    return dict(
        version=ver, level=level_id, flags=flags, width=width, height=height,
        tileset=tileset, entities=n_ent, links=n_link, regions=n_region,
        map=blob[off_map:off_map + width * height],
        entity_bytes=blob[off_ent:off_ent + n_ent * 8],
        offsets=(off_map, off_ent, off_link, off_region))


def main():
    city_map = open(os.path.join(BUILD, "city_map.bin"), "rb").read()
    ents = open(os.path.join(BUILD, "city_entities.bin"), "rb").read()
    # ENTITY COUNT IS THE LEVEL'S, NOT THE TABLE'S. city_entities.bin is
    # padded to ENT_MAX so the engine's LDIR is one length; the header
    # counts the ones that are actually there, which is what ENT_UPDATE
    # sweeps (CLAUDE.md 8.6).
    live = 0
    for i in range(0, len(ents), 8):
        if ents[i + 5] & 1:                     # EF_ACTIVE
            live = i // 8 + 1
    blob = pack(level_id=1, tileset_id=1, width=128, height=16,
                map_bytes=city_map, entities=ents[:live * 8])
    out = os.path.join(BUILD, "level_1.lvl")
    open(out, "wb").write(blob)
    back = read(blob)
    assert back["map"] == city_map and back["entities"] == live
    print(f"-> level_1.lvl     {len(blob)} bytes: header {HEADER}, map "
          f"{back['width']}x{back['height']} = {len(city_map)}, "
          f"{live} entities, 0 links, 0 regions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
