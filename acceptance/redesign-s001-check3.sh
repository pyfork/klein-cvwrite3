#!/usr/bin/env bash
# Locked check, redesign S-001. CHECK 3: the shell and the old pages at every width (AC-14, AC-19, AC-22 to AC-45, AC-64, AC-68 to AC-71)
# Run from the repo root as `bash acceptance/redesign-s001-check3.sh`. Sets up what it needs; exits 0 only when every case passes.
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
exec .venv/bin/python -m unittest discover -s acceptance -p 'redesign_s001_check3.py' -v
