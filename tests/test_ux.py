"""Chunk 7t: the UX audit's fixes (docs/README-ux-audit-001.md): what a first-time user sees, why Generate is blocked and
where the reason sits, the credit held by a running CV, "try again" keeping the ad, the bar that points at a CV, the edit
box's header. No render needed: runs are made through the real routes and left queued, or finished by hand. Made-up data only.
"""
import html
import re
import unittest

from app import cvtext, orders, pause
from tests.support import AD, MASTER, AppCase, CVCase

SAMPLE_DRAFT = MASTER.parent / "sample_draft.md"


def profile_form(**over):
    return {"master_text": MASTER.read_text(), "master_name": "master.md", "name": "Nadia Hamzah", "email": "nadia@example.com",
            "phone": "+60 12-345 6789", "location": "Shah Alam", "links": "", "standing_edits": "", **over}


class FirstRun(AppCase):
    """Approved and consented, nothing in the profile yet."""
    EMAIL = "nadia@example.com"

    def setUp(self):
        super().setUp()
        self.approve(self.EMAIL)
        self.agree(self.EMAIL)

    def test_home_goes_to_the_profile_until_it_is_ready(self):
        self.assertEqual(self.get("/", self.EMAIL).headers["location"], "/profile")
        self.post("/profile", self.EMAIL, profile_form(name=""))
        self.assertEqual(self.get("/", self.EMAIL).headers["location"], "/profile")   # a master CV, but no name
        self.post("/profile", self.EMAIL, profile_form())
        self.assertEqual(self.get("/", self.EMAIL).headers["location"], "/generate")

    def test_the_profile_says_it_is_step_1(self):
        self.assertIn("Step 1 of 2", self.get("/profile", self.EMAIL).text)
        self.post("/profile", self.EMAIL, profile_form())
        self.assertNotIn("Step 1 of 2", self.get("/profile", self.EMAIL).text)

    def test_generate_shows_a_checklist_and_no_ad_box(self):
        page = self.get("/generate", self.EMAIL).text
        self.assertIn("Before your first CV", page)
        self.assertIn('href="/profile">Go to Profile', page)
        self.assertNotIn('name="ad"', page)
        self.assertEqual(self.post("/generate", self.EMAIL, {"ad": AD}).status_code, 409)

    def test_the_checklist_ticks_what_is_done(self):
        self.post("/profile", self.EMAIL, profile_form(name=""))
        page = self.get("/generate", self.EMAIL).text
        self.assertRegex(page, r'class="is-done"><span class="dot" aria-hidden="true"></span><span>Upload your master CV')
        self.assertRegex(page, r'class="is-todo"><span class="dot" aria-hidden="true"></span><span>Add your full name')

    def test_the_profile_comes_before_the_paywall(self):
        with self.conn() as c:
            acct = c.execute("select account_id from allowed_users where email = %s", (self.EMAIL,)).fetchone()["account_id"]
            for _ in range(2):
                run = c.execute("insert into runs (account_id, ad_text, status) values (%s, %s, 'passed') returning id", (acct, "x" * 300)).fetchone()["id"]
                c.execute("insert into credit_ledger (account_id, delta, kind, run_id) values (%s, -1, 'spend', %s)", (acct, run))
        page = self.get("/generate", self.EMAIL).text
        self.assertIn("Before your first CV", page)
        self.assertNotIn("You're out of credits", page)

    def test_saving_without_a_name_warns(self):
        r = self.post("/profile", self.EMAIL, profile_form(name=""))
        self.assertEqual(r.headers["location"], "/profile?saved=1")
        page = self.get("/profile?saved=1", self.EMAIL).text
        self.assertIn("Still to do before you can write a CV: add your full name", page)
        self.assertNotIn("Paste a job ad", page)
        self.assertIn("needed to write a CV", page)

    def test_saving_a_ready_profile_offers_the_next_step(self):
        self.post("/profile", self.EMAIL, profile_form())
        page = self.get("/profile?saved=1", self.EMAIL).text
        self.assertIn('href="/generate">Paste a job ad', page)
        self.assertNotIn("Still to do", page)

    def test_the_stepper_has_two_steps_and_two_plain_tabs(self):
        page = self.get("/profile", self.EMAIL).text
        self.assertIn("<i>1</i><span>Profile</span>", page)
        self.assertIn('<a href="/credits"><span>Credits</span></a>', page)
        self.assertIn('<a href="/account"><span>Account</span></a>', page)
        self.post("/profile", self.EMAIL, profile_form())
        page = self.get("/profile", self.EMAIL).text
        self.assertIn('class="done"', page)
        self.assertIn('<i>✓</i><span>Profile<span class="sr"> (done)</span></span>', page)

    def test_the_profile_cards_are_not_numbered(self):
        page = self.get("/profile", self.EMAIL).text
        for old in ("<h2>1. Upload", "<h2>2. Check", "<h2>3. Contact", "<h2>4. Standing"):
            self.assertNotIn(old, page)
        self.assertIn("<h2>Contact details</h2>", page)

    def test_the_stylesheet_url_changes_with_the_version(self):
        """New classes and old cached CSS must never meet: Cloudflare and browsers keep /static/calm.css."""
        from app.main import APP_VERSION
        self.assertIn(f'href="/static/calm.css?v={APP_VERSION}"', self.get("/profile", self.EMAIL).text)
        self.assertEqual(self.client.get(f"/static/calm.css?v={APP_VERSION}").status_code, 200)

    def test_sign_in_no_longer_says_invite_only(self):
        self.assertNotIn("Invite only", self.client.get("/signin").text)


