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

rasm "$ROOT/src/main.asm" -I "$ROOT/src" -amper \
     -ob "$BUILD/game.bin" \
     -os "$BUILD/game.sym" -sa

cp "$ROOT/disc/disc.bas" "$BUILD/disc.bas"

cd "$BUILD"
iDSK "$DSK" -n >/dev/null
# -t 1 binary, -c load address, -e execution address
iDSK "$DSK" -i game.bin -t 1 -c 4000 -e 4000 -f >/dev/null
iDSK "$DSK" -i disc.bas -t 0 -f >/dev/null
rm -f disc.bas

echo "--- $DSK ---"
iDSK "$DSK" -l
