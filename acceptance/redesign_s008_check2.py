"""Locked check, redesign S-008. CHECK 2: the top half's look, measured in Chrome with scripts off, light and dark.

AC-101 (column, slabs, band width), AC-102 (colours are tokens), AC-105 and AC-106 (the header by width, sticky, blurred,
one line, sections land below it), AC-108 (the hero's columns), AC-109 (the heading), AC-118 (the navy band), AC-122
(the panel's columns and the slider's height), AC-123 (teal words), AC-125 and AC-133 (the counts' colours), AC-134
(the keyword columns), AC-163 (text sizes), AC-164 (touch targets), AC-165 (hover), AC-166 (focus rings), AC-170
(dark), AC-174 (gradients and blur), AC-175 (the sticky header) and AC-176 (fonts and heading sizes).
The stylesheets are the ones the home links, whatever their names (the decision on slice 8).
Fails before the work: there is no `home` setting, so there is no home to measure.
senior-lead-Opus5.5-agent, 2026-11-07
"""
import json
import re
import unittest

import redesign_s001_common as C
import redesign_s008_common as H

FIX = H.FIX
LIGHT = [320, 359, 360, 390, 699, 700, 768, 899, 900, 960, 961, 1280, 1440]
DARK = [390, 1280]

LOOK_JS = r"""
const out = {W, docW: doc.documentElement.scrollWidth};
const px = v => parseFloat(v) || 0;
const angle = e => { const m = cs(e).transform; if (!m || m === 'none') return 0; const v = m.match(/-?[\d.e]+/g).map(Number); return Math.round(Math.atan2(v[1], v[0]) * 180 / Math.PI * 10) / 10; };
const hd = header(doc);
out.header = hd ? {pos: cs(hd).position, top: px(cs(hd).top), blur: cs(hd).backdropFilter || cs(hd).webkitBackdropFilter, bg: cs(hd).backgroundColor,
  h: hd.getBoundingClientRect().height, tops: [...hd.querySelectorAll('a[href]')].filter(shown).map(a => Math.round(a.getBoundingClientRect().top + a.getBoundingClientRect().height / 2)),
  links: [...hd.querySelectorAll('a[href]')].filter(shown).length} : null;
const h1 = doc.querySelector('h1'), hero = h1 && h1.closest('section');
const band = section(doc, %(band)s), words = section(doc, %(words)s);
const slab = s => s ? {bg: cs(s).backgroundColor, r: cs(s).borderTopLeftRadius, pt: px(cs(s).paddingTop), pb: px(cs(s).paddingBottom), pl: px(cs(s).paddingLeft), pr: px(cs(s).paddingRight), ...box(s)} : null;
out.hero = slab(hero); out.words = slab(words); out.band = slab(band);
const pic = hero && hero.querySelector('[role="img"]');
out.pic = pic ? box(pic) : null;
const ink = e => { const rg = doc.createRange(); rg.selectNodeContents(e); const rs = [...rg.getClientRects()]; return rs.length ? Math.max(...rs.map(r => r.right)) + win.scrollX : null; };
out.h1 = h1 ? {...box(h1), ink: ink(h1), size: px(cs(h1).fontSize), weight: cs(h1).fontWeight, ls: px(cs(h1).letterSpacing), lh: px(cs(h1).lineHeight), family: cs(h1).fontFamily} : null;
const same = h1 && leafWith(h1, 'the same CV')[0], every = h1 && leafWith(h1, 'every')[0];
out.same = same ? {lines: same.getClientRects().length, color: cs(same).color} : null;
out.every = every ? cs(every).color : null;
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
// AC-163: every shown text outside the paper
out.small = [];
for (const e of doc.querySelectorAll('body *')) { if (!ownText(e) || !shown(e) || paper(e)) continue;
  const r = e.getBoundingClientRect(); if (r.width <= 1 || r.height <= 1) continue;
  const mono = /^"?Geist Mono/.test(cs(e).fontFamily); const s = px(cs(e).fontSize);
  if (s < (mono ? 14 : 16) - 0.01) out.small.push([T(e).slice(0, 40), s, mono]); }
// AC-176: which fonts carry which text
out.fonts = {mono: [], serif_upright: []};
for (const e of doc.querySelectorAll('body *')) { if (!ownText(e) || !shown(e) || paper(e)) continue;
  const f = cs(e).fontFamily;
  if (/^"?Libre Caslon/.test(f) && cs(e).fontStyle !== 'italic') out.fonts.serif_upright.push(T(e).slice(0, 40));
  if (/^"?Geist Mono/.test(f)) out.fonts.mono.push([T(e).slice(0, 40), cs(e).textTransform, px(cs(e).fontSize)]); }
out.h2 = heads(doc).filter(h => h.tagName === 'H2').slice(0, 2).map(h => ({size: px(cs(h).fontSize), weight: cs(h).fontWeight}));
// AC-174: gradients only on paper, blur only on the header
out.hover_on_home = %(hovers)s.filter(p => { try { return !!doc.querySelector(p.replace(/:hover/g, '')); } catch (e) { return true; } });
out.gradients = []; out.blurs = [];
for (const e of doc.querySelectorAll('body, body *')) { for (const p of [null, '::before', '::after']) { const s = cs(e, p);
  if (/gradient/.test(s.backgroundImage) && !paper(e)) out.gradients.push((e.className || e.tagName) + (p || ''));
  const bf = s.backdropFilter || s.webkitBackdropFilter; if (bf && bf !== 'none' && e !== hd) out.blurs.push((e.className || e.tagName) + (p || '')); } }
// AC-164: controls, their 44 px hit squares and their spacing
out.controls = focusables(doc).filter(e => !paper(e)).map(e => { e.focus(); e.scrollIntoView({block: 'center'});
  const r = e.getBoundingClientRect(), cx = r.left + r.width / 2, cy = r.top + r.height / 2;
  const pts = [[0, 0], [-21, 0], [21, 0], [0, -21], [0, 21]];   // 44 px across and 44 px down through the centre
  const miss = pts.filter(([dx, dy]) => { const h = doc.elementFromPoint(cx + dx, cy + dy); return !(h && (h === e || e.contains(h))); }).length;
  const o = {t: T(e).slice(0, 30), miss, x: r.left + win.scrollX, y: r.top + win.scrollY, r: r.right + win.scrollX, b: r.bottom + win.scrollY, h: r.height};
  e.blur(); return o; });
win.scrollTo(0, 0);
// AC-166: focus rings
out.rings = focusables(doc).filter(e => !paper(e)).map(e => { e.focus(); const s = cs(e);
  return {t: T(e).slice(0, 30), style: s.outlineStyle, width: px(s.outlineWidth), color: s.outlineColor, fill: bgOf(e), under: bgOf(e.parentElement)}; });
doc.activeElement && doc.activeElement.blur && doc.activeElement.blur();
// AC-106: a section reached by a link starts below the header
out.landing = ['main', 'demo'].map(id => { const t = doc.getElementById(id); if (!t || !hd) return null; win.location.hash = '#' + id;
  t.scrollIntoView(); return t.getBoundingClientRect().top - hd.getBoundingClientRect().bottom; });   // scrollIntoView honours scroll-margin, as a link does
win.scrollTo(0, 0);
// AC-170: the paper keeps its colours; every text pair outside the paper reads
out.paper = [...doc.querySelectorAll('[data-paper]')].filter(shown).slice(0, 40).map(e => [cs(e).backgroundColor, cs(e).color]);
out.low = []; for (const e of doc.querySelectorAll('body *')) { if (!ownText(e) || !shown(e) || paper(e)) continue;
  const r0 = e.getBoundingClientRect(); if (r0.width <= 1 || r0.height <= 1) continue;
  const big = px(cs(e).fontSize) >= 24 || (px(cs(e).fontSize) >= 18.66 && +cs(e).fontWeight >= 700);
  const r = ratio(cs(e).color, bgOf(e)); if (r < (big ? 3 : 4.5)) out.low.push([T(e).slice(0, 40), cs(e).color, bgOf(e), Math.round(r * 100) / 100]); }
out.ground = cs(doc.body).backgroundColor;
return out;
"""


