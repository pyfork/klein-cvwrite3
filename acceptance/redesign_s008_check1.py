"""Locked check, redesign S-008. CHECK 1: the flag `CVWRITE_HOME` (AC-185, AC-186).

AC-185: production refuses the setting on, and any value but on or off, naming it; dev takes on and off; blank is off.
AC-186: with it on, a visitor whose request carries no session cookie gets 200 and an HTML page (`index.html`; in slice 8
a placeholder, which slice 9 replaces with the top half), `private, no-store`, no cookie and no session row; a request
with a session cookie, live or not, goes through today's checks.
Fails before the work: Settings has no `home` field, so production loads `CVWRITE_HOME=on` and the app cannot be built
with the setting on. Needs no browser: the page's look is slice 9's.
senior-lead-Opus5.5-agent, 2026-11-07 (re-split by the plan review of #143: the flag is its own slice)
Re-planned 2026-11-08 (slice 9's plan, tech review of #145): an empty session cookie goes through today's checks; the
pending sign-in cookie alone, which is not a session cookie, gets the home.
"""
import dataclasses
import unittest

import redesign_s001_common  # noqa: F401  (puts the repo on sys.path)
from fastapi.testclient import TestClient
from tests.support import AppCase, ORIGIN


def env(**kw):
    base = {"CVWRITE_ENV": "dev", "CVWRITE_DATABASE_URL": "postgresql://x/y", "CVWRITE_OWNER_EMAIL": "owner@example.com",
            "CVWRITE_SECRET_KEY": "x" * 40, "CVWRITE_APP_ORIGIN": "https://cvwrite3.test", "CVWRITE_CLAUDE": "real"}
    if kw.get("CVWRITE_ENV") == "prod":
        base.update(CVWRITE_SMTP_HOST="smtp.example.com", CVWRITE_SMTP_USER="u", CVWRITE_SMTP_PASSWORD="p",
                    CVWRITE_MAIL_FROM="Better Jobs <signin@example.com>")
    base.update({k: v for k, v in kw.items() if v is not None})
    return base


class TheSetting(unittest.TestCase):
    """AC-185: production refuses CVWRITE_HOME=on and any value but on or off; dev takes on and off; blank is off."""

    def load(self, **kw):
        from app import config
        return config.load(env(**kw))

    def test_ac185_production_refuses_on_and_odd_values(self):
        from app import config
        for value in ("on", "ON", "yes", "1", "maybe"):
            with self.subTest(value=value):
                with self.assertRaises(config.ConfigError) as e:
                    self.load(CVWRITE_ENV="prod", CVWRITE_HOME=value)
                self.assertIn("CVWRITE_HOME", str(e.exception))

    def test_ac185_production_takes_off_and_unset(self):
        self.assertIs(self.load(CVWRITE_ENV="prod", CVWRITE_HOME="off").home, False)
        self.assertIs(self.load(CVWRITE_ENV="prod").home, False)
        self.assertIs(self.load(CVWRITE_ENV="prod", CVWRITE_HOME="").home, False)   # a blank line in the env file is off

    def test_ac185_dev_takes_on_and_off_only(self):
        from app import config
        self.assertIs(self.load(CVWRITE_HOME="on").home, True)
        self.assertIs(self.load(CVWRITE_HOME="off").home, False)
        self.assertIs(self.load().home, False)
        self.assertIs(self.load(CVWRITE_HOME="").home, False)
        with self.assertRaises(config.ConfigError) as e:
            self.load(CVWRITE_HOME="yes")
        self.assertIn("CVWRITE_HOME", str(e.exception))


class HomeCase(AppCase):
    """AppCase with the setting `home` on (dev)."""

    def setUp(self):
        super().setUp()
        self.client.close()
        self.settings = dataclasses.replace(self.settings, home=True)   # fails before the work: no such field
        from app.main import create_app
        self.app = create_app(self.settings, mail=self.outbox)
        self.client = TestClient(self.app, base_url=ORIGIN, follow_redirects=False)


class TheRoute(HomeCase):
    """AC-186: with the setting on, no cookie gets the home; a cookie goes through today's checks."""

    def test_ac186_no_cookie_gets_the_home(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.headers["content-type"].startswith("text/html"))
        self.assertEqual(r.headers.get("cache-control"), "private, no-store")
        self.assertNotIn("set-cookie", {k.lower() for k in r.headers.keys()})
        self.assertIn("<html", r.text)
        with self.conn() as c:
            self.assertEqual(c.execute("select count(*) n from sessions").fetchone()["n"], 0)

    def test_ac186_a_cookie_goes_through_todays_checks(self):
        junk = {"Cookie": "cvwrite3=not-a-session"}
        self.assertEqual((lambda r: (r.status_code, r.headers.get("location")))(self.client.get("/", headers=junk)), (303, "/signin"))
        cookie = self.as_user("ended@example.com")
        with self.conn() as c:
            c.execute("update sessions set expires_at = now() - interval '1 second'")
        r = self.client.get("/", headers=cookie)
        self.assertEqual((r.status_code, r.headers.get("location")), (303, "/signin"))
        r = self.get("/", "stranger@example.com")
        self.assertEqual((r.status_code, r.headers.get("location")), (303, "/request"))
        self.approve("nadia@example.com")
        self.agree("nadia@example.com")
        r = self.get("/", "nadia@example.com")
        self.assertEqual((r.status_code, r.headers.get("location")), (303, "/profile"))

    def test_ac186_an_empty_session_cookie_goes_through_todays_checks(self):
        # re-plan 2026-11-08 (slice 9's plan): tech review of #145, row 1. The cookie is there by name, so it is a session
        # cookie, live or not; its value is not read here.
        r = self.client.get("/", headers={"Cookie": "cvwrite3="})
        self.assertEqual((r.status_code, r.headers.get("location")), (303, "/signin"))

    def test_ac186_the_pending_sign_in_cookie_alone_gets_the_home(self):
        # re-plan 2026-11-08 (slice 9's plan): tech review of #145, the pending-cookie row. A visitor who asked for a code
        # carries `cvwrite3_pending` and no session cookie, so AC-186 gives them the home; slice 13 decides it again.
        r = self.client.get("/", headers={"Cookie": "cvwrite3_pending=1.e30.0"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers.get("cache-control"), "private, no-store")
        self.assertNotIn("set-cookie", {k.lower() for k in r.headers.keys()})
        with self.conn() as c:
            self.assertEqual(c.execute("select count(*) n from sessions").fetchone()["n"], 0)


if __name__ == "__main__":
    unittest.main()
