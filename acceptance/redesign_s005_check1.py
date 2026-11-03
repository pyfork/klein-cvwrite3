"""CHECK 1 of redesign S-005: .webp files are served as image/webp on any machine. Covers AC-89.

The app is built while Python's type table holds only its built-in entries, with .webp taken out, as on a machine whose
own list of types does not know it (CI's runner was one: closed #124; Python 3.10's built-ins lack it, 3.11's have it).
Then the app's table must answer .webp, and Starlette's file response, which /static uses, must send image/webp.
Fails before the work: the table answers None and the file goes out as application/octet-stream.
senior-lead-Opus5.5-agent, 2026-11-03"""
import mimetypes
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for p in (ROOT, ROOT / "tests"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from support import CVCase  # noqa: E402

# The smallest WebP the check needs: RIFF header and an empty VP8L chunk. Only its name decides the type.
WEBP = b"RIFF\x0e\x00\x00\x00WEBPVP8L\x02\x00\x00\x00\x2f\x00"


def bare_table():
    """Python's built-in type entries only, without .webp: mimetypes.guess_type, which Starlette uses, reads module _db."""
    db = mimetypes.MimeTypes()
    for strict in (True, False):
        db.types_map[strict].pop(".webp", None)
    return db


class BareTypeTable:
    """Swaps in bare_table() before the app is built (CVCase.setUp builds it) and puts the old table back after."""

    def setUp(self):
        self._saved_db = mimetypes._db
        mimetypes._db = bare_table()
        super().setUp()

    def tearDown(self):
        try:
            super().tearDown()
        finally:
            mimetypes._db = self._saved_db


class TheBareTableIsBare(unittest.TestCase):
    def test_control_the_bare_table_does_not_know_webp(self):
        self.assertEqual(bare_table().guess_type("a.webp"), (None, None))
        self.assertEqual(bare_table().guess_type("a.css")[0], "text/css")


class WebpIsServedAsWebp(BareTypeTable, CVCase):
    def test_ac89_the_app_table_answers_webp(self):
        self.assertEqual(mimetypes.guess_type("art/x.webp"), ("image/webp", None))

    def test_ac89_a_webp_file_is_sent_as_image_webp(self):
        from fastapi.testclient import TestClient
        from starlette.applications import Starlette
        from starlette.staticfiles import StaticFiles
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "x.webp").write_bytes(WEBP)
            # The StaticFiles class the app mounts at /static, on a folder that holds a .webp file. The type table is
            # process-wide, so this reads what create_app (run in setUp) left in it; app/static itself holds no .webp yet.
            probe = Starlette()
            probe.mount("/static", StaticFiles(directory=tmp))
            got = TestClient(probe).get("/static/x.webp")
        self.assertEqual(got.status_code, 200)
        self.assertEqual(got.headers.get("content-type"), "image/webp")
        self.assertEqual(got.content, WEBP)


if __name__ == "__main__":
    unittest.main()
