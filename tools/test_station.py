#!/usr/bin/env python3
"""Levels 21 to 24 on a 6128: the space station - its lasers, its
keycard doors, and the computer the game ends at. CLAUDE.md 8.23.

A LASER IS A TRAP (CLAUDE.md 8.17), the fourth kind: a column of four
cells from an emitter in a bulkhead's ceiling to one in the floor, whose
tile goes round off, on, the flicker, on - 20, 10, 10 and 10 game
frames, read here off the map byte. The on cels carry TA_HAZARD, so the
bite is HAZARD_HURT's; she cannot jump it, only time it.

A KEYCARD DOOR IS AN ALTAR. The reader beside it is a receptacle that
takes a key (PLACE_STATUE's counter is its p0's now), and HZ_SATISFIED
moves on every cell of the 3 x 5 around it that carries TA_ADVANCE: the
reader to its lit picture, the door's four shut tiles to its open ones.
So an inner door opens and the level goes on; the way out is an EK_DOOR
as everywhere else. Every expectation is read out of something other
than the code under test: the composites out of the artist's sheets,
the cycle off the map byte, the door off TILE_ATTR, the picture against
the map on every frame of a route driven from the joystick.
"""
import json
import os
import re
import sys

sys.path.insert(0, "/home/vasilhs/cpcemu")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bench import symbols, sync                                # noqa: E402
from make_level import read                                    # noqa: E402
import test_forest7 as F                                       # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
BUILD = os.path.join(ROOT, "build")
ART = os.path.join(ROOT, "assets", "sprites", "level6_station")
EDITOR = os.path.join(ROOT, "editor", "src", "CpcLevelEditor.Domain")

JOY_UP, JOY_RIGHT = 0x01, 0x08
GS_PLAY, GS_DEAD, GS_CLEAR = 0, 1, 2
EK_PICKUP, EK_HAZARD, EK_DOOR, EK_RECEPTACLE = 4, 5, 6, 7
EF_TAKEN = 2
MAP_W, ROW_FLOOR = 128, 9
STAND_WY = ROW_FLOOR * 16 - 64
FIRST, LAST = 21, 24
TA_SOLID, TA_HAZARD, TA_ADVANCE = 1, 4, 128

sym = symbols()
TILES = open(os.path.join(BUILD, "levels", "level6_station",
                          "stationtiles.bin"), "rb").read()
FLAGS = open(os.path.join(BUILD, "tileflags_level6_station.bin"), "rb").read()
fails = []
check = F.check
F.fails = fails


def lvl(n):
    return read(open(os.path.join(BUILD, f"level_{n}.lvl"), "rb").read())


def recs(n):
    e = lvl(n)["entity_bytes"]
    return [e[i:i + 8] for i in range(0, len(e), 8)]


def x_of(r):
    return (r[1] | r[2] << 8) // 8


def w(m, a):
    return F.word(m, sym[a])


def b(m, a):
    return m.peek(sym[a])


def cell(m, x, r):
    return m.peek(sym["MAP_ADDR"] + r * MAP_W + x)


def put(m, wx, wy=STAND_WY):
    m.poke(sym["KARA_WX"], wx & 255)
    m.poke(sym["KARA_WX"] + 1, wx >> 8)
    m.poke(sym["KARA_WY"], wy & 255)
    m.poke(sym["KARA_WY"] + 1, wy >> 8)
    for a in ("KARA_VY", "KARA_FELL", "KARA_COYOTE"):
        m.poke(sym[a], 0)
    m.poke(sym["KARA_GROUND"], 1)


def lasers(n):
    return [x_of(r) for r in recs(n) if r[0] == EK_HAZARD]


def laser_base(n):
    """Cel 0's tile, out of the pristine map: the beam's top cell."""
    c = lasers(n)[0]
    return lvl(n)["map"][5 * MAP_W + c]


