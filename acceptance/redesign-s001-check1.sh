#!/usr/bin/env bash
# Locked check, redesign S-001. CHECK 1: every page is wired to the new stylesheet and fonts (AC-1 to AC-5, AC-13, AC-14)
# Run from the repo root as `bash acceptance/redesign-s001-check1.sh`. Sets up what it needs; exits 0 only when every case passes.
# senior-lead-Sonnet5.5-agent, 2026-10-28
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
  .venv/bin/pip install --require-hashes --only-binary :all: -r requirements.lock
  grep -v '^-r' requirements-dev.txt | .venv/bin/pip install --only-binary :all: -r /dev/stdin
fi
if [ -z "${CVWRITE_CHROME:-}" ]; then
  c="$(grep -E '^CVWRITE_CHROME=' env.example | cut -d= -f2-)"
  if [ -n "$c" ] && [ -x "$c" ]; then export CVWRITE_CHROME="$c"; fi
fi
export CVWRITE_REQUIRE_RENDER=1
exec .venv/bin/python -m unittest discover -s acceptance -p 'redesign_s001_check1.py' -v
