"""Can this machine render a CV? Chrome and poppler, found AND working, checked once up front.

Three outcomes: "ok"; "absent" (a tool is not installed); "broken" (installed, but it will not start, e.g. a
Homebrew library the OS lacks). Either way the render tests skip. A broken tool also fails
tests/test_00_render_preflight.py once, naming the cause, instead of dozens of failures that read like product bugs.

CVWRITE_REQUIRE_RENDER=1 (set in CI) is strict mode: absent counts as broken, and a render test that cannot run
fails instead of skipping, so a green run always means the PDF rendered. Leave it unset or 0 to skip as before.
build-engineer-Sonnet5.5-agent, 2026-10-26
"""
import functools
import os
import shutil
import subprocess
import unittest
from pathlib import Path
from typing import NamedTuple

from render import build_cv

PROBE_TIMEOUT = 4  # seconds per tool; a working one answers in well under 1


class Result(NamedTuple):
    state: str  # "ok", "absent" or "broken"
    problems: tuple  # one line per tool that is not usable; empty when ok


def strict():
    raw = os.environ.get("CVWRITE_REQUIRE_RENDER", "")
    if raw not in ("", "0", "1"):  # "true" read as off would be the silent skip this switch exists to stop
        raise ValueError(f"CVWRITE_REQUIRE_RENDER must be 1 or 0, not {raw!r}")
    return raw == "1"


def _first_line(text):
    return next((line.strip() for line in text.splitlines() if line.strip()), "")


def _broken(name, argv):
    """None when the tool starts and exits 0, else why not (the first line of what it printed)."""
    try:
        done = subprocess.run(argv, capture_output=True, text=True, timeout=PROBE_TIMEOUT)
    except subprocess.TimeoutExpired:
        return f"{name} did not answer {argv[-1]} within {PROBE_TIMEOUT} s"
    except OSError as e:
        return f"{name} will not start: {e}"
    if done.returncode == 0:
        return None
    return f"{name} exited {done.returncode} on {argv[-1]}: {_first_line(done.stderr or done.stdout) or 'no output'}"


def probe():
    absent, broken = [], []
    tools = [("Chrome", build_cv.CHROME, "--version"), ("pdfinfo", shutil.which("pdfinfo"), "-v"),
             ("pdftotext", shutil.which("pdftotext"), "-v")]
    for name, path, flag in tools:
        if not path or not Path(path).exists():
            absent.append(f"{name} is not installed" + (f" (looked at {path})" if name == "Chrome" else ""))
        elif why := _broken(name, [path, flag]):
            broken.append(why)
    if broken:
        return Result("broken", tuple(broken + absent))
    return Result("absent", tuple(absent)) if absent else Result("ok", ())


@functools.cache
def status():
    return probe()


def needs_render(obj):
    """Decorator for a test or a test class that renders a PDF."""
    res = status()
    if res.state == "ok":
        return obj
    reason = "; ".join(res.problems)
    if strict():
        return _fail(obj, f"CVWRITE_REQUIRE_RENDER=1 and the render tools are not usable: {reason}")
    if res.state == "broken":
        return unittest.skip("the render tools are installed but broken: see test_00_render_preflight")(obj)
    return unittest.skip(f"cannot render: {reason}")(obj)


def _fail(obj, message):
    if isinstance(obj, type):
        def setUpClass(cls):
            raise AssertionError(message)
        obj.setUpClass = classmethod(setUpClass)
        return obj

    @functools.wraps(obj)
    def fail(*args, **kwargs):
        raise AssertionError(message)
    return fail
