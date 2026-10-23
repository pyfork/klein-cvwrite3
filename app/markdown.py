"""A small Markdown subset for the notice and terms files: ## headings, paragraphs, - and 1. lists,
**bold**, and [links](/path). Everything is HTML-escaped first, so a notice file can't inject markup."""
import html
import re

_LINK = re.compile(r"\[([^\]]+)\]\((/[^)\s]*|https://[^)\s]+|mailto:[^)\s]+)\)")
_BOLD = re.compile(r"\*\*(.+?)\*\*")


def _inline(text):
    out = html.escape(text, quote=True)
    out = _BOLD.sub(r"<b>\1</b>", out)
    return _LINK.sub(r'<a href="\2">\1</a>', out)


def to_html(md):
    blocks, para, items, kind = [], [], [], None

    def flush():
        nonlocal para, items, kind
        if para:
            blocks.append("<p>" + _inline(" ".join(para)) + "</p>")
        if items:
            blocks.append(f"<{kind}>" + "".join(f"<li>{_inline(i)}</li>" for i in items) + f"</{kind}>")
        para, items, kind = [], [], None

    for raw in md.splitlines():
        line = raw.strip()
        m = re.match(r"^(#{2,3}) (.+)$", line)
        if not line:
            flush()
        elif m:
            flush()
            n = len(m.group(1))
            blocks.append(f"<h{n}>{_inline(m.group(2))}</h{n}>")
        elif re.match(r"^- ", line) or re.match(r"^\d+\. ", line):
            new = "ul" if line.startswith("- ") else "ol"
            if para or (kind and kind != new):
                flush()
            kind = new
            items.append(re.sub(r"^(- |\d+\. )", "", line))
        elif items:
            items[-1] += " " + line
        else:
            para.append(line)
    flush()
    return "\n".join(blocks)


def section(md, heading):
    """The text under one ## heading, up to the next ## heading."""
    m = re.search(rf"^## {re.escape(heading)}\s*$(.*?)(?=^## |\Z)", md, re.M | re.S)
    return m.group(1).strip() if m else ""
