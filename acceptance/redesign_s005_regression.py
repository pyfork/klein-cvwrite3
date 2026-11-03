"""REGRESSION A and B of redesign S-005. Both pass before the work.

A (AC-92, dev-only): nothing the app, CI or the server installs names OpenCV, numpy, Pillow or gen/, and no Python file
the app, the render, the checks, the scripts or the suite runs imports them.
B (AC-90, the types every page relies on): registering .webp changes no other type: with Python's built-in type table
only, the stylesheet is text/css, the script a JavaScript type, and .css, .js, .html and .ttf answer as the built-ins do.
senior-lead-Opus5.5-agent, 2026-11-03"""
import ast
import mimetypes
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for p in (ROOT, ROOT / "tests"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from support import CVCase  # noqa: E402
from redesign_s005_check1 import BareTypeTable  # noqa: E402
INSTALLS = [ROOT / "requirements.txt", ROOT / "requirements.lock", ROOT / "requirements-dev.txt"]
WORDS = re.compile(r"opencv|numpy|pillow|(^|[^a-z0-9_-])gen/", re.I | re.M)
BANNED = {"cv2", "numpy", "PIL", "gen"}
CODE = ["app", "render", "checks", "scripts", "tests"]


class DevOnly(unittest.TestCase):
    def test_ac92_installs_and_workflows_do_not_name_them(self):
        files = INSTALLS + sorted((ROOT / ".github").rglob("*.yml")) + sorted((ROOT / ".github").rglob("*.yaml"))
        self.assertTrue(all(f.is_file() for f in INSTALLS), "an install file is missing")
        self.assertTrue(any((ROOT / ".github").rglob("*.yml")), "no workflow found")
        for f in files:
            with self.subTest(file=str(f.relative_to(ROOT))):
                m = WORDS.search(f.read_text(encoding="utf-8"))
                self.assertIsNone(m, m and m.group(0))

    def test_ac92_no_code_imports_them(self):
        seen = 0
        for folder in CODE:
            for f in sorted((ROOT / folder).rglob("*.py")):
                seen += 1
                for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
                    names = []
                    if isinstance(node, ast.Import):
                        names = [a.name for a in node.names]
                    elif isinstance(node, ast.ImportFrom) and node.level == 0:
                        names = [node.module or ""]
                    for n in names:
                        self.assertNotIn(n.split(".")[0], BANNED, f"{f.relative_to(ROOT)} imports {n}")
        self.assertGreater(seen, 20, "too few Python files read")

    def test_the_pattern_catches_a_named_package(self):
        self.assertIsNotNone(WORDS.search("Pillow==13.0.0"))
        self.assertIsNotNone(WORDS.search("python gen/collage.py"))
        self.assertIsNone(WORDS.search("regen/x"))


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
        builtin = mimetypes.MimeTypes()
        for name in ("a.css", "a.js", "a.html", "a.ttf"):
            with self.subTest(name=name):
                self.assertEqual(mimetypes.guess_type(name), builtin.guess_type(name))


if __name__ == "__main__":
    unittest.main()
