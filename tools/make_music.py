#!/usr/bin/env python3
"""make_music.py - the game's music and its sound effects, as data.

    python3 tools/make_music.py            -> build/music.inc
    python3 tools/make_music.py --wav      ... and build/music/*.wav

There is no audio in the art package and nobody here can listen, so the
music is COMPOSED here rather than transcribed (CLAUDE.md 11 step 9),
the way ~/repos/Homeplanet's MUSIC3 was: a score per tune, written as
bars of sixteenth-note steps, and the arithmetic that turns it into
bytes for src/sound.asm. What can be checked without an ear is checked:
the score's notes come back out of the compiled bytes (`expect`), the
player on the emulator writes the same AY registers this file's own
model does, tick for tick (tools/test_sound.py), and `--wav` renders
the model so a person can.

THE TICK IS A GAME FRAME, 25 Hz, and so is every length here. The
player runs once a game frame in the second sweep's wait for its head
gate, which is the one place in the frame that costs nothing (CLAUDE.md
9) - so a sixteenth is `step` ticks, 3 for 125 BPM and 4 for 94.

A CHANNEL IS A STREAM OF BYTES, and this is the whole of its grammar:

    00-5F   a note, 0 = C0, for the current length, restarting the
            instrument's envelope
    60      a rest for the current length
    61      a tie: the note goes on for the current length, envelope and
            all
    80-BF   the current length is (b AND 3F) + 1 ticks
    C0-DF   the current instrument is (b AND 1F)
    E0-EF   the channel's attenuation is (b AND 0F)
    F9      the end of a loop body: round again until its count is spent
    FA n    the start of a loop body, n times
    FC      return from a bar
    FD w    call the bar at w
    FF w    go to w - the end of the tune, and where it comes round to

A BAR USED MORE THAN ONCE IS A SUBROUTINE AND A RUN OF THEM IS A LOOP,
and both are this file's job rather than the score's: the score is
written out in full, so that what is played is what is read, and the
compiler finds the repetition. Every bar starts by saying its own
instrument and length, so a bar compiles to the same bytes wherever it
is used and two of them can be compared as bytes.

THE AY IS CLOCKED AT 1 MHz AND A TONE CYCLE IS SIXTEEN OF ITS PERIODS,
so a period p is 62,500 / p Hz. ~/repos/Homeplanet found its own
constant an octave out (`125000/p`) after three tunes had been written
against it, which is why the number is derived here and the test reads
it back off the chip.
"""
import json
import math
import os
import struct
import sys
import wave

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
BUILD = os.path.join(ROOT, "build")

TICK_HZ = 25
AY_CLOCK = 1_000_000
C0_HZ = 16.351597831287414

TONE, NOISE = 1, 2

# ---------------------------------------------------------------------
# Pitch. A note is 0..95 from C0, and its period comes out of a table
# of twelve - the octave-0 periods, times sixteen so a shift loses
# nothing that matters - shifted right by (octave + 4) WITH ROUNDING.
# The player does exactly this: (b >> (s - 1)) + 1, then >> 1, which
# is (b + 2^(s-1)) >> s by the floor arithmetic (src/sound.asm).
# ---------------------------------------------------------------------
NOTE_BASE = [round(AY_CLOCK / 16 / (C0_HZ * 2 ** (s / 12)) * 16)
             for s in range(12)]
assert max(NOTE_BASE) < 65536


def period(n):
    octave, semi = divmod(n, 12)
    s = octave + 4
    return ((NOTE_BASE[semi] >> (s - 1)) + 1) >> 1


SEMI = {"c": 0, "c#": 1, "db": 1, "d": 2, "d#": 3, "eb": 3, "e": 4,
        "f": 5, "f#": 6, "gb": 6, "g": 7, "g#": 8, "ab": 8, "a": 9,
        "a#": 10, "bb": 10, "b": 11}


def note(tok):
    name, octave = tok[:-1], int(tok[-1])
    n = octave * 12 + SEMI[name]
    assert 0 <= n < 0x60, tok
    return n


