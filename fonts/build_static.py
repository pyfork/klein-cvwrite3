#!/usr/bin/env python3
"""Cut fixed (static) TrueType fonts from the variable fonts in fonts/src/.

Why: Chrome stores variable fonts in a PDF as Type 3 (each letter drawn as a shape), which some
applicant-tracking systems read badly. A static TrueType file per weight/width embeds as a normal
font. The cuts below are exactly the ones the CV's CSS asks for (render/build_cv.py FONT_FACES).

Dev-time only (needs fontTools, not on the server): python3 fonts/build_static.py
"""
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

HERE = Path(__file__).resolve().parent

# (source, output, family name, axis values)
CUTS = [
    ("Archivo.ttf", "Archivo-600-78.ttf", "Archivo cvw", {"wght": 600, "wdth": 78}),
    ("Archivo.ttf", "Archivo-700-78.ttf", "Archivo cvw", {"wght": 700, "wdth": 78}),
    ("Archivo.ttf", "Archivo-720-78.ttf", "Archivo cvw", {"wght": 720, "wdth": 78}),
    ("Archivo.ttf", "Archivo-760-78.ttf", "Archivo cvw", {"wght": 760, "wdth": 78}),
    ("Archivo.ttf", "Archivo-800-70.ttf", "Archivo cvw", {"wght": 800, "wdth": 70}),
    ("SourceSerif4.ttf", "SourceSerif4-400.ttf", "Source Serif 4 cvw", {"wght": 400, "opsz": 12}),
    ("SourceSerif4.ttf", "SourceSerif4-650.ttf", "Source Serif 4 cvw", {"wght": 650, "opsz": 12}),
    ("SourceSerif4-Italic.ttf", "SourceSerif4-400-Italic.ttf", "Source Serif 4 cvw", {"wght": 400, "opsz": 12}),
    ("Manrope.ttf", "Manrope-400.ttf", "Manrope cvw", {"wght": 400}),
    ("Manrope.ttf", "Manrope-600.ttf", "Manrope cvw", {"wght": 600}),
    ("Manrope.ttf", "Manrope-700.ttf", "Manrope cvw", {"wght": 700}),
    ("Manrope.ttf", "Manrope-800.ttf", "Manrope cvw", {"wght": 800}),
]


def rename(font, family, style):
    """Unique names, so each cut shows up by name in pdffonts."""
    ps = f"{family.replace(' ', '')}-{style}"
    for rec in list(font["name"].names):
        if rec.nameID in (1, 2, 3, 4, 6, 16, 17, 25):
            font["name"].removeNames(nameID=rec.nameID)
    for nid, value in ((1, f"{family} {style}"), (2, "Regular"), (3, ps), (4, f"{family} {style}"), (6, ps)):
        font["name"].setName(value, nid, 3, 1, 0x409)


def main():
    for src, out, family, axes in CUTS:
        font = instantiateVariableFont(TTFont(HERE / "src" / src), axes)
        style = "-".join(str(v) for v in axes.values()) + ("-Italic" if "Italic" in out else "")
        rename(font, family, style)
        font.save(HERE / out)
        print(f"{out}: {axes}")


if __name__ == "__main__":
    main()
