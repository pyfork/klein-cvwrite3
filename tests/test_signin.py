"""Sign-in: the emailed code, sessions, the whitelist, request access, admin approval, wave 2, the ledger."""
import json
import unittest
from unittest import mock

import psycopg

from app import signin
from tests.support import ORIGIN, OWNER, AppCase

ALICE = "alice@example.com"
BOB = "bob@example.com"


class Code(AppCase):
    """The real flow, with no session made for us."""

    def ask(self, email=ALICE, ip=None, origin=ORIGIN):
        headers = {"Origin": origin} if origin else {}
        if ip:
            headers["CF-Connecting-IP"] = ip
        return self.client.post("/signin", data={"email": email}, headers=headers)

    def enter(self, code, origin=ORIGIN):
        return self.client.post("/signin/code", data={"code": code}, headers={"Origin": origin} if origin else {})

    def last_code(self):
        return self.outbox.sent[-1][1]

    def test_signed_out_goes_to_signin(self):
        for path in ("/", "/profile", "/account", "/admin", "/request"):
            r = self.client.get(path)
            self.assertEqual((r.status_code, r.headers["location"]), (303, "/signin"), path)
        self.assertIn("Email me a code", self.client.get("/signin").text)

    def test_code_signs_in_and_email_is_lowercased(self):
        r = self.ask("Alice@Example.COM")
        self.assertEqual((r.status_code, r.headers["location"]), (303, "/signin/code"))
        self.assertEqual(self.outbox.sent[0][0], ALICE)
        self.assertIn(ALICE, self.client.get("/signin/code").text)
        r = self.enter(self.last_code()[:3] + " " + self.last_code()[3:])   # a space, as people copy it
        self.assertEqual((r.status_code, r.headers["location"]), (303, "/"))
        self.assertEqual(self.client.get("/").headers["location"], "/request")   # signed in, not on the list yet
        self.client.post("/request", data={"note": "x"}, headers={"Origin": ORIGIN})   # no csrf: refused
        with self.conn() as c:
            self.assertIsNone(c.execute("select 1 from access_requests").fetchone())
            row = c.execute("select * from sessions").fetchone()
            self.assertEqual(row["email"], ALICE)
            codes = c.execute("select * from login_codes").fetchall()
        # Only HMACs are stored: neither the code nor the token nor the email.
        dump = json.dumps([dict(r) for r in codes], default=str) + row["token_hash"]
        self.assertNotIn(self.last_code(), dump)
        self.assertNotIn("alice", dump)
        self.assertIsNotNone(codes[0]["used_at"])

    def test_code_works_once(self):
        self.ask()
        code = self.last_code()
        self.enter(code)
        self.client.cookies.clear()
        self.ask()   # sets the pending cookie again
        self.assertEqual(self.enter(code).status_code, 400)

    def test_wrong_code_then_lockout_after_5_tries(self):
        self.ask()
        right = self.last_code()
        wrong = f"{(int(right) + 1) % 10 ** 6:06d}"
        for _ in range(signin.MAX_TRIES):
            r = self.enter(wrong)
            self.assertEqual(r.status_code, 400)
            self.assertIn("didn't work", r.text)
        self.assertEqual(self.enter(right).status_code, 400)   # the 6th try fails even when right

    def test_new_code_retires_the_old(self):
        self.ask()
        old = self.last_code()
        self.ask()
        if old != self.last_code():
            self.assertEqual(self.enter(old).status_code, 400)
        self.assertEqual(self.enter(self.last_code()).status_code, 303)

    def test_expired_code(self):
        self.ask()
        with self.conn() as c:
            c.execute("update login_codes set expires_at = now() - interval '1 second'")
        self.assertEqual(self.enter(self.last_code()).status_code, 400)

    def test_code_is_for_its_email_only(self):
        self.ask(ALICE)
        a = self.last_code()
        self.ask(BOB)   # the pending cookie now says Bob
        if a != self.last_code():
            self.assertEqual(self.enter(a).status_code, 400)

    def test_pending_cookie_is_signed(self):
        self.client.cookies.set("cvwrite3_pending", "9999999999.Ym9iQGV4YW1wbGUuY29t.0000")
        self.assertEqual(self.client.get("/signin/code").headers["location"], "/signin")

    def test_limits_per_email_and_per_ip(self):
        for _ in range(signin.PER_EMAIL):
            self.assertEqual(self.ask(ip="203.0.113.9").status_code, 303)
        r = self.ask(ip="203.0.113.9")
        self.assertEqual(r.status_code, 429)
        self.assertIn("Wait 15 minutes", r.text)
        for i in range(signin.PER_IP - signin.PER_EMAIL):
            self.assertEqual(self.ask(f"u{i}@example.com", ip="203.0.113.9").status_code, 303)
        self.assertEqual(self.ask("new@example.com", ip="203.0.113.9").status_code, 429)
        self.assertEqual(self.ask("new@example.com", ip="198.51.100.7").status_code, 303)
        self.assertEqual(len(self.outbox.sent), signin.PER_IP + 1)

    def test_bad_email_and_foreign_origin(self):
        self.assertEqual(self.ask("not-an-email").status_code, 400)
        self.assertEqual(self.ask(origin="https://evil.test").status_code, 403)
        self.assertEqual(self.ask(origin=None).status_code, 403)
        self.assertEqual(self.outbox.sent, [])

    def test_mail_failure_is_shown_and_recorded(self):
        from app import mailer

        class Broken:
            def send_code(self, to, code):
                raise mailer.MailError("SMTPAuthenticationError")
        from app.main import create_app
        from fastapi.testclient import TestClient
        client = TestClient(create_app(self.settings, mail=Broken()), base_url=ORIGIN, follow_redirects=False)
        r = client.post("/signin", data={"email": ALICE}, headers={"Origin": ORIGIN})
        self.assertEqual(r.status_code, 502)
        self.assertIn("couldn't send", r.text)
        with self.conn() as c:
            self.assertEqual(c.execute("select error_class from errors").fetchone()["error_class"], "MailError")

    def test_signout_ends_the_session(self):
        cookie = self.as_user(ALICE)
        from app import auth
        r = self.client.post("/signout", data={"csrf": auth.csrf_token(self.settings, ALICE)},
                             headers={**cookie, "Origin": ORIGIN})
        self.assertEqual((r.status_code, r.headers["location"]), (303, "/signin"))
        self.assertEqual(self.client.get("/", headers=cookie).headers["location"], "/signin")

    def test_expired_session_and_sliding_expiry(self):
        cookie = self.as_user(ALICE)
        with self.conn() as c:
            c.execute("update sessions set last_seen_at = now() - interval '2 hours', expires_at = now() + interval '1 day'")
        self.client.get("/", headers=cookie)
        with self.conn() as c:
            left = c.execute("select expires_at - now() d from sessions").fetchone()["d"]
            self.assertGreater(left.days, 28)
            c.execute("update sessions set expires_at = now() - interval '1 second'")
        self.assertEqual(self.client.get("/", headers=cookie).headers["location"], "/signin")

    def test_prod_cookie_is_host_only_and_secure(self):
        from dataclasses import replace
        from fastapi.responses import Response
        from app import auth
        r = Response()
        auth.set_cookie(replace(self.settings, env="prod"), r, "t")
        c = r.headers["set-cookie"]
        for part in ("__Host-cvwrite3=t", "Secure", "HttpOnly", "SameSite=lax", "Path=/"):
            self.assertIn(part.lower(), c.lower())
        self.assertNotIn("domain", c.lower())

    def test_dev_cookie_name_is_ignored_in_prod(self):
        from dataclasses import replace
        from app import auth

        class Req:
            cookies = {"cvwrite3": self.as_user(ALICE)["Cookie"].split("=", 1)[1]}
        with self.conn() as c, self.assertRaises(auth.NotSignedIn):
            auth.email(c, replace(self.settings, env="prod"), Req())

    def test_delete_and_purge_clear_sessions_and_codes(self):
        self.as_user(BOB)
        self.ask()
        with self.conn() as c:
            c.execute("update login_codes set created_at = now() - interval '2 days'")
            c.execute("update sessions set expires_at = now() - interval '1 second'")
            signin.purge(c)
            self.assertIsNone(c.execute("select 1 from login_codes").fetchone())
            self.assertIsNone(c.execute("select 1 from sessions").fetchone())


