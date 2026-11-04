"""Shared by the checks of redesign S-007 (the web fonts as woff2 cut to the Latin letters). Standard library only.
senior-lead-Opus5.5-agent, 2026-11-04"""
import mimetypes
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for p in (ROOT, ROOT / "tests", ROOT / "acceptance"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

FONTS = ROOT / "fonts"
KEPT = FONTS / "web-subset.txt"
TEST = ROOT / "tests" / "test_web_fonts.py"
# family -> (woff2 file, source TrueType file, font-style, font-weight today)
FACES = {
    "Schibsted Grotesk": ("SchibstedGrotesk-Variable.woff2", "SchibstedGrotesk-Variable.ttf", "normal", "400 900"),
    "Libre Caslon Text": ("LibreCaslonText-Italic-Variable.woff2", "LibreCaslonText-Italic-Variable.ttf", "italic", "400 700"),
    "Geist Mono": ("GeistMono-Variable.woff2", "GeistMono-Variable.ttf", "normal", "100 900"),
}
FILE_LIMIT = 60_000
TOTAL_LIMIT = 160_000
# The least the kept set holds (AC-179): Basic Latin, Latin-1, Latin Extended-A
REQUIRED = set(range(0x20, 0x7F)) | set(range(0xA0, 0x180))
# The app's own text (AC-181)
TEXT_GLOBS = ("app/templates/**/*.html", "app/content/**/*", "app/i18n.py", "app/static/*.css", "app/static/*.js")


def kept_set(path=KEPT):
    """Code points in fonts/web-subset.txt: one `U+XXXX` or `U+XXXX-YYYY` per line, `#` starts a comment."""
    if not path.is_file():
        raise AssertionError(f"{path.relative_to(ROOT)} does not exist yet")
    points = set()
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        m = re.fullmatch(r"U\+([0-9A-Fa-f]{4,6})(?:-([0-9A-Fa-f]{4,6}))?", line)
        if not m:
            raise AssertionError(f"web-subset.txt line {n} is not U+XXXX or U+XXXX-YYYY: {line!r}")
        lo = int(m.group(1), 16)
        hi = int(m.group(2), 16) if m.group(2) else lo
        points |= set(range(lo, hi + 1))
    return points


def app_text_chars(root=ROOT):
    """{code point: first file (repo-relative) that uses it} over the app's own text."""
    found = {}
    for g in TEXT_GLOBS:
        for f in sorted(root.glob(g)):
            if f.is_file():
                for ch in f.read_text(encoding="utf-8"):
                    found.setdefault(ord(ch), str(f.relative_to(root)))
    return found


def bare_table():
    """Python's built-in type entries only, without .woff2 (Python 3.10's built-ins have none; later ones may)."""
    db = mimetypes.MimeTypes()
    for strict in (True, False):
        db.types_map[strict].pop(".woff2", None)
    return db


class BareTypeTable:
    """Swaps in bare_table() before the app is built (CVCase.setUp builds it) and puts the old table back after."""

    def setUp(self):
        self._saved_db = mimetypes._db
        mimetypes._db = bare_table()
        super().setUp()

    def tearDown(self):
        try:
            super().tearDown()
        finally:
            mimetypes._db = self._saved_db


def run_in_copy(mutate=lambda root: None):
    """Copy what tests/test_web_fonts.py reads (the app's text, fonts/, the test) into a temp folder, apply
    mutate(root), and run the test there as the suite runs it. Returns (exit code, output)."""
    if not TEST.is_file():
        raise AssertionError("tests/test_web_fonts.py does not exist yet")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for sub in ("app/templates", "app/content", "app/static", "fonts"):
            shutil.copytree(ROOT / sub, root / sub)
        shutil.copy(ROOT / "app" / "i18n.py", root / "app" / "i18n.py")
        (root / "tests").mkdir()
        shutil.copy(TEST, root / "tests" / TEST.name)
        mutate(root)
        done = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", TEST.name],
                              cwd=root, capture_output=True, text=True, timeout=120)
        return done.returncode, done.stdout + done.stderr
