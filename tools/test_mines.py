#!/usr/bin/env python3
"""Level 14 on a 6128: the minefield. CLAUDE.md 8.19.

A MINE IS THE TRAP MACHINERY'S THIRD KIND, and the first that is not on
a clock. A spike trap and a cable go round their cels for ever; a mine
HOLDS - armed until her box meets it, then a fireball, the fireball
breaking into bubbles, and gone for good - and a duration of 0 in HZ_DUR
is what says so. Its picture is FOUR tiles and not one tile in a column,
so a cel is four consecutive indexes and HZ_WRITE writes a second column.
What she pays is MINE_HURT, once, out of HZ_TOUCHED - not a tile's bite.

Every expectation is read out of something other than the code under
test, and every one has a control:

    the spawn      sixteen slots out of the level's own records, every
                   one armed and HELD, the map showing cel 1 where the
                   pristine image holds cel 0
    the picture    the armed cel's tiles in bank C4 against the artist's
                   sheet, pixel for pixel, through an independent reading
                   of the column-major layout
    the touch      HZ_TOUCHED called from a stub with her box put one
                   byte - one line - either side of all four edges of the
                   artist's contact box: it goes up AT the edge and not
                   one short of it
    the blast      the four map bytes together, cel by cel, against
                   HZ_DUR's row, and 32 points off her once - and with
                   HZ_TOUCHED answering "no", she swims through the same
                   mine and nothing happens
    the restart    the mine she set off is armed again
    the route      from the surface to the siphon from the joystick,
                   past every mine without touching one, sliding under
                   the three that guard the gates, with every on-screen
                   cell checked against the map on every game frame
    the lock       game frames per 200 hardware frames, anchored, with
                   sixteen armed mines in the level
"""
import os
import re
import sys

sys.path.insert(0, "/home/vasilhs/cpcemu")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bench import sync                                          # noqa: E402
from make_level import read                                     # noqa: E402
import test_sea as TS                                           # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
BUILD = os.path.join(ROOT, "build")
sym = TS.sym
U, D, L, R, FIRE = TS.U, TS.D, TS.L, TS.R, TS.FIRE
GS_PLAY, GS_DEAD, GS_CLEAR = TS.GS_PLAY, TS.GS_DEAD, TS.GS_CLEAR
MAP_W = 32
LVL = read(open(os.path.join(BUILD, "level_14.lvl"), "rb").read())
TILES = open(os.path.join(BUILD, "levels", "level4_underwater",
                          "seatiles.bin"), "rb").read()
T, Rw = TS.T, TS.Rw
STUB = 0x9000

fails = []


def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}{'  ' + detail if detail else ''}")
    if not ok:
        fails.append(name)


def sea(level=14, before=None):
    TS.LEVEL = level
    return TS.Sea(before=before)


def slots(p):
    """[(column, row, base, tc, record)] out of HZ_TABLE - tile units."""
    out = []
    for k in range(p.b("HZ_COUNT")):
        e = sym["HZ_TABLE"] + 8 * k
        m = p.m
        out.append((m.peek(e + 4) // 2, m.peek(e + 5) // 2, m.peek(e + 6),
                    m.peek(e + 7), TS.word(m, e)))
    return out


def cells(p, c, r):
    a = sym["MAP_ADDR"] + r * MAP_W + c
    return [p.m.peek(a), p.m.peek(a + 1), p.m.peek(a + MAP_W),
            p.m.peek(a + MAP_W + 1)]


def mine_records():
    e = LVL["entity_bytes"]
    recs = [e[i:i + 8] for i in range(0, len(e), 8)]
    return [(r[1] | r[2] << 8, r[3] | r[4] << 8, r[7]) for r in recs
            if r[0] == 5 and r[6] == sym["HZ_MINE"]]