# ---------------------------------------------------------------------
# Instruments. An envelope is a list of volumes, one a tick, and the
# last one HOLDS until the note ends: so a drum ends on 0 and a
# sustained voice ends on its sustain level. THE LEVEL ONLY EVER FALLS
# OR STAYS, except for a swell at the very start - Homeplanet's lesson
# is that a level that moves up and down under a held note is tremolo,
# and an ear locks onto it and cannot let go.
#
# NOISE IS CHANNEL C'S. The AY has one noise generator for all three
# voices, and C is the drums and the effects; an instrument with noise
# on A or B would fight them for R6, so the compiler refuses one.
# ---------------------------------------------------------------------
INSTRUMENTS = [
    # name     flags  noise sweep  envelope
    ("silent", TONE,  0,    0,    [0]),
    ("lead",   TONE,  0,    0,    [12, 12, 11, 11, 10, 10, 10, 9]),
    ("lead2",  TONE,  0,    0,    [10, 10, 9, 9, 8, 8, 8, 7]),
    ("flute",  TONE,  0,    0,    [6, 8, 10, 11, 11, 10]),
    ("pluck",  TONE,  0,    0,    [12, 10, 8, 7, 6, 5, 4, 3, 2, 2, 1, 1, 0]),
    ("bass",   TONE,  0,    0,    [13, 12, 12, 11, 11, 10]),
    ("bassp",  TONE,  0,    0,    [13, 11, 9, 8, 7, 6, 5, 4]),
    ("pad",    TONE,  0,    0,    [4, 6, 8, 9, 9, 8]),
    ("bell",   TONE,  0,    0,    [13, 11, 10, 9, 8, 7, 6, 6, 5, 5, 4, 4,
                                   3, 3, 2, 2, 1, 1, 0]),
    ("kick",   TONE,  0,    90,   [12, 10, 7, 4, 0]),
    ("snare",  NOISE, 9,    0,    [11, 8, 6, 4, 2, 0]),
    ("hat",    NOISE, 1,    0,    [6, 3, 0]),
    ("hato",   NOISE, 1,    0,    [6, 5, 4, 3, 2, 1, 0]),
    ("wood",   NOISE, 14,   0,    [8, 4, 0]),
    ("drip",   TONE,  0,    -5,   [9, 6, 4, 2, 1, 0]),
]
INS = {name: i for i, (name, *_) in enumerate(INSTRUMENTS)}

# The drum letters a score may use instead of a note: an instrument and
# the pitch it is struck at. A kick is a tone swept DOWN - its period
# grows - from G3, 196 Hz, to about 105 over its four live ticks.
DRUMS = {"K": ("kick", "g3"), "S": ("snare", "c4"), "H": ("hat", "c4"),
         "O": ("hato", "c4"), "W": ("wood", "c4")}

# ---------------------------------------------------------------------
# Sound effects, in PRIORITY ORDER: a request only takes channel C from
# an effect that is no more important than itself, and a request that
# loses is dropped rather than queued - a sound that arrives late is
# about something that has already happened.
#
#   flags, noise period, noise step a tick, tone period, period step a
#   tick, and the volumes, one a tick. The effect ENDS when they do, and
#   C goes straight back to the music it was playing: the music on C
#   was counted the whole time, so it comes back in step and on its own
#   envelope rather than re-struck (plan.md 7).
# ---------------------------------------------------------------------
SFX = [
    # name      flags          noise nd  period sweep  volumes
    ("reload",  NOISE,         2,    0,  0,     0,     [9, 0, 0, 0, 0, 10, 4, 0]),
    ("eshot",   TONE,          0,    0,  60,    25,    [11, 10, 8, 5, 2, 0]),
    ("shot",    NOISE,         3,    4,  0,     0,     [15, 13, 10, 7, 4, 2, 0]),
    ("ehit",    TONE | NOISE,  5,    0,  300,   80,    [13, 9, 5, 0]),
    ("clip",    TONE,          0,    0,  120,   -20,   [12, 11, 10, 8, 6, 3, 0]),
    ("coin",    TONE,          0,    0,  50,    -4,    [13, 12, 10, 8, 6, 4, 2, 0]),
    ("key",     TONE,          0,    0,  80,    -6,    [14, 12, 10, 9, 8, 7, 6, 5,
                                                        4, 3, 2, 1, 0]),
    ("medkit",  TONE,          0,    0,  240,   -16,   [10, 11, 12, 12, 11, 10, 8,
                                                        6, 4, 2, 0]),
    ("ekill",   NOISE,         4,    1,  0,     0,     [15, 15, 14, 13, 12, 11, 10,
                                                        9, 8, 7, 6, 5, 4, 3, 2, 1, 0]),
    ("hurt",    TONE | NOISE,  12,   0,  400,   60,    [15, 13, 11, 8, 5, 2, 0]),
    ("altar",   TONE,          0,    0,  64,    0,     [15, 14, 13, 12, 11, 10, 9,
                                                        8, 7, 6, 5, 4, 3, 2, 1, 0]),
    ("door",    TONE,          0,    0,  500,   -25,   [12, 12, 12, 12, 12, 12, 11,
                                                        11, 10, 10, 9, 8, 6, 4, 2, 0]),
    ("die",     TONE,          0,    0,  150,   30,    [15, 15, 14, 14, 13, 13, 12,
                                                        12, 11, 11, 10, 10, 9, 9, 8,
                                                        8, 7, 6, 5, 4, 3, 2, 1, 0]),
]
SFX_ID = {name: i + 1 for i, (name, *_) in enumerate(SFX)}


