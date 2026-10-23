"""Sign-in: the Access token check, the whitelist, request access, admin approval, wave 2, the ledger."""
import unittest

import psycopg

from tests.support import OWNER, AUD, AppCase, _keys, token

ALICE = "alice@example.com"
BOB = "bob@example.com"


class Token(AppCase):
    def test_no_token_is_refused(self):
        r = self.get("/")
        self.assertEqual(r.status_code, 403)
        self.assertIn("Sign in first", r.text)

    def test_bad_tokens_are_refused(self):
        for bad in (
            token(ALICE, aud="someone-else"),
            token(ALICE, iss="https://evil.cloudflareaccess.com"),
            token(ALICE, exp_in=-120),
            token(ALICE, key=_keys()["other_key"]),
            "not.a.token",
        ):
            r = self.client.get("/", headers={"Cf-Access-Jwt-Assertion": bad})
            self.assertEqual(r.status_code, 403, bad[:20])

    def test_email_is_lowercased(self):
        self.post("/request", "Alice@Example.COM", {"note": "x"})
        with self.conn() as c:
            self.assertEqual(c.execute("select email from access_requests").fetchone()["email"], ALICE)

    def test_dev_cookie_is_ignored_in_prod(self):
        from dataclasses import replace
        from app.auth import DEV_COOKIE, Verifier, NotSignedIn

        class Req:
            headers = {}
            cookies = {DEV_COOKIE: token(ALICE)}
        prod = Verifier(replace(self.settings, env="prod"))
        with self.assertRaises(NotSignedIn):
            prod.email(Req())


class RequestAccess(AppCase):
    def test_unknown_email_goes_to_request_page(self):
        r = self.get("/", ALICE)
        self.assertEqual((r.status_code, r.headers["location"]), (303, "/request"))
        r = self.get("/request", ALICE)
        self.assertIn("Ask to join", r.text)
        self.assertIn(ALICE, r.text)

    def test_request_once_then_pending(self):
        self.post("/request", ALICE, {"note": "a friend"})
        self.post("/request", ALICE, {"note": "again"})
        with self.conn() as c:
            self.assertEqual(c.execute("select count(*) n from access_requests").fetchone()["n"], 1)
        self.assertIn("Request sent", self.get("/request", ALICE).text)

    def test_post_needs_csrf_and_our_origin(self):
        self.assertEqual(self.post("/request", ALICE, csrf=False).status_code, 403)
        self.assertEqual(self.post("/request", ALICE, origin="https://evil.test").status_code, 403)
        self.assertEqual(self.post("/request", ALICE, origin=None).status_code, 403)
        self.assertEqual(self.post("/request", ALICE, {"csrf": "x" * 40}).status_code, 403)
        with self.conn() as c:
            self.assertEqual(c.execute("select count(*) n from access_requests").fetchone()["n"], 0)