# ---------------------------------------------------------------------
def spawn():
    print("\nTHE WAY IN, and the spawn")
    p = sea(13)
    p.m.poke(sym["GAME_STATE"], GS_CLEAR)
    took = None
    for f in range(900):
        p.m.run_frames(1)
        if (p.b("GAME_STATE") == GS_PLAY and p.b("LEVEL_CUR") == 13):
            took = f + 1
            break
    p.m.run_frames(10)
    sync(p.m, sym, 0)
    check("level 14 comes in from level 13's siphon, inside one environment",
          took is not None and took < 100 and p.b("LEVEL_ENV") == 3
          and p.b("LEVEL_SWIM") == 1,
          f"{took} hardware frames - one sector and no art - LEVEL_ENV "
          f"{p.b('LEVEL_ENV')}, LEVEL_SWIM {p.b('LEVEL_SWIM')}")

    recs = mine_records()
    s = slots(p)
    check("sixteen mines, one record each - HZ_MAX of them",
          len(recs) == 16 == sym["HZ_MAX"] == len(s),
          f"{len(recs)} records, {len(s)} slots, HZ_MAX {sym['HZ_MAX']}")
    check("every record's p1 is 0x11: one cell below, armed",
          all(r[2] == 0x11 for r in recs))
    armed = [x for x in s if x[3] == 1]
    check("every slot is ARMED and HELD: cel 1, a timer of 0",
          len(armed) == len(s), f"{len(armed)} of {len(s)} with HZ_TC 1")
    img = sym["LEVEL_LVL"] + LVL["offsets"][0]      # the pristine map
    bad = []
    for c, r, base, tc, _ in s:
        live = cells(p, c, r)
        a = img + r * MAP_W + c
        pristine = [p.m.peek(a), p.m.peek(a + 1), p.m.peek(a + MAP_W),
                    p.m.peek(a + MAP_W + 1)]
        if live != [base + 4 + k for k in range(4)] or \
                pristine != [base + k for k in range(4)]:
            bad.append(((c, r), live, pristine, base))
    check("the map shows cel 1's four tiles where the pristine image holds "
          "cel 0's", not bad, f"{bad[:2]}" if bad else
          f"{len(s)} blocks, three bands: bases {sorted({x[2] for x in s})}")
    return p


def picture():
    print("\nTHE PICTURE: the armed cel against the artist's sheet")
    sys.path.insert(0, HERE)
    import cpclib
    from tilebake import sheet_frames, box_pens
    art = os.path.join(ROOT, "assets", "sprites", "level4_underwater")
    sheet, boxes = sheet_frames(art, "sea_mine_cpc_mode0_sheet")
    b = boxes[0]
    mine = box_pens(sheet, b["x"], b["y"], b["w"], b["h"], alpha=True)

    def tile_pens(i):
        """Tile i out of the blob, column-major (CLAUDE.md 9): for each
        of its two character columns, sixteen lines of two bytes."""
        t = TILES[64 * i:64 * i + 64]
        out = [[None] * 8 for _ in range(16)]
        for col in range(2):
            for y in range(16):
                for k in range(2):
                    p0, p1 = cpclib.decode_byte(t[col * 32 + y * 2 + k])
                    out[y][col * 4 + k * 2] = p0
                    out[y][col * 4 + k * 2 + 1] = p1
        return out
    wrong = total = 0
    for base in sorted({x[2] for x in SLOTS}):
        quad = [tile_pens(base + 4 + k) for k in range(4)]
        for y in range(24):
            for x in range(16):
                v = mine[y][x]
                if v is None:
                    continue
                q = quad[(y >= 16) * 2 + (x >= 8)]
                total += 1
                wrong += q[y % 16][x % 8] != v
    check("every opaque pixel of bob frame 0 is in the armed cel, in every "
          "band", total > 0 and wrong == 0, f"{wrong} of {total} wrong")
    # THE CONTROL: the same check against the GONE cel, which is water.
    gone = 0
    base = SLOTS[0][2]
    quad = [tile_pens(base + k) for k in range(4)]
    for y in range(24):
        for x in range(16):
            v = mine[y][x]
            if v is not None:
                gone += quad[(y >= 16) * 2 + (x >= 8)][y % 16][x % 8] != v
    band = total // len({x[2] for x in SLOTS})
    check("... and NOT in the gone one", gone > band // 2,
          f"{gone} of the {band} pixels one band has differ")


def stub_touch(p, slot_addr):
    """HZ_TOUCHED from a DI stub with IY = the slot: its carry."""
    code = bytes([0xF3, 0xFD, 0x21, slot_addr & 255, slot_addr >> 8,
                  0xCD, sym["HZ_TOUCHED"] & 255, sym["HZ_TOUCHED"] >> 8,
                  0xF5, 0xE1, 0x22, (STUB + 0x40) & 255, (STUB + 0x40) >> 8,
                  0x18, 0xFE])
    p.m.write_ram(STUB, code)
    p.m.set_pc(STUB)
    for _ in range(20000):
        p.m.run_us(1)
        if p.m.pc == STUB + len(code) - 2:
            break
    return p.m.peek(STUB + 0x40) & 1


