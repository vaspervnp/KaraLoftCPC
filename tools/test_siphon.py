#!/usr/bin/env python3
"""Level 16 on a 6128: the siphon - the sea's way out. CLAUDE.md 8.21.

THE SIPHON PULLS. The artist's note on sea_siphon is "within ~3 tiles
the vortex pulls the heroine towards the hole; touching the throat
triggers the transition", and that is a region of a new kind,
RG_VORTEX, read out of the level's own file: inside it, on two game
frames in four, VORTEX_PULL takes her stick - a direction held away from
the hole is let go, nothing held across is TOWARD it, UP is let go and
nothing held is DOWN. So every probe the water keeps keeps the pull,
and what it costs her is measured in her own speed. With a key, the
throat is the door and the current presses it for her.

Every expectation is read out of something other than the code under
test, and every one has a control:

    the way in     out of level 15's siphon, the current's region out of
                   the FILE, and the whirlpool's six cells over the
                   throat against the artist's sheet, pixel for pixel
    the pull       nothing held, she goes toward the hole's middle half
                   a byte a game frame and DOWN - and with
                   VORTEX_PULL poked to RET she stays where she is and
                   the water lifts her
    against it     holding away from the hole is half her speed, and
                   outside the current it is all of it
    the mines      a mine moored in the current, she put beside it at
                   its height: the current carries her into it - and
                   with the current off, it does not
    the throat     no key: held at the grate, and UP takes her out; a
                   key: the level clears the frame her box meets the
                   throat, nothing pressed - and with no key in her
                   pocket the same place clears nothing
    the route      from the surface past two cables, the key off the
                   floor, and down into the current from above, every
                   on-screen cell the map's on every game frame
    the lock       game frames per 200 hardware frames, in the current
    the cost       VORTEX_PULL from a DI stub, in it and out of it
"""
import os
import re
import sys

sys.path.insert(0, "/home/vasilhs/cpcemu")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bench import sync                                          # noqa: E402
from make_level import read                                     # noqa: E402
from tilebake import box_pens, sheet_frames                     # noqa: E402
import test_sea as TS                                           # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
BUILD = os.path.join(ROOT, "build")
ART = os.path.join(ROOT, "assets", "sprites", "level4_underwater")
sym = TS.sym
U, D, L, R, FIRE = TS.U, TS.D, TS.L, TS.R, TS.FIRE
GS_PLAY, GS_DEAD, GS_CLEAR = TS.GS_PLAY, TS.GS_DEAD, TS.GS_CLEAR
LEVEL = 16
MAP_W = 32
LVL = read(open(os.path.join(BUILD, f"level_{LEVEL}.lvl"), "rb").read())
TILES = TS.TILES
W = TS.word
ROW_SAND = 62

fails = []


def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}{'  ' + detail if detail else ''}")
    if not ok:
        fails.append(name)


def regions():
    """(kind, x, y, w, h) of every region, out of the FILE."""
    raw = open(os.path.join(BUILD, f"level_{LEVEL}.lvl"), "rb").read()
    off = raw[19] | raw[20] << 8
    n = raw[12]
    return [(raw[off + 7 * i], raw[off + 7 * i + 1], raw[off + 7 * i + 3],
             raw[off + 7 * i + 5], raw[off + 7 * i + 6]) for i in range(n)]


VORTEX = [r for r in regions() if r[0] == sym["RG_VORTEX"]]


def door():
    """The siphon's record: its tile column, out of the FILE."""
    e = LVL["entity_bytes"]
    for i in range(0, len(e), 8):
        if e[i] == sym["EK_DOOR"]:
            return (e[i + 1] | e[i + 2] << 8) // 8
    return None