class Mail(unittest.TestCase):
    def test_message_has_the_code_and_nothing_else_of_ours(self):
        from app import mailer
        m = mailer.message("cvwrite3 <signin@cvwrite3.test>", ALICE, "123456")
        self.assertEqual(m["Subject"], "123456 is your Better Jobs code")
        self.assertIn("123456", m.get_content())
        self.assertTrue(m["Message-ID"].endswith("@cvwrite3.test>"))

    def test_smtp_needs_starttls_and_logs_in(self):
        from types import SimpleNamespace
        from app import mailer
        s = SimpleNamespace(smtp_host="smtp.example.com", smtp_port=587, smtp_user="u", smtp_password="p",
                            mail_from="cvwrite3 <signin@cvwrite3.test>")
        with mock.patch("smtplib.SMTP") as smtp:
            mailer.SMTPMailer(s).send_code(ALICE, "123456")
        conn = smtp.return_value
        smtp.return_value.starttls.assert_called_once()
        conn.login.assert_called_once_with("u", "p")
        conn.send_message.assert_called_once()
        import smtplib
        with mock.patch("smtplib.SMTP") as smtp, self.assertRaises(mailer.MailError):
            smtp.return_value.starttls.side_effect = smtplib.SMTPNotSupportedError()
            mailer.SMTPMailer(s).send_code(ALICE, "123456")


