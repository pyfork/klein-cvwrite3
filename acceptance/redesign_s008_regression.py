"""Locked check, redesign S-008. REGRESSION A (passes before): with the setting off, `/` answers exactly as today (AC-184).

A flag-off case (plans/redesign-plan.md, Check cap): it keeps the off path whole while slices 8 to 10 build the home
behind the flag. Slice 11, which removes the flag, retires it by a re-plan of this check with the reason.
The app is built with the suite's own settings, which name no `home` setting, so this runs the same before and after.
senior-lead-Opus5.5-agent, 2026-11-07
"""
import unittest

import redesign_s001_common  # noqa: F401  (puts the repo on sys.path)
from tests.support import AppCase as Base, MASTER


def where(r):
    return r.status_code, r.headers.get("location")


class FlagOff(Base):
    def test_ac184_signed_out_goes_to_signin(self):
        self.assertEqual(where(self.client.get("/")), (303, "/signin"))
        self.assertEqual(where(self.client.get("/", headers={"Cookie": "cvwrite3=not-a-session"})), (303, "/signin"))
        cookie = self.as_user("ended@example.com")
        with self.conn() as c:
            c.execute("update sessions set expires_at = now() - interval '1 second'")
        self.assertEqual(where(self.client.get("/", headers=cookie)), (303, "/signin"))

    def test_ac184_signed_in_goes_where_it_goes_today(self):
        self.assertEqual(where(self.get("/", "stranger@example.com")), (303, "/request"))
        em = "nadia@example.com"
        self.approve(em)
        self.assertEqual(where(self.get("/", em)), (303, "/consent"))
        self.agree(em)
        self.assertEqual(where(self.get("/", em)), (303, "/profile"))
        self.post("/profile", em, {"master_text": MASTER.read_text(), "master_name": "master.md", "name": "Nadia Hamzah",
                                   "email": em, "phone": "+60 12-345 6789", "location": "Shah Alam", "links": "", "standing_edits": ""})
        self.assertEqual(where(self.get("/", em)), (303, "/generate"))

    def test_ac184_the_default_setting_is_off(self):
        self.assertFalse(getattr(self.settings, "home", False))


if __name__ == "__main__":
    unittest.main()
