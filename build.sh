#!/usr/bin/env bash
# =====================================================================
# Build kara.dsk from source.
#   rasm  assembles src/main.asm into a raw binary
#   iDSK  wraps it in an AMSDOS header and puts it on a fresh disc image
#         alongside the ASCII BASIC loader
# =====================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
BUILD="$ROOT/build"
DSK="kara.dsk"

mkdir -p "$BUILD"
rm -f "$BUILD/$DSK" "$BUILD/game.bin"

# --- assets -----------------------------------------------------------
# Regenerated every build so the binaries can never drift from the art.
# main.asm INCBINs the level's map; Module 6 links the title.
#
# THE PLACEHOLDER SHEET IS NOT EXPORTED ANY MORE. png2sprite.py made a
# 16x48 masked sprite for the Module 1-3 acceptance screen, and both the
# screen and the blitter that drew it are gone; the game draws her out
# of the span blobs build_levels.py exports below. Nor does anything
# here write preview PNGs: the build makes the disc, and a picture of
# the game comes from running it.

# ALL THE SPRITE ART, one directory per level plus a shared set.
# tools/build_levels.py walks the artists' manifest.json files, exports
# every sheet (tiles raw, everything else span-compressed, both facings
# where the thing turns to face her), and tools/level_banks.py lays the
# blobs out into banks and ZX0-packs one stream per bank. See
# CLAUDE.md 6.2, 7.1 and 7.4.
rm -rf "$BUILD/levels"
python3 "$ROOT/tools/build_levels.py"

# The City map, over the DRAWN 8x16 tiles. The tiles themselves are no
# longer generated or linked: build_levels.py exported them into the
# level's bank and LEVEL_LOAD unpacks them there, so only the map rides
# in the core image. Must run AFTER build_levels.py - it reads that
# export's sidecar to check the tile numbering has not shifted - and
# BEFORE level_banks.py, because it appends the baked overlay tiles to
# the level's tile blob (CLAUDE.md 7.3) and the banking has to see them.
# It re-packs that blob's .zx0 itself, since build_levels.py packed it
# before there was anything appended.
python3 "$ROOT/tools/make_city_map.py"

# ... and then the same bytes in the EDITOR's format. make_level.py is
# the reference implementation of docs/editor.md 9.2 and the engine's
# LEVEL_PARSE reads what it writes, so the format has a golden file and
# a level that is played on real hardware before the editor exists.
python3 "$ROOT/tools/make_level.py"

python3 "$ROOT/tools/level_banks.py"

# Where a shot leaves each firing frame, against the BLOB's numbering.
python3 "$ROOT/tools/spawns.py"

python3 "$ROOT/tools/png2screen.py" "$ROOT/assets/title/title_render.png" \
        -o "$BUILD/overscan.bin" \
        --inc "$BUILD/title_palette.asm" \
        --dither

# Where the level streams will sit on the disc. The layout comes from
# their sizes alone, so the include can be written before RASM runs and
# the image patched after iDSK has built it.
python3 "$ROOT/tools/dskdata.py" --inc

# --- code -------------------------------------------------------------

# ZX0 for everything that goes on the disc. It is the best cruncher RASM
# ships on BOTH ratio and depack speed - see tools/pack.py for the nine
# that were measured - and it buys disc space and load time, not frame
# time: the blitter reads uncompressed bytes out of a bank.
python3 "$ROOT/tools/pack.py" city_map.bin overscan.bin
# ... and it has to come AFTER everything it packs. It used to run
# before the tile exporter and quietly shipped the PREVIOUS build's tiles.


rasm "$ROOT/src/main.asm" -I "$ROOT/src" -I "$BUILD" -amper \
     -ob "$BUILD/game.bin" \
     -s -sa -os "$BUILD/game.sym"

cp "$ROOT/disc/disc.bas" "$BUILD/disc.bas"

cd "$BUILD"
iDSK "$DSK" -n >/dev/null
# -t 1 binary, -c load address, -e execution address
iDSK "$DSK" -i game.bin -t 1 -c 4000 -e 4000 -f >/dev/null
iDSK "$DSK" -i disc.bas -t 0 -f >/dev/null
rm -f disc.bas

echo "--- $DSK ---"
# ... and now the level streams go in as raw sectors, past the files.
python3 "$ROOT/tools/dskdata.py" --dsk

iDSK "$DSK" -l
