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
# main.asm INCBINs the sprites and the level; Module 6 links the title.
python3 "$ROOT/tools/png2sprite.py" "$ROOT/assets/placeholder/kara_sheet.png" \
        -o "$BUILD/kara_sprites.bin" \
        --inc "$BUILD/kara_sprites.inc" \
        --preview "$BUILD/kara_preview.png"

# ALL THE SPRITE ART, one directory per level plus a shared set.
# tools/build_levels.py walks the artists' manifest.json files, exports
# every sheet (tiles raw, everything else span-compressed, both facings
# where the thing turns to face her), and tools/level_banks.py lays the
# blobs out into banks and ZX0-packs one stream per bank. See
# CLAUDE.md 6.2, 7.1 and 7.4.
rm -rf "$BUILD/levels"
python3 "$ROOT/tools/build_levels.py"
python3 "$ROOT/tools/level_banks.py"

# Where a shot leaves each firing frame, against the BLOB's numbering.
python3 "$ROOT/tools/spawns.py"

python3 "$ROOT/tools/png2screen.py" "$ROOT/assets/title/title_render.png" \
        -o "$BUILD/overscan.bin" \
        --inc "$BUILD/title_palette.asm" \
        --preview "$BUILD/title_preview.png" --dither

# --- code -------------------------------------------------------------
python3 "$ROOT/tools/make_placeholder_level.py"
python3 "$ROOT/tools/png2tiles.py" "$ROOT/assets/placeholder/city_tiles.png" \
        -o "$BUILD/city_tiles.bin" --inc "$BUILD/city_tiles.inc"
cp "$ROOT/assets/placeholder/city_map.bin" "$BUILD/city_map.bin"

# ZX0 for everything that goes on the disc. It is the best cruncher RASM
# ships on BOTH ratio and depack speed - see tools/pack.py for the nine
# that were measured - and it buys disc space and load time, not frame
# time: the blitter reads uncompressed bytes out of a bank.
python3 "$ROOT/tools/pack.py" city_tiles.bin city_map.bin overscan.bin
# ... and it has to come AFTER everything it packs. It used to run
# before png2tiles and quietly shipped the PREVIOUS build's tiles.


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
iDSK "$DSK" -l
