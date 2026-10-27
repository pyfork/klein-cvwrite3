"""Chunk 5: orders, the pay screen, "I've paid", and the owner's approve (once) or reject (with a reason)."""
import re
import unittest
from pathlib import Path

from app import orders, pause
from tests.support import OWNER, AppCase


class Orders(AppCase):
    EMAIL = "nadia@example.com"

    def setUp(self):
        super().setUp()
        self.approve(self.EMAIL)
        self.agree(self.EMAIL)

    def buy(self, pack=5, email=None):
        r = self.post("/credits/buy", email or self.EMAIL, {"pack": str(pack)})
        self.assertEqual(r.status_code, 303)
        return r.headers["location"].split("/orders/")[1].split("?")[0]

    def order(self, ref):
        with self.conn() as c:
            return c.execute("select * from orders where ref = %s", (ref,)).fetchone()

    def balance_shown(self):
        return re.search(r'<span class="bal-n">(\d+)</span>', self.get("/credits", self.EMAIL).text).group(1)

    def test_buy_pay_approve(self):
        ref = self.buy(20)
        self.assertRegex(ref, r"^CV3-[A-HJ-NP-Z2-9]{4}$")
        page = self.get(f"/orders/{ref}", self.EMAIL).text
        self.assertIn("Pay RM30.00 by DuitNow QR", page)
        self.assertIn(f"<code>{ref}</code>", page)
        self.assertIn("Placeholder QR", page)
        self.assertIn("We add credits once your payment is confirmed. Credits last 12 months", page)
        self.assertNotIn("in the bank", page)  # the page says the state, never how a payment is checked
        qr = self.get("/orders/qr", self.EMAIL)
        self.assertEqual((qr.status_code, qr.headers["content-type"].split(";")[0]), (200, "image/svg+xml"))
        self.assertIn("no-store", qr.headers["cache-control"])
        self.assertNotIn('href="/admin"', page)  # the order isn't the owner
        self.post(f"/orders/{ref}/paid", self.EMAIL)
        self.assertIn("Payment pending", self.get(f"/orders/{ref}", self.EMAIL).text)
        self.assertEqual(self.balance_shown(), "2")  # "I've paid" adds nothing
        o = self.order(ref)
        self.assertIn("Says paid", self.get("/admin", OWNER).text)
        self.post(f"/admin/orders/{o['id']}/approve", OWNER)
        self.assertEqual(self.balance_shown(), "22")
        self.assertIn("Credits added", self.get(f"/orders/{ref}", self.EMAIL).text)
        with self.conn() as c:
            row = c.execute("select delta, kind, order_id, expires_at - created_at as left from credit_ledger where kind = 'pack'").fetchone()
        self.assertEqual((row["delta"], row["order_id"]), (20, o["id"]))
        self.assertTrue(360 <= row["left"].days <= 366)

    def test_approve_once(self):
        ref = self.buy(5)
        o = self.order(ref)
        self.post(f"/admin/orders/{o['id']}/approve", OWNER)
        self.post(f"/admin/orders/{o['id']}/approve", OWNER)
        with self.conn() as c:
            self.assertIsNone(orders.approve(c, o["id"]))
            self.assertEqual(c.execute("select count(*) n from credit_ledger where kind = 'pack'").fetchone()["n"], 1)
        self.assertEqual(self.balance_shown(), "7")

    def test_reject_needs_a_reason_the_user_sees(self):
        ref = self.buy(5)
        o = self.order(ref)
        self.assertEqual(self.post(f"/admin/orders/{o['id']}/reject", OWNER, {"reason": "  "}).status_code, 400)
        self.post(f"/admin/orders/{o['id']}/reject", OWNER, {"reason": "We received RM5.00, not RM10.00."})
        page = self.get(f"/orders/{ref}", self.EMAIL).text
        self.assertIn("Order not approved", page)
        self.assertIn("We received RM5.00, not RM10.00.", page)
        self.assertEqual(self.balance_shown(), "2")
        self.post(f"/admin/orders/{o['id']}/approve", OWNER)  # a rejected order can't then be approved
        self.assertEqual(self.balance_shown(), "2")

    def test_only_the_owner_decides(self):
        o = self.order(self.buy(5))
        self.assertEqual(self.post(f"/admin/orders/{o['id']}/approve", self.EMAIL).status_code, 403)
        self.assertEqual(self.balance_shown(), "2")

    def test_one_open_order_at_a_time(self):
        ref = self.buy(5)
        r = self.post("/credits/buy", self.EMAIL, {"pack": "20"})
        self.assertEqual(r.headers["location"], f"/orders/{ref}?open=1")
        self.post(f"/orders/{ref}/paid", self.EMAIL)
        self.assertNotEqual(self.buy(20), ref)  # once "I've paid", another order can start

    def test_cancel_only_before_paid(self):
        ref = self.buy(5)
        self.post(f"/orders/{ref}/cancel", self.EMAIL)
        self.assertEqual(self.order(ref)["status"], "cancelled")
        ref2 = self.buy(5)
        self.post(f"/orders/{ref2}/paid", self.EMAIL)
        self.assertEqual(self.post(f"/orders/{ref2}/cancel", self.EMAIL).status_code, 409)

    def test_bad_pack_and_others_orders(self):
        self.assertEqual(self.post("/credits/buy", self.EMAIL, {"pack": "7"}).status_code, 400)
        ref = self.buy(5)
        self.approve("bob@example.com")
        self.agree("bob@example.com")
        self.assertEqual(self.get(f"/orders/{ref}", "bob@example.com").status_code, 404)

    def test_buying_closes_after_4_hours_paused(self):
        with self.conn() as c:
            pause.pause(c, "test", "owner")
        self.buy(5)  # still open in the first 4 hours
        with self.conn() as c:
            c.execute("update system_pause set paused_at = now() - interval '5 hours'")
        self.assertEqual(self.post("/credits/buy", self.EMAIL, {"pack": "20"}).status_code, 409)
        self.assertIn("Buying is paused", self.get("/credits", self.EMAIL).text)

    def test_the_real_qr_is_served_when_configured(self):
        from dataclasses import replace
        from fastapi.testclient import TestClient
        from app.main import create_app
        png = Path(self.data_dir) / "qr.png"
        png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 32)
        client = TestClient(create_app(replace(self.settings, qr_path=str(png))), base_url=self.settings.app_origin)
        r = client.get("/orders/qr", headers=self.as_user(self.EMAIL))
        self.assertEqual(r.content[:4], b"\x89PNG")
        ref = self.buy(5)
        self.assertNotIn("Placeholder QR", client.get(f"/orders/{ref}", headers=self.as_user(self.EMAIL)).text)


if __name__ == "__main__":
    unittest.main()
