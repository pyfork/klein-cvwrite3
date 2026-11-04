#!/usr/bin/env bash
# Locked check, redesign S-007. REGRESSION A: serving the fonts as woff2 changes nothing else (AC-182). Passes before the work
# Run from the repo root as `bash acceptance/redesign-s007-regression.sh`. Sets up what it needs; exits 0 only when every case passes.
# senior-lead-Opus5.5-agent, 2026-11-04
set -euo pipefail
venv="${CVWRITE_TEST_VENV:-$HOME/.cvwrite3-test-venv}"
bash scripts/install.sh "$venv"
grep -v '^-r' requirements-dev.txt | "$venv/bin/pip" install --only-binary :all: -r /dev/stdin
export PYTHONDONTWRITEBYTECODE=1
exec "$venv/bin/python" -m unittest discover -s acceptance -p 'redesign_s007_regression.py' -v
