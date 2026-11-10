"""Shared helpers for the redesign S-009 acceptance checks (plans/redesign-plan.md, Slice 9: the home's frame, header and hero).

Locked with the checks. Builds on S-001's CSS reader and S-003's colour script, and adds:
  - the app built with the setting `home` on (CVWRITE_HOME=on, slice 8's AC-186), so `/` serves the home to a visitor
    with no session cookie; before the work that is slice 8's placeholder, which holds no header links and no hero;
  - a local server for that page, the real /static and /fonts, with fonts or art able to fail (AC-162, AC-171);
  - headless Chrome loading the home in iframes of exact widths, light or dark. Each iframe is sandboxed without
    `allow-scripts`, so the page is measured as it shows with scripts off: what slice 9 builds, and what stays true
    after slice 12 adds the home's scripts;
  - the words v2 shows in its header and hero, read out of v2 (acceptance/fixtures/s009_v2_text.json).
The checks find the paper pieces (the designer's comment above AC-100) by `data-paper` on each piece's outer element:
the one markup hook these checks ask of the build.
senior-lead-Opus5.5-agent, 2026-11-07 (drafted for the top half); 2026-11-08 (cut to slice 9: the frame, header and hero)
"""
import dataclasses
import html as _html
import http.server
import json
import mimetypes
import re
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path

import redesign_s001_common as C
import redesign_s003_common as D

ROOT = C.ROOT
FIX = json.loads((ROOT / "acceptance" / "fixtures" / "s009_v2_text.json").read_text(encoding="utf-8"))
LATER_IDS = ("demo", "how", "apps", "price", "privacy", "faq")   # sections slices 10 and 11 build; links to them wait for them
WIDTHS = sorted({*range(320, 1441, 40), 390, 768, 1024, 1440})   # AC-171: every 40 px or less, and the named ones

from fastapi.testclient import TestClient   # noqa: E402  (after C put the repo on sys.path)
from tests.support import AppCase, ORIGIN   # noqa: E402


class HomeCase(AppCase):
    """AppCase with the setting `home` on (dev)."""

    def setUp(self):
        super().setUp()
        self.client.close()
        self.settings = dataclasses.replace(self.settings, home=True)   # slice 8's setting
        from app.main import create_app
        self.app = create_app(self.settings, mail=self.outbox)
        self.client = TestClient(self.app, base_url=ORIGIN, follow_redirects=False)

    def runTest(self):
        pass


_home = {}


def home_html():
    """The home as a visitor with no session cookie gets it, with the setting on. Rendered once per run."""
    if "html" not in _home:
        case = HomeCase()
        case.setUp()
        try:
            r = case.client.get("/")
            if r.status_code != 200 or "<html" not in r.text:
                raise AssertionError(f"/ with the setting on gave {r.status_code}, not the home")
            _home["html"] = r.text
        finally:
            case.tearDown()
    return _home["html"]


def linked_sheets(page):
    """The text of every local stylesheet the page links (the decision on slice 9: the checks never name a file)."""
    out = []
    for href in re.findall(r'<link[^>]+rel="stylesheet"[^>]*href="([^"]+)"', page) + \
            re.findall(r'<link[^>]+href="([^"]+)"[^>]*rel="stylesheet"', page):
        path = href.split("?")[0]
        if not path.startswith("/static/"):
            raise AssertionError(f"the home links a stylesheet outside /static: {href}")
        out.append((path, (C.STATIC / path[len("/static/"):]).read_text(encoding="utf-8")))
    if not out:
        raise AssertionError("the home links no stylesheet")
    return out


def norm(s):
    return re.sub(r"\s+", " ", s or "").strip()


def squash(s):
    return re.sub(r"\s+", "", s or "")


class Site:
    """Serves the home at /p/home.html (and harness pages), the real /static and /fonts. block: 'fonts' or 'art'."""

    def __init__(self, page, block=None):
        self.pages = {"home": page}
        site = self

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                path = self.path.split("?")[0]
                body, ctype, code = b"", "text/plain", 200
                if path.startswith("/p/") and path.endswith(".html") and path[3:-5] in site.pages:
                    body, ctype = site.pages[path[3:-5]].encode("utf-8"), "text/html; charset=utf-8"
                elif path.startswith(("/static/", "/fonts/")):
                    base = C.STATIC if path.startswith("/static/") else C.FONTS
                    f = (base / path.split("/", 2)[2]).resolve()
                    blocked = (block == "fonts" and path.startswith("/fonts/")) or \
                              (block == "art" and path.startswith("/static/art/"))
                    if blocked or base.resolve() not in f.parents or not f.is_file():
                        code = 404
                    else:
                        body, ctype = f.read_bytes(), mimetypes.guess_type(str(f))[0] or "application/octet-stream"
                else:
                    code = 404
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.port = self.httpd.server_address[1]

    def __enter__(self):
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *a):
        self.httpd.shutdown()
        self.httpd.server_close()

    def url(self, path):
        return f"http://127.0.0.1:{self.port}{path}"


