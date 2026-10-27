"""Chunk 4: credits from the ledger. Oldest first, per-grant expiry, refundable amounts, the paywall, owner refunds."""
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app import credits
from tests.support import OWNER, AppCase

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def at(days):
    return T0 + timedelta(days=days)


def grant(i, kind, n, day):
    return {"id": i, "delta": n, "kind": kind, "expires_at": at(day + 365), "created_at": at(day), "run_id": None}


def debit(i, kind, n, day):
    return {"id": i, "delta": -n, "kind": kind, "expires_at": None, "created_at": at(day), "run_id": i if kind == "spend" else None}


class Math(unittest.TestCase):
    def test_refund_doc_example(self):
        # free 2 -> RM10 pack (5) -> RM30 pack (20) -> 10 used: the 2 free, all 5, and 3 of the 20 are gone.
        ledger = [grant(1, "free", 2, 0), grant(2, "pack", 5, 10), grant(3, "pack", 20, 20)]
        ledger += [debit(10 + i, "spend", 1, 30 + i) for i in range(10)]
        s = credits.compute(ledger, now=at(60))
        self.assertEqual(s.balance, 17)
        self.assertEqual((s.refundable_n, s.refundable_rm), (17, Decimal("25.50")))
        self.assertEqual([g.left for g in s.grants], [0, 0, 17])

    def test_oldest_first_and_expiry(self):
        ledger = [grant(1, "free", 2, 0), grant(2, "pack", 5, 200), debit(3, "spend", 1, 210)]
        s = credits.compute(ledger, now=at(220))
        self.assertEqual([g.left for g in s.grants], [1, 5])  # the free grant was spent first
        self.assertEqual(s.earliest_expiry, at(365))
        later = credits.compute(ledger, now=at(400))  # the free credit expired; the pack is still good
        self.assertEqual((later.balance, later.earliest_expiry), (5, at(565)))
        self.assertEqual((later.refundable_n, later.refundable_rm), (5, Decimal("10.00")))

    def test_spend_after_expiry_uses_a_valid_grant(self):
        ledger = [grant(1, "free", 2, 0), grant(2, "pack", 5, 300), debit(3, "spend", 1, 370)]
        s = credits.compute(ledger, now=at(371))
        self.assertEqual([g.left for g in s.grants], [2, 4])
        self.assertEqual(s.balance, 4)

    def test_expired_paid_credits_arent_refundable(self):
        s = credits.compute([grant(1, "pack", 5, 0)], now=at(366))
        self.assertEqual((s.balance, s.refundable_n), (0, 0))

    def test_refund_takes_the_newest_pack(self):
        ledger = [grant(1, "free", 2, 0), grant(2, "pack", 5, 10), grant(3, "pack", 20, 20), debit(4, "refund", 20, 30)]
        s = credits.compute(ledger, now=at(31))
        self.assertEqual([g.left for g in s.grants], [2, 5, 0])
        self.assertEqual((s.refundable_n, s.refundable_rm), (5, Decimal("10.00")))

    def test_free_credits_are_never_refundable(self):
        self.assertEqual(credits.compute([grant(1, "free", 2, 0)], now=at(1)).refundable_n, 0)

    def test_overdraw_never_shows_negative(self):
        s = credits.compute([grant(1, "free", 1, 0), debit(2, "spend", 1, 1), debit(3, "spend", 1, 2)], now=at(3))
        self.assertEqual((s.balance, s.overdrawn), (0, 1))


