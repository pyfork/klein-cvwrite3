"""The web fonts stay whole: every character the app's own text uses that a web font's source has is kept in its woff2
cut, and the cuts stay within the phone budget (redesign S-007, AC-180 and AC-181). Standard library only.
Run: python3 -m unittest discover tests. senior-lead-Opus5.5-agent, 2026-11-04"""
import hashlib
import struct
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "fonts"
SOURCES = {"SchibstedGrotesk-Variable.woff2": "SchibstedGrotesk-Variable.ttf",
           "LibreCaslonText-Italic-Variable.woff2": "LibreCaslonText-Italic-Variable.ttf",
           "GeistMono-Variable.woff2": "GeistMono-Variable.ttf"}
STAMP = FONTS / "web-subset.sha256"  # written by fonts/build_web.py with each cut
STAMPED = ("web-subset.txt", *SOURCES)
FILE_LIMIT, TOTAL_LIMIT = 60_000, 160_000
TEXT = ("app/templates/**/*.html", "app/content/**/*", "app/i18n.py", "app/static/*.css", "app/static/*.js")


def kept():
    points = set()
    for line in (FONTS / "web-subset.txt").read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            lo, _, hi = line[2:].partition("-")
            points |= set(range(int(lo, 16), int(hi or lo, 16) + 1))
    return points


def cmap(path):
    """Code points in a TrueType file's format 4 cmap subtable."""
    data = path.read_bytes()
    tables = {data[12 + 16 * i:16 + 16 * i]: struct.unpack(">I", data[20 + 16 * i:24 + 16 * i])[0]
              for i in range(struct.unpack(">H", data[4:6])[0])}
    base = tables[b"cmap"]
    for i in range(struct.unpack(">H", data[base + 2:base + 4])[0]):
        sub = base + struct.unpack(">I", data[base + 8 + 8 * i:base + 12 + 8 * i])[0]
        if struct.unpack(">H", data[sub:sub + 2])[0] == 4:
            n = struct.unpack(">H", data[sub + 6:sub + 8])[0] // 2
            ends = struct.unpack(f">{n}H", data[sub + 14:sub + 14 + 2 * n])
            starts = struct.unpack(f">{n}H", data[sub + 16 + 2 * n:sub + 16 + 4 * n])
            return {cp for s, e in zip(starts, ends) for cp in range(s, e + 1) if cp != 0xFFFF}
    raise AssertionError(f"{path.name} has no format 4 cmap")


class WebFonts(unittest.TestCase):
    def test_every_character_the_app_uses_is_kept(self):
        used = {}
        for g in TEXT:
            for f in sorted(ROOT.glob(g)):
                if f.is_file():
                    for ch in f.read_text(encoding="utf-8"):
                        used.setdefault(ord(ch), f.relative_to(ROOT))
        keep = kept()
        for woff2, ttf in SOURCES.items():
            src = cmap(FONTS / ttf)
            dropped = [f"U+{cp:04X} in {used[cp]}" for cp in sorted(used) if cp in src and cp not in keep]
            self.assertEqual(dropped, [], f"{ttf} has these and fonts/web-subset.txt drops them: add them there, then rerun fonts/build_web.py")

    def test_the_cuts_are_made_from_this_kept_set(self):
        rerun = "rerun fonts/build_web.py and commit what it writes"
        self.assertTrue(STAMP.is_file(), f"fonts/web-subset.sha256 is missing: {rerun}")
        stamped = {}
        for line in STAMP.read_text(encoding="utf-8").splitlines():
            digest, _, name = line.partition("  ")
            stamped[name] = digest
        for name in STAMPED:
            now = hashlib.sha256((FONTS / name).read_bytes()).hexdigest()
            self.assertEqual(stamped.get(name), now, f"fonts/{name} does not match fonts/web-subset.sha256: {rerun}")
        self.assertEqual(sorted(stamped), sorted(STAMPED), f"fonts/web-subset.sha256 names other files: {rerun}")

    def test_the_cuts_are_within_the_budget(self):
        sizes = {w: (FONTS / w).stat().st_size for w in SOURCES}
        for w, n in sizes.items():
            self.assertLessEqual(n, FILE_LIMIT, f"{w} is {n} bytes")
        self.assertLessEqual(sum(sizes.values()), TOTAL_LIMIT, f"the cuts total {sum(sizes.values())} bytes")


if __name__ == "__main__":
    unittest.main()
