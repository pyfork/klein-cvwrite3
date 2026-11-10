"""Locked check, redesign S-010. CHECK 1: "See it work." and the keywords as their words and links (scripts off).

AC-100 (the order: the hero, then the band, then the keywords, each heading v2's), AC-104 (the header's "Examples"
reaches `#demo`), AC-123 to AC-125 and AC-131 (the three samples' panels with scripts off), AC-132 (the note),
AC-133 and AC-134 (the keywords), AC-135 ("See {name}'s CV" is a plain link to that sample's panel), AC-136 (the
stickers' places are in the HTML; an inline style sets custom properties only, the tech review of #153, row 3) and
AC-161 (where the new links go). The words are v2's (acceptance/fixtures/s010_v2_text.json).
Fails before the work: the home ends after the hero, so it has no band, no keywords and no `#demo`.
senior-lead-Opus5.5-agent, 2026-11-10 (cut from the top half's draft on branch draft-redesign-top-half, 3411036)
"""
import json
import unittest

import redesign_s009_common as H

FIX = json.loads((H.ROOT / "acceptance" / "fixtures" / "s010_v2_text.json").read_text(encoding="utf-8"))
HEADS = H.FIX["headings"] + FIX["headings"]   # the hero's heading (slice 9), then the band's and the keywords'
LATER_IDS = ("how", "apps", "price", "privacy", "faq")   # sections slice 11 builds; links to them wait for it

PAGE_JS = r"""
const out = {};
out.heads = heads(doc).map(T);
out.hrefs = [...doc.querySelectorAll('a[href]')].map(a => a.getAttribute('href'));
out.ids = [...doc.querySelectorAll('[id]')].map(e => e.id);
const hd = header(doc);
out.examples = hd ? ([...hd.querySelectorAll('a[href]')].find(a => T(a) === 'Examples') || {getAttribute: () => null}).getAttribute('href') : null;
const demo = doc.getElementById('demo');
out.demo_heading = demo ? T(demo.querySelector('h2')) : null;
// the tech review of #153, row 3: inline styles escape the stylesheet checks, so any here may set custom properties only
out.styles = ['demo', 'words'].map(id => doc.getElementById(id)).filter(Boolean).flatMap(r => [r, ...r.querySelectorAll('[style]')]).map(e => e.getAttribute('style')).filter(Boolean);
const band = section(doc, %(band)s);
out.band = !!band;
if (band) {
  out.tablist_shown = [...band.querySelectorAll('[role="tablist"], [role="tab"]')].some(shown);
  out.slider_shown = [...band.querySelectorAll('[role="slider"]')].some(shown);
  out.drag_shown = shownText(band, 'Drag');
  out.tags_shown = [...band.querySelectorAll('button')].filter(b => ['Before', 'After'].includes(T(b))).some(shown);
  out.note = (() => { const n = leafWith(band, %(note)s).filter(shown)[0]; if (!n) return null;
    const panels = [...band.querySelectorAll('[id]')].filter(e => e !== band);
    return {italic: cs(n).fontStyle === 'italic', last: panels.every(p => p.contains(n) || !!(p.compareDocumentPosition(n) & 4))}; })();
}
const words = section(doc, %(words)s);
out.words = !!words;
if (words) {
  out.words_text = T(words);
  out.summary_shown = %(summary)s.map(s => shownText(words, s));
  out.people = %(people)s.map(p => {
    const link = [...words.querySelectorAll('a[href]')].find(a => T(a) === p.link);
    let blk = link; while (blk && blk !== words && !(T(blk).includes(p.head.split(' · ')[0]) && leafWith(blk, 'Before').length && leafWith(blk, 'After').length)) blk = blk.parentElement;
    if (!link || !blk || blk === words) return {found: false};
    const side = el => { for (let n = el; n && n !== blk; n = n.parentElement) { if (leafWith(n, 'Before').length && !leafWith(n, 'After').length) return 'before'; if (leafWith(n, 'After').length && !leafWith(n, 'Before').length) return 'after'; } return null; };
    const kws = p.after.stickers.map(s => s[0]);
    const stickers = [...blk.querySelectorAll('*')].filter(e => kws.includes(T(e)) && shown(e) && ![...e.children].some(c => kws.includes(T(c))));
    const bands = leafWith(blk, 'First 50 words').filter(shown).map(l => l.parentElement);
    const where = e => { const r = e.getBoundingClientRect(); const b = bands.find(x => x.contains(e) || (side(x) === side(e)));
      if (!b) return 'none'; const z = b.getBoundingClientRect(); const cy = r.top + r.height / 2; return cy >= z.top && cy <= z.bottom ? 'zone' : (cy > z.bottom ? 'out' : 'above'); };
    const rects = stickers.map(e => e.getBoundingClientRect());
    let overlap = 0; for (let i = 0; i < rects.length; i++) for (let j = i + 1; j < rects.length; j++) { const a = rects[i], b = rects[j];
      if (Math.min(a.right, b.right) - Math.max(a.left, b.left) > 1 && Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 1) overlap++; }
    return {found: true, text: T(blk), href: link.getAttribute('href'), firsts: bands.length,
      before: stickers.filter(e => side(e) === 'before').map(e => [T(e), where(e)]).sort(),
      after: stickers.filter(e => side(e) === 'after').map(e => [T(e), where(e)]).sort(), overlap};
  });
}
out.panels = (out.people || []).map(p => { if (!p.href || !p.href.startsWith('#')) return null;
  const el = doc.getElementById(p.href.slice(1)); if (!el) return null;
  const after = [...el.querySelectorAll('*')].filter(e => SQ(T(e)).includes(SQ(%(afters)s[(out.people || []).indexOf(p)])));
  const deepest = after.filter(e => !after.some(o => o !== e && e.contains(o)))[0];
  let whole = false;
  if (deepest && shown(deepest)) { deepest.scrollIntoView({block: 'center'}); const r = deepest.getBoundingClientRect();   // clear of the sticky header
    const pts = [[.1, .3], [.5, .3], [.9, .3], [.1, .6], [.9, .6], [.5, .8]].map(([x, y]) => [r.left + r.width * x, r.top + r.height * y]);
    whole = pts.filter(([x, y]) => y > 0 && y < H).every(([x, y]) => { const hit = doc.elementFromPoint(x, y); return hit && (deepest.contains(hit) || hit === deepest); }); }
  return {inBand: !!band && band.contains(el), text: T(el), after_whole: whole, metres: (() => { const re = /^Top 3 keywords: \d of 3 before, \d of 3 after, from word \d+$/; const m = [...el.querySelectorAll('*')].filter(e => shown(e) && re.test(T(e)));
    return m.filter(e => !m.some(o => o !== e && e.contains(o))).map(T); })()}; });
out.hrefs = [...doc.querySelectorAll('a[href]')].map(a => a.getAttribute('href'));
out.ids = [...doc.querySelectorAll('[id]')].map(e => e.id);
out.imgs = [...doc.querySelectorAll('img')].map(i => ({src: i.getAttribute('src'), w: i.getAttribute('width'), h: i.getAttribute('height'), alt: i.getAttribute('alt')}));
return out;
"""