# =====================================================================
# THE SCORES. A channel is a list of bars and a bar is a string of
# steps, one token a step:
#
#   a4  c#5  bb3     a note, which restarts its instrument's envelope
#   K S H O W        a drum (DRUMS above)
#   .                the note before goes on; at the start of a bar it
#                    ties over from the bar before
#   -                a rest
#   @name            the instrument from here on - takes no step
#
# The chords are written above each tune because the melody was written
# against them and the harmony is the first thing to check if a bar
# sounds wrong.
# =====================================================================
def bass8(root, low, high):
    """Root eighths with an octave bounce on the off-beats."""
    return f"{low} . {low} . {high} . {low} . {low} . {low} . {high} . {low} ."


def drive(low, high):
    """The City's: syncopated eighths, pushed by two sixteenths."""
    return f"{low} . {low} {low} {high} . {low} . {low} . {low} {low} {high} . {low} ."


# ---- the title: D minor, 94 BPM -------------------------------------
# Dm | Bb | C | A | Dm | Bb | Gm A | Dm || Bb | C | Dm | A | Bb | C | A | A
# i - VI - VII - V with the A MAJOR, so the C# pulls home; the second
# half leans on the VI and VII and ends on the dominant, which is what
# the loop resolves.
TITLE = dict(name="title", step=4, bar=16)
TITLE["A"] = ["@lead " + b if i == 0 else b for i, b in enumerate([
    "d5 . . . a4 . . . d5 . e5 . f5 . . .",
    "g5 . . . f5 . e5 . d5 . . . . . . .",
    "e5 . . . c5 . . . e5 . f5 . g5 . . .",
    "a5 . . . . . . . g5 . f5 . e5 . c#5 .",
    "d5 . . . a4 . . . d5 . e5 . f5 . . .",
    "g5 . . . a5 . bb5 . a5 . g5 . f5 . . .",
    "g5 . . . f5 . e5 . d5 . . . c#5 . . .",
    "d5 . . . . . . . . . . . - - - -",
    "f4 . . . bb4 . . . d5 . . . c5 . bb4 .",
    "c5 . . . e5 . . . g5 . . . f5 . e5 .",
    "f5 . . . e5 . d5 . a4 . . . d5 . f5 .",
    "e5 . . . . . . . c#5 . . . e5 . . .",
    "d5 . f5 . bb5 . . . a5 . g5 . f5 . . .",
    "e5 . g5 . c6 . . . bb5 . a5 . g5 . . .",
    "a5 . . . e5 . . . c#5 . e5 . a5 . g5 .",
    "a5 . . . . . . . . . . . - - - -",
])]
_TITLE_ROOTS = ["d", "bb", "c", "a", "d", "bb", None, "d",
                "bb", "c", "d", "a", "bb", "c", "a", "a"]
TITLE["B"] = []
for i, r in enumerate(_TITLE_ROOTS):
    if r is None:
        b = "g1 . g1 . g2 . g1 . a1 . a1 . a2 . a1 ."
    else:
        lo = f"{r}1" if r in ("bb", "a") else f"{r}2"
        hi = f"{r}2" if r in ("bb", "a") else f"{r}3"
        b = bass8(r, lo, hi)
    TITLE["B"].append(("@bassp " if i == 0 else "") + b)
_TB = "K . H . S . H . K . K . S . H ."
_TF = "S . S . S . S . K . S . S . S S"
TITLE["C"] = [_TB] * 7 + [_TF] + [_TB] * 7 + [_TF]

# ---- the City: A minor, 125 BPM -------------------------------------
# Am | Am | F | F | C | C | G | G || Am | Am | F | F | Dm | Dm | E | E
# The second phrase climbs where the first fell, and the E7 at the end
# (G# B D, then C over it) is what makes the loop's Am an arrival.
CITY = dict(name="city", step=3, bar=16)
CITY["A"] = ["@lead " + b if i == 0 else b for i, b in enumerate([
    "a4 . . . c5 . a4 . e5 . . . d5 . c5 .",
    "d5 . c5 . a4 . . . g4 . a4 . . . . .",
    "a4 . . . c5 . a4 . f5 . . . e5 . c5 .",
    "e5 . d5 . c5 . . . a4 . . . . . . .",
    "g4 . . . c5 . g4 . e5 . . . d5 . c5 .",
    "d5 . e5 . g5 . . . e5 . . . d5 . . .",
    "d5 . . . b4 . g4 . b4 . d5 . g5 . . .",
    "f5 . g5 . d5 . . . b4 . . . . . . .",
    "e5 . . . a5 . . . g5 . e5 . a5 . . .",
    "g5 . e5 . d5 . c5 . d5 . e5 . . . . .",
    "f5 . . . a5 . . . g5 . f5 . e5 . . .",
    "f5 . e5 . c5 . . . a4 . . . c5 . . .",
    "d5 . . . f5 . . . a5 . . . g5 . f5 .",
    "e5 . f5 . d5 . . . a4 . . . d5 . . .",
    "e5 . . . g#5 . . . b5 . . . d6 . . .",
    "c6 . b5 . a5 . g#5 . e5 . . . . . . .",
])]
_CITY_ROOTS = [("a1", "a2"), ("a1", "a2"), ("f1", "f2"), ("f1", "f2"),
               ("c2", "c3"), ("c2", "c3"), ("g1", "g2"), ("g1", "g2"),
               ("a1", "a2"), ("a1", "a2"), ("f1", "f2"), ("f1", "f2"),
               ("d2", "d3"), ("d2", "d3"), ("e1", "e2"), ("e1", "e2")]
