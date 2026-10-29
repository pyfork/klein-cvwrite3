"""CHECK 2 of redesign S-001: the look the stylesheet gives (tokens, type, shape, components, states). Covers AC-9 to
AC-12, AC-15 to AC-18, AC-20, AC-21, AC-27 (the mark's shape), AC-44, AC-46 to AC-67 and the no-viewport-height part of
AC-70. Static rules are read from app/static/betterjobs.css; computed values come from headless Chrome on a gallery of
the old markup (acceptance/fixtures/s001_gallery.html). Fails before the work: there is no betterjobs.css.
Re-plan 2026-10-28 (senior-lead-Opus5.5-agent): AC-17 measures each focus ring against the parent's background.
AC-11 is retired by the dark-mode slice, as a re-plan of this check.
Re-plan 2026-10-29 (senior-lead-Opus5.5-agent, slice 2 plan): AC-9 muted is split by surface and AC-44's ring is coral on
white slabs (the owner's approved rows in README-brief-amended.md).
senior-lead-Sonnet5.5-agent, 2026-10-28"""
import re
import unittest

import redesign_s001_common as C

INK, CORAL, GROUND, SLAB, QUIET = "rgb(19, 35, 58)", "rgb(255, 90, 71)", "rgb(242, 241, 237)", "rgb(255, 255, 255)", "rgb(247, 246, 242)"
GREY, GREY_INK, TEAL, MARIGOLD = "rgb(214, 212, 206)", "rgb(90, 88, 94)", "rgb(38, 150, 138)", "rgb(243, 180, 60)"
MUTED, MUTED_SLAB, ERROR, EDGE = "rgb(86, 98, 117)", "rgb(106, 117, 134)", "rgb(180, 35, 24)", "rgb(125, 135, 152)"
TINT = {"warn": "rgb(251, 231, 176)", "bad": "rgb(250, 221, 215)", "ok": "rgb(217, 238, 233)", "info": "rgb(220, 235, 247)"}
EDGE_OF = {"warn": MARIGOLD, "bad": ERROR, "ok": TEAL, "info": "rgb(160, 205, 236)"}
WIDTHS = [320, 390, 544, 768, 1280]
TOKEN_HEX = """F2F1ED FFFFFF 13233A FF5A47 D6D4CE 5A585E 26968A F3B43C A0CDEC F7F6F2 566275 6A7586 3A4960 C2382A B42318 7D8798
E6E5E0 FBE7B0 FADDD7 D9EEE9 DCEBF7""".split()