# =====================================================================
# 1. THE BAKE, THE FLAGS AND THE FILES - before any machine
# =====================================================================
def offline():
    print("\nTHE BAKE AND THE FLAGS, out of the artist's own sheets")
    import cpclib
    from PIL import Image
    from aseprite2spans import game_palette
    pal = game_palette(os.path.join(ROOT, "src", "palette.asm"))

    def sheet(stem):
        img = Image.open(os.path.join(ART, stem + ".png")).convert("RGBA")
        fr = json.load(open(os.path.join(ART, stem + ".json")))["frames"]
        fr = fr if isinstance(fr, list) else list(fr.values())
        return img, [f["frame"] for f in fr]

    def pens(img, f, dx=0, dy=0):
        return cpclib.quantise(img.crop((f["x"] + dx, f["y"] + dy,
                                         f["x"] + dx + 8, f["y"] + dy + 16)),
                               pal)

    def decode(i):
        t = TILES[i * 64:(i + 1) * 64]
        p = [[0] * 8 for _ in range(16)]
        for col in range(2):
            for y in range(16):
                for k in range(2):
                    l, r = cpclib.decode_byte(t[col * 32 + y * 2 + k])
                    p[y][col * 4 + k * 2], p[y][col * 4 + k * 2 + 1] = l, r
        return p

    timg, tfr = sheet("station_tiles_cpc_mode0_sheet")
    WALL = 7                                # 'wall', by the sheet's own order
    wall = pens(timg, tfr[WALL])
    limg, lfr = sheet("station_laser_cpc_mode0_sheet")
    base = laser_base(FIRST)
    bad = opaque = 0
    for cel, frame in ((0, 5), (1, 3), (2, 4), (3, 3)):
        over = pens(limg, lfr[frame])
        got = decode(base + cel)
        for y in range(16):
            for x in range(8):
                want = over[y][x] if over[y][x] else wall[y][x]
                bad += got[y][x] != want
                opaque += bool(over[y][x])
    check("the laser's four cels are the artist's beam over the wall",
          bad == 0 and opaque > 0, f"{bad} of 512 pixels wrong, {opaque} of "
          f"them the beam's")
    check("... cel 0 is off and harmless, cels 1 to 3 bite",
          FLAGS[base] & TA_HAZARD == 0
          and all(FLAGS[base + c] & TA_HAZARD for c in (1, 2, 3)),
          f"flags {[FLAGS[base + c] for c in range(4)]}")
    # every laser of every level is the same four tiles, and its column
    # is four cells of cel 0 in the pristine map
    ok = True
    for n in range(FIRST, LAST + 1):
        mp = lvl(n)["map"]
        for c in lasers(n):
            ok &= all(mp[r * MAP_W + c] == base for r in range(5, 9))
    check("every laser in the station is one column of cel 0, rows 5 to 8",
          ok)

    # the doors: shut tiles carry SOLID and ADVANCE, their open picture
    # is the next index and carries no SOLID, the lintel excepted
    rs = recs(FIRST)
    rec = next(r for r in rs if r[0] == EK_RECEPTACLE)
    d = x_of(rec) + 1
    mp = lvl(FIRST)["map"]
    shut = [mp[r * MAP_W + d] for r in range(4, 9)]
    okd = all(FLAGS[t] & (TA_SOLID | TA_ADVANCE) == TA_SOLID | TA_ADVANCE
              for t in shut) and all(not FLAGS[t + 1] & TA_SOLID
                                     for t in shut[1:])
    reader = mp[7 * MAP_W + d - 1]
    check("a door is shut tiles that are SOLID and advance onto open ones "
          "that are not, and its reader advances onto its lit picture",
          okd and FLAGS[reader] & TA_ADVANCE and rec[6] == 0 and rec[7] == 1,
          f"shut {shut} flags {[FLAGS[t] for t in shut]}, open "
          f"{[FLAGS[t + 1] for t in shut]}, reader {FLAGS[reader]}")
    # ... and the open pictures are the artist's open door
    names = ["door_head_open", "door_open_mid", "door_open_mid",
             "door_open_bot"]
    idx = {"door_head_open": 26, "door_open_mid": 27, "door_open_bot": 28}
    badd = sum(decode(t + 1) != decode(idx[nm])
               for t, nm in zip([shut[0], shut[1], shut[2], shut[4]], names))
    check("... and the open tiles are the sheet's open door", badd == 0,
          f"{badd} of 4 differ")

    for n in range(FIRST, LAST + 1):
        ev = sorted([(x_of(r), "key") for r in recs(n)
                     if r[0] == EK_PICKUP and r[6] == 0]
                    + [(x_of(r), "door") for r in recs(n)
                       if r[0] in (EK_RECEPTACLE, EK_DOOR)])
        held, low = 0, 99
        for x, what in ev:
            held += 1 if what == "key" else -1
            low = min(low, held)
        check(f"level {n}: a keycard before every door she meets",
              low >= 0, f"{ev}")

    src = open(os.path.join(EDITOR, "HazardKind.cs")).read()
    q = re.search(r"Laser\s*=\s*(\d+)", src)
    check("the editor's HazardKind.Laser is the engine's HZ_LASER",
          q and int(q.group(1)) == sym["HZ_LASER"],
          f"{q.group(1) if q else None} against {sym['HZ_LASER']}")


