"""The render tools, checked first (the 00 puts this file first in the run).

The real machine, not a stub. Installed but unusable is always one failure here; the render tests then skip
instead of failing one by one. Not installed skips here too, unless CVWRITE_REQUIRE_RENDER=1 (see render_env).
"""
import unittest

from tests import render_env


class RenderPreflight(unittest.TestCase):
    def test_chrome_and_poppler_work(self):
        res = render_env.status()
        if res.state == "ok":
            return
        message = "the PDF render cannot run on this machine:\n  " + "\n  ".join(res.problems)
        if res.state == "broken" or render_env.strict():
            self.fail(message)
        self.skipTest(message)


if __name__ == "__main__":
    unittest.main()