GALLERY_JS = r"""
const q = s => doc.querySelector(s);
const cs = (e, p) => win.getComputedStyle(e, p || null);
const rgb = c => (c.match(/[\d.]+/g) || []).map(Number);
const lum = c => { const [r, g, b] = rgb(c).slice(0, 3).map(v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, o) => o - p); return (x + 0.05) / (y + 0.05); };
const bgOf = e => { for (let n = e; n; n = n.parentElement) { const m = rgb(cs(n).backgroundColor); if ((m[3] === undefined ? 1 : m[3]) > 0.5) return cs(n).backgroundColor; } return cs(doc.body).backgroundColor; };
const P = ['font-family','font-size','font-weight','font-style','color','background-color','background-image','border-top-width','border-top-style',
  'border-top-color','border-bottom-width','border-left-width','border-left-color','border-top-left-radius','box-shadow','padding-left','padding-top','min-height','opacity','cursor',
  'outline-style','outline-width','outline-offset','outline-color','display','position','clip','clip-path','overflow-x','overflow-y',
  'font-variant-numeric','accent-color','max-width','height','list-style-type','animation-name','transition','text-decoration-line','text-transform'];
const info = s => { const e = q(s); if (!e) return {missing: s}; const c = cs(e), r = e.getBoundingClientRect();
  const o = {w: r.width, h: r.height, x: r.x, y: r.y, sw: e.scrollWidth, cw: e.clientWidth, sh: e.scrollHeight, ch: e.clientHeight};
  for (const p of P) o[p] = c.getPropertyValue(p); return o; };
const pseudo = (s, which) => { const e = q(s); if (!e) return {}; const c = cs(e, which); return {content: c.content, bg: c.backgroundImage, mask: c.webkitMaskImage || c.maskImage || '', w: c.width, h: c.height, bgc: c.backgroundColor, bw: c.borderTopWidth, bc: c.borderTopColor, radius: c.borderTopLeftRadius, an: c.animationName}; };
const D = {looked: cs(doc.documentElement).colorScheme === 'light' && cs(doc.body).backgroundColor === 'rgb(242, 241, 237)'};
D.html_bg = cs(doc.documentElement).backgroundColor; D.body_bg = cs(doc.body).backgroundColor;
const ids = ['t-eyebrow','t-h1','t-lede','t-h2','t-p','t-link','t-hint','t-meta','t-note','t-kicker','t-stime','t-pass','t-code','t-opt','t-need','card1','card2','tcard',
  'b-primary','b-btn','b-ghost','b-danger','b-dghost','b-sm','b-dis-primary','b-dis','b-swap','b-long','row','f-text','f-req','f-sel','f-area','f-dis','c1','c-box','c-on','c-radio',
  'drop','drop-t','drop-s','drop-picked','drop-picked-t','drop-big','drop-big-s','a-warn','a-bad','a-ok','a-info','a-bare','a-multi','n-banner','n-bar','g-ok','g-wait','g-bad','g-off','g-chip','g-chipout',
  's-wait','s-run','s-done','s-fail','tbl','t-num','p-one','p-best','p-tag','p-dis','img','img-bad','imgcard','sum','det','cvtext','narrow'];
D.el = {}; for (const id of ids) D.el['#' + id] = info('#' + id);
D.extra = {
  body: info('body'), th: info('#tbl th'), td1: info('#tbl td:first-child'), tr: info('#tbl tbody tr'), thead: info('#tbl thead'),
  dot: ['s-wait','s-run','s-done','s-fail'].map(i => ({st: i, dot: info('#' + i + ' .dot'), b: pseudo('#' + i + ' .dot', '::before'), a: pseudo('#' + i + ' .dot', '::after')})),
  icons: ['a-warn','a-bad','a-ok','a-info','a-bare','n-banner','n-bar'].map(i => ({id: i, el: info('#' + i), b: pseudo('#' + i, '::before'), a: pseudo('#' + i, '::after')})),
  multi_child: (() => { const e = q('#a-multi > *'); return e ? e.getBoundingClientRect().x - q('#a-multi').getBoundingClientRect().x : null; })(),
  details_open: (() => { const d = q('#det'); d.open = true; const s = q('#sum').getBoundingClientRect(), u = q('#det ul').getBoundingClientRect(); return {gap: u.top - s.bottom, marker: cs(q('#sum')).display}; })(),
  pack_dis_focus: (() => { const b = q('#p-dis'); b.focus(); return doc.activeElement === b; })(),
  sum_marker: pseudo('#sum', '::before'),
  picked_b: pseudo('#drop-picked-t', '::before'), picked_a: pseudo('#drop-picked-t', '::after'),
  card_gap: q('#card2').getBoundingClientRect().top - q('#card1').getBoundingClientRect().bottom,
  img_ratio: (() => { const r = q('#img').getBoundingClientRect(); return r.width / r.height; })(),
  img_bad: (() => { const i = q('#img-bad'), t = q('#after-img'); return {h: i.getBoundingClientRect().height, bottom: i.getBoundingClientRect().bottom, next: t.getBoundingClientRect().top}; })(),
  row_btns: [...doc.querySelectorAll('#row .btn')].map(b => b.getBoundingClientRect().width), row_w: q('#row').getBoundingClientRect().width,
  shadow_probe: (() => { const d = doc.createElement('div'); d.style.boxShadow = 'var(--shadow)'; doc.body.appendChild(d); const s = cs(d).boxShadow; d.remove(); return s; })(),
};
// contrast of every piece of text against what it sits on (disabled controls are exempt)
D.low = []; for (const e of doc.querySelectorAll('#main *')) { if (e.closest(':disabled, [disabled]')) continue;
  if (![...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())) continue;
  const r = ratio(cs(e).color, bgOf(e)); if (r < 4.5) D.low.push([e.id || e.className || e.tagName, Math.round(r * 100) / 100]); }
// focus rings
D.focus = {}; for (const s of ['#b-btn','#b-primary','#f-text','#t-link','#sum','#c-box','#p-one']) { const e = q(s); e.focus(); const c = cs(e);
  D.focus[s] = {style: c.outlineStyle, width: c.outlineWidth, offset: c.outlineOffset, color: c.outlineColor, border: c.borderTopColor, shadow: c.boxShadow, bg: bgOf(e), ratio: ratio(c.outlineColor, bgOf(e)),
    ring_bg: bgOf(e.parentElement), ring_ratio: ratio(c.outlineColor, bgOf(e.parentElement))}; }
D.focus_input = {}; q('#drop-in').focus(); { const c = cs(q('#drop')); D.focus_input = {style: c.outlineStyle, width: c.outlineWidth, color: c.outlineColor}; }
D.edge_ratio = ratio(cs(q('#f-text')).borderTopColor, bgOf(q('#f-text')));
// swap main for ghost on a button: nothing may move
{ const b = q('#b-swap'), r0 = b.getBoundingClientRect(); b.classList.remove('btn-primary'); b.classList.add('btn-ghost'); await new Promise(r => setTimeout(r, 400));
  const r1 = b.getBoundingClientRect(); D.swap = [r0.x, r0.y, r0.width, r0.height, r1.x, r1.y, r1.width, r1.height]; }
return D;
"""