class Blocked(CVCase):
    """A ready profile, 2 free credits. The reason sits between the ad box and the button."""

    def get_generate(self):
        return html.unescape(self.get("/generate", self.EMAIL).text)

    def assert_reason_at_the_button(self, page, reason):
        self.assertIn(reason, page)
        box, why, button = page.index('name="ad"'), page.index('id="gen-why"'), page.index('type="submit" class="btn btn-primary"')
        self.assertLess(box, why)
        self.assertLess(why, button)
        self.assertRegex(page, r'class="btn btn-primary" disabled aria-describedby="gen-why"')

    def test_not_blocked_has_no_reason_and_an_enabled_button(self):
        page = self.get_generate()
        self.assertNotIn("gen-why", page)
        self.assertNotRegex(page, r'class="btn btn-primary" disabled')

    def test_paused_says_it_once_and_the_box_is_read_only(self):
        with self.conn() as c:
            pause.pause(c, "render failing", "auto")
        page = self.get_generate()
        self.assert_reason_at_the_button(page, "you can't start a new CV right now")
        self.assertEqual(page.count("Nothing has been charged"), 1)
        self.assertRegex(page, r'<textarea name="ad"[^>]* readonly')

    def test_the_daily_cap_says_when_it_resets(self):
        with self.conn() as c:
            acct = c.execute("select account_id from allowed_users where email = %s", (self.EMAIL,)).fetchone()["account_id"]
            c.execute("insert into usage (account_id, step, model, input_tokens, output_tokens, cost_usd) "
                      "select %s, 'call_a', 'fake', 1, 1, 0 from generate_series(1, 20)", (acct,))
        self.assert_reason_at_the_button(self.get_generate(), "midnight, Malaysia time")

    def test_out_of_credits_has_the_paywall_and_a_reason_at_the_button(self):
        with self.conn() as c:
            acct = c.execute("select account_id from allowed_users where email = %s", (self.EMAIL,)).fetchone()["account_id"]
            for _ in range(2):
                run = c.execute("insert into runs (account_id, ad_text, status) values (%s, %s, 'passed') returning id", (acct, "x" * 300)).fetchone()["id"]
                c.execute("insert into credit_ledger (account_id, delta, kind, run_id) values (%s, -1, 'spend', %s)", (acct, run))
        page = self.get_generate()
        self.assertIn("You're out of credits", page)
        self.assertIn("RM30", page)
        self.assert_reason_at_the_button(page, "Pick a pack above")

    def test_a_credit_held_by_a_running_cv_is_not_out_of_credits(self):
        first, second = self.start(), self.start()   # both left queued: each holds a credit
        page = self.get_generate()
        self.assertNotIn("You're out of credits", page)
        self.assertNotIn("Pick a pack", page)
        self.assert_reason_at_the_button(page, "Your last credit is held for the CV that's being written")
        self.assertIn(f'href="/runs/{second}">Open it', page)
        self.assertIn('<span class="bal-use">· 2 in use</span>', page)
        self.assertIn("(2 in use right now)", page)
        self.assertNotEqual(first, second)

    def test_the_pill_shows_nothing_in_use_when_nothing_is(self):
        self.assertNotIn("bal-use", self.get_generate())

    def test_one_credit_reads_naturally(self):
        with self.conn() as c:
            acct = c.execute("select account_id from allowed_users where email = %s", (self.EMAIL,)).fetchone()["account_id"]
            run = c.execute("insert into runs (account_id, ad_text, status) values (%s, %s, 'passed') returning id", (acct, "x" * 300)).fetchone()["id"]
            c.execute("insert into credit_ledger (account_id, delta, kind, run_id) values (%s, -1, 'spend', %s)", (acct, run))
        self.assertRegex(self.get_generate(), r"You have 1 credit; it expires on \d")


