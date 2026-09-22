#!/usr/bin/env python3
"""A level NOBODY PAINTED, played on a 6128.

The editor can fill an empty project in with a level - floors, a shaft
from each one down to the next, the records - and every check on that is
one piece of software reading another's output: the validator says
nothing, and a flood fill over the C# model says she can reach every
pickup. Neither of them is the heroine getting to the bottom of it.

So this is the same shape as tools/test_painter.py one step further on:
the CLI generates a 32x64 level, it goes into build/, the disc is
relinked and a 6128 is booted off it - and then the joystick is driven,
floor by floor, until she is standing on the bottom one.

WHAT MAKES IT A CHECK AND NOT A DEMO IS THAT NOTHING HERE KNOWS WHERE
THE GENERATOR PUT ANYTHING. The shaft's column on each floor is read out
of the level's OWN map through the engine's own TILE_ATTR, so the driver
follows whatever was laid out; if the generator moved its ladders
tomorrow this would follow them, and if it laid down a shaft she cannot
reach it would stop there and say which floor.

AND THE DRONE IS 8.7's WIDENING BEING EXERCISED BY A LEVEL NOBODY BUILT
BY HAND. It goes on the floors in the middle of the descent, which on a
64-row map is past world line 255: its ES_Y is a number a byte cannot
hold, its signed screen Y runs from +488 down through 0 to -264 as the
camera passes it, and on the floor it patrols it sees her and fires.
tools/test_shape.py owns the control for that (ENEMY_Y_HI put back to
the eight-bit reading); what this adds is that it happens in a level a
designer could have made by pressing one button.

TWO CONTROLS, because a descent could be a fall:

  * TA_CLIMB taken off the ladder tile in TILE_ATTR. The same drive then
    gets nowhere at all - which is what says the descent is the
    generator's shafts and not gravity finding a hole.
  * and the drone's damage against a run with ENEMY_LIVE held at 0, so
    "she lost 8 points on that floor" is the drone and not the fall.

It costs two discs and three boots and it writes into build/, so it runs
beside test_painter.py at the end of tools/run_tests.sh and restores
build/ with a full ./build.sh whatever happens.
"""
import hashlib
import os
import shutil
import subprocess
import sys

sys.path.insert(0, "/home/vasilhs/cpcemu")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bench import symbols, boot, raw                           # noqa: E402
from build_levels import zx0                                   # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BUILD = os.path.join(ROOT, "build")
TILES = os.path.join(BUILD, "levels", "level1_city", "citytiles.bin")
DOTNET = "/home/vasilhs/.dotnet/dotnet"
CLI = os.path.join(ROOT, "editor", "src", "CpcLevelEditor.Cli")
SCRATCH = os.environ.get("KARA_SCRATCH") or os.path.join(
    "/tmp", f"kara-generated-{os.getuid()}")

EXPORTED = {
    "level_1.lvl": BUILD,
    "tileflags_level1_city.bin": BUILD,
    "city_baked.json": BUILD,
    "citytiles.bin": os.path.dirname(TILES),
}
WIDTH = 32                              # ... so the map is 32 x 64
TA_SOLID, TA_CLIMB = 1, 8
JOY = {"right": 0x08, "left": 0x04, "down": 0x02}

fails = []


def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}{'  ' + detail if detail else ''}")
    if not ok:
        fails.append(name)


def run(*args):
    r = subprocess.run(args, capture_output=True, text=True, cwd=ROOT)
    if r.returncode:
        raise SystemExit(f"{' '.join(args)}:\n{r.stdout}{r.stderr}")
    return r.stdout


def generate(out):
    """The editor's four files, with the map filled in by the generator."""
    shutil.rmtree(out, ignore_errors=True)
    return run(DOTNET, "run", "--project", CLI, "-v", "q", "--", "export",
               "--out", out, "--width", str(WIDTH), "--generate")


