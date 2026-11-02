"""KIT-020 stand-in pages: write the 23 pages CHECK 3 loads to static HTML, for the `screens` job.

The job opens them as files (no server, no database): acceptance/screens/pages.txt lists each name and its file.
The pages and betterjobs.css are copies of what the app serves, so run this again after any template or
stylesheet change and commit the result; SCREENS_CHECK=1 fails instead of writing when a copy is stale.
Run from the repo root (fake stand-in data only):
  ~/.cvwrite3-test-venv/bin/python acceptance/screens/make_pages.py
senior-lead-Sonnet5.5-agent, 2026-11-02
"""
import base64
import os
import re
import sys
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "acceptance"), str(ROOT), str(ROOT / "tests")]
import redesign_s001_common as C  # noqa: E402
from support import CVCase  # noqa: E402
from app.routes_pay import placeholder_qr  # noqa: E402

OUT = ROOT / "acceptance" / "screens"
PAGES = OUT / "pages"
QR = "data:image/svg+xml;base64," + base64.b64encode(placeholder_qr().encode()).decode()
# What differs between two runs, fixed so a second run writes the same bytes.
FIXED = [(r"\d\d [A-Z][a-z]{2}, \d\d:\d\d", "01 Jan, 09:00"), (r"Paused since \d\d:\d\d", "Paused since 09:00"),
         (r"CV3-[A-Z0-9]{4}", "CV3-AAAA")]
# Today and a year on ("2 Nov 2026", "2 Nov 2027") move daily; the one fixed date app_pages sets stays.
DAY = re.compile(r"\b(?!28 Sep 2027\b)\d{1,2} [A-Z][a-z]{2} (20\d\d)\b")
LIST_HEAD = ("# KIT-020: one stand-in page per line: <name> <file>. Written by make_pages.py; a name is a page template's\n"
             "# name or <template>_<state>.\n")


def localise(html):
    """Point the page at files next to it (a file:// page cannot ask a server for /static) and fix what moves."""
    html = re.sub(r'(href|src)="/static/(betterjobs\.css)(\?[^"]*)?"', r'\1="\2"', html)
    html = html.replace('src="/static/upload.js"', 'src="../../../app/static/upload.js"')
    html = html.replace('src="/orders/qr"', f'src="{QR}"')
    for pattern, fixed in FIXED:
        html = re.sub(pattern, fixed, html)
    return DAY.sub(lambda m: "1 Jan 2026" if int(m.group(1)) == datetime.now().year else "1 Jan 2027", html)


class MakePages(CVCase):
    def test_pages(self):
        pages = C.app_pages(self)
        css = C.SHEET.read_text(encoding="utf-8").replace("url(/fonts/", "url(../../../fonts/")
        self.assertNotIn("url(/", css, "the stylesheet asks for a file this script does not point at")
        want = {PAGES / f"{name}.html": localise(html) for name, (html, _) in pages.items()}
        want[PAGES / "betterjobs.css"] = css
        want[OUT / "pages.txt"] = LIST_HEAD + "".join(
            f"{name} acceptance/screens/pages/{name}.html\n" for name in sorted(pages))
        if os.environ.get("SCREENS_CHECK"):
            stale = [str(p.relative_to(ROOT)) for p, text in want.items()
                     if not p.is_file() or p.read_text(encoding="utf-8") != text]
            stale += [str(p.relative_to(ROOT)) for p in PAGES.glob("*.html") if p not in want]
            self.assertEqual(stale, [], "stale: run acceptance/screens/make_pages.py and commit")
            return
        PAGES.mkdir(parents=True, exist_ok=True)
        for p in PAGES.glob("*.html"):
            if p not in want:
                p.unlink()
        for p, text in want.items():
            p.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    unittest.main(verbosity=0)
