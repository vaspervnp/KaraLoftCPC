#!/usr/bin/env python3
"""level_<n>.lvl: the format, the file, and the engine that reads it.

docs/editor.md 9.2 is the contract between this engine and the editor
that does not exist yet, and CLAUDE.md 11 explains why the engine reads
it first: the editor's whole output is this file, so if the format is
not exercised until a web application writes it, the first disagreement
costs a change on both sides. tools/make_level.py is the reference
writer and this suite is the golden file.

What it checks:

  1. the bytes: an independent reader takes the header apart field by
     field and finds the map and the entities where the offsets say
  2. the engine: MAP_INSTALL puts THAT map in RAM, THOSE entities in the
     table, the header's own count in ENT_COUNT, and the tileset's flags
     in TILE_ATTR - with the only differences being the pickups
     ENT_BAKE stamps into the map (CLAUDE.md 8.6)
  3. the controls, and there are three, because a loader that ignored
     the file entirely would pass everything above on a build where the
     data still rode in the core image:
       - break the magic and it refuses, leaving the map alone
       - give it a map of another shape and it refuses
       - take TA_CLIMB off the ladder IN THE FILE and the table in RAM
         loses it too, which is what says the flags come from the file
"""
import os
import sys

sys.path.insert(0, "/home/vasilhs/cpcemu")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bench import symbols, boot, raw                           # noqa: E402
import make_level                                              # noqa: E402
import make_city_map as city                                   # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
BUILD = os.path.join(ROOT, "build")
MAP_BYTES = city.MAP_W * city.MAP_H
SCRATCH_FIRST = 240                     # the bake's private tiles (8.6)

fails = []


def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}{'  ' + detail if detail else ''}")
    if not ok:
        fails.append(name)


def main():
    sym = symbols()
    for n in ("LEVEL_LVL", "LEVEL_TILEFLAGS", "MAP_INSTALL", "MAP_ADDR",
              "ENT_TABLE", "ENT_COUNT", "TILE_ATTR", "TILE_ATTR_N"):
        if n not in sym:
            check(f"the engine has {n}", False)
    if fails:
        return 1

    blob = open(os.path.join(BUILD, "level_1.lvl"), "rb").read()
    flags = open(os.path.join(BUILD, "tileflags_level1_city.bin"), "rb").read()
    src_map = open(os.path.join(BUILD, "city_map.bin"), "rb").read()
    src_ents = open(os.path.join(BUILD, "city_entities.bin"), "rb").read()

    # ---- 1. the bytes ----------------------------------------------
    print("\n  the file, read back by hand:")
    lvl = make_level.read(blob)
    check("it says it is a level", blob[:2] == b"LV" and lvl["version"] == 1,
          f"magic {blob[:2]!r}, version {lvl['version']}")
    check("the shape is the engine's",
          lvl["width"] == city.MAP_W and lvl["height"] == city.MAP_H,
          f"{lvl['width']}x{lvl['height']} tiles")
    check("the offsets land where the sections are",
          lvl["offsets"][0] == make_level.HEADER
          and lvl["offsets"][1] == make_level.HEADER + MAP_BYTES
          and lvl["offsets"][3] == len(blob),
          f"map at {lvl['offsets'][0]}, entities at {lvl['offsets'][1]}, "
          f"regions at {lvl['offsets'][3]} of {len(blob)} bytes")
    check("the map section IS the map", lvl["map"] == src_map,
          f"{len(lvl['map'])} bytes, byte for byte")
    check("the entity section is the live records, in RAM's own layout",
          lvl["entity_bytes"] == src_ents[:lvl["entities"] * 8]
          and lvl["entities"] == sum(1 for i in range(0, len(src_ents), 8)
                                     if src_ents[i + 5] & 1),
          f"{lvl['entities']} of the table's 24, eight bytes each - so the "
          f"loader is an LDIR and not a conversion")
    check("links and regions are counted even at zero",
          lvl["links"] == 0 and lvl["regions"] == 0,
          "the City has none, and the offsets are still real")

    # ---- 2. the engine ----------------------------------------------
    print("\n  and what the engine made of it:")
    m = boot(sym, scroll=True)
    ram_map = bytes(m.read_ram(sym["MAP_ADDR"], MAP_BYTES))
    diff = [i for i in range(MAP_BYTES) if ram_map[i] != lvl["map"][i]]
    baked = [i for i in diff if ram_map[i] >= SCRATCH_FIRST]
    check("the map in RAM is the file's map",
          len(diff) == len(baked) and len(baked) <= 8,
          f"{len(diff)} cells differ and all {len(baked)} of them are "
          f"pickups ENT_BAKE stamped into scratch tiles (8.6)")
    check("the entity table is the file's records",
          bytes(m.read_ram(sym["ENT_TABLE"], lvl["entities"] * 8))
          == lvl["entity_bytes"])
    check("ENT_COUNT is the header's count, not a walk of the table",
          m.peek(sym["ENT_COUNT"]) == lvl["entities"],
          f"{m.peek(sym['ENT_COUNT'])} of {sym['ENT_MAX']} slots - what "
          f"ENT_UPDATE sweeps every other frame")
    attr = bytes(m.read_ram(sym["TILE_ATTR"], sym["TILE_ATTR_N"]))
    check("TILE_ATTR is the tileset's flags file",
          attr[:len(flags)] == flags,
          f"{len(flags)} tiles, {sum(1 for f in flags if f)} with anything on")
    check("... and every other index answers zero",
          set(attr[len(flags):]) == {0},
          f"a map byte is an index, so all {sym['TILE_ATTR_N']} of them have "
          f"to be there")

    # ---- 3. the controls --------------------------------------------
    print("\n  the controls - it really is reading the file:")

    def reinstall(mm):
        """Wipe the map, run the loader, say whether it put one back."""
        mm.write_ram(sym["MAP_ADDR"], bytes(MAP_BYTES))
        raw(mm, sym["MAP_INSTALL"])
        return bytes(mm.read_ram(sym["MAP_ADDR"], MAP_BYTES))

    m = boot(sym, scroll=True)
    again = reinstall(m)
    check("re-running the loader puts the map back",
          again[:16] == lvl["map"][:16],
          "which is what the two controls below are measured against")

    m.poke(sym["LEVEL_LVL"], ord("X"))          # "XV" is not a level
    blank = reinstall(m)
    check("a broken magic is refused, and the map is left alone",
          set(blank) == {0},
          "nothing installed - the loader read the header and gave up")
    m.poke(sym["LEVEL_LVL"], ord("L"))

    m.poke(sym["LEVEL_LVL"] + 5, 64)            # a 64-tile-wide map
    wrong = reinstall(m)
    check("a map of another shape is refused too",
          set(wrong) == {0},
          "MAP_CELL scales the row out of the base address at compile "
          "time, so 128x16 is not a preference")
    m.poke(sym["LEVEL_LVL"] + 5, city.MAP_W & 255)

    ladder = [i for i, n in enumerate(city.tile_names()[1]) if n == "ladder"][0]
    m.poke(sym["LEVEL_TILEFLAGS"] + ladder, 0)
    reinstall(m)
    check("and the flags come from the file, not from the engine",
          m.peek(sym["TILE_ATTR"] + ladder) == 0,
          f"tile {ladder} is the ladder: zero it in the file and the table "
          f"in RAM loses TA_CLIMB with it")

    print()
    if fails:
        print(f"FAILED: {len(fails)} check(s): " + ", ".join(sorted(set(fails))))
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
