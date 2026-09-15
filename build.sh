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

# The drawn heroine, span-compressed. Six blobs out of two sheets: the
# art is bigger than a bank, and BOTH FACINGS are stored because
# mirroring at draw time costs ~7,900 T a frame and the frame has not
# got it - see CLAUDE.md 6.2 and 7.1. Built every time so the format
# and the art cannot drift apart; tools/test_spans.py checks them.
ASE="$ROOT/assets/sprites"
# Clear the sprite outputs first: which blobs exist is decided by the
# loops below, and a stale one from a previous layout is indistinguishable
# from a current one to anything that enumerates the build directory.
rm -f "$BUILD"/kara_core*.bin "$BUILD"/kara_core*.inc \
      "$BUILD"/kara_extra*.bin "$BUILD"/kara_extra*.inc \
      "$BUILD"/kara_swim*.bin "$BUILD"/kara_swim*.inc \
      "$BUILD"/kara_*_frames.json \
      "$BUILD"/enem*.bin "$BUILD"/enem*.inc "$BUILD"/enem*_frames.json \
      "$BUILD"/spear*.bin "$BUILD"/spear*.inc "$BUILD"/spear*_frames.json \
      "$BUILD"/bullet*.bin "$BUILD"/bullet*.inc "$BUILD"/bullet*_frames.json \
      "$BUILD"/*.zx0
python3 "$ROOT/tools/aseprite2spans.py" "$ASE/heroine_cpc_mode0_sheet.json" \
        -o "$BUILD/kara_core.bin" --inc "$BUILD/kara_core.inc" --name KCORE \
        --tags idle,walk,jump,shoot_draw,shoot \
        --drop idle=3 --drop walk=2,4,6 --drop run=2,4,6 --drop jump=3,5 \
        --mirror-table "$BUILD/mode0_mirror.bin"
python3 "$ROOT/tools/aseprite2spans.py" "$ASE/heroine_cpc_mode0_sheet.json" \
        -o "$BUILD/kara_extra.bin" --inc "$BUILD/kara_extra.inc" --name KEXTRA \
        --tags run,roll \
        --drop idle=3 --drop walk=2,4,6 --drop run=2,4,6 --drop jump=3,5
python3 "$ROOT/tools/aseprite2spans.py" "$ASE/heroine_cpc_mode0_swim_sheet.json" \
        -o "$BUILD/kara_swim.bin" --inc "$BUILD/kara_swim.inc" --name KSWIM
python3 "$ROOT/tools/aseprite2spans.py" "$ASE/heroine_cpc_mode0_sheet.json" \
        -o "$BUILD/kara_core_l.bin" --inc "$BUILD/kara_core_l.inc" --name KCOREL \
        --tags idle,walk,jump,shoot_draw,shoot --mirror \
        --drop idle=3 --drop walk=2,4,6 --drop run=2,4,6 --drop jump=3,5
python3 "$ROOT/tools/aseprite2spans.py" "$ASE/heroine_cpc_mode0_sheet.json" \
        -o "$BUILD/kara_extra_l.bin" --inc "$BUILD/kara_extra_l.inc" --name KEXTRAL \
        --tags run,roll --mirror \
        --drop idle=3 --drop walk=2,4,6 --drop run=2,4,6 --drop jump=3,5
python3 "$ROOT/tools/aseprite2spans.py" "$ASE/heroine_cpc_mode0_swim_sheet.json" \
        -o "$BUILD/kara_swim_l.bin" --inc "$BUILD/kara_swim_l.inc" --name KSWIML \
        --mirror

# The enemies and the projectiles, same format, both facings. Six enemy
# types share one sheet (merc, hunter, commando, guard, raider, heavy),
# two more swim (diver, frogman), and the spear and bullet are the
# things they and Kara throw.
# ONE BLOB PER ENEMY TYPE. All six together are 23,278 bytes, half as
# much again as a bank, and no level wants all six anyway - the banks
# are reloaded per level, so the loader picks the types that level uses.
for e in merc hunter commando guard raider heavy; do
    for f in "" "_l"; do
        python3 "$ROOT/tools/aseprite2spans.py" "$ASE/enemies_cpc_mode0_sheet.json" \
                -o "$BUILD/enemy_$e$f.bin" --inc "$BUILD/enemy_$e$f.inc" \
                --name "E$(echo $e | tr a-z A-Z)$(echo $f | tr a-z A-Z)" \
                --tags "${e}_walk,${e}_fire" ${f:+--mirror}
    done
done
for e in diver frogman; do
    for f in "" "_l"; do
        python3 "$ROOT/tools/aseprite2spans.py" "$ASE/enemies_swim_cpc_mode0_sheet.json" \
                -o "$BUILD/enemy_$e$f.bin" --inc "$BUILD/enemy_$e$f.inc" \
                --name "E$(echo $e | tr a-z A-Z)$(echo $f | tr a-z A-Z)" \
                --tags "${e}_swim,${e}_fire" ${f:+--mirror}
    done
done
for pair in "spear_cpc_mode0_sheet SPEAR spear" \
            "bullet_cpc_mode0_sheet BULLET bullet"; do
    set -- $pair
    python3 "$ROOT/tools/aseprite2spans.py" "$ASE/$1.json" \
            -o "$BUILD/$3.bin" --inc "$BUILD/$3.inc" --name "$2"
    python3 "$ROOT/tools/aseprite2spans.py" "$ASE/$1.json" \
            -o "$BUILD/${3}_l.bin" --inc "$BUILD/${3}_l.inc" --name "${2}L" --mirror
done

# Where a shot leaves each firing frame, against the BLOB's numbering.
python3 "$ROOT/tools/spawns.py"

# ZX0 for everything that goes on the disc. It is the best cruncher RASM
# ships on BOTH ratio and depack speed - see tools/pack.py for the nine
# that were measured - and it buys disc space and load time, not frame
# time: the blitter reads uncompressed bytes out of a bank.
python3 "$ROOT/tools/pack.py" kara_core.bin kara_core_l.bin \
        kara_extra.bin kara_extra_l.bin kara_swim.bin kara_swim_l.bin \
        enemy_merc.bin enemy_merc_l.bin enemy_hunter.bin enemy_hunter_l.bin \
        enemy_commando.bin enemy_commando_l.bin enemy_guard.bin enemy_guard_l.bin \
        enemy_raider.bin enemy_raider_l.bin enemy_heavy.bin enemy_heavy_l.bin \
        enemy_diver.bin enemy_diver_l.bin enemy_frogman.bin enemy_frogman_l.bin \
        spear.bin spear_l.bin bullet.bin bullet_l.bin \
        city_tiles.bin city_map.bin overscan.bin

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
