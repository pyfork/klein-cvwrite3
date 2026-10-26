"""Chunk 6: the caps, "not good" feedback, report a problem, errors, /healthz, uptime, degraded events, the funnel."""
import unittest
from decimal import Decimal

from app import caps, health, orders, pause
from tests.support import AD, OWNER, AppCase, CVCase
from tests.render_env import needs_render


def usage(c, acct, step, cost="0.01", n=1, when="now()"):
    for _ in range(n):
        c.execute(f"insert into usage (account_id, step, model, input_tokens, output_tokens, cost_usd, created_at) "
                  f"values (%s, %s, 'claude-opus-5-5', 1, 1, %s, {when})", (acct, step, Decimal(cost)))


class Caps(CVCase):
    def acct(self):
        with self.conn() as c:
            return c.execute("select account_id from allowed_users where email = %s", (self.EMAIL,)).fetchone()["account_id"]

    def test_twenty_a_day_counts_generations_and_rerenders(self):
        with self.conn() as c:
            usage(c, self.acct(), "call_a", n=15)
            usage(c, self.acct(), "reformat", n=4)
            usage(c, self.acct(), "call_b", n=10)            # not counted: the generation already counted at call A
            usage(c, self.acct(), "call_a", n=5, when="now() - interval '2 days'")   # another day
        self.assertEqual(self.post("/generate", self.EMAIL, {"ad": AD}).status_code, 303)  # 19 used, 1 reserved now
        r = self.post("/generate", self.EMAIL, {"ad": AD})
        self.assertEqual(r.status_code, 409)
        self.assertIn("today&#39;s limit of 20", r.text)

    def test_spend_stop_blocks_free_cvs_only(self):
        with self.conn() as c:
            usage(c, None, "call_b", cost="50.01")
            self.assertTrue(caps.next_credit_is_free(c, self.acct()))
        r = self.post("/generate", self.EMAIL, {"ad": AD})
        self.assertEqual(r.status_code, 409)
        self.assertIn("Free CVs are paused", self.get("/generate", self.EMAIL).text)
        with self.conn() as c:  # a paid pack: the free 2 still come first, so still blocked...
            orders.approve(c, orders.create(c, self.acct(), 5)["id"])
            self.assertTrue(caps.next_credit_is_free(c, self.acct()))
            run = c.execute("insert into runs (account_id, ad_text, status) values (%s, %s, 'passed') returning id", (self.acct(), AD)).fetchone()["id"]
            run2 = c.execute("insert into runs (account_id, ad_text, status) values (%s, %s, 'passed') returning id", (self.acct(), AD)).fetchone()["id"]
            for r_ in (run, run2):
                c.execute("insert into credit_ledger (account_id, delta, kind, run_id) values (%s, -1, 'spend', %s)", (self.acct(), r_))
            self.assertFalse(caps.next_credit_is_free(c, self.acct()))  # ...until they're used: then paid CVs run
        self.assertEqual(self.post("/generate", self.EMAIL, {"ad": AD}).status_code, 303)

    def test_reserved_credits_are_skipped(self):
        with self.conn() as c:
            orders.approve(c, orders.create(c, self.acct(), 5)["id"])
            self.assertTrue(caps.next_credit_is_free(c, self.acct(), reserved=1))
            self.assertFalse(caps.next_credit_is_free(c, self.acct(), reserved=2))

    def test_last_month_doesnt_count(self):
        with self.conn() as c:
            usage(c, None, "call_b", cost="60", when="now() - interval '40 days'")
            self.assertLess(caps.month_spend(c), caps.MONTHLY_WARN_USD)


@needs_render
class Feedback(CVCase):
    def test_not_good_is_a_signal_only(self):
        run_id = self.start()
        self.drain()
        draft = self.run_row(run_id)["draft_md"]
        self.assertIn("Something off with this CV?", self.get(f"/runs/{run_id}", self.EMAIL).text)
        self.post(f"/runs/{run_id}/feedback", self.EMAIL, {"reason": "problem"})
        self.post(f"/runs/{run_id}/feedback", self.EMAIL, {"reason": "long"})   # one per CV
        with self.conn() as c:
            self.assertEqual([r["reason"] for r in c.execute("select reason from feedback")], ["problem"])
        self.assertEqual(self.run_row(run_id)["draft_md"], draft)  # nothing rewritten
        self.assertIn("Thanks. This helps us improve", self.get(f"/runs/{run_id}", self.EMAIL).text)
        page = self.get("/admin", OWNER).text
        self.assertIn("Wrong main problem", page)
        self.assertIn("revisit the pause over 20%", page)
        self.assertEqual(self.post(f"/runs/{run_id}/feedback", self.EMAIL, {"reason": "nope"}).status_code, 400)


