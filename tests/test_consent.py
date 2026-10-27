"""The privacy notice and consent: first consent, versions, the text hash, and asking again."""
import json
import unittest
from unittest import mock

from app import notices
from tests.support import AppCase

ALICE = "alice@example.com"


def fake_versions(*specs):
    return tuple(notices.Version(version=v, date="2026-11-01", status="published", what=f"change {v}", why="test") for v in specs)


class Consent(AppCase):
    def setUp(self):
        super().setUp()
        self.approve(ALICE)

    def test_approved_user_must_consent_first(self):
        r = self.get("/", ALICE)
        self.assertEqual(r.headers["location"], "/consent")
        page = self.get("/consent", ALICE).text
        self.assertIn("Before you start: your privacy", page)
        self.assertIn("What we collect:", page)
        self.assertNotIn("checked", page)  # the boxes start unticked

    def test_consent_needs_the_box(self):
        r = self.post("/consent", ALICE, {"version": notices.latest().version, "lang": "en"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("Tick the first box", r.text)
        with self.conn() as c:
            self.assertIsNone(c.execute("select 1 from consents").fetchone())

    def test_consent_records_version_hash_language_and_sensitive_line(self):
        self.agree(ALICE, sensitive=True)
        with self.conn() as c:
            row = c.execute("select * from consents where email = %s", (ALICE,)).fetchone()
        v = notices.latest().version
        self.assertEqual((row["notice_version"], row["lang"], row["sensitive"]), (v, "en", True))
        self.assertEqual(row["text_hash"], notices.text_hash(v, "en"))
        r = self.get("/generate", ALICE)
        self.assertEqual(r.status_code, 200)
        self.assertIn("New CV for a job ad", r.text)
        self.assertEqual(self.get("/consent", ALICE).headers["location"], "/")

    def test_stale_version_is_refused(self):
        r = self.post("/consent", ALICE, {"agree": "yes", "version": "0.9", "lang": "en"})
        self.assertEqual(r.status_code, 400)

    def test_major_version_asks_again(self):
        self.agree(ALICE)
        major, minor = notices.parse(notices.latest().version)   # the version Alice just agreed to
        base, minor_next, major_next = f"{major}.{minor}", f"{major}.{minor + 1}", f"{major + 1}.0"
        with mock.patch.object(notices, "versions", lambda: fake_versions(base, minor_next, major_next)), \
             mock.patch.object(notices, "text_hash", lambda v, lang: "b" * 64), \
             mock.patch.object(notices, "text", lambda v, lang: "## In short\n- **New:** something"):
            r = self.get("/", ALICE)
            self.assertEqual(r.headers["location"], "/consent")
            page = self.get("/consent", ALICE).text
            self.assertIn("updated our privacy notice", page)
            self.assertIn(f"What changed in v{major_next}:", page)
            self.assertIn(f"What changed in v{minor_next}:", page)
            self.agree(ALICE)
            self.assertEqual(self.get("/generate", ALICE).status_code, 200)
        with self.conn() as c:
            self.assertEqual([r["notice_version"] for r in c.execute("select notice_version from consents order by id")], [base, major_next])

    def test_minor_version_doesnt_ask(self):
        self.agree(ALICE)
        major, minor = notices.parse(notices.latest().version)   # the version Alice just agreed to
        with mock.patch.object(notices, "versions", lambda: fake_versions(f"{major}.{minor}", f"{major}.{minor + 1}")):
            self.assertEqual(self.get("/generate", ALICE).status_code, 200)

    def test_deleted_accounts_consent_doesnt_count(self):
        self.agree(ALICE)
        with self.conn() as c:
            c.execute("update consents set account_deleted_at = now()")
        self.assertEqual(self.get("/", ALICE).headers["location"], "/consent")


class NoticePages(AppCase):
    def test_malay_consent_and_notice(self):
        self.approve(ALICE)
        page = self.get("/consent?lang=ms", ALICE).text
        for s in ("Sebelum anda bermula", "Sesetengah penyedia berada di luar Malaysia", "Saya telah membaca notis privasi ini dan bersetuju.",
                  "Teruskan", '<a href="/consent?lang=en" lang="en">English</a>'):
            self.assertIn(s, page)
        v = notices.latest().version
        self.assertIn("Tandakan kotak pertama", self.post("/consent", ALICE, {"version": v, "lang": "ms"}).text)
        self.post("/consent", ALICE, {"agree": "yes", "version": v, "lang": "ms"})
        with self.conn() as c:
            row = c.execute("select lang, text_hash from consents where email = %s", (ALICE,)).fetchone()
        self.assertEqual((row["lang"], row["text_hash"]), ("ms", notices.text_hash(v, "ms")))
        notice = self.get("/privacy?lang=ms", ALICE).text
        self.assertIn("1. Siapa kami", notice)
        self.assertIn('<div lang="ms">', notice)

    def test_unknown_language_falls_back_to_english(self):
        self.assertIn("1. Who we are", self.get("/privacy?lang=xx", ALICE).text)

    def test_pages(self):
        v = notices.latest().version
        self.assertIn("1. Who we are", self.get("/privacy", ALICE).text)
        self.assertEqual(self.get(f"/privacy/v{v}", ALICE).status_code, 200)
        self.assertEqual(self.get("/privacy/v9.9", ALICE).status_code, 404)
        self.assertIn(f"v{v}", self.get("/privacy/changes", ALICE).text)

    def test_notice_html_is_escaped(self):
        from app.markdown import to_html
        out = to_html("## Hi <script>\n- a <b>x</b> [ok](/privacy) [bad](javascript:alert(1))")
        self.assertNotIn("<script>", out)
        self.assertNotIn("<b>x</b>", out)
        self.assertIn('<a href="/privacy">ok</a>', out)
        self.assertNotIn('href="javascript', out)


class ProdGuard(AppCase):
    def test_prod_refuses_a_draft_notice(self):
        from dataclasses import replace
        from app import config
        from app.main import create_app
        drafts = (notices.Version("1.0", "2026-10-22", "draft", "x", "y"),)
        with mock.patch.object(notices, "versions", lambda: drafts):
            with self.assertRaises(config.ConfigError):
                create_app(replace(self.settings, env="prod"))


if __name__ == "__main__":
    unittest.main()
