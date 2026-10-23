"""CV text helpers: Markdown <-> the plain edit-box text, the summary word count, the Haiku word check,
and where each keyword sits in a CV. No Claude calls here."""
import difflib
import re

SUMMARY = "PROFESSIONAL SUMMARY"
SUMMARY_MAX_WORDS = 50
_WORD = re.compile(r"[\w][\w'’%.+#/&-]*", re.U)


def words(text):
    return [w.lower().strip(".'’-/") for w in _WORD.findall(text) if w.strip(".'’-/")]


def strip_markup(md):
    t = re.sub(r"<!--.*?-->", " ", md, flags=re.S)
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)
    t = re.sub(r"^#{1,3} ", "", t, flags=re.M)
    t = t.replace("**", "").replace("{{NAME}}", " ").replace("{{CONTACT}}", " ")
    t = re.sub(r"^---+$", " ", t, flags=re.M)
    t = re.sub(r"^\s*[-*] ", "", t, flags=re.M)
    return t.replace("|", " ")


def summary_words(md):
    m = re.search(rf"^## {SUMMARY}\s*$(.*?)(?=^## |\Z)", md, re.M | re.S)
    return len(words(strip_markup(m.group(1)))) if m else 0


# ---- the edit box --------------------------------------------------------------
def header_and_body(md):
    """Everything before the first ## heading is the header (name, headline, contact), which edits can't change."""
    m = re.search(r"^## ", md, re.M)
    return (md, "") if not m else (md[: m.start()], md[m.start():])


def to_plain(md):
    """The edit box text: CAPS headings, "- " bullets, no # or **. The header shows as placeholders."""
    _, body = header_and_body(md)
    out = ["[NAME]", "[CONTACT]", "(Change your name and contact details in Profile.)", ""]
    for line in body.splitlines():
        s = line.rstrip()
        if s.strip() in ("---", "<!-- layout: airy -->"):
            continue
        if s.startswith("## "):
            if out and out[-1] != "":
                out.append("")
            out.append(s[3:].strip())
            continue
        s = re.sub(r"^### ", "", s)
        s = s.replace("**", "")
        s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r"\1 (\2)", s)
        s = re.sub(r"^\* ", "- ", s)
        out.append(s)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip() + "\n"


def plain_body(text):
    """The user's text from the first CAPS heading on. Anything above it (the header) is ignored."""
    lines = text.replace("\r\n", "\n").split("\n")
    for i, line in enumerate(lines):
        s = line.strip()
        if len(s) >= 4 and s == s.upper() and re.fullmatch(r"[A-Z][A-Z0-9 &/·,()+-]+", s):
            return "\n".join(lines[i:]).strip() + "\n", i > 0 and any(l.strip() for l in lines[:i]
                                                                       if l.strip() not in ("[NAME]", "[CONTACT]", "(Change your name and contact details in Profile.)"))
    return text, False


def word_check(user_text, new_md, keep=0.97, extra=0.03):
    """Haiku may only re-format. At least 97% of the user's words must come back unchanged and in order,
    and no more than 3% new words may appear. Returns (passed, kept_share)."""
    a = words(user_text)
    b = words(strip_markup(header_and_body(new_md)[1]))
    if not a:
        return False, 0.0
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    matched = sum(blk.size for blk in sm.get_matching_blocks())
    kept = matched / len(a)
    added = (len(b) - matched) / len(a)
    return kept >= keep and added <= extra, round(kept, 4)


# ---- the result page ---------------------------------------------------------------
def keyword_places(md, keywords):
    """{keyword: ["Summary", "Core competencies", ...]} by section, case-insensitive."""
    sections, current = [], "Header"
    for line in md.splitlines():
        if line.startswith("## "):
            current = line[3:].split("·")[0].split("|")[0].strip().capitalize()
        sections.append((current, line))
    out = {}
    for kw in keywords:
        k = re.sub(r"\s+", " ", kw.lower())
        places = []
        for sec, line in sections:
            if k in re.sub(r"\s+", " ", strip_markup(line).lower()) and sec not in places:
                places.append(sec)
        out[kw] = places
    return out
