#!/usr/bin/env python3
"""Throwaway check for chunk 1: the same made-up CV renders to the same 2-page PDF here and on sk24.

Usage: render_check.py [out_dir]
Merges a made-up contact, renders style 1, runs check_cv.py, confirms every font is embedded,
then prints a fingerprint (pages, fonts, text hash) to compare between machines.
Needs Chrome at $CVWRITE_CHROME and poppler (pdfinfo, pdftotext, pdffonts). Exit 0 = pass.
"""
import hashlib
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "render"))
import contact  # noqa: E402

FAKE = {"name": "Test Candidate", "location": "Shah Alam", "phone": "+60 12-000 0000", "email": "test@example.com"}
KEYWORDS = ["payroll", "HRIS", "employee relations"]
FAMILIES = ["Archivo", "SourceSerif4", "IBMPlexMono"]


def run(*cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.mkdtemp())
    out.mkdir(parents=True, exist_ok=True)
    md, pdf = out / "sample.md", out / "sample.pdf"
    md.write_text(contact.merge((ROOT / "tests/fixtures/sample_draft.md").read_text(), FAKE), encoding="utf-8")

    code, log = run(sys.executable, str(ROOT / "render/build_cv.py"), str(md), str(pdf), "--style", "1")
    print(log.strip())
    if code or not pdf.exists():
        sys.exit("FAIL  render")
    failed = "WARNING" in log

    code, log = run(sys.executable, str(ROOT / "render/check_cv.py"), str(pdf), *KEYWORDS)
    print(log.strip())
    failed |= code != 0

    _, fonts = run("pdffonts", str(pdf))
    rows = [l.split() for l in fonts.splitlines()[2:] if l.strip()]
    names = sorted({r[0].split("+")[-1] for r in rows})
    not_embedded = [r[0] for r in rows if "no" in r[-5:-3]]  # emb, sub columns
    for fam in FAMILIES:
        ok = any(fam in n for n in names)
        print(f"{'PASS' if ok else 'FAIL'}  font embedded: {fam}")
        failed |= not ok
    others = [n for n in names if not any(f in n for f in FAMILIES)]
    print(f"{'PASS' if not others else 'FAIL'}  no fallback fonts {others or ''}")
    print(f"{'PASS' if not not_embedded else 'FAIL'}  all fonts embedded {not_embedded or ''}")
    failed |= bool(others or not_embedded)

    _, text = run("pdftotext", "-layout", str(pdf), "-")
    _, info = run("pdfinfo", str(pdf))
    pages = re.search(r"^Pages:\s+(\d+)", info, re.M).group(1)
    print(f"FINGERPRINT pages={pages} fonts={','.join(names)} text={hashlib.sha256(text.encode()).hexdigest()[:16]}")
    print(f"PDF: {pdf}")
    print("RESULT: FAIL" if failed else "RESULT: PASS")
    sys.exit(1 if failed else 0)


main()
