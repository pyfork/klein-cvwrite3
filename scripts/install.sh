#!/usr/bin/env bash
# The one install command, the same on sk24 and in CI (runtime.txt's INSTALL): hash-locked wheels only,
# then pip check. Run from the repo root; the venv defaults to .venv. kit-keeper-Opus5.5-agent, 2026-10-28
set -euo pipefail
venv="${1:-.venv}"
[ -x "$venv/bin/python" ] || python3 -m venv "$venv"
"$venv/bin/pip" install --require-hashes --only-binary :all: -r requirements.lock
"$venv/bin/pip" check
