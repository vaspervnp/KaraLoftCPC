#!/usr/bin/env python3
"""The disc's front door: the label screen, then the game.

`RUN"KARA` puts REVIVE8BIT's screen up, holds it for ten seconds or
until SPACE, and then loads the game exactly the way disc.bas does.

WHY IT IS GENERATED AND NOT WRITTEN BY HAND. The screen comes with a
palette note - sixteen firmware inks, one per pen - and that note is
the artist's, not the loader's. Typed into the .bas once, a re-exported
picture would come up in the last one's colours and nothing would say
so; read off the note, a re-export re-writes the loader. It is the same
rule the HUD's cells and the title's crop already follow (CLAUDE.md 7).

WHY BASIC AND NOT THE ENGINE. The engine disables both ROMs before it
runs (CLAUDE.md 4) and drives the disc itself, so a picture shown from
inside it would cost a place in the bank map and a read through
src/disc.asm. Shown from BASIC it costs one LOAD and nothing at all
afterwards: by the time CALL &4000 happens, BASIC and its screen are
both gone.
"""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
ART = os.path.join(ROOT, "assets")
BUILD = os.path.join(ROOT, "build")

SPLASH = "revive8b"             # ... and REVIVE8B.SCR on the disc
SCREEN_BYTES = 16384            # a whole CPC screen: &C000 to the top of RAM
SCREEN_ADDR = 0xC000

# TIME COUNTS IN 1/300 s, which is the 300 Hz interrupt the gate array
# delivers (CLAUDE.md 9) and not the 50 Hz frame.
HOLD_SECONDS = 10
TICKS_PER_SECOND = 300
KEY_SPACE = 47                  # ... and INKEY returns -1 while it is up


def inks():
    """The firmware ink per pen, off the artist's own palette note.

    The note is a table with a header line and a worked BASIC example
    under it; only the sixteen rows have `pen firmware &hardware' in
    that order, so the pattern picks them out and nothing else.
    """
    rows = {}
    for line in open(os.path.join(ART, SPLASH + ".txt")):
        m = re.match(r"\s*(\d+)\s+(\d+)\s+&([0-9A-Fa-f]{2})\s", line)
        if m:
            pen, firmware, hw = int(m[1]), int(m[2]), int(m[3], 16)
            assert 0 <= firmware <= 26, (pen, firmware)
            # The note gives the hardware byte as well, and the two have
            # to be the same colour or one of them is a typo - the same
            # check make_intro.py makes on the title's palette.
            assert 0x40 <= hw <= 0x5F, (pen, hw)
            rows[pen] = firmware
    assert sorted(rows) == list(range(16)), sorted(rows)
    return [rows[p] for p in range(16)]


def main():
    scr = os.path.join(ART, SPLASH + ".scr")
    n = os.path.getsize(scr)
    if n != SCREEN_BYTES:
        raise SystemExit(f"{SPLASH}.scr is {n} bytes and a whole screen is "
                         f"{SCREEN_BYTES} - it cannot be loaded at "
                         f"&{SCREEN_ADDR:04X}")

    ink = inks()
    half = 8                    # eight INKs to a line keeps both well
    lines = []                  # inside BASIC's 255-character limit

    # MEMORY FIRST, BEFORE THERE IS A VARIABLE TO LOSE. It drops HIMEM
    # to just under the game's load address so that LOAD"GAME.BIN" at
    # &4000 lands above BASIC's stack instead of through it.
    lines.append("10 MODE 0:BORDER 0:MEMORY &3FFF")
    for i in range(0, 16, half):
        lines.append(f"{20 + i // half * 10} " + ":".join(
            f"INK {p},{ink[p]}" for p in range(i, i + half)))
    lines.append(f'40 LOAD"{SPLASH.upper()}.SCR",&{SCREEN_ADDR:04X}')

    # THE COUNT STARTS AFTER THE LOAD AND NOT BEFORE IT. Interrupts are
    # off for the disc read, so TIME stands still through it; started
    # first, the ten seconds would be ten seconds minus the read.
    lines.append(f"50 t=TIME+{HOLD_SECONDS * TICKS_PER_SECOND}")
    lines.append(f"60 WHILE TIME<t AND INKEY({KEY_SPACE})=-1:WEND")

    # AND THE PRESS IS NOT SWALLOWED. The game's own title waits for the
    # RELEASE as well as the press (CLAUDE.md 7.7), so a SPACE still
    # held when the game starts does not run straight past it.
    lines.append('70 LOAD"GAME.BIN"')
    lines.append("80 CALL &4000")

    path = os.path.join(BUILD, "kara.bas")
    open(path, "w", newline="\r\n").write("\n".join(lines) + "\n")
    print(f"-> kara.bas          {len(lines)} lines, {SPLASH.upper()}.SCR at "
          f"&{SCREEN_ADDR:04X}, held {HOLD_SECONDS}s or until SPACE")


if __name__ == "__main__":
    main()
