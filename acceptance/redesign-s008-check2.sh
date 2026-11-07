#!/usr/bin/env bash
# Locked check, redesign S-008. CHECK 2: the top half's look in Chrome, light and dark (AC-101 to AC-109, AC-118 to AC-134, AC-163 to AC-176)
# Run from the repo root as `bash acceptance/redesign-s008-check2.sh`. Sets up what it needs; exits 0 only when every case passes.
# The Chrome cases need Chrome (CVWRITE_CHROME); a missing Chrome fails the check, it is never skipped.
# senior-lead-Opus5.5-agent, 2026-11-07
set -euo pipefail
venv="${CVWRITE_TEST_VENV:-$HOME/.cvwrite3-test-venv}"
bash scripts/install.sh "$venv"
grep -v '^-r' requirements-dev.txt | "$venv/bin/pip" install --only-binary :all: -r /dev/stdin
if [ -z "${CVWRITE_CHROME:-}" ]; then
  c="$(grep -E '^CVWRITE_CHROME=' env.example | cut -d= -f2-)"
  if [ -n "$c" ] && [ -x "$c" ]; then export CVWRITE_CHROME="$c"; fi
fi
export PYTHONDONTWRITEBYTECODE=1
exec "$venv/bin/python" -m unittest discover -s acceptance -p 'redesign_s008_check2.py' -v