CITY["B"] = [("@bassp " if i == 0 else "") + drive(lo, hi)
             for i, (lo, hi) in enumerate(_CITY_ROOTS)]
_CB = "K . H . S . H K . K H . S . H ."
_CF = "K . S . S . S . K S . S S S S S"
CITY["C"] = [_CB] * 7 + [_CF] + [_CB] * 7 + [_CF]

# ---- the forest: D Dorian, 12/16 ------------------------------------
# Dm | Dm | G | G | Am | C | Dm | Dm || F | C | G | G | Dm | Am | C | Dm
# The G MAJOR is the mode: a minor key with a raised sixth, which reads
# as old rather than sad. Twelve steps a bar and the beat on every
# third, so it sways where the City drives; the bass is root and fifth
# held, and the drums are a wooden knock and a hat, nothing struck hard.
FOREST = dict(name="forest", step=3, bar=12)
FOREST["A"] = ["@flute " + b if i == 0 else b for i, b in enumerate([
    "d5 . . . . . a4 . . c5 . .",
    "d5 . . e5 . . f5 . . . . .",
    "g5 . . . . . b4 . . d5 . .",
    "e5 . . d5 . . b4 . . . . .",
    "c5 . . . . . e5 . . a5 . .",
    "g5 . . e5 . . c5 . . . . .",
    "d5 . . f5 . . a5 . . g5 . .",
    "f5 . . e5 . . d5 . . . . .",
    "c5 . . . . . f5 . . a5 . .",
    "g5 . . . . . e5 . . c5 . .",
    "b4 . . d5 . . g5 . . . . .",
    "a5 . . g5 . . b5 . . . . .",
    "a5 . . . . . f5 . . d5 . .",
    "e5 . . . . . c5 . . a4 . .",
    "g4 . . c5 . . e5 . . g5 . .",
    "d5 . . . . . . . . - - -",
])]
_FOREST_ROOTS = [("d2", "a2"), ("d2", "a2"), ("g1", "d2"), ("g1", "d2"),
                 ("a1", "e2"), ("c2", "g2"), ("d2", "a2"), ("d2", "a2"),
                 ("f1", "c2"), ("c2", "g2"), ("g1", "d2"), ("g1", "d2"),
                 ("d2", "a2"), ("a1", "e2"), ("c2", "g2"), ("d2", "a2")]
FOREST["B"] = [("@bass " if i == 0 else "") + f"{r} . . . . . {f} . . . . ."
               for i, (r, f) in enumerate(_FOREST_ROOTS)]
_FB = "W . . H . . W . . H . H"
FOREST["C"] = [_FB] * 16

# ---- the cave: E Phrygian, 94 BPM -----------------------------------
# E | E | E | E | F | F | E | E || C | C | D | D | F | F | E | E
# The flat second is the whole of the mood, so the bass sits on E and
# leans on F; the melody enters late, moves in long notes and leaves
# for the last two bars, because with three voices taking one away is
# the biggest change there is. Channel C is water, not drums: a drop,
# now and then, high and short.
CAVE = dict(name="cave", step=4, bar=16)
CAVE["A"] = ["@pad " + b if i == 0 else b for i, b in enumerate([
    "- - - - - - - - - - - - - - - -",
    "- - - - - - - - e4 . . . . . . .",
    "f4 . . . . . . . . . . . g4 . . .",
    "e4 . . . . . . . - - - - - - - -",
    "- - - - a4 . . . . . . . b4 . . .",
    "c5 . . . . . . . b4 . . . a4 . . .",
    "g4 . . . . . . . f4 . . . . . . .",
    "e4 . . . . . . . - - - - - - - -",
    "- - - - g4 . . . c5 . . . . . . .",
    "b4 . . . . . . . a4 . . . g4 . . .",
    "a4 . . . . . . . d5 . . . . . . .",
    "c5 . . . b4 . . . a4 . . . . . . .",
    "f4 . . . . . . . a4 . . . g4 . . .",
    "f4 . . . . . . . e4 . . . . . . .",
    "- - - - - - - - - - - - - - - -",
    "- - - - - - - - - - - - - - - -",
])]
_CAVE_ROOTS = ["e1", "e1", "e1", "e1", "f1", "f1", "e1", "e1",
               "c2", "c2", "d2", "d2", "f1", "f1", "e1", "e1"]