def hover_parts(sheets):
    return sorted({part.strip() for _, css in sheets for _, sel, body in C.rules(css) if body is not None
                   for part in sel.split(",") if ":hover" in part})


def look_js(sheets):
    s = FIX["samples"]
    return LOOK_JS % {"hovers": json.dumps(hover_parts(sheets)),"band": json.dumps(FIX["headings"][1]), "words": json.dumps(FIX["headings"][2]),
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
            cls.L = {w: v for (w, _), v in H.measure(site, LIGHT, look_js(cls.sheets)).items()}
            cls.Dk = {w: v for (w, _), v in H.measure(site, DARK, look_js(cls.sheets), scheme="dark").items()}

    # ---------------------------------------------------------------------------------------------- the frame
    def test_ac101_column_slabs_and_band(self):
        for w in (1280, 1440):
            m = self.L[w]
            with self.subTest(w=w):
                for s in (m["hero"], m["words"]):
                    self.assertLessEqual(s["w"], 1240.5)
                    self.assertAlmostEqual(s["x"] + s["w"] / 2, w / 2, delta=1)
                    self.assertEqual(s["bg"], "rgb(255, 255, 255)")
                    self.assertEqual(s["r"], "32px")
                for s in (m["words"],):   # the hero keeps v2's own padding (`.hero`), the other slabs v2's `.slab`
                    self.assertAlmostEqual(s["pt"], min(max(40, 0.06 * w), 88), delta=0.6)
                    self.assertAlmostEqual(s["pb"], min(max(40, 0.06 * w), 88), delta=0.6)
                    self.assertAlmostEqual(s["pl"], min(max(20, 0.05 * w), 72), delta=0.6)
                    self.assertAlmostEqual(s["pr"], min(max(20, 0.05 * w), 72), delta=0.6)
                self.assertAlmostEqual(m["band"]["x"], 0, delta=0.5)
                self.assertAlmostEqual(m["band"]["w"], w, delta=0.5)

    def test_ac102_colour_literals_are_tokens(self):
        colour = re.compile(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(")
        for path, css in self.sheets:
            for chain, sel, body in C.rules(css):
                if body is None or sel == "@font-face" or re.fullmatch(r":root(\s*,\s*:host)?", sel):
                    continue
                for prop, val in C.decls(body):
                    if prop.startswith("--"):
                        continue
                    with self.subTest(sheet=path, rule=sel[:60], prop=prop):
                        self.assertIsNone(colour.search(C.without_urls(val)), f"a colour outside the tokens: {val[:60]}")
        values = " ".join(v.upper() for _, css in self.sheets for v in C.tokens(css).values())
        for lit in ("#E2E0DA", "#FCFAF5", "#F4F1EA", "#B8C2D2", "#C4B2EC", "#1B7369"):
            self.assertIn(lit, values, f"v2's {lit} is a token")

    # ---------------------------------------------------------------------------------------------- the header
    def test_ac105_ac106_ac175_the_header(self):
        for w, m in self.L.items():
            h = m["header"]
            with self.subTest(w=w):
                self.assertEqual(h["pos"], "sticky")
                self.assertIn("blur", h["blur"] or "")
                r, g, b, a = [float(x) for x in re.findall(r"[\d.]+", h["bg"])[:4]] + [1.0] * (4 - len(re.findall(r"[\d.]+", h["bg"])[:4]))
                self.assertEqual((round(r), round(g), round(b)), (242, 241, 237))
                self.assertAlmostEqual(a, 0.82, delta=0.011)
                self.assertLessEqual(h["h"], 68.5)
                self.assertLessEqual(max(h["tops"]) - min(h["tops"]), 4, "one line")
                self.assertEqual(h["links"], 8 if w >= 900 else 2, "brand, six links, Get started; below 900 brand and Get started")
                for gap in m["landing"]:
                    self.assertIsNotNone(gap)
                    self.assertGreaterEqual(gap, -0.5, "a section reached by a link starts below the header")

    # ---------------------------------------------------------------------------------------------- the hero
    def test_ac108_the_hero_columns(self):
        for w, m in self.L.items():
            with self.subTest(w=w):
                if w >= 900:
                    # glyph advance boxes, not ink: 1 px of slack for side bearings and subpixel rounding
                    self.assertLessEqual(m["h1"]["ink"], m["pic"]["x"] + 1, "the words left, the picture right")
                else:
                    self.assertGreaterEqual(m["pic"]["y"], m["h1"]["y"] + m["h1"]["h"], "the picture under the words")

    def test_ac109_the_heading(self):
        for w, m in self.L.items():
            h = m["h1"]
            want = 42 if w < 360 else min(max(48, 0.072 * w), 104)
            with self.subTest(w=w):
                self.assertAlmostEqual(h["size"], want, delta=0.6)
                self.assertEqual(h["weight"], "900")
                self.assertAlmostEqual(h["ls"], -0.05 * h["size"], delta=0.3)
                self.assertAlmostEqual(h["lh"], 0.9 * h["size"], delta=0.6)
                self.assertEqual(m["same"]["lines"], 1, "'the same CV' stays on one line")
                self.assertEqual(m["same"]["color"], rgb("#5A585E"))
                self.assertEqual(m["every"], rgb("#FF5A47"))
        for w in DARK:
            self.assertEqual(self.Dk[w]["same"]["color"], rgb("#A6A3AC"))

    # ---------------------------------------------------------------------------------------------- the band
    def test_ac118_the_navy_band(self):
        for w, m in self.L.items():
            with self.subTest(w=w):
                self.assertEqual(m["band"]["bg"], rgb("#13233A"))
                self.assertAlmostEqual(m["band"]["w"], w, delta=0.5)
                self.assertAlmostEqual(m["gap_above"], 64, delta=0.6)
                self.assertAlmostEqual(m["gap_below"], 64, delta=0.6)
                self.assertGreaterEqual(m["edge_masks"], 2, "torn top and bottom edges from edge.webp")
                self.assertIsNotNone(m["band_art"])
                self.assertEqual(m["band_art"]["shown"], w >= 700)
                if w >= 700:
                    self.assertAlmostEqual(m["band_art"]["angle"], -8, delta=0.2)
        for w in DARK:
            self.assertEqual(self.Dk[w]["band"]["bg"], rgb("#1A2C49"))

    def test_ac122_the_panel_columns(self):
        for w, m in self.L.items():
            for i, p in enumerate(m["panels"]):
                with self.subTest(w=w, panel=i):
                    self.assertIsNotNone(p["sheet"], "the 'after' sheet")
                    self.assertIsNotNone(p["clip"], "the clipping")
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
                self.assertTrue(all(p))
                if w >= 901:
                    self.assertTrue(abs(p[0]["y"] - p[1]["y"]) < 1 and abs(p[1]["y"] - p[2]["y"]) < 1 and p[0]["x"] < p[1]["x"] < p[2]["x"])
                else:
                    self.assertTrue(p[0]["y"] < p[1]["y"] < p[2]["y"])
                    for q in p:
                        self.assertEqual(len(q["pages"]), 2)
                        a, b = sorted(q["pages"], key=lambda x: x["x"])
                        self.assertLessEqual(b["x"] + b["w"] - a["x"], 420.5, "the two pages 420 px wide at most")
                        self.assertAlmostEqual(q["pages"][0]["y"], q["pages"][1]["y"], delta=1, msg="side by side")

    # ---------------------------------------------------------------------------------------------- across the top half
    def test_ac163_text_sizes(self):
        for w, m in {**self.L, **{f"dark{w}": v for w, v in self.Dk.items()}}.items():
            with self.subTest(w=w):
                self.assertEqual(m["small"], [])

    def test_ac164_touch_targets(self):
        for w in (320, 390, 1280):
            cs = self.L[w]["controls"]
            with self.subTest(w=w):
                self.assertEqual([c["t"] for c in cs if c["miss"]], [], "44 by 44 px of hit area round each control")
                start = [c for c in cs if c["t"] == "Get started"]
                self.assertTrue(start and start[0]["h"] >= 43.5, "the Get started pill is 44 px tall")
                for i, a in enumerate(cs):
                    for b in cs[i + 1:]:
                        dx = max(b["x"] - a["r"], a["x"] - b["r"], 0)
                        dy = max(b["y"] - a["b"], a["y"] - b["b"], 0)
                        if dx or dy:
                            self.assertGreaterEqual((dx * dx + dy * dy) ** 0.5, 7.5, f"{a['t']!r} and {b['t']!r}")

    def test_ac165_hover_inside_hover_media_with_a_press_twin(self):
        on_home = set(self.L[1280]["hover_on_home"])   # hover rules whose element is on the home (Chrome's querySelector)
        self.assertTrue(on_home, "the home's pills and section links take a hover")
        sels = [p.strip() for _, css in self.sheets for _, s, b in C.rules(css) if b is not None for p in s.split(",")]
        for path, css in self.sheets:
            for chain, sel, body in C.rules(css):
                for part in (p.strip() for p in sel.split(",") if body is not None and ":hover" in p):
                    if part not in on_home:
                        continue
                    with self.subTest(sheet=path, rule=part[:60]):
                        self.assertTrue(any(re.search(r"\(\s*hover\s*:\s*hover\s*\)", a) for a in chain), "inside @media (hover: hover)")
                        self.assertIn(part.replace(":hover", ":active"), sels, "a press twin")

    def test_ac166_focus_rings(self):
        coral, ink = rgb("#FF5A47"), rgb("#13233A")
        white, navy, ground = "rgb(255, 255, 255)", rgb("#13233A"), rgb("#F2F1ED")
        for w in (390, 1280):
            for r in self.L[w]["rings"]:
                with self.subTest(w=w, control=r["t"]):
                    self.assertNotEqual(r["style"], "none")
                    self.assertGreaterEqual(r["width"], 2)
                    if r["fill"] == coral:
                        self.assertEqual(r["color"], ink, "ink on a coral surface")
                    elif r["under"] in (white, navy):
                        self.assertEqual(r["color"], coral, "coral on a white slab and the navy band")
                    elif r["under"].startswith("rgb(242, 241, 237") or r["under"] == ground:
                        self.assertEqual(r["color"], ink, "ink on the ground")

    def test_ac170_dark(self):
        for w in DARK:
            d, l = self.Dk[w], self.L[w]
            with self.subTest(w=w):
                self.assertEqual(d["ground"], rgb("#0C1626"))
                self.assertEqual(d["hero"]["bg"], rgb("#14223A"))
                self.assertEqual(d["paper"], l["paper"], "the paper keeps its light colours")
                self.assertEqual(d["low"], [], "every text pair reads in dark")
                self.assertEqual(l["low"], [], "and in light")

    def test_ac174_gradients_on_paper_blur_on_the_header(self):
        for w, m in self.L.items():
            with self.subTest(w=w):
                self.assertEqual(m["gradients"], [])
                self.assertEqual(m["blurs"], [])

    def test_ac176_fonts_and_heading_sizes(self):
        for w, m in self.L.items():
            with self.subTest(w=w):
                self.assertEqual(m["fonts"]["serif_upright"], [], "Libre Caslon only in italic")
                self.assertTrue(m["h1"]["family"].lstrip('"').startswith("Schibsted Grotesk"))
                for h in m["h2"]:
                    self.assertAlmostEqual(h["size"], min(max(33.6, 0.044 * w), 62.4), delta=0.6)
                    self.assertEqual(h["weight"], "850")
        self.assertEqual({t for t, _, _ in self.L[1280]["fonts"]["mono"] if len(t.split()) > 6}, set(),
                         "Geist Mono carries labels and file names, not sentences")


if __name__ == "__main__":
    unittest.main()
