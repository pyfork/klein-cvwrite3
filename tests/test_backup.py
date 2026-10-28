"""Chunk 7b: the backup job, against a fake bucket. The real dump, encryption and checks run for real."""
import os
import unittest
from pathlib import Path

import pyrage

from app import backup
from tests.support import AppCase

PG_BIN = Path(backup.__file__).resolve().parent.parent / ".venv/lib/python3.10/site-packages/pgserver/pginstall/bin"


class FakeStore:
    def __init__(self, fail_puts=0, corrupt=False):
        self.objects, self.fail_puts, self.corrupt, self.puts = {}, fail_puts, corrupt, 0

    def put(self, key, data):
        self.puts += 1
        if self.fail_puts:
            self.fail_puts -= 1
            raise ConnectionError("network down")
        self.objects[key] = data[:-1] if self.corrupt else data

    def head(self, key):
        import hashlib
        d = self.objects[key]
        return len(d), hashlib.sha256(d).hexdigest()

    def list(self):
        return list(self.objects)

    def delete(self, key):
        self.objects.pop(key, None)


@unittest.skipUnless((PG_BIN / "pg_dump").exists(), "needs pgserver's pg_dump")
class Backup(AppCase):
    def setUp(self):
        super().setUp()
        os.environ["PATH"] = f"{PG_BIN}:{os.environ['PATH']}"
        self.identity = pyrage.x25519.Identity.generate()
        self.recipient = str(self.identity.to_public())
        self.spool = Path(self.data_dir) / "spool"

    def run_backup(self, store, force=False):
        with self.conn() as c:
            return backup.run(c, self.settings, store, self.recipient, self.spool, sleep=lambda s: None, force=force)

    def test_encrypted_dump_and_tombstones_uploaded(self):
        with self.conn() as c:
            c.execute("insert into tombstones (hash) values (%s)", ("a" * 64,))
        store = FakeStore()
        self.assertEqual(self.run_backup(store), "ok")
        dumps = [k for k in store.objects if k.endswith(".dump.age")]
        self.assertEqual(len(dumps), 1)
        plain = pyrage.decrypt(store.objects[dumps[0]], [self.identity])
        self.assertTrue(plain.startswith(b"PGDMP"))          # a pg_dump custom-format archive
        self.assertNotIn(b"PGDMP", store.objects[dumps[0]])   # and it's encrypted at rest
        self.assertIn(b"a" * 64, store.objects[dumps[0].replace(".dump.age", ".tombstones.txt")])
        self.assertEqual(list(self.spool.glob("*")), [])

    def test_only_when_due(self):
        store = FakeStore()
        self.run_backup(store)
        self.assertEqual(self.run_backup(store), "skipped")      # the last good copy is minutes old
        with self.conn() as c:
            c.execute("update backup_runs set finished_at = now() - interval '19 hours' where outcome = 'ok'")
        self.assertEqual(self.run_backup(store), "skipped")      # a timer that fires a little early skips
        with self.conn() as c:
            c.execute("update backup_runs set finished_at = now() - interval '23 hours' where outcome = 'ok'")
        self.assertEqual(self.run_backup(store), "ok")           # every night

    def test_upload_retries_then_succeeds(self):
        store = FakeStore(fail_puts=2)
        self.assertEqual(self.run_backup(store), "ok")

    def test_failed_upload_keeps_the_dump_for_next_time(self):
        store = FakeStore(fail_puts=99)
        self.assertEqual(self.run_backup(store), "failed")
        self.assertEqual(len(list(self.spool.glob("*.dump.age"))), 1)
        with self.conn() as c:
            row = c.execute("select outcome, error_class from backup_runs order by id desc").fetchone()
            self.assertEqual((row["outcome"], row["error_class"]), ("failed", "upload_failed"))
            self.assertTrue(backup.due(c))                          # tries again the very next night
        good = FakeStore()
        self.assertEqual(self.run_backup(good), "ok")
        self.assertEqual(len([k for k in good.objects if k.endswith(".dump.age")]), 2)  # yesterday's too
        self.assertEqual(list(self.spool.glob("*")), [])

    def test_a_copy_that_doesnt_verify_is_a_failure(self):
        self.assertEqual(self.run_backup(FakeStore(corrupt=True)), "failed")

    def test_keeps_the_four_newest(self):
        store = FakeStore()
        for i in range(6):
            store.objects[f"cvwrite3/2026010{i}T0230Z.dump.age"] = b"x"
            store.objects[f"cvwrite3/2026010{i}T0230Z.tombstones.txt"] = b""
        self.run_backup(store, force=True)
        dumps = sorted(k for k in store.objects if k.endswith(".dump.age"))
        self.assertEqual(len(dumps), 4)
        self.assertNotIn("cvwrite3/20260100T0230Z.dump.age", dumps)
        self.assertNotIn("cvwrite3/20260100T0230Z.tombstones.txt", store.objects)

    def test_health_panel_shows_the_last_good_backup(self):
        from tests.support import OWNER
        self.assertIn("none yet", self.get("/admin", OWNER).text)
        self.run_backup(FakeStore())
        self.assertIn("0.0 days ago", self.get("/admin", OWNER).text)


if __name__ == "__main__":
    unittest.main()
