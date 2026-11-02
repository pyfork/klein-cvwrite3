"""Redesign S-004 (brief Addendum 15): the scripts the app may serve are listed here; any other fails the suite.
A script is added by adding its entry to ALLOWED in the same change as the script. Standard library only: it reads
app/templates and app/static from the folder above tests/. Run: python3 -m unittest discover tests
senior-lead-Sonnet5.5-agent, 2026-11-03
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "app" / "static"
TEMPLATES = ROOT / "app" / "templates"

# script path under app/static -> the template files that load it, and what the page does without it (AC-87)
ALLOWED = {
    "upload.js": {
        "pages": {"profile.html"},
        "without": "The upload form still works: pick a file, press Read this file. The page does not show the file name "
                   "or the 2 MB warning; the server still refuses a file over 2 MB. Nothing moves.",
    },
}

TAG = re.compile(r"<script\b([^>]*)>(.*?)(?:</script\s*>|\Z)", re.I | re.S)
ATTR = re.compile(r'([\w:-]+)(?:\s*=\s*"([^"]*)")?')
SRC = re.compile(r"/static/([\w./-]+\.js)(?:\?v=[^\"]*)?")
HANDLER = re.compile(r"<[^>]*\son[a-z]+\s*=|javascript\s*:", re.I)


def problems():
    found, loads = [], {}
    for page in sorted(TEMPLATES.glob("*.html")):
        text = page.read_text(encoding="utf-8")
        if HANDLER.search(text):
            found.append(f"{page.name}: an inline handler (on...=) or a javascript: address")
        for m in TAG.finditer(text):
            attrs = {k.lower(): v for k, v in ATTR.findall(m.group(1))}
            src = SRC.fullmatch(attrs.get("src", ""))
            if set(attrs) != {"src", "defer"} or not src or m.group(2).strip():
                found.append(f'{page.name}: a <script> that is not <script src="/static/NAME.js" defer></script>')
                continue
            loads.setdefault(page.name, set()).add(src.group(1))
            if src.group(1) not in ALLOWED:
                found.append(f"{page.name}: loads {src.group(1)}, which is not on the allow-list")
            elif page.name not in ALLOWED[src.group(1)]["pages"]:
                found.append(f"{page.name}: loads {src.group(1)}, which is not listed for this page")
    for f in sorted(p for p in STATIC.rglob("*") if p.is_file()):
        rel, text = f.relative_to(STATIC).as_posix(), f.read_bytes().decode("utf-8", "replace")
        if f.suffix.lower() in {".js", ".mjs"} and rel not in ALLOWED:
            found.append(f"app/static/{rel}: a script that is not on the allow-list")
        elif f.suffix.lower() in {".svg", ".html", ".htm", ".xml"} and (re.search(r"<script", text, re.I) or HANDLER.search(text)):
            found.append(f"app/static/{rel}: holds a script, an inline handler or a javascript: address")
    for js, entry in ALLOWED.items():  # a stale entry fails too
        if not (STATIC / js).is_file():
            found.append(f"allow-list: {js} is listed but app/static/{js} does not exist")
        if not entry["pages"] or not entry["without"].strip():
            found.append(f"allow-list: {js} needs its pages and its 'without' text")
        for page in entry["pages"]:
            if js not in loads.get(page, ()):
                found.append(f"allow-list: {js} is listed for {page}, which does not load it")
    return found


class ScriptAllowList(unittest.TestCase):
    # shortcut: names the template file that holds the tag, not the pages that include it; revisit when a script sits in a partial.
    def test_every_script_is_listed_and_safe(self):
        found = problems()
        self.assertFalse(found, "\n" + "\n".join(found))
