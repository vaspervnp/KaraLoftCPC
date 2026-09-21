#!/usr/bin/env python3
"""Going to the NEXT level, which is a map read and usually nothing else.

A LEVEL IS A MAP AND AN ENVIRONMENT IS A BANK SET (CLAUDE.md 8.1). The
art is 16-20 KB and about 1.6 s off the disc; a map is 358 packed bytes,
ONE SECTOR. So four levels share an environment's art and three of the
four transitions between them cost a sector - which is the whole reason
LEVEL_GOTO takes the environment out of the level's OWN header instead
of reloading whatever it is given.

WHAT THIS SUITE DRIVES is that claim from both sides:

  * the same environment          LEVEL_ENV must NOT move, and the art
                                  in bank C4 must be the same bytes
  * a different environment       LEVEL_ENV must move, and C4 must hold
                                  the other environment's tiles

Without the second one the first proves nothing: a LEVEL_GOTO that
never loaded art at all would pass it.

AND WHAT SHE CARRIES IS THE OTHER HALF. Health, both magazines and the
reserve cross a door and only a death restores them; this level's own
key does not travel, because a level that started with the last one's
key in her hand is a level whose lock is already open.

It writes its own levels into build/ and relinks, the way
tools/test_painter.py does, so it is LAST in tools/run_tests.sh with
that one. It restores build/ with a full ./build.sh whatever happens
and checks the shipped disc comes back byte for byte.
"""
import hashlib
import os
import struct
import shutil
import subprocess
import sys

sys.path.insert(0, "/home/vasilhs/cpcemu")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bench import symbols, boot, sync, STUB                     # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
BUILD = os.path.join(ROOT, "build")
GS_CLEAR = 2
LVL_ID, LVL_TILESET = 3, 9
MADE = ("level_2.lvl", "level_5.lvl", "tileflags_level2_forest.bin")

fails = []


def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}{'  ' + detail if detail else ''}")
    if not ok:
        fails.append(name)


def run(*cmd):
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        print(r.stdout[-3000:], r.stderr[-3000:])
        raise SystemExit(f"{' '.join(cmd)} failed")


def make_levels():
    """Two more levels, as test DATA rather than as design.

    level_2 is the City again with her start moved sixteen tiles along
    and a stripe of `void` laid across the wall - two things a peek can
    tell from level 1 without reading the whole map. level_5 is the
    FOREST's number and the forest's tileset with the same map in it:
    it looks like nothing, and what it is for is the environment byte.
    """
    src = bytearray(open(os.path.join(BUILD, "level_1.lvl"), "rb").read())
    off_map, off_ent = struct.unpack("<HH", src[13:17])
    assert src[LVL_TILESET] == 1

    two = bytearray(src)
    two[LVL_ID] = 2
    two[off_ent + 1:off_ent + 3] = struct.pack("<H", 86 + 16 * 8)
    for k in range(64):
        two[off_map + 12 * 128 + 4 + k] = 1          # `void`, and nothing else
    open(os.path.join(BUILD, "level_2.lvl"), "wb").write(bytes(two))

    five = bytearray(src)
    five[LVL_ID] = 5
    five[LVL_TILESET] = 2                            # ... the forest's art
    open(os.path.join(BUILD, "level_5.lvl"), "wb").write(bytes(five))
    # ... which needs a flags file of its own, and an empty one will do:
    # nothing here walks on it.
    open(os.path.join(BUILD, "tileflags_level2_forest.bin"), "wb").write(bytes(51))
    return two, off_map


def call(m, sym, name, a=0):
    """One routine, from a DI stub, with A set."""
    code = bytes([0xF3, 0x3E, a, 0xCD, sym[name] & 0xFF, sym[name] >> 8, 0x18, 0xFE])
    m.write_ram(STUB, code)
    m.set_pc(STUB)
    for _ in range(4000000):
        m.run_us(1)
        if m.pc == STUB + len(code) - 2:
            return True
    return False


