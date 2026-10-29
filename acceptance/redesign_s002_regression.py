"""REGRESSION A of redesign S-002 (AC-73, passes before; guards slice 1's look): with the device set to light, slice 1's
gallery keeps slice 1's colours. A browser with no preference matches no prefers-color-scheme rule, and CHECK 1 locks that
the dark block is the only one, so it gets these same values; Chrome's no-preference setting hangs under this harness
(2026-10-29), so it is not measured here.
senior-lead-Opus5.5-agent, 2026-10-29"""
import unittest

import redesign_s001_common as C
import redesign_s002_common as D

WIDTHS = [320, 1280]
GROUND, SLAB, INK, MUTED, CORAL = "rgb(242, 241, 237)", "rgb(255, 255, 255)", "rgb(19, 35, 58)", "rgb(86, 98, 117)", "rgb(255, 90, 71)"
JS = r"""
const cs = e => win.getComputedStyle(e), q = s => doc.querySelector(s);
return {scheme: cs(doc.documentElement).colorScheme, html: cs(doc.documentElement).backgroundColor, body: cs(doc.body).backgroundColor,
  text: cs(doc.body).color, card: cs(q('#card1')).backgroundColor, primary: [cs(q('#b-primary')).backgroundColor, cs(q('#b-primary')).color],
  btn: [cs(q('#b-btn')).backgroundColor, cs(q('#b-btn')).color], edge: cs(q('#f-text')).borderTopColor, tint: cs(q('#a-warn')).backgroundColor};
"""


class LightStays(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        C.require_chrome()
        with C.Site() as site:
            cls.light = D.measure(site, "/fx/s001_gallery.html", WIDTHS, JS, "light")["/fx/s001_gallery.html"]

    def test_ac73_a_light_device_sees_slice_1s_look(self):
        for w in WIDTHS:
            d = self.light[w]
            self.assertIn("light", d["scheme"].split(), w)
            self.assertEqual((d["html"], d["body"], d["text"], d["card"]), (GROUND, GROUND, INK, SLAB), w)
            self.assertEqual(d["primary"], [CORAL, INK], w)
            self.assertEqual(d["btn"], [INK, SLAB], w)
            self.assertEqual((d["edge"], d["tint"]), ("rgb(125, 135, 152)", "rgb(251, 231, 176)"), w)


if __name__ == "__main__":
    unittest.main()
