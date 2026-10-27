"""Chunk 7a: the account page, download my data, delete my account, the 30-day purge, tombstones, the terms."""
import io
import json
import unittest
import zipfile

from app import account, notices, orders, rendering
from tests.support import AD, OWNER, CVCase
from tests.render_env import needs_render


@needs_render
class Account(CVCase):
    def setUp(self):
        super().setUp()
        self.run_id = self.start()
        self.drain()
        with self.conn() as c:
            self.acct = c.execute("select account_id from allowed_users where email = %s", (self.EMAIL,)).fetchone()["account_id"]

    def test_account_page(self):
        page = self.get("/account", self.EMAIL).text
        self.assertIn(f"You agreed to <b>Privacy notice v{notices.latest().version}</b>", page)
        self.assertIn("You didn&#39;t tick the sensitive-data line.", page)
        self.assertIn("Download my data", page)
        self.assertIn("Delete my account", page)

    def test_download_my_data(self):
        r = self.get("/account/download", self.EMAIL)
        self.assertEqual(r.headers["content-type"], "application/zip")
        z = zipfile.ZipFile(io.BytesIO(r.content))
        names = set(z.namelist())
        for f in ("profile.json", "master_cv.txt", f"runs/{self.run_id}/cv.md", f"runs/{self.run_id}/cv.pdf",
                  f"runs/{self.run_id}/ad.txt", "credit_ledger.json", "orders.json", "consents.json", "problem_reports.json"):
            self.assertIn(f, names)
        self.assertEqual(json.loads(z.read("profile.json"))["name"], "Nadia Hamzah")
        self.assertIn("# Nadia Hamzah", z.read(f"runs/{self.run_id}/cv.md").decode())
        self.assertEqual(len(json.loads(z.read("credit_ledger.json"))), 2)  # +2 free, -1 spend

    def test_delete_needs_the_word(self):
        self.assertEqual(self.post("/account/delete", self.EMAIL, {"confirm": "delete"}).status_code, 400)
        with self.conn() as c:
            self.assertIsNotNone(c.execute("select 1 from allowed_users where email = %s", (self.EMAIL,)).fetchone())

    def test_delete_my_account(self):
        pdf = rendering.pdf_path(self.data_dir, self.run_id, self.run_row(self.run_id)["pdf_rev"])
        self.assertTrue(pdf.exists())
        self.post("/report", self.EMAIL, {"category": "other", "body": "hello"})
        r = self.post("/account/delete", self.EMAIL, {"confirm": "DELETE"})
        self.assertEqual(r.headers["location"], "/deleted")
        self.assertIn("Your account is deleted", self.get("/deleted", self.EMAIL).text)
        with self.conn() as c:
            run = c.execute("select * from runs where id = %s", (self.run_id,)).fetchone()
            self.assertIsNone(run["ad_text"])
            self.assertIsNone(run["draft_md"])
            self.assertIsNotNone(run["purged_at"])
            for table in ("profiles", "problem_reports", "allowed_users"):
                self.assertIsNone(c.execute(f"select 1 from {table} where account_id = %s", (self.acct,)).fetchone(), table)
            self.assertIsNone(c.execute("select 1 from access_requests where email = %s", (self.EMAIL,)).fetchone())
            self.assertEqual(c.execute("select count(*) n from credit_ledger where account_id = %s", (self.acct,)).fetchone()["n"], 2)
            self.assertIsNotNone(c.execute("select account_deleted_at from consents where email = %s", (self.EMAIL,)).fetchone()["account_deleted_at"])
            self.assertIsNotNone(c.execute("select 1 from tombstones where hash = %s", (account.tombstone_hash(self.acct),)).fetchone())
            self.assertIsNone(c.execute("select 1 from sessions where email = %s", (self.EMAIL,)).fetchone())
        self.assertFalse(pdf.exists())
        self.assertEqual(self.get("/generate", self.EMAIL).headers["location"], "/signin")   # signed out by the delete
        self.sessions.clear()   # signing in again: the email is no longer on the list
        self.assertEqual(self.get("/generate", self.EMAIL).headers["location"], "/request")
        self.assertIn(f"deleted-", self.get("/admin", OWNER).text)

    def test_delete_with_a_refund_and_a_pending_order(self):
        with self.conn() as c:
            orders.approve(c, orders.create(c, self.acct, 5)["id"])
            pending = orders.create(c, self.acct, 20)
            orders.mark_paid(c, pending)
        page = self.get("/account", self.EMAIL).text
        self.assertIn("Refund my 5 unused paid credits (RM10.00)", page)
        r = self.post("/account/delete", self.EMAIL, {"confirm": "DELETE", "refund": "yes"})
        self.assertEqual(r.headers["location"], "/deleted?refund=10.00")
        admin = self.get("/admin", OWNER).text
        self.assertIn("Asked for a refund of RM10.00 before deleting", admin)
        self.assertIn("account deleted: refund if received", admin)

    def test_delete_stops_a_running_cv(self):
        run2 = self.start()
        self.post("/account/delete", self.EMAIL, {"confirm": "DELETE"})
        self.drain()
        self.assertEqual(self.run_row(run2)["status"], "cancelled")
        with self.conn() as c:
            self.assertIsNone(c.execute("select 1 from credit_ledger where run_id = %s", (run2,)).fetchone())

    def test_no_free_credits_on_rejoining(self):
        self.post("/account/delete", self.EMAIL, {"confirm": "DELETE"})
        self.sessions.clear()   # signs in again
        self.approve(self.EMAIL)
        with self.conn() as c:
            acct = c.execute("select account_id from allowed_users where email = %s", (self.EMAIL,)).fetchone()["account_id"]
            self.assertEqual(c.execute("select count(*) n from credit_ledger where account_id = %s", (acct,)).fetchone()["n"], 0)

    def test_tombstones_survive_a_restore(self):
        with self.conn() as c:
            row = c.execute("select * from allowed_users where email = %s", (self.EMAIL,)).fetchone()
        self.post("/account/delete", self.EMAIL, {"confirm": "DELETE"})
        with self.conn() as c:  # as if an older backup were restored: the person is back
            c.execute("insert into allowed_users (email, account_id, approved_via) values (%s, %s, %s)",
                      (row["email"], row["account_id"], row["approved_via"]))
            c.execute("update accounts set deleted_at = null where id = %s", (self.acct,))
            self.assertEqual(account.replay_tombstones(c, self.data_dir), 1)
            self.assertIsNone(c.execute("select 1 from allowed_users where email = %s", (self.EMAIL,)).fetchone())

    def test_30_day_purge(self):
        with self.conn() as c:
            c.execute("update runs set created_at = now() - interval '31 days' where id = %s", (self.run_id,))
            self.assertEqual(account.purge_old_runs(c, self.data_dir), 1)
        self.assertEqual(self.get(f"/runs/{self.run_id}", self.EMAIL).status_code, 410)
        self.assertNotIn(f"/runs/{self.run_id}", self.get("/generate", self.EMAIL).text)
        with self.conn() as c:   # nothing of the ad is kept, not even its hash
            row = c.execute("select ad_text, ad_hash from runs where id = %s", (self.run_id,)).fetchone()
        self.assertEqual((row["ad_text"], row["ad_hash"]), (None, None))

    def test_terms(self):
        page = self.get("/terms", self.EMAIL).text
        self.assertIn("Unused paid credits that haven&#x27;t expired can be refunded", page)
        self.assertIn('<p class="eyebrow">Terms</p>', page)   # no longer labelled a draft (owner, 2026-10-27)
        self.assertNotIn("draft", page.lower())


if __name__ == "__main__":
    unittest.main()
