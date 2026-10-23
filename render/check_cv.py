#!/usr/bin/env python3
"""cvwrite check: a CV PDF must be exactly 2 A4 pages and its text must hold the top-3 keywords.

Usage: check_cv.py <cv.pdf> <keyword 1> <keyword 2> <keyword 3>
Needs poppler's pdfinfo and pdftotext. Exit 0 = pass, 1 = fail, 2 = could not check.
Keywords are matched as the ad worded them: case-insensitive, whitespace collapsed, nothing else.
"""
import re
import subprocess
import sys


def run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError) as e:
        print(f"CANNOT CHECK: {cmd[0]} failed: {e}")
        sys.exit(2)


def squash(s):
    return re.sub(r"\s+", " ", s).strip().lower()


class CannotCheck(RuntimeError):
    pass


def check(pdf, keywords):
    """The same checks as the CLI, as data: {"pages", "a4", "text_ok", "keywords": {kw: bool}, "passed"}."""
    try:
        info = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True, check=True, timeout=30).stdout
        text = squash(subprocess.run(["pdftotext", str(pdf), "-"], capture_output=True, text=True, check=True, timeout=30).stdout)
    except (OSError, subprocess.SubprocessError) as e:
        raise CannotCheck(type(e).__name__) from None
    pages = int(re.search(r"^Pages:\s+(\d+)", info, re.M).group(1))
    a4 = "A4" in re.search(r"^Page size:\s+(.*)$", info, re.M).group(1)
    found = {kw: squash(kw) in text for kw in keywords}
    out = {"pages": pages, "a4": a4, "text_ok": len(text) >= 200, "keywords": found}
    out["passed"] = pages == 2 and a4 and out["text_ok"] and all(found.values())
    return out


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    pdf, keywords = sys.argv[1], sys.argv[2:]
    info = run(["pdfinfo", pdf])
    pages = int(re.search(r"^Pages:\s+(\d+)", info, re.M).group(1))
    size = re.search(r"^Page size:\s+(.*)$", info, re.M).group(1)
    text = squash(run(["pdftotext", pdf, "-"]))

    failed = False
    ok = pages == 2
    print(f"{'PASS' if ok else 'FAIL'}  pages: {pages} (need exactly 2)")
    failed |= not ok
    ok = "A4" in size
    print(f"{'PASS' if ok else 'FAIL'}  page size: {size} (need A4)")
    failed |= not ok
    if len(text) < 200:
        print("FAIL  text layer: almost no text found in the PDF")
        failed = True
    for kw in keywords:
        ok = squash(kw) in text
        print(f"{'PASS' if ok else 'FAIL'}  keyword in text: {kw!r}")
        failed |= not ok
    print("RESULT: FAIL" if failed else "RESULT: PASS")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
