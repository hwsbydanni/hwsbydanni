#!/usr/bin/env bash
# Every check that can pass or fail on its own. Run before pushing a change
# to the CSS, the markup or the metadata.
#
#   tools/check_all.sh            # the fast set
#   tools/check_all.sh --states   # also hover every link and open every accordion
#
# Exits non-zero if any check fails, so it can gate a commit.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

status=0
for check in check_metadata.py check_css.py check_gutters.py; do
  echo "=============================================================="
  python3 "tools/$check" || status=1
done

echo "=============================================================="
python3 tools/check_contrast.py "$@" || status=1

echo "=============================================================="
if [ $status -eq 0 ]; then echo "All checks passed."; else echo "Some checks FAILED (see above)."; fi
exit $status