class Play:
    """The running game, in the units the level is written in."""

    def __init__(self, sym, disc=None):
        self.sym, self.m = sym, boot(sym, scroll=True, disc=disc)
        lvl = self.m.read_ram(sym["LEVEL_LVL"], 21)
        self.w = lvl[5] | lvl[6] << 8
        self.h = lvl[7] | lvl[8] << 8
        self.map = bytes(self.m.read_ram(sym["LEVEL_LVL"] + 21, self.w * self.h))
        self.attr = bytes(self.m.read_ram(sym["TILE_ATTR"], sym["TILE_ATTR_N"]))

    def word(self, name):
        a = self.sym[name]
        return self.m.peek(a) | self.m.peek(a + 1) << 8

    def byte(self, name):
        return self.m.peek(self.sym[name])

    def is_floor(self, row):
        """A row the generator drew a FLOOR on, rather than one the shaft
        passes through: solid nearly all the way across, which leaves room
        for the ladder's own column and the three tiles of a hole."""
        solid = sum(1 for x in range(self.w)
                    if self.attr[self.map[row * self.w + x]] & TA_SOLID)
        return solid > self.w - 6

    def shafts(self, row):
        """The columns on `row` the ENGINE would call a ladder."""
        return [x for x in range(self.w)
                if self.attr[self.map[row * self.w + x]] & TA_CLIMB]

    def row(self):
        """The map row her feet are on: KARA_WY is the TOP of a 64-line box."""
        return (self.word("KARA_WY") + 64) // 16

    def column(self):
        """The tile column CLIMB_AT probes - the middle of her six-byte box."""
        return (self.word("KARA_WX") + 3) // 4

    def walk_to(self, column, frames=400):
        for _ in range(frames):
            if self.column() == column:
                break
            self.m.joystick(JOY["right"] if self.column() < column else JOY["left"])
            self.m.run_frames(1)
        self.m.joystick(0)
        self.m.run_frames(2)
        return self.column() == column

    def climb_down(self, frames=600):
        """DOWN until the next floor catches her, or she is not moving."""
        was, still, from_row = self.word("KARA_WY"), 0, self.row()
        self.m.joystick(JOY["down"])
        for _ in range(frames):
            self.m.run_frames(1)
            now = self.word("KARA_WY")
            still = still + 1 if now == was else 0
            was = now
            if still >= 25 and self.row() > from_row:
                break
        self.m.joystick(0)
        self.m.run_frames(6)
        return self.row()


