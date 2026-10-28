#!/usr/bin/env bash
# Locked check, redesign S-001. REGRESSION A, B, C: the shell keeps its parts, the PDF render is untouched, nothing asks another host (AC-6, AC-7, AC-8)
# Run from the repo root as `bash acceptance/redesign-s001-regression.sh`. Sets up what it needs; exits 0 only when every case passes.
# senior-lead-Sonnet5.5-agent, 2026-10-28
set -euo pipefail
# Re-plan 2026-10-28: the venv goes in $HOME, never in the tree (the checker runs on a read-only copy).
# Re-plan 2026-10-28 (2): no cd to the script's folder; the checker runs main's copy from the PR's root.
venv="${CVWRITE_TEST_VENV:-$HOME/.cvwrite3-test-venv}"
bash scripts/install.sh "$venv"
grep -v '^-r' requirements-dev.txt | "$venv/bin/pip" install --only-binary :all: -r /dev/stdin
if [ -z "${CVWRITE_CHROME:-}" ]; then
  c="$(grep -E '^CVWRITE_CHROME=' env.example | cut -d= -f2-)"
  if [ -n "$c" ] && [ -x "$c" ]; then export CVWRITE_CHROME="$c"; fi
fi
export CVWRITE_REQUIRE_RENDER=1
export PYTHONDONTWRITEBYTECODE=1
exec "$venv/bin/python" -m unittest discover -s acceptance -p 'redesign_s001_regression.py' -v