class Pages(AppCase):
    EMAIL = "nadia@example.com"

    def setUp(self):
        super().setUp()
        self.approve(self.EMAIL)
        self.agree(self.EMAIL)
        with self.conn() as c:
            self.acct = c.execute("select account_id from allowed_users where email = %s", (self.EMAIL,)).fetchone()["account_id"]

    def add_pack(self, n):
        from app import orders
        with self.conn() as c:
            orders.approve(c, orders.create(c, self.acct, n)["id"])

    def test_balance_and_expiry_on_every_page(self):
        from zoneinfo import ZoneInfo
        from app import caps
        # the user's date, as the app shows it (Malaysia), not UTC: they differ from midnight to 08:00 MYT
        expiry = (datetime.now(ZoneInfo(caps.TZ)) + timedelta(days=365)).strftime("%-d %b %Y")
        for path in ("/generate", "/profile", "/credits"):
            page = self.get(path, self.EMAIL).text
            self.assertIn('<span class="bal-n">2</span>', page, path)
            self.assertIn("earliest expire", page, path)
        self.assertIn(f"The earliest expire on {expiry}", self.get("/credits", self.EMAIL).text)

    def test_dates_are_malaysian_whatever_the_server_timezone(self):
        """Senior D5: no wall clock. A grant made at 23:30 UTC is the next day in Malaysia, and the page
        must say so even when Postgres itself runs in UTC (as on CI)."""
        import psycopg
        from tests.support import _server_uri
        with psycopg.connect(_server_uri(), autocommit=True) as c:
            c.execute(f"alter database {self.dbname} set timezone = 'UTC'")
        with self.conn() as c:
            c.execute("insert into credit_ledger (account_id, delta, kind, created_at, expires_at) values "
                      "(%s, 1, 'free', '2026-03-01 23:30+00', '2027-03-01 23:30+00')", (self.acct,))
        page = self.get("/credits", self.EMAIL).text
        self.assertIn("The earliest expire on 2 Mar 2027", page)   # 07:30 on 2 March in Malaysia
        self.assertIn("<td>2 Mar 2026</td>", page)

    def test_paywall_at_zero(self):
        self.post("/profile", self.EMAIL, {"master_text": "Test Person\n" + "text " * 60, "name": "Test Person"})   # the profile comes first
        with self.conn() as c:
            run = c.execute("insert into runs (account_id, ad_text, status) values (%s, %s, 'passed') returning id", (self.acct, "x" * 300)).fetchone()["id"]
            run2 = c.execute("insert into runs (account_id, ad_text, status) values (%s, %s, 'passed') returning id", (self.acct, "x" * 300)).fetchone()["id"]
            for r in (run, run2):
                c.execute("insert into credit_ledger (account_id, delta, kind, run_id) values (%s, -1, 'spend', %s)", (self.acct, r))
        page = self.get("/generate", self.EMAIL).text
        self.assertIn("You're out of credits", page)
        self.assertIn("RM10", page)
        self.assertIn("RM30", page)
        self.assertIn("buy more", page)
        self.assertEqual(self.post("/generate", self.EMAIL, {"ad": "x" * 300}).status_code, 409)

    def test_credits_page_lists_grants(self):
        self.add_pack(5)
        page = self.get("/credits", self.EMAIL).text
        self.assertIn("Free credits", page)
        self.assertIn("5 credits for RM10", page)
        self.assertIn("5 unused paid credits (RM10.00) can be refunded", page)

    def test_owner_records_a_refund(self):
        self.add_pack(20)
        self.assertIn("20 = RM30.00", self.get("/admin", OWNER).text)
        self.assertEqual(self.post(f"/admin/accounts/{self.acct}/refund", self.EMAIL, {"n": "20"}).status_code, 403)
        self.assertEqual(self.post(f"/admin/accounts/{self.acct}/refund", OWNER, {"n": "21"}).status_code, 400)
        self.assertEqual(self.post(f"/admin/accounts/{self.acct}/refund", OWNER, {"n": "20"}).status_code, 303)
        with self.conn() as c:
            row = c.execute("select delta, kind from credit_ledger where kind = 'refund'").fetchone()
        self.assertEqual((row["delta"], row["kind"]), (-20, "refund"))
        self.assertIn('<span class="bal-n">2</span>', self.get("/credits", self.EMAIL).text)  # the free 2 stay

    def test_refund_amount_returned(self):
        self.add_pack(5)
        self.add_pack(20)
        with self.conn() as c:
            self.assertEqual(credits.record_refund(c, self.acct, 22), Decimal("34.00"))  # 20 x RM1.50 + 2 x RM2.00


if __name__ == "__main__":
    unittest.main()
