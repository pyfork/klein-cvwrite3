"""Locked check, redesign S-010. CHECK 3: "See it work." and the keywords at every width, light and dark, and when things fail.

AC-122 and AC-131 (each sample's "after" sheet shows whole, inside the window, with no grip), AC-134 (each sticker
inside its page, none covering another), AC-171 (every width from 320 to 1440 in steps of 40 px or less, light and dark,
with every image blocked and with `/fonts` failing: the band and the keywords show whole, nothing in them overlaps,
clips or leaves the window) and AC-172 (short screens: the slider shows its "after" sheet with no grip, and no section
is sized to the window). The whole page's overflow, overlap and sideways-scroll cases stay slice 9's CHECK 3, still
locked and run on every PR. Scripts off (sandboxed iframes), which is all slice 10 builds.
Fails before the work: the home ends after the hero, so it has no band and no keywords.
senior-lead-Opus5.5-agent, 2026-11-10
"""
import json
import unittest

import redesign_s009_common as H

FIX = json.loads((H.ROOT / "acceptance" / "fixtures" / "s010_v2_text.json").read_text(encoding="utf-8"))

WIDTH_JS = r"""
const out = {};
const band = section(doc, %(band)s), words = section(doc, %(words)s);
out.band = !!band && shown(band); out.words = !!words && shown(words);
const inWin = r => r.left >= -0.5 && r.right <= W + 0.5;
const afters = %(afters)s;
out.sheets = band ? afters.map(a => {
  const els = [...band.querySelectorAll('[data-paper]')].filter(e => SQ(T(e)).includes(SQ(a)));
  const s = els.filter(e => !els.some(o => o !== e && e.contains(o)))[0];
  if (!s || !shown(s)) return null;
  s.scrollIntoView({block: 'center'}); const r = s.getBoundingClientRect();
  const pts = [[.1, .3], [.5, .3], [.9, .3], [.1, .6], [.9, .6], [.5, .8]].map(([x, y]) => [r.left + r.width * x, r.top + r.height * y]);
  const whole = pts.filter(([x, y]) => y > 0 && y < H).every(([x, y]) => { const hit = doc.elementFromPoint(x, y); return !!hit && (s.contains(hit) || hit === s); });
  return {whole, inside: inWin(r), h: Math.round(r.height)}; }) : [];
win.scrollTo(0, 0);
out.grips = band ? [...band.querySelectorAll('[role="slider"]')].filter(shown).length : null;
// every text box in the band and the keywords: outside the window, or (outside the paper) clipped or overlapping another
const items = [];
for (const root of [band, words].filter(Boolean)) for (const e of root.querySelectorAll('*')) { if (!ownText(e) || !shown(e)) continue;
  const r = e.getBoundingClientRect(); if (r.width <= 1 || r.height <= 1) continue; items.push({e, r, t: T(e).slice(0, 40), paper: paper(e)}); }
out.outside = items.filter(({r}) => !inWin(r)).map(i => i.t);
out.clipped = items.filter(({e, paper}) => !paper && e.scrollWidth > e.clientWidth + 1 && /hidden|clip|auto|scroll/.test(cs(e).overflowX)).map(i => i.t);
const blockOf = e => { for (let n = e; n; n = n.parentElement) if (!/^inline/.test(cs(n).display)) return n; return e; };
const plain = items.filter(i => !i.paper);
out.overlaps = [];
for (let i = 0; i < plain.length; i++) for (let j = i + 1; j < plain.length; j++) { const a = plain[i], b = plain[j];
  if (a.e.contains(b.e) || b.e.contains(a.e) || blockOf(a.e) === blockOf(b.e)) continue;
  if (Math.min(a.r.right, b.r.right) - Math.max(a.r.left, b.r.left) > 2 && Math.min(a.r.bottom, b.r.bottom) - Math.max(a.r.top, b.r.top) > 2) out.overlaps.push([a.t, b.t]); }
// the stickers: each inside its page, none covering another on the same page
const kws = [...new Set(%(kws)s)];
out.stickers = [];
if (words) for (const pg of words.querySelectorAll('[data-paper]')) {
  const pr = pg.getBoundingClientRect();
  const st = [...pg.querySelectorAll('*')].filter(e => kws.includes(T(e)) && shown(e) && ![...e.children].some(c => kws.includes(T(c)))).map(e => [T(e), e.getBoundingClientRect()]);
  for (let i = 0; i < st.length; i++) { const [k, r] = st[i];
    if (r.left < pr.left - 0.5 || r.right > pr.right + 0.5 || r.top < pr.top - 0.5 || r.bottom > pr.bottom + 0.5) out.stickers.push(['outside', k]);
    for (let j = i + 1; j < st.length; j++) { const q = st[j][1];
      if (Math.min(r.right, q.right) - Math.max(r.left, q.left) > 1 && Math.min(r.bottom, q.bottom) - Math.max(r.top, q.top) > 1) out.stickers.push(['covers', k, st[j][0]]); } } }
out.links = words ? [...words.querySelectorAll('a[href]')].filter(shown).map(T) : [];
out.sections = [band, words].filter(Boolean).map(s => Math.round(s.getBoundingClientRect().height));
return out;
"""