def descend(p, report=True):
    """Down every shaft the level has, and where she got to."""
    landings, hurt = [p.row()], {}
    for _ in range(p.h // 4):
        row, before = p.row(), p.byte("PLAYER_HP")
        shafts = p.shafts(row)
        if not shafts:
            break                       # the bottom floor: no way down
        if not p.walk_to(shafts[0]):
            print(f"      could not reach the shaft at tile {shafts[0]} on "
                  f"row {row}, stopped at {p.column()}")
            break
        if p.climb_down() == row:
            print(f"      row {row}: DOWN did not take her off it")
            break
        landings.append(p.row())
        hurt[row] = before - p.byte("PLAYER_HP")
        if report:
            print(f"      floor {row:2d} -> {p.row():2d}   "
                  f"WY {p.word('KARA_WY'):4d}  "
                  f"view ({p.byte('WORLD_X')},{p.byte('WORLD_CR')})  "
                  f"HP {p.byte('PLAYER_HP')}   "
                  f"drone SY {p.word('ENEMY_SY') - 65536 * (p.word('ENEMY_SY') > 32767)}")
    return landings, hurt


def main():
    os.makedirs(SCRATCH, exist_ok=True)
    saved = os.path.join(SCRATCH, "shipped")
    os.makedirs(saved, exist_ok=True)
    for name, src in EXPORTED.items():
        shutil.copy(os.path.join(src, name), os.path.join(saved, name))
    shipped_dsk = hashlib.md5(
        open(os.path.join(BUILD, "kara.dsk"), "rb").read()).hexdigest()
    sym = symbols()

    try:
        print("\n  the editor, asked for a level:")
        made = os.path.join(SCRATCH, "generated")
        said = generate(made).strip().splitlines()
        check("the CLI generated one and said what it made",
              any("generated" in line for line in said),
              next((l.strip() for l in said if "generated" in l), "nothing"))
        for name, dest in EXPORTED.items():
            shutil.copy(os.path.join(made, name), os.path.join(dest, name))
        zx0(TILES)
        run(os.path.join(ROOT, "build.sh"), "--relink")

        print("\n  ... and the machine, booted off a disc made of it:")
        p = Play(sym)
        check("the level installed, in the shape the generator cut",
              p.byte("LEVEL_OK") == 1 and (p.w, p.h) == (WIDTH, 2048 // WIDTH),
              f"LEVEL_OK {p.byte('LEVEL_OK')}, {p.w}x{p.h}, "
              f"ENT_COUNT {p.byte('ENT_COUNT')}")
        # SHE IS STANDING ON A GENERATED FLOOR. The record is placed a row
        # HIGH on purpose - a 64-line box level with the tiles starts
        # inside them (CLAUDE.md 8.6) - so the first thing the level does
        # is drop her 16 pixels onto the floor it drew.
        floors = [r for r in range(p.h) if p.is_floor(r)]
        check("she is standing on the top floor it drew",
              p.row() == floors[0] and p.byte("PLAYER_HP") == 100,
              f"row {p.row()}, WY {p.word('KARA_WY')}, of the floor rows "
              f"{floors} - the last is the ground the shaft ends on")

        print("\n  the descent, with the shafts read off the level's own map:")
        landings, hurt = descend(p)
        # EVERY FLOOR BUT THE GROUND, which is the one she stands ON and
        # never lands on: the generator paints row h-1 as well so the
        # shaft has a bottom.
        expected = [r for r in floors if r < p.h - 1]
        check("SHE GOT TO THE BOTTOM OF IT",
              landings == expected,
              f"floors {landings} - every one the generator drew")
        # V_CR_MAX is PATCHED at install out of the level's own header
        # (CLAUDE.md 8.3), so the assembled symbol is the City's 8 and the
        # number to compare against is this map's.
        v_cr_max = (p.h * 16 - 192) // 8
        check("... and the camera came with her, the whole map",
              p.byte("WORLD_CR") == v_cr_max,
              f"WORLD_CR {p.byte('WORLD_CR')} of {v_cr_max} - the bottom of "
              f"a {p.h}-row map, which is what V_CR_MAX is patched to")

        print("\n  the drone it placed, which is 8.7's own widening:")
        # ENEMIES is the slot's ADDRESS and not a pointer held in it.
        at = sym["ENEMIES"] + sym["ES_Y"]
        es_y = p.m.peek(at) | p.m.peek(at + 1) << 8
        check("its ES_Y is past what a byte reaches",
              es_y > 255 and p.byte("ENEMY_LIVE") == 1,
              f"ES_Y {es_y}, ENEMY_LIVE {p.byte('ENEMY_LIVE')} - and the "
              f"eight-bit reading's own control is in tools/test_shape.py")
        drone_row = next(r for r in floors if r * 16 > es_y)
        took = {row: lost for row, lost in hurt.items() if lost}
        check("... and it saw her and fired, on its own floor and nowhere else",
              len(took) == 1
              and landings[landings.index(next(iter(took))) + 1] == drone_row
              and sum(took.values()) % sym["EBUL_DAMAGE"] == 0,
              f"{sum(took.values())} points on the way down to row "
              f"{drone_row}, in whole EBUL_DAMAGE of {sym['EBUL_DAMAGE']}, "
              f"and nothing on any other floor - which is what says it is "
              f"the drone and not the fall (a ladder is not a fall at all)")

        # ---- the control: the shafts are what carried her --------------
        # A descent could be gravity finding a hole in the floor, and the
        # generator cuts holes. With TA_CLIMB taken off the ladder tile
        # the same drive has to get nowhere.
        print("\n  and with TA_CLIMB taken off the ladder tile:")
        q = Play(sym)
        rung = q.map[floors[0] * q.w + q.shafts(floors[0])[0]]
        # ... in the ENGINE's table only. The driver keeps its own copy,
        # so it still walks her to the shaft and still presses DOWN: what
        # is under test is the engine refusing, not the lookup.
        q.m.poke(sym["TILE_ATTR"] + rung, q.attr[rung] & ~TA_CLIMB)
        blind, _ = descend(q, report=False)
        check("she cannot leave the first floor",
              blind == [floors[0]],
              f"floors {blind} against {landings} with the rung as the "
              f"generator marked it")
    finally:
        print("\n  putting build/ back:")
        for name, dest in EXPORTED.items():
            shutil.copy(os.path.join(saved, name), os.path.join(dest, name))
        run(os.path.join(ROOT, "build.sh"))
        back = hashlib.md5(
            open(os.path.join(BUILD, "kara.dsk"), "rb").read()).hexdigest()
        check("the shipped disc is back, byte for byte", back == shipped_dsk,
              f"md5 {back[:12]}")

    print()
    if fails:
        print(f"FAILED: {len(fails)} check(s): " + ", ".join(sorted(set(fails))))
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