def touch():
    print("\nTHE TOUCH: the artist's contact box, to the byte and the line")
    p = sea()
    m = p.m
    c, r = SLOTS[0][0], SLOTS[0][1]
    slot = sym["HZ_TABLE"]
    mx, my = c * 8 // 2, r * 16           # its left byte, its top line
    W, H = sym["SWIM_BOX_W"], sym["SWIM_BOX_H"]
    x0, x1 = mx + sym["MINE_X0"], mx + sym["MINE_X1"]
    y0, y1 = my + sym["MINE_Y0"], my + sym["MINE_Y1"]
    sx, sy = mx + 1, my + 4               # a place well inside on the other
    results = []
    # (her WX, her WY, should it go up)
    for wx, wy, want in ((x0 - W, sy, 0), (x0 - W + 1, sy, 1),   # from the left
                         (x1, sy, 0), (x1 - 1, sy, 1),           # the right
                         (sx, y0 - H, 0), (sx, y0 - H + 1, 1),   # above
                         (sx, y1, 0), (sx, y1 - 1, 1)):          # below
        m.poke(sym["PLAYER_HP"], 100)
        m.write_ram(sym["KARA_WX"], bytes([wx & 255, wx >> 8]))
        m.write_ram(sym["KARA_WY"], bytes([wy & 255, wy >> 8]))
        got = stub_touch(p, slot)
        results.append((wx, wy, want, got, m.peek(sym["PLAYER_HP"])))
    ok = all(w == g for _, _, w, g, _ in results)
    paid = all(hp == (100 - sym["MINE_HURT"] if g else 100)
               for _, _, _, g, hp in results)
    check("it goes up AT each edge of the contact box and not a byte or a "
          "line short of it", ok,
          f"bytes {x0}..{x1 - 1}, lines {y0}..{y1 - 1}, her box {W}x{H}: "
          + ", ".join(f"({x},{y})->{g}" for x, y, _, g, _ in results))
    check("... and it is HZ_TOUCHED that charges her, MINE_HURT a touch",
          paid, f"MINE_HURT {sym['MINE_HURT']}")


def blast():
    print("\nTHE BLAST: off the map bytes, from the joystick")
    p = sea()
    c, r, base = SLOTS[0][0], SLOTS[0][1], SLOTS[0][2]
    hp0 = p.b("PLAYER_HP")
    seen = []
    hit_at = None
    for t in range(80):
        p.frame(R)
        q = cells(p, c, r)
        seen.append(q)
        if q[0] != base + 4 and hit_at is None:
            hit_at = t
            break
    for t in range(40):
        p.frame(0)
        seen.append(cells(p, c, r))
    cels = []
    for q in seen[hit_at:]:
        k = (q[0] - base) // 4
        together = q == [base + 4 * k + j for j in range(4)]
        if not together:
            cels.append(("split", q))
            break
        if not cels or cels[-1][0] != k:
            cels.append([k, 1])
        else:
            cels[-1][1] += 1
    dur = [p.m.peek(sym["HZ_DUR"] + 4 * sym["HZ_MINE"] + i) for i in range(4)]
    run = [tuple(x) for x in cels]
    check("swimming into it, all four of its tiles go up together: the "
          "fireball and the bubbles for HZ_DUR's frames, then gone",
          hit_at is not None and run[:3] == [(2, dur[2]), (3, dur[3]),
                                             (0, run[2][1])]
          and run[2][1] >= 20 and len(run) == 3,
          f"{run}, HZ_DUR {dur}")
    check("... and it cost her MINE_HURT, once",
          hp0 - p.b("PLAYER_HP") == sym["MINE_HURT"],
          f"{hp0} -> {p.b('PLAYER_HP')}")
    s = [x for x in slots(p) if (x[0], x[1]) == (c, r)][0]
    check("... and the slot holds on cel 0, gone", s[3] == 0,
          f"HZ_TC {s[3]}")

    print("  ... and with HZ_TOUCHED answering no:")
    q = sea(before=lambda m: m.write_ram(sym["HZ_TOUCHED"],
                                         bytes([0xB7, 0xC9])))
    for t in range(60):
        q.frame(R)
    check("she swims through the same mine and it stays armed, and she is "
          "not hurt", cells(q, c, r) == [base + 4 + j for j in range(4)]
          and q.b("PLAYER_HP") == 100 and q.w("KARA_WX") > c * 4 + 8,
          f"WX {q.w('KARA_WX')} - past its column {c * 4} - HP "
          f"{q.b('PLAYER_HP')}, its tiles {cells(q, c, r)}")
    return p


