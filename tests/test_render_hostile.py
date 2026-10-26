"""Senior Q7: what a malicious ad can do to the render. A URL the model writes (steerable by the ad) must
not break out of its href, and the render runs no JavaScript (the page's CSP; a Chrome flag can't do it,
see render/build_cv.py page()). Run: python3 -m unittest discover tests"""
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from render import build_cv
from tests.render_env import needs_render

HOSTILE = [
    'https://a.com/"style="display:none',
    "https://a.com/'onmouseover='x",
    'https://a.com/"><span style="font-size:0">SQL Kubernetes</span><a href="',
]
MD = "# Test Person\n\n## SUMMARY\nvisible words here\n"
SCRIPT = "<script>document.body.textContent = 'JSRAN'</script>"
CSP = """<meta http-equiv="Content-Security-Policy" content="script-src 'none'">"""


class Escaping(unittest.TestCase):
    def assert_one_clean_link(self, out):
        self.assertLessEqual(out.count("<a "), 1)         # a URL with spaces is left as plain text
        self.assertEqual(out.count('"'), 2 * out.count("<a "))  # only the href's own quotes
        self.assertNotIn("'", out)
        self.assertNotIn("<span", out)

    def test_inline_link(self):
        for url in HOSTILE:
            with self.subTest(url=url):
                self.assert_one_clean_link(build_cv.inline(f"[site]({url})"))

    def test_featured_project_link(self):
        for url in HOSTILE:
            with self.subTest(url=url):
                _, body = build_cv.convert(f"# Test Person\n\n## FEATURED PROJECT | {url.removeprefix('https://')}\ntext\n")
                h2 = body.split('<section class="box"><h2>', 1)[1].split("</h2>", 1)[0]
                self.assert_one_clean_link(h2.split("</span>", 1)[1])

    def test_only_http_links(self):
        self.assertNotIn("<a ", build_cv.inline("[x](javascript:alert(1))"))
        _, body = build_cv.convert("# T\n\n## FEATURED PROJECT | javascript:alert(1)\ntext\n")
        self.assertIn('href="https://javascript:alert(1)"', body)  # a dead https link, never a script URL


@needs_render
class NoJavaScript(unittest.TestCase):
    def render_text(self, csp):
        real = build_cv.page

        def page(*a, **kw):
            out = real(*a, **kw).replace("</body>", SCRIPT + "</body>")
            return out if csp else out.replace(CSP, "")
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(build_cv, "page", page):
            pdf = Path(tmp) / "cv.pdf"
            build_cv.render_pdf(MD, pdf)
            return subprocess.run(["pdftotext", str(pdf), "-"], capture_output=True, text=True, check=True).stdout

    def test_the_check_can_see_javascript(self):
        self.assertIn("JSRAN", self.render_text(csp=False))

    def test_the_csp_stops_it(self):
        self.assertIn(CSP, build_cv.page("t", "<p>x</p>"))
        text = self.render_text(csp=True)
        self.assertNotIn("JSRAN", text)
        self.assertIn("visible words here", text)


if __name__ == "__main__":
    unittest.main()
