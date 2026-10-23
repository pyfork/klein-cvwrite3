"""Run by a systemd timer every minute: calls /healthz on this box and writes an uptime_checks row.

    python -m app.uptime          (CVWRITE_HEALTHZ_URL, default http://127.0.0.1:8000/healthz)
"""
import json
import os
import time
import urllib.error
import urllib.request

from . import config, db


def check(url):
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            body = json.loads(r.read() or b"{}")
            ok = r.status == 200 and bool(body.get("ok"))
    except urllib.error.HTTPError as e:
        ok, body = False, {"http": e.code}
    except (OSError, ValueError) as e:
        ok, body = False, {"error": type(e).__name__}
    detail = ",".join(f"{k}={v}" for k, v in sorted(body.items()) if k != "ok")[:300]
    return ok, int((time.monotonic() - t0) * 1000), detail


def main():
    settings = config.load()
    ok, ms, detail = check(os.environ.get("CVWRITE_HEALTHZ_URL", "http://127.0.0.1:8000/healthz"))
    with db.connect(settings.database_url) as conn:
        conn.execute("insert into uptime_checks (ok, ms, detail) values (%s, %s, %s)", (ok, ms, detail))


if __name__ == "__main__":
    main()