def tiles_in_c4(m, sym, n=512):
    """The first n bytes of the tile blob, read through the gate array.

    peek AND NOT read_ram: cpc.py's read_ram is base RAM and hands back
    bank 1 at &4000 whatever is selected, which is the trap that made a
    whole picture check vacuous once (CLAUDE.md 8.3).

    AND IT SPENDS THE MACHINE. There is no bank selection in cpc.py, so
    the only way to page C4 is to run BANK_SET_C4 - and running anything
    from a stub leaves the PC parked in the stub's own spin with the
    registers the routine left. Every caller here does it LAST, and the
    machine goes in the bin afterwards; the first version of this suite
    did it in the middle and measured a game that had stopped.
    """
    call(m, sym, "BANK_SET_C4")
    return bytes(m.peek(0x4000 + k) for k in range(n))


def clear_to_next(m, sym, want, limit=900):
    """Open the way out, and count the hardware frames it takes."""
    m.poke(sym["GAME_STATE"], GS_CLEAR)
    for f in range(limit):
        m.run_frames(1)
        if m.peek(sym["GAME_STATE"]) == 0 and m.peek(sym["LEVEL_CUR"]) == want:
            return f
    return None


def main():
    sym = symbols()
    saved = os.path.join(BUILD, "_transition_saved")
    os.makedirs(saved, exist_ok=True)
    shipped = hashlib.md5(
        open(os.path.join(BUILD, "kara.dsk"), "rb").read()).hexdigest()

    print("\n  two more levels into build/, and a disc made of them:")
    two, off_map = make_levels()
    try:
        run(os.path.join(ROOT, "build.sh"), "--relink")
        city = open(os.path.join(BUILD, "levels", "level1_city",
                                 "citytiles.bin"), "rb").read()[:512]
        forest = open(os.path.join(BUILD, "levels", "level2_forest",
                                   "foresttiles.bin"), "rb").read()[:512]
        check("the two environments' tiles are not the same bytes",
              city != forest, "which is what the art check below reads")

        m = boot(sym, scroll=True)
        m.run_frames(20)
        check("it booted on level 1 of environment 1",
              m.peek(sym["LEVEL_CUR"]) == 0 and m.peek(sym["LEVEL_ENV"]) == 0
              and m.peek(sym["LEVEL_OK"]) == 1,
              f"LEVEL_CUR {m.peek(sym['LEVEL_CUR'])}, "
              f"LEVEL_ENV {m.peek(sym['LEVEL_ENV'])}")
        # ---- spend something, and pick something up ----------------
        # A poke is a fair question here: what is asked is whether the
        # door keeps them, not whether she can get into that state.
        m.poke(sym["PLAYER_HP"], 61)
        m.poke(sym["AMMO_RESERVE"], 9)
        m.poke(sym["MAG_LEFT"], 3)
        m.poke(sym["KEYS_COUNT"], 1)

        print("\n  ... and through the door, inside one environment:")
        frames = clear_to_next(m, sym, 1)
        check("she arrives in the next level", frames is not None,
              f"{frames} hardware frames, fade and all" if frames else
              "GAME_STATE never came back to GS_PLAY")
        check("LEVEL_CUR is the level after it",
              m.peek(sym["LEVEL_CUR"]) == 1, f"{m.peek(sym['LEVEL_CUR'])}")
        check("... and LEVEL_ENV did NOT move", m.peek(sym["LEVEL_ENV"]) == 0,
              "one sector read, and no 1.6 s of art")

        # ---- the map really is the OTHER level's -------------------
        want = bytes(two[off_map:off_map + 2048])
        got = bytes(m.read_ram(sym["MAP_ADDR"], 2048))
        bad = sum(1 for a, b in zip(want, got) if a != b)
        # The pickups ENT_BAKE stamps into scratch tiles are the cells
        # where RAM and file are meant to differ (CLAUDE.md 8.3).
        check("the map in RAM is level 2's", bad <= 8,
              f"{bad} of 2,048 bytes differ, which is the pickup bake")
        check("... and it is not level 1's",
              got[12 * 128 + 4:12 * 128 + 12] == bytes([1] * 8),
              "the stripe level 2 has and level 1 has not")
        check("she is where level 2 says, not where level 1 did",
              (m.peek(sym["KARA_WX"]) | m.peek(sym["KARA_WX"] + 1) << 8) == 107,
              f"KARA_WX {m.peek(sym['KARA_WX']) | m.peek(sym['KARA_WX']+1) << 8}, "
              f"which is the record's 214 world pixels")

        # ---- what crossed the door, and what did not ---------------
        print("\n  ... and what she took with her:")
        check("her health crossed it", m.peek(sym["PLAYER_HP"]) == 61,
              f"{m.peek(sym['PLAYER_HP'])} of 100 - a door is not a medkit")
        check("her reserve crossed it", m.peek(sym["AMMO_RESERVE"]) == 9,
              f"{m.peek(sym['AMMO_RESERVE'])}")
        check("... and what was in the gun", m.peek(sym["MAG_LEFT"]) == 3,
              f"{m.peek(sym['MAG_LEFT'])}")
        check("the LAST level's key did not", m.peek(sym["KEYS_COUNT"]) == 0,
              "a key opens one garage")
        check("and no round is left in the air from the old screen",
              m.peek(sym["BUL_LIVE"]) == 0 and m.peek(sym["BUL_TOP"]) == 0)

        # ---- and what is really in the banks, which spends m -------
        check("... and bank C4 still holds the CITY's tiles",
              tiles_in_c4(m, sym) == city,
              "512 bytes of the blob, through the gate array - so "
              "LEVEL_ENV is a fact about the banks and not a byte")

        # ---- a DIFFERENT environment, which is the control ---------
        # On its own machine, because reading a bank spends one.
        print("\n  and the control - a level of another environment:")
        m3 = boot(sym, scroll=True)
        m3.run_frames(20)
        check("LEVEL_GOTO returned for level 5", call(m3, sym, "LEVEL_GOTO", 4))
        check("LEVEL_ENV moved to the forest", m3.peek(sym["LEVEL_ENV"]) == 1,
              f"{m3.peek(sym['LEVEL_ENV'])}, which is environment 2 zero based")
        check("... and bank C4 holds the FOREST's tiles now",
              tiles_in_c4(m3, sym) == forest,
              "so the check above is not passing on a routine that never "
              "loads art at all")

        # ---- off the end of what anybody has painted ---------------
        print("\n  and off the end of the painted levels:")
        m2 = boot(sym, scroll=True)
        m2.run_frames(20)
        m2.poke(sym["PLAYER_HP"], 40)
        m2.poke(sym["AMMO_RESERVE"], 2)
        clear_to_next(m2, sym, 1)
        m2.poke(sym["GAME_STATE"], GS_CLEAR)
        back = None
        for f in range(1200):
            m2.run_frames(1)
            if m2.peek(sym["LEVEL_CUR"]) == 0 and m2.peek(sym["GAME_STATE"]) == 0:
                back = f
                break
            if f > 200:                      # the title waits for a press
                m2.joystick(0x10); m2.run_frames(2); m2.joystick(0)
        check("level 3 is not painted, so it goes back to the first",
              back is not None, f"after {back} hardware frames and a title"
              if back is not None else "it never came back")
        check("... and THAT is a full reset, not a transition",
              m2.peek(sym["PLAYER_HP"]) == 100
              and m2.peek(sym["AMMO_RESERVE"]) == 28,
              f"HP {m2.peek(sym['PLAYER_HP'])}, "
              f"reserve {m2.peek(sym['AMMO_RESERVE'])} - starting the game "
              f"over is not walking through a door")
    finally:
        print("\n  putting build/ back:")
        for name in MADE:
            p = os.path.join(BUILD, name)
            if os.path.exists(p):
                os.remove(p)
        shutil.rmtree(saved, ignore_errors=True)
        run(os.path.join(ROOT, "build.sh"))
        got = hashlib.md5(
            open(os.path.join(BUILD, "kara.dsk"), "rb").read()).hexdigest()
        check("the shipped disc is back, byte for byte", got == shipped,
              f"md5 {got[:12]}")

    print()
    if fails:
        print(f"FAILED: {len(fails)} check(s): " + ", ".join(sorted(set(fails))))
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
