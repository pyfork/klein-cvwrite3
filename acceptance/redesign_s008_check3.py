"""Locked check, redesign S-008. CHECK 3: the top half at every width, light and dark, and when things fail.

AC-103 (no sideways scroll, no overflow hidden on html or body), AC-105 (the header one line at 320), AC-162 (every image
blocked: words, controls and sections still show, nothing overlaps), AC-171 (every width from 320 to 1440 in steps of
40 px or less, light and dark, with real content, and with `/fonts` failing: nothing overlaps, clips or scrolls
sideways), AC-172 (short screens: the header one line, "Get started" always on screen, no section sized to the window)
and AC-173 (the first screen at 390). Scripts off (sandboxed iframes), which is all slice 8 builds.
Fails before the work: there is no `home` setting, so there is no home to measure.
senior-lead-Opus5.5-agent, 2026-11-07
"""
import unittest

import redesign_s008_common as H

WIDTH_JS = r"""
const out = {W, docW: doc.documentElement.scrollWidth, bodyW: doc.body.scrollWidth};
out.hide = ['html', 'body'].map(t => { const s = cs(t === 'html' ? doc.documentElement : doc.body); return [s.overflowX, s.overflow]; });
const hd = header(doc);
out.header_lines = hd ? (() => { const ms = [...hd.querySelectorAll('a[href]')].filter(shown).map(a => a.getBoundingClientRect()); return ms.length ? Math.max(...ms.map(r => r.top)) - Math.min(...ms.map(r => r.top)) : 99; })() : 99;
// every shown text box outside the paper: clipped, or overlapping another text box that is not its own
const items = [];
for (const e of doc.querySelectorAll('body *')) { if (!ownText(e) || !shown(e)) continue;
  const r = e.getBoundingClientRect(); if (r.width <= 1 || r.height <= 1) continue;
  items.push({e, r, t: T(e).slice(0, 40), paper: paper(e)}); }
out.clipped = items.filter(({e}) => !e.closest('[data-paper]') && (e.scrollWidth > e.clientWidth + 1) && /hidden|clip|auto|scroll/.test(cs(e).overflowX)).map(i => i.t);
out.outside = items.filter(({r}) => (r.left < -0.5 && r.right > 0) || r.right > W + 0.5).map(i => i.t);   // a skip link parked wholly off-screen is not 'outside'
out.overlaps = [];
// runs of text inside one block (spans on the lines of one heading) share its leading: compare blocks, not spans
const blockOf = e => { for (let n = e; n; n = n.parentElement) if (!/^inline/.test(cs(n).display)) return n; return e; };
const plain = items.filter(i => !i.paper);
for (let i = 0; i < plain.length; i++) for (let j = i + 1; j < plain.length; j++) { const a = plain[i], b = plain[j];
  if (a.e.contains(b.e) || b.e.contains(a.e) || blockOf(a.e) === blockOf(b.e)) continue;
  const x = Math.min(a.r.right, b.r.right) - Math.max(a.r.left, b.r.left), y = Math.min(a.r.bottom, b.r.bottom) - Math.max(a.r.top, b.r.top);
  if (x > 2 && y > 2) out.overlaps.push([a.t, b.t]); }
const ctr = focusables(doc).filter(e => !paper(e)).map(e => [T(e).slice(0, 30), e.getBoundingClientRect()]);
for (let i = 0; i < ctr.length; i++) for (let j = i + 1; j < ctr.length; j++) { const a = ctr[i][1], b = ctr[j][1];
  if (Math.min(a.right, b.right) - Math.max(a.left, b.left) > 1 && Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 1) out.overlaps.push([ctr[i][0], ctr[j][0]]); }
out.sideways = [...doc.querySelectorAll('body *')].filter(e => shown(e) && !paper(e) && /auto|scroll/.test(cs(e).overflowX) && e.scrollWidth > e.clientWidth + 1).map(e => e.className || e.tagName);
out.heads = heads(doc).map(T).slice(0, 3);
out.sections = [...doc.querySelectorAll('main > section, main section')].filter(shown).map(s => Math.round(s.getBoundingClientRect().height));
out.controls = focusables(doc).filter(e => !paper(e)).map(e => T(e).slice(0, 30));
// short screens and the first screen
const start = hd ? [...hd.querySelectorAll('a[href]')].find(a => T(a) === 'Get started') : null;
const docH = doc.documentElement.scrollHeight;
out.start_seen = [0, 0.25, 0.5, 0.75, 1].map(f => { win.scrollTo(0, f * (docH - H)); const r = start && start.getBoundingClientRect(); return !!r && shown(start) && r.top >= -0.5 && r.bottom <= H + 0.5; });
win.scrollTo(0, 0);
const brand = hd && hd.querySelector('a[href]'), h1 = doc.querySelector('h1'), lede = h1 && h1.parentElement.querySelector('p');
out.first = {brand: !!brand && brand.getBoundingClientRect().bottom <= H, start: !!start && start.getBoundingClientRect().bottom <= H,
  h1: !!h1 && h1.getBoundingClientRect().bottom <= H, lede: !!lede && lede.getBoundingClientRect().top < H};
return out;
"""

