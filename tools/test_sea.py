#!/usr/bin/env python3
"""Level 13 on a 6128: the undersea, the swimmer, her air and the cables.
CLAUDE.md 8.18.

SHE SWIMS. The undersea is the first environment where she is not
standing up: 64x24 and horizontal, out of the swim sheet the art has
shipped since the start, and the level header's underwater bit is what
says so. Twenty-seven immediates that say how big she is are patched for
it at install, the way the map's shape is (src/swim.asm, src/mapshape.
asm); she moves in four directions with nothing under her and the water
lifting her; she breathes at the surface and over a vent, spends her air
everywhere else and drowns without it; and the cables between the ledges
are the forest's trap machinery with a second kind.

WHAT MAKES IT A CHECK AND NOT A SCREENSHOT is that every expectation is
read out of something other than the code under test, and every one has
a control:

    the box        the patch table read back out of RAM, against the
                   bytes on a land level and the swimmer's on this one -
                   and with BOX_SET a RET, she lands 40 lines short of
                   the ledge, which is a 64-line box swimming
    the physics    lines a game frame, off KARA_WY, against SWIM_VY and
                   the drift, and where she stops against the map's rock
    her air        OXYGEN a unit every OXY_RATE frames, breathed back in
                   the level's own regions, drowned without - and with
                   OXY_STEP a RET nothing moves
    the cables     the cycle off the map byte, the whole run of cells at
                   once - with the run's nibble zeroed only the first
                   cell moves - and a bite that HAZARD_TICK = RET takes
                   away
    the route      driven from the joystick to the siphon, with every
                   on-screen cell checked against the map on every game
                   frame - and with HZ_WHERE saying every cell off the
                   screen is FAR, which is what the engine did before it,
                   the cells that came in with a row go stale
    the lock       game frames per 200 hardware frames, anchored
"""
import os
import re
import sys

sys.path.insert(0, "/home/vasilhs/cpcemu")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bench import boot, symbols, sync                          # noqa: E402
from make_level import read                                    # noqa: E402
import test_forest7 as FO                                      # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
BUILD = os.path.join(ROOT, "build")

U, D, L, R, FIRE, SHIFT = 0x01, 0x02, 0x04, 0x08, 0x10, None
GS_PLAY, GS_DEAD, GS_CLEAR = 0, 1, 2
MAP_W = 32
LEVEL = 13
KST_SWIM, KST_SWIM_FIRE, KST_DIE = 13, 14, 10
KSET_SWIM = 3
RG_OXYGEN = 2

fails = []


def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}{'  ' + detail if detail else ''}")
    if not ok:
        fails.append(name)


def word(m, a):
    return m.peek(a) | m.peek(a + 1) << 8



sym = symbols()
TILES = open(os.path.join(BUILD, "levels", "level4_underwater",
                          "seatiles.bin"), "rb").read()
LVL = read(open(os.path.join(BUILD, f"level_{LEVEL}.lvl"), "rb").read())
FO.MAP_W = MAP_W


class Sea:
    """The running game in level 13, in the level's own units."""

    def __init__(self, before=None):
        self.m = m = boot(sym, scroll=True)
        if before:
            before(m)
        m.poke(sym["LEVEL_CUR"], LEVEL - 2)
        m.poke(sym["GAME_STATE"], GS_CLEAR)
        self.took = None
        for f in range(1200):
            m.run_frames(1)
            if (m.peek(sym["GAME_STATE"]) == GS_PLAY
                    and m.peek(sym["LEVEL_CUR"]) == LEVEL - 1):
                self.took = f + 1
                break
        m.run_frames(10)
        sync(m, sym, 0)
        self.wrong = []

    def b(self, n):
        return self.m.peek(sym[n])

    def w(self, n):
        return word(self.m, sym[n])

    def frame(self, joy=0, picture=False):
        """One GAME frame with `joy` held, ending at the top of the loop."""
        FO.gframe(self.m, sym, joy)
        if picture:
            bad = wrong_cells(self.m)
            if bad:
                self.wrong.append((self.b("FRAME_COUNT"), bad[:3]))

    def frames(self, n, joy=0, picture=False):
        for _ in range(n):
            self.frame(joy, picture)

    def go(self, tx, ty, limit=600, picture=True):
        """Swim her box's top-left to (tx bytes, ty lines)."""
        for _ in range(limit):
            x, y = self.w("KARA_WX"), self.w("KARA_WY")
            if abs(x - tx) <= 1 and abs(y - ty) <= 2:
                break
            j = 0
            if x < tx - 1:
                j |= R
            elif x > tx + 1:
                j |= L
            if y < ty - 2:
                j |= D
            elif y > ty + 2:
                j |= U
            self.frame(j, picture)
        return self.w("KARA_WX"), self.w("KARA_WY")

    def cable_byte(self, col, row):
        return self.m.peek(sym["MAP_ADDR"] + row * MAP_W + col)

    def cross(self, col, row, tx, ty, picture=True):
        """Wait for the cable whose first cell is (col, row) to go OFF,
        then swim to (tx, ty)."""
        was = self.cable_byte(col, row)
        for _ in range(200):
            self.frame(0, picture)
            now = self.cable_byte(col, row)
            if now < was:                   # cel 3 -> cel 0
                break
            was = now
        return self.go(tx, ty, picture=picture)


