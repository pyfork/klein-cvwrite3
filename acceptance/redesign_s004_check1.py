"""CHECK 1 of redesign S-004: a script the allow-list does not allow fails the suite and is named. Covers AC-84 and AC-85.

Each case changes a throwaway copy of app/templates and app/static, runs tests/test_scripts_allowlist.py there, and
expects it to fail and to name the file. The first case is the control: the unchanged copy passes, so a test that
fails on everything cannot pass this check. Fails before the work: the test does not exist.
senior-lead-Sonnet5.5-agent, 2026-11-03"""
import unittest

import redesign_s004_common as S

SRC = '<script src="/static/%s" defer></script>'


class UnlistedScripts(unittest.TestCase):
    # The tag-shape cases use profile.html, the page upload.js is listed for, so only the shape rule can fail them.
    def fails(self, mutate, *names):
        code, out = S.run_in_copy(mutate)
        self.assertNotEqual(code, 0, "the suite passed with this change:\n" + out)
        for n in names:
            self.assertIn(n, out, f"the failure does not name {n}:\n{out}")

    def test_control_the_real_files_pass(self):
        code, out = S.run_in_copy()
        self.assertEqual(code, 0, out)
        self.assertGreaterEqual(S.tests_run(out), 1, "the run found no test:\n" + out)

    def test_ac84_an_unlisted_js_file(self):
        self.fails(S.add_file("app/static/evil.js", "alert(1)"), "evil.js")

    def test_ac84_an_unlisted_js_file_in_a_subfolder(self):
        self.fails(S.add_file("app/static/lib/evil.js", "alert(1)"), "lib/evil.js")

    def test_ac84_an_unlisted_mjs_file(self):
        self.fails(S.add_file("app/static/evil.mjs", "export {}"), "evil.mjs")

    def test_ac84_an_svg_that_holds_a_script(self):
        self.fails(S.add_file("app/static/pic.svg", '<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'), "pic.svg")

    def test_ac84_an_svg_with_an_inline_handler(self):
        self.fails(S.add_file("app/static/pic.svg", '<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"></svg>'), "pic.svg")

    def test_ac85_an_inline_script_in_a_template(self):
        self.fails(S.add_to_template("account.html", "<script>alert(1)</script>"), "account.html")

    def test_ac85_an_inline_script_in_capitals(self):
        self.fails(S.add_to_template("account.html", "<SCRIPT>alert(1)</SCRIPT>"), "account.html")

    def test_ac85_a_script_from_another_address(self):
        self.fails(S.add_to_template("account.html", '<script src="https://cdn.example.com/x.js" defer></script>'), "account.html")

    def test_ac85_a_script_without_defer(self):
        self.fails(S.add_to_template("profile.html", '<script src="/static/upload.js"></script>'), "profile.html")

    def test_ac85_a_script_with_another_attribute(self):
        self.fails(S.add_to_template("profile.html", '<script src="/static/upload.js" defer type="module"></script>'), "profile.html")

    def test_ac85_a_script_with_single_quotes(self):
        self.fails(S.add_to_template("profile.html", "<script src='/static/upload.js' defer></script>"), "profile.html")

    def test_ac85_a_script_with_a_body_and_a_src(self):
        self.fails(S.add_to_template("profile.html", '<script src="/static/upload.js" defer>alert(1)</script>'), "profile.html")

    def test_ac85_a_script_that_is_not_on_the_list(self):
        self.fails(S.add_to_template("account.html", SRC % "other.js"), "account.html", "other.js")

    def test_ac85_an_inline_handler(self):
        self.fails(S.add_to_template("account.html", '<button onclick="alert(1)">x</button>'), "account.html")

    def test_ac85_an_inline_handler_in_capitals(self):
        self.fails(S.add_to_template("account.html", '<button ONCLICK="alert(1)">x</button>'), "account.html")

    def test_ac85_a_javascript_address(self):
        self.fails(S.add_to_template("account.html", '<a href="javascript:alert(1)">x</a>'), "account.html")


if __name__ == "__main__":
    unittest.main()
