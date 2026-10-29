#!/usr/bin/env bash
# Locked check, redesign S-002. REGRESSION A: a light device, or none, sees slice 1's look (AC-73)
# Run from the repo root as `bash acceptance/redesign-s002-regression.sh`. Sets up what it needs; exits 0 only when every case passes.
# senior-lead-Opus5.5-agent, 2026-10-29
set -euo pipefail
venv="${CVWRITE_TEST_VENV:-$HOME/.cvwrite3-test-venv}"
bash scripts/install.sh "$venv"
grep -v '^-r' requirements-dev.txt | "$venv/bin/pip" install --only-binary :all: -r /dev/stdin
if [ -z "${CVWRITE_CHROME:-}" ]; then
  c="$(grep -E '^CVWRITE_CHROME=' env.example | cut -d= -f2-)"
  if [ -n "$c" ] && [ -x "$c" ]; then export CVWRITE_CHROME="$c"; fi
fi
export CVWRITE_REQUIRE_RENDER=1
export PYTHONDONTWRITEBYTECODE=1
exec "$venv/bin/python" -m unittest discover -s acceptance -p 'redesign_s002_regression.py' -v
