#!/usr/bin/env python3
"""Put the packed level streams on the disc as RAW SECTORS.

Not as AMSDOS files. The engine has no firmware left to call by the
time a level changes (src/disc.asm explains why), so it talks to the
uPD765 itself - and a directory to parse would be the only reason it
would need to. Raw sectors past whatever AMSDOS allocated cost a build
step instead.

Two phases, because the include has to exist before RASM runs and the
disc image only exists after it:

    --inc   work out the layout from the stream sizes, write disc.inc
    --dsk   patch the streams into build/kara.dsk

The layout depends only on the sizes, so the two agree by construction.
It also checks that AMSDOS's own allocation has not grown into the data
area, which is the one way this could quietly corrupt a build.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
LEV = os.path.join(ROOT, "build", "levels")
DSK = os.path.join(ROOT, "build", "kara.dsk")
INTRO = os.path.join(ROOT, "build", "intro.zx0")

DATA_TRACK = 9              # ... and it was 8 until the label screen went on
                            # the disc. REVIVE8B.SCR is a whole 16 KB
                            # screen - BASIC loads it straight to &C000
                            # and cannot unpack anything - so AMSDOS's
                            # own allocation went from block 18 to 36,
                            # which IS the first data block at track 8.
                            # At track 9 the first data block is 40 and
                            # the files have four 1 KB blocks of room
                            # left; the data ends at sector 346 of 360,
                            # so there are fourteen at the other end
                            # too. Both numbers are checked below.
SECT_FIRST = 0xC1
SECTORS = 9
SECT_SIZE = 512

# A LEVEL AND AN ENVIRONMENT ARE DIFFERENT THINGS NOW (CLAUDE.md 8.1).
# An environment is a bank set - the tiles, the characters, the machines
# - and it is read at a transition that changes it, 16-20 KB and ~1.6 s.
# A level is one map, and it is 358 packed bytes: ONE SECTOR. So several
# levels share an environment's art and cost a sector each, which is why
# the maps are indexed by LEVEL here and the sets by ENVIRONMENT.
#
# The global number is in the FILE NAME - map_<n>.zx0 - because
# DISC_LEVEL_MAPS is indexed by it and a sidecar saying so would be a
# second place to get it wrong.
ENVIRONMENTS = 6
LEVELS_PER_ENV = 4
MAX_LEVELS = ENVIRONMENTS * LEVELS_PER_ENV

# WHAT THE DISC HOLDS, AND THE TWO NUMBERS ARE NOT THE SAME. A CPC DATA
# disc is 40 tracks and that is what every drive reads; the .dsk this
# build makes is 42, and the last two are the extended pair that many
# drives and some emulators will not touch. So crossing 40 tracks is a
# WARNING with the number in it and crossing 42 is an error - because
# the second one is data that is simply not on the disc, and the
# symptom would be a level that loads noise.
STD_TRACKS = 40
IMG_TRACKS = 42
# the RAM configuration each bank image is unpacked into
CFG = {"C0": 0xC0, "C4": 0xC4, "C5": 0xC5, "C6": 0xC6, "C7": 0xC7}


def levels():
    """The ENVIRONMENT directories, in order - one bank set each."""
    return sorted(x for x in os.listdir(LEV)
                  if x.startswith("level") and os.path.isdir(os.path.join(LEV, x)))


def maps_in(d):
    """The global level numbers this environment has a map for."""
    out = []
    for f in os.listdir(d):
        if f.startswith("map_") and f.endswith(".zx0"):
            n = f[4:-4]
            if n.isdigit():
                out.append(int(n))
    return sorted(out)


def plan():
    """[(level, kind, [(cfg, track, sector, nsectors, path)])], in disc order."""
    out, cursor = [], DATA_TRACK * SECTORS
    # THE TITLE PICTURE GOES FIRST, and it is here rather than in a
    # level directory because it belongs to no level: it is read once,
    # before the first one loads, and unpacked straight into video RAM
    # (src/intro.asm). It travels as a one-"bank" record so the layout,
    # the include and the reader are all the same shape as a level's.
    if os.path.exists(INTRO):
        n = (os.path.getsize(INTRO) + SECT_SIZE - 1) // SECT_SIZE
        out.append(("intro", "scr", [(CFG["C0"], cursor // SECTORS,
                                      SECT_FIRST + cursor % SECTORS,
                                      n, INTRO)]))
        cursor += n
    for lvl in levels():
        d = os.path.join(LEV, lvl)
        # THE LEVEL'S OWN BYTES FIRST, then its art. map.zx0 is the map,
        # the entity table and the tile flags in one stream
        # (tools/make_level_image.py); it is one "bank" whose RAM
        # configuration is never used, because LEVEL_MAP_LOAD unpacks it
        # into base RAM at LEVEL_IMAGE and pages nothing.
        kinds = [f"map_{n}" for n in maps_in(d)] + ["lvl", "set"]
        for kind in kinds:
            banks = []
            names = ["."] if kind.startswith("map") else ["C0", "C4", "C5",
                                                          "C6", "C7"]
            for cfg in names:
                p = (os.path.join(d, f"{kind}.zx0") if kind.startswith("map")
                     else os.path.join(d, f"{kind}_{cfg}.zx0"))
                if not os.path.exists(p):
                    continue
                n = (os.path.getsize(p) + SECT_SIZE - 1) // SECT_SIZE
                banks.append((CFG.get(cfg, 0), cursor // SECTORS,
                              SECT_FIRST + cursor % SECTORS, n, p))
                cursor += n
            if banks:
                out.append((lvl, kind, banks))
    return out, cursor


def write_inc(layout, end):
    lines = ["; Generated by tools/dskdata.py",
             "; Where each level's packed bank images are on the disc, as raw",
             "; sectors - see src/disc.asm for why they are not files.",
             "",
             f"DISC_DATA_TRACK         equ {DATA_TRACK}",
             f"DISC_DATA_END_TRACK     equ {(end + SECTORS - 1) // SECTORS}",
             ""]
    syms = {}
    for lvl, kind, banks in layout:
        sym = f"D_{lvl.upper().replace('LEVEL', 'L').split('_')[0]}_{kind.upper()}"
        syms[(lvl, kind)] = sym
        lines.append(f"{sym}:")
        lines.append(f"                db {len(banks)}"
                     f"                   ; banks")
        for cfg, track, sect, n, _ in banks:
            lines.append(f"                db &{cfg:02X}, {track}, &{sect:02X}, {n}")
        lines.append("")
    lines.append("; Indexed by level * 2, then + 1 for the set pieces. A zero")
    lines.append("; means that level has none.")
    lines.append("DISC_LEVEL_SETS:")
    for lvl in levels():
        for kind in ("lvl", "set"):
            s = syms.get((lvl, kind))
            lines.append(f"                dw {s if s else 0}"
                         f"{'':<12}; {lvl} {kind}")
    lines.append("")
    lines.append("; And the level's OWN bytes - one entry a LEVEL, indexed by")
    lines.append("; the global level number less one, with no stride to get")
    lines.append("; wrong. A zero means no map has been painted for that")
    lines.append("; level, and LEVEL_GOTO treats it as the end of the game.")
    lines.append("; Which ENVIRONMENT a level belongs to is not here: it is")
    lines.append("; byte 9 of the level's own header, which LEVEL_GOTO reads")
    lines.append("; after the map lands (CLAUDE.md 8.1).")
    lines.append(f"DISC_LEVEL_N            equ {MAX_LEVELS}")
    lines.append("DISC_LEVEL_MAPS:")
    owner = {}
    for lvl in levels():
        for n in maps_in(os.path.join(LEV, lvl)):
            owner[n] = (lvl, f"map_{n}")
    for n in range(1, MAX_LEVELS + 1):
        who = owner.get(n)
        sym = syms.get(who) if who else None
        lines.append(f"                dw {sym if sym else 0}"
                     f"{'':<12}; level {n}"
                     f"{'  ' + who[0] if who else ''}")
    path = os.path.join(LEV, "disc.inc")
    open(path, "w").write("\n".join(lines) + "\n")
    used = end - DATA_TRACK * SECTORS
    std = (STD_TRACKS - DATA_TRACK) * SECTORS
    img = (IMG_TRACKS - DATA_TRACK) * SECTORS
    print(f"  -> {path}  {sum(len(b) for _, _, b in layout)} streams, "
          f"tracks {DATA_TRACK}-{(end - 1) // SECTORS}, "
          f"{used} of {img} data sectors")
    if used > img:
        raise SystemExit(
            f"the level data is {used} sectors and the disc holds {img} "
            f"from track {DATA_TRACK} - over by {used - img}. A map is one "
            f"sector and a bank set is 30-40, so this is art, not levels.")
    if used > std:
        print(f"     ... and {used - std} of them are past track {STD_TRACKS}, "
              f"on the extended pair many drives will not read. The image is "
              f"{IMG_TRACKS} tracks; a standard DATA disc is {STD_TRACKS}.")


def dsk_offsets(img):
    """{(track, sector id): file offset of its 512 bytes}"""
    ts = img[0x32] | (img[0x33] << 8)
    tracks = img[0x30]
    out = {}
    for t in range(tracks):
        base = 0x100 + t * ts
        ti = img[base:base + 256]
        if ti[:10] != b"Track-Info":
            continue
        pos = base + 256
        for i in range(ti[0x15]):
            out[(ti[0x10], ti[0x18 + 8 * i + 2])] = pos
            pos += SECT_SIZE
    return out


def amsdos_top_block(img, off):
    """Highest 1 KB block AMSDOS has allocated, or -1 for an empty disc."""
    data = b"".join(img[off[(0, r)]:off[(0, r)] + SECT_SIZE]
                    for r in range(0xC1, 0xC5))
    top = -1
    for i in range(0, len(data), 32):
        e = data[i:i + 32]
        if e[0] == 0xE5:
            continue
        top = max([top] + [b for b in e[16:32] if b])
    return top


def write_dsk(layout, end):
    img = bytearray(open(DSK, "rb").read())
    off = dsk_offsets(img)

    # A block is two sectors, numbered from the start of the disc, so
    # the data area starts at block DATA_TRACK * 9 / 2.
    first_block = DATA_TRACK * SECTORS // 2
    top = amsdos_top_block(img, off)
    if top >= first_block:
        raise SystemExit(
            f"AMSDOS has allocated up to block {top} and the raw data area "
            f"starts at block {first_block} (track {DATA_TRACK}). The files "
            f"have outgrown their room - raise DATA_TRACK.")

    written = 0
    for lvl, kind, banks in layout:
        for cfg, track, sect, n, path in banks:
            data = open(path, "rb").read()
            for i in range(n):
                s = SECT_FIRST + (sect - SECT_FIRST + i) % SECTORS
                t = track + (sect - SECT_FIRST + i) // SECTORS
                if (t, s) not in off:
                    raise SystemExit(f"{path}: track {t} sector &{s:02X} "
                                     f"is not on the image")
                chunk = data[i * SECT_SIZE:(i + 1) * SECT_SIZE]
                chunk += bytes(SECT_SIZE - len(chunk))
                img[off[(t, s)]:off[(t, s)] + SECT_SIZE] = chunk
                written += 1
    open(DSK, "wb").write(bytes(img))
    print(f"  -> {DSK}  {written} sectors of level data "
          f"({written * SECT_SIZE} bytes), AMSDOS tops out at block {top}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inc", action="store_true")
    ap.add_argument("--dsk", action="store_true")
    a = ap.parse_args()
    layout, end = plan()
    if a.inc:
        write_inc(layout, end)
    if a.dsk:
        write_dsk(layout, end)
    return 0


if __name__ == "__main__":
    sys.exit(main())
