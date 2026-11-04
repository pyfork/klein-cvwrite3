"""CHECK 1 of redesign S-007: the three web faces load woff2 files that are their TrueType sources cut to the kept set.
Covers AC-178 and AC-179. Fails before the work: there are no woff2 files and the stylesheet links the TrueType files.
Needs fontTools (acceptance/redesign-s007-requirements.txt, which the wrapper installs).
senior-lead-Opus5.5-agent, 2026-11-04"""
import mimetypes
import re
import unittest

import redesign_s007_common as S
import redesign_s001_common as C
from support import CVCase


def faces_by_family():
    """{family: [(style, weight, display, raw src)]} from every @font-face in the stylesheet."""
    out = {}
    for chain, sel, body in C.rules(C.strip_comments(C.sheet_text())):
        if sel == "@font-face":
            d = dict(C.decls(body))
            out.setdefault(d.get("font-family", "").strip("\"' "), []).append(
                (d.get("font-style", "normal"), d.get("font-weight", ""), d.get("font-display", ""), d.get("src", "")))
    return out


class TheBareTableIsBare(unittest.TestCase):
    def test_control_the_bare_table_does_not_know_woff2(self):
        db = S.bare_table()
        self.assertEqual(db.guess_type("a.woff2"), (None, None))
        self.assertEqual(db.guess_type("a.css")[0], "text/css")


class FacesLoadWoff2(S.BareTypeTable, CVCase):
    def test_ac178_each_face_has_one_woff2_source_and_keeps_its_settings(self):
        faces = faces_by_family()
        for family, (woff2, ttf, style, weight) in S.FACES.items():
            with self.subTest(family=family):
                self.assertEqual(len(faces.get(family, [])), 1, f"{family}: expected one @font-face")
                f_style, f_weight, f_display, src = faces[family][0]
                self.assertEqual(f_style, style)
                self.assertEqual(f_weight, weight)
                self.assertEqual(f_display, "swap")
                urls = re.findall(r"url\(\s*[\"']?([^\"')]+)[\"']?\s*\)", src)
                self.assertEqual(urls, [f"/fonts/{woff2}"], src)
                self.assertRegex(src, r"format\(\s*[\"']woff2[\"']\s*\)")
                self.assertNotIn(".ttf", src)

    def test_ac178_each_woff2_is_served_as_font_woff2(self):
        for family, (woff2, *_rest) in S.FACES.items():
            with self.subTest(font=woff2):
                r = self.client.get(f"/fonts/{woff2}")
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.headers["content-type"], "font/woff2")
                self.assertEqual(r.content, (S.FONTS / woff2).read_bytes())
                self.assertEqual(r.content[:4], b"wOF2")
        self.assertEqual(mimetypes.guess_type("a.woff2")[0], "font/woff2", "the app's table does not know .woff2")


class TheCutIsFaithful(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from fontTools.ttLib import TTFont  # noqa: F401
            from fontTools.pens.recordingPen import DecomposingRecordingPen  # noqa: F401
        except ImportError as e:
            raise AssertionError(f"fontTools is needed (acceptance/redesign-s007-requirements.txt): {e}")

    def load(self, name):
        from fontTools.ttLib import TTFont
        path = S.FONTS / name
        self.assertTrue(path.is_file(), f"fonts/{name} does not exist")
        return TTFont(str(path))

    def test_ac179_the_kept_set_holds_latin_and_the_apps_text(self):
        kept = S.kept_set()
        self.assertEqual(sorted(S.REQUIRED - kept), [], "the kept set misses part of U+0020-007E or U+00A0-017F")
        used = S.app_text_chars()
        for family, (woff2, ttf, *_rest) in S.FACES.items():
            src = set(self.load(ttf).getBestCmap())
            missing = {f"U+{cp:04X} ({used[cp]})" for cp in used if cp in src and cp not in kept}
            self.assertEqual(sorted(missing), [], f"{family}: the app uses these and the kept set drops them")

    def test_ac179_each_woff2_holds_exactly_the_kept_characters_with_the_same_outlines(self):
        from fontTools.pens.recordingPen import DecomposingRecordingPen
        kept = S.kept_set()
        for family, (woff2, ttf, *_rest) in S.FACES.items():
            with self.subTest(family=family):
                src, cut = self.load(ttf), self.load(woff2)
                self.assertEqual(cut.flavor, "woff2")
                src_map, cut_map = src.getBestCmap(), cut.getBestCmap()
                self.assertEqual(sorted(set(cut_map)), sorted(cp for cp in src_map if cp in kept))
                src_glyphs, cut_glyphs = src.getGlyphSet(), cut.getGlyphSet()
                for cp in sorted(cut_map):
                    a, b = DecomposingRecordingPen(src_glyphs), DecomposingRecordingPen(cut_glyphs)
                    src_glyphs[src_map[cp]].draw(a)
                    cut_glyphs[cut_map[cp]].draw(b)
                    self.assertEqual(a.value, b.value, f"{family}: U+{cp:04X} draws differently")
                    self.assertEqual(src["hmtx"][src_map[cp]][0], cut["hmtx"][cut_map[cp]][0], f"U+{cp:04X} width")

    def test_ac179_the_weight_axis_is_the_sources(self):
        for family, (woff2, ttf, *_rest) in S.FACES.items():
            with self.subTest(family=family):
                axes = lambda f: [(a.axisTag, a.minValue, a.defaultValue, a.maxValue) for a in f["fvar"].axes]  # noqa: E731
                src, cut = self.load(ttf), self.load(woff2)
                self.assertEqual(axes(cut), axes(src))
                self.assertIn("gvar", cut, f"{family}: the cut lost its variations")

    def test_ac179_each_source_keeps_its_licence(self):
        for family, (woff2, ttf, *_rest) in S.FACES.items():
            with self.subTest(family=family):
                self.assertTrue((S.FONTS / ttf).is_file(), f"fonts/{ttf} is gone")
                licence = S.FONTS / (ttf.split("-")[0] + "-OFL.txt")
                self.assertTrue(licence.is_file(), f"fonts/{licence.name} is gone")


if __name__ == "__main__":
    unittest.main()
