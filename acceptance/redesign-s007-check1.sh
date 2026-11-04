#!/usr/bin/env bash
# Locked check, redesign S-007. CHECK 1: the three web faces load woff2 files cut faithfully from their sources (AC-178, AC-179)
# Run from the repo root as `bash acceptance/redesign-s007-check1.sh`. Sets up what it needs; exits 0 only when every case passes.
# senior-lead-Opus5.5-agent, 2026-11-04
set -euo pipefail
venv="${CVWRITE_TEST_VENV:-$HOME/.cvwrite3-test-venv}"
bash scripts/install.sh "$venv"
grep -v '^-r' requirements-dev.txt | "$venv/bin/pip" install --only-binary :all: -r /dev/stdin
"$venv/bin/pip" install --require-hashes --only-binary :all: -r acceptance/redesign-s007-requirements.txt
export PYTHONDONTWRITEBYTECODE=1
exec "$venv/bin/python" -m unittest discover -s acceptance -p 'redesign_s007_check1.py' -v
