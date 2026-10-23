#!/usr/bin/env python3
"""Render a tailored CV written in the pdf-cv Markdown layout to an A4 PDF.

Usage:
    build_cv.py <input.md> <output.pdf> [--style 1|2]

cvwrite styles: 1 = Archivo condensed headings, Source Serif 4 body, IBM Plex Mono labels (default);
2 = Manrope throughout.

Standard library only. Printing uses headless Chrome or Chromium with its own
temporary profile, found at $CVWRITE_CHROME (default: the macOS Chrome path).
Fonts are self-hosted from $CVWRITE_FONTS (default: the repo's fonts/), so a
render never needs the internet.
"""
import html
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

CHROME = os.environ.get("CVWRITE_CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
CHROME_FLAGS = os.environ.get("CVWRITE_CHROME_FLAGS", "").split()  # extra flags, e.g. to cut memory on a small box
FONTS = Path(os.environ.get("CVWRITE_FONTS", Path(__file__).resolve().parent.parent / "fonts"))

CSS = """
@page { size: A4; margin: 13mm 14mm 12mm; }
:root { --ink:#1b1f24; --muted:#555d66; --accent:#0b4f6c; --rule:#c9d3da; --tint:#eef4f7; --navy:#122b6e; --navy-soft:#b9c6e6; }
* { box-sizing: border-box; }
body { margin: 0; color: var(--ink); background: #fff; font-family: Manrope, "Helvetica Neue", Arial, sans-serif; font-size: 9.4pt; line-height: 1.36; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
a { color: var(--accent); text-decoration: none; }
b { font-weight: 700; }
header { display: flex; justify-content: space-between; align-items: flex-end; gap: 16px; padding-bottom: 7px; border-bottom: 2px solid var(--ink); }
h1 { margin: 0; font-size: 22pt; font-weight: 800; line-height: 1.1; }
.headline { margin-top: 3px; color: var(--accent); font-size: 11pt; font-weight: 700; }
.tagline { margin-top: 1px; color: var(--muted); font-size: 9pt; }
.meta { text-align: right; color: var(--muted); font-size: 9pt; white-space: nowrap; }
.meta a { color: var(--muted); }
h2 { margin: 11px 0 4px; padding-bottom: 2px; border-bottom: 1px solid var(--rule); color: var(--accent); font-size: 9.5pt; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase; break-after: avoid; }
p { margin: 0 0 4px; }
ul { margin: 2px 0 4px; padding-left: 15px; }
li { margin: 0 0 2px; }
.job { margin-top: 6px; break-inside: avoid; }
.role { display: flex; justify-content: space-between; gap: 10px; font-weight: 700; break-after: avoid; }
.dates { color: var(--muted); font-weight: 600; white-space: nowrap; }
.ctx { margin: 1px 0 2px; color: var(--muted); font-style: italic; }
.comp-row { display: grid; grid-template-columns: 34% 1fr; column-gap: 12px; margin-bottom: 3px; }
.comp-label { font-weight: 700; }
.plain { padding-left: 0; list-style: none; }
.plain li { display: flex; justify-content: space-between; gap: 10px; }
.box { margin-top: 10px; padding: 10px 14px 11px; background: var(--navy); color: #fff; border-radius: 4px; break-inside: avoid; }
.box h2 { display: flex; justify-content: space-between; gap: 10px; margin: 0 0 3px; padding: 0; border: 0; color: var(--navy-soft); letter-spacing: 1.2px; }
.box a { color: #fff; }
.box h2 a { letter-spacing: 0; text-transform: none; font-weight: 600; }
.box-desc { margin: 0 0 7px; font-size: 10pt; }
.stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.stats.flow { grid-template-columns: 1fr auto 1fr auto 1fr; column-gap: 16px; align-items: start; }
.stat b { display: block; color: #fff; font-size: 15pt; font-weight: 700; line-height: 1.15; }
.stat span { color: var(--navy-soft); font-size: 8.6pt; }
/* CV renderer maintainer-Opus5.5-agent: "airy" layout spends spare space on hierarchy, for CVs well under 2 pages */
body.airy { font-size: 9.6pt; line-height: 1.44; }
.airy header { padding-bottom: 10px; }
.airy h2 { margin: 16px 0 7px; }
.airy p { margin-bottom: 7px; }
.airy li { margin-bottom: 4px; break-inside: avoid; }
.airy .comp-row { margin-bottom: 5px; }
.airy .box { margin-top: 15px; padding: 13px 16px 14px; }
.airy .box-desc { margin-bottom: 10px; }
.airy .job { margin-top: 11px; }
.airy .role { font-size: 9.9pt; }
.airy .ctx { margin: 2px 0 5px; }
.arrow { color: var(--navy-soft); font-size: 15pt; line-height: 1.15; }
"""

# cvwrite styles. Style 2 is the base CSS above (Manrope). Style 1 swaps the fonts and spacing.
# (family, file in FONTS, descriptors). Static cuts from fonts/build_static.py, one per weight and
# width the CSS asks for: variable fonts would be stored in the PDF as Type 3, which ATS read badly.
FONT_FACES = {
    1: [
        ("Archivo", "Archivo-600-78.ttf", "font-weight: 600; font-stretch: 78%;"),
        ("Archivo", "Archivo-700-78.ttf", "font-weight: 700; font-stretch: 78%;"),
        ("Archivo", "Archivo-720-78.ttf", "font-weight: 720; font-stretch: 78%;"),
        ("Archivo", "Archivo-760-78.ttf", "font-weight: 760; font-stretch: 78%;"),
        ("Archivo", "Archivo-800-70.ttf", "font-weight: 800; font-stretch: 70%;"),
        ("Source Serif 4", "SourceSerif4-400.ttf", "font-weight: 400;"),
        ("Source Serif 4", "SourceSerif4-650.ttf", "font-weight: 700;"),  # the Google link capped bold at 650
        ("Source Serif 4", "SourceSerif4-400-Italic.ttf", "font-weight: 400; font-style: italic;"),
        ("IBM Plex Mono", "IBMPlexMono-Regular.ttf", "font-weight: 400;"),
        ("IBM Plex Mono", "IBMPlexMono-Medium.ttf", "font-weight: 500;"),
        ("IBM Plex Mono", "IBMPlexMono-SemiBold.ttf", "font-weight: 600;"),  # .dates; else a faked bold
    ],
    2: [
        ("Manrope", "Manrope-400.ttf", "font-weight: 400;"),
        ("Manrope", "Manrope-600.ttf", "font-weight: 600;"),
        ("Manrope", "Manrope-700.ttf", "font-weight: 700;"),
        ("Manrope", "Manrope-800.ttf", "font-weight: 800;"),
    ],
}


def font_css(style):
    faces = []
    for family, file, desc in FONT_FACES[style]:
        path = FONTS / file
        if not path.is_file():
            sys.exit(f"font file missing: {path}")
        faces.append(f'@font-face {{ font-family: "{family}"; src: url("{path.as_uri()}") format("truetype"); {desc} }}')
    return "\n".join(faces)
FONT_NAMES = {1: "Archivo", 2: "Manrope"}
STYLE1_CSS = """
:root { --f-display: "Archivo", "Arial Narrow", Arial, sans-serif; --f-body: "Source Serif 4", Georgia, serif; --f-mono: "IBM Plex Mono", Menlo, monospace; }
body { font-family: var(--f-body); font-size: 8.9pt; line-height: 1.32; letter-spacing: 0.01em; }
h1, .headline, h2, .role > span:first-child, .comp-label, .stat b { font-family: var(--f-display); font-stretch: 78%; letter-spacing: 0.035em; }
h1 { font-size: 26pt; font-weight: 800; font-stretch: 70%; letter-spacing: 0.04em; }
.headline { font-size: 12.5pt; font-weight: 700; }
.tagline, .meta, .dates, .stat span { font-family: var(--f-mono); font-size: 7.8pt; letter-spacing: 0.02em; }
h2 { font-weight: 760; font-size: 10.5pt; letter-spacing: 0.1em; }
.role { font-size: 10pt; }
.role > span:first-child { font-weight: 720; }
.comp-label { font-weight: 700; font-size: 10pt; }
.ctx { font-style: italic; }
"""

# "... · Sheffield Hallam University, UK · 2002" -> body + right-aligned date
DATE_TAIL = re.compile(
    r"^(.*\S)\s+·\s+((?:19|20)\d{2}(?:\s*[–-]\s*(?:present|(?:19|20)\d{2}))?)$",
    re.IGNORECASE,
)
# "**HR Strategy & Leadership:** items" -> label + rest
BOLD_LABEL = re.compile(r"^\*\*(.+?):?\*\*:?\s*(.*)$")
LAYOUT_AIRY = "<!-- layout: airy -->"
# "1. **Audit** | text" inside the featured box -> one stage of an arrow flow
FLOW_ITEM = re.compile(r"^\d+\.\s+")


def inline(text):
    """Escape text, then apply **bold** and [label](url) markup."""
    text = html.escape(text, quote=False)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    return re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', text)


def render_header(name, lines):
    """Name and headline on the left; contact pieces stacked on the right."""
    left = [f"<h1>{inline(name)}</h1>"]
    right = []
    tagline_done = False
    for text in lines:
        if text.startswith("**") and text.endswith("**"):
            left.append(f'<div class="headline">{inline(text)}</div>')
        elif not tagline_done:
            left.append(f'<div class="tagline">{inline(text)}</div>')
            tagline_done = True
        else:
            right += [f"<div>{inline(piece)}</div>" for piece in text.split(" · ")]
    return (
        '<header><div class="id">' + "".join(left) + "</div>"
        '<div class="meta">' + "".join(right) + "</div></header>"
    )


def convert(md):
    out, stack = [], []  # stack holds closing tags of containers still open
    name, header, in_header = "", [], False
    kind = ""  # "comp", "edu", "box" or "" for the current ## section
    in_job = False

    def close_to(depth):
        while len(stack) > depth:
            out.append(stack.pop())

    def close_job():
        while stack and stack[-1] != "</section>":
            out.append(stack.pop())

    def end_list():
        if stack and stack[-1] == "</ul>":
            out.append(stack.pop())

    for raw in md.splitlines():
        line = raw.strip()
        if in_header and (line == "---" or line.startswith("#")):
            out.append(render_header(name, header))
            in_header = False
        if not line:
            continue
        if line == LAYOUT_AIRY:  # CV renderer maintainer-Opus5.5-agent: opt-in layout marker, never printed
            continue
        if in_header:
            header.append(line)
        elif line == "---":
            close_to(0)
        elif line.startswith("# "):
            name, header, in_header = line[2:].strip(), [], True
        elif line.startswith("## "):
            close_to(0)
            in_job = False
            title = line[3:].strip()
            upper = title.upper()
            if upper.startswith("FEATURED PROJECT"):
                kind = "box"
                label, _, url = title.partition(" | ")
                url = url.strip()
                link = ""
                if url:
                    href = url if url.startswith("http") else "https://" + url
                    link = f'<a href="{href}">{html.escape(url)}</a>'
                out.append(f'<section class="box"><h2><span>{inline(label)}</span>{link}</h2>')
            else:
                kind = "comp" if "COMPETENCIES" in upper else "edu" if "EDUCATION" in upper else ""
                out.append(f"<section><h2>{inline(title)}</h2>")
            stack.append("</section>")
        elif line.startswith("### "):
            close_job()
            left, _, dates = line[4:].partition(" | ")
            out.append(
                f'<div class="job"><div class="role"><span>{inline(left)}</span>'
                f'<span class="dates">{inline(dates)}</span></div>'
            )
            stack.append("</div>")
            in_job = True
        elif kind == "box" and FLOW_ITEM.match(line):
            # CV renderer maintainer-Opus5.5-agent: numbered items are stages, joined by arrows
            item = FLOW_ITEM.sub("", line)
            big, _, small = item.partition(" | ")
            if stack and stack[-1] == "</div>":
                out.append('<div class="arrow">→</div>')
            else:
                out.append('<div class="stats flow">')
                stack.append("</div>")
            out.append(f'<div class="stat"><b>{inline(big)}</b><span>{inline(small)}</span></div>')
        elif line.startswith("- "):
            item = line[2:].strip()
            if kind == "comp":
                m = BOLD_LABEL.match(item)
                label, rest = (m.group(1), m.group(2)) if m else ("", item)
                out.append(
                    f'<div class="comp-row"><span class="comp-label">{inline(label)}</span>'
                    f"<span>{inline(rest)}</span></div>"
                )
            elif kind == "box":
                big, _, small = item.partition(" | ")
                if not (stack and stack[-1] == "</div>"):  # open the stats row once
                    out.append('<div class="stats">')
                    stack.append("</div>")
                out.append(f'<div class="stat"><b>{inline(big)}</b><span>{inline(small)}</span></div>')
            else:
                if not (stack and stack[-1] == "</ul>"):
                    out.append('<ul class="plain">' if kind == "edu" else "<ul>")
                    stack.append("</ul>")
                m = DATE_TAIL.match(item) if kind == "edu" else None
                if m:
                    out.append(
                        f'<li><span>{inline(m.group(1))}</span>'
                        f'<span class="dates">{inline(m.group(2))}</span></li>'
                    )
                else:
                    out.append(f"<li>{inline(item)}</li>")
        else:
            end_list()
            if kind == "box":
                out.append(f'<p class="box-desc">{inline(line)}</p>')
            elif in_job:
                out.append(f'<p class="ctx">{inline(line)}</p>')
            else:
                out.append(f"<p>{inline(line)}</p>")

    if in_header:
        out.append(render_header(name, header))
    close_to(0)
    return name, "\n".join(out)


def page(title, body, airy=False, style=1):
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>{font_css(style)}
{CSS}{STYLE1_CSS if style == 1 else ""}</style>
</head>
<body{' class="airy"' if airy else ''}>
{body}
</body>
</html>
"""


def count_pages(pdf):
    match = re.search(rb"/Type\s*/Pages\b[^>]*?/Count\s+(\d+)", pdf.read_bytes())
    return int(match.group(1)) if match else 0


def wait_for_pdf(pdf, proc, timeout=120):
    """Headless Chrome can stay alive after printing, so poll until the PDF is complete."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if pdf.exists() and pdf.read_bytes().rstrip().endswith(b"%%EOF"):
            return True
        if proc.poll() is not None:
            break
        time.sleep(0.5)
    return False


# No network for the render: the page is untrusted (the ad steered the text), so Chrome may fetch nothing.
NO_NETWORK = ["--proxy-server=127.0.0.1:9", "--host-resolver-rules=MAP * ~NOTFOUND"]


class RenderError(RuntimeError):
    pass


def _chrome_child():
    """In the child, before Chrome starts: on Linux, be the first thing the kernel kills if memory runs out."""
    try:
        with open("/proc/self/oom_score_adj", "w") as f:
            f.write("1000")
    except OSError:
        pass


def render_pdf(md, dst, style=1, timeout=30):
    """Markdown text -> A4 PDF at dst. Chrome runs in its own process group, which is killed whole
    when it finishes or after `timeout` seconds. Raises RenderError if no complete PDF appears."""
    import signal
    name, body = convert(md)
    airy = LAYOUT_AIRY in md
    dst = Path(dst).resolve()
    dst.unlink(missing_ok=True)  # so the wait below cannot pick up a stale PDF
    with tempfile.TemporaryDirectory() as tmp:
        html_file = Path(tmp) / "cv.html"
        html_file.write_text(page(f"{name} - CV", body, airy, style), encoding="utf-8")
        proc = subprocess.Popen(
            [
                CHROME,
                "--headless=new",
                "--disable-gpu",
                "--no-first-run",
                f"--user-data-dir={tmp}/profile",
                "--no-pdf-header-footer",
                "--virtual-time-budget=8000",
                *NO_NETWORK,
                *CHROME_FLAGS,
                f"--print-to-pdf={dst}",
                html_file.as_uri(),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            preexec_fn=_chrome_child if sys.platform.startswith("linux") else None,
        )
        try:
            done = wait_for_pdf(dst, proc, timeout)
        finally:
            try:
                os.killpg(proc.pid, signal.SIGKILL)  # Chrome may not exit on its own after printing
            except ProcessLookupError:
                pass
            proc.wait()
    if not done:
        raise RenderError("timeout" if proc.returncode in (None, -9) else f"chrome_exit_{proc.returncode}")
    return {"pages": count_pages(dst), "font_embedded": FONT_NAMES[style].encode() in dst.read_bytes()}


def main():
    args, style = sys.argv[1:], 1
    if "--style" in args:
        i = args.index("--style")
        try:
            style = int(args[i + 1])
            assert style in FONT_NAMES
        except (IndexError, ValueError, AssertionError):
            sys.exit("--style must be 1 (Archivo) or 2 (Manrope)")
        del args[i : i + 2]
    if len(args) != 2:
        sys.exit("usage: build_cv.py <input.md> <output.pdf> [--style 1|2]")
    src, dst = Path(args[0]).resolve(), Path(args[1]).resolve()
    try:
        render_pdf(src.read_text(encoding="utf-8"), dst, style, timeout=120)
    except RenderError:
        sys.exit(f"Chrome did not produce a complete PDF at {dst}")
    print(f"Wrote {dst}")
    print(f"Pages: {count_pages(dst)}")
    print(f"Style: {style} ({FONT_NAMES[style]})")
    if FONT_NAMES[style].encode() not in dst.read_bytes():
        print(f"WARNING: {FONT_NAMES[style]} is not embedded in the PDF. Check {FONTS} and re-run.")


if __name__ == "__main__":
    main()
