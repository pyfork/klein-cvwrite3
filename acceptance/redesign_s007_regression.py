"""REGRESSION A of redesign S-007: serving the fonts as woff2 changes nothing else. Covers AC-182. Passes before the work.

Guards what every page and the PDF render rely on: with Python's built-in type table only (and no .woff2), .css, .js,
.webp and .ttf answer as they do on main today, the stylesheet and script keep their types, and every TrueType file in
fonts/ (the three web sources and the CV fonts the render reads) is byte for byte unchanged.
senior-lead-Opus5.5-agent, 2026-11-04"""
import hashlib
import mimetypes
import unittest

import redesign_s007_common as S
from support import CVCase

# SHA-256 of every TrueType file in fonts/ on main when the slice was planned (2026-11-04, `57ecb35` and later).
TTF_SHA = {
    "Archivo-600-78.ttf": "7836bf03497d8d6aecca63fe4e75b05edb274c5b1260587ed0bf0995a5c07c7f",
    "Archivo-700-78.ttf": "e7aeadc6b9b4aebe8fec6486f1889066b95b7a52a04653383983a17d055a7c43",
    "Archivo-720-78.ttf": "9ab67e022d2ee603d29019a47add551bd02069b9c4b663115be00c346839f45f",
    "Archivo-760-78.ttf": "03ece95f16eac3e318e48c03e31e1576c325ae142cd8c4f04150c84f23440712",
    "Archivo-800-70.ttf": "996f349d24b55c65c8ebfc6893adaeecf32691ed86ed618d22a230400fb0f65c",
    "GeistMono-Variable.ttf": "d00e590b8eb3a59acc329b2d044fd143ae935090b7da33199ebee27cc7de8196",
    "IBMPlexMono-Medium.ttf": "a9b4c49bb299e05b5f6c481e7fb5e78943d2793249a0c8874ab574a2d1ea6755",
    "IBMPlexMono-Regular.ttf": "6a3412f058c7d8dfd9170c41e85ade48e5156ecb89356110ca57a0a27734af46",
    "IBMPlexMono-SemiBold.ttf": "d3c38e55c78f5b0f28009fddba4834ec503278936a5986032424c9bd2d23aa46",
    "LibreCaslonText-Italic-Variable.ttf": "60ca1a3aade61c8c381800ca85b9b2f0fb341d89ebe065e12cd6ec2ee2e53e54",
    "Manrope-400.ttf": "fb779e3ba6c78bb227ce3f5034f0e898bccf73d847bf525c225dcd357e45c0d4",
    "Manrope-600.ttf": "401df60733db819d002934b3b715aec3548a1eb971bec0daf0f0d449e5a07fa9",
    "Manrope-700.ttf": "25fcd92cc4d34dada66999d74fff367760f19a1b4beacc05b4f0a00708fc1431",
    "Manrope-800.ttf": "55bad97514b1873612c1151250b24f8146750bab99a0f34ff78950cc7bd65b22",
    "SchibstedGrotesk-Variable.ttf": "6ceeadf6be8e1fd7687011c7fa38ed0edd1abe967a0b73d97caec183552e823d",
    "SourceSerif4-400-Italic.ttf": "c98a2f800a8e4ca7ef51416936a5b5b9412f10acf323792f708c1223365dd467",
    "SourceSerif4-400.ttf": "c3cfc437d1fdc6c68c10cfbb3350e20e53aec79a023e96c125ecacab6cbd3292",
    "SourceSerif4-650.ttf": "185a257a0f28f64d0b7a8cebc4514f9d01632ed5dab95c6170ad2ca3dcd862dd",
}


class OtherThingsUnchanged(S.BareTypeTable, CVCase):
    def test_ac182_stylesheet_and_script_keep_their_types(self):
        css = self.client.get("/static/betterjobs.css")
        js = self.client.get("/static/upload.js")
        self.assertEqual(css.status_code, 200)
        self.assertEqual(js.status_code, 200)
        self.assertTrue(css.headers["content-type"].startswith("text/css"), css.headers["content-type"])
        self.assertTrue(js.headers["content-type"].startswith(("application/javascript", "text/javascript")),
                        js.headers["content-type"])

    def test_ac182_other_types_answer_as_before(self):
        builtin = S.bare_table()
        self.assertEqual(mimetypes.guess_type("a.webp")[0], "image/webp")  # slice 5's line
        for name in ("a.css", "a.js", "a.html", "a.ttf"):
            with self.subTest(name=name):
                self.assertEqual(mimetypes.guess_type(name), builtin.guess_type(name))

    def test_ac182_every_truetype_file_is_unchanged(self):
        self.assertEqual(sorted(p.name for p in S.FONTS.glob("*.ttf")), sorted(TTF_SHA))
        for name, sha in TTF_SHA.items():
            with self.subTest(font=name):
                self.assertEqual(hashlib.sha256((S.FONTS / name).read_bytes()).hexdigest(), sha, f"{name} changed")


if __name__ == "__main__":
    unittest.main()