HARNESS = """<!doctype html><meta charset="utf-8"><body style="margin:0"><pre id="out"></pre>
<script>
const SIZES = %(sizes)s;
const MEASURE = async (doc, win, W, H) => { %(js)s };
async function main() {
  const out = {};
  for (const [w, h] of SIZES) {
    const f = document.createElement('iframe');
    f.setAttribute('sandbox', 'allow-same-origin');   /* scripts off inside the page */
    f.style.cssText = 'width:' + w + 'px;height:' + h + 'px;border:0;display:block';
    f.src = '/p/home.html';
    document.body.appendChild(f);
    await new Promise(r => f.addEventListener('load', r));
    try { await f.contentWindow.document.fonts.ready; } catch (e) {}
    await new Promise(r => setTimeout(r, 50));
    out[w + 'x' + h] = await MEASURE(f.contentDocument, f.contentWindow, w, h);
    f.remove();
  }
  document.getElementById('out').textContent = JSON.stringify(out);
}
main().catch(e => { document.getElementById('out').textContent = JSON.stringify({__error: String(e && e.stack || e)}); });
</script>"""


def measure(site, sizes, js, scheme="light"):
    """Load the home in a sandboxed iframe of each (width, height) and run `js` (the body of an async function of
    doc, win, W, H). Returns {(w, h): result}. scheme: 'light' or 'dark' (the device's theme)."""
    C.require_chrome()
    sizes = [(s, 900) if isinstance(s, int) else tuple(s) for s in sizes]
    name = f"__h{abs(hash((tuple(sizes), js, scheme)))}"
    site.pages[name] = HARNESS % {"sizes": json.dumps(sizes), "js": D.COLOUR_JS + VIS_JS + js}
    with tempfile.TemporaryDirectory() as tmp:
        cmd = [C.CHROME, "--headless=new", "--disable-gpu", "--no-first-run", f"--user-data-dir={tmp}/profile",
               f"--blink-settings=preferredColorScheme={D.SCHEME[scheme]}", "--hide-scrollbars",
               "--virtual-time-budget=60000", "--dump-dom", site.url(f"/p/{name}.html")]
        try:
            done = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        except (OSError, subprocess.TimeoutExpired) as e:
            raise AssertionError(f"Chrome did not run: {e}")
    m = re.search(r'<pre id="out">(.*?)</pre>', done.stdout, re.S)
    if not m or not m.group(1).strip():
        raise AssertionError("the page measured nothing (Chrome output: %r)" % done.stdout[-300:])
    data = json.loads(_html.unescape(m.group(1)))
    if "__error" in data:
        raise AssertionError("the measuring script failed: " + data["__error"])
    return {tuple(int(x) for x in k.split("x")): v for k, v in data.items()}


# Helpers every measuring script gets (after S-003's COLOUR_JS: cs, rgb, ratio, bgOf).
VIS_JS = r"""
const T = e => (e && e.textContent || '').replace(/\s+/g, ' ').trim();
const SQ = s => (s || '').replace(/\s+/g, '');
const shown = e => { if (!e || !e.getClientRects().length) return false;
  for (let n = e; n && n.nodeType === 1; n = n.parentElement) { const s = cs(n); if (s.visibility === 'hidden' || s.display === 'none' || +s.opacity === 0) return false; }
  const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
const box = e => { const r = e.getBoundingClientRect(); return {x: r.left + win.scrollX, y: r.top + win.scrollY, w: r.width, h: r.height}; };
const paper = e => !!e.closest('[data-paper]');
const ownText = e => [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
const leafWith = (root, text) => [...root.querySelectorAll('*')].filter(e => T(e) === text && ![...e.children].some(c => T(c) === text));
const shownText = (root, text) => leafWith(root, text).some(shown);
const focusables = root => [...root.querySelectorAll('a[href], button, input, select, textarea, summary, [tabindex]')]
  .filter(e => e.tabIndex >= 0 && !e.disabled && shown(e));
const heads = doc => [...doc.querySelectorAll('h1, h2')].filter(shown);
const section = (doc, title) => { const h = heads(doc).find(x => T(x) === title); return h && h.closest('section'); };
const header = doc => doc.querySelector('body > header, header');
"""
