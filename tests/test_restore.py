"""Senior S5 and C7: a real restore. Back up, delete an account, back up again, then restore the OLDER
copy into a scratch database and replay the newest tombstones: the deleted person stays deleted, everyone
else comes back. Uses the real dump, age encryption, pg_restore and replay code; only the bucket is fake."""
import os
import subprocess
import unittest
import uuid

import psycopg
import pyrage

from app import account, db
from tests.support import AppCase, _server_uri, _with_db
from tests.test_backup import PG_BIN, FakeStore

GONE, KEPT = "gone@example.com", "kept@example.com"


@unittest.skipUnless((PG_BIN / "pg_restore").exists(), "needs pgserver's pg_restore")
class Restore(AppCase):
    def setUp(self):
        super().setUp()
        os.environ["PATH"] = f"{PG_BIN}:{os.environ['PATH']}"
        self.identity = pyrage.x25519.Identity.generate()
        self.store = FakeStore()
        self.scratch = "r_" + uuid.uuid4().hex[:10]
        for email in (GONE, KEPT):
            self.approve(email)
            self.agree(email)

    def tearDown(self):
        with psycopg.connect(_server_uri(), autocommit=True) as c:
            c.execute(f"drop database if exists {self.scratch} with (force)")
        super().tearDown()

    def backup(self):
        from app import backup
        with self.conn() as c:
            self.assertEqual(backup.run(c, self.settings, self.store, str(self.identity.to_public()),
                                        f"{self.data_dir}/spool", sleep=lambda s: None, force=True), "ok")
        return sorted(k for k in self.store.objects if k.endswith(".dump.age"))[-1]

    def restore(self, key):
        """Runbook step 10, with the fake bucket: decrypt, pg_restore into a scratch database."""
        plain = pyrage.decrypt(self.store.objects[key], [self.identity])
        with psycopg.connect(_server_uri(), autocommit=True) as c:
            c.execute(f"create database {self.scratch}")
        subprocess.run([str(PG_BIN / "pg_restore"), "--no-owner", "--dbname", _with_db(self.scratch)],
                       input=plain, check=True, capture_output=True)
        return db.connect(_with_db(self.scratch))

    def ids(self, c):
        return {r["email"]: r["account_id"] for r in c.execute("select email, account_id from allowed_users")}

    def test_older_copy_plus_newest_tombstones(self):
        with self.conn() as c:
            gone_id = self.ids(c)[GONE]
        older = self.backup()
        with self.conn() as c:
            account.delete_account(c, self.data_dir, gone_id, GONE)
        newest = self.backup()
        self.assertNotEqual(older, newest)
        tombstones = self.store.objects[newest.replace(".dump.age", ".tombstones.txt")].decode()

        with self.restore(older) as c:
            self.assertIn(GONE, self.ids(c))                           # the older copy still holds them
            self.assertEqual(db.migrate(c), [])                        # the schema came back whole
            self.assertEqual(account.replay_file(c, self.data_dir, tombstones.splitlines()), 1)
            self.assertIn(KEPT, self.ids(c))
            self.assertNotIn(GONE, self.ids(c))
            self.assertIsNotNone(c.execute("select deleted_at from accounts where id = %s", (gone_id,)).fetchone()["deleted_at"])
            self.assertEqual(account.replay_file(c, self.data_dir, tombstones.splitlines()), 0)  # safe to run twice

    def test_the_tombstones_next_to_an_older_dump_are_not_enough(self):
        """Why the runbook says to replay the NEWEST tombstones file."""
        with self.conn() as c:
            gone_id = self.ids(c)[GONE]
        older = self.backup()
        with self.conn() as c:
            account.delete_account(c, self.data_dir, gone_id, GONE)
        self.backup()
        stale = self.store.objects[older.replace(".dump.age", ".tombstones.txt")].decode()
        with self.restore(older) as c:
            self.assertEqual(account.replay_file(c, self.data_dir, stale.splitlines()), 0)
            self.assertIn(GONE, self.ids(c))


if __name__ == "__main__":
    unittest.main()
