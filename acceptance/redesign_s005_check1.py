"""CHECK 1 of redesign S-005: the home's art is in app/static/art and the app serves it. Covers AC-89 and AC-90.

The folder holds exactly the 20 WebP files the home uses, each with alpha and no wider than 2,400 px, within the
weight budget; each is served as image/webp, cached like the other /static/ files, with no sign-in.
WebP headers are read with the standard library, so no image package is needed.
Fails before the work: app/static/art does not exist.
senior-lead-Opus5.5-agent, 2026-11-03"""
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for p in (ROOT, ROOT / "tests"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from support import CVCase  # noqa: E402

ART = ROOT / "app" / "static" / "art"
NAMES = {"ad-lilac", "ad-marigold", "ad-teal", "arrow", "clipping", "copy", "cv-lilac", "cv-marigold", "cv-teal", "edge",
         "folder", "ground", "pages", "redacted", "scissors", "scissors-ink", "scrap-dot", "scrap-star", "scrap-tri",
         "spotlight"}
TOTAL_MAX = 600_000
EACH_MAX = 100_000
WIDTH_MAX = 2400


def webp_info(data):
    """(width, height, has_alpha) from a WebP file's first chunk; raises ValueError if it is not a WebP."""
    if len(data) < 30 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise ValueError("not a WebP file")
    chunk = data[12:16]
    if chunk == b"VP8X":
        flags = data[20]
        w = 1 + int.from_bytes(data[24:27], "little")
        h = 1 + int.from_bytes(data[27:30], "little")
        return w, h, bool(flags & 0x10)
    if chunk == b"VP8L":
        if data[20] != 0x2F:
            raise ValueError("bad VP8L signature")
        bits = struct.unpack("<I", data[21:25])[0]
        return 1 + (bits & 0x3FFF), 1 + ((bits >> 14) & 0x3FFF), bool((bits >> 28) & 1)
    if chunk == b"VP8 ":
        w, h = struct.unpack("<HH", data[26:30])
        return w & 0x3FFF, h & 0x3FFF, False
    raise ValueError(f"unknown WebP chunk {chunk!r}")


class TheArtFolder(unittest.TestCase):
    def test_ac89_exactly_the_home_set(self):
        self.assertTrue(ART.is_dir(), "app/static/art does not exist")
        found = {p.name for p in ART.iterdir()}
        self.assertEqual(found, {n + ".webp" for n in NAMES})

    def test_ac89_each_is_a_webp_with_alpha(self):
        self.assertTrue(ART.is_dir(), "app/static/art does not exist")
        for name in sorted(NAMES):
            with self.subTest(name=name):
                w, h, alpha = webp_info((ART / f"{name}.webp").read_bytes())
                self.assertTrue(alpha, f"{name}.webp has no alpha channel")
                self.assertLessEqual(w, WIDTH_MAX)
                self.assertGreater(h, 0)

    def test_ac90_weight_budget(self):
        self.assertTrue(ART.is_dir(), "app/static/art does not exist")
        sizes = {p.name: p.stat().st_size for p in ART.iterdir()}
        for name, size in sizes.items():
            self.assertLessEqual(size, EACH_MAX, f"{name} is {size} bytes")
        self.assertLessEqual(sum(sizes.values()), TOTAL_MAX, f"the folder is {sum(sizes.values())} bytes")

    def test_the_reader_refuses_what_is_not_webp(self):
        with self.assertRaises(ValueError):
            webp_info(b"\x89PNG\r\n\x1a\n" + b"\0" * 40)


class ServedPublicly(CVCase):
    def test_ac90_served_as_webp_cached_without_sign_in(self):
        for name in sorted(NAMES):
            with self.subTest(name=name):
                r = self.client.get(f"/static/art/{name}.webp")
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.headers.get("content-type"), "image/webp")
                self.assertNotIn("no-store", r.headers.get("cache-control", ""))
                self.assertEqual(r.content, (ART / f"{name}.webp").read_bytes())


if __name__ == "__main__":
    unittest.main()