class Admin(AppCase):
    def test_owner_only(self):
        self.assertEqual(self.get("/admin", ALICE).status_code, 403)
        self.assertEqual(self.get("/admin", OWNER).status_code, 200)
        self.post("/request", ALICE)
        with self.conn() as c:
            rid = c.execute("select id from access_requests").fetchone()["id"]
        self.assertEqual(self.post(f"/admin/requests/{rid}/approve", ALICE).status_code, 403)

    def test_approve_grants_2_free_credits_for_12_months(self):
        self.approve(ALICE)
        with self.conn() as c:
            u = c.execute("select * from allowed_users where email = %s", (ALICE,)).fetchone()
            self.assertEqual(u["approved_via"], "owner")
            rows = c.execute("select delta, kind, expires_at - created_at as left from credit_ledger where account_id = %s", (u["account_id"],)).fetchall()
            self.assertEqual([(r["delta"], r["kind"]) for r in rows], [(2, "free")])
            self.assertTrue(360 <= rows[0]["left"].days <= 366)
            self.assertEqual(c.execute("select status from access_requests").fetchone()["status"], "approved")
        self.assertEqual(self.get("/", ALICE).headers["location"], "/consent")

    def test_decline(self):
        self.post("/request", ALICE)
        with self.conn() as c:
            rid = c.execute("select id from access_requests").fetchone()["id"]
        self.post(f"/admin/requests/{rid}/decline", OWNER)
        with self.conn() as c:
            self.assertEqual(c.execute("select status from access_requests").fetchone()["status"], "declined")
            self.assertIsNone(c.execute("select 1 from allowed_users").fetchone())

    def test_approve_twice_grants_once(self):
        self.approve(ALICE)
        with self.conn() as c:
            rid = c.execute("select id from access_requests").fetchone()["id"]
        self.post(f"/admin/requests/{rid}/approve", OWNER)
        with self.conn() as c:
            self.assertEqual(c.execute("select count(*) n from credit_ledger").fetchone()["n"], 1)

    def test_recent_deleter_gets_no_free_credits(self):
        with self.conn() as c:
            c.execute("insert into consents (email, notice_version, text_hash, lang, sensitive, account_deleted_at) "
                      "values (%s, '1.0', repeat('a', 64), 'en', false, now() - interval '2 months')", (BOB,))
        self.post("/request", BOB)
        self.assertIn("no free credits", self.get("/admin", OWNER).text)
        self.approve(BOB)
        with self.conn() as c:
            self.assertIsNotNone(c.execute("select 1 from allowed_users where email = %s", (BOB,)).fetchone())
            self.assertEqual(c.execute("select count(*) n from credit_ledger").fetchone()["n"], 0)

    def test_deleter_over_12_months_ago_gets_free_credits(self):
        with self.conn() as c:
            c.execute("insert into consents (email, notice_version, text_hash, lang, sensitive, account_deleted_at) "
                      "values (%s, '1.0', repeat('a', 64), 'en', false, now() - interval '13 months')", (BOB,))
        self.approve(BOB)
        with self.conn() as c:
            self.assertEqual(c.execute("select sum(delta) n from credit_ledger").fetchone()["n"], 2)


class Wave2(AppCase):
    def test_auto_approve_up_to_the_cap(self):
        self.post("/admin/wave2", OWNER, {"on": "yes"})
        self.assertIn("On: turn off", self.get("/admin", OWNER).text)
        r = self.post("/request", ALICE, {"note": ""})
        self.assertEqual(r.headers["location"], "/")
        with self.conn() as c:
            self.assertEqual(c.execute("select approved_via from allowed_users").fetchone()["approved_via"], "wave2")
            # Fill up to the cap with made-up users, then the next one waits for the owner.
            for i in range(self.settings.wave2_cap - 1):
                acct = c.execute("insert into accounts (tag) values (%s) returning id", (f"T{i:05d}",)).fetchone()["id"]
                c.execute("insert into allowed_users (email, account_id, approved_via) values (%s, %s, 'owner')", (f"u{i}@example.com", acct))
        r = self.post("/request", BOB, {"note": ""})
        self.assertEqual(r.headers["location"], "/request")
        with self.conn() as c:
            self.assertIsNone(c.execute("select 1 from allowed_users where email = %s", (BOB,)).fetchone())
            self.assertEqual(c.execute("select status from access_requests where email = %s", (BOB,)).fetchone()["status"], "pending")

    def test_off_by_default(self):
        r = self.post("/request", ALICE)
        self.assertEqual(r.headers["location"], "/request")


class Ledger(AppCase):
    def test_insert_only(self):
        self.approve(ALICE)
        with self.conn() as c:
            for sql in ("update credit_ledger set delta = 50", "delete from credit_ledger", "truncate credit_ledger"):
                with self.assertRaises(psycopg.Error, msg=sql):
                    c.execute(sql)

    def test_grants_need_an_expiry(self):
        self.approve(ALICE)
        with self.conn() as c:
            acct = c.execute("select account_id from allowed_users").fetchone()["account_id"]
            with self.assertRaises(psycopg.errors.CheckViolation):
                c.execute("insert into credit_ledger (account_id, delta, kind) values (%s, 5, 'pack')", (acct,))


class Migrations(AppCase):
    def test_rerun_is_a_no_op(self):
        from app import db
        with self.conn() as c:
            self.assertEqual(db.migrate(c), [])


if __name__ == "__main__":
    unittest.main()
