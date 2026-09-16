#!/usr/bin/env python3
"""Lay every level's blobs out into banks and ZX0-pack one image per bank.

Why one stream per BANK and not one per blob
--------------------------------------------
The loader's job becomes three lines: read the file to a staging buffer,
page the bank in, `dzx0_fast` it to &4000. No directory to walk, no
per-blob addresses to fix up, and ZX0 sees the whole 16 KB at once so
repeated art across blobs (and the zero padding) costs almost nothing.

What has to fit
---------------
The window at &4000 can show bank 1 or banks 4-7, so there are FIVE
banks of art, 81,920 bytes. Unpacked, a level needs 57-77 KB of that:
every level's own sheets plus the shared set - the heroine, her
projectiles, the HUD - which is 49,161 bytes on its own and is most of
the problem.

Two rules make it fit:

* **The set pieces load separately.** The escape car, the shuttle, the
  base door, the escape pod, the siphon and the computer are each one
  fixed moment; between them they are 60 KB that never has to be
  resident while the level is being played. Level 5 is 55,526 bytes of
  art and 28,134 of it is the finale.
* **The swim set replaces the run/roll set.** She does not run or roll
  under water and she does not swim anywhere else.

The compressed form of ALL SIX LEVELS is 43,910 bytes, which would fit
in three banks - but the unpacked working set needs five, so there is
nowhere to keep it. Hence a disc read per level, of about 20 KB.
"""
import json
import os
import random
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
LEV = os.path.join(ROOT, "build", "levels")
BANK_SIZE = 16384
WINDOW = 0x4000
# The top of C4 is not the allocator's to give. src/entity.asm bakes each
# pickup into a scratch TILE there - a pickup is 8x16, which is exactly
# one tile, so the column painter draws it for nothing instead of the
# span blitter costing 12,116 T a frame for one of them. TILE_SRC reads
# any 64-aligned address in C4 as a tile index, so the reserve only has
# to be aligned and out of the way; ENT_BAKE_ADDR is the same number on
# the engine's side.
TILE_BANK = 1                    # index into BANKS: C4
BAKE_BYTES = 16 * 64
SIZES = [BANK_SIZE] * 5
SIZES[TILE_BANK] = BANK_SIZE - BAKE_BYTES
# The configurations that put a bank in the window. &C0 is the default,
# so bank 1 needs no OUT to reach - put the busiest art there.
BANKS = [("C0", 0xC0), ("C4", 0xC4), ("C5", 0xC5), ("C6", 0xC6), ("C7", 0xC7)]

# Shared by every level. She is in all of them and so is her HUD.
SHARED_ALWAYS = ["kcore", "kcore_l", "kextra", "kextra_l", "kact", "kact_l",
                 "bullet", "bullet_l", "hudicon", "huddigit", "hudbar"]
# Level 4 swims instead of running.
SHARED_SWIM = ["kcore", "kcore_l", "kswim", "kswim_l", "kact", "kact_l",
               "bullet", "bullet_l", "spear", "spear_l",
               "hudicon", "huddigit", "hudbar"]

# CLIMB IS NOT SHARED, AND THE ART SAYS WHICH LEVELS GET IT. Only a
# level with a ladder tile in its tileset has anything to climb, and
# `climb` is 2,714 bytes - which four levels out of six would carry and
# never draw. Since `drop` and `die` joined the action sheet there is no
# level with room for that: level 5 is 2,029 bytes over five banks with
# it and 685 under without. So the levels whose tile_table.json has no
# tile called "ladder" take the blob that stops before it. The frames
# they DO get are at the same indices, so nothing in the engine changes.
LADDER_TILE = "ladder"


def has_ladder(level):
    p = os.path.join(ROOT, "assets", "sprites", level, "tile_table.json")
    if not os.path.exists(p):
        return True                          # unknown: carry it
    t = json.load(open(p))
    return any(tile["name"] == LADDER_TILE
               for sheet in t["sheets"] for tile in sheet["tiles"])


# One fixed moment each, loaded for that moment and not before.
SETPIECE = {"citycar", "desertshuttle", "desertbasedoor",
            "stationpod", "stationcomputer", "seasiphon"}


