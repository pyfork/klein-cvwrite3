"""Published privacy notices never change. Publishing a version means adding its hash here."""
import json
import re
import unittest

from app import notices

# version -> {lang: sha256 of notices/vX.Y.<lang>.md}. Add a version when its status becomes "published".
PINNED = {}


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
                self.assertTrue(section(notices.text(v.version, lang), "In short"), f"v{v.version}.{lang} has no 'In short'")


if __name__ == "__main__":
    unittest.main()
