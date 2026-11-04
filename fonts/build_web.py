#!/usr/bin/env python3
"""Cut the three web fonts to woff2 files that keep only the characters in fonts/web-subset.txt (redesign S-007).

Why: the whole variable TrueType files are 524,216 bytes, and every page loads all three. The cut keeps the
weight axis, the layout features and the names, so each kept letter draws as it does in the source.

Dev-time only (needs fontTools and Brotli, never on the server):
    pip install --only-binary :all: --require-hashes -r fonts/requirements-web.txt
    python3 fonts/build_web.py
senior-lead-Opus5.5-agent, 2026-11-04
"""
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont

HERE = Path(__file__).resolve().parent
SOURCES = ("SchibstedGrotesk-Variable.ttf", "LibreCaslonText-Italic-Variable.ttf", "GeistMono-Variable.ttf")


def kept():
    """Code points from web-subset.txt: one U+XXXX or U+XXXX-YYYY per line, # starts a comment."""
    points = set()
    for line in (HERE / "web-subset.txt").read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            lo, _, hi = line[2:].partition("-")
            points |= set(range(int(lo, 16), int(hi or lo, 16) + 1))
    return points


def main():
    unicodes = kept()
    for src in SOURCES:
        options = subset.Options(flavor="woff2", layout_features=["*"], name_IDs=["*"], name_languages=["*"],
                                 notdef_outline=True)
        font = TTFont(HERE / src, recalcTimestamp=False)  # keep the source date, so a rerun writes the same bytes
        sub = subset.Subsetter(options)
        sub.populate(unicodes=unicodes)
        sub.subset(font)
        out = HERE / src.replace(".ttf", ".woff2")
        font.flavor = "woff2"
        font.save(out)
        print(f"{out.name}: {out.stat().st_size} bytes")


if __name__ == "__main__":
    main()
