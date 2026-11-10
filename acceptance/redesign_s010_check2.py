"""Locked check, redesign S-010. CHECK 2: the look of "See it work." and the keywords, in Chrome with scripts off, light and dark.

AC-101 (the keywords slab: white, 32 px radius, v2's `.slab` padding; the navy band the full window width), AC-102 (the
band's and the keywords' v2 literals are tokens), AC-106 ("Examples" lands below the sticky header), AC-118 (the navy
band: its colour, 64 px from its neighbours, torn edges from `edge.webp`, the scissors at -8 degrees from 700 px),
AC-122 (the panel's columns either side of 961 and the slider's height), AC-123 (teal words on the darker teal),
AC-125 and AC-133 (the counts' colours), AC-134 (the keyword columns either side of 901), AC-170 (the band in dark)
and AC-176 (v2's `h2`). The stylesheets are the ones the home links, whatever their names (the decision on slice 9).
Fails before the work: the home ends after the hero, so there is no band and no keywords slab to measure.
senior-lead-Opus5.5-agent, 2026-11-10 (cut from the top half's draft on branch draft-redesign-top-half, 3411036)
"""
import json
import re
import unittest

import redesign_s001_common as C
import redesign_s009_common as H

FIX = json.loads((H.ROOT / "acceptance" / "fixtures" / "s010_v2_text.json").read_text(encoding="utf-8"))
LIGHT = [320, 390, 699, 700, 768, 900, 901, 960, 961, 1280, 1440]   # each side of the band's 700, the keywords' 901, the panel's 961
DARK = [390, 1280]

LOOK_JS = r"""
const out = {W};
const px = v => parseFloat(v) || 0;
const angle = e => { const m = cs(e).transform; if (!m || m === 'none') return 0; const v = m.match(/-?[\d.e]+/g).map(Number); return Math.round(Math.atan2(v[1], v[0]) * 180 / Math.PI * 10) / 10; };
const hd = header(doc);
const h1 = doc.querySelector('h1'), hero = h1 && h1.closest('section');
const band = section(doc, %(band)s), words = section(doc, %(words)s);
const slab = s => s ? {bg: cs(s).backgroundColor, r: cs(s).borderTopLeftRadius, pt: px(cs(s).paddingTop), pb: px(cs(s).paddingBottom), pl: px(cs(s).paddingLeft), pr: px(cs(s).paddingRight), ...box(s)} : null;
out.words = slab(words); out.band = slab(band);
if (band) {
  const edges = [band, ...band.querySelectorAll('*')].flatMap(e => [cs(e), cs(e, '::before'), cs(e, '::after')]).map(s => (s.maskImage || '') + ' ' + (s.webkitMaskImage || ''));
  out.edge_masks = edges.filter(m => m.includes('edge.webp')).length;
  const art = [...band.querySelectorAll('img')].filter(i => /scissors/.test(i.getAttribute('src') || '') && !i.closest('[data-paper]'))[0];
  out.band_art = art ? {shown: shown(art), angle: angle(art)} : null;
  out.gap_above = hero ? box(band).y - (box(hero).y + box(hero).h) : null;
  out.gap_below = words ? box(words).y - (box(band).y + box(band).h) : null;
  const afters = %(afters)s, titles = %(titles)s;
  out.panels = titles.map((t, i) => {
    const sheetEls = [...band.querySelectorAll('[data-paper]')].filter(e => SQ(T(e)).includes(SQ(afters[i])));
    const sheet = sheetEls.filter(e => !sheetEls.some(o => o !== e && e.contains(o)))[0];
    const clipEls = [...band.querySelectorAll('[data-paper]')].filter(e => SQ(T(e)).includes(SQ(t)) && !SQ(T(e)).includes(SQ(afters[i])));
    const clip = clipEls.filter(e => !clipEls.some(o => o !== e && e.contains(o)))[0];
    const meter = [...band.querySelectorAll('*')].filter(e => shown(e) && /^Top 3 keywords: \d of 3 before/.test(T(e)))[i];
    const nums = meter ? [...meter.querySelectorAll('*')].filter(e => /^\d of 3$/.test(T(e))).map(e => cs(e).color) : [];
    const title = clip ? leafWith(clip, t)[0] : null;
    return {sheet: sheet ? box(sheet) : null, clip: clip ? box(clip) : null, meter: meter ? box(meter) : null, nums,
      title: title ? {color: cs(title).color, bg: [bgOf(title), cs(clip).backgroundColor, cs(clip, '::before').backgroundColor]} : null};
  });
}
if (words) {
  const sum = %(summary)s.map(s => leafWith(words, s)[0]);
  out.summary = sum.map(e => e ? cs(e).color : null);
  out.people = %(links)s.map(l => { const a = [...words.querySelectorAll('a[href]')].find(x => T(x) === l); if (!a) return null;
    let blk = a; while (blk.parentElement && blk.parentElement !== words && !leafWith(blk, 'Before').length) blk = blk.parentElement;
    const pages = [...blk.querySelectorAll('[data-paper]')].filter(shown).map(box);
    return {...box(blk), pages}; });
}
out.h2 = [band, words].map(s => s && s.querySelector('h2')).filter(Boolean).map(h => ({size: px(cs(h).fontSize), weight: cs(h).fontWeight}));
// AC-106: "Examples" reaches #demo, which starts below the header
const t = doc.getElementById('demo');
out.landing = t && hd ? (t.scrollIntoView(), t.getBoundingClientRect().top - hd.getBoundingClientRect().bottom) : null;   // scrollIntoView honours scroll-margin, as a link does
win.scrollTo(0, 0);
return out;
"""