CAVE["B"] = [("@bass " if i == 0 else "") + f"{r} . . . . . . . . . . . . . . ."
             for i, r in enumerate(_CAVE_ROOTS)]
_DRIPS = [
    "- - - - - - - - - - b6 . . . . .",
    "- - - - - - - - - - - - - - - -",
    "- - - - - e6 . . . . . . . . . .",
    "- - - - - - - - - - - - g6 . . .",
    "- - b6 . . . . . . . . . . . . .",
    "- - - - - - - - - - - - - - - -",
    "- - - - - - - - e7 . . . . . . .",
    "- - - - - - - - - - - - - - - -",
]
CAVE["C"] = ["@drip " + _DRIPS[0]] + _DRIPS[1:] + _DRIPS

TUNES = [TITLE, CITY, FOREST, CAVE]
TUNE_ID = {t["name"]: i for i, t in enumerate(TUNES)}

# Which tune an environment plays, by LEVEL_ENV (src/flow.asm): the City,
# the forest and the cave have theirs; the three nobody has painted yet
# play the title's, which is never wrong and always obviously a stand-in.
ENV_TUNE = ["city", "forest", "cave", "title", "title", "title"]


# =====================================================================
# The compiler.
# =====================================================================
def parse_bar(text, ins, bar_len):
    """A bar's text -> its items, and the instrument it leaves in force.

    Items are ('ins', i), ('note', n, steps), ('rest', steps) and
    ('tie', steps) - a '.' at the start of a bar ties over the bar line.
    Every note is preceded by the instrument it is played with, so a
    bar does not depend on what the bar before it left in force.
    """
    items, steps = [], 0
    for tok in text.split():
        if tok.startswith("@"):
            ins = INS[tok[1:]]
            continue
        steps += 1
        if tok == ".":
            if items and items[-1][0] in ("note", "rest", "tie"):
                kind, *rest = items[-1]
                items[-1] = (kind, *rest[:-1], rest[-1] + 1)
            else:
                items.append(("tie", 1))
        elif tok == "-":
            items.append(("rest", 1))
        elif tok in DRUMS:
            dins, dnote = DRUMS[tok]
            ins = INS[dins]
            items += [("ins", ins), ("note", note(dnote), 1)]
        else:
            items += [("ins", ins), ("note", note(tok), 1)]
    assert steps == bar_len, f"{steps} steps in a bar of {bar_len}: {text}"
    return items, ins


def bar_bytes(items, step):
    """A bar's bytes. It says its own length first, and the instrument
    of its first NOTE, so a bar is the same bytes wherever it is used
    whatever the bar before it left in force. A bar with no note in it
    - rests and ties only - names no instrument, because neither reads
    one."""
    out, cur_len, cur_ins = [], None, None
    for i, it in enumerate(items):
        if it[0] == "ins":
            # only the last of a run of changes before a note matters
            nxt = next((x for x in items[i + 1:] if x[0] != "ins"), None)
            if nxt is not None and nxt[0] == "note" and it[1] != cur_ins \
                    and items[i + 1][0] != "ins":
                out.append(0xC0 | it[1])
                cur_ins = it[1]
            continue
        kind, steps = it[0], it[-1]
        if kind == "note" and cur_ins is None:
            raise AssertionError("a note with no instrument before it")
        ticks = steps * step
        first = True
        while ticks:
            chunk = min(ticks, 64)
            if chunk != cur_len:
                out.append(0x80 | (chunk - 1))
                cur_len = chunk
            if kind == "note" and first:
                out.append(it[1])
            elif kind == "rest" and first:
                out.append(0x60)
            else:
                out.append(0x61)        # a tie, or the rest of a long one
            first = False
            ticks -= chunk
    return bytes(out)


def compile_channel(tune, ch):
    """A channel -> its bars as bytes, and which of them are subroutines."""
    step, bar_len = tune["step"], tune["bar"]
    ins = INS["silent"]
    bars = []
    for text in tune[ch]:
        items, ins = parse_bar(text, ins, bar_len)
        if ch in "AB":
            for it in items:
                if it[0] == "ins":
                    assert INSTRUMENTS[it[1]][1] == TONE, \
                        f"{tune['name']} {ch}: noise is channel C's"
        bars.append(bar_bytes(items, step))
    uses = {}
    for b in bars:
        uses[b] = uses.get(b, 0) + 1
    subs = [b for b in dict.fromkeys(bars) if uses[b] > 1]
    return bars, subs


def layout(tune, ch):
    """A channel's main stream as (body, count) pieces - a body item is
    ('call', j) for subroutine j or ('bar', bytes) - and the subroutines.
    emit_tune writes this and the model reads it, so the two lay the
    bytes out identically by construction."""
    bars, subs = compile_channel(tune, ch)
    keys = [("call", subs.index(b)) if b in subs else ("bar", b)
            for b in bars]
    return loops(keys), subs


