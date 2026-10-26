"""The render preflight and strict mode (tests/render_env.py), against fake tools, so this runs anywhere, CI included."""
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests import render_env
from tests.render_env import Result

LOADER_ERROR = "dyld[1]: Library not loaded: /usr/lib/libhvf.dylib"


def fake_tool(directory, name, script="exit 0"):
    path = Path(directory) / name
    path.write_text(f"#!/bin/sh\n{script}\n")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


class Probe(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="cvw3-tools-")
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.chrome = fake_tool(self.dir, "chrome")
        for patch in (mock.patch.dict(os.environ, {"PATH": self.dir}), mock.patch.object(render_env.build_cv, "CHROME", str(self.chrome))):
            patch.start()
            self.addCleanup(patch.stop)

    def test_all_three_work(self):
        fake_tool(self.dir, "pdfinfo")
        fake_tool(self.dir, "pdftotext")
        self.assertEqual(render_env.probe(), Result("ok", ()))

    def test_found_but_broken_names_the_tool_and_the_first_line_only(self):
        fake_tool(self.dir, "pdfinfo")
        fake_tool(self.dir, "pdftotext", f"echo '{LOADER_ERROR}' >&2\necho '  Referenced from: somewhere' >&2\nexit 134")
        res = render_env.probe()
        self.assertEqual(res.state, "broken")
        self.assertEqual(res.problems, (f"pdftotext exited 134 on -v: {LOADER_ERROR}",))

    def test_nothing_installed_is_absent(self):
        self.chrome.unlink()
        res = render_env.probe()
        self.assertEqual(res.state, "absent")
        self.assertEqual(len(res.problems), 3)
        self.assertIn(str(self.chrome), res.problems[0])

    def test_broken_wins_over_absent_and_both_are_listed(self):
        fake_tool(self.dir, "pdftotext", "exit 134")
        res = render_env.probe()
        self.assertEqual(res.state, "broken")
        self.assertEqual([p.split()[0] for p in res.problems], ["pdftotext", "pdfinfo"])

    def test_a_tool_that_hangs_is_broken_not_a_wait(self):
        fake_tool(self.dir, "pdfinfo")
        fake_tool(self.dir, "pdftotext")
        real_run = subprocess.run

        def run(argv, **kwargs):
            if argv[0].endswith("pdftotext"):
                raise subprocess.TimeoutExpired(argv, kwargs["timeout"])
            return real_run(argv, **kwargs)

        with mock.patch.object(render_env.subprocess, "run", run):
            res = render_env.probe()
        self.assertEqual(res, Result("broken", (f"pdftotext did not answer -v within {render_env.PROBE_TIMEOUT} s",)))


class Strict(unittest.TestCase):
    def strict(self, value):
        with mock.patch.dict(os.environ, {"CVWRITE_REQUIRE_RENDER": value}):
            return render_env.strict()

    def test_off_and_on(self):
        self.assertFalse(self.strict(""))
        self.assertFalse(self.strict("0"))
        self.assertTrue(self.strict("1"))

    def test_unset_is_off(self):
        with mock.patch.dict(os.environ):
            os.environ.pop("CVWRITE_REQUIRE_RENDER", None)
            self.assertFalse(render_env.strict())

    def test_a_value_that_is_neither_is_an_error_not_a_quiet_off(self):
        for value in ("true", "yes", "on", "2"):
            with self.subTest(value), self.assertRaises(ValueError):
                self.strict(value)


class NeedsRender(unittest.TestCase):
    """Decorate a throwaway test (and test class) under each state, run it, and read the outcome."""

    def outcome(self, state, strict, as_class):
        class Inner(unittest.TestCase):
            def test_it(self):
                pass

        res = Result(state, () if state == "ok" else ("pdftotext: gone",))
        env = {"CVWRITE_REQUIRE_RENDER": "1" if strict else "0"}
        with mock.patch.dict(os.environ, env), mock.patch.object(render_env, "status", return_value=res):
            if as_class:
                Inner = render_env.needs_render(Inner)
            else:
                Inner.test_it = render_env.needs_render(Inner.test_it)
        result = unittest.TestResult()
        unittest.defaultTestLoader.loadTestsFromTestCase(Inner).run(result)
        return result

    def test_ok_runs(self):
        for as_class in (False, True):
            r = self.outcome("ok", True, as_class)
            self.assertEqual((r.testsRun, r.wasSuccessful(), len(r.skipped)), (1, True, 0))

    def test_absent_skips_when_not_strict(self):
        for as_class in (False, True):
            r = self.outcome("absent", False, as_class)
            self.assertEqual(len(r.skipped), 1)
            self.assertTrue(r.wasSuccessful())
            self.assertIn("cannot render: pdftotext: gone", r.skipped[0][1])

    def test_broken_skips_with_a_pointer_to_the_one_failure(self):
        r = self.outcome("broken", False, False)
        self.assertIn("test_00_render_preflight", r.skipped[0][1])

    def test_strict_fails_instead_of_skipping(self):
        for state in ("absent", "broken"):
            for as_class in (False, True):
                with self.subTest(state=state, as_class=as_class):
                    r = self.outcome(state, True, as_class)
                    self.assertEqual(len(r.skipped), 0)
                    self.assertFalse(r.wasSuccessful())
                    failed = (r.failures + r.errors)[0][1]
                    self.assertIn("CVWRITE_REQUIRE_RENDER=1", failed)
                    self.assertIn("pdftotext: gone", failed)


if __name__ == "__main__":
    unittest.main()
