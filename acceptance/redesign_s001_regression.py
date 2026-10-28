"""REGRESSION A, B and C of redesign S-001: what the slice could break and must not. All three pass before the work.
A (AC-8): the shell keeps its parts. B (AC-7): the CV PDF render and its fonts are untouched. C (AC-6): no page or
stylesheet asks another host for a stylesheet, script, font or image.
senior-lead-Sonnet5.5-agent, 2026-10-28"""
import hashlib
import re
import subprocess
import sys
import unittest

import redesign_s001_common as C
from support import CVCase

# SHA-256 of every file in fonts/ on main when the slice was planned. The PDF render reads these by name.
FONT_SHA = {
    "Archivo-600-78.ttf": "7836bf03497d8d6aecca63fe4e75b05edb274c5b1260587ed0bf0995a5c07c7f",
    "Archivo-700-78.ttf": "e7aeadc6b9b4aebe8fec6486f1889066b95b7a52a04653383983a17d055a7c43",
    "Archivo-720-78.ttf": "9ab67e022d2ee603d29019a47add551bd02069b9c4b663115be00c346839f45f",
    "Archivo-760-78.ttf": "03ece95f16eac3e318e48c03e31e1576c325ae142cd8c4f04150c84f23440712",
    "Archivo-800-70.ttf": "996f349d24b55c65c8ebfc6893adaeecf32691ed86ed618d22a230400fb0f65c",
    "Archivo-OFL.txt": "108b4e57c9c796d3d38d0428ca7ee39de47ad93187302718d9b2d8864b9b716b",
    "IBMPlexMono-Medium.ttf": "a9b4c49bb299e05b5f6c481e7fb5e78943d2793249a0c8874ab574a2d1ea6755",
    "IBMPlexMono-OFL.txt": "7e6b2818edbd8f6a01ae80641cc8f16a51080d08fb4e532be3a0b6f74adb07da",
    "IBMPlexMono-Regular.ttf": "6a3412f058c7d8dfd9170c41e85ade48e5156ecb89356110ca57a0a27734af46",
    "IBMPlexMono-SemiBold.ttf": "d3c38e55c78f5b0f28009fddba4834ec503278936a5986032424c9bd2d23aa46",
    "Manrope-400.ttf": "fb779e3ba6c78bb227ce3f5034f0e898bccf73d847bf525c225dcd357e45c0d4",
    "Manrope-600.ttf": "401df60733db819d002934b3b715aec3548a1eb971bec0daf0f0d449e5a07fa9",
    "Manrope-700.ttf": "25fcd92cc4d34dada66999d74fff367760f19a1b4beacc05b4f0a00708fc1431",
    "Manrope-800.ttf": "55bad97514b1873612c1151250b24f8146750bab99a0f34ff78950cc7bd65b22",
    "Manrope-OFL.txt": "58172e0c0fac2cda8a37b348164bb55e44b0e69051e557e92b1d3f6910141f7b",
    "SourceSerif4-400-Italic.ttf": "c98a2f800a8e4ca7ef51416936a5b5b9412f10acf323792f708c1223365dd467",
    "SourceSerif4-400.ttf": "c3cfc437d1fdc6c68c10cfbb3350e20e53aec79a023e96c125ecacab6cbd3292",
    "SourceSerif4-650.ttf": "185a257a0f28f64d0b7a8cebc4514f9d01632ed5dab95c6170ad2ca3dcd862dd",
    "SourceSerif4-OFL.txt": "5f94c3fd3a23131a417ab5a0c8452de57e70c3cfb9f604d88241f7065ebf9fd9",
}
# From checks/render_check.py on the Mac that the deploy runbook compares with sk24, 2026-10-28.
FINGERPRINT = ("pages=2 fonts=Archivocvw-600-78,Archivocvw-700-78,Archivocvw-720-78,Archivocvw-760-78,Archivocvw-800-70,"
               "IBMPlexMono-Regular,IBMPlexMono-SemiBold,SourceSerif4cvw-400-12,SourceSerif4cvw-400-12-Italic,SourceSerif4cvw-650-12 "
               "text=9ae8203743da6831")