def loops(items):
    """Greedy runs: (body, count) pieces covering `items` in order."""
    def cost(x):
        return 3 if x[0] == "call" else len(x[1])
    out, i = [], 0
    while i < len(items):
        best = (1, 1, 0)                     # period, count, saving
        for p in range(1, 9):
            body = items[i:i + p]
            if len(body) < p:
                break
            k = 1
            while items[i + k * p:i + (k + 1) * p] == body:
                k += 1
            if k > 1:
                saving = (k - 1) * sum(cost(x) for x in body) - 3
                if saving > best[2]:
                    best = (p, k, saving)
        p, k, _ = best
        out.append((items[i:i + p], k))
        i += p * k
    return out


class Asm:
    """Bytes with labels in them: RASM resolves the addresses."""

    def __init__(self):
        self.lines = []

    def label(self, name):
        self.lines.append(f"{name}:")

    def db(self, data):
        data = list(data)
        for i in range(0, len(data), 16):
            self.lines.append("                db " + ",".join(
                f"&{b:02X}" for b in data[i:i + 16]))

    def raw(self, text):
        self.lines.append("                " + text)


def emit_tune(asm, t, ti):
    sizes = {}
    asm.label(f"TUNE_{ti}")
    asm.raw(f"dw T{ti}_A, T{ti}_B, T{ti}_C")
    for ch in "ABC":
        pieces, subs = layout(t, ch)
        size = 0
        asm.label(f"T{ti}_{ch}")
        for body, k in pieces:
            if k > 1:
                asm.db([0xFA, k])
                size += 2
            for kind, x in body:
                if kind == "call":
                    asm.db([0xFD])
                    asm.raw(f"dw T{ti}_{ch}_S{x}")
                    size += 3
                else:
                    asm.db(x)
                    size += len(x)
            if k > 1:
                asm.db([0xF9])
                size += 1
        asm.db([0xFF])
        asm.raw(f"dw T{ti}_{ch}")
        size += 3
        for j, b in enumerate(subs):
            asm.label(f"T{ti}_{ch}_S{j}")
            asm.db(b + b"\xFC")
            size += len(b) + 1
        sizes[ch] = size
    return sizes


def build_inc():
    asm = Asm()
    asm.lines.append("; GENERATED by tools/make_music.py - do not edit")
    asm.lines.append("")
    for name, i in SFX_ID.items():
        asm.lines.append(f"SFX_{name.upper():<14}equ {i}")
    asm.lines.append(f"SFX_N            equ {len(SFX)}")
    for name, i in TUNE_ID.items():
        asm.lines.append(f"TUNE_{name.upper():<13}equ {i}")
    asm.lines.append(f"TUNE_N           equ {len(TUNES)}")
    asm.lines.append(f"ENV_TUNE_N       equ {len(ENV_TUNE)}")
    asm.lines.append("")
    asm.label("SND_NOTE_BASE")
    asm.raw("dw " + ",".join(str(b) for b in NOTE_BASE))
    asm.label("ENV_TUNE")
    asm.db([TUNE_ID[n] for n in ENV_TUNE])
    asm.label("SND_INSTR")
    asm.raw("dw " + ",".join(f"INS_{i}" for i in range(len(INSTRUMENTS))))
    for i, (name, flags, noise, sweep, env) in enumerate(INSTRUMENTS):
        assert 0 <= noise < 32 and all(0 <= v < 16 for v in env)
        asm.label(f"INS_{i}")
        asm.db([flags, noise, sweep & 0xFF, (sweep >> 8) & 0xFF]
               + env + [0xFF])
    asm.label("SFX_TABLE")
    asm.raw("dw " + ",".join(f"SFXD_{i + 1}" for i in range(len(SFX))))
    for i, (name, flags, noise, nd, per, sweep, vols) in enumerate(SFX):
        # the noise period is five bits and the player does not clamp
        # it, so a sweep that would leave 0..31 is refused here
        assert all(0 <= noise + nd * k < 32 for k in range(len(vols))), name
        assert all(0 <= per + sweep * k < 4096 for k in range(len(vols))), name
        asm.label(f"SFXD_{i + 1}")
        asm.db([flags, noise, nd & 0xFF, per & 0xFF, per >> 8,
                sweep & 0xFF, (sweep >> 8) & 0xFF] + vols + [0xFF])
    asm.label("TUNE_TABLE")
    asm.raw("dw " + ",".join(f"TUNE_{i}" for i in range(len(TUNES))))
    sizes = {}
    for ti, t in enumerate(TUNES):
        for ch in "ABC":
            assert len(t[ch]) == len(t["A"]), (t["name"], ch)
        sizes[t["name"]] = emit_tune(asm, t, ti)
    return "\n".join(asm.lines) + "\n", sizes


