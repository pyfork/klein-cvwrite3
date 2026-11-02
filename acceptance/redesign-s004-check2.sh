#!/usr/bin/env bash
# Locked check, redesign S-004. CHECK 2: the list is exact and the real tree passes (AC-86 to AC-88)
# Run from the repo root as `bash acceptance/redesign-s004-check2.sh`. Sets up what it needs; exits 0 only when every case passes.
# senior-lead-Sonnet5.5-agent, 2026-11-03
set -euo pipefail
venv="${CVWRITE_TEST_VENV:-$HOME/.cvwrite3-test-venv}"
bash scripts/install.sh "$venv"
export PYTHONDONTWRITEBYTECODE=1
exec "$venv/bin/python" -m unittest discover -s acceptance -p 'redesign_s004_check2.py' -v
