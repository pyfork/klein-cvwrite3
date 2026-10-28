"""Chunk 7w: interview prep notes (Addendum 12), the payment-confirmed email (Addendum 11), and the notice's tables."""
import unittest

from app import markdown, mailer, prep
from tests.render_env import needs_render
from tests.support import OWNER, CVCase

AD_TEXT = "Operations Analyst\nWe need someone who can fix late deliveries. The first round is a practical task."
MASTER = "Led route planning for two hubs.\nBuilt weekly SQL reports."


class Verify(unittest.TestCase):
    def test_keeps_notes_whose_sources_are_there_word_for_word(self):
        raw = [{"note": "Bring one late-delivery fix.", "ad_quote": "fix late deliveries", "cv_line": "Led route planning for two hubs"},
               {"note": "Expect a practical task.", "ad_quote": "The first round is a practical task", "cv_line": ""},
               {"note": "Made up.", "ad_quote": "not in the ad at all", "cv_line": ""},
               {"note": "Claims a CV line that isn't there.", "ad_quote": "", "cv_line": "Ran a team of 40"},
               {"note": "No source.", "ad_quote": "", "cv_line": ""},
               {"note": "", "ad_quote": "fix late deliveries", "cv_line": ""}]
        self.assertEqual([n["note"] for n in prep.verify(raw, AD_TEXT, MASTER)],
                         ["Bring one late-delivery fix.", "Expect a practical task."])

    def test_at_most_five_and_bad_input_is_empty(self):
        raw = [{"note": f"Note {i}.", "ad_quote": "fix late deliveries", "cv_line": ""} for i in range(8)]
        self.assertEqual(len(prep.verify(raw, AD_TEXT, MASTER)), 5)
        self.assertEqual(prep.verify("nonsense", AD_TEXT, MASTER), [])


@needs_render
class Prep(CVCase):
    def test_a_passed_cv_has_checked_notes_on_the_result_and_applications(self):
        run_id = self.start()
        self.drain()
        notes = self.run_row(run_id)["interview_prep"]
        self.assertEqual(len(notes), 1)  # the fake's made-up quote is dropped
        page = self.get(f"/runs/{run_id}", self.EMAIL).text
        self.assertIn("Before the interview", page)
        self.assertIn(notes[0]["note"], page)
        apps = self.get("/applications", self.EMAIL).text
        self.assertIn("<summary>Before the interview</summary>", apps)
        self.assertIn("Top keywords:", apps)

    def test_prep_is_not_in_the_cv(self):
        run_id = self.start()
        self.drain()
        self.assertNotIn(self.run_row(run_id)["interview_prep"][0]["note"], self.run_row(run_id)["draft_md"])


class Thanks(CVCase):
    def order(self, credits=5):
        self.post("/credits/buy", self.EMAIL, {"pack": str(credits)})
        with self.conn() as c:
            return c.execute("select * from orders order by id desc limit 1").fetchone()

    def test_approve_sends_one_thank_you(self):
        o = self.order()
        self.post(f"/admin/orders/{o['id']}/approve", OWNER)
        self.post(f"/admin/orders/{o['id']}/approve", OWNER)
        thanks = [m for m in self.outbox.sent if m[1] == "thanks"]
        self.assertEqual(thanks, [(self.EMAIL, "thanks", o["credits"], o["ref"])])
        with self.conn() as c:
            self.assertIsNotNone(c.execute("select thanked_at from orders where id = %s", (o["id"],)).fetchone()["thanked_at"])

    def test_a_failed_send_keeps_the_approval(self):
        def boom(*a):
            raise mailer.MailError("SMTPException")
        self.outbox.send_thanks = boom
        o = self.order()
        self.post(f"/admin/orders/{o['id']}/approve", OWNER)
        with self.conn() as c:
            row = c.execute("select status, thanked_at from orders where id = %s", (o["id"],)).fetchone()
            self.assertEqual((row["status"], row["thanked_at"]), ("approved", None))
            self.assertEqual(c.execute("select route from errors").fetchone()["route"], "orders.thank")

    def test_the_text(self):
        m = mailer.thanks_message("signin@puascari.com", "a@example.com", 12, "CV3-ABCD", "https://betterjobs.puascari.com")
        self.assertEqual(m["Subject"], "Thank you for your payment!")
        self.assertIn("12 credits have been added to your account (order CV3-ABCD). You can use them now: https://betterjobs.puascari.com",
                      m.get_content())


class Tables(unittest.TestCase):
    def test_a_table_is_escaped_and_ends_at_the_next_paragraph(self):
        html = markdown.to_html("| A | B |\n|---|---|\n| **x** | <i>y</i> |\nAfter.")
        self.assertIn("<th scope=\"col\">A</th>", html)
        self.assertIn("<td><b>x</b></td><td>&lt;i&gt;y&lt;/i&gt;</td>", html)
        self.assertTrue(html.endswith("<p>After.</p>"))


if __name__ == "__main__":
    unittest.main()
