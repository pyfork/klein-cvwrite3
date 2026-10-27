"""Chunk 7v (Addendum 8): the applications list (one row per job, the ad and the latest CV), kept 30 days or, by choice,
3 months. The choice exists once notice v2.0 is the latest; until then the page says 30 days and the route refuses.
Runs are made by hand, so no render is needed. Made-up data only.
"""
import io
import json
import unittest
import zipfile
from types import SimpleNamespace
from unittest.mock import patch

from app import account, cvtext, notices
from tests.support import CVCase

CHOICE = patch("app.notices.keeps_choice", return_value=True)   # as if v2.0 were published


def ad(topic):
    return f"{topic} wanted. " + "We are a growing team and we need someone to fix things that keep slipping. " * 4


class Apps(CVCase):
    def acct(self, email=None):
        with self.conn() as c:
            return c.execute("select account_id from allowed_users where email = %s", (email or self.EMAIL,)).fetchone()["account_id"]

    def add(self, text, status="passed", title=None, days_old=0, hashed=True, email=None):
        with self.conn() as c:
            return c.execute(
                "insert into runs (account_id, ad_text, ad_hash, status, ad_read, created_at, passed_at) "
                "values (%s, %s, %s, %s, %s::jsonb, now() - make_interval(days => %s), "
                "case when %s = 'passed' then now() - make_interval(days => %s) end) returning id",
                (self.acct(email), text, cvtext.ad_hash(text) if hashed else None, status,
                 json.dumps({"job_title": title}) if title else None, days_old, status, days_old)).fetchone()["id"]

    def page(self, path="/applications", email=None):
        return self.get(path, email or self.EMAIL).text

    # ---- the list ----------------------------------------------------------------
    def test_one_row_per_job_newest_first_with_the_latest_cv(self):
        old = self.add(ad("Analyst"), title="Analyst", days_old=9)
        new = self.add(ad("Analyst"), title="Analyst", days_old=2)   # the same ad again: the same job
        other = self.add(ad("Planner"), title="Planner", days_old=5)
        page = self.page()
        self.assertIn("2 jobs", page)
        self.assertIn(f'href="/runs/{new}/cv.pdf"', page)
        self.assertNotIn(f'href="/runs/{old}/cv.pdf"', page)
        self.assertLess(page.index(f'href="/runs/{new}">Analyst'), page.index(f'href="/runs/{other}">Planner'))

    def test_a_newer_failure_does_not_hide_the_cv_you_have(self):
        good = self.add(ad("Analyst"), title="Analyst", days_old=6)
        self.add(ad("Analyst"), status="failed", days_old=1)
        page = self.page()
        self.assertIn(f'href="/runs/{good}/cv.pdf"', page)
        self.assertIn("1 job<", page)

    def test_a_job_with_no_cv_says_why(self):
        self.add(ad("Planner"), status="failed")
        self.add(ad("Driver"), status="generating")
        page = self.page()
        self.assertIn("No credit used", page)
        self.assertIn('<span class="badge badge-wait">Working</span>', page)
        self.assertNotIn("/cv.pdf", page)

    def test_a_new_cv_being_written_is_shown_beside_the_old_one(self):
        self.add(ad("Analyst"), title="Analyst", days_old=6)
        self.add(ad("Analyst"), status="generating")
        self.assertIn("New one working", self.page())

    def test_a_run_with_no_title_is_named_by_its_ad(self):
        self.add(ad("Warehouse Supervisor"), status="failed")
        self.assertIn("Warehouse Supervisor wanted.", self.page())

    def test_runs_from_before_the_hash_each_stand_alone(self):
        self.add(ad("Analyst"), title="Analyst", hashed=False, days_old=3)
        self.add(ad("Analyst"), title="Analyst", hashed=False, days_old=1)
        self.assertIn("2 jobs", self.page())

    def test_only_your_own_jobs_and_ads(self):
        mine = self.add(ad("Analyst"), title="Analyst")
        other = "other@example.com"
        self.approve(other)
        self.agree(other)
        page = self.page(email=other)
        self.assertIn("No applications yet", page)
        self.assertNotIn("Analyst", page)
        self.assertEqual(self.get(f"/runs/{mine}/ad", other).status_code, 404)

    def test_empty_state_points_at_generate(self):
        page = self.page()
        self.assertIn("No applications yet", page)
        self.assertIn('href="/generate">Write your first CV', page)

    def test_the_ad_page_and_the_ways_back(self):
        run = self.add(ad("Analyst"), title="Analyst")
        page = self.page(f"/runs/{run}/ad")
        self.assertIn("Analyst wanted.", page)
        self.assertIn(f'href="/runs/{run}">Open the CV', page)
        self.assertIn('href="/applications">Back to your applications', page)
        failed = self.add(ad("Driver"), status="failed")
        self.assertNotIn("Open the CV", self.page(f"/runs/{failed}/ad"))

    def test_the_nav_and_generate_lead_to_the_list(self):
        page = self.page("/generate")
        self.assertIn('<a href="/applications"><span>Applications</span></a>', page)
        self.assertIn('<a href="/applications" aria-current="page"><span>Applications</span></a>', self.page())
        self.add(ad("Analyst"), title="Analyst")
        self.assertIn('href="/applications">See all your applications', self.page("/generate"))

    # ---- how long they are kept --------------------------------------------------
    def test_until_v2_the_page_says_30_days_and_has_no_tick(self):
        page = self.page()
        self.assertIn("30 days from the day its CV was made", page)
        self.assertNotIn('name="keep"', page)
        r = self.post("/applications/keep", self.EMAIL, {"keep": "yes"})
        self.assertEqual(r.status_code, 404)
        with self.conn() as c:
            self.assertFalse(c.execute("select keep_applications from accounts where id = %s", (self.acct(),)).fetchone()["keep_applications"])

    def test_the_choice_follows_the_notice_version(self):
        for key, expected in (((1, 0), False), ((1, 9), False), ((2, 0), True), ((3, 1), True)):
            with patch("app.notices.latest", return_value=SimpleNamespace(key=key)):
                self.assertEqual(notices.keeps_choice(), expected, key)

    def test_ticking_keeps_applications_3_months(self):
        with CHOICE:
            page = self.page()
            self.assertIn('<input type="checkbox" name="keep" value="yes">', page)
            self.assertIn("Keep my applications for 3 months", page)
            r = self.post("/applications/keep", self.EMAIL, {"keep": "yes"})
            self.assertEqual(r.headers["location"], "/applications?saved=on")
            page = self.page("/applications?saved=on")
            self.assertIn("We keep your applications for 3 months", page)
            self.assertIn('name="keep" value="yes" checked', page)
        with self.conn() as c:
            self.assertEqual(account.retention_label(c, self.acct()), "3 months")

    def test_retention_keeps_ticked_accounts_3_months_and_others_30_days(self):
        mine_60 = self.add(ad("Analyst"), title="Analyst", days_old=60)
        mine_100 = self.add(ad("Planner"), title="Planner", days_old=100)
        other = "other@example.com"
        self.approve(other)
        self.agree(other)
        theirs_31 = self.add(ad("Driver"), email=other, days_old=31)
        theirs_20 = self.add(ad("Clerk"), email=other, days_old=20)
        with CHOICE:
            self.post("/applications/keep", self.EMAIL, {"keep": "yes"})
        with self.conn() as c:
            account.purge_old_runs(c, self.data_dir)
            gone = {r["id"] for r in c.execute("select id from runs where purged_at is not null").fetchall()}
        self.assertEqual(gone, {mine_100, theirs_31})
        self.assertNotIn(mine_60, gone)
        self.assertNotIn(theirs_20, gone)

    def test_a_running_cv_is_never_purged(self):
        run = self.add(ad("Analyst"), status="generating", days_old=200)
        with self.conn() as c:
            account.purge_old_runs(c, self.data_dir)
        self.assertIsNone(self.run_row(run)["purged_at"])

    def test_unticking_asks_first_when_older_ones_would_go(self):
        old = self.add(ad("Analyst"), title="Analyst", days_old=50)
        self.add(ad("Planner"), title="Planner", days_old=3)
        with CHOICE:
            self.post("/applications/keep", self.EMAIL, {"keep": "yes"})
            r = self.post("/applications/keep", self.EMAIL, {"keep": ""})   # an unticked box posts nothing
            self.assertEqual(r.status_code, 200)
            self.assertIn("1 application is older than 30 days", r.text)
            self.assertIn("deleted at the next daily clean-up", r.text)
            with self.conn() as c:
                self.assertEqual(account.retention_label(c, self.acct()), "3 months")   # nothing changed yet
            r = self.post("/applications/keep", self.EMAIL, {"keep": "", "confirm": "yes"})
            self.assertEqual(r.headers["location"], "/applications?saved=off")
        with self.conn() as c:
            self.assertEqual(account.retention_label(c, self.acct()), "30 days")
            self.assertEqual(c.execute("select purged_at from runs where id = %s", (old,)).fetchone()["purged_at"], None)   # not yet: tonight's job
            account.purge_old_runs(c, self.data_dir)
        self.assertIsNotNone(self.run_row(old)["purged_at"])

    def test_unticking_with_nothing_older_just_saves(self):
        self.add(ad("Planner"), title="Planner", days_old=3)
        with CHOICE:
            self.post("/applications/keep", self.EMAIL, {"keep": "yes"})
            r = self.post("/applications/keep", self.EMAIL, {"keep": ""})
        self.assertEqual(r.headers["location"], "/applications?saved=off")

    def test_posting_the_same_choice_changes_nothing(self):
        with CHOICE:
            r = self.post("/applications/keep", self.EMAIL, {"keep": ""})
        self.assertEqual(r.headers["location"], "/applications")

    def test_a_removed_cv_says_how_long_you_keep_them(self):
        run = self.add(ad("Analyst"), title="Analyst", days_old=40)
        with self.conn() as c:
            account.purge_old_runs(c, self.data_dir)
        self.assertIn("for 30 days, then delete", self.get(f"/runs/{run}", self.EMAIL).text)
        with self.conn() as c:
            c.execute("update accounts set keep_applications = true where id = %s", (self.acct(),))
        self.assertIn("for 3 months, then delete", self.get(f"/runs/{run}", self.EMAIL).text)

    def test_the_download_says_the_same(self):
        with self.conn() as c:
            c.execute("update accounts set keep_applications = true where id = %s", (self.acct(),))
            data = account.export_zip(c, self.data_dir, self.acct(), self.EMAIL)
        z = zipfile.ZipFile(io.BytesIO(data))
        self.assertIn("we keep CVs for 3 months", z.read("README.txt").decode())
        self.assertTrue(json.loads(z.read("profile.json"))["keep_applications_3_months"])


if __name__ == "__main__":
    unittest.main()
