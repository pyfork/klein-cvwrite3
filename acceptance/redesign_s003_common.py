"""Shared helpers for the redesign S-003 acceptance checks (plans/redesign-plan.md, Slice 3: dark mode).

Locked with the checks. Builds on S-001's helpers (the CSS reader, the real pages, the local server) and adds:
  - Chrome told which theme the device asks for (`--blink-settings=preferredColorScheme`: 0 dark, 1 light,
    2 no preference), so a check never depends on the machine's own setting;
  - the dark block read out of the stylesheet.
senior-lead-Opus5.5-agent, 2026-10-29
"""
import html as _html
import json
import re
import subprocess
import tempfile

import redesign_s001_common as C

SCHEME = {"dark": 0, "light": 1, "none": 2}
DARK_MEDIA = re.compile(r"@media\s*\(\s*prefers-color-scheme\s*:\s*dark\s*\)\s*$")


def measure(site, paths, widths, js, scheme, height=900):
    """C.measure with the device's theme set: scheme is 'dark', 'light' or 'none'."""
    paths = [paths] if isinstance(paths, str) else list(paths)
    name = f"__d{abs(hash((tuple(paths), tuple(widths), js, scheme, height)))}"
    site.add(name, C.HARNESS % {"widths": json.dumps(list(widths)), "height": height, "urls": json.dumps(paths), "js": js})
    with tempfile.TemporaryDirectory() as tmp:
        cmd = [C.CHROME, "--headless=new", "--disable-gpu", "--no-first-run", f"--user-data-dir={tmp}/profile",
               f"--blink-settings=preferredColorScheme={SCHEME[scheme]}",
               "--virtual-time-budget=30000", "--dump-dom", site.url(f"/p/{name}.html")]
        try:
            done = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        except (OSError, subprocess.TimeoutExpired) as e:
            raise AssertionError(f"Chrome did not run: {e}")
    m = re.search(r'<pre id="out">(.*?)</pre>', done.stdout, re.S)
    if not m or not m.group(1).strip():
        raise AssertionError("the page measured nothing (Chrome output: %r)" % done.stdout[-300:])
    data = json.loads(_html.unescape(m.group(1)))
    if "__error" in data:
        raise AssertionError("the measuring script failed: " + data["__error"])
    return {p: {int(w): v for w, v in by_w.items()} for p, by_w in data.items()}


def dark_rules(css):
    """[(chain, selector, body)] of every rule inside @media (prefers-color-scheme: dark)."""
    return [(ch, sel, b) for ch, sel, b in C.rules(css) if any(DARK_MEDIA.match(a.strip()) for a in ch)]


def dark_tokens(css):
    """{--name: value} from the :root rules inside @media (prefers-color-scheme: dark)."""
    found = {}
    for ch, sel, body in dark_rules(css):
        if body is not None and re.fullmatch(r":root", sel):
            found.update((p, v) for p, v in C.decls(body))
    return found


def light_root(css):
    """{property: value} from the :root rules outside any @media (the light tokens)."""
    found = {}
    for ch, sel, body in C.rules(css):
        if not ch and body is not None and re.fullmatch(r":root(\s*,\s*:host)?", sel):
            found.update(C.decls(body))
    return found


# the colour of the first opaque box behind e, and contrast, for the browser checks
COLOUR_JS = r"""
const cs = (e, p) => win.getComputedStyle(e, p || null);
const rgb = c => (c.match(/[\d.]+/g) || []).map(Number);
const lum = c => { const [r, g, b] = rgb(c).slice(0, 3).map(v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, o) => o - p); return (x + 0.05) / (y + 0.05); };
const opaque = c => { const m = rgb(c); return (m[3] === undefined ? 1 : m[3]) > 0.5; };
const bgOf = e => { for (let n = e; n; n = n.parentElement) { if (opaque(cs(n).backgroundColor)) return cs(n).backgroundColor; } return cs(doc.documentElement).backgroundColor; };
const lowText = root => { const low = []; for (const e of root.querySelectorAll('*')) { if (e.closest(':disabled, [disabled], .qr')) continue;
  if (!e.getClientRects().length || cs(e).visibility === 'hidden') continue;
  if (![...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())) continue;
  const r = ratio(cs(e).color, bgOf(e)); if (r < 4.5) low.push([e.id || e.className || e.tagName, cs(e).color, bgOf(e), Math.round(r * 100) / 100]); } return low; };
"""
