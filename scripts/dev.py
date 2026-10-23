"""Runs the app and the worker on this Mac with a throwaway Postgres, a dev signing key and the fake
Claude (set CVWRITE_CLAUDE=real to use the API). Never on sk24.

    .venv/bin/python scripts/dev.py          then open http://localhost:8766/dev/login

Everything lives in data/dev/ (git-ignored). The owner email here is made up: owner@example.com.
"""
import os
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
DEV = ROOT / "data" / "dev"
PORT = int(os.environ.get("PORT", "8766"))


def main():
    import pgserver
    import uvicorn

    from app import db, devlogin

    DEV.mkdir(parents=True, exist_ok=True)
    pg = pgserver.get_server(str(DEV / "pg"), cleanup_mode=None)
    url = pg.get_uri()
    with db.connect(url) as c:
        print("migrations:", db.migrate(c) or "up to date")
    key, certs = DEV / "key.pem", DEV / "certs.json"
    if not key.exists():
        devlogin.make_keys(key, certs)
    secret = DEV / "secret"
    if not secret.exists():
        secret.write_text(secrets.token_hex(32))
        secret.chmod(0o600)
    os.environ.update(
        CVWRITE_ENV="dev", CVWRITE_DATABASE_URL=url, CVWRITE_OWNER_EMAIL="owner@example.com",
        CVWRITE_SECRET_KEY=secret.read_text(), CVWRITE_ACCESS_TEAM="cvw3-dev.cloudflareaccess.com",
        CVWRITE_ACCESS_AUD="dev-aud", CVWRITE_ACCESS_CERTS_URL=certs.as_uri(),
        CVWRITE_APP_ORIGIN=f"http://localhost:{PORT}", CVWRITE_DEV_KEY_FILE=str(key),
        CVWRITE_DATA_DIR=str(DEV / "files"), CVWRITE_CLAUDE=os.environ.get("CVWRITE_CLAUDE", "fake"),
    )
    # A real-API run reads the key the owner typed into data/dev/anthropic_key (0600). It's never printed.
    key_file = DEV / "anthropic_key"
    if os.environ["CVWRITE_CLAUDE"] == "real":
        if not key_file.exists() or key_file.stat().st_mode & 0o077:
            sys.exit("CVWRITE_CLAUDE=real needs data/dev/anthropic_key with mode 0600")
        os.environ["ANTHROPIC_API_KEY"] = key_file.read_text().strip()
    # The worker runs in a thread here; on sk24 it's its own systemd unit.
    import threading
    from app import config, worker
    threading.Thread(target=worker.serve, args=(config.load(),), daemon=True).start()
    uvicorn.run("app.main:create_app", factory=True, host="127.0.0.1", port=PORT, access_log=False)


if __name__ == "__main__":
    main()
