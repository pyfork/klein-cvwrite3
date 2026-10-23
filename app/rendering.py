"""Render and check, with the sk24 limits: one Chrome at a time, a memory admission check, a 30 s
timeout with the process group killed, one retry. Records memory.peak where the kernel offers it."""
import os
import threading
import time
from pathlib import Path

from render import build_cv, check_cv

LOCK = threading.Lock()          # one Chrome at a time in this worker
MIN_FREE_BYTES = 500 * 1024 * 1024
ADMISSION_WAIT_S = 120
TIMEOUT_S = 30


class RenderFailed(RuntimeError):
    def __init__(self, kind):
        super().__init__(kind)
        self.kind = kind


def mem_available():
    """Bytes of MemAvailable on Linux; None elsewhere (the check is skipped on the Mac)."""
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) * 1024
    except OSError:
        return None
    return None


def _cgroup_file(name):
    try:
        rel = Path("/proc/self/cgroup").read_text().strip().split("::", 1)[1]
        return Path("/sys/fs/cgroup" + rel) / name
    except (OSError, IndexError):
        return None


def _peak():
    f = _cgroup_file("memory.peak")
    try:
        return int(f.read_text()) if f else None
    except (OSError, ValueError):
        return None


def render(md, dst, attempts=2):
    """Returns {"ms", "wait_ms", "memory_peak", "pages", "tries"}. Raises RenderFailed after `attempts` tries."""
    with LOCK:
        t_wait = time.monotonic()
        while (free := mem_available()) is not None and free < MIN_FREE_BYTES:
            if time.monotonic() - t_wait > ADMISSION_WAIT_S:
                raise RenderFailed("low_memory")
            time.sleep(2)
        wait_ms = int((time.monotonic() - t_wait) * 1000)
        last = "unknown"
        for i in range(1, attempts + 1):
            t0 = time.monotonic()
            try:
                info = build_cv.render_pdf(md, dst, style=1, timeout=TIMEOUT_S)
                return {"ms": int((time.monotonic() - t0) * 1000), "wait_ms": wait_ms, "memory_peak": _peak(),
                        "pages": info["pages"], "tries": i}
            except build_cv.RenderError as e:
                last = str(e)
            except SystemExit:  # build_cv exits when a font file is missing
                last = "font_missing"
                break
        raise RenderFailed(last)


def check(pdf, keywords):
    try:
        return check_cv.check(pdf, keywords)
    except check_cv.CannotCheck as e:
        raise RenderFailed("check_" + str(e)) from None


def pdf_path(data_dir, run_id, rev):
    d = Path(data_dir) / "pdfs"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{run_id}-{rev}.pdf"


def replace_pdf(data_dir, run_id, old_rev, new_tmp, new_rev):
    final = pdf_path(data_dir, run_id, new_rev)
    os.replace(new_tmp, final)
    if old_rev and old_rev != new_rev:
        pdf_path(data_dir, run_id, old_rev).unlink(missing_ok=True)
    return final
