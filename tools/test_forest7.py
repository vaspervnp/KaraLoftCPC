#!/usr/bin/env python3
"""Levels 7 and 8 on a 6128: the forest's spike traps, the altar that
stops them, and the first reader the level format's LINKS have had.

A TRAP IS A MAP CELL WHOSE TILE CHANGES (CLAUDE.md 8.17). The artist's
four cels of the spike trap and two states of the altar are composited
over the tile under them at build time, into consecutive indexes of the
forest's tileset; src/hazard.asm moves a trap's cell round its cycle by
writing one byte of the map, and HAZARD_HURT - which has bitten her in
the spike pits since 8.12 - bites her the frame a trap she is standing
in comes up, because the cels that bite carry TA_HAZARD. An altar given
its idol walks the level's links and puts down every trap it Disables.

WHAT MAKES IT A CHECK AND NOT A SCREENSHOT is that every expectation is
read out of something other than the code under test: the composites
are re-made here out of the artist's PNGs, the cycle is HZ_DUR's against
the map byte on the machine, the picture is every on-screen character
cell against the map's own tile, and the price of the altar is a walk
across the field with and without the idol. Each has a control that
puts back the thing it is about.
"""
import json
import os
import re
import sys

sys.path.insert(0, "/home/vasilhs/cpcemu")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bench import boot, symbols, sync                          # noqa: E402
from make_level import read                                    # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
BUILD = os.path.join(ROOT, "build")
ART = os.path.join(ROOT, "assets", "sprites", "level2_forest")
EDITOR = os.path.join(ROOT, "editor", "src", "CpcLevelEditor.Domain")

JOY_UP, JOY_RIGHT, JOY_FIRE = 0x01, 0x08, 0x10
GS_PLAY, GS_DEAD, GS_CLEAR = 0, 1, 2
TA_HAZARD, TA_ADVANCE = 4, 128
EK_HAZARD, EK_RECEPTACLE, EF_TAKEN = 5, 7, 2
MAP_W, ROW_BASE, ROW_GROUND = 128, 8, 9
FOREST_TILES = 42
TRAP_CELS = 4

fails = []


def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}{'  ' + detail if detail else ''}")
    if not ok:
        fails.append(name)


def word(m, a):
    return m.peek(a) | m.peek(a + 1) << 8


# =====================================================================
# THE MACHINE - helpers
# =====================================================================
def to_level(sym, level, frm=None):
    """Into `level` the way the game goes there: through the door of the
    one before it. `frm` is a machine already standing in that one."""
    m = frm or boot(sym, scroll=True)
    if frm is None:
        m.poke(sym["LEVEL_CUR"], level - 2)
    m.poke(sym["GAME_STATE"], GS_CLEAR)
    took = None
    for f in range(900):
        m.run_frames(1)
        if (m.peek(sym["GAME_STATE"]) == GS_PLAY
                and m.peek(sym["LEVEL_CUR"]) == level - 1):
            took = f + 1
            break
    m.run_frames(10)
    return m, took


def gframe(m, sym, joy):
    """One GAME frame with `joy` held, ending at the top of the loop."""
    m.joystick(joy)
    m.run_frames(1)
    sync(m, sym, 0)


def tile_of(m, sym):
    return (word(m, sym["KARA_WX"]) + 3) // 4


def pending(m, sym):
    n, p = m.peek(sym["HZ_PEND_N"]), sym["HZ_PEND"]
    return {(m.peek(p + 2 * i), m.peek(p + 2 * i + 1)) for i in range(n)}


