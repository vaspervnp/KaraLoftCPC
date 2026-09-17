"""Getting a suite past the title screen.

RUN"DISC no longer lands in the game: it lands on the title picture with
PRESS SPACE OR FIRE blinking on it, and stays there until something
presses it (CLAUDE.md 7.7). Every suite that boots the real disc has to
answer that prompt, so the answer is written down once here.

The signal that the prompt is up is INTRO_BLINK MOVING: it is bumped
once a frame by INTRO_WAIT and by nothing else, so two consecutive
samples a frame apart differing by exactly one means the wait is
running - which a resting value cannot tell you, and which does not
depend on how long the disc read took.
"""


def past_intro(m, sym, limit=1500):
    """Press fire on the title screen. True once the game loop is running."""
    prev, seen = None, 0
    for _ in range(limit):
        m.run_frames(1)
        v = m.peek(sym["INTRO_BLINK"])
        if prev is not None and (v - prev) & 0xFF == 1 and m.mode == 0:
            seen += 1
            if seen >= 2:
                break
        else:
            seen = 0
        prev = v
    else:
        return False
    # ... and let go of it. INTRO_WAIT waits for the release as well,
    # because the same bit is her trigger (CLAUDE.md 8.4).
    m.joystick(0x10)
    m.run_frames(6)
    m.joystick(0)
    for _ in range(200):
        m.run_frames(2)
        if m.peek(sym["FRAME_COUNT"]):
            return True
    return False
