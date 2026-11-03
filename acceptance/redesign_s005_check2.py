"""CHECK 2 of redesign S-005: the generator is in gen/, seeded, writes the home's set into app/static/art, and its
packages are pinned with hashes. Covers AC-91 and AC-92 (the pins).

Reads gen/collage.py with ast, so OpenCV, numpy and Pillow are never imported or installed (CI never installs them).
Fails before the work: gen/ does not exist.
senior-lead-Opus5.5-agent, 2026-11-03"""
import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GEN = ROOT / "gen" / "collage.py"
REQS = ROOT / "gen" / "requirements.txt"
ART = ROOT / "app" / "static" / "art"
NAMES = {"ad-lilac", "ad-marigold", "ad-teal", "arrow", "clipping", "copy", "cv-lilac", "cv-marigold", "cv-teal", "edge",
         "folder", "ground", "pages", "redacted", "scissors", "scissors-ink", "scrap-dot", "scrap-star", "scrap-tri",
         "spotlight"}
PINNED = {"opencv-python-headless", "numpy", "pillow"}


def tree():
    if not GEN.is_file():
        raise AssertionError("gen/collage.py does not exist")
    return ast.parse(GEN.read_text(encoding="utf-8"))


def assigned(module, name):
    for node in module.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return node.value
    raise AssertionError(f"gen/collage.py has no module-level {name}")


def requirements():
    """{name: (version, [hashes])} from gen/requirements.txt, continuation lines joined; comments and blanks skipped."""
    if not REQS.is_file():
        raise AssertionError("gen/requirements.txt does not exist")
    text = REQS.read_text(encoding="utf-8").replace("\\\n", " ")
    out = {}
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        m = re.fullmatch(r"([A-Za-z0-9_.-]+)==([0-9][^\s;]*)((?:\s+--hash=sha256:[0-9a-f]{64})+)", line)
        if not m:
            raise AssertionError(f"not an exact pin with hashes: {line!r}")
        out[m.group(1).lower()] = (m.group(2), re.findall(r"[0-9a-f]{64}", m.group(3)))
    return out


class TheGenerator(unittest.TestCase):
    def test_ac91_names_are_the_home_set_and_the_folder(self):
        names = ast.literal_eval(assigned(tree(), "NAMES"))
        self.assertIsInstance(names, tuple)
        self.assertEqual(len(names), len(set(names)), "NAMES repeats a name")
        self.assertEqual(set(names), NAMES)
        self.assertEqual({p.name for p in ART.iterdir()} if ART.is_dir() else set(), {n + ".webp" for n in names})

    def test_ac91_writes_into_app_static_art_by_default(self):
        out = ast.unparse(assigned(tree(), "OUT")).replace('"', "'")
        self.assertTrue(out.endswith("/ 'app' / 'static' / 'art'"), out)
        self.assertIn("__file__", out)

    def test_ac91_every_draw_is_seeded(self):
        module = tree()
        rngs = 0
        for node in ast.walk(module):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                mods = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
                for m in mods:
                    self.assertNotIn(m.split(".")[0], {"random", "time", "datetime", "secrets", "uuid"}, m)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "default_rng":
                rngs += 1
                self.assertTrue(node.args or node.keywords, f"default_rng() without a seed, line {node.lineno}")
                first = node.args[0] if node.args else node.keywords[0].value
                self.assertFalse(isinstance(first, ast.Constant) and first.value is None, f"default_rng(None), line {node.lineno}")
        self.assertGreater(rngs, 0, "no seeded generator found")

    def test_ac91_docstring_says_how_to_run(self):
        doc = ast.get_docstring(tree()) or ""
        self.assertIn("gen/collage.py", doc)
        self.assertIn("gen/requirements.txt", doc)
        self.assertIn("--require-hashes", doc)
        self.assertIn("--only-binary :all:", doc)


class ThePins(unittest.TestCase):
    def test_ac92_three_exact_pins_with_hashes(self):
        reqs = requirements()
        self.assertEqual(set(reqs), PINNED)
        for name, (version, hashes) in reqs.items():
            with self.subTest(name=name):
                self.assertTrue(hashes, f"{name} has no hash")
                self.assertEqual(len(hashes), len(set(hashes)), f"{name} repeats a hash")

    def test_the_reader_refuses_a_loose_pin(self):
        line = "numpy>=2.0 --hash=sha256:" + "0" * 64
        self.assertIsNone(re.fullmatch(r"([A-Za-z0-9_.-]+)==([0-9][^\s;]*)((?:\s+--hash=sha256:[0-9a-f]{64})+)", line))


if __name__ == "__main__":
    unittest.main()