# =====================================================================
# The model - what the player does, tick by tick, written a second time
# so the test can hold the Z80 to it (tools/test_sound.py). It runs on
# the COMPILED bytes, so it is a check on src/sound.asm and not on the
# compiler; `expect` below is the check on the compiler.
# =====================================================================
class Stream:
    """A channel's bytes as one address space, from address 0 - laid out
    by `layout`, exactly as emit_tune writes them, so `mem` is the very
    bytes RASM assembles with every address taken from the channel's
    own start (tools/test_sound.py compares the two)."""

    def __init__(self, t, ch):
        pieces, subs = layout(t, ch)
        self.mem = bytearray()
        fix = []
        for body, k in pieces:
            if k > 1:
                self.mem += bytes([0xFA, k])
            for kind, x in body:
                if kind == "call":
                    self.mem += b"\xFD"
                    fix.append((len(self.mem), x))
                    self.mem += b"\0\0"
                else:
                    self.mem += x
            if k > 1:
                self.mem += b"\xF9"
        self.mem += b"\xFF\0\0"            # back to address 0
        sub_at = []
        for b in subs:
            sub_at.append(len(self.mem))
            self.mem += b + b"\xFC"
        for at, j in fix:
            struct.pack_into("<H", self.mem, at, sub_at[j])

    def at(self, base):
        """The same bytes with every address relocated to `base`."""
        out = bytearray(self.mem)
        i = 0
        while i < len(out):
            b = out[i]
            if b in (0xFD, 0xFF):
                a = (out[i + 1] | out[i + 2] << 8) + base
                out[i + 1], out[i + 2] = a & 0xFF, a >> 8
                i += 3
            elif b == 0xFA:
                i += 2
            else:
                i += 1
        return bytes(out)


class Voice:
    def __init__(self, stream):
        self.s = stream.mem
        self.ptr, self.cnt, self.len = 0, 1, 1
        self.ins = INSTRUMENTS[0]
        self.env, self.epos = [0], 0
        self.per, self.swp, self.vol, self.att = 0, 0, 0, 0
        self.ret = self.lptr = 0
        self.lcnt = 0
        self.flags, self.noise = TONE, 0

    def tick(self):
        self.per = (self.per + self.swp) & 0xFFFF
        self.cnt = (self.cnt - 1) & 0xFF
        if self.cnt == 0:
            self.event()
        self.vol = self.env[self.epos]
        if self.epos + 1 < len(self.env):
            self.epos += 1

    def event(self):
        s = self.s
        while True:
            b = s[self.ptr]
            self.ptr += 1
            if b < 0x60:
                self.per = period(b)
                name, self.flags, self.noise, sweep, env = self.ins
                self.swp = sweep & 0xFFFF
                self.env, self.epos = env, 0
                break
            if b == 0x60:
                self.env, self.epos = [0], 0
                self.swp = 0
                break
            if b == 0x61:
                break
            if b < 0xC0:
                self.len = (b & 0x3F) + 1
            elif b < 0xE0:
                self.ins = INSTRUMENTS[b & 0x1F]
            elif b < 0xF0:
                self.att = b & 0x0F
            elif b == 0xF9:
                self.lcnt = (self.lcnt - 1) & 0xFF
                if self.lcnt:
                    self.ptr = self.lptr
            elif b == 0xFA:
                self.lcnt = s[self.ptr]
                self.ptr += 1
                self.lptr = self.ptr
            elif b == 0xFC:
                self.ptr = self.ret
            elif b == 0xFD:
                at = s[self.ptr] | s[self.ptr + 1] << 8
                self.ret = self.ptr + 2
                self.ptr = at
            elif b == 0xFF:
                self.ptr = s[self.ptr] | s[self.ptr + 1] << 8
            else:
                raise ValueError(f"byte {b:#x}")
        self.cnt = self.len


def regs(voices, atten=0):
    """R0..R10 as the player's SND_MIX builds them, music only."""
    out = []
    for v in voices:
        out += [v.per & 0xFF, (v.per >> 8) & 0x0F]
    c = voices[2]
    out.append(c.noise & 0x1F)
    mix = 0b00111111
    for i, v in enumerate(voices):
        if v.flags & TONE:
            mix &= ~(1 << i)
        if v.flags & NOISE:
            mix &= ~(1 << (i + 3))
    out.append(mix)
    for v in voices:
        out.append(max(0, v.vol - v.att - atten))
    return out


def simulate(ti, ticks):
    t = TUNES[ti]
    voices = [Voice(Stream(t, ch)) for ch in "ABC"]
    frames = []
    for _ in range(ticks):
        for v in voices:
            v.tick()
        frames.append(regs(voices))
    return frames


