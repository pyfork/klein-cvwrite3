"""CHECK 1 of redesign S-001: every page is wired to the new stylesheet and the new fonts. Covers AC-1, AC-2, AC-3,
AC-4, AC-5, AC-13 and the font-display part of AC-14. Fails before the work: there is no betterjobs.css.
senior-lead-Sonnet5.5-agent, 2026-10-28"""
import re
import unittest
from unittest import mock

import redesign_s001_common as C
from support import CVCase

# Classes the templates use that have no rule in Calm today: markers, JS hooks, and words that sit inside a Jinja
# condition in a class attribute. They need no rule. Anything else a template uses needs one (AC-4).
HOOKS = {
    "act": "marker on the profile form's action row; Calm has no rule",
    "admin-reports": "marker on the admin reports block; no rule in Calm",
    "checklist": "marker on the Generate checklist card; no rule in Calm",
    "failed": "a word inside a Jinja condition in a class attribute, not a class",
    "generating": "a word inside a Jinja condition in a class attribute, not a class",
    "is-todo": "the waiting state of the checklist; the plain dot is the waiting look",
    "master": "a word inside a Jinja condition in a class attribute, not a class",
    "name": "a word inside a Jinja condition in a class attribute, not a class",
    "notice-summary": "marker on the consent summary; no rule in Calm",
    "open": "a word inside a Jinja condition in a class attribute, not a class",
    "passed": "a word inside a Jinja condition in a class attribute, not a class",
    "pay": "marker on the pay page; no rule in Calm",
    "paywall": "marker on the Generate paywall card; no rule in Calm",
    "prep": "marker on the interview prep block; no rule in Calm",
    "prep-row": "marker on the applications prep row; no rule in Calm",
}
REQUIRED_FAMILIES = {"Schibsted Grotesk": None, "Libre Caslon Text": "italic", "Geist Mono": None}


class SheetAndFonts(CVCase):
    def test_ac1_every_page_links_the_new_sheet_and_not_calm(self):
        from app.main import APP_VERSION
        base = (C.TEMPLATES / "base.html").read_text(encoding="utf-8")
        self.assertIn('href="/static/betterjobs.css?v={{ app_version }}"', base)
        for f in sorted(C.TEMPLATES.glob("*.html")):
            text = f.read_text(encoding="utf-8")
            self.assertNotIn("calm.css", text, f.name)
            if f.name != "base.html" and not f.name.startswith("_"):
                self.assertRegex(text, r"\{%\s*extends\s+[\"']base.html[\"']\s*%\}", f.name + " does not extend base.html")
        pages = C.app_pages(self)
        self.assertGreaterEqual(len(pages), 18, sorted(pages))
        for name, (html, who) in pages.items():
            with self.subTest(page=name):
                self.assertIn(f'href="/static/betterjobs.css?v={APP_VERSION}"', html)
                self.assertNotIn("calm.css", html)

    def test_ac2_the_sheet_is_served_and_cached_and_calm_is_gone(self):
        from app.main import APP_VERSION
        r = self.client.get(f"/static/betterjobs.css?v={APP_VERSION}")
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("no-store", r.headers.get("cache-control", ""))
        self.assertEqual(self.client.get("/static/calm.css").status_code, 404)
        self.assertFalse((C.STATIC / "calm.css").exists())

    def test_ac3_the_sheet_url_carries_the_version(self):
        with mock.patch("app.main.APP_VERSION", "9.9.9"):
            page = self.get("/profile", self.EMAIL).text
        self.assertIn('href="/static/betterjobs.css?v=9.9.9"', page)

    def test_ac4_every_class_the_templates_use_has_a_rule(self):
        sheet = C.sheet_classes(C.sheet_text())
        missing = {c: sorted(w) for c, w in C.used_classes().items() if c not in sheet and c not in HOOKS}
        self.assertEqual(missing, {})

    def test_ac5_the_fonts_are_self_hosted_with_their_licences(self):
        faces = C.font_faces(C.sheet_text())
        self.assertTrue(faces, "no @font-face in the stylesheet")
        for fam, style in REQUIRED_FAMILIES.items():
            with self.subTest(family=fam):
                mine = [f for f in faces if f["family"] == fam]
                self.assertTrue(mine, f"no @font-face for {fam}")
                if style:
                    self.assertTrue(any(f["style"] == style for f in mine), f"no {style} face for {fam}")
                key = fam.replace(" ", "").lower()
                licences = [p.name for p in C.FONTS.iterdir() if key in p.name.lower() and re.search(r"ofl|licen", p.name.lower())]
                self.assertTrue(licences, f"no licence file for {fam} in fonts/")
        for f in faces:
            for src in f["srcs"]:
                with self.subTest(font=src):
                    self.assertTrue(src.startswith("/fonts/"), f"{src} is not under the app's /fonts mount")
                    self.assertTrue((C.FONTS / src[len("/fonts/"):]).is_file())
                    self.assertEqual(self.client.get(src).status_code, 200)

    def test_ac13_no_old_font_and_no_calm_body_class(self):
        css = C.strip_comments(C.sheet_text())
        for name in ("Manrope", "Source Serif", "IBM Plex Mono", "Archivo"):
            self.assertNotIn(name.lower(), css.lower(), name)
        self.assertNotIn("opt-calm", css)
        self.assertNotIn("opt-calm", (C.TEMPLATES / "base.html").read_text(encoding="utf-8"))

    def test_ac14_every_font_face_swaps(self):
        faces = C.font_faces(C.sheet_text())
        self.assertTrue(faces)
        for f in faces:
            self.assertEqual(f["display"], "swap", f["family"])


if __name__ == "__main__":
    unittest.main()
