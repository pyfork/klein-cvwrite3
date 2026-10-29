"""CHECK 2 of redesign S-003: the look in dark, measured in headless Chrome on slice 1's gallery of the old markup
(acceptance/fixtures/s001_gallery.html) with the device set to dark. Covers AC-72, AC-76, AC-77, AC-79, AC-81 and AC-82.
Fails before the work: the stylesheet has no dark values, so the gallery stays light.
senior-lead-Opus5.5-agent, 2026-10-29"""
import unittest

import redesign_s001_common as C
import redesign_s003_common as D

GROUND, SLAB, SLAB2, INK = "rgb(12, 22, 38)", "rgb(20, 34, 58)", "rgb(25, 41, 67)", "rgb(242, 238, 230)"
MUTED, CORAL, ON_ACCENT, ERROR, EDGE = "rgb(149, 162, 181)", "rgb(255, 90, 71)", "rgb(19, 35, 58)", "rgb(255, 138, 128)", "rgb(107, 122, 144)"
TINT = {"a-warn": "rgb(58, 49, 32)", "a-bad": "rgb(62, 35, 41)", "a-ok": "rgb(22, 51, 47)", "a-info": "rgb(24, 47, 72)"}
WIDTHS = [320, 1280]
RINGED = ["#b-btn", "#b-primary", "#f-text", "#t-link", "#sum", "#c-box", "#p-one"]

JS = D.COLOUR_JS + r"""
const q = s => doc.querySelector(s);
const pick = s => { const e = q(s); if (!e) return {missing: s}; const c = cs(e);
  return {color: c.color, bg: c.backgroundColor, edge: c.borderTopColor, left: c.borderLeftColor, opacity: c.opacity, under: bgOf(e.parentElement)}; };
const out = {scheme: cs(doc.documentElement).colorScheme, html: cs(doc.documentElement).backgroundColor, body: cs(doc.body).backgroundColor, text: cs(doc.body).color};
out.el = {}; for (const s of ['#card1','#tcard','#t-hint','#t-p','#b-primary','#b-dis-primary','#b-btn','#b-danger','#f-text','#f-area','#drop','#a-warn','#a-bad','#a-ok','#a-info','#tbl th']) out.el[s] = pick(s);
out.low = lowText(doc.body);
out.marks = ['#a-warn','#a-bad','#a-ok','#a-info'].map(s => { const e = q(s); return [s, ratio(cs(e).borderLeftColor, cs(e).backgroundColor)]; });
out.edge = ratio(cs(q('#f-text')).borderTopColor, bgOf(q('#f-text')));
out.rings = {}; for (const s of %(ringed)s) { const e = q(s); e.focus(); const c = cs(e);
  out.rings[s] = {style: c.outlineStyle, width: c.outlineWidth, color: c.outlineColor, fill: c.backgroundColor, under: bgOf(e.parentElement), ratio: ratio(c.outlineColor, bgOf(e.parentElement))}; }
return out;
""" % {"ringed": RINGED}


class DarkLook(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        C.require_chrome()
        with C.Site() as site:
            cls.data = D.measure(site, "/fx/s001_gallery.html", WIDTHS, JS, "dark")["/fx/s001_gallery.html"]

    def el(self, w, s):
        e = self.data[w]["el"][s]
        self.assertNotIn("missing", e, s)
        return e

    def test_ac72_the_page_is_dark_from_the_root(self):
        for w in WIDTHS:
            d = self.data[w]
            self.assertIn("dark", d["scheme"].split(), w)
            self.assertEqual((d["html"], d["body"], d["text"]), (GROUND, GROUND, INK), w)

    def test_ac76_surfaces_and_text(self):
        for w in WIDTHS:
            self.assertEqual(self.el(w, "#card1")["bg"], SLAB)
            self.assertEqual(self.el(w, "#t-p")["color"], INK)
            self.assertEqual(self.el(w, "#t-hint")["color"], MUTED)
            self.assertEqual(self.el(w, "#tbl th")["color"], MUTED)
            self.assertEqual((self.el(w, "#b-btn")["bg"], self.el(w, "#b-btn")["color"]), (INK, SLAB), "ink buttons invert")

    def test_ac77_app_only_tokens(self):
        for w in WIDTHS:
            self.assertEqual(self.el(w, "#f-text")["edge"], EDGE)
            self.assertEqual(self.el(w, "#b-danger")["bg"], ERROR)
            for s, tint in TINT.items():
                self.assertEqual(self.el(w, s)["bg"], tint, s)

    def test_ac79_text_on_coral_stays_navy(self):
        for w in WIDTHS:
            for s in ("#b-primary", "#b-dis-primary"):
                self.assertEqual((self.el(w, s)["bg"], self.el(w, s)["color"]), (CORAL, ON_ACCENT), s)

    def test_ac81_focus_rings(self):
        for w in WIDTHS:
            for s, r in self.data[w]["rings"].items():
                want = INK if r["fill"] == CORAL else CORAL
                self.assertEqual((r["style"], r["width"], r["color"]), ("solid", "3px", want), (w, s))
                self.assertGreaterEqual(r["ratio"], 3, (w, s, r["under"]))

    def test_ac82_contrast(self):
        for w in WIDTHS:
            d = self.data[w]
            self.assertEqual(d["low"], [], w)
            self.assertGreaterEqual(d["edge"], 3, "field edge")
            for s, r in d["marks"]:
                self.assertGreaterEqual(r, 3, s)


if __name__ == "__main__":
    unittest.main()
