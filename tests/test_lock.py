"""requirements.lock must match requirements.txt (senior S7): every pin, same version, with hashes.
If this fails, run python3 scripts/lock.py and commit both files. Run: python3 -m unittest discover tests"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PIN = re.compile(r"^([A-Za-z0-9_.\-]+)(?:\[[^\]]*\])?==(\S+)")


def normalise(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def pins(text):
    return {normalise(m[1]): m[2] for m in (PIN.match(l.strip()) for l in text.splitlines()) if m}


class Lock(unittest.TestCase):
    def test_lock_covers_every_pin(self):
        wanted = pins((ROOT / "requirements.txt").read_text())
        locked = pins((ROOT / "requirements.lock").read_text())
        stale = sorted(n for n, v in wanted.items() if locked.get(n) != v)
        self.assertEqual(stale, [], "requirements.lock is stale: run python3 scripts/lock.py")

    def test_every_locked_package_has_a_hash(self):
        body = (ROOT / "requirements.lock").read_text().split("\n\n", 1)[1].strip()
        blocks = re.split(r"\n(?=[a-z0-9])", body)
        self.assertGreater(len(blocks), 0)
        for b in blocks:
            self.assertRegex(b, r"--hash=sha256:[0-9a-f]{64}")


if __name__ == "__main__":
    unittest.main()