def wrong_cells(m, sym, tiles, excuse="her"):
    """Every on-screen character cell whose bytes are not its map tile.

    At the top of the loop she has been erased and the background is
    finished, so video RAM is the map's picture - except three things
    that are not faults: the HUD strip, which is screen-fixed; the
    incoming column, whose head is painted into column 0 of the rows
    below while a step is pending (CLAUDE.md 8.2); and the cells still on
    the hazard painter's pending list THAT SHE IS STANDING IN - the one
    place the painter is allowed to leave a cel behind (CLAUDE.md 8.17).
    A pending cell anywhere else is a fault and is counted: excusing
    every pending cell would excuse a painter that never painted. A
    baked pickup's scratch tile is in bank C4, not in the blob, and is
    skipped.

    `excuse` is which pending cells are not faults: "her" is the rule
    above, "none" counts the cells she stands in as well - which is what
    HAZARD_PAINT_C is for - and "all" is the lax model, which can see
    nothing but a cell painted where it must not be."""
    wx, wcr = m.peek(sym["WORLD_X"]), m.peek(sym["WORLD_CR"])
    scroll = word(m, sym["SCROLL"])
    mp = bytes(m.peek(sym["MAP_ADDR"] + i) for i in range(2048))
    kx, ky = word(m, sym["EN_KX"]), word(m, sym["EN_KY"])
    kw, kh = m.peek(sym["EN_KW"]), m.peek(sym["EN_KH"])

    def under_her(c, r):                # HZ_UNDER_HER's own question
        return (kh and c * 2 < kx + kw and kx < c * 2 + 4
                and r * 8 < ky + kh and ky < r * 8 + 16)

    pend = {p for p in pending(m, sym)
            if excuse == "all" or (excuse == "her" and under_her(*p))}
    hpend = m.peek(sym["H_PENDING"])
    strip = sym["HUD_STRIP_CELLS"]
    bad = []
    for sr in range(24):
        for sc in range(40):
            if sr == 23 and sc < strip:
                continue
            if sc == 0 and 1 <= sr <= sym["COL_HEAD"] and hpend:
                continue
            wc, wr = wx + sc, wcr + sr
            if (wc & ~1, wr & ~1) in pend:
                continue
            t = mp[(wr // 2) * MAP_W + wc // 2]
            if t >= 240:
                continue
            w_ = (scroll + sr * 40 + sc) & 0x3FF
            for r in range(8):
                a = 0xC000 | (r << 11) | (w_ << 1)
                off = t * 64 + (wc & 1) * 32 + ((wr & 1) * 8 + r) * 2
                if m.peek(a) != tiles[off] or m.peek(a + 1) != tiles[off + 1]:
                    bad.append((wc // 2, wr // 2))
                    break
    return bad


def walk(m, sym, tile, tiles=None, run=False, limit=900, stop=None,
         excuse="her"):
    """RIGHT, and UP whenever she has not moved for eight game frames.
    Returns (bites as (tile, points), frames whose picture was wrong)."""
    if run:
        m.key_down('A')                 # SHIFT: an upper-case letter
    bites, wrong, stuck, was = [], [], 0, -1
    hp = m.peek(sym["PLAYER_HP"])
    for _ in range(limit):
        t = tile_of(m, sym)
        if t >= tile or (stop and stop(m)):
            break
        wx = word(m, sym["KARA_WX"])
        stuck = stuck + 1 if wx == was else 0
        was = wx
        gframe(m, sym, JOY_RIGHT | (JOY_UP if stuck >= 8 else 0))
        if stuck >= 8:
            stuck = 0
        now = m.peek(sym["PLAYER_HP"])
        if now < hp:
            bites.append((t, hp - now))
        hp = now
        if tiles is not None:
            b = wrong_cells(m, sym, tiles, excuse)
            if b:
                wrong.append((t, b[:3]))
    m.joystick(0)
    if run:
        m.key_up('A')
    gframe(m, sym, 0)
    return bites, wrong


def edge_walk(m, sym, tile, tiles, row):
    """walk() to `tile`, with every trap's cell that is at the LEFT edge
    - screen column -1 or 0 - put on the painter's pending list on each
    frame a step right is in flight: between the two sweeps, after the
    camera has asked for the step and before HAZARD_TICK and the passes
    run. `row` is the traps' character row. Returns (frames whose
    picture was wrong, frames a cell was put on the list)."""
    t0, cols = sym["HZ_TABLE"], []
    for k in range(m.peek(sym["HZ_COUNT"])):
        cols.append((word(m, t0 + 8 * k + 2) - sym["MAP_ADDR"]) % MAP_W)
    wrong, made, stuck, was = [], 0, 0, -1
    for _ in range(900):
        t = tile_of(m, sym)
        if t >= tile:
            break
        wx = word(m, sym["KARA_WX"])
        stuck = stuck + 1 if wx == was else 0
        was = wx
        m.joystick(JOY_RIGHT | (JOY_UP if stuck >= 8 else 0))
        if stuck >= 8:
            stuck = 0
        sync(m, sym, 1)
        if m.peek(sym["H_PENDING"]):
            v, n = m.peek(sym["WORLD_X"]), m.peek(sym["HZ_PEND_N"])
            have = set(pending(m, sym))
            for c in cols:
                if 2 * c - v in (-1, 0) and (2 * c, row) not in have \
                        and n < 16:
                    m.poke(sym["HZ_PEND"] + 2 * n, 2 * c)
                    m.poke(sym["HZ_PEND"] + 2 * n + 1, row)
                    n += 1
                    made += 1
            m.poke(sym["HZ_PEND_N"], n)
        sync(m, sym, 0)
        b = wrong_cells(m, sym, tiles, "all")
        if b:
            wrong.append((t, b[:3]))
    m.joystick(0)
    gframe(m, sym, 0)
    return wrong, made


def climb(m, sym, ground, branch7, until):
    """Up two branches: UP under the row-7 one and UP again on it, which
    is test_forest.py's level-6 drive with this level's columns."""
    g_wy, b7_wy = ROW_GROUND * 16 - 64, 7 * 16 - 64
    stuck, last = 0, -1
    for _ in range(1500):
        x, y = word(m, sym["KARA_WX"]), word(m, sym["KARA_WY"])
        stuck = stuck + 1 if x == last else 0
        last = x
        joy = JOY_RIGHT
        if y == g_wy and ground[0] <= x // 4 <= ground[1]:
            joy |= JOY_UP
        elif y == b7_wy and branch7[0] <= x // 4 <= branch7[1]:
            joy |= JOY_UP
        elif stuck > 8:
            joy |= JOY_UP
        gframe(m, sym, joy)
        if until(m):
            break
    m.joystick(0)
    gframe(m, sym, 0)


def interact(m, sym):
    """UP once - a PRESS, which is what the interact pass reads."""
    gframe(m, sym, JOY_UP)
    gframe(m, sym, 0)
    for _ in range(6):
        gframe(m, sym, 0)


def hazards(m, sym):
    """[(record, cell, base, tc)] out of HZ_TABLE."""
    t = sym["HZ_TABLE"]
    return [(word(m, t + 8 * i), word(m, t + 8 * i + 2), m.peek(t + 8 * i + 6),
             m.peek(t + 8 * i + 7)) for i in range(m.peek(sym["HZ_COUNT"]))]


def stand_count(m, sym, frames=200, pattern=None):
    """Game frames in `frames` hardware ones, anchored on a game frame,
    with `pattern(game frame)` on the joystick; bites counted with her
    health topped up so that she lives through it."""
    sync(m, sym, 0)
    f0 = last = m.peek(sym["FRAME_COUNT"])
    n = bites = 0
    for _ in range(frames):
        m.joystick(pattern((last - f0) & 255) if pattern else 0)
        m.run_frames(1)
        fc = m.peek(sym["FRAME_COUNT"])
        n += (fc - last) & 255
        last = fc
        if m.peek(sym["PLAYER_HP"]) < 100:
            bites += 1
            m.poke(sym["PLAYER_HP"], 100)
    m.joystick(0)
    return n, bites


# =====================================================================
# 1. THE BAKE, THE FLAGS AND THE FILE - before any machine
# =====================================================================
def offline(sym):
    print("\n  the bake, out of the artist's own sheets:")
    import cpclib
    from PIL import Image
    from aseprite2spans import game_palette
    pal = game_palette(os.path.join(ROOT, "src", "palette.asm"))
    tiles = open(os.path.join(BUILD, "levels", "level2_forest",
                              "foresttiles.bin"), "rb").read()
    flags = open(os.path.join(BUILD, "tileflags_level2_forest.bin"), "rb").read()

    def frames(stem):
        img = Image.open(os.path.join(ART, stem + ".png")).convert("RGBA")
        fr = json.load(open(os.path.join(ART, stem + ".json")))["frames"]
        fr = fr if isinstance(fr, list) else list(fr.values())
        return img, [f["frame"] for f in fr]

    def pens(img, x, y, w=8, h=16, alpha=False):
        crop = img.crop((x, y, x + w, y + h))
        p = cpclib.quantise(crop, pal)
        if not alpha:
            return p
        a = crop.getchannel("A").load()
        return [[p[j][i] if a[i, j] else None for i in range(w)] for j in range(h)]

    def enc(p):                         # column-major, written out again
        out = bytearray()
        for col in range(2):
            for y in range(16):
                for x in (col * 4, col * 4 + 2):
                    out.append(cpclib.encode_pixels(p[y][x], p[y][x + 1]))
        return bytes(out)

    def over(top, under):
        return [[t if t is not None else u for t, u in zip(a, b)]
                for a, b in zip(top, under)]

    timg, tfr = frames("forest_tiles_cpc_mode0_sheet")
    names = {}
    man = json.load(open(os.path.join(ART, "manifest.json")))
    desc = next(s for s in man["sheets"] if s["name"] == "forest_tiles")["description"]
    for part in desc.split("Frame index:", 1)[1].strip().rstrip(".").split(","):
        i, n = part.strip().split(None, 1)
        names[n.strip()] = int(i)
    band = {n: pens(timg, tfr[names[n]]["x"], tfr[names[n]]["y"])
            for n in ("far_trunks_a", "far_trunks_b", "far_base")}

    l7 = read(open(os.path.join(BUILD, "level_7.lvl"), "rb").read())
    l8 = read(open(os.path.join(BUILD, "level_8.lvl"), "rb").read())
    blob7 = open(os.path.join(BUILD, "level_7.lvl"), "rb").read()

    # ---- the trap: four cels over far_base, at the index the map names
    simg, sfr = frames("forest_spiketrap_cpc_mode0_sheet")
    trap0 = l7["map"][ROW_BASE * MAP_W + 62]
    made = [enc(over(pens(simg, f["x"], f["y"], alpha=True), band["far_base"]))
            for f in sfr]
    got = [tiles[(trap0 + c) * 64:(trap0 + c + 1) * 64] for c in range(TRAP_CELS)]
    check("a trap is its four cels over the undergrowth, consecutive",
          made == got and trap0 >= FOREST_TILES,
          f"tiles {trap0}..{trap0 + 3}, {sum(a == b for a, b in zip(made, got))} "
          f"of 4 re-made here out of the PNG")
    check("... and the three that bite are the three that carry TA_HAZARD",
          [bool(flags[trap0 + c] & TA_HAZARD) for c in range(4)]
          == [False, True, True, True],
          f"flags {[flags[trap0 + c] for c in range(4)]} - the artist's "
          f"'damage on frames 1-3'")

    # ---- the altar: an empty piece and its lit one, over the bands
    aimg, afr = frames("forest_altar_cpc_mode0_sheet")
    ok_pieces = adv_ok = 0
    for col in range(3):
        for row in range(2):
            x, r = 57 - 1 + col, ROW_GROUND - 2 + row
            e = l7["map"][r * MAP_W + x]
            empty = pens(aimg, afr[0]["x"] + col * 8, afr[0]["y"] + row * 16,
                         alpha=True)
            lit = pens(aimg, afr[3]["x"] + col * 8, afr[3]["y"] + row * 16,
                       alpha=True)
            # whichever band it stands over: the test does not assume the
            # generator's parity rule, it asks which one makes the bytes
            for under in band.values():
                if (enc(over(empty, under)) == tiles[e * 64:(e + 1) * 64]
                        and enc(over(lit, under)) == tiles[(e + 1) * 64:(e + 2) * 64]):
                    ok_pieces += 1
                    break
            adv_ok += (flags[e] & TA_ADVANCE and not flags[e + 1] & TA_ADVANCE)
    check("an altar is six pieces, each an empty tile and its lit one",
          ok_pieces == 6, f"{ok_pieces} of 6 re-made here, empty at index e "
          f"and lit at e + 1 - which is the whole contract with PLACE_STATUE")
    check("... and only the empty ones carry TA_ADVANCE", adv_ok == 6,
          f"{adv_ok} of 6 - so a lit altar cannot be lit again, and a cell "
          f"that is not an altar's is left alone")

    # ---- the file: records, cells and links
    def recs(lvl):
        e = lvl["entity_bytes"]
        return [e[i:i + 8] for i in range(0, len(e), 8)]

    def links(blob):
        n = blob[11]
        off = blob[17] | blob[18] << 8
        return [tuple(blob[off + 4 * i:off + 4 * i + 4]) for i in range(n)]

    r7 = recs(l7)
    traps7 = [i for i, r in enumerate(r7) if r[0] == EK_HAZARD]
    alt7 = [i for i, r in enumerate(r7) if r[0] == EK_RECEPTACLE]
    on_cell = all(l7["map"][((r7[i][3] | r7[i][4] << 8) // 16 - 1) * MAP_W
                            + (r7[i][1] | r7[i][2] << 8) // 8] == trap0
                  for i in traps7)
    check("level 7: eight trap records, each on a trap's cel 0",
          len(traps7) == 8 and on_cell, f"records {traps7}")
    lk7 = links(blob7)
    check("... and eight Disables links, every one from the altar",
          sorted(t for k, s, t, p in lk7 if k == 1 and s == alt7[0]) == traps7,
          f"{len(lk7)} links from record {alt7}")
    blob8 = open(os.path.join(BUILD, "level_8.lvl"), "rb").read()
    r8 = recs(l8)
    alt8 = [i for i, r in enumerate(r8) if r[0] == EK_RECEPTACLE]
    lk8 = links(blob8)
    fields = {a: sorted((r8[t][1] | r8[t][2] << 8) // 8
                        for k, src, t, _ in lk8 if src == a and k == 1)
              for a in alt8}
    check("level 8: two altars, and each one stops its own field",
          len(alt8) == 2 and fields[alt8[0]] == [32, 34, 36, 38]
          and fields[alt8[1]] == [78, 80, 82, 84],
          f"{ {a: fields[a] for a in alt8} }")

    # ---- the editor's lists, against the engine's
    hz = re.findall(r"^\s+(\w+) = (\d+),",
                    open(os.path.join(EDITOR, "HazardKind.cs")).read(), re.M)
    lk = dict(re.findall(r"^\s+(\w+) = (\d+),",
                         open(os.path.join(EDITOR, "LinkKind.cs")).read(), re.M))
    tf = dict(re.findall(r"^\s+(\w+) = (\d+),",
                         open(os.path.join(EDITOR, "TileFlags.cs")).read(), re.M))
    check("the editor's HazardKind, LinkKind and TileFlags are the engine's",
          len(hz) == sym["HZ_KINDS"] and int(lk["Disables"]) == sym["LK_DISABLES"]
          and int(tf["Advances"]) == sym["TA_ADVANCE"],
          f"HazardKind {len(hz)} against HZ_KINDS {sym['HZ_KINDS']}, Disables "
          f"{lk['Disables']} against LK_DISABLES {sym['LK_DISABLES']}, Advances "
          f"{tf['Advances']} against TA_ADVANCE {sym['TA_ADVANCE']}")
    return tiles, trap0


# =====================================================================
# 2. LEVEL 7 ON THE MACHINE
# =====================================================================
def level7(sym, tiles, trap0):
    print("\n  level 7, through level 6's cave:")
    m6, _ = to_level(sym, 6)
    m, took = to_level(sym, 7, m6)
    check("she arrives in level 7 out of level 6's door",
          m.peek(sym["LEVEL_OK"]) == 1 and m.peek(sym["LEVEL_ENV"]) == 1,
          f"{took} hardware frames, LEVEL_ENV {m.peek(sym['LEVEL_ENV'])} - one "
          f"sector and no art, levels 5-8 being one environment")
    hz = hazards(m, sym)
    check("HAZARD_SPAWN took all eight traps, each on its own cel 0",
          len(hz) == 8 and all(b == trap0 for _, _, b, _ in hz),
          f"HZ_COUNT {len(hz)}, base {sorted({b for _, _, b, _ in hz})}")

    # ---- the cycle, read off the map byte
    cell = hz[0][1]
    seq = []
    for _ in range(29):
        seq.append([m.peek(c) - trap0 for _, c, _, _ in hz])
        gframe(m, sym, 0)
    runs, cur, n = [], seq[0][0], 0
    for s in seq:
        if s[0] == cur:
            n += 1
        else:
            runs.append((cur, n))
            cur, n = s[0], 1
    dur = [m.peek(sym["HZ_DUR"] + i) for i in range(4)]
    inner = runs[1:-1]
    check("the map goes round the cycle HZ_DUR says",
          all(n == dur[c] for c, n in inner) and len(inner) >= 4,
          f"cels {[c for c, _ in runs]} held {[n for _, n in runs]} game frames "
          f"against HZ_DUR {dur} - 200, 70, 200 and 70 ms at 40 a frame")
    check("... and all eight in phase, so the field breathes",
          all(len(set(s)) == 1 for s in seq), f"cell {hex(cell)} and its seven")

    # ---- standing in it, and the control
    walk(m, sym, 66)
    m.poke(sym["PLAYER_HP"], 100)
    frames, bites = stand_count(m, sym)
    check("standing in the field she is bitten once a cycle",
          frames == 100 and 6 <= bites <= 8,
          f"{bites} bites in {frames} game frames against a 14-frame cycle - "
          f"an EDGE, the frame a trap she is in comes up (8.12)")
    mc, _ = to_level(sym, 7, to_level(sym, 6)[0])
    mc.poke(sym["HAZARD_TICK"], 0xC9)
    walk(mc, sym, 66)
    mc.poke(sym["PLAYER_HP"], 100)
    _, cbites = stand_count(mc, sym)
    check("... and with HAZARD_TICK poked to RET, never",
          cbites == 0, f"{cbites} bites: the traps stay on cel 0, which is "
          f"what says the bite is the cycle and not the tile alone")

    # ---- crossing it without the idol, and the picture every frame
    print("\n  across the field without the idol:")
    mw, _ = to_level(sym, 7, to_level(sym, 6)[0])
    walk(mw, sym, 58)
    mw.poke(sym["PLAYER_HP"], 100)
    wb, wrong = walk(mw, sym, 80, tiles)
    check("walking across costs her", len(wb) >= 3,
          f"{len(wb)} bites of 16 at tiles {[t for t, _ in wb]} - HP 100 -> "
          f"{mw.peek(sym['PLAYER_HP'])}")
    check("... and the picture is the map on every frame of it", not wrong,
          f"{len(wrong)} frames with a wrong cell"
          + (f", first {wrong[0]}" if wrong else ""))
    mr, _ = to_level(sym, 7, to_level(sym, 6)[0])
    walk(mr, sym, 58)
    mr.poke(sym["PLAYER_HP"], 100)
    rb, _ = walk(mr, sym, 80, run=True)
    check("running across costs her less, and still costs her", 1 <= len(rb) < len(wb),
          f"{len(rb)} bites at a run against {len(wb)} at a walk")

    # ---- the controls on the picture
    for name, poke in (("HAZARD_PAINT_B poked to RET",
                        [("HAZARD_PAINT_B", 0xC9)]
                        + ([("HAZARD_PAINT_E", 0xC9)] if "HAZARD_PAINT_E" in sym
                           else [])),
                       ("HZ_UNDER_HER told she is never there",
                        [("HZ_UNDER_HER", 0xB7), ("HZ_UNDER_HER", 0xC9, 1)])):
        mx, _ = to_level(sym, 7, to_level(sym, 6)[0])
        for p in poke:
            mx.poke(sym[p[0]] + (p[2] if len(p) > 2 else 0), p[1])
        walk(mx, sym, 58)
        mx.poke(sym["PLAYER_HP"], 100)
        _, wx = walk(mx, sym, 80, tiles)
        for _ in range(20):
            gframe(mx, sym, 0)
        left = wrong_cells(mx, sym, tiles)
        check(f"... with {name}, it is not", wx or left,
              f"{len(wx)} frames with a wrong cell on the way, {len(left)} "
              f"cells wrong after standing still"
              + (f", first {(wx or [left])[0]}" if (wx or left) else ""))

    # ---- what HAZARD_PAINT_C is for: the cells under her feet
    under = {}
    for name, poke in (("as built", None), ("C poked to RET", "HAZARD_PAINT_C")):
        mx, _ = to_level(sym, 7, to_level(sym, 6)[0])
        if poke:
            mx.poke(sym[poke], 0xC9)
        walk(mx, sym, 58)
        mx.poke(sym["PLAYER_HP"], 100)
        _, wx = walk(mx, sym, 80, tiles, excuse="none")
        under[name] = len(wx)
    check("HAZARD_PAINT_C paints the cell she stands in at the end of the "
          "second sweep", under["as built"] * 2 < under["C poked to RET"],
          f"walking across, the cell under her a cel behind the map on "
          f"{under['as built']} game frames, {under['C poked to RET']} with "
          f"HAZARD_PAINT_C poked to RET - no cell excused but the incoming "
          f"column's")

    # ---- and the words it must keep out of. A trap on row 8 is below the
    # head's rows, so H_TAIL paints over anything C left there; lifted to
    # map row 3 it is inside them, and with B off C gets the edge cells.
    # The model excuses EVERY pending cell, so what it can see is a cell
    # painted where it must not be.
    #
    # AND THE CELL AT THE EDGE IS PUT ON THE LIST, NOT WAITED FOR. What
    # the guard is for is a trap's cell at column -1 or 0 still on C's
    # list on a frame a step right is in flight. This control used to
    # get one for free, because C was late: it spent 1,868 T painting
    # every cell wholly off the screen, and the eighth trap's waited for
    # the next frame. Those cells are off the list now (CLAUDE.md 8.23),
    # C is on time, and the same walk without the guard was 0 frames
    # wrong - a control that had gone blind, not a guard that was not
    # needed: traced, the frame it failed on was C painting the cell at
    # column -1 with H_PENDING set.
    seen = {}
    for name, guard in (("with the guard", True), ("without it", False)):
        mx, _ = to_level(sym, 7, to_level(sym, 6)[0])
        mx.poke(sym["HAZARD_PAINT_B"], 0xC9)
        if "HAZARD_PAINT_E" in sym:         # ... and the pass before the
            mx.poke(sym["HAZARD_PAINT_E"], 0xC9)    # strip, or it paints them
        t = sym["HZ_TABLE"]
        for k in range(mx.peek(sym["HZ_COUNT"])):
            e = t + 8 * k
            cell = word(mx, e + 2)
            col = (cell - sym["MAP_ADDR"]) % MAP_W
            base = mx.peek(e + 6)
            new_cell = sym["MAP_ADDR"] + 3 * MAP_W + col
            mx.poke(new_cell, mx.peek(cell))
            mx.poke(e + 2, new_cell & 255)
            mx.poke(e + 3, new_cell >> 8)
            mx.poke(e + 5, 3 * 2)
        if not guard:
            # the two immediates are NAMED, because a search through the
            # painter's code for `cp 2` is a control that breaks the day
            # anything is put in front of it (CLAUDE.md 10)
            assert mx.peek(sym["HZ_GUARD_L"]) == 2
            assert mx.peek(sym["HZ_GUARD_R"]) == 39
            mx.poke(sym["HZ_GUARD_L"], 0)
            mx.poke(sym["HZ_GUARD_R"], 255)
        walk(mx, sym, 50)
        mx.poke(sym["PLAYER_HP"], 100)
        wx, made = edge_walk(mx, sym, 96, tiles, 6)
        seen[name] = wx
        seen[name + " made"] = made
    check("HAZARD_PAINT_C keeps out of the incoming column's words",
          not seen["with the guard"] and seen["without it"],
          f"traps lifted into the head's rows: {len(seen['with the guard'])} "
          f"frames with a cell painted where it must not be, "
          f"{len(seen['without it'])} without the guard, with a cell at "
          f"the edge put on the list on {seen['without it made']} frames a "
          f"step was in flight"
          + (f", first {seen['without it'][0]}" if seen["without it"] else ""))

    # ---- the lock, and the rule that holds it
    print("\n  the frame:")
    for label, run, pattern, nop in (
            ("running across the field", True, None, False),
            ("standing in it, jumping and firing", False,
             lambda g: (JOY_UP if g % 10 == 0 else 0) | (JOY_FIRE if g % 6 < 2 else 0),
             False),
            # THE RUN WITH THE GUN, because that is the path the rule is
            # for: 800 T of room in its first sweep (CLAUDE.md 9). Once the
            # paint was 4,100 T a cell (8.18), a plain run had room for one
            # in front of her draw and this control, run there, was blind.
            ("running and firing across it, the A paint allowed to run",
             True, lambda g: JOY_RIGHT | (JOY_FIRE if g % 6 < 2 else 0), True)):
        ml, _ = to_level(sym, 7, to_level(sym, 6)[0])
        if nop:
            a = sym["HAZARD_PAINT_A"] + 10
            assert ml.peek(a) == 0xC0, "HAZARD_PAINT_A's `ret nz` moved"
            ml.poke(a, 0x00)
            # ... AND C OFF, because B and the pass before the strip now
            # paint every cell she is not standing in (CLAUDE.md 8.18):
            # without this A has nothing to paint, the run cannot drop a
            # frame, and the control is blind rather than the rule wrong.
            # The cells under her are A's then, in front of her draw.
            ml.poke(sym["HAZARD_PAINT_C"], 0xC9)
        walk(ml, sym, 58 if run else 66)
        ml.poke(sym["PLAYER_HP"], 100)
        if run:
            ml.key_down('A')
            n, _ = stand_count(ml, sym, pattern=pattern or (lambda g: JOY_RIGHT))
            ml.key_up('A')
        else:
            n, _ = stand_count(ml, sym, pattern=pattern)
        expect = (n < 100) if nop else (n == 100)
        check(f"{label}: {'it drops' if nop else 'the 25 Hz lock'}", expect,
              f"{n} game frames in 200 hardware"
              + (" - a cell is ~4,100 T in front of her draw and the run with "
                 "the gun has 800 (CLAUDE.md 9), which is why it waits for her "
                 "to stop" if nop else ""))

    # ---- the whole of it: the idol, the altar, the field, the key
    print("\n  and with the idol:")
    md, _ = to_level(sym, 7, to_level(sym, 6)[0])
    md.poke(sym["PLAYER_HP"], 100)
    climb(md, sym, (20, 24), (23, 26), lambda m: m.peek(sym["STATUES_HELD"]))
    check("she climbs two branches for the idol", md.peek(sym["STATUES_HELD"]) == 1,
          f"STATUES_HELD {md.peek(sym['STATUES_HELD'])}")
    walk(md, sym, 57)
    alt = [(r, c) for r in (7, 8) for c in (56, 57, 58)]
    before = [md.peek(sym["MAP_ADDR"] + r * MAP_W + c) for r, c in alt]
    interact(md, sym)
    after = [md.peek(sym["MAP_ADDR"] + r * MAP_W + c) for r, c in alt]
    hz = hazards(md, sym)
    check("UP at the altar takes the idol and lights it",
          md.peek(sym["STATUES_HELD"]) == 0 and after == [b + 1 for b in before],
          f"cells {before} -> {after}")
    check("... and every trap it Disables is marked down",
          all(md.peek(r + 5) & EF_TAKEN for r, _, _, _ in hz),
          f"{sum(1 for r, _, _, _ in hz if md.peek(r + 5) & EF_TAKEN)} of {len(hz)} "
          f"records EF_TAKEN")
    still = []
    for _ in range(30):
        gframe(md, sym, 0)
        still.append({md.peek(c) - trap0 for _, c, _, _ in hazards(md, sym)})
    check("... and the field goes down and stays down",
          all(s == {0} for s in still[2:]), f"cels over 30 frames: {still[-1]}")
    db, dwrong = walk(md, sym, 80, tiles)
    check("crossing it now costs nothing", not db,
          f"{len(db)} bites, HP {md.peek(sym['PLAYER_HP'])}")
    check("... and the lit altar and the sleeping field are the picture",
          not dwrong, f"{len(dwrong)} frames with a wrong cell")
    climb(md, sym, (94, 97), (200, 200), lambda m: m.peek(sym["KEYS_COUNT"]))
    check("she takes the key past the field", md.peek(sym["KEYS_COUNT"]) == 1)

    # ---- the control: the links
    print("\n  and with the level's links taken away:")
    mk, _ = to_level(sym, 7, to_level(sym, 6)[0])
    mk.poke(sym["LEVEL_LVL"] + sym["LVL_LINKS"], 0)
    mk.poke(sym["STATUES_HELD"], 1)
    walk(mk, sym, 57)
    b2 = [mk.peek(sym["MAP_ADDR"] + r * MAP_W + c) for r, c in alt]
    interact(mk, sym)
    a2 = [mk.peek(sym["MAP_ADDR"] + r * MAP_W + c) for r, c in alt]
    mk.poke(sym["PLAYER_HP"], 100)
    kb, _ = walk(mk, sym, 80)
    check("the altar still lights and the field still bites",
          a2 == [b + 1 for b in b2] and len(kb) >= 3,
          f"{len(kb)} bites - so it is the LINK that stops a trap, and not "
          f"the altar being lit")

    # ---- the restart puts it all back
    print("\n  and a restart:")
    md.poke(sym["PLAYER_HP"], 0)
    for _ in range(600):
        md.run_frames(1)
        if md.peek(sym["GAME_STATE"]) == GS_PLAY and md.peek(sym["PLAYER_HP"]) == 100:
            break
    md.run_frames(20)
    hz = hazards(md, sym)
    back = [md.peek(sym["MAP_ADDR"] + r * MAP_W + c) for r, c in alt]
    check("dying puts the altar out and the traps back up",
          back == before and not any(md.peek(r + 5) & EF_TAKEN for r, _, _, _ in hz)
          and len(hz) == 8,
          f"altar {back}, {sum(1 for r, _, _, _ in hz if md.peek(r + 5) & EF_TAKEN)} "
          f"traps down - all of it out of the pristine LEVEL_IMAGE (8.1)")
    return md


# =====================================================================
# 3. LEVEL 8: TWO ALTARS, AND THE WAY OUT OF THE FOREST
# =====================================================================
def level8(sym, tiles, trap0):
    print("\n  level 8, the forest's last:")
    m7, _ = to_level(sym, 7, to_level(sym, 6)[0])
    m, took = to_level(sym, 8, m7)
    check("she arrives in level 8 out of level 7's door",
          m.peek(sym["LEVEL_OK"]) == 1 and m.peek(sym["HZ_COUNT"]) == 8,
          f"{took} hardware frames, HZ_COUNT {m.peek(sym['HZ_COUNT'])}")
    m.poke(sym["PLAYER_HP"], 100)
    climb(m, sym, (12, 16), (15, 18), lambda m: m.peek(sym["STATUES_HELD"]))
    walk(m, sym, 27)
    interact(m, sym)
    hz = hazards(m, sym)

    def field(lo, hi):
        return [m.peek(r + 5) & EF_TAKEN for r, c, _, _ in hz
                if lo <= (c - sym["MAP_ADDR"]) % MAP_W <= hi]
    a_down, b_down = field(32, 38), field(78, 84)
    check("the first idol on the first altar puts the first field down",
          all(a_down) and len(a_down) == 4, f"{a_down}")
    check("... and leaves the second one breathing", not any(b_down) and len(b_down) == 4,
          f"{b_down} - a Disables link names its source")
    walk(m, sym, 58)
    climb(m, sym, (58, 62), (61, 64), lambda m: m.peek(sym["STATUES_HELD"]))
    walk(m, sym, 73)
    interact(m, sym)
    hz = hazards(m, sym)
    check("the second idol on the second altar puts the second down",
          all(field(78, 84)), f"{field(78, 84)}")
    hp = m.peek(sym["PLAYER_HP"])
    b, wrong = walk(m, sym, 87, tiles)
    check("... and the way through is free, and the picture right",
          not b and not wrong, f"{len(b)} bites, {len(wrong)} wrong frames, HP {hp}")
    climb(m, sym, (87, 90), (200, 200), lambda m: m.peek(sym["KEYS_COUNT"]))
    walk(m, sym, 119)
    for _ in range(3):
        interact(m, sym)
        if m.peek(sym["GAME_STATE"]) == GS_CLEAR:
            break
    on = None
    for f in range(900):
        m.run_frames(1)
        if m.peek(sym["GAME_STATE"]) == GS_PLAY and m.peek(sym["LEVEL_CUR"]) == 8:
            on = f + 1
            break
    m.run_frames(10)
    check("and the cave in the mountain leads out of the forest, to level 9",
          on is not None and m.peek(sym["LEVEL_ENV"]) == 2
          and m.peek(sym["LEVEL_OK"]) == 1,
          f"after {on} hardware frames, LEVEL_ENV {m.peek(sym['LEVEL_ENV'])} - "
          f"the cave's art, an environment away (CLAUDE.md 8.1)")


def main():
    sym = symbols()
    tiles, trap0 = offline(sym)
    level7(sym, tiles, trap0)
    level8(sym, tiles, trap0)
    print()
    print("ALL CHECKS PASSED" if not fails else f"{len(fails)} FAILED: {fails}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
