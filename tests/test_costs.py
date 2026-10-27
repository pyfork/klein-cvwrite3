"""Chunk 7x: cost and credits per CV for the owner. The admin page shows the latest 20; the CSV has every one."""
import csv
import io

from tests.support import OWNER, CVCase


class Costs(CVCase):
    def test_admin_shows_the_latest_20_and_the_csv_has_all(self):
        for _ in range(2):
            self.start()
            self.drain()
        with self.conn() as c:
            n = c.execute("select count(distinct run_id) n from usage").fetchone()["n"]
            c.execute("""insert into usage (run_id, account_id, step, model, input_tokens, output_tokens, cost_usd)
                         select r.id, r.account_id, 'call_b', 'claude-opus-5-5', 10, 10, 0.01
                         from (select id, account_id from runs limit 1) r, generate_series(1, 1)""")
            first = c.execute("select id, account_id, ad_text from runs order by id limit 1").fetchone()
            for _ in range(25):
                rid = c.execute("insert into runs (account_id, ad_text, status) select account_id, ad_text, 'failed' from runs where id = %s returning id",
                                (first["id"],)).fetchone()["id"]
                c.execute("insert into usage (run_id, account_id, step, model, input_tokens, output_tokens, cost_usd) "
                          "values (%s, %s, 'call_a', 'claude-opus-5-5', 100, 50, 0.002)", (rid, first["account_id"]))
        page = self.get("/admin", OWNER).text
        self.assertIn("Latest CVs: cost and credits", page)
        self.assertEqual(page.count("<td>failed</td>") + page.count("<td>passed</td>"), 20)
        r = self.get("/admin/costs.csv", OWNER)
        self.assertEqual((r.status_code, r.headers["content-type"].split(";")[0]), (200, "text/csv"))
        rows = list(csv.DictReader(io.StringIO(r.text)))
        self.assertEqual(len(rows), n + 25)
        passed = [x for x in rows if x["status"] == "passed"]
        self.assertTrue(all(x["credits_used"] == "1" and x["interview_prep"] == "True" for x in passed))
        self.assertNotIn("Operations", r.text)  # numbers only, never ad or CV text

    def test_only_the_owner(self):
        self.assertNotEqual(self.get("/admin/costs.csv", self.EMAIL).status_code, 200)