SIZES = [(w, 900) for w in H.WIDTHS]


class EveryWidth(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        cls.page = H.home_html()
        cls.runs = {}
        with H.Site(cls.page) as site:
            cls.runs["light"] = H.measure(site, SIZES, WIDTH_JS)
            cls.runs["dark"] = H.measure(site, SIZES, WIDTH_JS, scheme="dark")
            cls.runs["short"] = H.measure(site, [(320, 568), (667, 375), (390, 844)], WIDTH_JS)
        with H.Site(cls.page, block="fonts") as site:
            cls.runs["no fonts"] = H.measure(site, SIZES, WIDTH_JS)
        with H.Site(cls.page, block="art") as site:
            cls.runs["no images"] = H.measure(site, SIZES, WIDTH_JS)

    def each(self, kinds=("light", "dark", "no fonts", "no images")):
        for k in kinds:
            for (w, h), m in self.runs[k].items():
                yield f"{k} {w}x{h}", w, m

    def test_ac103_no_sideways_scroll(self):
        for name, w, m in self.each():
            with self.subTest(run=name):
                self.assertEqual(m["docW"], w)
                self.assertEqual(m["bodyW"], w)
                for overflow_x, overflow in m["hide"]:
                    self.assertNotIn(overflow_x, ("hidden", "clip"), "html and body do not hide an overflow")
                    self.assertNotIn(overflow, ("hidden", "clip"))

    def test_ac105_the_header_is_one_line_at_every_width(self):
        for name, w, m in self.each(("light", "dark", "no fonts", "short")):
            with self.subTest(run=name):
                self.assertLessEqual(m["header_lines"], 4)

    def test_ac171_nothing_overlaps_clips_or_scrolls_sideways(self):
        for name, w, m in self.each():
            with self.subTest(run=name):
                self.assertEqual(m["outside"], [], "text outside the window")
                self.assertEqual(m["clipped"], [], "clipped text")
                self.assertEqual(m["overlaps"], [], "overlapping text or controls")
                self.assertEqual(m["sideways"], [], "a part of the page that scrolls sideways")

    def test_ac171_the_longest_title_and_company_are_whole(self):
        # both are in the real samples: "Graphic Designer, Digital and Motion" (the hero) and "ABC Property Rentals"
        page = H.norm(H.home_html())
        self.assertIn("Graphic Designer, Digital and Motion", page)
        self.assertIn("ABC Property Rentals", page)

    def test_ac162_with_every_image_blocked_everything_still_shows(self):
        for (w, h), m in self.runs["no images"].items():
            with self.subTest(w=w):
                self.assertEqual(m["heads"], self.runs["light"][(w, h)]["heads"])
                self.assertEqual(m["controls"], self.runs["light"][(w, h)]["controls"])

    def test_ac172_short_screens(self):
        for size in ((320, 568), (667, 375)):
            m = self.runs["short"][size]
            with self.subTest(size=size):
                self.assertLessEqual(m["header_lines"], 4)
                self.assertEqual(m["start_seen"], [True] * 5, "Get started on screen at every scroll position")
                tall = self.runs["light"][(size[0], 900)]["sections"] if (size[0], 900) in self.runs["light"] else None
                if tall:
                    self.assertEqual(m["sections"], tall, "no section is sized to the window's height")
        self.assertEqual(self.runs["short"][(320, 568)]["sections"], self.runs["light"][(320, 900)]["sections"])

    def test_ac173_the_first_screen_at_390(self):
        self.assertEqual(self.runs["short"][(390, 844)]["first"], {"brand": True, "start": True, "h1": True, "lede": True})


if __name__ == "__main__":
    unittest.main()
