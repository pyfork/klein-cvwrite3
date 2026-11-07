#!/usr/bin/env bash
# Locked check, redesign S-008. CHECK 1: the flag CVWRITE_HOME (AC-185, AC-186)
# Run from the repo root as `bash acceptance/redesign-s008-check1.sh`. Sets up what it needs; exits 0 only when every case passes.
# senior-lead-Opus5.5-agent, 2026-11-07
set -euo pipefail
venv="${CVWRITE_TEST_VENV:-$HOME/.cvwrite3-test-venv}"
bash scripts/install.sh "$venv"
grep -v '^-r' requirements-dev.txt | "$venv/bin/pip" install --only-binary :all: -r /dev/stdin
export PYTHONDONTWRITEBYTECODE=1
exec "$venv/bin/python" -m unittest discover -s acceptance -p 'redesign_s008_check1.py' -v
