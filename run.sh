#!/usr/bin/env bash
# One command for an official run:
#   ./run.sh <organisations.jsonl|.json|.txt> [output-dir]
# Creates a clean virtual environment, installs the pinned dependencies, researches every
# organisation number and writes envelopes.jsonl, run-report.json and a static viewer.
# A second run with the same output directory is a refresh: it diffs against the previous envelopes.
set -euo pipefail
INPUT="${1:?usage: ./run.sh <organisations file> [output dir]}"
OUT="${2:-out}"
HERE="$(cd "$(dirname "$0")" && pwd)"
PY="${PYTHON:-python3}"
if [ ! -x "$HERE/.venv/bin/python" ]; then
  "$PY" -m venv "$HERE/.venv"
  "$HERE/.venv/bin/python" -m pip install --quiet --disable-pip-version-check -r "$HERE/requirements.txt"
fi
mkdir -p "$OUT"
export PYTHONPATH="$HERE${PYTHONPATH:+:$PYTHONPATH}"
exec "$HERE/.venv/bin/python" -m kildespor run \
  --organisations "$INPUT" \
  --output "$OUT/envelopes.jsonl" \
  --report "$OUT/run-report.json" \
  --html "$OUT/viewer" \
  ${KILDESPOR_ARGS:-}
