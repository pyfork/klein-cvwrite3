"""CHECK 2 of redesign S-004: the list is exact and the real tree passes. Covers AC-86, AC-87 and AC-88.

The test exposes a module-level dict `ALLOWED`: script path under app/static -> {"pages": set of template file names,
"without": text}. Cases: the real tree passes and the suite finds the test; an allowed script on a page it is not listed
for fails; a stale entry (the file is gone, or the listed page does not load it) fails; an entry with no `without` text fails.
Fails before the work: the test does not exist.
senior-lead-Sonnet5.5-agent, 2026-11-03"""
import copy
import importlib.util
import io
import subprocess
import sys
import unittest
from unittest import mock

import redesign_s004_common as S


def load_module():
    if not S.TEST.is_file():
        raise AssertionError("tests/test_scripts_allowlist.py does not exist yet")
    spec = importlib.util.spec_from_file_location("allowlist_under_check", S.TEST)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def remove_the_tag(root):
    path = root / "app" / "templates" / "profile.html"
    text = path.read_text(encoding="utf-8")
    assert "upload.js" in text, "profile.html no longer loads upload.js"
    path.write_text("\n".join(l for l in text.splitlines() if "upload.js" not in l), encoding="utf-8")


class ListIsExact(unittest.TestCase):
    def fails(self, mutate, *names):
        code, out = S.run_in_copy(mutate)
        self.assertNotEqual(code, 0, "the suite passed with this change:\n" + out)
        for n in names:
            self.assertIn(n, out, f"the failure does not name {n}:\n{out}")

    def test_ac88_the_real_tree_passes(self):
        done = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", S.TEST.name],
                              cwd=S.ROOT, capture_output=True, text=True, timeout=120)
        out = done.stdout + done.stderr
        self.assertEqual(done.returncode, 0, out)
        self.assertGreaterEqual(S.tests_run(out), 1, "the run found no test:\n" + out)

    def test_ac88_the_suite_runner_finds_the_test(self):
        suite = unittest.TestLoader().discover(str(S.ROOT / "tests"), pattern=S.TEST.name)
        self.assertGreaterEqual(suite.countTestCases(), 1)

    def test_ac88_upload_js_is_listed_for_the_profile_page(self):
        allowed = load_module().ALLOWED
        self.assertIn("upload.js", allowed)
        self.assertIn("profile.html", allowed["upload.js"]["pages"])

    def test_ac86_a_listed_script_on_a_page_it_is_not_listed_for(self):
        self.fails(S.add_to_template("account.html", '<script src="/static/upload.js" defer></script>'), "account.html", "upload.js")

    def test_ac86_a_listed_script_whose_file_is_gone(self):
        self.fails(lambda root: (root / "app" / "static" / "upload.js").unlink(), "upload.js")

    def test_ac86_a_listed_page_that_does_not_load_the_script(self):
        self.fails(remove_the_tag, "profile.html", "upload.js")

    def test_ac87_every_entry_has_pages_and_a_without_text(self):
        allowed = load_module().ALLOWED
        self.assertTrue(allowed)
        for js, entry in allowed.items():
            self.assertTrue(entry["pages"], f"{js} lists no page")
            self.assertTrue(entry["without"].strip(), f"{js} has no 'without' text")

    def test_ac87_an_empty_without_text_fails_the_test(self):
        mod = load_module()
        for js in mod.ALLOWED:
            altered = copy.deepcopy(mod.ALLOWED)
            altered[js]["without"] = "  "
            with mock.patch.object(mod, "ALLOWED", altered):
                result = unittest.TextTestRunner(stream=io.StringIO()).run(unittest.defaultTestLoader.loadTestsFromModule(mod))
            self.assertFalse(result.wasSuccessful(), f"an empty 'without' text for {js} passed")


if __name__ == "__main__":
    unittest.main()