def px(v):
    return float(str(v).replace("px", "")) if str(v).replace("px", "").replace(".", "").replace("-", "").isdigit() else float("nan")


def root_decls(css):
    return dict((p, v) for ch, sel, b in C.rules(css) if b is not None and re.fullmatch(r":root(\s*,\s*:host)?", sel) for p, v in C.decls(b))


def declared(css, selector_re):
    """Declarations of every non-root style rule whose selector matches selector_re -> [(chain, selector, prop, value)]."""
    out = []
    for chain, sel, body in C.rules(css):
        if body is not None and not sel.startswith("@") and re.search(selector_re, sel):
            out.extend((chain, sel, p, v) for p, v in C.decls(body))
    return out


class Look(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        C.require_chrome()
        cls.css = C.sheet_text() if C.SHEET.exists() else ""
        cls.bare = C.strip_comments(cls.css)
        with C.Site() as site:
            cls.data = C.measure(site, "/fx/s001_gallery.html", WIDTHS, GALLERY_JS)["/fx/s001_gallery.html"]

    def at(self, w):
        d = self.data[w]
        self.assertTrue(d["looked"], "the new stylesheet is not applied (the ground is not #F2F1ED / color-scheme is not light)")
        return d

    def el(self, w, sel):
        e = self.at(w)["el"][sel]
        self.assertNotIn("missing", e, sel)
        return e

    # ------------------------------------------------------------------------------ tokens and plain CSS rules
    def test_ac9_the_tokens_hold_these_colours(self):
        self.assertTrue(self.css, "no stylesheet")
        values = " ".join(C.tokens(self.css).values()).lower()
        for h in TOKEN_HEX:
            with self.subTest(colour=h):
                self.assertIn("#" + h.lower(), values)
        for name in ("--shadow", "--hover", "--halo", "--slab", "--slab-2"):
            self.assertIn(name, C.tokens(self.css), name)

    def test_ac10_no_colour_literal_outside_the_tokens(self):
        self.assertTrue(self.css, "no stylesheet")
        bad = []
        for chain, sel, body in C.rules(self.css):
            if body is None or re.fullmatch(r":root(\s*,\s*:host)?", sel):
                continue
            for p, v in C.decls(body):
                if re.search(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(", C.without_urls(v)):
                    bad.append((sel, p))
        self.assertEqual(bad, [])

    def test_ac11_light_only_for_now(self):
        self.assertTrue(self.css, "no stylesheet")
        self.assertEqual(root_decls(self.css).get("color-scheme"), "light")
        self.assertNotIn("prefers-color-scheme", self.bare)

    def test_ac12_font_stacks_end_in_a_system_fallback(self):
        self.assertTrue(self.css, "no stylesheet")
        toks, stacks = C.tokens(self.css), []
        for chain, sel, body in C.rules(self.css):
            if body is None or sel == "@font-face":
                continue
            for p, v in C.decls(body):
                if p == "font-family" or (p.startswith("--") and "font" in p and "," in v):
                    stacks.append(re.sub(r"var\((--[\w-]+)\)", lambda m: toks.get(m.group(1), ""), v))
        self.assertTrue(stacks)
        for s in stacks:
            if "Schibsted Grotesk" in s:
                self.assertRegex(s, r"Helvetica Neue.*Arial.*sans-serif\s*$", s)
            if "Libre Caslon Text" in s:
                self.assertRegex(s, r"Georgia.*serif\s*$", s)
            if "Geist Mono" in s:
                self.assertRegex(s, r"ui-monospace.*Menlo.*monospace\s*$", s)

    def test_ac21_flat_paper_and_one_shadow(self):
        self.assertTrue(self.css, "no stylesheet")
        for word in ("gradient(", "backdrop-filter", "blur("):
            self.assertNotIn(word, self.bare)
        for chain, sel, p, v in declared(self.css, r".*"):
            if p == "box-shadow":
                self.assertTrue(v == "none" or "var(--shadow)" in v or "var(--halo)" in v, f"{sel}: {v}")

    def test_ac27_the_brand_mark_is_drawn_in_css(self):
        self.assertTrue(self.css, "no stylesheet")
        self.assertRegex(self.bare, r"clip-path\s*:\s*polygon\(\s*8%\s+14%\s*,\s*92%\s+2%\s*,\s*100%\s+70%\s*,\s*70%\s+98%\s*,\s*4%\s+88%\s*\)")

    def test_ac46_hover_only_where_a_pointer_hovers(self):
        self.assertTrue(self.css, "no stylesheet")
        n = 0
        for chain, sel, body in C.rules(self.css):
            if body is not None and ":hover" in sel:
                n += 1
                self.assertTrue(any(re.search(r"\(\s*hover\s*:\s*hover\s*\)", a) for a in chain), f"{sel} is not inside @media (hover: hover)")
        self.assertGreater(n, 0, "no hover style at all")

    def test_ac47_a_press_gives_the_touch_its_feedback(self):
        self.assertTrue(self.css, "no stylesheet")
        active = declared(self.css, r":active")
        text = " ".join(f"{s}{{{p}:{v}}}" for c, s, p, v in active)
        self.assertRegex(text, r"scale\(\s*0?\.98\s*\)")
        self.assertTrue(any(".drop" in s and "--hover" in v for c, s, p, v in active), "no press fill on the drop zone")
        for want in (".btn", ".pack"):
            self.assertTrue(any(want in s for c, s, p, v in active), f"no :active rule for {want}")

    def test_ac49_nothing_loops_and_transitions_are_short(self):
        self.assertTrue(self.css, "no stylesheet")
        self.assertNotIn("infinite", self.bare)
        self.assertNotRegex(self.bare, r"@keyframes\s+[\w-]*pulse")
        allowed = {"transform", "opacity", "color", "background-color", "border-color", "outline-color", "fill", "stroke"}
        for chain, sel, p, v in declared(self.css, r".*"):
            if p in ("transition", "transition-duration", "transition-property"):
                for t in re.findall(r"(\d*\.?\d+)(ms|s)\b", v):
                    ms = float(t[0]) * (1000 if t[1] == "s" else 1)
                    self.assertLessEqual(ms, 300, f"{sel}: {v}")
                if p != "transition-duration":
                    for prop in re.findall(r"(?:^|,)\s*([a-z-]+)", v):
                        self.assertTrue(prop in allowed or prop in ("none", "0s", "0ms"), f"{sel} transitions {prop}")

    def test_ac50_reduced_motion_turns_motion_off(self):
        self.assertTrue(self.css, "no stylesheet")
        text = " ".join(f"{p}:{v}" for chain, sel, p, v in declared(self.css, r".*") if any("prefers-reduced-motion" in a for a in chain))
        self.assertRegex(text, r"transition(-duration)?\s*:\s*(none|0s|0ms|0\b)")
        self.assertRegex(text, r"transform\s*:\s*none")

    def test_ac54_a_field_turns_red_only_after_the_person_touched_it(self):
        self.assertTrue(self.css, "no stylesheet")
        self.assertTrue(any(":user-invalid" in s for c, s, p, v in declared(self.css, r".*")), "no :user-invalid rule")
        for chain, sel, p, v in declared(self.css, r"(?<!user-):invalid"):
            self.assertNotIn("border", p, f"{sel} reddens an untouched field")

    def test_ac58_the_notes_carry_heroicons_and_their_licence(self):
        self.assertTrue(self.css, "no stylesheet")
        top = self.css[:self.css.find("*/") + 2] if self.css.lstrip().startswith("/*") else ""
        self.assertIn("Heroicons", top)
        self.assertIn("MIT", top)
        self.assertGreaterEqual(self.css.count("data:image/svg+xml"), 4)

    def test_budget_the_stylesheet_stays_light_for_a_phone(self):
        """Plan budget, not an AC: at most 45,000 bytes (today's calm.css is 21,023)."""
        self.assertTrue(self.css, "no stylesheet")
        self.assertLessEqual(C.SHEET.stat().st_size, 45000)

    def test_ac70_nothing_is_sized_to_the_window_height(self):
        self.assertTrue(self.css, "no stylesheet")
        for chain, sel, p, v in declared(self.css, r".*"):
            self.assertNotRegex(v, r"\d(vh|dvh|svh|lvh)\b", f"{sel} {p}: {v}")

    # --------------------------------------------------------------------------------- computed, in Chrome
    def test_ac12_type_families(self):
        for w in (320, 1280):
            for sel in ("#t-h1", "#t-h2", "#t-p", "#t-hint", "#t-link", "#b-btn", "#f-text"):
                self.assertTrue(self.el(w, sel)["font-family"].startswith('"Schibsted Grotesk"'), (w, sel))
            self.assertIn("Libre Caslon Text", self.el(w, "#t-note")["font-family"])
            self.assertEqual(self.el(w, "#t-note")["font-style"], "italic")
            for sel in ("#t-eyebrow", "#t-kicker", "#t-stime", "#t-pass", "#t-code", "#t-opt", "#g-ok", "#g-chip", "#cvtext"):
                self.assertIn("Geist Mono", self.el(w, sel)["font-family"], (w, sel))

    def test_ac15_text_sizes(self):
        for w in WIDTHS:
            body = self.at(w)["extra"]["body"]
            self.assertEqual(body["font-size"], "17px", w)
            for sel in ("#t-lede", "#t-hint", "#t-meta", "#t-p", "#a-warn", "#b-btn", "#f-text", "#f-sel", "#f-area", "#sum", "#c1"):
                self.assertGreaterEqual(px(self.el(w, sel)["font-size"]), 16, (w, sel))
            for sel in ("#t-eyebrow", "#t-kicker", "#t-stime", "#t-pass", "#t-opt", "#g-ok", "#g-chip"):
                self.assertGreaterEqual(px(self.el(w, sel)["font-size"]), 14, (w, sel))
            self.assertGreaterEqual(px(self.at(w)["extra"]["th"]["font-size"]), 14)
        self.assertEqual(self.el(320, "#t-h1")["font-size"], "28px")
        self.assertEqual(self.el(768, "#t-h1")["font-size"], "40px")
        self.assertEqual(self.el(1280, "#t-h1")["font-size"], "40px")
        self.assertTrue(28 < px(self.el(544, "#t-h1")["font-size"]) < 40, "the heading does not rise evenly between 320 and 768")
        for sel in ("#t-p", "#t-hint", "#b-btn", "#t-eyebrow"):
            self.assertEqual({self.el(w, sel)["font-size"] for w in WIDTHS}, {self.el(320, sel)["font-size"]}, sel + " changes size with width")

    def test_ac16_every_text_is_4_5_to_1(self):
        for w in (320, 1280):
            self.assertEqual(self.at(w)["low"], [], w)

    def test_ac17_edges_and_rings_are_3_to_1(self):
        d = self.at(1280)
        self.assertGreaterEqual(d["edge_ratio"], 3)
        # the ring sits 3px outside the element, so it is measured against the parent's opaque background, not the
        # element's own fill (re-plan 2026-10-28: an ink button gave ink on ink, 1:1)
        for sel, f in d["focus"].items():
            self.assertGreaterEqual(f["ring_ratio"], 3, (sel, f["ring_bg"]))

    def test_ac18_the_ground_fills_the_window(self):
        for w in WIDTHS:
            d = self.at(w)
            self.assertEqual((d["html_bg"], d["body_bg"]), (GROUND, GROUND), w)

    def test_ac20_a_card_is_a_slab(self):
        for w in WIDTHS:
            c = self.el(w, "#card1")
            self.assertEqual(c["background-color"], SLAB)
            self.assertEqual(c["border-top-left-radius"], "24px")
            self.assertEqual(c["box-shadow"], self.at(w)["extra"]["shadow_probe"])
            self.assertNotEqual(c["box-shadow"], "none")
            self.assertEqual(c["padding-left"], "28px" if w >= 560 else "20px", w)
            self.assertEqual(round(self.at(w)["extra"]["card_gap"]), 20, w)

    def test_ac44_focus_ring(self):
        # re-plan 2026-10-29: coral where the colour behind the ring is a white slab, ink on the ground, on a quiet
        # slab and on a coral button
        for sel, f in self.at(1280)["focus"].items():
            want = CORAL if f["ring_bg"] == SLAB and f["bg"] != CORAL else INK
            self.assertEqual((f["style"], f["width"], f["offset"], f["color"]), ("solid", "3px", "3px", want), sel)
        f = self.at(1280)["focus"]["#f-text"]
        self.assertEqual(f["border"], INK)
        self.assertIn("rgba(19, 35, 58, 0.18)", f["shadow"])
        self.assertEqual(self.at(1280)["focus_input"]["style"], "solid", "the drop zone shows no ring when its input has focus")

    def test_ac48_disabled(self):
        for w in (390, 1280):
            for sel in ("#b-dis", "#b-dis-primary", "#f-dis", "#p-dis"):
                e = self.el(w, sel)
                self.assertEqual(e["opacity"], "0.45", sel)
                self.assertEqual(e["cursor"], "not-allowed", sel)
            self.assertEqual(self.el(w, "#b-dis-primary")["background-color"], CORAL)
            self.assertFalse(self.at(w)["extra"]["pack_dis_focus"])

    def test_ac51_ac52_buttons(self):
        for w in WIDTHS:
            self.assertEqual((self.el(w, "#b-primary")["background-color"], self.el(w, "#b-primary")["color"]), (CORAL, INK))
            for s in ("#b-btn", "#b-ghost"):
                self.assertEqual((self.el(w, s)["background-color"], self.el(w, s)["color"]), (INK, SLAB), s)
            self.assertEqual((self.el(w, "#b-danger")["background-color"], self.el(w, "#b-danger")["color"]), (ERROR, SLAB))
            dg = self.el(w, "#b-dghost")
            self.assertEqual((dg["color"], dg["border-top-width"], dg["border-top-color"]), (ERROR, "2px", ERROR))
            self.assertEqual(dg["background-color"], "rgba(0, 0, 0, 0)")
            for s in ("#b-primary", "#b-btn", "#b-ghost", "#b-danger", "#b-dghost"):
                e = self.el(w, s)
                self.assertGreaterEqual(e["h"], 48, s)
                self.assertGreaterEqual(e["w"], 44, s)
                self.assertGreaterEqual(px(e["border-top-left-radius"]), e["h"] / 2 - 0.5, s + " is not a pill")
            self.assertGreaterEqual(self.el(w, "#b-sm")["h"], 44)
            long = self.el(w, "#b-long")
            self.assertLessEqual(long["sw"], long["cw"], "the label overflows its button")
            x = self.at(w)["swap"]
            self.assertEqual(x[:4], x[4:], "swapping main for ghost moved or resized the button")
        for w in (320, 390, 544):
            ex = self.at(w)["extra"]
            for bw in ex["row_btns"]:
                self.assertLessEqual(abs(bw - ex["row_w"]), 2, f"{w}: buttons in an action row do not fill it")

    def test_ac53_ac55_ac56_fields_and_choices(self):
        for w in (320, 1280):
            f = self.el(w, "#f-text")
            self.assertGreaterEqual(f["h"], 48)
            self.assertEqual((f["font-size"], f["border-top-width"], f["border-top-color"], f["border-top-left-radius"]), ("16px", "2px", EDGE, "16px"))
            ro = self.el(w, "#f-area")
            self.assertEqual((ro["background-color"], ro["cursor"]), (QUIET, "default"))
            self.assertEqual(self.el(w, "#f-dis")["cursor"], "not-allowed")
            box = self.el(w, "#c-box")
            self.assertEqual((round(box["w"]), round(box["h"]), box["accent-color"]), (24, 24, INK))
            self.assertGreaterEqual(self.el(w, "#c1")["h"], 44)

    def test_ac57_the_drop_zone(self):
        for w in (320, 1280):
            d = self.el(w, "#drop")
            self.assertEqual((d["border-top-style"], d["border-top-width"], d["border-top-color"], d["background-color"]), ("dashed", "2px", EDGE, QUIET))
            self.assertGreaterEqual(d["h"], 120)
            p = self.el(w, "#drop-picked")
            self.assertEqual((p["border-top-style"], p["border-top-color"]), ("solid", INK))
            ex = self.at(w)["extra"]
            tick = self.el(w, "#drop-picked-t")["background-image"] + str(ex["picked_b"]) + str(ex["picked_a"])
            self.assertIn("svg", tick, "no tick before the file name")
            self.assertLessEqual(p["sw"], p["cw"], "a long file name overflows the zone")
            big = self.el(w, "#drop-big")
            self.assertEqual(big["border-top-color"], ERROR)
            s = self.el(w, "#drop-big-s")
            self.assertEqual(s["color"], ERROR)
            self.assertGreaterEqual(int(s["font-weight"]), 700)

    def test_ac58_ac59_status_notes(self):
        for w in (320, 1280):
            for ic in self.at(w)["extra"]["icons"]:
                kind = {"a-warn": "warn", "a-bad": "bad", "a-ok": "ok", "a-info": "info", "a-bare": "info", "n-banner": "warn", "n-bar": "info"}[ic["id"]]
                e = ic["el"]
                self.assertEqual(e["background-color"], TINT[kind], ic["id"])
                self.assertEqual((e["border-left-width"], e["border-left-color"]), ("4px", EDGE_OF[kind]), ic["id"])
                has_icon = "svg" in (e["background-image"] + ic["b"].get("bg", "") + ic["b"].get("mask", "") + ic["a"].get("bg", "") + ic["a"].get("mask", ""))
                self.assertTrue(has_icon, f"{ic['id']} has no icon")
            m = self.el(w, "#a-multi")
            self.assertLessEqual(m["sh"], m["ch"] + 1, "the note clips its text")
            self.assertGreaterEqual(self.at(w)["extra"]["multi_child"], 52, "the text does not clear the icon gutter")

    def test_ac60_ac61_labels_and_dots(self):
        for w in (320, 1280):
            for s, bg, fg in (("#g-ok", TINT["ok"], INK), ("#g-wait", TINT["warn"], INK), ("#g-bad", TINT["bad"], INK), ("#g-off", GREY, GREY_INK)):
                e = self.el(w, s)
                self.assertEqual((e["background-color"], e["color"], e["font-size"]), (bg, fg, "14px"), s)
                self.assertIn("Geist Mono", e["font-family"])
                self.assertGreaterEqual(px(e["border-top-left-radius"]), e["h"] / 2 - 0.5, s)
            sig = []
            for d in self.at(w)["extra"]["dot"]:
                sig.append(str([d["dot"]["background-color"], d["dot"]["border-top-color"], d["dot"]["border-top-width"], d["dot"]["background-image"], d["b"], d["a"]]))
                self.assertEqual(d["dot"]["animation-name"], "none")
            self.assertEqual(len(set(sig)), 4, "the four step states do not differ in shape")

    def test_ac62_ac63_tables(self):
        for w in (768, 1280):
            ex = self.at(w)["extra"]
            self.assertEqual((ex["th"]["font-size"], ex["th"]["color"]), ("14px", MUTED_SLAB))
            self.assertEqual(ex["td1"]["font-size"], "16px")
            self.assertTrue("1px" in (ex["td1"]["border-bottom-width"], ex["tr"]["border-bottom-width"]), "no 1 px divider between rows")
            self.assertGreaterEqual(int(ex["td1"]["font-weight"]), 700)
            self.assertIn("tabular-nums", self.el(w, "#t-num")["font-variant-numeric"])
        for w in (320, 390, 544):
            ex = self.at(w)["extra"]
            self.assertEqual(ex["tr"]["display"], "block", w)
            self.assertEqual(ex["td1"]["display"], "block", w)
            t = ex["thead"]
            self.assertNotEqual(t["display"], "none")
            self.assertTrue((t["w"] <= 1.5 and t["h"] <= 1.5) or t["clip"] != "auto" or t["clip-path"] != "none", "the stacked table's header is not hidden from the eye")

    def test_ac65_packs(self):
        for w in (320, 1280):
            p = self.el(w, "#p-one")
            self.assertEqual((p["border-top-left-radius"], p["border-top-width"]), ("20px", "2px"))
            self.assertGreaterEqual(p["h"], 48)
            self.assertEqual(self.el(w, "#p-best")["border-top-color"], INK)
            tag = self.el(w, "#p-tag")
            self.assertEqual((tag["background-color"], tag["color"]), (INK, SLAB))

    def test_ac66_images_shrink_and_keep_their_ratio(self):
        for w in (320, 390):
            img, card = self.el(w, "#img"), self.el(w, "#imgcard")
            self.assertLessEqual(img["w"], card["cw"] + 0.5)
            self.assertAlmostEqual(self.at(w)["extra"]["img_ratio"], 2.0, places=1)

    def test_ac67_details(self):
        for w in (320, 1280):
            s = self.el(w, "#sum")
            self.assertEqual((s["font-size"], s["color"]), ("16px", INK))
            self.assertGreaterEqual(int(s["font-weight"]), 700)
            self.assertGreaterEqual(s["h"], 44)
            ex = self.at(w)["extra"]
            native = s["display"] == "list-item" and s["list-style-type"] != "none"
            drawn = ex["sum_marker"].get("content", "none") not in ("none", "normal") and ("svg" in ex["sum_marker"].get("bg", "") or ex["sum_marker"].get("w", "auto") != "auto")
            self.assertTrue(native or drawn, "the summary has no visible marker")
            self.assertAlmostEqual(ex["details_open"]["gap"], 8, delta=1.5)


if __name__ == "__main__":
    unittest.main()
