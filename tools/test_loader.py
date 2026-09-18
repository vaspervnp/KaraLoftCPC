#!/usr/bin/env python3
"""The disc's front door: RUN"KARA, the label screen, and the game.

THREE TRANSFORMATIONS ARE CHECKED AT ONCE by comparing video RAM with
the artist's file byte for byte: iDSK's AMSDOS header, BASIC's LOAD at
&C000, and the sixteen INKs the generated loader sets. Its control is
the mistake that looks almost right - comparing against the GAME's own
title picture, which is also a 16 KB Mode 0 screen and which must fail.

And the hold is checked from both ends: left alone the game starts by
itself, and SPACE gets there the better part of nine seconds sooner.
That pair is its own negative control - a loader that ignored the key
would give the same number twice, and one that never waited at all
would give the short number twice.
"""
import os
import re
import sys

sys.path.insert(0, "/home/vasilhs/cpcemu")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cpc import CPC                                              # noqa: E402
from bench import symbols                                        # noqa: E402
import make_loader                                               # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
ART = os.path.join(ROOT, "assets")
BUILD = os.path.join(ROOT, "build")
DSK = os.path.abspath(os.path.join(BUILD, "kara.dsk"))
SCREEN = 0xC000
SCREEN_BYTES = 16384

fails = []


def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  {detail}" if detail
                                                      else ""))
    if not ok:
        fails.append(name)


def boot_loader(m):
    m.run_frames(150)
    m.insert_disc(DSK)
    m.type_text('RUN"KARA\n')


def frames_to_title(sym, press_at=None, hold=30, limit=1400):
    """Frames from RUN"KARA to the game's own title being up.

    THE SIGNAL IS INTRO_BLINK MOVING, not a resting value: it is bumped
    once a frame by INTRO_WAIT and by nothing else (tools/cpcboot.py),
    so it does not depend on how long either disc read took.
    """
    m = CPC()
    boot_loader(m)
    blink, prev, seen = sym["INTRO_BLINK"], None, 0
    shot = None
    for f in range(limit):
        m.run_frames(1)
        if press_at is not None:
            if f == press_at:
                m.key_down(" ")
            elif f == press_at + hold:
                m.key_up(" ")
        if f == 260:                        # the label is up and settled
            shot = bytes(m.read_ram(SCREEN, SCREEN_BYTES))
        v = m.peek(blink)
        if prev is not None and (v - prev) & 0xFF == 1 and m.mode == 0:
            seen += 1
            if seen >= 3:
                return f, shot
        else:
            seen = 0
        prev = v
    return None, shot


def main():
    sym = symbols()
    print("\n  the loader is the artist's palette note, not a copy of it:")
    bas = open(os.path.join(BUILD, "kara.bas")).read()
    got = {int(p): int(v) for p, v in re.findall(r"INK (\d+),(\d+)", bas)}
    want = {p: v for p, v in enumerate(make_loader.inks())}
    # ... and the note itself carries a worked BASIC line, which is a
    # third opinion neither the tool nor the .bas derives from the other
    line = [ln for ln in open(os.path.join(ART, "revive8b.txt"))
            if ln.startswith("BASIC:")][0]
    noted = {int(p): int(v) for p, v in re.findall(r"INK (\d+),(\d+)", line)}
    check("all sixteen INKs are the note's", got == want == noted,
          f"{len(got)} pens, and the note's own BASIC line agrees")
    check("MEMORY comes before there is a variable to lose",
          bas.index("MEMORY") < bas.index("t=TIME"),
          "LOAD\"GAME.BIN\" lands at &4000, above a HIMEM of &3FFF")

    print("\n  RUN\"KARA puts the label screen up:")
    art = open(os.path.join(ART, "revive8b.scr"), "rb").read()
    left, shot = frames_to_title(sym)
    wrong = sum(1 for a, b in zip(shot, art) if a != b)
    check("video RAM is the artist's file, byte for byte", wrong == 0,
          f"{wrong} wrong of {SCREEN_BYTES} - the AMSDOS header, BASIC's "
          f"LOAD at &C000 and the file itself, all three at once")

    # THE CONTROL IS THE MISTAKE THAT LOOKS ALMOST RIGHT. The game's own
    # title is a 16 KB Mode 0 screen too, so a check that passed against
    # either would be proving nothing about WHICH picture came up.
    other = open(os.path.join(BUILD, "intro.bin"), "rb").read()
    agree = sum(1 for a, b in zip(shot, other) if a == b)
    check("... and it is NOT the game's own title picture",
          agree < SCREEN_BYTES // 2,
          f"{agree} of {SCREEN_BYTES} bytes agree with intro.bin by "
          f"coincidence, which is what stops the check above passing "
          f"either way")

    print("\n  the hold, from both ends:")
    pressed, _ = frames_to_title(sym, press_at=300)
    check("left alone the game starts by itself", left is not None,
          f"the title is up {left} frames in ({left / 50:.1f} s), which is "
          f"the ten-second hold plus both disc reads")
    check("and SPACE gets there sooner", pressed is not None
          and left - pressed > 400,
          f"{pressed} frames ({pressed / 50:.1f} s) against {left} - the "
          f"press saves {(left - pressed) / 50:.1f} s of a {make_loader.HOLD_SECONDS}s hold")

    print()
    if fails:
        print(f"FAILED: {len(fails)} check(s): " + ", ".join(fails))
        sys.exit(1)
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
