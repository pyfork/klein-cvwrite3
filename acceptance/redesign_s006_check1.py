"""CHECK 1 of redesign S-006: the home's art is in app/static/art and the app serves it. Covers AC-91 and AC-92.

The folder holds exactly the 20 WebP files the home uses, each with alpha and no wider than 2,400 px, within the
weight budget; each is served by the app's own /static mount as image/webp, cached like the other /static/ files,
with no sign-in, on a machine whose type table does not know .webp (slice 5's bare table).
The limits are proven at their edges on made-up files: one at each limit passes, one past it fails.
WebP headers are read with the standard library, so no image package is needed.
Fails before the work: app/static/art does not exist.
senior-lead-Opus5.5-agent, 2026-11-03"""
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for p in (ROOT, ROOT / "tests", ROOT / "acceptance"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from support import CVCase  # noqa: E402
from redesign_s005_check1 import BareTypeTable  # noqa: E402  (slice 5's locked check: a table without .webp)

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


def problems(folder):
    """Every way the files in folder break AC-91's format rules or AC-92's weight budget; empty when none."""
    out, total = [], 0
    for f in sorted(folder.iterdir()):
        data = f.read_bytes()
        total += len(data)
        try:
            w, h, alpha = webp_info(data)
        except ValueError as e:
            out.append(f"{f.name}: {e}")
            continue
        if not alpha:
            out.append(f"{f.name}: no alpha channel")
        if w > WIDTH_MAX:
            out.append(f"{f.name}: {w} px wide")
        if h < 1:
            out.append(f"{f.name}: no height")
        if len(data) > EACH_MAX:
            out.append(f"{f.name}: {len(data)} bytes")
    if total > TOTAL_MAX:
        out.append(f"the folder is {total} bytes")
    return out


def fake_webp(width, size, alpha=True):
    """A VP8X header with the given width (height 10) and alpha flag, padded to exactly size bytes."""
    head = (b"RIFF" + struct.pack("<I", size - 8) + b"WEBP" + b"VP8X" + struct.pack("<I", 10)
            + bytes([0x10 if alpha else 0, 0, 0, 0]) + (width - 1).to_bytes(3, "little") + (9).to_bytes(3, "little"))
    return head + b"\0" * (size - len(head))


class TheArtFolder(unittest.TestCase):
    def test_ac91_exactly_the_home_set(self):
        self.assertTrue(ART.is_dir(), "app/static/art does not exist")
        self.assertEqual({p.name for p in ART.iterdir()}, {n + ".webp" for n in NAMES})

    def test_ac91_ac92_each_file_and_the_folder_within_the_rules(self):
        self.assertTrue(ART.is_dir(), "app/static/art does not exist")
        self.assertEqual(problems(ART), [])


class TheLimitsAtTheirEdges(unittest.TestCase):
    """The same problems() the real folder is judged by, on made-up files at and just past each limit."""

    def run_on(self, files):
        with tempfile.TemporaryDirectory() as d:
            for name, data in files.items():
                (Path(d) / name).write_bytes(data)
            return problems(Path(d))

    def test_ac91_width_2400_passes_2401_fails(self):
        self.assertEqual(self.run_on({"a.webp": fake_webp(2400, 1000)}), [])
        self.assertEqual(self.run_on({"a.webp": fake_webp(2401, 1000)}), ["a.webp: 2401 px wide"])

    def test_ac92_file_100000_bytes_passes_100001_fails(self):
        self.assertEqual(self.run_on({"a.webp": fake_webp(100, 100_000)}), [])
        self.assertEqual(self.run_on({"a.webp": fake_webp(100, 100_001)}), ["a.webp: 100001 bytes"])

    def test_ac92_folder_600000_bytes_passes_600001_fails(self):
        five = {f"f{i}.webp": fake_webp(100, 100_000) for i in range(5)}
        self.assertEqual(self.run_on({**five, "g.webp": fake_webp(100, 50_000), "h.webp": fake_webp(100, 50_000)}), [])
        self.assertEqual(self.run_on({**five, "g.webp": fake_webp(100, 50_000), "h.webp": fake_webp(100, 50_001)}),
                         ["the folder is 600001 bytes"])

    def test_ac91_no_alpha_and_a_png_fail(self):
        self.assertEqual(self.run_on({"a.webp": fake_webp(100, 1000, alpha=False)}), ["a.webp: no alpha channel"])
        self.assertEqual(self.run_on({"a.webp": b"\x89PNG\r\n\x1a\n" + b"\0" * 40}), ["a.webp: not a WebP file"])


class ServedByTheAppOnABareTable(BareTypeTable, CVCase):
    def test_ac92_each_served_as_webp_cached_without_sign_in(self):
        self.assertTrue(ART.is_dir(), "app/static/art does not exist")
        for name in sorted(NAMES):
            with self.subTest(name=name):
                r = self.client.get(f"/static/art/{name}.webp")
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.headers.get("content-type"), "image/webp")
                self.assertNotIn("no-store", r.headers.get("cache-control", ""))
                self.assertEqual(r.content, (ART / f"{name}.webp").read_bytes())


if __name__ == "__main__":
    unittest.main()
