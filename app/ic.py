"""Spots anything shaped like a Malaysian IC number (YYMMDD-PB-###G, with or without dashes), so the user
can remove it before anything is sent to Claude. Reports line numbers and a masked form only."""
import re

_IC = re.compile(r"(?<!\d)(\d{2})(\d{2})(\d{2})[-\s]?(\d{2})[-\s]?(\d{4})(?!\d)")


def find(text):
    """[(line number, masked)] for each date-valid match, e.g. (3, "92••••-••-••41")."""
    hits = []
    for n, line in enumerate(text.splitlines(), 1):
        for m in _IC.finditer(line):
            month, day = int(m.group(2)), int(m.group(3))
            if 1 <= month <= 12 and 1 <= day <= 31:
                hits.append((n, m.group(1) + "••••-••-••" + m.group(5)[-2:]))
    return hits