def look_js():
    s = FIX["samples"]
    return LOOK_JS % {"band": json.dumps(FIX["headings"][0]), "words": json.dumps(FIX["headings"][1]),
                      "afters": json.dumps([x["after"] for x in s]), "titles": json.dumps([x["clipParts"][1] for x in s]),
                      "summary": json.dumps(FIX["keywords"]["summary"]), "links": json.dumps([p["link"] for p in FIX["keywords"]["people"]])}


def rgb(h):
    r, g, b = C.hex_rgb(h)
    return f"rgb({r}, {g}, {b})"


class TheLook(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        cls.page = H.home_html()
        cls.sheets = H.linked_sheets(cls.page)
        with H.Site(cls.page) as site:
            cls.L = {w: v for (w, _), v in H.measure(site, LIGHT, look_js()).items()}
            cls.Dk = {w: v for (w, _), v in H.measure(site, DARK, look_js(), scheme="dark").items()}

    def test_ac101_the_keywords_slab_and_the_band(self):
        for w, m in self.L.items():
            with self.subTest(w=w):
                s = m["words"]
                self.assertIsNotNone(s, "the keywords slab")
                self.assertIsNotNone(m["band"], "the band")
                if w >= 1280:
                    self.assertLessEqual(s["w"], 1240.5)
                    self.assertAlmostEqual(s["x"] + s["w"] / 2, w / 2, delta=1)
                self.assertEqual(s["bg"], "rgb(255, 255, 255)")
                self.assertEqual(s["r"], "32px")
                self.assertAlmostEqual(s["pt"], min(max(40, 0.06 * w), 88), delta=0.6)
                self.assertAlmostEqual(s["pb"], min(max(40, 0.06 * w), 88), delta=0.6)
                self.assertAlmostEqual(s["pl"], min(max(20, 0.05 * w), 72), delta=0.6)
                self.assertAlmostEqual(s["pr"], min(max(20, 0.05 * w), 72), delta=0.6)
                self.assertAlmostEqual(m["band"]["x"], 0, delta=0.5)
                self.assertAlmostEqual(m["band"]["w"], w, delta=0.5)

    def test_ac102_the_band_and_keywords_literals_are_tokens(self):
        # every colour outside the token blocks is slice 9's case (CHECK 2, AC-102), still locked and run
        values = " ".join(v.upper() for _, css in self.sheets for v in C.tokens(css).values())
        for lit in ("#E2E0DA", "#FCFAF5", "#B8C2D2", "#C4B2EC", "#1B7369"):   # photocopy sheet, paper, on-band-2, lilac, D2's teal
            self.assertIn(lit, values, f"v2's {lit} is a token")

    def test_ac106_examples_lands_below_the_header(self):
        for w, m in self.L.items():
            with self.subTest(w=w):
                self.assertIsNotNone(m["landing"], "#demo exists")
                self.assertGreaterEqual(m["landing"], -0.5)

    def test_ac118_the_navy_band(self):
        for w, m in self.L.items():
            with self.subTest(w=w):
                self.assertEqual(m["band"]["bg"], rgb("#13233A"))
                self.assertAlmostEqual(m["gap_above"], 64, delta=0.6)
                self.assertAlmostEqual(m["gap_below"], 64, delta=0.6)
                self.assertGreaterEqual(m["edge_masks"], 2, "torn top and bottom edges from edge.webp")
                self.assertIsNotNone(m["band_art"])
                self.assertEqual(m["band_art"]["shown"], w >= 700)
                if w >= 700:
                    self.assertAlmostEqual(m["band_art"]["angle"], -8, delta=0.2)

    def test_ac122_the_panel_columns(self):
        for w, m in self.L.items():
            for i, p in enumerate(m["panels"]):
                with self.subTest(w=w, panel=i):
                    self.assertIsNotNone(p["sheet"], "the 'after' sheet")
                    self.assertIsNotNone(p["clip"], "the clipping")
                    self.assertIsNotNone(p["meter"], "the meter")
                    if w >= 961:
                        self.assertLessEqual(p["clip"]["x"] + p["clip"]["w"], p["sheet"]["x"] + 0.5, "clipping left, sheet right")
                        self.assertAlmostEqual(p["sheet"]["h"], 700, delta=1)
                    else:
                        self.assertLess(p["sheet"]["y"], p["clip"]["y"], "the meter and the sheet first")
                        self.assertAlmostEqual(p["sheet"]["h"], 560, delta=1)
                    self.assertLess(p["meter"]["y"], p["sheet"]["y"], "the meter above the sheet")

    def test_ac123_teal_words_read(self):
        for w in (390, 1280):
            t = self.L[w]["panels"][1]["title"]
            with self.subTest(w=w):
                self.assertIsNotNone(t, "the teal clipping's title")
                self.assertIn(rgb("#1B7369"), t["bg"], "the paper behind the words (the clipping or its torn ::before)")
                self.assertEqual(t["color"], rgb("#F4F1EA"))

    def test_ac125_ac133_the_counts_colours(self):
        for w in (390, 1280):
            with self.subTest(w=w):
                for p in self.L[w]["panels"]:
                    self.assertEqual(p["nums"], [rgb("#B8C2D2"), rgb("#FF5A47")])
                self.assertEqual(self.L[w]["summary"], [rgb("#5A585E"), rgb("#C2382A")])
                self.assertEqual(self.Dk[w]["summary"], [rgb("#A6A3AC"), rgb("#FF8A79")])

    def test_ac134_the_keyword_columns(self):
        for w, m in self.L.items():
            p = m["people"]
            with self.subTest(w=w):
                self.assertTrue(p and all(p), "each person's block")
                if w >= 901:
                    self.assertTrue(abs(p[0]["y"] - p[1]["y"]) < 1 and abs(p[1]["y"] - p[2]["y"]) < 1 and p[0]["x"] < p[1]["x"] < p[2]["x"])
                else:
                    self.assertTrue(p[0]["y"] < p[1]["y"] < p[2]["y"])
                    for q in p:
                        self.assertEqual(len(q["pages"]), 2)
                        a, b = sorted(q["pages"], key=lambda x: x["x"])
                        self.assertLessEqual(b["x"] + b["w"] - a["x"], 420.5, "the two pages 420 px wide at most")
                        self.assertAlmostEqual(q["pages"][0]["y"], q["pages"][1]["y"], delta=1, msg="side by side")

    def test_ac170_the_band_in_dark(self):
        for w in DARK:
            with self.subTest(w=w):
                self.assertEqual(self.Dk[w]["band"]["bg"], rgb("#1A2C49"))
                self.assertEqual(self.Dk[w]["words"]["bg"], rgb("#14223A"), "the keywords slab")

    def test_ac176_v2s_h2(self):
        for w, m in self.L.items():
            with self.subTest(w=w):
                self.assertEqual(len(m["h2"]), 2, "the band's and the keywords' headings are h2")
                for h in m["h2"]:
                    self.assertAlmostEqual(h["size"], min(max(33.6, 0.044 * w), 62.4), delta=0.6)
                    self.assertEqual(h["weight"], "850")


if __name__ == "__main__":
    unittest.main()
