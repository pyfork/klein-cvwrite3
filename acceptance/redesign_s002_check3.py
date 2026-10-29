"""CHECK 3 of redesign S-002: the real pages (stand-in data) in dark at every width, in headless Chrome, against the same
pages in light. Covers AC-79 (the admin marker), AC-80 (the QR frame), AC-81 and AC-82 on real controls, and AC-83.
Fails before the work: with the device set to dark the pages stay light.
senior-lead-Opus5.5-agent, 2026-10-29"""
import unittest

import redesign_s001_common as C
import redesign_s002_common as D
from support import CVCase

GROUND, INK, CORAL, ON_ACCENT, WHITE = "rgb(12, 22, 38)", "rgb(242, 238, 230)", "rgb(255, 90, 71)", "rgb(19, 35, 58)", "rgb(255, 255, 255)"
# fills that keep one value in both themes (AC-78) or invert with ink (AC-76: the ink pill); not surfaces
ACCENTS = {CORAL, "rgb(38, 150, 138)", "rgb(243, 180, 60)", "rgb(160, 205, 236)", INK, "rgb(255, 138, 128)"}
WIDTHS = [320, 375, 768, 1024, 1280, 1440]

JS = D.COLOUR_JS + r"""
const qa = s => [...doc.querySelectorAll(s)];
const vis = e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 && cs(e).display !== 'none'; };
const out = {scheme: cs(doc.documentElement).colorScheme, html: cs(doc.documentElement).backgroundColor, body: cs(doc.body).backgroundColor};
out.overflow = doc.documentElement.scrollWidth > doc.documentElement.clientWidth;
out.boxes = qa('body *').filter(vis).map(e => { const r = e.getBoundingClientRect(); return [e.tagName, Math.round(r.x * 2) / 2, Math.round(r.y * 2) / 2, Math.round(r.width * 2) / 2, Math.round(r.height * 2) / 2]; });
out.light = qa('body *').filter(e => vis(e) && !e.closest('.qr') && opaque(cs(e).backgroundColor) && lum(cs(e).backgroundColor) > 0.2)
  .map(e => [e.tagName + '.' + e.className, cs(e).backgroundColor]);
out.qr = qa('.qr').map(e => cs(e).backgroundColor);
out.marker = qa('.nav-admin i').map(e => [cs(e).color, cs(e).backgroundColor]);
out.primary = qa('.btn-primary').filter(vis).map(e => cs(e).color);
out.low = lowText(doc.body);
const rings = {brand: doc.querySelector('header a[href="/"]'), nav: qa('nav a')[0], foot: qa('footer a')[0], field: doc.querySelector('main input[type=text], main input[type=email], main textarea'),
  btn: doc.querySelector('main .btn'), primary: doc.querySelector('main .btn-primary')};
out.rings = {}; for (const [k, e] of Object.entries(rings)) { if (!e || !vis(e)) continue; e.focus(); const c = cs(e);
  out.rings[k] = {color: c.outlineColor, width: c.outlineWidth, fill: c.backgroundColor, ratio: ratio(c.outlineColor, bgOf(e.parentElement))}; }
return out;
"""


class DarkPages(CVCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass() if hasattr(super(), "setUpClass") else None
        C.require_chrome()

    def setUp(self):
        super().setUp()
        if not hasattr(DarkPages, "dark"):
            pages = C.app_pages(self)
            DarkPages.who = {k: v[1] for k, v in pages.items()}
            with C.Site(pages) as site:
                paths = {k: f"/p/{k}.html" for k in pages}
                dark = D.measure(site, list(paths.values()), WIDTHS, JS, "dark")
                light = D.measure(site, list(paths.values()), WIDTHS, JS, "light")
            DarkPages.dark = {k: dark[p] for k, p in paths.items()}
            DarkPages.lite = {k: light[p] for k, p in paths.items()}

    def collect(self, ac, bad):
        self.assertEqual(bad[:12], [], f"{ac}: {len(bad)} problems")

    def test_ac83_only_colour_changes(self):
        bad = []
        for name, by_w in DarkPages.dark.items():
            for w, r in by_w.items():
                if "dark" not in r["scheme"].split() or (r["html"], r["body"]) != (GROUND, GROUND):
                    bad.append(f"{name}@{w}: root is {r['scheme']} {r['html']} {r['body']}")
                if r["overflow"]:
                    bad.append(f"{name}@{w}: scrolls sideways in dark")
                if r["boxes"] != DarkPages.lite[name][w]["boxes"]:
                    diff = next((a, b) for a, b in zip(r["boxes"] + [None], DarkPages.lite[name][w]["boxes"] + [None]) if a != b)
                    bad.append(f"{name}@{w}: layout differs from light at {diff}")
                lit = [x for x in r["light"] if x[1] not in ACCENTS]
                if lit:
                    bad.append(f"{name}@{w}: light surfaces {lit[:3]}")
        self.collect("AC-83", bad)

    def test_ac79_ac80_marker_button_and_qr(self):
        bad = []
        for name, by_w in DarkPages.dark.items():
            for w in (320, 1280):
                r = by_w[w]
                if any(c != ON_ACCENT for c, bg in r["marker"]) or any(c != ON_ACCENT for c in r["primary"]):
                    bad.append(f"{name}@{w}: text on an accent is {r['marker']} {r['primary']}")
        owners = [k for k, v in DarkPages.who.items() if v == "owner"]
        self.assertTrue(owners and any(DarkPages.dark[k][320]["marker"] for k in owners), "no owner page with the admin marker")
        self.assertIn("order", DarkPages.dark, "no order page")
        for w in WIDTHS:
            if DarkPages.dark["order"][w]["qr"] != [WHITE]:
                bad.append(f"order@{w}: QR frame is {DarkPages.dark['order'][w]['qr']}")
        self.collect("AC-79 and AC-80", bad)

    def test_ac81_ac82_rings_and_contrast(self):
        bad = []
        for name, by_w in DarkPages.dark.items():
            for w in (320, 1280):
                r = by_w[w]
                if r["low"]:
                    bad.append(f"{name}@{w}: text under 4.5:1 {r['low'][:2]}")
                for k, ring in r["rings"].items():
                    want = INK if ring["fill"] == CORAL else CORAL
                    if ring["color"] != want or ring["width"] != "3px" or ring["ratio"] < 3:
                        bad.append(f"{name}@{w}: ring on {k} is {ring}")
        self.collect("AC-81 and AC-82", bad)


if __name__ == "__main__":
    unittest.main()
