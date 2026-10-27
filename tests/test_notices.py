"""Published privacy notices never change. Publishing a version means adding its hash here."""
import json
import re
import unittest

from app import i18n, notices

# version -> {lang: sha256 of notices/vX.Y.<lang>.md}. Add a version when its status becomes "published".
PINNED = {
    "1.0": {
        "en": "c8f4662b8e8bc21e3a56f80538fa3e5da688dcd451b21e09b76894e5cdecd551",
        "ms": "5281e2c2f0346c1fc5b6c9756ddb71086c1014fd3df958331b01b1b150a36c1c",
    },
    "1.1": {
        "en": "5be2197ce43bbb2dd9a06c5f3a89d25d73440723e842f0fa144465b997ae81bd",
        "ms": "494cd40f9098cbd6bbd64754f3e6d8e232b63bf97ff722d64b087857c2aabd57",
    },
}


class Notices(unittest.TestCase):
    def test_published_files_match_their_pinned_hash(self):
        for v in notices.versions():
            if v.status != "published":
                continue
            self.assertIn(v.version, PINNED, f"v{v.version} is published but its hash isn't pinned")
            for lang in notices.langs(v.version):
                self.assertEqual(notices.text_hash(v.version, lang), PINNED[v.version].get(lang),
                                 f"notices/v{v.version}.{lang}.md changed after publishing; make a new version instead")

    def test_every_pin_is_a_published_version(self):
        published = {v.version for v in notices.versions() if v.status == "published"}
        self.assertLessEqual(set(PINNED), published)

    def test_versions_file(self):
        raw = json.loads((notices.NOTICES / "versions.json").read_text())
        seen = set()
        for v in raw:
            self.assertRegex(v["version"], r"^\d+\.\d+$")
            self.assertNotIn(v["version"], seen)
            seen.add(v["version"])
            self.assertIn(v["status"], ("draft", "published"))
            self.assertRegex(v["date"], r"^\d{4}-\d{2}-\d{2}$")
            self.assertTrue(v["what"] and v["why"])
            self.assertTrue(notices.path(v["version"], "en").exists(), f"v{v['version']} has no English text")

    def test_every_version_has_the_summary(self):
        from app.markdown import section
        for v in notices.versions():
            for lang in notices.langs(v.version):
                heading = i18n.strings(lang)["summary_heading"]
                self.assertTrue(section(notices.text(v.version, lang), heading), f"v{v.version}.{lang} has no '{heading}'")


if __name__ == "__main__":
    unittest.main()


class Malay(unittest.TestCase):
    def test_same_shape_and_numbers_as_the_english(self):
        """Every period, count and version is a promise: the Malay must carry exactly the same ones."""
        for v in notices.versions():
            if "ms" not in notices.langs(v.version):
                continue
            en, ms = notices.text(v.version, "en"), notices.text(v.version, "ms")
            for pattern in (r"(?m)^## ", r"(?m)^- ", r"\d+"):
                self.assertEqual(sorted(re.findall(pattern, en)), sorted(re.findall(pattern, ms)), (v.version, pattern))
            for kept in ("privacy@puascari.com", "KIP ADVISORS", "Amazon Web Services", "Anthropic", "Cloudflare", "DigitalOcean"):
                self.assertEqual(en.count(kept), ms.count(kept), kept)

    def test_both_languages_have_every_string(self):
        self.assertEqual(set(i18n.STRINGS["en"]), set(i18n.STRINGS["ms"]))