class TryAgain(CVCase):
    def fail(self, run_id, failure="check_failed"):
        with self.conn() as c:
            c.execute("update runs set status = 'failed', failure = %s where id = %s", (failure, run_id))
            c.execute("update jobs set status = 'done', outcome = 'failed', message = 'No credit used.' where run_id = %s", (run_id,))

    def test_try_again_puts_the_ad_back(self):
        run = self.start()
        self.fail(run)
        self.assertIn(f'href="/generate?from={run}">Try again', self.get(f"/runs/{run}", self.EMAIL).text)
        page = self.get(f"/generate?from={run}", self.EMAIL).text
        self.assertIn("FreshRoute delivers groceries", page)
        self.assertIn("We kept the ad from the CV that didn't finish", page)

    def test_only_your_own_failed_run_is_offered(self):
        other = "other@example.com"
        self.approve(other)
        self.agree(other)
        self.post("/profile", other, profile_form(name="Other Person", email="other@example.com"))
        run = self.start()
        self.assertNotIn("FreshRoute", self.get(f"/generate?from={run}", self.EMAIL).text)   # still generating
        self.fail(run)
        self.assertNotIn("FreshRoute", self.get(f"/generate?from={run}", other).text)         # not theirs
        self.assertNotIn("FreshRoute", self.get("/generate?from=99999", self.EMAIL).text)

    def test_try_again_is_offered_twice_then_the_run_page_asks_for_a_report(self):
        runs = []
        for n in range(3):
            runs.append(self.start())
            self.fail(runs[-1])
            page = self.get(f"/runs/{runs[-1]}", self.EMAIL).text
            self.assertEqual("Try again" in page, n < 2, f"failure {n + 1}")
        self.assertIn("failed 3 times", page)
        self.assertIn("Report this problem", page)
        self.assertEqual(len({self.run_row(r)["ad_hash"] for r in runs}), 1)   # the same ad hashes the same

    def test_a_different_ad_starts_a_fresh_count(self):
        for _ in range(3):
            self.fail(self.start())
        other = self.start(ad=AD.replace("Operations Analyst", "Planning Analyst"))
        self.fail(other)
        self.assertIn("Try again", self.get(f"/runs/{other}", self.EMAIL).text)

    def test_our_failures_never_use_up_the_tries(self):
        for _ in range(4):
            run = self.start()
            self.fail(run, "claude_failed")
        self.assertIn("Try again", self.get(f"/runs/{run}", self.EMAIL).text)

    def test_the_failed_page_and_the_list_name_the_run_by_its_ad(self):
        run = self.start()
        self.fail(run)
        page = self.get(f"/runs/{run}", self.EMAIL).text
        self.assertIn('<h1 class="title">Operations Analyst (Last-Mile Delivery)</h1>', page)
        self.assertNotIn("Your new CV", page)
        listing = self.get("/generate", self.EMAIL).text
        self.assertIn("Operations Analyst (Last-Mile Delivery)", listing)
        self.assertNotIn("Reading the ad", listing)

    def test_a_purge_forgets_the_ad_hash(self):
        from app import account
        run = self.start()
        with self.conn() as c:
            account.purge_run(c, self.data_dir, c.execute("select * from runs where id = %s", (run,)).fetchone())
        row = self.run_row(run)
        self.assertIsNone(row["ad_hash"])
        self.assertIsNone(row["ad_text"])


