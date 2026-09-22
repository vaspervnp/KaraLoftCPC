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

# --relink: ASSEMBLE AND IMAGE WHAT build/ ALREADY HOLDS. Every generator
# below - the sprite export, the City's map, level_1.lvl, the title, the
# HUD - is skipped, and only the steps that turn build/'s own bytes into a
# disc are run: the bank layout, the sector map, RASM and iDSK.
#
# It is here for tools/test_painter.py, which puts the EDITOR's own three
# files into build/ and needs a disc made of them - make_city_map.py and
# make_level.py would write the generator's straight back over them.
# Nothing else should use it: a disc built this way is exactly as current
# as whatever happened to be in build/ when it ran.
RELINK=0
if [ "${1:-}" = "--relink" ]; then
    RELINK=1
    echo "=== --relink: nothing is regenerated; build/ is taken as it stands ==="
fi
gen() { [ "$RELINK" = 1 ] && return 0; "$@"; }

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
gen rm -rf "$BUILD/levels"
gen python3 "$ROOT/tools/build_levels.py"

# The City map, over the DRAWN 8x16 tiles. The tiles themselves are no
# longer generated or linked: build_levels.py exported them into the
# level's bank and LEVEL_LOAD unpacks them there, so only the map rides
# in the core image. Must run AFTER build_levels.py - it reads that
# export's sidecar to check the tile numbering has not shifted - and
# BEFORE level_banks.py, because it appends the baked overlay tiles to
# the level's tile blob (CLAUDE.md 7.3) and the banking has to see them.
# It re-packs that blob's .zx0 itself, since build_levels.py packed it
# before there was anything appended.
gen python3 "$ROOT/tools/make_city_map.py"

# ... and then the same bytes in the EDITOR's format. make_level.py is
# the reference implementation of docs/editor.md 9.2 and the engine's
# LEVEL_PARSE reads what it writes, so the format has a golden file and
# a level that is played on real hardware before the editor exists.
gen python3 "$ROOT/tools/make_level.py"

# LEVEL 5: THE FOREST, and the first map that is not the City's. It
# writes the format directly - there is no city_map.bin step to mirror,
# because there are no overlays to bake: all 42 of the forest's tiles
# are `draw: opaque` in its tile_table.json. Gated like the other
# generators, so --relink carries whatever build/ already holds.
gen python3 "$ROOT/tools/make_forest_map.py"

# ... and the cave's, which is the first level that is TALL (32x64) and
# the first since the City with OVERLAYS in it - its ladder is one. So
# like make_city_map.py above it must run AFTER build_levels.py, which
# exports cavetiles.bin, and BEFORE level_banks.py, which lays that
# blob into a bank: it appends the baked pairs to it and re-packs the
# .zx0 itself.
gen python3 "$ROOT/tools/make_cave_map.py"

python3 "$ROOT/tools/level_banks.py"

# A level's OWN bytes - its map, its entity table and its tile flags -
# as one packed stream for the disc. They used to be INCBINed into the
# core image, which is 2,200 bytes for one level and no room at all for
# six (CLAUDE.md 7.5).
#
# UNGATED, like level_banks.py above and for the same reason: it is not
# a generator, it is the container the two files travel in, and
# --relink has to carry whatever build/ holds onto the disc.
python3 "$ROOT/tools/make_level_image.py"

# Where a shot leaves each firing frame, against the BLOB's numbering.
gen python3 "$ROOT/tools/spawns.py"

gen python3 "$ROOT/tools/png2screen.py" "$ROOT/assets/title/title_render.png" \
        -o "$BUILD/overscan.bin" \
        --inc "$BUILD/title_palette.asm" \
        --dither

# Where the level streams will sit on the disc. The layout comes from
# their sizes alone, so the include can be written before RASM runs and
# the image patched after iDSK has built it.
# The title picture: the artist's linear .scr into the CRTC's own screen
# order, ZX0-packed for the disc, plus its palette and the two strips the
# PRESS SPACE OR FIRE prompt blinks between. Must run BEFORE dskdata.py,
# which lays the packed streams out on the disc from their sizes.
gen python3 "$ROOT/tools/make_intro.py"

# The HUD's two health cells, as raw Mode 0 bytes for the core image.
gen python3 "$ROOT/tools/make_hud.py"

# The fade ramp: one step toward black for every hardware colour, out
# of the 3x3x3 cube the CPC palette is (CLAUDE.md 6.6). Generated
# because the cube is a fact about the hardware and a table typed from
# it would be a second copy of docs/cpc_palette.md.
gen python3 "$ROOT/tools/make_fade.py"

python3 "$ROOT/tools/dskdata.py" --inc

# --- code -------------------------------------------------------------

# ZX0 for everything that goes on the disc. It is the best cruncher RASM
# ships on BOTH ratio and depack speed - see tools/pack.py for the nine
# that were measured - and it buys disc space and load time, not frame
# time: the blitter reads uncompressed bytes out of a bank.
gen python3 "$ROOT/tools/pack.py" city_map.bin overscan.bin
# ... and it has to come AFTER everything it packs. It used to run
# before the tile exporter and quietly shipped the PREVIOUS build's tiles.


rasm "$ROOT/src/main.asm" -I "$ROOT/src" -I "$BUILD" -amper \
     -ob "$BUILD/game.bin" \
     -s -sa -os "$BUILD/game.sym"

cp "$ROOT/disc/disc.bas" "$BUILD/disc.bas"

# THE FRONT DOOR: the label screen, then the game. Generated rather
# than written, because its sixteen INKs are the artist's palette note
# and a typed copy would go stale silently.
python3 "$ROOT/tools/make_loader.py"
cp "$ROOT/assets/revive8b.scr" "$BUILD/revive8b.scr"

cd "$BUILD"
iDSK "$DSK" -n >/dev/null
# -t 1 binary, -c load address, -e execution address
iDSK "$DSK" -i game.bin -t 1 -c 4000 -e 4000 -f >/dev/null
iDSK "$DSK" -i disc.bas -t 0 -f >/dev/null
iDSK "$DSK" -i kara.bas -t 0 -f >/dev/null
# ... and the label screen, a whole 16 KB one, straight to video RAM
iDSK "$DSK" -i revive8b.scr -t 1 -c C000 -e C000 -f >/dev/null
rm -f disc.bas revive8b.scr

echo "--- $DSK ---"
# ... and now the level streams go in as raw sectors, past the files.
python3 "$ROOT/tools/dskdata.py" --dsk

iDSK "$DSK" -l
