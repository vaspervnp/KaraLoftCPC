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

# The drawn heroine, span-compressed. Two blobs out of one sheet because
# 24x64 does not fit a 16 KB bank whole - see CLAUDE.md 6.2 and 7.1. The
# span blitter is not written yet, so nothing INCBINs these; they are
# built every time so the format and the art cannot drift apart, and
# tools/test_spans.py checks them.
ASE="$ROOT/assets/sprites"
python3 "$ROOT/tools/aseprite2spans.py" "$ASE/heroine_cpc_mode0_sheet.json" \
        -o "$BUILD/kara_core.bin" --inc "$BUILD/kara_core.inc" --name KCORE \
        --tags idle,walk,jump,shoot_draw,shoot \
        --mirror-table "$BUILD/mode0_mirror.bin"
python3 "$ROOT/tools/aseprite2spans.py" "$ASE/heroine_cpc_mode0_sheet.json" \
        -o "$BUILD/kara_extra.bin" --inc "$BUILD/kara_extra.inc" --name KEXTRA \
        --tags run,roll
python3 "$ROOT/tools/aseprite2spans.py" "$ASE/heroine_cpc_mode0_swim_sheet.json" \
        -o "$BUILD/kara_swim.bin" --inc "$BUILD/kara_swim.inc" --name KSWIM

python3 "$ROOT/tools/png2screen.py" "$ROOT/assets/title/title_render.png" \
        -o "$BUILD/overscan.bin" \
        --inc "$BUILD/title_palette.asm" \
        --preview "$BUILD/title_preview.png" --dither

# --- code -------------------------------------------------------------
python3 "$ROOT/tools/make_placeholder_level.py"
python3 "$ROOT/tools/png2tiles.py" "$ROOT/assets/placeholder/city_tiles.png" \
        -o "$BUILD/city_tiles.bin" --inc "$BUILD/city_tiles.inc"
cp "$ROOT/assets/placeholder/city_map.bin" "$BUILD/city_map.bin"

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
