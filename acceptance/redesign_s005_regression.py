"""REGRESSION A of redesign S-005: registering .webp changes no other type. Covers AC-90. Passes before the work.

Guards what every page relies on: with Python's built-in type table only (and no .webp), the stylesheet is text/css,
the script a JavaScript type, and .css, .js, .html and .ttf answer as the built-in entries do.
senior-lead-Opus5.5-agent, 2026-11-03"""
import mimetypes
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for p in (ROOT, ROOT / "tests"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from support import CVCase  # noqa: E402
from redesign_s005_check1 import BareTypeTable, bare_table  # noqa: E402


class OtherTypesUnchanged(BareTypeTable, CVCase):
    def test_ac90_stylesheet_and_script_keep_their_types(self):
        css = self.client.get("/static/betterjobs.css")
        js = self.client.get("/static/upload.js")
        self.assertEqual(css.status_code, 200)
        self.assertEqual(js.status_code, 200)
        self.assertTrue(css.headers["content-type"].startswith("text/css"), css.headers["content-type"])
        self.assertTrue(js.headers["content-type"].startswith(("application/javascript", "text/javascript")),
                        js.headers["content-type"])

    def test_ac90_the_table_answers_other_types_as_the_built_ins_do(self):
        builtin = bare_table()
        for name in ("a.css", "a.js", "a.html", "a.ttf"):
            with self.subTest(name=name):
                self.assertEqual(mimetypes.guess_type(name), builtin.guess_type(name))


if __name__ == "__main__":
    unittest.main()