def expect(ti):
    """The score's own statement of each channel: (tick, note) for every
    note struck, out of the TEXT and not out of the bytes."""
    t = TUNES[ti]
    out = {}
    for ch in "ABC":
        tick, ins, seq = 0, INS["silent"], []
        for text in t[ch]:
            for tok in text.split():
                if tok.startswith("@"):
                    continue
                if tok in DRUMS:
                    seq.append((tick, note(DRUMS[tok][1])))
                elif tok not in (".", "-"):
                    seq.append((tick, note(tok)))
                tick += t["step"]
        out[ch] = (seq, tick)
    return out


def loop_ticks(ti):
    t = TUNES[ti]
    return len(t["A"]) * t["bar"] * t["step"]


# =====================================================================
# The preview: the model's registers through a model of the chip.
# =====================================================================
AY_LEVEL = [0.0, 0.0137, 0.0205, 0.0291, 0.0423, 0.0618, 0.0847, 0.1369,
            0.1691, 0.2647, 0.3527, 0.4499, 0.5704, 0.6873, 0.8482, 1.0]


def render(frames, path, rate=22050):
    per_tick = rate // TICK_HZ
    phase = [0.0, 0.0, 0.0]
    nphase, lfsr, nbit = 0.0, 1, 1
    out = bytearray()
    for r in frames:
        pers = [max(1, r[0] | r[1] << 8), max(1, r[2] | r[3] << 8),
                max(1, r[4] | r[5] << 8)]
        steps = [AY_CLOCK / 16 / p / rate for p in pers]
        nstep = AY_CLOCK / 16 / max(1, r[6]) / rate
        mix, vols = r[7], r[8:11]
        for _ in range(per_tick):
            nphase += nstep
            while nphase >= 1:
                nphase -= 1
                bit = (lfsr ^ (lfsr >> 3)) & 1
                lfsr = (lfsr >> 1) | (bit << 16)
                nbit = lfsr & 1
            s = 0.0
            for i in range(3):
                phase[i] = (phase[i] + steps[i]) % 1.0
                tone = 1 if phase[i] < 0.5 else 0
                t_on = tone or (mix >> i) & 1
                n_on = nbit or (mix >> (i + 3)) & 1
                if t_on and n_on:
                    s += AY_LEVEL[vols[i]]
            out += struct.pack("<h", int((s / 3 - 0.25) * 52000))
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes(out))


def sfx_frames(name):
    flags, noise, nd, per, sweep, vols = SFX[SFX_ID[name] - 1][1:]
    frames = []
    for k, v in enumerate(vols):
        p = per + sweep * k
        mix = 0b00111111
        if flags & TONE:
            mix &= ~4
        if flags & NOISE:
            mix &= ~32
        frames.append([0, 0, 0, 0, p & 0xFF, (p >> 8) & 0xF,
                       (noise + nd * k) & 0x1F, mix, 0, 0, v])
    return frames + [[0] * 7 + [0b00111111, 0, 0, 0]] * 5


def main():
    os.makedirs(BUILD, exist_ok=True)
    text, sizes = build_inc()
    with open(os.path.join(BUILD, "music.inc"), "w") as f:
        f.write(text)
    total = 0
    for name, s in sizes.items():
        n = sum(s.values())
        total += n
        ti = TUNE_ID[name]
        secs = loop_ticks(ti) / TICK_HZ
        print(f"  {name:<7} {n:4} bytes  A {s['A']:3} B {s['B']:3} "
              f"C {s['C']:3}  {secs:5.1f} s a loop")
    print(f"-> music.inc  {len(TUNES)} tunes, {total} bytes of score, "
          f"{len(SFX)} effects, {len(INSTRUMENTS)} instruments")
    # the compiler, checked against the score: every note the TEXT
    # strikes is the period the MODEL plays on that tick
    for ti in range(len(TUNES)):
        frames = simulate(ti, loop_ticks(ti) * 2)
        for ci, ch in enumerate("ABC"):
            seq, length = expect(ti)[ch]
            assert length == loop_ticks(ti), (TUNES[ti]["name"], ch)
            for loop in range(2):
                for tick, n in seq:
                    r = frames[loop * length + tick]
                    got = r[ci * 2] | r[ci * 2 + 1] << 8
                    assert got == period(n), (TUNES[ti]["name"], ch, tick, n)
    if "--wav" in sys.argv:
        d = os.path.join(BUILD, "music")
        os.makedirs(d, exist_ok=True)
        for ti, t in enumerate(TUNES):
            p = os.path.join(d, f"{t['name']}.wav")
            render(simulate(ti, loop_ticks(ti)), p)
            print(f"  {p}")
        allfx = []
        for name in SFX_ID:
            allfx += sfx_frames(name)
        p = os.path.join(d, "effects.wav")
        render(allfx, p)
        print(f"  {p}  ({', '.join(SFX_ID)})")


if __name__ == "__main__":
    main()