def page_js():
    f = FIX
    return PAGE_JS % {
        "band": json.dumps(f["headings"][0]), "note": json.dumps(f["band_note"]), "words": json.dumps(f["headings"][1]),
        "summary": json.dumps(f["keywords"]["summary"]), "people": json.dumps(f["keywords"]["people"]),
        "afters": json.dumps([s["after"] for s in f["samples"]]),
    }


class ThePage(unittest.TestCase):
    """The band's and the keywords' words, links and states, read in Chrome with scripts off, at 1280 and at 390."""

    @classmethod
    def setUpClass(cls):
        cls.page = H.home_html()
        with H.Site(cls.page) as site:
            got = H.measure(site, [(1280, 900), (390, 844)], page_js())
        cls.wide, cls.narrow = got[(1280, 900)], got[(390, 844)]

    def runs(self):
        return (("1280", self.wide), ("390", self.narrow))

    def test_ac100_hero_then_band_then_keywords(self):
        for w, m in self.runs():
            with self.subTest(w=w):
                self.assertEqual(m["heads"][:3], HEADS)

    def test_ac104_examples_reaches_the_band(self):
        self.assertEqual(self.wide["examples"], "#demo")
        self.assertEqual(self.wide["demo_heading"], FIX["headings"][0], "#demo is the band")

    def test_ac131_three_panels_one_after_another(self):
        for w, m in self.runs():
            with self.subTest(w=w):
                self.assertTrue(m["band"])
                self.assertFalse(m["tablist_shown"], "no tab list with scripts off")
                self.assertFalse(m["slider_shown"], "no grip")
                self.assertFalse(m["drag_shown"], "no 'Drag' label")
                self.assertFalse(m["tags_shown"], "no Before or After tags")
                self.assertEqual(len([p for p in m["panels"] if p and p["inBand"]]), 3)

    def test_ac123_ac124_ac125_each_panel_holds_its_sample(self):
        for w, m in self.runs():
            for s, p in zip(FIX["samples"], m["panels"]):
                with self.subTest(w=w, sample=s["tabTitle"]):
                    self.assertIsNotNone(p, "the sample's panel")
                    text = H.squash(p["text"])
                    for piece in [s["tabTitle"], s["tabLine"], *s["clipParts"], "What we found in the ad", "Top 3 keywords",
                                  *[x for pq in s["problems"] for x in pq], *s["chips"], s["after"], s["before"]]:
                        self.assertIn(H.squash(piece), text, piece[:60])
                    self.assertEqual(p["metres"], [s["meter"]])
                    self.assertTrue(p["after_whole"], "the 'after' sheet shows whole")

    def test_ac132_the_note_ends_the_band(self):
        self.assertIsNotNone(self.wide["note"], "the made-up note is shown")
        self.assertTrue(self.wide["note"]["italic"])
        self.assertTrue(self.wide["note"]["last"], "it comes after the panels")

    def test_ac133_ac134_the_keywords(self):
        kw = FIX["keywords"]
        for w, m in self.runs():
            with self.subTest(w=w):
                self.assertTrue(m["words"])
                self.assertIn(kw["lede"], m["words_text"])
                self.assertEqual(m["summary_shown"], [True, True])
            for want, got in zip(kw["people"], m["people"]):
                with self.subTest(w=w, person=want["head"]):
                    self.assertTrue(got["found"], "the person's block, with its link")
                    for piece in (want["head"], want["before"]["note"], want["after"]["note"]):
                        self.assertIn(H.squash(piece), H.squash(got["text"]))
                    self.assertEqual(got["firsts"], 2, "a 'First 50 words' band on each page")
                    self.assertEqual(got["before"], sorted([k, z] for k, z, _ in want["before"]["stickers"]))
                    self.assertEqual(got["after"], sorted([k, z] for k, z, _ in want["after"]["stickers"]))
                    self.assertEqual(got["overlap"], 0, "a sticker never covers another")

    def test_ac135_see_cv_links_to_that_panel(self):
        for i, (p, panel) in enumerate(zip(self.wide["people"], self.wide["panels"])):
            with self.subTest(person=i):
                self.assertTrue(p["href"].startswith("#"), "a plain in-page link with scripts off")
                self.assertIsNotNone(panel, "the link's target exists")
                self.assertIn(H.squash(FIX["samples"][i]["tabTitle"]), H.squash(panel["text"]))
                for j, other in enumerate(FIX["samples"]):
                    if j != i:
                        self.assertNotIn(H.squash(other["clipParts"][0]), H.squash(panel["text"]), "that sample's panel only")

    def test_ac136_sticker_places_are_in_the_html(self):
        # measured with scripts off: the places come from the HTML and the stylesheet alone
        for got in self.wide["people"]:
            self.assertTrue(got["found"])
            self.assertTrue(all(z in ("zone", "out") for _, z in got["before"] + got["after"]))

    def test_ac102_inline_styles_set_custom_properties_only(self):
        # a colour, size or font in a style="" attribute would escape slice 9's AC-102, AC-163 and slice 1's AC-21 cases
        for st in self.wide["styles"]:
            for decl in filter(None, (d.strip() for d in st.split(";"))):
                with self.subTest(decl=decl[:60]):
                    self.assertTrue(decl.startswith("--"), "a custom property (a sticker's place or tilt), nothing else")
                    self.assertNotRegex(decl, r"#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(", "no colour")

    def test_ac161_where_links_go(self):
        ids = set(self.wide["ids"])
        self.assertIn("demo", ids)
        for href in self.wide["hrefs"]:
            with self.subTest(href=href):
                if href.startswith("#"):
                    if href[1:] not in LATER_IDS:
                        self.assertIn(href[1:], ids, "an in-page link has its target")
                else:
                    self.assertIn(href, ("/", "/signin", "/privacy", "/terms"), "nothing else leaves the page")


if __name__ == "__main__":
    unittest.main()
