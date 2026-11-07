"""CVWRITE_HOME (redesign slice 8): the flag's parse in the app's own loader, and `/` with it on or off.
The locked checks in acceptance/ prove the rules; these pin the pieces around them.
senior-lead-Opus5.5-agent, 2026-11-07"""
import unittest
from dataclasses import replace

from app import config
from app.main import create_app
from fastapi.testclient import TestClient
from tests.support import ORIGIN, AppCase

ALICE = "alice@example.com"
BASE = {"CVWRITE_ENV": "dev", "CVWRITE_DATABASE_URL": "postgresql://x/y", "CVWRITE_OWNER_EMAIL": "o@example.com",
        "CVWRITE_SECRET_KEY": "x" * 40, "CVWRITE_APP_ORIGIN": "https://x.test"}


class Setting(unittest.TestCase):
    def test_default_is_off_and_whitespace_is_trimmed(self):
        self.assertIs(config.load(BASE).home, False)
        self.assertIs(config.load({**BASE, "CVWRITE_HOME": " on "}).home, True)

    def test_uppercase_is_refused(self):
        with self.assertRaises(config.ConfigError):
            config.load({**BASE, "CVWRITE_HOME": "ON"})


class Home(AppCase):
    def turn_on(self):
        self.client.close()
        self.settings = replace(self.settings, home=True)
        self.client = TestClient(create_app(self.settings, mail=self.outbox), base_url=ORIGIN, follow_redirects=False)

    def test_off_no_cookie_goes_to_signin(self):
        self.assertEqual(self.client.get("/").headers["location"], "/signin")

    def test_on_page_extends_the_shell(self):
        self.turn_on()
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn('class="skip"', r.text)   # base.html's skip link: the placeholder is inside the shell

    def test_on_an_empty_session_cookie_goes_through_todays_checks(self):   # AC-186: present counts, even empty
        self.turn_on()
        r = self.client.get("/", headers={"Cookie": "cvwrite3="})
        self.assertEqual(r.headers["location"], "/signin")

    def test_on_a_signed_in_visitor_is_redirected_as_today(self):
        self.turn_on()
        self.assertEqual(self.get("/", ALICE).headers["location"], "/request")


if __name__ == "__main__":
    unittest.main()
