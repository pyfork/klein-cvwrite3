#!/usr/bin/env bash
# Locked check, redesign S-009. CHECK 1: the frame, the header and the hero as their words and links (AC-100, AC-104, AC-107, AC-109 to AC-111, AC-117, AC-161, AC-162, the home's budget)
# Run from the repo root as `bash acceptance/redesign-s009-check1.sh`. Sets up what it needs; exits 0 only when every case passes.
# The Chrome cases need Chrome (CVWRITE_CHROME); a missing Chrome fails the check, it is never skipped.
# senior-lead-Opus5.5-agent, 2026-11-08
set -euo pipefail
venv="${CVWRITE_TEST_VENV:-$HOME/.cvwrite3-test-venv}"
bash scripts/install.sh "$venv"
grep -v '^-r' requirements-dev.txt | "$venv/bin/pip" install --only-binary :all: -r /dev/stdin
if [ -z "${CVWRITE_CHROME:-}" ]; then
  c="$(grep -E '^CVWRITE_CHROME=' env.example | cut -d= -f2-)"
  if [ -n "$c" ] && [ -x "$c" ]; then export CVWRITE_CHROME="$c"; fi
fi
export PYTHONDONTWRITEBYTECODE=1
exec "$venv/bin/python" -m unittest discover -s acceptance -p 'redesign_s009_check1.py' -v