# =====================================================================
# 2. THE LASER
# =====================================================================
def slot_of(m, col):
    """The HZ_TABLE slot whose cell is the beam's top at `col`."""
    t = sym["HZ_TABLE"]
    for i in range(m.peek(sym["HZ_COUNT"])):
        if m.peek(t + 8 * i + 4) == col * 2 and m.peek(t + 8 * i + 5) == 10:
            return t + 8 * i
    return None


def laser():
    print("\nTHE LASER: its cycle off the map byte, and its bite")
    m, took = F.to_level(sym, FIRST)
    check("into the station out of the shuttle: an environment away",
          took is not None and b(m, "LEVEL_ENV") == 5 and b(m, "LEVEL_OK")
          and b(m, "LEVEL_HAZARD"), f"{took} hardware frames, LEVEL_ENV "
          f"{b(m, 'LEVEL_ENV')}, LEVEL_HAZARD {b(m, 'LEVEL_HAZARD')}, "
          f"{b(m, 'HZ_COUNT')} traps")
    c = lasers(FIRST)[0]
    base = laser_base(FIRST)
    F.walk(m, sym, c - 4)
    seen, runs, last, n = [], [], None, 0
    for _ in range(160):
        F.gframe(m, sym, 0)
        cels = {cell(m, c, r) - base for r in range(5, 9)}
        seen.append(cels)
        cel = min(cels)
        if cel == last:
            n += 1
        else:
            if last is not None:
                runs.append((last, n))
            last, n = cel, 1
    whole = all(len(s) == 1 for s in seen)
    durs = {}
    for cel, k in runs[1:]:
        durs.setdefault(cel, set()).add(k)
    check("its four cells change together, round 20, 10, 10 and 10 game "
          "frames", whole and durs == {0: {20}, 1: {10}, 2: {10}, 3: {10}},
          f"{durs}, all four together on every frame: {whole}")

    # THE BITE: standing in the beam for a whole cycle
    put(m, c * 4 - 1)
    hp0 = b(m, "PLAYER_HP")
    for _ in range(50):
        F.gframe(m, sym, 0)
    bitten = hp0 - b(m, "PLAYER_HP")
    c2, _ = F.to_level(sym, FIRST)
    c2.poke(sym["HAZARD_TICK"], 0xC9)
    F.walk(c2, sym, c - 4)
    put(c2, c * 4 - 1)
    for _ in range(50):
        F.gframe(c2, sym, 0)
    check("standing in it for a cycle she is bitten once, and with "
          "HAZARD_TICK poked to RET never", bitten == 16
          and b(c2, "PLAYER_HP") == 100,
          f"{bitten} points; with the control {100 - b(c2, 'PLAYER_HP')}")