def mines():
    e = LVL["entity_bytes"]
    return [((e[i + 1] | e[i + 2] << 8) // 8, (e[i + 3] | e[i + 4] << 8) // 16 - 1)
            for i in range(0, len(e), 8)
            if e[i] == sym["EK_HAZARD"] and e[i + 6] == sym["HZ_MINE"]]


class Siphon(TS.Sea):
    def __init__(self, before=None):
        TS.LEVEL = LEVEL
        super().__init__(before=before)

    def frame(self, joy=0, picture=False):
        """test_sea's frame, with the picture checked only while the level
        is being played: past GS_CLEAR the fade and the next level's
        install are on the screen, and they are not this map."""
        TS.Sea.frame(self, joy, picture and self.b("GAME_STATE") == GS_PLAY)

    def go(self, tx, ty, limit=600, picture=True):
        """test_sea's go(), stopping when the level is over."""
        for _ in range(limit):
            if self.b("GAME_STATE") != GS_PLAY:
                break
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

    def put(self, wx, wy, keys=0):
        """Her box's top left at (wx bytes, wy lines), and a frame for the
        camera to find her."""
        m = self.m
        m.poke(sym["KEYS_COUNT"], keys)
        m.poke(sym["KARA_WX"], wx & 255)
        m.poke(sym["KARA_WX"] + 1, wx >> 8)
        m.poke(sym["KARA_WY"], wy & 255)
        m.poke(sym["KARA_WY"] + 1, wy >> 8)
        m.poke(sym["OXYGEN"], 99)

    def track(self, n, joy=0):
        out = []
        for _ in range(n):
            self.frame(joy)
            out.append((self.w("KARA_WX"), self.w("KARA_WY"),
                        self.b("PLAYER_HP"), self.b("GAME_STATE")))
        return out


def middle_col(wx):
    return (wx + sym["SWIM_BOX_W"] // 2) // 4


# =====================================================================
def way_in():
    print("\nTHE WAY IN: out of level 15's siphon, and the current")
    p = Siphon()
    check("level 16 is the sea's last map, one sector and no art",
          p.took is not None and p.took < 200 and p.b("LEVEL_OK") == 1
          and p.b("LEVEL_ENV") == 3 and p.b("LEVEL_CUR") == LEVEL - 1,
          f"{p.took} hardware frames, LEVEL_ENV {p.b('LEVEL_ENV')}, "
          f"LEVEL_CUR {p.b('LEVEL_CUR')}")
    s = door()
    v = VORTEX[0] if VORTEX else None
    check("one region of the current, centred on the siphon's hole and "
          "down to the sand",
          len(VORTEX) == 1 and s is not None
          and v[1] + v[3] // 2 == s + 2 and v[2] + v[4] == ROW_SAND,
          f"{VORTEX}, the throat at tile {s} - its middle column "
          f"{v[1] + v[3] // 2 if v else '-'}, the hole's {s + 2 if s else '-'}")

    # THE WHIRLPOOL'S TOP HALF, over the water above the throat: six map
    # cells, each a tile of the blob whose pixels are the artist's swirl
    # frame 0 where it is opaque and the deep water where it is not.
    sheet, boxes = sheet_frames(ART, "sea_siphon_cpc_mode0_sheet")
    b = boxes[0]
    swirl = box_pens(sheet, b["x"], b["y"], b["w"], b["h"], alpha=True)
    tsheet, tboxes = sheet_frames(ART, "sea_tiles_cpc_mode0_sheet")
    names, t = TS_names()
    deep = tboxes[t["bg_deep"]]
    under = box_pens(tsheet, deep["x"], deep["y"], deep["w"], deep["h"])
    m = p.m
    row = ROW_SAND - 1
    wrong, total = 0, 0
    first = s - 1 if s is not None else 0       # rim_l's column
    for k in range(6):
        idx = m.peek(sym["MAP_ADDR"] + row * MAP_W + first + k)
        for y in range(16):
            for x in range(8):
                o = swirl[y][8 * k + x]
                want = o if o is not None else under[y][x]
                got = pen_of(idx, x, y)
                total += 1
                wrong += got != want
    check("the whirlpool's six cells over the throat are the artist's "
          "swirl over the deep water", wrong == 0,
          f"{wrong} of {total} pixels wrong")
    return p


def TS_names():
    sys.path.insert(0, HERE)
    import make_sea_map as MS
    return MS.tile_names()


def pen_of(idx, x, y):
    """Pixel (x, y) of tile `idx` of the blob on the disc - column-major,
    two pixels a byte (6.3)."""
    byte = TILES[idx * 64 + (x // 4) * 32 + y * 2 + (x % 4) // 2]
    left = (x % 2) == 0
    sh = 1 if left else 0
    p = (((byte >> (6 + sh)) & 1) | ((byte >> (2 + sh)) & 1) << 1
         | ((byte >> (4 + sh)) & 1) << 2 | ((byte >> (0 + sh)) & 1) << 3)
    return p


def pull():
    print("\nTHE PULL: nothing held, toward the hole and down")
    v = VORTEX[0]
    mid = v[1] + v[3] // 2
    wx = (v[1] + 1) * 4                     # her middle two tiles in
    wy = (ROW_SAND - 2) * 16                # low, under the mines

    def run(before=None):
        p = Siphon(before=before)
        p.put(wx, wy)
        p.frames(2)
        x0, y0 = p.w("KARA_WX"), p.w("KARA_WY")
        tr = p.track(20)
        return x0, y0, tr
    x0, y0, tr = run()
    dx, dy = tr[-1][0] - x0, tr[-1][1] - y0
    check("nothing held, the current takes her toward the hole's middle "
          "half a byte a game frame", dx == 10,
          f"{dx} bytes in 20 game frames, middle column "
          f"{middle_col(x0)} -> {middle_col(tr[-1][0])} of {mid}")
    floor = (ROW_SAND * 16) - sym["SWIM_BOX_H"]
    # AT THE SAND THE WATER STILL LIFTS HER on one frame in four, so she
    # rides a line off it and back: within one line of the floor.
    check("... and down three quarters of a line a game frame, to the sand",
          floor - 1 <= tr[-1][1] <= floor and tr[7][1] - y0 == 6,
          f"WY {y0} -> {tr[7][1]} in 8 -> {tr[-1][1]}, the sand at {floor}")
    c0, cy0, ctr = run(lambda m: m.poke(sym["VORTEX_PULL"], 0xC9))
    check("... and with VORTEX_PULL poked to RET she stays where she is "
          "and the water lifts her",
          ctr[-1][0] == c0 and ctr[-1][1] < cy0,
          f"{ctr[-1][0] - c0} bytes across, WY {cy0} -> {ctr[-1][1]}")


def against():
    print("\nAGAINST IT: half her speed away from the hole")
    v = VORTEX[0]
    wx = (v[1] + v[3] // 2) * 4             # her middle two tiles right
                                            # of the hole's

    def away(wy):
        p = Siphon()
        p.put(wx, wy)
        p.frames(2)
        x0 = p.w("KARA_WX")
        tr = p.track(20, R)
        return tr[-1][0] - x0
    # IN IT, low and under the mines; OUT OF IT, the same column four rows
    # above its top - so the only thing that differs is the current.
    a, b = away((ROW_SAND - 3) * 16), away((v[2] - 4) * 16)
    check("holding RIGHT, away from the hole, in the current: half a byte "
          "a game frame - and outside it, a byte", a == 10 and b == 20,
          f"{a} bytes in the current, {b} outside it, in 20 game frames")
    p = Siphon()
    p.put((v[1] + v[3] // 2 - 2) * 4, (ROW_SAND - 3) * 16)
    p.frames(2)
    y0 = p.w("KARA_WY")
    tr = p.track(20, U)
    check("... and UP is a line and a quarter a game frame, not two - she "
          "can always swim out", y0 - tr[-1][1] == 25,
          f"{y0 - tr[-1][1]} lines in 20 game frames")


def the_mines():
    print("\nTHE MINES IN IT: carried in from the side")
    v = VORTEX[0]
    inside = [(x, r) for x, r in mines()
              if v[1] <= x < v[1] + v[3] and v[2] <= r < v[2] + v[4]]
    check("the level moors mines in the current, either side of the hole",
          len(inside) == 2 and inside[0][0] < v[1] + v[3] // 2 < inside[1][0],
          f"{inside} in {v}")
    if not inside:
        return
    mx, mr = inside[0]
    wx = (mx - 4) * 4                       # her box ends a tile short of it
    wy = mr * 16

    def run(before=None):
        p = Siphon(before=before)
        p.put(wx, wy)
        tr = p.track(30)
        return min(t[2] for t in tr), p
    hp, p = run()
    check("put beside the left one at its height, the current carries her "
          "into it", hp == 100 - sym["MINE_HURT"],
          f"HP 100 -> {hp}")
    hp, p = run(lambda m: m.poke(sym["VORTEX_PULL"], 0xC9))
    check("... and with the current off, the same place is safe",
          hp == 100, f"HP {hp}")


def throat():
    print("\nTHE THROAT: held without a key, flushed out with one")
    v = VORTEX[0]
    wx = (v[1] + v[3] // 2) * 4 - sym["SWIM_BOX_W"] // 2
    wy = v[2] * 16

    def run(keys, before=None, n=160):
        p = Siphon(before=before)
        p.put(wx, wy, keys)
        tr = p.track(n)
        clear = next((i for i, t in enumerate(tr) if t[3] == GS_CLEAR), None)
        return clear, tr, p
    clear, tr, p = run(0)
    floor = (ROW_SAND * 16) - sym["SWIM_BOX_H"]
    check("no key: she is held at the grate, and nothing clears",
          clear is None and tr[-1][1] == floor,
          f"WY {tr[-1][1]}, the sand at {floor}, state {tr[-1][3]}")
    up = p.track(100, U)
    check("... and UP takes her out of it",
          up[-1][1] + sym["SWIM_BOX_H"] // 2 < v[2] * 16,
          f"WY {tr[-1][1]} -> {up[-1][1]}, the current's top at {v[2] * 16}")
    clear, tr, p = run(1)
    check("a key: the level clears the frame she meets the throat, with "
          "nothing pressed", clear is not None,
          f"GS_CLEAR on game frame {clear}, WY {tr[clear][1] if clear is not None else '-'}")
    c2, tr2, _ = run(1, lambda m: m.poke(sym["VORTEX_PULL"], 0xC9))
    check("... and with the current off, the same key and the same place "
          "clear nothing", c2 is None, f"WY {tr2[-1][1]}")


def route(p):
    """From the surface to the siphon. Each cable is crossed from right
    beside it, the moment it goes off: its quiet is 38 game frames, and
    her 16-byte box takes 20 to clear a 4-byte column, so the run-up has
    to be short. Down the gap past the mine under ledge 30, ACROSS the
    chamber under the spheres, down the left side - outside the current,
    because coming into it from the side at the mines' height is what
    the mines are there for - to the key, and into the current from
    above the hole."""
    T = TS.T
    p.go(T(6), 200)                         # the top chamber's vent
    p.frames(20, 0, True)
    p.go(T(24), 200)                        # the tank
    p.go(T(24), 314)                        # through ledge 16's gap
    p.go(T(18), 314)                        # beside the first cable
    p.cross(15, 19, T(4), 314)
    p.go(T(4), 428)                         # through ledge 23's gap, into
    p.frames(20, 0, True)                   # ... ledge 30's vent
    p.go(T(11), 428)                        # beside the second cable
    p.cross(16, 26, T(24), 428)
    p.go(T(24), 700)                        # past the mine under the gap,
                                            # and the tank
    p.go(T(3), 700)                         # across, under the spheres
    p.go(T(3), 968)                         # down the left: the key
    p.go(T(3), 840)                         # up, with it
    p.go(T(16) - 8, 840)                    # over the hole
    p.go(T(16) - 8, 968)                    # and down into it


def the_route():
    print("\nTHE ROUTE: from the surface, out through the siphon")
    p = Siphon()
    hp = []
    orig = p.frame

    def frame(joy=0, picture=False):
        orig(joy, picture)
        hp.append((p.b("PLAYER_HP"), p.b("GAME_STATE")))
    p.frame = frame
    route(p)
    clear = next((i for i, h in enumerate(hp) if h[1] == GS_CLEAR), None)
    check("she reaches the siphon with the key and the current flushes her "
          "out", clear is not None,
          f"GS_CLEAR on game frame {clear} of {len(hp)}, keys "
          f"{p.b('KEYS_COUNT')}, WX {p.w('KARA_WX')} WY {p.w('KARA_WY')}")
    check("... never touched by anything on the way",
          min(h[0] for h in hp) == 100,
          f"HP at least {min(h[0] for h in hp)}, air {p.b('OXYGEN')}")
    check("every on-screen cell is the map's on every game frame of it",
          not p.wrong, f"{len(p.wrong)} frames: {p.wrong[:3]}")
    m = p.m
    took = None
    for f in range(600):
        m.run_frames(1)
        if (p.b("GAME_STATE") == 0 and p.b("LEVEL_CUR") == 16
                and p.b("LEVEL_OK")):
            took = f + 1
            break
    check("... and it leads to level 17, the desert: an environment away, "
          "and out of the water", took is not None and p.b("LEVEL_ENV") == 4
          and p.b("LEVEL_SWIM") == 0,
          f"{took} hardware frames, LEVEL_ENV {p.b('LEVEL_ENV')}, "
          f"LEVEL_SWIM {p.b('LEVEL_SWIM')}")


def lock():
    print("\nTHE LOCK: game frames in 200 hardware frames, in the current")
    v = VORTEX[0]
    p = Siphon()
    p.put((v[1] + 2) * 4, (ROW_SAND - 3) * 16)
    p.frames(2)

    def count(joy):
        sync(p.m, sym, 0)
        f0 = p.b("FRAME_COUNT")
        for _ in range(100):
            p.m.joystick(joy)
            p.m.run_frames(2)
        p.m.joystick(0)
        return (p.b("FRAME_COUNT") - f0) % 256
    for name, joy in (("carried in, nothing held", 0),
                      ("swimming against it", L),
                      ("swimming up out of it", U)):
        n = count(joy)
        check(f"{name}: 100", n == 100, f"{n}")


def cost():
    print("\nWHAT IT COSTS: VORTEX_PULL from a DI stub")
    import bench
    v = VORTEX[0]
    p = Siphon()
    b = bench.Bench(p.m, sym)
    out = b.T("VORTEX_PULL")
    p.put((v[1] + 2) * 4, (ROW_SAND - 3) * 16)
    p.frames(2)
    b2 = bench.Bench(p.m, sym)
    ins = max(b2.T("VORTEX_PULL"), b2.T("VORTEX_PULL"))
    TS.LEVEL = 15
    q = TS.Sea()
    none = bench.Bench(q.m, sym).T("VORTEX_PULL")
    print(f"  level 16, out of the current {out} T, in it {ins} T; level 15, "
          f"which has none, {none} T")
    check("a level with no current pays a byte's test for it",
          none is not None and none < 40 and q.b("VORTEX_ON") == 0
          and p.b("VORTEX_ON") != 0,
          f"{none} T on level 15, VORTEX_ON {q.b('VORTEX_ON')} there and "
          f"{p.b('VORTEX_ON')} here")
    check("... and the one that has it, under a thousand T a game frame",
          out is not None and ins is not None and max(out, ins) < 1000,
          f"{out} T out of it, {ins} T in it - the region walk, which "
          f"OXY_IN_AIR pays as well")
    # THE CONTROL: the scan poked to RET leaves VORTEX_ON at the 0 the
    # boot gave it, and level 16's current is then nothing at all.
    r = Siphon(before=lambda m: m.poke(sym["VORTEX_SCAN"], 0xC9))
    r.put((v[1] + 1) * 4, (ROW_SAND - 2) * 16)
    r.frames(2)
    x0 = r.w("KARA_WX")
    r.frames(20)
    check("... and with VORTEX_SCAN poked to RET, level 16 has no current",
          r.b("VORTEX_ON") == 0 and r.w("KARA_WX") == x0,
          f"VORTEX_ON {r.b('VORTEX_ON')}, {r.w('KARA_WX') - x0} bytes across "
          f"in 20 game frames")


def editor():
    print("\nTHE EDITOR'S COPY: RegionKind.Vortex")
    src = open(os.path.join(ROOT, "editor", "src", "CpcLevelEditor.Domain",
                            "RegionKind.cs")).read()
    v = re.search(r"Vortex\s*=\s*(\d+)", src)
    check("the editor numbers the current as the engine does",
          v and int(v.group(1)) == sym["RG_VORTEX"],
          f"Vortex = {v and v.group(1)} against RG_VORTEX {sym['RG_VORTEX']}")


def main():
    way_in()
    pull()
    against()
    the_mines()
    throat()
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