def blobs(level):
    """The level's own blobs - not the bank images this tool writes."""
    d = os.path.join(LEV, level)
    return sorted(f for f in os.listdir(d)
                  if f.endswith(".bin")
                  and not f.startswith(("lvl_", "set_")))


def stem(f):
    return f[:-4]


def pack(path, out):
    asm = out + ".asm"
    open(asm, "w").write(f'        org 0\n        LZX0\n'
                         f'        incbin "{path}"\n        LZCLOSE\n')
    r = subprocess.run(["rasm", asm, "-amper", "-ob", out],
                       capture_output=True, text=True)
    os.remove(asm)
    if r.returncode:
        raise SystemExit(f"{path}:\n{r.stdout}{r.stderr}")
    return os.path.getsize(out)


def _try(order):
    """Best-fit: put each blob in the bank it leaves least room in.

    First-fit-decreasing is the usual advice and it fails here - level 5
    is 76,553 bytes into 81,920 and FFD strands 5,364 in fragments too
    small for the 5,764-byte blob that is left. Best-fit clears it, and
    the shuffles below are the backstop for whatever the next level's
    art does.
    """
    free = list(SIZES)
    place = {}
    for name, size in order:                 # the pinned ones go first
        i = pin_of(name)
        if i is None:
            continue
        if size > free[i]:
            return None
        place[name] = (i, WINDOW + SIZES[i] - free[i])
        free[i] -= size
    for name, size in order:
        if name in place:
            continue
        fits = [(f - size, i) for i, f in enumerate(free) if f >= size]
        if not fits:
            return None
        i = min(fits)[1]
        place[name] = (i, WINDOW + SIZES[i] - free[i])
        free[i] -= size
    return place, free


# Three blobs are pinned, because where they land has consequences
# beyond fitting:
#   the level's tiles      C4, so the tilemap engine always pages the
#                          same bank and the scrolling demo can drop the
#                          placeholder tileset on top of it
#   kcore / kcore_l        C5 and C6, one facing each, so the two banks
#   (the heroine)          Kara is drawn from are never the tilemap's
# THE ENGINE ADDRESSES HER BY CONSTANT, not by a lookup, so where her
# frames live cannot be an allocator decision. src/kara.asm pages a bank
# and reads a frame table at a fixed address; a run that came back in a
# different bank each level would need a per-level table in RAM and a
# reload of it at every transition, for animation sets that are the same
# bytes in every level anyway.
#
#   C5   kcore     facing right   idle / walk / jump / shoot_draw / shoot
#   C6   kcore_l   facing left
#   C7   kextra + kextra_l        run / roll, BOTH facings, one bank
#        ... or kswim + kswim_l on level 4, which swims instead
#
# C7 is the title buffer while the title is up and free by the time a
# level runs, which is what makes the third bank affordable. The pair
# fits: 7,179 x 2 = 14,358 of 16,384, and the swim pair 6,624 x 2.
PINNED = {"kcore": 2, "kcore_l": 3,          # indices into BANKS
          "kextra": 4, "kextra_l": 4,
          "kswim": 4, "kswim_l": 4}


def pin_of(name):
    if name in PINNED:
        return PINNED[name]
    if name.endswith("tiles"):
        return 1                             # C4
    return None


def allocate(items):
    """Fit the blobs into the five banks. Returns {name: (bank, addr)}."""
    big = sorted(items, key=lambda kv: -kv[1])
    r = _try(big)
    if r:
        return r
    rng = random.Random(12345)              # deterministic: the same build
    for _ in range(2000):                   # must give the same map
        order = big[:]
        rng.shuffle(order)
        r = _try(order)
        if r:
            return r
    total = sum(s for _, s in items)
    raise SystemExit(f"cannot fit {total} bytes into "
                     f"{sum(SIZES)}: biggest are "
                     f"{[(n, s) for n, s in big[:4]]}")