# =====================================================================
# 3. THE KEYCARD DOOR
# =====================================================================
def door():
    print("\nTHE DOOR: a reader that takes a keycard, and a door it opens")

    def at_reader(rows=None):
        m, _ = F.to_level(sym, FIRST)
        if rows is not None:
            m.poke(sym["HZ_ADV_LIMIT"], rows)
        rec = next(r for r in recs(FIRST) if r[0] == EK_RECEPTACLE)
        d = x_of(rec) + 1
        F.walk(m, sym, d - 6)
        put(m, d * 4 - 6)
        for _ in range(30):
            F.gframe(m, sym, 0)
        return m, d

    m, d = at_reader()
    shut = [cell(m, d, r) for r in range(4, 9)]
    m.poke(sym["KEYS_COUNT"], 0)
    F.interact(m, sym)
    still = [cell(m, d, r) for r in range(4, 9)]
    m.poke(sym["KEYS_COUNT"], 1)
    F.interact(m, sym)
    opened = [cell(m, d, r) for r in range(4, 9)]
    check("without a keycard the reader takes nothing and the door stays "
          "shut; with one it takes it and all five tiles open",
          still == shut and opened == [t + 1 for t in shut]
          and b(m, "KEYS_COUNT") == 0,
          f"shut {shut}, after a bare UP {still}, with a key {opened}, keys "
          f"left {b(m, 'KEYS_COUNT')}")
    for _ in range(40):
        F.gframe(m, sym, JOY_RIGHT)
    check("... and she walks through it", (w(m, "KARA_WX") + 3) // 4 > d + 1,
          f"tile {(w(m, 'KARA_WX') + 3) // 4} against the door at {d}")
    # THE CONTROL: the receptacle's area two rows tall again, the altar's
    # own size. The lower two cells open and the door is still a wall.
    c, d = at_reader(rows=2)
    c.poke(sym["KEYS_COUNT"], 1)
    F.interact(c, sym)
    part = [cell(c, d, r) for r in range(4, 9)]
    for _ in range(40):
        F.gframe(c, sym, JOY_RIGHT)
    check("... and with the area two rows tall, as the altar's was, the top "
          "of the door stays shut and so does the way",
          part[3:] == [t + 1 for t in shut[3:]] and part[:3] == shut[:3]
          and (w(c, "KARA_WX") + 3) // 4 <= d,
          f"{part}, she is at tile {(w(c, 'KARA_WX') + 3) // 4}")


