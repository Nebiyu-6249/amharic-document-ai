#!/usr/bin/env bash
# Control C-39: dependency audit with a build-failing threshold.
#
# Two tiers, because they have different risk and different remediability:
#
#   api + dev  -- STRICT. Any advisory fails the build. These are the images that face
#                 the internet and run in CI, so there is no acceptable finding here.
#
#   ml         -- TRACKED. The ml extra is pinned transitively by kraken 7.1, which
#                 requires click>=8.1,<8.3 and lightning==2.6.1 exactly. Both carry
#                 advisories and neither can be upgraded without kraken moving --
#                 verified by resolver error, not assumed. lightning's advisory has NO
#                 fixed version at all. Those two ids are listed below and everything
#                 else still fails the build, so a NEW ml advisory is not swallowed.
#
# The ml stack never runs in the API container (ADR-0007 / C-45), which is what keeps
# this tolerable rather than urgent.

set -euo pipefail
PY="${PY:-.venv/bin/python}"

# Known-unfixable, blocked by kraken 7.1's pins. Review whenever kraken is upgraded.
ML_TRACKED_IGNORES=(
  --ignore-vuln PYSEC-2026-2132   # click 8.2.1  -> fixed in 8.3.3, blocked by kraken
  --ignore-vuln PYSEC-2026-3624   # lightning 2.6.1 -> NO fix published
)

echo "--- C-39 strict: api ---"
"$PY" -m pip_audit -r requirements/api.lock.txt --progress-spinner off

echo "--- C-39 strict: dev ---"
"$PY" -m pip_audit -r requirements/dev.lock.txt --progress-spinner off

if [ -f requirements/ml.lock.txt ]; then
  echo "--- C-39 tracked: ml (kraken-pinned exceptions listed in this script) ---"
  "$PY" -m pip_audit -r requirements/ml.lock.txt --progress-spinner off "${ML_TRACKED_IGNORES[@]}"
fi

echo "C-39: dependency audit passed."