class CvBar(CVCase):
    """A bar on every page points at a CV being written, then at a finished one nobody has opened."""

    def finish(self, run_id):
        with self.conn() as c:
            c.execute("update runs set status = 'passed', passed_at = now(), draft_md = %s, checks = %s::jsonb, ad_read = %s::jsonb where id = %s",
                      (SAMPLE_DRAFT.read_text(), '{"pages": 2, "keywords": {}}', '{"job_title": "Operations Analyst"}', run_id))
            c.execute("update jobs set status = 'done', outcome = 'passed' where run_id = %s", (run_id,))

    def test_a_cv_being_written_is_pointed_at_from_other_pages(self):
        run = self.start()
        for path in ("/credits", "/profile", "/generate", "/account"):
            page = self.get(path, self.EMAIL).text
            self.assertIn("A CV is being written:", page, path)
            self.assertIn(f'<a href="/runs/{run}">Open it</a>', page, path)
        self.assertNotIn("A CV is being written:", self.get(f"/runs/{run}", self.EMAIL).text)   # not on its own page

    def test_no_bar_without_a_run(self):
        self.assertNotIn("cvbar", self.get("/credits", self.EMAIL).text)

    def test_a_finished_cv_stays_pointed_at_until_it_is_opened(self):
        run = self.start()
        self.finish(run)
        page = self.get("/credits", self.EMAIL).text
        self.assertIn("Your CV is ready:", page)
        self.assertIn("<b>Operations Analyst</b>", page)
        self.assertEqual(self.get(f"/runs/{run}", self.EMAIL).status_code, 200)   # opening it clears the bar
        self.assertNotIn("cvbar", self.get("/credits", self.EMAIL).text)
        self.assertIsNotNone(self.run_row(run)["opened_at"])

    def test_a_cv_in_progress_comes_before_a_finished_one(self):
        done = self.start()
        self.finish(done)
        working = self.start()
        page = self.get("/credits", self.EMAIL).text
        self.assertIn("A CV is being written:", page)
        self.assertIn(f'href="/runs/{working}"', page)

    def test_a_cv_finished_more_than_a_week_ago_is_left_alone(self):
        run = self.start()
        self.finish(run)
        with self.conn() as c:
            c.execute("update runs set passed_at = now() - interval '8 days' where id = %s", (run,))
        self.assertNotIn("cvbar", self.get("/credits", self.EMAIL).text)

    def test_other_people_never_see_your_bar(self):
        other = "other@example.com"
        self.approve(other)
        self.agree(other)
        self.start()
        self.assertNotIn("cvbar", self.get("/credits", other).text)


class Pending(AppCase):
    EMAIL = "nadia@example.com"

    def test_pending_says_where_to_look(self):
        self.approve(self.EMAIL)
        self.agree(self.EMAIL)
        with self.conn() as c:
            acct = c.execute("select account_id from allowed_users where email = %s", (self.EMAIL,)).fetchone()["account_id"]
            ref = orders.create(c, acct, 5)["ref"]
        self.post(f"/orders/{ref}/paid", self.EMAIL)
        page = self.get(f"/orders/{ref}", self.EMAIL).text
        self.assertIn("Payment pending", page)
        self.assertIn("come back later and check your balance in the top corner", page)


class Units(unittest.TestCase):
    def test_ad_title_is_the_first_line_cut_short(self):
        self.assertEqual(cvtext.ad_title("\n\n  Senior   Analyst  \nmore"), "Senior Analyst")
        self.assertEqual(cvtext.ad_title("x" * 80), "x" * 49 + "…")
        self.assertEqual(cvtext.ad_title(""), "Your ad")
        self.assertEqual(cvtext.ad_title(None), "Your ad")

    def test_ad_hash_ignores_spacing_and_case(self):
        self.assertEqual(cvtext.ad_hash("Big  Ad\nText "), cvtext.ad_hash("big ad text"))
        self.assertNotEqual(cvtext.ad_hash("big ad text"), cvtext.ad_hash("big ad texts"))

    def test_the_edit_box_text_starts_at_the_first_heading(self):
        box = cvtext.to_plain(SAMPLE_DRAFT.read_text())
        body = cvtext.plain_body(box)[0]
        self.assertTrue(body.startswith("PROFESSIONAL SUMMARY"))
        self.assertNotIn("[NAME]", body)
        self.assertEqual(re.findall(r"\[(?:NAME|CONTACT)\]", box), ["[NAME]", "[CONTACT]"])


if __name__ == "__main__":
    unittest.main()