def restart(p):
    print("\nTHE RESTART: what went up is armed again")
    c, r, base = SLOTS[0][0], SLOTS[0][1], SLOTS[0][2]
    p.m.poke(sym["PLAYER_HP"], 0)
    back = False
    for _ in range(700):
        p.frame(0)
        if p.b("GAME_STATE") == GS_PLAY and p.b("PLAYER_HP") == 100:
            back = True
            break
    p.frames(2)
    s = [x for x in slots(p) if (x[0], x[1]) == (c, r)][0]
    check("she dies, the level comes back, and the mine is armed",
          back and s[3] == 1
          and cells(p, c, r) == [base + 4 + j for j in range(4)],
          f"back {back}, HZ_TC {s[3]}, tiles {cells(p, c, r)}")


def route(p):
    """From the surface to the siphon. Every move is along one axis, and
    the heights are the windows the mines leave - worked out from their
    contact boxes, not found by trying."""
    def gx(x):
        p.go(x, p.w("KARA_WY"))

    def gy(y):
        p.go(p.w("KARA_WX"), y)

    def slide(joy, done):
        for _ in range(120):
            if done():
                break
            p.frame(joy, True)
    gx(32)                                  # under (14,3)'s sphere: left
    gy(80)                                  # of its column, below it
    gx(50)
    gy(230)                                 # onto the ledge, left of the
    slide(R | D, lambda: p.w("KARA_WX") >= 76)   # gate, and under its guard
    gy(300)
    gy(406)                                 # the tank
    slide(L | D, lambda: p.w("KARA_WX") <= 38)   # under the second guard
    gy(560)
    slide(D, lambda: p.w("KARA_WY") >= 616)
    slide(R | D, lambda: p.w("KARA_WX") >= 72)   # under the third
    gy(710)
    gx(96)                                  # the tank
    gx(80)
    gy(812)                                 # under (24,49)
    gx(100)
    gy(962)                                 # the key
    gy(871)                                 # over the ruins, under (9,53)
    gx(30)
    gx(24)
    gy(964)                                 # the siphon


def the_route():
    print("\nTHE ROUTE: past sixteen mines, from the joystick")
    p = sea()
    hp = []
    orig = p.frame

    def frame(joy=0, picture=False):
        orig(joy, picture)
        hp.append(p.b("PLAYER_HP"))
    p.frame = frame
    route(p)
    check("she reaches the siphon with the key and every mine still armed",
          p.b("KEYS_COUNT") == 1
          and all(s[3] == 1 for s in slots(p)),
          f"WX {p.w('KARA_WX')} WY {p.w('KARA_WY')}, O2 {p.b('OXYGEN')}, "
          f"armed {sum(1 for s in slots(p) if s[3] == 1)} of 16")
    check("... and was never touched by one", min(hp) == 100,
          f"HP at least {min(hp)} over {len(hp)} game frames")
    check("every on-screen cell is the map's on every game frame of it",
          not p.wrong, f"{len(p.wrong)} frames: {p.wrong[:3]}")
    p.frame(U)
    p.frame(0)
    check("UP at the siphon opens the way out",
          p.b("GAME_STATE") == GS_CLEAR)
    took = None
    for f in range(400):
        p.m.run_frames(1)
        if p.b("GAME_STATE") == GS_PLAY and p.b("LEVEL_CUR") == 14:
            took = f + 1
            break
    check("... and it leads to level 15, the patrol, inside one "
          "environment", took is not None and p.b("LEVEL_ENV") == 3
          and took < 100,
          f"{took} hardware frames - one sector, no art - LEVEL_ENV "
          f"{p.b('LEVEL_ENV')}, LEVEL_CUR {p.b('LEVEL_CUR')}")


