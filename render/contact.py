"""Contact masking and merging, ported from the skill's _contact.py, read_master.py and merge_contact.py.

The one change: values come from the user's profile row (a dict), not profile/contact.md.
Nothing here prints or logs a value.
"""
import re
import subprocess

FIELDS = ("name", "location", "phone", "email", "address", "links")


class MergeError(ValueError):
    pass


def contact_line(data):
    """The header's contact line: location, phone, email, address, links."""
    return " · ".join(data[k] for k in ("location", "phone", "email", "address", "links") if data.get(k))


def patterns(data):
    """(label, compiled regex) for each value to remove."""
    out = []
    if data.get("name"):
        out.append(("name", re.compile(re.escape(data["name"]), re.I)))
    if data.get("phone"):
        core = re.sub(r"\s*\([^)]*\)\s*$", "", data["phone"])  # drop "(WhatsApp)"
        out.append(("phone", re.compile(re.escape(data["phone"]), re.I)))
        digits = re.sub(r"\D", "", core)
        if len(digits) >= 7:
            out.append(("phone", re.compile(r"\+?" + r"[\s\-.]*".join(digits), re.I)))
    for key in ("email", "address"):
        if data.get(key):
            out.append((key, re.compile(re.escape(data[key]), re.I)))
    for link in re.split(r"\s*[,;·]\s*", data.get("links", "")):
        if link:
            out.append(("link", re.compile(re.escape(link), re.I)))
    return out


def header_to_placeholders(text):
    """In a Markdown CV header (`# Name` ... `---`): name -> {{NAME}}, lines after the tagline -> {{CONTACT}}."""
    lines, out, i = text.splitlines(), [], 0
    while i < len(lines):
        if lines[i].startswith("# "):
            out.append("# {{NAME}}")
            i += 1
            block = []
            while i < len(lines) and lines[i].strip() != "---" and not lines[i].startswith("#"):
                block.append(lines[i])
                i += 1
            tagline_seen, contact_done = False, False
            for line in block:
                t = line.strip()
                if not t:
                    out.append(line)
                elif t.startswith("**") and t.endswith("**"):
                    out.append(line)
                elif not tagline_seen:
                    tagline_seen = True
                    out.append(line)
                elif not contact_done:
                    out.append("{{CONTACT}}")
                    contact_done = True
            continue
        out.append(lines[i])
        i += 1
    return "\n".join(out) + "\n"


def master_text(path):
    """A master CV file as text: .md and .txt as is, .pdf via pdftotext."""
    if path.suffix.lower() == ".pdf":
        return subprocess.run(["pdftotext", str(path), "-"], capture_output=True, text=True, check=True).stdout
    return path.read_text(encoding="utf-8")


def mask(text, data, markdown=False):
    """Return (masked text, {label: count}). Counts only, never the values."""
    if markdown:
        text = header_to_placeholders(text)
    counts = {}
    for label, rx in patterns(data):
        text, n = rx.subn(f"[{label}]", text)
        if n:
            counts[label] = counts.get(label, 0) + n
    return text, counts


def merge(draft, data):
    """Put the name and contact line into a draft with `# {{NAME}}` and a `{{CONTACT}}` line."""
    for marker in ("{{NAME}}", "{{CONTACT}}"):
        if draft.count(marker) != 1:
            raise MergeError(f"draft must contain {marker} exactly once (found {draft.count(marker)})")
    if not data.get("name"):
        raise MergeError("profile has no name")
    return draft.replace("{{NAME}}", data["name"]).replace("{{CONTACT}}", contact_line(data))
