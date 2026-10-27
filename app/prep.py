"""Interview prep (Addendum 12): 3 to 5 short notes from call B, each pointing to a quote from the ad, a line of the
master CV, or both. A note whose quote or line isn't there word for word is dropped, the way call A's quotes are."""
from .adread import _in, normalise

MAX_NOTES = 5
MAX_CHARS = 300

SCHEMA = {
    "type": "array",
    "description": "3 to 5 notes to get ready for this job's interview; not part of the CV",
    "items": {
        "type": "object", "additionalProperties": False, "required": ["note", "ad_quote", "cv_line"],
        "properties": {
            "note": {"type": "string", "description": "one or two short sentences, plain English, to the user as \"you\""},
            "ad_quote": {"type": "string", "description": "words from the ad that the note answers, copied exactly; empty if none"},
            "cv_line": {"type": "string", "description": "words from the master CV the note relies on, copied exactly; empty if none"},
        },
    },
}


def verify(raw, ad_text, master_text):
    """The notes that pass: at least one source, and every source given is in the ad or the master CV as worded."""
    ad, cv = normalise(ad_text or ""), normalise(master_text or "")
    kept = []
    for n in raw if isinstance(raw, list) else []:
        if not isinstance(n, dict):
            continue
        note, q, line = (normalise(str(n.get(k, ""))) for k in ("note", "ad_quote", "cv_line"))
        if not note or not (q or line):
            continue
        if (q and not _in(q, ad)) or (line and not _in(line, cv)):
            continue
        kept.append({"note": note[:MAX_CHARS], "ad_quote": q[:MAX_CHARS], "cv_line": line[:MAX_CHARS]})
    return kept[:MAX_NOTES]