def lock():
    print("\nTHE LOCK: game frames in 200 hardware frames, anchored")
    p = sea()

    def count(joy):
        sync(p.m, sym, 0)
        f0 = p.b("FRAME_COUNT")
        for _ in range(200):
            p.m.joystick(joy)
            p.m.run_frames(1)
        p.m.joystick(0)
        return (p.b("FRAME_COUNT") - f0) % 256
    got = {"treading water among sixteen armed mines": count(0),
           "swimming right, into the first one": count(R),
           "down the chamber, the view stepping": count(D)}
    for k, v in got.items():
        check(f"{k}: 100", v == 100, f"{v}")
    check("... and the first went up on the way, four cells at once",
          [s for s in slots(p) if (s[0], s[1]) == SLOTS[0][:2]][0][3] != 1)


def cost():
    print("\nWHAT IT COSTS: the tick, and the strip it goes in front of")
    import bench
    p = sea()
    b = bench.Bench(p.m, sym)
    armed = b.T("HAZARD_TICK")
    for k in range(16):
        p.m.poke(sym["HZ_TABLE"] + 8 * k + 7, 0)
    gone = b.T("HAZARD_TICK")
    print(f"  HAZARD_TICK from a DI stub: sixteen armed {armed} T, sixteen "
          f"gone {gone} T")

    # THE BOUND IS THE STRIP'S, so the strip is what is timed. The tick
    # is the first thing in the second sweep after the latch, and the
    # first pass's cells and the strip come after it; on a row step the
    # strip is 32,856 T of its own and has to be done before the beam
    # reaches row 22 - 63,488 T on a real 6845 (CLAUDE.md 7.8). Timed
    # from the instruction after the second WAIT_VSYNC to the call after
    # the second HUD_SERVICE, over a swim into the first mine and down.
    q = sea()
    m = q.m
    a0, a1 = sym["ENEMY_SLOT"], sym["ENEMY_THINK"]
    rows = []
    for joy, n in ((R, 25), (D, 140)):
        for _ in range(n):
            m.joystick(joy)
            sync(m, sym, 1)
            cr0, hp0 = m.peek(sym["WORLD_CR"]), m.peek(sym["PLAYER_HP"])
            while m.pc != a0:
                m.run_us(1)
            t = 0
            while m.pc != a1 and t < 40000:
                m.run_us(1)
                t += 1
            rows.append((t * 4, m.peek(sym["WORLD_CR"]) != cr0,
                         m.peek(sym["PLAYER_HP"]) != hp0))
    m.joystick(0)
    worst = max(r[0] for r in rows)
    steps = [r[0] for r in rows if r[1]]
    blast = [r[0] for r in rows if r[2]]
    check("the second sweep's strip is down before row 22 on every game "
          "frame - the row steps and the blast among them",
          worst < 63488 and steps and blast,
          f"worst {worst} T of 63,488 over {len(rows)} game frames; "
          f"{len(steps)} row steps, worst {max(steps) if steps else '-'}; "
          f"the blast's frame {blast[0] if blast else '-'}")


def editor():
    print("\nTHE EDITOR'S COPY: HazardKind.Mine and MaxHazards")
    src = open(os.path.join(ROOT, "editor", "src", "CpcLevelEditor.Domain",
                            "HazardKind.cs")).read()
    mine = re.search(r"Mine\s*=\s*(\d+)", src)
    lim = re.search(r"MaxHazards\s*=\s*(\d+)", open(os.path.join(
        ROOT, "editor", "src", "CpcLevelEditor.Domain",
        "EngineLimits.cs")).read())
    check("the editor numbers the mine and the table as the engine does",
          mine and int(mine.group(1)) == sym["HZ_MINE"]
          and lim and int(lim.group(1)) == sym["HZ_MAX"],
          f"Mine = {mine and mine.group(1)} against HZ_MINE "
          f"{sym['HZ_MINE']}, MaxHazards {lim and lim.group(1)} against "
          f"HZ_MAX {sym['HZ_MAX']}")


SLOTS = []


def main():
    p = spawn()
    SLOTS.extend(slots(p))
    picture()
    touch()
    q = blast()
    restart(q)
    the_route()
    lock()
    cost()
    editor()
    print()
    if fails:
        print(f"{len(fails)} CHECK(S) FAILED")
        for f in fails:
            print("  -", f)
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
