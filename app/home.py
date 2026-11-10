"""The home's three invented samples (redesign S-010): their words, and every count the page shows worked out from them.

The rules are v2's script's (docs/spikes/betterjobs-collage/v2), run once at start-up so the page shows them with
scripts off: a CV is read as one run of words, a keyword's place is the number of words before its first match, the
"First 50 words" band holds the keywords that start before word 50, and a sticker below it sits at its share of the page.
senior-lead-Opus5.5-agent
"""
import json
import re
from pathlib import Path

from markupsafe import Markup, escape

ZONE = 50   # the "First 50 words" band
LABEL = {"backed": "strong match", "bridged": "good match"}
TILT = (-1.5, 1.2, -0.6)
_FILE = Path(__file__).parent / "content" / "home_samples.json"


def _words(text):
    return len(text.split())


def _first_at(text, pattern):
    m = re.search(pattern, text, re.I)
    return None if m is None else _words(text[:m.start()])


def _master_text(m):
    parts = [m["name"], m["intro"]]
    for j in m["jobs"]:
        parts += [j["head"], *j["b"]]
    return " ".join(parts + m["tail"])


def _cv_text(s):
    c = s["cv"]
    parts = [s["master"]["name"], c["title"], c["kw"], "PROFESSIONAL SUMMARY", c["summary"], "FEATURED PROJECT",
             c["featured"]["head"], c["featured"]["line"], *(f"{v} {l}" for v, l in c["featured"]["stats"]),
             "CORE COMPETENCIES", *(f"{k}: {v}" for k, v in c["comp"]), "KEY ACHIEVEMENTS", *(f"{k}: {v}" for k, v in c["ach"]),
             "PROFESSIONAL EXPERIENCE"]
    for e in c["exp"]:
        parts += [f"{e['role']} {e['dates']}", *([e["note"]] if e.get("note") else []), *(f"{k}: {v}" for k, v in e["b"])]
    return " ".join(parts + ["EDUCATION & CERTIFICATIONS", *c["edu"]])


def _highlighter(top):
    def hi(text):
        h = str(escape(text))
        for _, pattern, _ in top:
            h = re.sub(f"({pattern})", r"<mark>\1</mark>", h, flags=re.I)
        return Markup(h)
    return hi


def _page(rows, total):
    """One small page: the keywords in the band, then the rest at their share of the page, each below the last."""
    pct = lambda v: 6 + v / total * 88
    zone = [r for r in rows if r["at"] < ZONE]
    out, last = [], -1.0
    for r in sorted((r for r in rows if r["at"] >= ZONE), key=lambda r: r["at"]):
        last = max(pct(r["at"]), last + 11)   # 11 points apart, so a sticker never sits on another
        out.append({**r, "y": f"{last:.1f}%"})
    sticker = lambda r, j: {"k": r["k"], "r": f"{TILT[j % 3]}deg", "y": r.get("y"), "title": f"Word {r['at'] + 1} of {total}"}
    return {"z": f"{pct(ZONE):.1f}%", "zone": [sticker(r, j) for j, r in enumerate(zone)],
            "out": [sticker(r, j + len(zone)) for j, r in enumerate(out)]}


def _sample(s):
    mt, ct = _master_text(s["master"]), _cv_text(s)
    rows = [{"k": k, "m": _first_at(mt, p), "c": _first_at(ct, p)} for k, p, _ in s["top"]]
    found = [r["c"] for r in rows if r["c"] is not None]
    return {
        **s, "rows": rows, "hi": _highlighter(s["top"]),
        "more_lines": s["ad"]["lines"] - len(s["problems"]),
        "chips": [(k, LABEL[status]) for k, _, status in s["top"]],
        "before_n": sum(r["m"] is not None for r in rows), "after_n": len(found),
        "from_word": min(found) + 1 if found else None,
        "missing": [r["k"] for r in rows if r["m"] is None],
        "in_zone": sum(r["c"] is not None and r["c"] < ZONE for r in rows),
        "before_page": _page([{"k": r["k"], "at": r["m"]} for r in rows if r["m"] is not None], _words(mt)),
        "after_page": _page([{"k": r["k"], "at": r["c"]} for r in rows if r["c"] is not None], _words(ct)),
    }


def load(path=_FILE):
    """The samples and the summary line's counts, for the home's template."""
    samples = [_sample(s) for s in json.loads(path.read_text(encoding="utf-8"))["samples"]]
    rows = [r for s in samples for r in s["rows"]]
    return {"samples": samples, "zone": ZONE, "total": len(rows),
            "before": sum(r["m"] is not None for r in rows), "after": sum(r["c"] is not None for r in rows),
            "after_in_zone": sum(r["c"] is not None and r["c"] < ZONE for r in rows)}
