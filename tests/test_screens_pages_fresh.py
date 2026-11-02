"""KIT-020: the stand-in pages in acceptance/screens/ are copies of what the app renders; they must be current.
A template or stylesheet change without `python acceptance/screens/make_pages.py` leaves the `screens` job
comparing the old copy and passing. Run: python3 -m unittest discover tests
senior-lead-Sonnet5.5-agent, 2026-11-02
"""
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class ScreensPagesFresh(unittest.TestCase):
    def test_copies_are_current(self):
        done = subprocess.run([sys.executable, str(ROOT / "acceptance" / "screens" / "make_pages.py")], cwd=ROOT,
                              env={**os.environ, "SCREENS_CHECK": "1"}, capture_output=True, text=True, timeout=300)
        self.assertEqual(done.returncode, 0, "run acceptance/screens/make_pages.py and commit the result:\n" + done.stderr[-1500:])


if __name__ == "__main__":
    unittest.main()