# =====================================================================
# 4. THE ROUTE - from the joystick, 21 to 24
# =====================================================================
def drive(m, n, log):
    """One level, start to way out. RIGHT; hold before a laser until it
    has just gone off and run through it; UP under a catwalk with a
    keycard on it; UP at a reader with a key; UP at the way out."""
    rs = recs(n)
    keys = sorted((x_of(r), (r[3] | r[4] << 8) // 16) for r in rs
                  if r[0] == EK_PICKUP and r[6] == 0)
    readers = [x_of(r) for r in rs if r[0] == EK_RECEPTACLE]
    out = next(x_of(r) for r in rs if r[0] == EK_DOOR)
    beams = lasers(n)
    stuck, was, prev_up, wrong, opened = 0, -1, False, 0, set()
    for f in range(3000):
        if b(m, "GAME_STATE") != GS_PLAY:
            break
        wx, wy = w(m, "KARA_WX"), w(m, "KARA_WY")
        stuck = stuck + 1 if wx == was else 0
        was = wx
        left, right = wx // 4, (wx + 5) // 4
        joy, run, want = JOY_RIGHT, False, False
        # a laser ahead: wait for it to go off, then run
        for c in beams:
            if right < c and c - right <= 3:
                s = slot_of(m, c)
                tc = m.peek(s + 7) if s else 0
                if not (tc & 3 == 0 and tc >> 2 >= 12):
                    joy = 0
                run = True
            elif left <= c <= right:
                run = True
        # a keycard on a catwalk over her
        for kx, kr in keys:
            if kr < ROW_FLOOR and left <= kx <= right + 1 \
                    and wy == STAND_WY and b(m, "KEYS_COUNT") < 3:
                if any(cell(m, kx, kr) == t for t in (cell(m, kx, kr),)):
                    want = True
        if wy < STAND_WY and b(m, "KARA_GROUND"):
            # on a catwalk: on to the key, and off the far end
            pass
        # a reader she has a key for
        for rx in readers:
            if rx not in opened and right >= rx and b(m, "KEYS_COUNT"):
                joy, want = 0, True
                if cell(m, rx + 1, 8) != lvl(n)["map"][8 * MAP_W + rx + 1]:
                    opened.add(rx)
        if right >= out and b(m, "KEYS_COUNT"):
            joy, want = 0, True
        if stuck >= 10 and joy:
            want, stuck = True, 0
        up = want and not prev_up
        prev_up = up
        if run:
            m.key_down('A')
        F.gframe(m, sym, joy | (JOY_UP if up else 0))
        if run:
            m.key_up('A')
        log["hp"] = min(log["hp"], b(m, "PLAYER_HP"))
        if b(m, "GAME_STATE") == GS_PLAY and F.wrong_cells(m, sym, TILES):
            wrong += 1
    m.joystick(0)
    return f, wrong


def route():
    print("\nTHE ROUTE: through the station, from the joystick")
    m, _ = F.to_level(sym, FIRST)
    for n in range(FIRST, LAST + 1):
        log = {"hp": 100}
        frames, wrong = drive(m, n, log)
        check(f"level {n}: every laser timed, every door opened, out",
              b(m, "GAME_STATE") == GS_CLEAR and log["hp"] == 100,
              f"{frames} game frames, HP at least {log['hp']}, keys "
              f"{b(m, 'KEYS_COUNT')}")
        check(f"level {n}: every on-screen cell is the map's on every game "
              f"frame", wrong == 0, f"{wrong} frames")
        if n < LAST:
            took = None
            for f in range(600):
                m.run_frames(1)
                if (b(m, "GAME_STATE") == GS_PLAY and b(m, "LEVEL_CUR") == n
                        and b(m, "LEVEL_OK")):
                    took = f + 1
                    break
            check(f"... into level {n + 1}, one sector and no art",
                  took is not None and took < 100, f"{took} hardware frames")
            m.run_frames(10)
    m.run_frames(300)
    lo, hi = sym["INTRO_WAIT"], sym["INTRO_WAIT"] + 0x80
    title = False
    for _ in range(2 * 19968 // 8):
        m.run_us(8)
        if lo <= m.pc < hi:
            title = True
            break
    check("... and the computer is the end of the game: back to the title",
          title)
    # THE CONTROL: a cell wholly off the left or the right is off the
    # list (HZ_PAINT_LIST's .off). Kept, it is a paint that draws
    # nothing, and level 23's three lasers that change together - one on
    # the screen, two off it - are twelve cells for the seven the passes
    # in the second sweep have room for.
    m, _ = F.to_level(sym, 23)
    m.poke(sym["HZ_OFF_COL"], 255)
    frames, wrong = drive(m, 23, {"hp": 100})
    check("... and with the cells off the screen kept on the list, level 23 "
          "shows a beam a cel behind", wrong > 0, f"{wrong} frames")


# =====================================================================
# 5. THE LOCK
# =====================================================================
def lock():
    print("\nTHE LOCK: game frames in 200 hardware frames")
    m, _ = F.to_level(sym, 23)
    c = lasers(23)[0]
    F.walk(m, sym, c - 4)
    n, _ = F.stand_count(m, sym)
    check("standing by a laser: 100", n == 100, f"{n}")
    n, _ = F.stand_count(m, sym, pattern=lambda g: JOY_RIGHT
                         | (JOY_UP if g % 10 == 0 else 0))
    check("walking and jumping through the lasers: 100", n == 100, f"{n}")
    m.key_down('A')
    n, _ = F.stand_count(m, sym, pattern=lambda g: JOY_RIGHT
                         | (0x10 if g % 6 < 2 else 0))
    m.key_up('A')
    check("running and firing: 100", n == 100, f"{n}")


def main():
    offline()
    laser()
    door()
    route()
    lock()
    print()
    print("ALL CHECKS PASSED" if not fails else
          f"{len(fails)} FAILED: {fails}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
