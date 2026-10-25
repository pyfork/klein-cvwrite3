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


# Shapes taken out whatever the profile says, so an email, phone or profile link that isn't typed there
# (or is typed differently) still never reaches the AI.
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
_SEP = r"[\s.-]{0,2}"
PHONE = re.compile(
    r"(?<![\w+])(?:\(?\+?\s?60\)?" + _SEP + r"|0)\d(?:" + _SEP + r"\d){7,9}(?!\d)"  # Malaysian: 012-345 6789, +60 3-1234 5678
    r"|(?<![\w+])\+\d{1,3}(?:" + _SEP + r"\d){7,12}(?!\d)")                       # any number written with a +
PROFILE_LINK = re.compile(r"(?:https?://)?(?:[a-z]{2,3}\.)?(?:linkedin\.com/(?:in|pub)/|github\.com/)[\w%-]+/?", re.I)
SHAPES = (("email", EMAIL), ("phone", PHONE), ("link", PROFILE_LINK))


def _all(data):
    return patterns(data) + list(SHAPES)


def found(text, data):
    """[(label, value)] that mask() takes out, each once, in the order they appear. Only for the user's own page."""
    original, out = text, []
    for label, rx in _all(data):
        for m in rx.finditer(text):
            if (label, m.group(0)) not in out:
                out.append((label, m.group(0)))
        text = rx.sub(f"[{label}]", text)
    return sorted(out, key=lambda lv: original.lower().find(lv[1].lower()))


def guess(text):
    """{field: first value of that shape in the text}, to pre-fill empty contact fields for the user to check."""
    out = {}
    for field, rx in (("email", EMAIL), ("phone", PHONE), ("links", PROFILE_LINK)):
        m = rx.search(text)
        if m:
            out[field] = m.group(0).strip()
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
    for label, rx in _all(data):
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
