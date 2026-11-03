#!/usr/bin/env bash
# Locked check, redesign S-006. CHECK 2: the seeded generator and its hashed pins (AC-93, AC-94 pins)
# Run from the repo root as `bash acceptance/redesign-s006-check2.sh`. Sets up what it needs; exits 0 only when every case passes.
# senior-lead-Opus5.5-agent, 2026-11-03
set -euo pipefail
venv="${CVWRITE_TEST_VENV:-$HOME/.cvwrite3-test-venv}"
bash scripts/install.sh "$venv"
export PYTHONDONTWRITEBYTECODE=1
exec "$venv/bin/python" -m unittest discover -s acceptance -p 'redesign_s006_check2.py' -v
