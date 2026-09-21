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
import json
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


def disc_checks(sym, lvl):
    """... and it came off the DISC, which nothing above would notice.

    A level's map, its entity table and its tile flags used to be
    INCBINed into the core image and LDIRed to &B000 by the bootstrap:
    2,200 bytes of a binary that loads at &4000 and relocates below it,
    which is fine for exactly one level and impossible for six. They
    are raw sectors now, packed as one stream with the art
    (tools/make_level_image.py, LEVEL_MAP_LOAD) - and every check above
    would pass unchanged if they had never moved, because they compare
    RAM against the same build/ files either way.

    So this one writes a DIFFERENT level onto a copy of the disc and
    asks the machine what it drew. Nothing but the bytes on that disc
    can account for the answer.
    """
    import shutil
    import subprocess
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import dskdata
    from build_levels import zx0
    from make_level_image import FLAGS_BYTES

    print("\n  and it came off the DISC, not out of the binary:")
    scratch = os.environ.get("KARA_SCRATCH") or os.path.join(
        "/tmp", f"kara-format-{os.getuid()}")
    os.makedirs(scratch, exist_ok=True)

    # The same image the build makes, with one map cell changed. Cell 0
    # is the top-left of the sky and is `sky_stars`; `crate` is the last
    # tile of the artist's sheet and nothing else in the level uses it
    # up there, so finding it in RAM at cell 0 can only have come from
    # these bytes.
    names = city.tile_names()[1]
    marker = names.index("crate")
    flags = open(os.path.join(BUILD, "tileflags_level1_city.bin"), "rb").read()
    raw_lvl = bytearray(open(os.path.join(BUILD, "level_1.lvl"), "rb").read())
    off_map = raw_lvl[13] | (raw_lvl[14] << 8)
    was = raw_lvl[off_map]
    raw_lvl[off_map] = marker
    image = flags + bytes(FLAGS_BYTES - len(flags)) + bytes(raw_lvl)
    src = os.path.join(scratch, "marked.bin")
    open(src, "wb").write(image)
    zx0(src)
    packed = open(src.replace(".bin", ".zx0"), "rb").read()

    # ... onto a copy of the disc, at the sectors dskdata.py put the
    # real one on. The layout is worked out from the stream sizes, so
    # asking it again is asking the build where it wrote them.
    marked = os.path.join(scratch, "marked.dsk")
    shutil.copy(os.path.join(BUILD, "kara.dsk"), marked)
    layout, _ = dskdata.plan()
    where = [b for lvl_name, kind, b in layout if kind == "map"]
    if not where:
        check("the disc carries a level image at all", False,
              "dskdata.py planned no map stream")
        return
    _, track, sect, n, _ = where[0][0]
    img = bytearray(open(marked, "rb").read())
    off = dskdata.dsk_offsets(img)
    for i in range(n):
        sector = dskdata.SECT_FIRST + (sect - dskdata.SECT_FIRST + i) % dskdata.SECTORS
        t = track + (sect - dskdata.SECT_FIRST + i) // dskdata.SECTORS
        chunk = packed[i * 512:(i + 1) * 512]
        img[off[(t, sector)]:off[(t, sector)] + 512] = chunk + bytes(512 - len(chunk))
    open(marked, "wb").write(bytes(img))

    check("the marked level fits the sectors the real one has",
          len(packed) <= n * 512,
          f"{len(packed)} bytes into {n} sector(s) at track {track}")

    m = boot(sym, scroll=True, disc=marked)
    got = m.peek(sym["MAP_ADDR"])
    check("the map the engine drew is the map on THAT disc",
          got == marker and m.peek(sym["LEVEL_OK"]) == 1,
          f"cell 0 is tile {got} - `{names[marker]}` - where the build's "
          f"own level has {was}, `{names[was]}`")
    check("... and the binary has no level in it to fall back on",
          subprocess.run(["grep", "-c", "incbin \"level_", 
                          os.path.join(ROOT, "src", "main.asm")],
                         capture_output=True, text=True).stdout.strip() == "0",
          "main.asm INCBINs no level file, so &B000 is whatever the disc "
          "put there")


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

    # ---- 2b. the baked overlay tiles --------------------------------
    # CLAUDE.md 7.3: 34 tiles across three levels are drawn with pen 0
    # meaning TRANSPARENT and every tile blitter is a plain copy, so an
    # overlay placed as an ordinary cell paints its transparent pixels
    # BLACK - a lamp on a brick wall punches an 8x32 hole in it. They
    # are composited into new tiles at build time instead, which costs
    # 64 bytes of bank a pair and nothing per frame.
    print("\n  the overlays, baked onto what they cover:")
    import cpclib                                              # noqa: E402
    from aseprite2spans import game_palette                    # noqa: E402
    from PIL import Image                                      # noqa: E402
    art = os.path.join(ROOT, "assets", "sprites", "level1_city")
    sheet = Image.open(os.path.join(
        art, "city_tiles_cpc_mode0_sheet.png")).convert("RGBA")
    boxes = json.load(open(os.path.join(
        art, "city_tiles_cpc_mode0_sheet.json")))["frames"]
    if isinstance(boxes, dict):
        boxes = [boxes[k] for k in boxes]
    palette = game_palette(os.path.join(ROOT, "src", "palette.asm"))
    blob = open(os.path.join(BUILD, "levels", "level1_city",
                             "citytiles.bin"), "rb").read()
    names = city.tile_names()[1]
    per = 64                            # 4 bytes x 16 lines

    # WHAT THE BUILD BAKED, from the build's own record: BAKED is filled
    # while the map is generated, so importing the generator gets an
    # empty dict and a loop over it passes without looking at anything.
    baked = json.load(open(os.path.join(BUILD, "city_baked.json")))
    # ONLY THE ONES THAT WERE ACTUALLY BAKED RESOLVE. A pair whose
    # composite came out byte for byte the overlay itself keeps the
    # overlay's index (the background was black everywhere it showed),
    # so it is its own tile and not a recipe.
    by_index = {b["index"]: b for b in baked if b["baked"]}

    def pens_of(i):
        if i not in by_index:
            b = boxes[i]["frame"]
            return cpclib.quantise(sheet.crop(
                (b["x"], b["y"], b["x"] + b["w"], b["y"] + b["h"])), palette)
        top, bottom = pens_of(by_index[i]["over"]), pens_of(by_index[i]["under"])
        return [[top[y][x] or bottom[y][x] for x in range(8)]
                for y in range(16)]

    def encode(pens):
        out = bytearray()
        for col in range(2):
            for y in range(16):
                for x in (col * 4, col * 4 + 2):
                    out.append(cpclib.encode_pixels(pens[y][x], pens[y][x + 1]))
        return bytes(out)

    check("the build baked something at all", len(baked) > 0,
          f"{len(baked)} pairs in build/city_baked.json - the checks below "
          f"iterate it, so an empty one is a failure and not a pass")
    wrong, hid = [], []
    for b in [b for b in baked if b["baked"]]:
        index, over = b["index"], b["over"]
        if encode(pens_of(index)) != blob[index * per:(index + 1) * per]:
            wrong.append(b["name"])
        # ... and it has to differ from the overlay ALONE, or the
        # background did not come through and the bake did nothing.
        if blob[index * per:(index + 1) * per] == blob[over * per:(over + 1) * per]:
            hid.append(b["name"])
    check("every baked tile is the two it was made from", not wrong,
          f"{len(by_index)} of {len(baked)} pairs, composited independently "
          f"here from the artist's sheet and compared byte for byte"
          if not wrong else f"wrong: {wrong}")
    check("... and none of them is just the overlay again", not hid,
          "the background shows through where the overlay's pen 0 is, which "
          "is the hole this replaces" if not hid else f"flat: {hid}")
    # An overlay whose pair was DROPPED is placed raw and is meant to
    # be: the composite came out byte for byte the overlay, so there is
    # nothing under it to lose. Only an overlay that has a bake of its
    # own may not appear on its own.
    kept = {b["index"] for b in baked if not b["baked"]}
    raw_overlays = {b["over"] for b in by_index.values()} - kept
    check("the map places the baked tile, never the raw overlay",
          not (set(lvl["map"]) & raw_overlays),
          f"{len(set(lvl['map']))} distinct tiles in the map and none of the "
          f"{len(raw_overlays)} baked-away overlays among them"
          if not (set(lvl["map"]) & raw_overlays)
          else f"raw in the map: {sorted(set(lvl['map']) & raw_overlays)}")

    # THE NEGATIVE CONTROL FOR THE BAKE: composite the pair the other
    # way round - the background's pens over the overlay's - and the
    # bytes must stop matching. Without it "every baked tile is the two
    # it was made from" would pass for any tile made of the same two.
    flat = []
    for b in by_index.values():
        top, bottom = pens_of(b["over"]), pens_of(b["under"])
        wrong_way = [[bottom[y][x] or top[y][x] for x in range(8)]
                     for y in range(16)]
        if encode(wrong_way) == blob[b["index"] * per:(b["index"] + 1) * per]:
            flat.append(b["name"])
    check("... and the two are not interchangeable",
          len(flat) < len(by_index),
          f"{len(by_index) - len(flat)} of {len(by_index)} change when the "
          f"background is painted over the overlay instead - the other "
          f"{len(flat)} are tiles whose overlay covers everything it stands on")

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

    disc_checks(sym, lvl)

    print()
    if fails:
        print(f"FAILED: {len(fails)} check(s): " + ", ".join(sorted(set(fails))))
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