SIZES = [(w, 900) for w in H.WIDTHS]


def width_js():
    kws = [k for p in FIX["keywords"]["people"] for side in ("before", "after") for k, _, _ in p[side]["stickers"]]
    return WIDTH_JS % {"band": json.dumps(FIX["headings"][0]), "words": json.dumps(FIX["headings"][1]),
                       "afters": json.dumps([s["after"] for s in FIX["samples"]]), "kws": json.dumps(kws)}


class EveryWidth(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        page = H.home_html()
        js = width_js()
        cls.runs = {}
        with H.Site(page) as site:
            cls.runs["light"] = H.measure(site, SIZES, js)
            cls.runs["dark"] = H.measure(site, SIZES, js, scheme="dark")
            cls.runs["short"] = H.measure(site, [(320, 568), (667, 375), (667, 900)], js)
        with H.Site(page, block="fonts") as site:
            cls.runs["no fonts"] = H.measure(site, SIZES, js)
        with H.Site(page, block="art") as site:
            cls.runs["no images"] = H.measure(site, SIZES, js)

    def each(self, kinds=("light", "dark", "no fonts", "no images")):
        for k in kinds:
            for (w, h), m in self.runs[k].items():
                yield f"{k} {w}x{h}", m

    def test_ac171_the_band_and_the_keywords_show_whole(self):
        for name, m in self.each():
            with self.subTest(run=name):
                self.assertTrue(m["band"], "the band")
                self.assertTrue(m["words"], "the keywords")
                self.assertEqual(m["outside"], [], "text outside the window")
                self.assertEqual(m["clipped"], [], "clipped text")
                self.assertEqual(m["overlaps"], [], "overlapping text")
                self.assertEqual(len(m["links"]), 3, "the three 'See {name}'s CV' links")

    def test_ac122_ac131_each_after_sheet_whole_with_no_grip(self):
        for name, m in self.each(("light", "dark", "no fonts", "no images", "short")):
            with self.subTest(run=name):
                self.assertEqual(m["grips"], 0, "no grip with scripts off")
                self.assertEqual(len(m["sheets"]), 3)
                for i, s in enumerate(m["sheets"]):
                    self.assertIsNotNone(s, f"sample {i}'s 'after' sheet is shown")
                    self.assertTrue(s["whole"], f"sample {i}'s 'after' sheet is not covered")
                    self.assertTrue(s["inside"], f"sample {i}'s 'after' sheet is inside the window")

    def test_ac134_stickers_inside_their_page_none_covering_another(self):
        for name, m in self.each():
            with self.subTest(run=name):
                self.assertEqual(m["stickers"], [])

    def test_ac172_no_section_sized_to_the_window(self):
        short = self.runs["short"]
        for (w, h), tall in (((320, 568), self.runs["light"][(320, 900)]), ((667, 375), short[(667, 900)])):
            with self.subTest(size=(w, h)):
                self.assertTrue(short[(w, h)]["sections"], "the band and the keywords")
                self.assertEqual(short[(w, h)]["sections"], tall["sections"], "the same heights in a 900 px tall window")

if __name__ == "__main__":
    unittest.main()