class Reports(CVCase):
    def test_report_reply_close(self):
        self.assertIn("Report a problem", self.get("/generate", self.EMAIL).text)
        self.post("/report", self.EMAIL, {"category": "privacy", "body": "Send me my data.", "page": "/generate"})
        mine = self.get("/reports?sent=1", self.EMAIL).text
        self.assertIn("Send me my data.", mine)
        self.assertIn("Sent. We'll reply here.", mine.replace("&#39;", "'"))
        admin = self.get("/admin", OWNER).text
        self.assertIn("21 days left to reply", admin)
        with self.conn() as c:
            rid = c.execute("select id, request_id, app_version from problem_reports").fetchone()
        self.assertTrue(rid["request_id"] and rid["app_version"])
        self.post(f"/admin/reports/{rid['id']}/reply", OWNER, {"reply": "Done: download it from your account."})
        self.assertIn("Done: download it from your account.", self.get("/reports", self.EMAIL).text)
        self.post(f"/admin/reports/{rid['id']}/close", OWNER)
        self.assertIn("No open reports.", self.get("/admin", OWNER).text)

    def test_payment_report_links_the_latest_order(self):
        with self.conn() as c:
            acct = c.execute("select account_id from allowed_users where email = %s", (self.EMAIL,)).fetchone()["account_id"]
            o = orders.create(c, acct, 5)
        self.post("/report", self.EMAIL, {"category": "paid", "body": "Paid yesterday."})
        self.assertIn(o["ref"], self.get("/admin", OWNER).text)

    def test_no_duplicate_reports_during_a_pause(self):
        with self.conn() as c:
            pause.pause(c, "test", "owner")
        r = self.post("/report", self.EMAIL, {"category": "broke", "body": "It broke"})
        self.assertEqual(r.headers["location"], "/reports?known=1")
        with self.conn() as c:
            self.assertIsNone(c.execute("select 1 from problem_reports").fetchone())

    def test_owner_only(self):
        self.post("/report", self.EMAIL, {"category": "other", "body": "x"})
        with self.conn() as c:
            rid = c.execute("select id from problem_reports").fetchone()["id"]
        self.assertEqual(self.post(f"/admin/reports/{rid}/reply", self.EMAIL, {"reply": "hi"}).status_code, 403)


class Health(AppCase):
    def test_errors_are_recorded_without_content(self):
        from fastapi import Request

        @self.app.get("/boom")
        def boom(request: Request):
            raise ValueError("secret CV text that must not be stored")
        r = self.client.get("/boom")
        self.assertEqual(r.status_code, 500)
        self.assertIn("Something went wrong", r.text)
        with self.conn() as c:
            e = c.execute("select * from errors").fetchone()
        self.assertEqual((e["error_class"], e["route"]), ("ValueError", "/boom"))
        self.assertNotIn("secret", e["traceback"])
        self.assertIn("in boom", e["traceback"])

    def test_healthz_is_local_only(self):
        from fastapi.testclient import TestClient
        local = TestClient(self.app, base_url="http://127.0.0.1", client=("127.0.0.1", 50000))
        r = local.get("/healthz")
        self.assertIn(r.status_code, (200, 503))
        self.assertIn("db", r.json())
        self.assertEqual(local.get("/healthz", headers={"X-Forwarded-For": "1.2.3.4"}).status_code, 404)
        self.assertEqual(self.client.get("/healthz").status_code, 404)

    def test_uptime_counts_missing_minutes_as_down(self):
        with self.conn() as c:
            for m in range(60):
                c.execute("insert into uptime_checks (checked_at, ok, ms) values (now() - make_interval(mins => %s), true, 5)", (m,))
            self.assertAlmostEqual(health.uptime(c, 24), 100 * 60 / (24 * 60), places=1)
            self.assertAlmostEqual(health.uptime(c, 1), 100.0, places=0)

    def test_uptime_script_writes_a_row(self):
        from app import uptime
        ok, ms, detail = uptime.check("http://127.0.0.1:9/healthz")
        self.assertFalse(ok)
        self.assertIn("error=", detail)

    def test_degraded_opens_and_closes(self):
        with self.conn() as c:
            acct = c.execute("insert into accounts (tag) values ('TTTTTT') returning id").fetchone()["id"]
            for _ in range(6):
                c.execute("insert into runs (account_id, ad_text, status, created_at, passed_at) "
                          "values (%s, %s, 'passed', now() - interval '200 seconds', now())", (acct, AD))
            health.evaluate_degraded(c)
            self.assertEqual([d["kind"] for d in health.degraded_now(c)], ["generation_p95"])
            c.execute("update runs set created_at = passed_at - interval '30 seconds'")
            health.evaluate_degraded(c)
            self.assertEqual(health.degraded_now(c), [])

    def test_too_few_samples_dont_breach(self):
        with self.conn() as c:
            acct = c.execute("insert into accounts (tag) values ('TTTTTU') returning id").fetchone()["id"]
            c.execute("insert into runs (account_id, ad_text, status) values (%s, %s, 'failed')", (acct, AD))
            health.evaluate_degraded(c)
            self.assertEqual(health.degraded_now(c), [])

    def test_admin_panel_and_funnel_render(self):
        page = self.get("/admin", OWNER).text
        for text in ("Health", "Uptime", "Funnel", "Used both free CVs", "Problem reports"):
            self.assertIn(text, page)

    def test_retention(self):
        with self.conn() as c:
            c.execute("insert into errors (error_class, created_at) values ('Old', now() - interval '13 months'), ('New', now())")
            c.execute("insert into run_steps (step, started_at, duration_ms, outcome) values ('render', now() - interval '91 days', 1, 'ok')")
            health.retention(c)
            self.assertEqual([r["error_class"] for r in c.execute("select error_class from errors")], ["New"])
            self.assertIsNone(c.execute("select 1 from run_steps").fetchone())


if __name__ == "__main__":
    unittest.main()
