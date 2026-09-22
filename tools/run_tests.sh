#!/usr/bin/env bash
# Every acceptance test, in dependency order. Assumes ./build.sh has run.
#
# test_painter.py, test_generated.py and test_transition.py are LAST
# because they are the only ones that write into build/: the first puts
# the editor's own level there and relinks the disc three times, the
# second a level the editor GENERATED and relinks once, the third writes
# two more levels and relinks once. All three run ./build.sh again to put
# the generator's back, and all three check the shipped disc returns byte
# for byte.
set -uo pipefail
cd "$(dirname "$0")/.."
status=0
for t in tools/test_cpclib.py tools/test_fdc.py tools/test_spans.py tools/test_spanblit.py tools/test_xclip.py tools/test_kara.py tools/test_levels.py tools/test_overscan.py tools/test_module1.py tools/test_intro.py tools/test_loader.py tools/test_hud.py tools/test_format.py tools/test_shape.py tools/test_actions.py tools/test_entities.py tools/test_enemies.py tools/test_climb.py tools/test_module4.py tools/test_module5.py tools/test_flow.py tools/test_forest.py tools/test_painter.py tools/test_generated.py tools/test_transition.py; do
    echo "=== $t"
    python3 "$t" || status=1
done
echo
[ $status -eq 0 ] && echo "ALL SUITES PASSED" || echo "SOME SUITES FAILED"
exit $status
