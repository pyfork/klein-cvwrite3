"""A small Markdown subset for the notice and terms files: ## headings, paragraphs, - and 1. lists,
| tables | with a header row |, **bold**, and [links](/path). Everything is HTML-escaped first, so a notice file can't inject markup."""
import html
import re

_LINK = re.compile(r"\[([^\]]+)\]\((/[^)\s]*|https://[^)\s]+|mailto:[^)\s]+)\)")
_BOLD = re.compile(r"\*\*(.+?)\*\*")


def _inline(text):
    out = html.escape(text, quote=True)
    out = _BOLD.sub(r"<b>\1</b>", out)
    return _LINK.sub(r'<a href="\2">\1</a>', out)


def _cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _table(rows):
    body = [r for r in rows[1:] if not re.fullmatch(r"\|?[\s:|-]+\|?", r)]
    head = "".join(f'<th scope="col">{_inline(c)}</th>' for c in _cells(rows[0]))
    trs = "".join("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in _cells(r)) + "</tr>" for r in body)
    return f'<table class="tbl"><thead><tr>{head}</tr></thead><tbody>{trs}</tbody></table>'


def to_html(md):
    blocks, para, items, kind, rows = [], [], [], None, []

    def flush():
        nonlocal para, items, kind, rows
        if rows:
            blocks.append(_table(rows))
        if para:
            blocks.append("<p>" + _inline(" ".join(para)) + "</p>")
        if items:
            blocks.append(f"<{kind}>" + "".join(f"<li>{_inline(i)}</li>" for i in items) + f"</{kind}>")
        para, items, kind, rows = [], [], None, []

    for raw in md.splitlines():
        line = raw.strip()
        m = re.match(r"^(#{2,3}) (.+)$", line)
        if not line:
            flush()
        elif m:
            flush()
            n = len(m.group(1))
            blocks.append(f"<h{n}>{_inline(m.group(2))}</h{n}>")
        elif line.startswith("|"):
            if para or items:
                flush()
            rows.append(line)
        elif rows:
            flush()
            para.append(line)
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
