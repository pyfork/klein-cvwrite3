"""CHECK 2 of redesign S-007: the fonts' phone budget, and the suite test that keeps the cut whole on every later PR.
Covers AC-180, AC-181 and AC-183. Fails before the work: there are no woff2 files and no tests/test_web_fonts.py.
Standard library only. senior-lead-Opus5.5-agent, 2026-11-04 (AC-183 stamp cases: re-plan, the same day)"""
import ast
import hashlib
import subprocess
import sys
import unittest

import redesign_s007_common as S

WOFF2 = [w for w, *_rest in S.FACES.values()]
PLANTED = "Ș"  # Ș: in all three sources, outside U+00A0-017F; a kept set of the required ranges drops it
ABSENT = "☃"  # ☃: in none of the three sources, so the page falls back for it whatever is kept
STAMP = "web-subset.sha256"
STAMPED = ["web-subset.txt", *WOFF2]  # what fonts/build_web.py stamps, in this order


def restamp(root):
    """Write the stamp as fonts/build_web.py does after a cut: one `<sha256>  <name>` line per stamped file."""
    fonts = root / "fonts"
    (fonts / STAMP).write_text("".join(f"{hashlib.sha256((fonts / n).read_bytes()).hexdigest()}  {n}\n"
                                       for n in STAMPED), encoding="utf-8")


def add_text(rel, text):
    def mutate(root):
        path = root / rel
        path.write_text(path.read_text(encoding="utf-8") + text, encoding="utf-8")
    return mutate


def sized(sizes):
    """Set each woff2 in the copy to exactly the size given (the suite test reads only their sizes)."""
    def mutate(root):
        for name, size in sizes.items():
            path = root / "fonts" / name
            data = path.read_bytes()[:size]
            path.write_bytes(data + b"\0" * (size - len(data)))
        restamp(root)  # a cut of that size, as a rerun would stamp it, so only the budget is under test
    return mutate


class TheBudget(unittest.TestCase):
    def test_ac180_the_real_files_are_within_the_budget(self):
        sizes = {}
        for w in WOFF2:
            self.assertTrue((S.FONTS / w).is_file(), f"fonts/{w} does not exist")
            sizes[w] = (S.FONTS / w).stat().st_size
        print(f"\nwoff2 sizes: {sizes}, total {sum(sizes.values())}")
        for w, n in sizes.items():
            self.assertLessEqual(n, S.FILE_LIMIT, w)
        self.assertLessEqual(sum(sizes.values()), S.TOTAL_LIMIT)