class Unbroken(CVCase):
    def test_a_the_shell_keeps_its_parts(self):
        """AC-8"""
        pages = C.app_pages(self)
        for name in ("profile", "profile_paused", "credits_zero"):
            html = pages[name][0]
            with self.subTest(page=name):
                self.assertRegex(html, r'<a[^>]+href="#main"')
                self.assertIn('id="main"', html)
                self.assertRegex(html, r'href="/credits"[^>]*>(?s:.*?)(earliest expire|buy more)')
                hrefs = re.findall(r'<nav[^>]*>(.*?)</nav>', html, re.S)
                self.assertEqual(len(hrefs), 1)
                self.assertEqual(re.findall(r'href="(/[a-z]+)"', hrefs[0]), ["/profile", "/generate", "/applications", "/credits", "/account"])
                for text in ("Report a problem", "Your reports", "Privacy notice", "Terms", "Sign out"):
                    self.assertIn(text, html)
                self.assertRegex(html, r'<form[^>]+action="/signout"')
                self.assertRegex(html, r">v\d+\.\d+\.\d+<")
        self.assertIn("Generating is paused", pages["profile_paused"][0])
        self.assertIn("Paused since", pages["profile_paused"][0])
        self.assertRegex(pages["profile"][0], r"A CV is being written:|Your CV is ready:")
        self.assertIn('href="/admin"', pages["owner_profile"][0])
        out = pages["signin"][0]
        self.assertNotIn("<nav", out)
        self.assertNotIn('href="/credits"', out)
        for text in ("Privacy notice", "Terms"):
            self.assertIn(text, out)
        self.assertNotIn("Sign out", out)

    def test_b_the_cv_pdf_and_its_fonts_are_untouched(self):
        """AC-7"""
        for name, sha in FONT_SHA.items():
            with self.subTest(font=name):
                f = C.FONTS / name
                self.assertTrue(f.is_file(), f"{name} is gone")
                self.assertEqual(hashlib.sha256(f.read_bytes()).hexdigest(), sha, f"{name} changed")
        self.assertNotRegex((C.ROOT / "render" / "build_cv.py").read_text(encoding="utf-8"), r"app/static|betterjobs|calm\.css")
        done = subprocess.run([sys.executable, str(C.ROOT / "checks" / "render_check.py")], capture_output=True, text=True, timeout=170)
        self.assertEqual(done.returncode, 0, done.stdout[-400:] + done.stderr[-400:])
        self.assertIn("RESULT: PASS", done.stdout)
        got = re.search(r"^FINGERPRINT (.*)$", done.stdout, re.M)
        self.assertTrue(got, "no fingerprint printed")
        self.assertEqual(got.group(1).strip(), FINGERPRINT)

    def test_c_nothing_asks_another_host(self):
        """AC-6"""
        offhost = re.compile(r"^(?:https?:)?//", re.I)
        pages = C.app_pages(self)
        for name, (html, who) in pages.items():
            with self.subTest(page=name):
                for m in re.finditer(r"<(link|script|img|source|iframe|video|audio|embed|object)\b([^>]*)>", html, re.I):
                    for url in re.findall(r"\b(?:href|src|srcset|data)=\"([^\"]*)\"", m.group(2)):
                        self.assertFalse(offhost.match(url.strip()), f"<{m.group(1)}> asks {url}")
                self.assertNotRegex(html, r"@import\s+(?:url\()?[\"']?(?:https?:)?//")
        css = C.SHEET.read_text(encoding="utf-8") if C.SHEET.exists() else (C.STATIC / "calm.css").read_text(encoding="utf-8")
        for u in re.findall(r"url\(\s*[\"']?([^\"')]+)", css):
            self.assertFalse(offhost.match(u.strip()), f"the stylesheet asks {u[:60]}")
        self.assertNotRegex(css, r"@import\s+(?:url\()?[\"']?(?:https?:)?//")


if __name__ == "__main__":
    unittest.main()
