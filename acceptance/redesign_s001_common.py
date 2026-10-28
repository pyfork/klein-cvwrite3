"""Shared helpers for the redesign S-001 acceptance checks (plans/redesign-plan.md, Slice 1).

Locked with the checks. Three tools:
  - a small CSS reader (rules, declarations, @font-face, tokens), standard library only;
  - the real app's pages, rendered through the same test client the suite uses (fake stand-in data only);
  - a local server plus headless Chrome that loads those pages in iframes of exact widths and returns what a
    script measured (sizes, computed styles), so the layout rules are measured and not guessed.
senior-lead-Sonnet5.5-agent, 2026-10-28
"""
import http.server
import json
import mimetypes
import os
import re
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for p in (ROOT, ROOT / "tests"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

STATIC = ROOT / "app" / "static"
FONTS = ROOT / "fonts"
TEMPLATES = ROOT / "app" / "templates"
SHEET = STATIC / "betterjobs.css"
CHROME = os.environ.get("CVWRITE_CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


# --------------------------------------------------------------------------------------------- the stylesheet
def sheet_text():
    if not SHEET.exists():
        raise AssertionError("app/static/betterjobs.css does not exist yet")
    return SHEET.read_text(encoding="utf-8")


def strip_comments(css):
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def _skip(css, i, stops):
    """Index of the first char in `stops` at or after i, outside strings and parentheses."""
    depth, n = 0, len(css)
    while i < n:
        c = css[i]
        if c in "\"'":
            j = css.find(c, i + 1)
            i = n if j < 0 else j + 1
            continue
        if c == "(":
            depth += 1
        elif c == ")":
            depth = max(0, depth - 1)
        elif depth == 0 and c in stops:
            return i
        i += 1
    return n


def _close(css, i):
    """Index of the } that closes the { at i."""
    depth, n = 0, len(css)
    while i < n:
        c = css[i]
        if c in "\"'":
            j = css.find(c, i + 1)
            i = n if j < 0 else j + 1
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return n


def rules(css, chain=()):
    """Every rule as (at_rules_around_it, prelude, body). @media and @supports are entered; @font-face and
    @keyframes come back as rules of their own, with their own prelude."""
    css = strip_comments(css)
    out, i, n = [], 0, len(css)
    while i < n:
        while i < n and css[i].isspace():
            i += 1
        if i >= n:
            break
        j = _skip(css, i, "{;")
        if j >= n:
            break
        if css[j] == ";":
            out.append((chain, css[i:j].strip(), None))
            i = j + 1
            continue
        k = _close(css, j)
        prelude, body = css[i:j].strip(), css[j + 1:k]
        if prelude.startswith(("@media", "@supports", "@layer")):
            out.extend(rules(body, chain + (prelude,)))
        else:
            out.append((chain, prelude, body))
        i = k + 1
    return out


def decls(body):
    """[(property, value)] from a rule body."""
    out, i, n = [], 0, len(body)
    while i < n:
        j = _skip(body, i, ";")
        part = body[i:j]
        if ":" in part:
            k = part.index(":")
            out.append((part[:k].strip().lower(), part[k + 1:].strip()))
        i = j + 1
    return out


def tokens(css):
    """{--name: value} from every :root rule."""
    found = {}
    for chain, sel, body in rules(css):
        if body is not None and re.fullmatch(r":root(\s*,\s*:host)?", sel):
            for prop, val in decls(body):
                if prop.startswith("--"):
                    found[prop] = val
    return found


def without_urls(text):
    return re.sub(r"url\((?:\"[^\"]*\"|'[^']*'|[^)]*)\)", "url()", text)


def font_faces(css):
    """[{'family':..., 'style':..., 'weight':..., 'display':..., 'srcs':[...]}] from every @font-face."""
    faces = []
    for chain, sel, body in rules(css):
        if sel == "@font-face":
            d = dict(decls(body))
            faces.append({
                "family": d.get("font-family", "").strip("\"' "),
                "style": d.get("font-style", "normal"),
                "weight": d.get("font-weight", ""),
                "display": d.get("font-display", ""),
                "srcs": re.findall(r"url\(\s*[\"']?([^\"')]+)[\"']?\s*\)", d.get("src", "")),
            })
    return faces


# ------------------------------------------------------------------------------------------------- colours
def hex_rgb(h):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def luminance(rgb):
    def lin(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


# ------------------------------------------------------------------------------------ the real app's pages
def app_pages(case):
    """Render the app's pages through `case` (a tests.support.CVCase) and return {name: (html, who)}.
    who is 'user', 'owner' or 'out'. Fake stand-in data only."""
    from app import pause
    from tests.support import OWNER

    pages = {}

    def keep(name, resp, who):
        if resp.status_code == 200 and "<html" in resp.text:
            pages[name] = (resp.text, who)

    em, owner = case.EMAIL, OWNER
    run_id = case.start()          # a queued run: the CV bar says "A CV is being written"
    for name, path, who in [
        ("profile", "/profile", "user"), ("generate", "/generate", "user"), ("credits", "/credits", "user"),
        ("account", "/account", "user"), ("applications", "/applications", "user"), ("reports", "/reports", "user"),
        ("report", "/report?page=/profile", "user"), ("run", f"/runs/{run_id}", "user"), ("ad", f"/runs/{run_id}/ad", "user"),
        ("admin", "/admin", "owner"),
    ]:
        keep(name, case.get(path, owner if who == "owner" else em), who)
    for name, path in [("signin", "/signin"), ("privacy", "/privacy"), ("privacy_changes", "/privacy/changes"),
                       ("terms", "/terms"), ("deleted", "/deleted"), ("error_404", "/no-such-page")]:
        r = case.client.get(path)
        pages[name] = (r.text, "out") if "<html" in r.text else pages.get(name)
    # a user with no profile yet (the nav shows step 1 as "1"), one with a zero balance, one who has not agreed yet
    sam, lee = "sam@example.com", "lee@example.com"
    case.approve(sam)
    case.agree(sam)
    keep("generate_notready", case.get("/generate", sam), "user")
    with case.conn() as c:
        acct = c.execute("select account_id from allowed_users where email = %s", (sam,)).fetchone()["account_id"]
        for _ in range(2):
            rid = c.execute("insert into runs (account_id, ad_text, status) values (%s, %s, 'passed') returning id",
                            (acct, "x" * 300)).fetchone()["id"]
            c.execute("insert into credit_ledger (account_id, delta, kind, run_id) values (%s, -1, 'spend', %s)", (acct, rid))
    keep("credits_zero", case.get("/credits", sam), "user")
    case.approve(lee)
    keep("consent", case.get("/consent", lee), "user")
    r = case.post("/credits/buy", em, {"pack": "5"})
    if r.status_code == 303:
        keep("order", case.get(r.headers["location"], em), "user")
    keep("request", case.get("/request", "stranger@example.com"), "out")
    # 120 credits with 3 in use, the longest balance the shell shows
    from tests.support import MASTER
    max_ = "max@example.com"
    case.approve(max_)
    case.agree(max_)
    case.post("/profile", max_, {"master_text": MASTER.read_text(), "master_name": "master.md", "name": "Max Tan",
                                 "email": max_, "phone": "+60 12-345 6789", "location": "Shah Alam", "links": "", "standing_edits": ""})
    with case.conn() as c:
        acct = c.execute("select account_id from allowed_users where email = %s", (max_,)).fetchone()["account_id"]
        c.execute("insert into credit_ledger (account_id, delta, kind, expires_at) values (%s, 118, 'free', timestamp '2027-09-28')", (acct,))
    for _ in range(3):
        case.start(email=max_)
    keep("profile_heavy", case.get("/profile", max_), "user")
    # the owner as a user too: the nav then holds all six labels
    from app import access
    with case.conn() as c:
        access._approve(c, owner, "owner")
    case.agree(owner)
    case.post("/profile", owner, {"master_text": MASTER.read_text(), "master_name": "master.md", "name": "Owner Stand-in",
                                  "email": owner, "phone": "+60 12-345 6789", "location": "Shah Alam", "links": "", "standing_edits": ""})
    keep("owner_profile", case.get("/profile", owner), "owner")
    pages = {k: v for k, v in pages.items() if v}
    # the pause banner and the CV bar together, on a user page
    with case.conn() as c:
        pause.pause(c, "stand-in", "owner")
        c.execute("update system_pause set paused_at = now() - interval '5 hours' where resumed_at is null")
    keep("profile_paused", case.get("/profile", em), "user")
    with case.conn() as c:
        pause.resume(c)
    return pages


# ------------------------------------------------------------------------------- local server and Chrome
class Site:
    """Serves in-memory pages at /p/<name>.html, the real /static and /fonts, and acceptance/fixtures at /fx/."""

    def __init__(self, pages=None, block_fonts=False):
        self.pages = {k: (v[0] if isinstance(v, tuple) else v) for k, v in (pages or {}).items()}
        self.block_fonts = block_fonts
        site = self

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                path = self.path.split("?")[0]
                body, ctype, code = b"", "text/plain", 200
                if path.startswith("/p/") and path[3:-5] in site.pages and path.endswith(".html"):
                    body, ctype = site.pages[path[3:-5]].encode("utf-8"), "text/html; charset=utf-8"
                elif path.startswith("/static/") or path.startswith("/fonts/") or path.startswith("/fx/"):
                    base = {"static": STATIC, "fonts": FONTS, "fx": ROOT / "acceptance" / "fixtures"}[path.split("/")[1]]
                    f = (base / path.split("/", 2)[2]).resolve()
                    if (path.startswith("/fonts/") and site.block_fonts) or base.resolve() not in f.parents or not f.is_file():
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

    def add(self, name, html):
        self.pages[name] = html


HARNESS = """<!doctype html><meta charset="utf-8"><body style="margin:0"><pre id="out"></pre>
<script>
const WIDTHS = %(widths)s, HEIGHT = %(height)s, URLS = %(urls)s;
const MEASURE = async (doc, win, W) => { %(js)s };
async function main() {
  const out = {};
  for (const url of URLS) {
    out[url] = {};
    for (const w of WIDTHS) {
      const f = document.createElement('iframe');
      f.style.cssText = 'width:' + w + 'px;height:' + HEIGHT + 'px;border:0;display:block';
      f.src = url;
      document.body.appendChild(f);
      await new Promise(r => f.addEventListener('load', r));
      try { await f.contentWindow.document.fonts.ready; } catch (e) {}
      out[url][w] = await MEASURE(f.contentDocument, f.contentWindow, w);
      f.remove();
    }
  }
  document.getElementById('out').textContent = JSON.stringify(out);
}
main().catch(e => { document.getElementById('out').textContent = JSON.stringify({__error: String(e && e.stack || e)}); });
</script>"""


def measure(site, paths, widths, js, height=900):
    """Load each path in an iframe of each width and run `js` (the body of an async function of doc, win, W) in it.
    Returns {path: {width: whatever js returned}}. Raises AssertionError if Chrome or the script failed."""
    paths = [paths] if isinstance(paths, str) else list(paths)
    name = f"__h{abs(hash((tuple(paths), tuple(widths), js)))}"
    site.add(name, HARNESS % {"widths": json.dumps(list(widths)), "height": height, "urls": json.dumps(paths), "js": js})
    with tempfile.TemporaryDirectory() as tmp:
        cmd = [CHROME, "--headless=new", "--disable-gpu", "--no-first-run", f"--user-data-dir={tmp}/profile",
               "--virtual-time-budget=30000", "--dump-dom", site.url(f"/p/{name}.html")]
        try:
            done = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        except (OSError, subprocess.TimeoutExpired) as e:
            raise AssertionError(f"Chrome did not run: {e}")
    m = re.search(r'<pre id="out">(.*?)</pre>', done.stdout, re.S)
    if not m or not m.group(1).strip():
        raise AssertionError("the page measured nothing (Chrome output: %r)" % done.stdout[-300:])
    import html as _html
    data = json.loads(_html.unescape(m.group(1)))
    if "__error" in data:
        raise AssertionError("the measuring script failed: " + data["__error"])
    return {p: {int(w): v for w, v in by_w.items()} for p, by_w in data.items()}


def require_chrome():
    """A missing Chrome fails the check; it is never skipped."""
    if not Path(CHROME).exists():
        raise AssertionError(f"Chrome not found at {CHROME}")


# JS shared by the browser checks: "is the new stylesheet applied?" Resolved by one token it must define.
NEW_LOOK_JS = """
const bodyBg = win.getComputedStyle(doc.body).backgroundColor;
const looked = win.getComputedStyle(doc.documentElement).getPropertyValue('color-scheme').trim() === 'light'
  && bodyBg === 'rgb(242, 241, 237)';
"""


# ------------------------------------------------------------------------------- classes used by the pages
_ATTR = re.compile(r'class="((?:[^"{]|\{\{.*?\}\}|\{%.*?%\})*)"', re.S)
_JINJA = re.compile(r"\{\{.*?\}\}|\{%.*?%\}", re.S)


def used_classes():
    """{class: {file, ...}} from every template's class="..." (words in plain text and string literals inside
    {{ }} and {% %}) and from upload.js's classList calls."""
    found = {}

    def add(name, where):
        if re.fullmatch(r"[A-Za-z_][\w-]*", name) and not name.endswith("-"):
            found.setdefault(name, set()).add(where)

    for f in sorted(TEMPLATES.glob("*.html")):
        text = re.sub(r"\{#.*?#\}", "", f.read_text(encoding="utf-8"), flags=re.S)
        for m in _ATTR.finditer(text):
            value = m.group(1)
            for block in _JINJA.findall(value):
                for a, b in re.findall(r"'([^']*)'|\"([^\"]*)\"", block):
                    for w in (a or b).split():
                        add(w, f.name)
            for w in _JINJA.sub(" \0 ", value).split():
                if "\0" not in w:
                    add(w, f.name)
    js = (STATIC / "upload.js").read_text(encoding="utf-8")
    for w in re.findall(r"classList\.\w+\(\"([^\"]+)\"", js):
        add(w, "upload.js")
    return found


def sheet_classes(css):
    """Every class named in a selector of a style rule."""
    names = set()
    for chain, sel, body in rules(css):
        if body is not None and not sel.startswith("@"):
            names.update(re.findall(r"\.([A-Za-z_][\w-]*)", re.sub(r"\[[^\]]*\]", "", sel)))
    return names
