"""Shared helpers for the redesign S-004 acceptance checks (plans/redesign-plan.md, Slice 4: the scripts allow-list).

Locked with the checks. The slice's deliverable is one standard-library test, tests/test_scripts_allowlist.py, that reads
app/templates and app/static from the folder above tests/. These helpers run that test, as the suite runs it, against a
throwaway copy of those two folders that a case has changed, so each case sees the real test fail or pass.
senior-lead-Sonnet5.5-agent, 2026-11-03
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEST = ROOT / "tests" / "test_scripts_allowlist.py"


def run_in_copy(mutate=lambda root: None):
    """Copy app/templates, app/static and the test into a temp folder, apply mutate(root), run the test there.
    Returns (exit code, output)."""
    if not TEST.is_file():
        raise AssertionError("tests/test_scripts_allowlist.py does not exist yet")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for sub in ("templates", "static"):
            shutil.copytree(ROOT / "app" / sub, root / "app" / sub)
        (root / "tests").mkdir()
        shutil.copy(TEST, root / "tests" / TEST.name)
        mutate(root)
        done = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", TEST.name],
            cwd=root, capture_output=True, text=True, timeout=120,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        return done.returncode, done.stdout + done.stderr


def tests_run(output):
    """How many tests the unittest output says ran (0 when it says none), so a run that found nothing never counts as a pass."""
    m = re.search(r"^Ran (\d+) tests?", output, re.M)
    return int(m.group(1)) if m else 0


def add_file(rel, text):
    """A mutate function: write text to root/rel."""
    def mutate(root):
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return mutate


def add_to_template(name, text):
    """A mutate function: append text to the template root/app/templates/<name>."""
    def mutate(root):
        with open(root / "app" / "templates" / name, "a", encoding="utf-8") as f:
            f.write("\n" + text + "\n")
    return mutate
