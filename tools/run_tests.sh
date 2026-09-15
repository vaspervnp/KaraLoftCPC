#!/usr/bin/env bash
# Every acceptance test, in dependency order. Assumes ./build.sh has run.
set -uo pipefail
cd "$(dirname "$0")/.."
status=0
for t in tools/test_cpclib.py tools/test_fdc.py tools/test_sprites.py tools/test_spans.py tools/test_spanblit.py tools/test_kara.py tools/test_levels.py tools/test_overscan.py tools/test_module1.py tools/test_actions.py tools/test_entities.py tools/test_enemies.py tools/test_module3.py tools/test_module4.py; do
    echo "=== $t"
    python3 "$t" || status=1
done
echo
[ $status -eq 0 ] && echo "ALL SUITES PASSED" || echo "SOME SUITES FAILED"
exit $status