def wrong_cells(m):
    """forest7's model of the picture, with the LEFT step's head excused
    as well. H_COL 0 is a step left, and its rows 0..COL_HEAD-1 go down
    under the old start address at column 39 of the row ABOVE (CLAUDE.md
    8.2) - the forest's walks only ever went right, so its model never
    needed it."""
    bad = FO.wrong_cells(m, sym, TILES)
    if m.peek(sym["H_PENDING"]) and m.peek(sym["H_COL"]) == 0:
        wx, wcr = m.peek(sym["WORLD_X"]), m.peek(sym["WORLD_CR"])
        ex = {((wx + 39) // 2, (wcr + sr) // 2)
              for sr in range(0, sym["COL_HEAD"] - 1)}
        bad = [c for c in bad if c not in ex]
    return bad


T = lambda c: c * 4          # a tile column -> her box's byte column
Rw = lambda r: r * 16        # a tile row -> a world line


def records():
    e = LVL["entity_bytes"]
    return [e[i:i + 8] for i in range(0, len(e), 8)]


def cables():
    """(column, first row, p1) of every cable record, out of the FILE."""
    out = []
    for r in records():
        if r[0] == 5 and r[6] == 1:         # EK_HAZARD, HZ_CABLE
            x, y = r[1] | r[2] << 8, r[3] | r[4] << 8
            out.append((x // 8, y // 16 - 1, r[7]))
    return out


# =====================================================================
def the_box():
    print("\nTHE BOX: her size in the engine's immediates, patched at install")
    m = boot(sym, scroll=True)
    table = sym["BOX_SITES"]
    sites = []
    a = table
    while word(m, a):
        sites.append((word(m, a), m.peek(a + 2), m.peek(a + 3)))
        a += 4
    land = [s for s, l_, w_ in sites if m.peek(s) != l_]
    check(f"on level 1 every one of the {len(sites)} sites holds the land "
          "byte", not land and len(sites) == sym["BOX_SITES_N"],
          f"{len(land)} do not")
    # ... AND THE LAND BYTE IS THE SOURCE'S OWN, read out of the image the
    # assembler wrote, before BOX_SET has ever run. The check above reads
    # the table back against itself, and two sites whose `equ $ - 2` sat
    # BEFORE their instruction instead of after it passed it while every
    # land level drew its drone out of ld hl,(&2F03) (CLAUDE.md 10).
    img = open(os.path.join(BUILD, "engine.bin"), "rb").read()
    def built(a, n=1):
        o = a - sym["CORE_ADDR"] + sym["CORE_IMAGE"] - sym["BOOT_ADDR"]
        return img[o] if n == 1 else img[o] | img[o + 1] << 8
    off = [f"{s:04X}" for s, l_, _ in sites if built(s) != l_]
    check("... and every land byte is the one the source assembles there",
          not off, f"{len(off)} are not: {off}")
    words = []
    a = sym["BOX_WORDS"]
    while word(m, a):
        words.append((word(m, a), word(m, a + 2), word(m, a + 4)))
        a += 6
    check("... and the HUD's second slot reads the coins",
          all(word(m, s) == l_ == built(s, 2) for s, l_, _ in words),
          f"{len(words)} words, each the source's own")
    p = Sea()
    water = [s for s, _, w_ in sites if p.m.peek(s) != w_]
    check("on level 13 every one holds the swimmer's", not water,
          f"{len(water)} do not")
    check("... and the slot reads her air",
          all(word(p.m, s) == w_ for s, _, w_ in words))
    check("LEVEL_SWIM says so", p.b("LEVEL_SWIM") == 1)
    return p


def physics(p):
    print("\nTHE SWIMMER: four directions, nothing under her, the water "
          "lifting her")
    check("she arrives swimming, out of the swim set",
          p.b("KARA_STATE") == KST_SWIM and p.b("KARA_SET") == KSET_SWIM,
          f"state {p.b('KARA_STATE')}, set {p.b('KARA_SET')}")
    start = (p.w("KARA_WX"), p.w("KARA_WY"))
    col, row = 6, 2
    check("where the record puts her", start == (T(col), Rw(row)),
          f"{start} - the record's base less her 24 lines")
    y0 = p.w("KARA_WY")
    p.frames(5, U)
    check("UP against the surface does nothing", p.w("KARA_WY") == y0,
          f"WY {p.w('KARA_WY')} - the surface tiles are SOLID")
    y0 = p.w("KARA_WY")
    p.frames(20, D)
    dy = p.w("KARA_WY") - y0
    check("DOWN is SWIM_VY lines a game frame", dy == 20 * sym["SWIM_VY"],
          f"{dy} lines in 20 frames")
    y0 = p.w("KARA_WY")
    p.frames(20, 0)
    dy = y0 - p.w("KARA_WY")
    check("... and with nothing held the water lifts her a line every "
          "other frame", dy == 10, f"{dy} lines in 20 frames")
    y0 = p.w("KARA_WY")
    p.frames(10, U)
    check("UP is SWIM_VY too", y0 - p.w("KARA_WY") == 10 * sym["SWIM_VY"],
          f"{y0 - p.w('KARA_WY')} in 10")
    x0 = p.w("KARA_WX")
    p.frames(20, R)
    check("RIGHT is a byte a game frame, PLAYER_X's walk",
          p.w("KARA_WX") - x0 == 20, f"{p.w('KARA_WX') - x0} bytes")
    p.m.key_down('A')                       # SHIFT: an upper-case letter
    x0 = p.w("KARA_WX")
    p.frames(20, R)
    p.m.key_up('A')
    check("... and SHIFT does not run her: there is no run in the water",
          p.w("KARA_WX") - x0 == 20, f"{p.w('KARA_WX') - x0} bytes")
    # the first ledge is at row 16, under the column she is in now
    p.go(T(12), Rw(14), picture=False)
    p.frames(60, D)
    check("she stops FLUSH on the ledge: her bottom line on its top",
          p.w("KARA_WY") == Rw(16) - 24, f"WY {p.w('KARA_WY')}, the ledge "
          f"is at {Rw(16)}")


def box_control():
    print("\n  ... and with BOX_SET a RET, the box stays a walker's:")
    p = Sea(before=lambda m: m.poke(sym["BOX_SET"], 0xC9))
    p.go(T(12), Rw(10), picture=False)
    p.frames(60, D)
    y = p.w("KARA_WY")
    check("she stops 40 lines short of the ledge - a 64-line box",
          y == Rw(16) - 64, f"WY {y}")


def gun(p):
    print("\nHER GUN: draw-hold-release, the swim sheet's own recoil")
    p.go(T(10), Rw(8), picture=False)
    res = p.b("MAG_LEFT") + p.b("MAG_RIGHT")
    p.frames(3, FIRE)
    held = p.b("KARA_STATE")
    p.frame(0)
    st, fr = p.b("KARA_STATE"), p.b("KARA_FRAME")
    check("holding SPACE she swims on; letting go is SWIM_FIRE",
          held == KST_SWIM and st == KST_SWIM_FIRE,
          f"held {held}, released {st}, cel {fr}")
    seen = set()
    for _ in range(8):
        seen.add(p.b("KARA_FRAME"))
        p.frame(0)
    check("... which plays swim_shoot's four cels and comes back",
          {8, 9, 10, 11} <= seen and p.b("KARA_STATE") == KST_SWIM,
          f"cels {sorted(seen)}")
    check("... and a round left the gun",
          p.b("MAG_LEFT") + p.b("MAG_RIGHT") < res,
          f"rounds {res} -> {p.b('MAG_LEFT') + p.b('MAG_RIGHT')}")


def air():
    print("\nHER AIR: spent, breathed back, drowned without")
    p = Sea()
    p.go(T(10), Rw(8), picture=False)
    # seventy game frames with nothing held: she drifts up 35 lines and
    # stays clear of the surface's region, and ANY seventy consecutive
    # frames out of the air hold exactly 70 / OXY_RATE wraps of OXY_T
    o0 = p.b("OXYGEN")
    p.frames(70, 0)
    spent = o0 - p.b("OXYGEN")
    check("a unit every OXY_RATE game frames",
          spent == 70 // sym["OXY_RATE"],
          f"{spent} units in 70 frames, OXY_RATE {sym['OXY_RATE']}")
    check("... and the HUD's digit is OXYGEN / 11",
          p.b("OXY_DIGIT") == p.b("OXYGEN") // 11
          and p.b("HUD_INV_C") == p.b("OXY_DIGIT"),
          f"OXYGEN {p.b('OXYGEN')}, digit {p.b('OXY_DIGIT')}, laid out "
          f"{p.b('HUD_INV_C')}")
    p.go(T(10), Rw(2), picture=False)
    o0 = p.b("OXYGEN")
    p.frames(5, U)
    check("at the surface she breathes: the level's own region",
          p.b("OXYGEN") > o0, f"{o0} -> {p.b('OXYGEN')}")
    regions = LVL["regions"]
    check("... which the FILE carries, two of RegionKind.OxygenVent",
          regions == 2)
    p.m.poke(sym["OXYGEN"], 0)
    p.go(T(10), Rw(10), picture=False)
    hp0 = p.b("PLAYER_HP")
    p.frames(sym["DROWN_RATE"] * 3, 0)
    p.go(T(10), Rw(10), picture=False)
    lost = hp0 - p.b("PLAYER_HP")
    check("out of air the water takes DROWN_HURT every DROWN_RATE frames",
          lost in (3 * sym["DROWN_HURT"], 4 * sym["DROWN_HURT"]),
          f"{hp0} -> {p.b('PLAYER_HP')}")
    print("  ... and with OXY_STEP a RET:")
    q = Sea(before=lambda m: m.poke(sym["OXY_STEP"], 0xC9))
    q.go(T(10), Rw(8), picture=False)
    o0 = q.b("OXYGEN")
    q.frames(70, 0)
    check("nothing is spent", q.b("OXYGEN") == o0, f"{o0} -> {q.b('OXYGEN')}")


def the_cables():
    print("\nTHE CABLES: a trap that is a column of cells")
    cs = cables()
    check("four cables, ONE record each", len(cs) == 4,
          f"{[(x, r, hex(p1)) for x, r, p1 in cs]}")
    p = Sea()
    x, r, p1 = cs[0]
    n = (p1 >> 4) + 1
    seq, together = [], True
    for _ in range(140):
        cells = [p.cable_byte(x, r + k) for k in range(n)]
        together &= len(set(cells)) == 1
        seq.append(cells[0])
        p.frame(0)
    runs, cur, cnt = [], seq[0], 0
    for c in seq:
        if c == cur:
            cnt += 1
        else:
            runs.append((cur, cnt))
            cur, cnt = c, 1
    whole = [k for _, k in runs[1:]]
    dur = [p.m.peek(sym["HZ_DUR"] + 4 + i) for i in range(4)]
    check("the cycle off the map byte is HZ_DUR's cable row",
          whole[:4] == [dur[(runs[1][0] - runs[0][0] + i) % 4]
                        for i in range(4)] or sorted(whole[:4]) == sorted(dur),
          f"{runs[:6]} against {dur}")
    check(f"... and all {n} cells of the run change together", together)
    # the phases: no two cables change within two frames of each other
    changes = {i: [] for i in range(len(cs))}
    last = [p.cable_byte(cx, cr) for cx, cr, _ in cs]
    for t in range(130):
        p.frame(0)
        for i, (cx, cr, _) in enumerate(cs):
            v = p.cable_byte(cx, cr)
            if v != last[i]:
                changes[i].append(t)
            last[i] = v
    gap = min(abs(a - b) for i in changes for j in changes if i < j
              for a in changes[i] for b in changes[j])
    check("no two cables change within two game frames of each other",
          gap >= 2, f"nearest {gap} - the head start in p1's bits 2-3")
    print("  ... and with the run's nibble zeroed in the record:")
    rec = sym["ENT_TABLE"] + 8 * next(
        i for i, rr in enumerate(records()) if rr[0] == 5)
    q = Sea(before=None)
    q.m.poke(rec + 7, q.m.peek(rec + 7) & 0x0F)
    q.m.poke(sym["HAZARD_SPAWN"] - 0, q.m.peek(sym["HAZARD_SPAWN"]))
    x, r, _ = cs[0]
    moved = set()
    first = set()
    for _ in range(100):
        q.frame(0)
        first.add(q.cable_byte(x, r))
        moved |= {q.cable_byte(x, r + k) for k in range(1, n)}
    check("only the first cell goes round", len(first) > 1 and len(moved) == 1,
          f"first cell {sorted(first)}, the rest {sorted(moved)}")


def bite():
    print("\nTHE BITE: the live cel's TA_HAZARD, under her")
    x, r, _ = cables()[0]

    def live_cel(p):
        """The slot's HZ_BASE + 3 - cel 3 is the one that bites."""
        cell = sym["MAP_ADDR"] + r * MAP_W + x
        for k in range(p.b("HZ_COUNT")):
            e = sym["HZ_TABLE"] + 8 * k
            if word(p.m, e + 2) == cell:
                return p.m.peek(e + 6) + 3
        return None

    def toward(p, tx, ty):
        """The joystick that holds her at (tx, ty) against the drift."""
        j = 0
        x, y = p.w("KARA_WX"), p.w("KARA_WY")
        if x < tx:
            j |= R
        elif x > tx:
            j |= L
        if y < ty:
            j |= D
        return j

    def sit(p):
        """Into the first corridor beside the cable and HELD there until
        it goes OFF, then into its column and held there for the rest of
        ONE cycle - so it comes on under her exactly once."""
        p.go(T(23), Rw(14), picture=False)
        p.go(T(23), Rw(r), picture=False)
        p.go(T(x) + 8, Rw(r) + 4, picture=False)
        was = p.cable_byte(x, r + 1)
        for _ in range(200):
            p.frame(toward(p, T(x) + 8, Rw(r) + 4))
            now = p.cable_byte(x, r + 1)
            if now < was:                   # cel 3 -> cel 0: just gone off
                break
            was = now
        hp0, live, hot = p.b("PLAYER_HP"), 0, live_cel(p)
        last = p.cable_byte(x, r + 1)
        for t in range(cycle - 4):
            p.frame(toward(p, T(x) - 6, Rw(r) + 4))
            now = p.cable_byte(x, r + 1)
            live += now == hot and last != hot
            last = now
        return hp0, live
    p = Sea()
    cycle = sum(p.m.peek(sym["HZ_DUR"] + 4 + i) for i in range(4))
    hp0, live = sit(p)
    lost = hp0 - p.b("PLAYER_HP")
    check("sitting in a cable's column through its cycle costs her one "
          "bite", lost == sym["TILE_HURT"] and live == 1,
          f"{hp0} -> {p.b('PLAYER_HP')}, the cable came on {live} time(s)")
    print("  ... and with HAZARD_TICK a RET:")
    q = Sea(before=lambda m: m.poke(sym["HAZARD_TICK"], 0xC9))
    q.go(T(23), Rw(14), picture=False)
    q.go(T(23), Rw(r), picture=False)
    hp0 = q.b("PLAYER_HP")
    q.go(T(x) - 6, Rw(r) + 4, picture=False)
    for _ in range(cycle):
        q.frame(toward(q, T(x) - 6, Rw(r) + 4))
    check("the cable never comes on and she is not bitten",
          q.b("PLAYER_HP") == hp0, f"{hp0} -> {q.b('PLAYER_HP')}")


def route(p, label=""):
    """The whole level, from the joystick, to the siphon."""
    p.go(T(23), Rw(14))
    p.go(T(23), Rw(19))
    p.go(T(23), Rw(23) - 24)                       # the ammo
    p.go(T(17), Rw(20))
    p.cross(15, 19, T(5), Rw(20))
    p.go(T(5), Rw(25) + 4)
    p.go(T(6), Rw(27) + 2)
    p.frames(20, 0, True)                          # the vent
    p.go(T(15), Rw(27))
    p.cross(18, 26, T(23), Rw(27))
    p.go(T(23), Rw(32) + 4)
    p.go(T(20), Rw(34))
    p.cross(17, 33, T(5), Rw(34))
    p.go(T(5), Rw(36))                             # a tank
    p.go(T(5), Rw(39) + 4)
    p.go(T(11), Rw(41))
    p.cross(14, 40, T(23), Rw(41))
    p.go(T(23), Rw(43))                            # the medkit
    p.go(T(23), Rw(50))
    p.go(T(5), Rw(60))                             # the key
    p.go(T(11), Rw(60))                            # a tank
    p.go(T(21), Rw(60) + 6)                        # over the siphon


def the_route():
    print("\nTHE ROUTE: from the surface to the siphon, from the joystick")
    p = Sea()
    check("level 13 comes in from the cave's last door, an environment "
          "away", p.took is not None and p.b("LEVEL_ENV") == 3,
          f"{p.took} hardware frames, LEVEL_ENV {p.b('LEVEL_ENV')}")
    route(p)
    check("she reaches the siphon with the key", p.b("KEYS_COUNT") == 1,
          f"WX {p.w('KARA_WX')} WY {p.w('KARA_WY')}, O2 {p.b('OXYGEN')}, "
          f"HP {p.b('PLAYER_HP')}, reserve {p.b('AMMO_RESERVE')}")
    check("every on-screen cell is the map's on every game frame of it",
          not p.wrong, f"{len(p.wrong)} frames: {p.wrong[:3]}")
    p.frame(U)
    p.frame(0)
    check("UP at the siphon opens the way out", p.b("GAME_STATE") == GS_CLEAR)
    took = None
    for f in range(400):
        p.m.run_frames(1)
        if p.b("GAME_STATE") == GS_PLAY and p.b("LEVEL_CUR") == LEVEL:
            took = f + 1
            break
    check("... and it leads to level 14, the minefield, inside one "
          "environment", took is not None and p.b("LEVEL_ENV") == 3
          and took < 100,
          f"{took} hardware frames - one sector, no art - LEVEL_ENV "
          f"{p.b('LEVEL_ENV')}, LEVEL_CUR {p.b('LEVEL_CUR')}")
    # NOT "every cell is on the screen": a cell one row below the view is
    # then painted into the margin the incoming row is painted in, which
    # is right by accident. What HZ_WHERE replaced DROPPED them.
    print("  ... and with HZ_WHERE calling every cell off the screen FAR:")
    q = Sea(before=lambda m: m.write_ram(sym["HZ_WHERE"], bytes([0x3E, 0, 0xC9])))
    route(q)
    check("the cells that changed while their row was coming in go stale",
          len(q.wrong) > 0, f"{len(q.wrong)} game frames with a wrong cell")


def lock():
    print("\nTHE LOCK: game frames in 200 hardware frames, anchored")
    p = Sea()

    def count(joy, tap=False):
        sync(p.m, sym, 0)
        f0 = p.b("FRAME_COUNT")
        for _ in range(200):
            g = (p.b("FRAME_COUNT") - f0) % 256
            p.m.joystick(joy | (FIRE if tap and g % 6 < 2 else 0))
            p.m.run_frames(1)
        p.m.joystick(0)
        return (p.b("FRAME_COUNT") - f0) % 256
    got = {"treading water": count(0), "swimming right": count(R),
           "swimming down, the view stepping": count(D),
           "swimming left": count(L),
           "firing while swimming right": count(R, tap=True),
           "down and right": count(D | R)}
    for k, v in got.items():
        check(f"{k}: 100", v == 100, f"{v}")


def death():
    print("\nA DEATH IN THE WATER, and the restart")
    p = Sea()
    p.go(T(10), Rw(8), picture=False)
    p.m.poke(sym["PLAYER_HP"], 8)
    p.m.poke(sym["OXYGEN"], 0)
    died = False
    for _ in range(600):
        p.frame(0)
        died |= p.b("KARA_STATE") == KST_DIE
        if died and p.b("GAME_STATE") == GS_PLAY and p.b("PLAYER_HP") == 100:
            break
    at = (p.w("KARA_WX"), p.w("KARA_WY"))
    o2 = p.b("OXYGEN")
    p.frames(2, 0)                          # ACT_UPDATE has run on it
    check("she drowns, and the level comes back",
          died and p.b("PLAYER_HP") == 100 and p.b("KARA_STATE") == KST_SWIM,
          f"died {died}, HP {p.b('PLAYER_HP')}, state {p.b('KARA_STATE')}")
    check("... at her start, with a full breath",
          at == (T(6), Rw(2)) and o2 == sym["OXY_MAX"],
          f"{at}, O2 {o2}")


def main():
    p = the_box()
    physics(p)
    gun(p)
    box_control()
    air()
    the_cables()
    bite()
    the_route()
    lock()
    death()
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
