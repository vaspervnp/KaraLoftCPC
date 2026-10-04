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

IT RUNS ON THE SHIPPED DISC NOW, AND IT USED TO WRITE ITS OWN. Until
level 2 existed there was no second level in any environment, so this
suite made one - level 1 with a stripe across its wall - and a fake
level 5, relinked, and rebuilt the shipped disc afterwards. Both of
those numbers are real levels now, and a suite that overwrote them
would be measuring a level that does not ship: the City's level 2 is
the same-environment case and the forest's level 5 the control, as
they come off the disc. Nothing is written into build/, and the md5 at
the end says so.
"""
import hashlib
import os
import struct
import sys

sys.path.insert(0, "/home/vasilhs/cpcemu")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bench import symbols, boot, sync, STUB                     # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
BUILD = os.path.join(ROOT, "build")
GS_CLEAR = 2
LVL_ID, LVL_TILESET = 3, 9

fails = []


def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}{'  ' + detail if detail else ''}")
    if not ok:
        fails.append(name)


def levels():
    """Levels 1, 2 and 5 as the build wrote them, and where each one's map
    and entity table start."""
    out = {}
    for n in (1, 2, 5):
        blob = open(os.path.join(BUILD, f"level_{n}.lvl"), "rb").read()
        off_map, off_ent = struct.unpack("<HH", blob[13:17])
        out[n] = (blob, off_map, off_ent)
    assert out[1][0][LVL_TILESET] == out[2][0][LVL_TILESET] == 1
    assert out[5][0][LVL_TILESET] == 2
    return out


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
    shipped = hashlib.md5(
        open(os.path.join(BUILD, "kara.dsk"), "rb").read()).hexdigest()
    lv = levels()
    two, off_map, off_ent = lv[2]
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
    one, om1, _ = lv[1]
    other = sum(1 for a, b in zip(one[om1:om1 + 2048], got) if a != b)
    check("... and it is not level 1's", other > 500,
          f"{other} of 2,048 bytes are not level 1's")
    start = struct.unpack("<H", two[off_ent + 1:off_ent + 3])[0]
    wx = m.peek(sym["KARA_WX"]) | m.peek(sym["KARA_WX"] + 1) << 8
    check("she is where level 2 says, not where level 1 did",
          wx == start // 2 and start // 2 != 43,
          f"KARA_WX {wx}, which is the record's {start} world pixels")

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
    # THE LAST PAINTED LEVEL IS READ OFF build/, because written down
    # it was "level 2" and stopped being true the day level 3 shipped.
    last = 1
    while os.path.exists(os.path.join(BUILD, f"level_{last + 1}.lvl")):
        last += 1
    for lv in range(2, last + 1):
        clear_to_next(m2, sym, lv - 1)
    m2.poke(sym["GAME_STATE"], GS_CLEAR)
    back = None
    for f in range(1200):
        m2.run_frames(1)
        if m2.peek(sym["LEVEL_CUR"]) == 0 and m2.peek(sym["GAME_STATE"]) == 0:
            back = f
            break
        if f > 200:                      # the title waits for a press
            m2.joystick(0x10); m2.run_frames(2); m2.joystick(0)
    check(f"level {last + 1} is not painted, so it goes back to the first",
          back is not None, f"after {back} hardware frames and a title"
          if back is not None else "it never came back")
    check("... and THAT is a full reset, not a transition",
          m2.peek(sym["PLAYER_HP"]) == 100
          and m2.peek(sym["AMMO_RESERVE"]) == 28,
          f"HP {m2.peek(sym['PLAYER_HP'])}, "
          f"reserve {m2.peek(sym['AMMO_RESERVE'])} - starting the game "
          f"over is not walking through a door")

    got = hashlib.md5(
        open(os.path.join(BUILD, "kara.dsk"), "rb").read()).hexdigest()
    check("nothing was written to the shipped disc", got == shipped,
          f"md5 {got[:12]}")

    print()
    if fails:
        print(f"FAILED: {len(fails)} check(s): " + ", ".join(sorted(set(fails))))
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
