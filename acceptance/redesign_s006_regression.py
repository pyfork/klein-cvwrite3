"""REGRESSION A of redesign S-006: the generator's packages stay dev-only. Covers AC-94 (dev-only). Passes before the work.

Guards what this slice could break: nothing the app, CI or the server installs names OpenCV, numpy, Pillow or gen/, and
no Python file the app, the render, the checks, the scripts or the suite runs imports them.
senior-lead-Opus5.5-agent, 2026-11-03"""
import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INSTALLS = [ROOT / "requirements.txt", ROOT / "requirements.lock", ROOT / "requirements-dev.txt"]
WORDS = re.compile(r"opencv|numpy|pillow|(^|[^a-z0-9_-])gen/", re.I | re.M)
BANNED = {"cv2", "numpy", "PIL", "gen"}
CODE = ["app", "render", "checks", "scripts", "tests"]


class DevOnly(unittest.TestCase):
    def test_ac94_installs_and_workflows_do_not_name_them(self):
        files = INSTALLS + sorted((ROOT / ".github").rglob("*.yml")) + sorted((ROOT / ".github").rglob("*.yaml"))
        self.assertTrue(all(f.is_file() for f in INSTALLS), "an install file is missing")
        self.assertTrue(any((ROOT / ".github").rglob("*.yml")), "no workflow found")
        for f in files:
            with self.subTest(file=str(f.relative_to(ROOT))):
                m = WORDS.search(f.read_text(encoding="utf-8"))
                self.assertIsNone(m, m and m.group(0))

    def test_ac94_no_code_imports_them(self):
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


if __name__ == "__main__":
    unittest.main()