class RequestAccess(AppCase):
    def test_unknown_email_goes_to_request_page(self):
        r = self.get("/", ALICE)
        self.assertEqual((r.status_code, r.headers["location"]), (303, "/request"))
        r = self.get("/request", ALICE)
        self.assertIn("Join the waitlist", r.text)  # open sign-ups are off by default
        self.assertIn(ALICE, r.text)

    def test_request_once_then_pending(self):
        self.post("/request", ALICE, {"note": "a friend"})
        self.post("/request", ALICE, {"note": "again"})
        with self.conn() as c:
            self.assertEqual(c.execute("select count(*) n from access_requests").fetchone()["n"], 1)
        self.assertIn("You're on the waitlist", self.get("/request", ALICE).text)

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


class Waitlist(AppCase):
    def fill(self, n):
        with self.conn() as c:
            for i in range(n):
                acct = c.execute("insert into accounts (tag) values (%s) returning id", (f"W{i:05d}",)).fetchone()["id"]
                c.execute("insert into allowed_users (email, account_id, approved_via) values (%s, %s, 'owner')", (f"w{i}@example.com", acct))

    def test_cap_is_30(self):
        self.assertEqual(self.settings.wave2_cap, 30)

    def test_open_and_room_lets_people_straight_in(self):
        self.post("/admin/wave2", OWNER, {"on": "yes"})
        page = self.get("/request", ALICE).text
        self.assertIn("Join Better Jobs", page)
        self.assertNotIn("Email me once", page)
        self.assertEqual(self.post("/request", ALICE, {"note": ""}).headers["location"], "/")

    def test_full_means_waitlist_with_an_opt_in_email(self):
        self.post("/admin/wave2", OWNER, {"on": "yes"})
        self.fill(self.settings.wave2_cap)
        page = self.get("/request", ALICE).text
        self.assertIn("Join the Better Jobs waitlist", page)
        self.assertIn('name="notify" value="yes">', page)  # unticked
        self.post("/request", ALICE, {"note": "", "notify": "yes"})
        self.post("/request", BOB, {"note": ""})
        with self.conn() as c:
            rows = {r["email"]: r["notify"] for r in c.execute("select email, notify from access_requests where status = 'pending'")}
        self.assertEqual(rows, {ALICE: True, BOB: False})
        self.assertIn("1 asked for an email", self.get("/admin", OWNER).text)

    def test_email_the_waitlist_once_to_those_who_asked(self):
        self.post("/request", ALICE, {"note": "", "notify": "yes"})
        self.post("/request", BOB, {"note": ""})
        self.assertEqual(self.post("/admin/waitlist/email", OWNER).status_code, 400)  # the box must be ticked
        self.assertEqual(self.outbox.sent, [])
        self.assertEqual(self.post("/admin/waitlist/email", ALICE, {"confirm": "yes"}).status_code, 403)  # owner only
        r = self.post("/admin/waitlist/email", OWNER, {"confirm": "yes"})
        self.assertEqual(r.headers["location"], "/admin?emailed=1#waitlist")
        self.assertEqual(self.outbox.sent, [(ALICE, "open")])
        self.post("/admin/waitlist/email", OWNER, {"confirm": "yes"})
        self.assertEqual(self.outbox.sent, [(ALICE, "open")])  # never twice

    def test_a_failed_send_stops_and_keeps_the_rest(self):
        from app import mailer
        for e in (ALICE, BOB):
            self.post("/request", e, {"note": "", "notify": "yes"})
        self.outbox.send_open = mock.Mock(side_effect=mailer.MailError("SMTPServerDisconnected"))
        r = self.post("/admin/waitlist/email", OWNER, {"confirm": "yes"})
        self.assertEqual(r.headers["location"], "/admin?emailed=0-stopped#waitlist")
        with self.conn() as c:
            self.assertEqual(c.execute("select count(*) n from access_requests where notified_at is null").fetchone()["n"], 2)

    def test_waitlisted_person_joins_when_there_is_room(self):
        self.post("/request", ALICE, {"note": "", "notify": "yes"})
        self.post("/admin/wave2", OWNER, {"on": "yes"})
        self.assertIn("Join now", self.get("/request", ALICE).text)
        self.assertEqual(self.post("/request", ALICE).headers["location"], "/")

    def test_open_email_says_where_to_sign_in(self):
        from app import mailer
        m = mailer.open_message("Better Jobs <signin@puascari.com>", ALICE, ORIGIN)
        self.assertEqual(m["Subject"], "There's room at Better Jobs now")
        self.assertIn(ORIGIN, m.get_content())

    def test_retention(self):
        from app import health
        self.post("/request", ALICE, {"note": ""})
        self.post("/request", BOB, {"note": ""})
        with self.conn() as c:
            c.execute("insert into access_requests (email, status, created_at, decided_at) values "
                      "('old-declined@example.com', 'declined', now() - interval '14 months', now() - interval '13 months'), "
                      "('new-declined@example.com', 'declined', now() - interval '2 months', now() - interval '1 month'), "
                      "('old-wait@example.com', 'pending', now() - interval '13 months', null)")
            c.execute("update access_requests set notify = true, notified_at = now() - interval '31 days' where email = %s", (ALICE,))
            health.retention(c)
            left = sorted(r["email"] for r in c.execute("select email from access_requests"))
        self.assertEqual(left, [BOB, "new-declined@example.com"])


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
