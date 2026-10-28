#!/usr/bin/env bash
# The full suite from a fresh checkout: the guards' GUARD_TEST_COMMAND. The reviewer's checker runs it as
# its own user on a read-only copy of the PR, so the venv goes in $HOME, never in the tree. Render tests
# skip here without poppler (the `test` job in ci.yml is the render gate). senior-lead-Opus5.5-agent, 2026-10-28
set -euo pipefail
venv="${CVWRITE_TEST_VENV:-$HOME/.cvwrite3-test-venv}"
bash scripts/install.sh "$venv"
grep -v '^-r' requirements-dev.txt | "$venv/bin/pip" install --only-binary :all: -r /dev/stdin
# CI=1: a checker's copy has no local push guard to check (tests/test_prepush.py ThisClone).
CI="${CI:-1}" PYTHONDONTWRITEBYTECODE=1 "$venv/bin/python" -m unittest discover tests