def build(level, setpieces=False):
    d = os.path.join(LEV, level)
    shared = SHARED_SWIM if level == "level4_underwater" else SHARED_ALWAYS
    items, src = [], {}
    for f in blobs(level):
        # prefix, not equality: a sheet too big for a bank was split by
        # tag, so the shuttle is desertshuttle_idle / _launch
        is_set = any(stem(f).startswith(sp) for sp in SETPIECE)
        if is_set != setpieces:
            continue
        p = os.path.join(d, f)
        items.append((stem(f), os.path.getsize(p)))
        src[stem(f)] = p
    if not setpieces:
        climbs = has_ladder(level)
        for s in shared:
            f = s
            if s == "kact" and not climbs:
                f = "kactnoclimb"            # the same blob, minus the tail
            p = os.path.join(LEV, "_shared", f + ".bin")
            if os.path.exists(p):
                items.append((s, os.path.getsize(p)))
                src[s] = p                   # ... under the name KACT, so the
                                             # engine's symbol does not move
    if not items:
        return None
    place, free = allocate(items)

    out = []
    for i, (cfg, code) in enumerate(BANKS):
        img = bytearray(BANK_SIZE)
        used = 0
        for name, (b, addr) in place.items():
            if b != i:
                continue
            data = open(src[name], "rb").read()
            img[addr - WINDOW:addr - WINDOW + len(data)] = data
            used = max(used, addr - WINDOW + len(data))
        if not used:
            continue
        tag = "set" if setpieces else "lvl"
        raw = os.path.join(d, f"{tag}_{cfg}.bin")
        open(raw, "wb").write(bytes(img[:used]))
        pk = pack(raw, os.path.join(d, f"{tag}_{cfg}.zx0"))
        out.append((cfg, code, used, pk))
    return place, out


def main():
    levels = sorted(x for x in os.listdir(LEV)
                    if x.startswith("level") and
                    os.path.isdir(os.path.join(LEV, x)))
    inc = ["; Generated by tools/level_banks.py",
           "; Where every blob lives once its level is loaded.", ""]
    grand = 0
    every = {}
    for lvl in levels:
        for setp in (False, True):
            r = build(lvl, setp)
            if not r:
                continue
            place, banks = r
            every.setdefault(lvl + ("_set" if setp else ""), {}).update(place)
            tot_raw = sum(b[2] for b in banks)
            tot_pk = sum(b[3] for b in banks)
            grand += tot_pk
            kind = "set pieces" if setp else "gameplay  "
            print(f"\n  {lvl} {kind}  {tot_raw:6d} raw in "
                  f"{len(banks)} bank(s), {tot_pk:5d} packed")
            for cfg, code, used, pk in banks:
                print(f"    &{code:02X}  {used:6d} -> {pk:5d}"
                      f"   {SIZES[BANKS.index((cfg, code))] - used:6d} spare")
            pre = lvl.upper().replace("LEVEL", "L").split("_")[0]
            inc.append(f"; ---- {lvl} {'set pieces' if setp else 'gameplay'}")
            for name, (b, addr) in sorted(place.items(),
                                          key=lambda kv: (kv[1][0], kv[1][1])):
                sym = f"{pre}_{name.upper()}"
                inc.append(f"{sym + '_BANK':<28} equ &{BANKS[b][1]:02X}")
                inc.append(f"{sym + '_ADDR':<28} equ &{addr:04X}")
            inc.append("")
    # The pinned blobs, once, without a level prefix. src/kara.asm reads
    # her frames through these: they are the same bank and the same
    # address in every level BY CONSTRUCTION (see PINNED), so the engine
    # addresses her with a constant instead of a table it would have to
    # reload at every transition. Emitting them from the allocator and
    # not by hand is what makes that a checked fact rather than a
    # comment - a pin that stopped holding fails the build here.
    fixed = ["; ---- pinned: the same in EVERY level, asserted below"]
    for name in sorted(PINNED):
        seen = {(b, a) for lv, pl in every.items() for n, (b, a) in pl.items()
                if n == name}
        if not seen:
            continue
        if len(seen) != 1:
            raise SystemExit(f"{name} is pinned but landed in {len(seen)} "
                             f"different places: {sorted(seen)}")
        b, addr = seen.pop()
        sym = name.upper()
        fixed.append(f"{sym + '_PIN_BANK':<28} equ &{BANKS[b][1]:02X}")
        fixed.append(f"{sym + '_PIN_ADDR':<28} equ &{addr:04X}")
    fixed.append("")
    open(os.path.join(LEV, "banks.inc"), "w").write(
        "\n".join(fixed + inc) + "\n")
    print(f"\n  {grand} bytes of packed level data in all "
          f"({grand / 1024:.0f} KB on the disc)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
