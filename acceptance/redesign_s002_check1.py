"""CHECK 1 of redesign S-002: the dark block in the stylesheet, read as text. Covers AC-72 (color-scheme), AC-74, AC-75 and
the token values of AC-76 to AC-80. Fails before the work: the stylesheet has no prefers-color-scheme rule and declares
`color-scheme: light`.
senior-lead-Opus5.5-agent, 2026-10-29"""
import re
import unittest
from pathlib import Path

import redesign_s001_common as C
import redesign_s002_common as D

# AC-76 and AC-77: the dark values (the icons are checked by their stroke)
DARK = {
    "--ground": "#0C1626", "--slab": "#14223A", "--slab-2": "#192943", "--ink": "#F2EEE6", "--ink-2": "#CBD2DD",
    "--coral-text": "#FF8A79", "--grey": "#2E3B50", "--grey-ink": "#A6A3AC",
    "--shadow": "0 1px 0 rgba(0,0,0,.2), 0 18px 40px -22px rgba(0,0,0,.7)",
    "--error": "#FF8A80", "--edge": "#6B7A90", "--hover": "#22334F",
    "--tint-warn": "#3A3120", "--tint-bad": "#3E2329", "--tint-ok": "#16332F", "--tint-info": "#182F48",
    "--halo": "0 0 0 4px rgba(242,238,230,.24)",
}
MUTED_LIGHT = {"#566275", "#6a7586"}
ICONS = ("--icon-warn", "--icon-bad", "--icon-ok", "--icon-info")
# AC-78, AC-79, AC-80: never in the dark block
KEEP = ("--coral", "--teal", "--marigold", "--sky", "--font-sans", "--font-serif", "--font-mono", "--ease",
        "--mark-tick", "--mark-cross", "--on-accent", "--qr-ground")
APP = Path(C.ROOT) / "app"


def norm(v):
    return re.sub(r"\s+", "", v).lower()


class DarkBlock(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.css = C.sheet_text()
        cls.light = D.light_root(cls.css)
        cls.dark = D.dark_tokens(cls.css)

    def test_ac72_root_declares_both_themes(self):
        self.assertEqual(norm(self.light.get("color-scheme", "")), "lightdark")

    def test_ac74_one_dark_block_of_tokens_only(self):
        rules = D.dark_rules(self.css)
        self.assertTrue(rules, "no @media (prefers-color-scheme: dark) rule")
        for ch, sel, body in rules:
            self.assertEqual(sel, ":root", f"the dark block styles {sel}, not tokens")
            for p, v in C.decls(body or ""):
                self.assertTrue(p.startswith("--"), f"the dark block sets {p}")
        other = [a for ch, sel, b in C.rules(self.css) for a in ch if "prefers-color-scheme" in a and not D.DARK_MEDIA.match(a.strip())]
        self.assertEqual(other, [], "a prefers-color-scheme rule other than the dark block")

    def test_ac74_ac10_no_colour_literal_outside_the_token_blocks(self):
        bad = []
        for ch, sel, body in C.rules(self.css):
            if body is None or re.fullmatch(r":root(\s*,\s*:host)?", sel):
                continue
            for p, v in C.decls(body):
                if re.search(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(", C.without_urls(v)):
                    bad.append((sel, p))
        self.assertEqual(bad, [])

    def test_ac75_the_theme_follows_the_device_only(self):
        self.assertNotIn("data-theme", C.strip_comments(self.css))
        hits = []
        for f in sorted(list((APP / "templates").glob("*.html")) + list((APP / "static").glob("*.js")) + list(APP.glob("*.py"))):
            text = f.read_text(encoding="utf-8")
            for word in re.findall(r"data-theme|matchMedia|localStorage|sessionStorage|prefers-color-scheme|\btheme\b", text, re.I):
                hits.append((f.name, word))
        self.assertEqual(hits, [], "a switch, a stored choice or a script for the theme")

    def test_ac76_ac77_dark_values(self):
        for name, want in DARK.items():
            with self.subTest(token=name):
                self.assertEqual(norm(self.dark.get(name, "")), norm(want))

    def test_ac76_muted_is_one_value_on_every_surface(self):
        names = [n for n, v in self.light.items() if n.startswith("--") and v.strip().lower() in MUTED_LIGHT]
        self.assertTrue(names, "no muted token in the light block")
        for n in names:
            self.assertEqual(norm(self.dark.get(n, "")), "#95a2b5", n)

    def test_ac77_the_icons_are_drawn_light_in_dark(self):
        for name in ICONS:
            with self.subTest(icon=name):
                light, dark = self.light.get(name, ""), self.dark.get(name, "")
                self.assertIn("%2313233A", light)
                self.assertEqual(dark, light.replace("%2313233A", "%23F2EEE6"), "the dark icon differs by more than its stroke")

    def test_ac78_to_ac80_these_keep_one_value(self):
        for name in KEEP:
            with self.subTest(token=name):
                self.assertIn(name, self.light)
                self.assertNotIn(name, self.dark)
        self.assertEqual(norm(self.light["--on-accent"]), "#13233a")
        self.assertEqual(norm(self.light["--qr-ground"]), "#ffffff")
        for n in self.dark:
            self.assertFalse(n.startswith("--paper"), f"{n} has a dark value")

    def test_ac79_text_on_coral_and_marigold_uses_on_accent(self):
        seen = 0
        for ch, sel, body in C.rules(self.css):
            if body is None or sel.startswith("@") or ch:
                continue
            d = dict(C.decls(body))
            fill = d.get("background", "") + d.get("background-color", "")
            if re.search(r"var\(--(coral|marigold)\)", fill) and "color" in d:
                seen += 1
                self.assertEqual(d["color"], "var(--on-accent)", sel)
        self.assertGreaterEqual(seen, 2, "the primary button and the admin marker")

    def test_ac80_the_qr_frame_stays_white(self):
        qr = [dict(C.decls(b)) for ch, s, b in C.rules(self.css) if b is not None and s == ".qr"]
        self.assertTrue(qr, "no .qr rule")
        self.assertTrue(any("var(--qr-ground)" in (d.get("background", "") + d.get("background-color", "")) for d in qr))


if __name__ == "__main__":
    unittest.main()