class TheSuiteTest(unittest.TestCase):
    def assertPasses(self, mutate=lambda root: None):
        code, out = S.run_in_copy(mutate)
        self.assertEqual(code, 0, out[-2000:])
        self.assertRegex(out, r"Ran [1-9]\d* test")

    def assertFailsNaming(self, mutate, *names):
        code, out = S.run_in_copy(mutate)
        self.assertNotEqual(code, 0, "the suite test passed:\n" + out[-2000:])
        for n in names:
            self.assertIn(n, out)

    def test_ac181_the_real_tree_passes_and_the_suite_finds_the_test(self):
        self.assertPasses()
        done = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_web_fonts.py", "-v"],
                              cwd=S.ROOT, capture_output=True, text=True, timeout=120)
        self.assertEqual(done.returncode, 0, done.stderr[-2000:])
        self.assertRegex(done.stderr, r"Ran [1-9]\d* test")

    def test_ac181_the_test_imports_only_the_standard_library(self):
        tree = ast.parse(S.TEST.read_text(encoding="utf-8"))
        names = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        names |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.level == 0 and n.module}
        self.assertEqual(sorted(names - set(sys.stdlib_module_names)), [])

    def test_ac181_a_dropped_character_fails_and_is_named(self):
        for rel in ("app/templates/base.html", "app/content/terms.md", "app/i18n.py", "app/static/betterjobs.css",
                    "app/static/upload.js"):
            text = (f"\n# {PLANTED}\n" if rel.endswith(".py") else f"\n/* {PLANTED} */\n" if rel.endswith(".css")
                    else f"\n// {PLANTED}\n" if rel.endswith(".js") else f"\n{PLANTED}\n")
            with self.subTest(file=rel):
                self.assertFailsNaming(add_text(rel, text), "U+0218", rel)

    def test_ac181_a_character_no_source_has_passes(self):
        self.assertPasses(add_text("app/templates/base.html", f"\n{ABSENT}\n"))

    def test_ac181_a_kept_set_that_keeps_the_character_passes(self):
        both = lambda root: (add_text("app/templates/base.html", f"\n{PLANTED}\n")(root),  # noqa: E731
                             add_text("fonts/web-subset.txt", "\nU+0218\n")(root), restamp(root))
        self.assertPasses(both)

    def test_ac180_a_file_at_the_limit_passes_and_one_byte_over_fails(self):
        small = {WOFF2[0]: 1_000, WOFF2[1]: 1_000}
        self.assertPasses(sized({**small, WOFF2[2]: S.FILE_LIMIT}))
        self.assertFailsNaming(sized({**small, WOFF2[2]: S.FILE_LIMIT + 1}), WOFF2[2], str(S.FILE_LIMIT + 1))

    def test_ac180_a_total_at_the_limit_passes_and_one_byte_over_fails(self):
        rest = S.TOTAL_LIMIT - 2 * S.FILE_LIMIT
        self.assertPasses(sized({WOFF2[0]: S.FILE_LIMIT, WOFF2[1]: S.FILE_LIMIT, WOFF2[2]: rest}))
        self.assertFailsNaming(sized({WOFF2[0]: S.FILE_LIMIT, WOFF2[1]: S.FILE_LIMIT, WOFF2[2]: rest + 1}),
                               str(S.TOTAL_LIMIT + 1))



class TheStamp(unittest.TestCase):
    """AC-183: the kept set and the three cuts match fonts/web-subset.sha256, or the suite fails and says to rerun."""
    assertFailsNaming = TheSuiteTest.assertFailsNaming

    def test_ac183_the_stamp_names_the_kept_set_and_the_three_cuts(self):
        lines = (S.FONTS / STAMP).read_text(encoding="utf-8").splitlines()
        stamped = dict(reversed(line.split("  ", 1)) for line in lines)
        self.assertEqual(sorted(stamped), sorted(STAMPED))
        for name, digest in stamped.items():
            self.assertEqual(digest, hashlib.sha256((S.FONTS / name).read_bytes()).hexdigest(), name)

    def test_ac183_a_kept_set_edited_without_a_new_cut_fails(self):
        self.assertFailsNaming(add_text("fonts/web-subset.txt", "\nU+0218\n"), "fonts/web-subset.txt", "fonts/build_web.py")

    def test_ac183_a_cut_changed_without_a_new_stamp_fails(self):
        for name in WOFF2:
            def flip(root, name=name):
                path = root / "fonts" / name
                data = bytearray(path.read_bytes())
                data[-1] ^= 0xFF
                path.write_bytes(bytes(data))
            with self.subTest(file=name):
                self.assertFailsNaming(flip, f"fonts/{name}", "fonts/build_web.py")

    def test_ac183_a_missing_stamp_fails(self):
        self.assertFailsNaming(lambda root: (root / "fonts" / STAMP).unlink(), f"fonts/{STAMP}", "fonts/build_web.py")

    def test_ac183_a_stamp_without_a_cut_fails(self):
        def drop(root):
            path = root / "fonts" / STAMP
            path.write_text("".join(path.read_text(encoding="utf-8").splitlines(keepends=True)[:-1]), encoding="utf-8")
        self.assertFailsNaming(drop, f"fonts/{STAMP}", "fonts/build_web.py")


if __name__ == "__main__":
    unittest.main()
