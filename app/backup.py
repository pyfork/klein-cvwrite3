"""The backup: the cvwrite3 database only, encrypted on the box, to cvwrite3's own Spaces bucket.

    python -m app.backup            (systemd timer, every night at 02:30; does the work only when due)

- Runs nightly, but backs up only when the last good copy is over 20 hours old: every night, and
  again the next night after a failure. The timer has Persistent=true for a box that was down.
- pg_dump (custom format) -> age encryption to the owner's public key (the private key stays offline
  with the owner) -> upload, with the tombstones file next to it.
- Verified after upload (size and checksum); a copy that doesn't verify counts as failed.
- Upload retries 3 times (1, 5, 15 minutes); the dump is retried once. A failed encrypted dump stays on
  the box (0600) and goes up with the next run.
- Keeps the 4 newest good copies, and deletes older ones only after a newer copy has verified.
PDFs are never backed up (CV text is in the database, and PDFs go after 30 days anyway).
Settings: CVWRITE_BACKUP_BUCKET, CVWRITE_BACKUP_ENDPOINT, CVWRITE_BACKUP_AGE_RECIPIENT,
CVWRITE_BACKUP_KEY_ID and CVWRITE_BACKUP_SECRET (typed by the owner into the .env, never in git).
"""
import hashlib
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from . import config, db

KEEP = 4
DUE_AFTER_H = 20
UPLOAD_WAITS_S = (60, 300, 900)
PREFIX = "cvwrite3/"


class BackupError(RuntimeError):
    pass


def due(conn):
    row = conn.execute("select max(finished_at) t from backup_runs where outcome = 'ok'").fetchone()
    return row["t"] is None or (datetime.now(timezone.utc) - row["t"]).total_seconds() > DUE_AFTER_H * 3600


def last_good_age_days(conn):
    row = conn.execute("select extract(epoch from now() - max(finished_at)) / 86400 d from backup_runs where outcome = 'ok'").fetchone()
    return None if row["d"] is None else float(row["d"])


def encrypt(data, recipient):
    import pyrage
    return pyrage.encrypt(data, [pyrage.x25519.Recipient.from_str(recipient)])


def dump(database_url):
    for attempt in (1, 2):
        r = subprocess.run(["pg_dump", "--format=custom", "--no-owner", "--dbname", database_url], capture_output=True, timeout=600)
        if r.returncode == 0 and r.stdout:
            return r.stdout
        if attempt == 1:
            time.sleep(10)
    raise BackupError("dump_failed")


class SpacesStore:
    """DigitalOcean Spaces through the S3 API."""

    def __init__(self, env=os.environ):
        import boto3
        self.bucket = env["CVWRITE_BACKUP_BUCKET"]
        self.s3 = boto3.client("s3", endpoint_url=env["CVWRITE_BACKUP_ENDPOINT"],
                               aws_access_key_id=env["CVWRITE_BACKUP_KEY_ID"], aws_secret_access_key=env["CVWRITE_BACKUP_SECRET"])

    def put(self, key, data):
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=data, ACL="private",
                           Metadata={"sha256": hashlib.sha256(data).hexdigest()})

    def head(self, key):
        h = self.s3.head_object(Bucket=self.bucket, Key=key)
        return h["ContentLength"], h.get("Metadata", {}).get("sha256")

    def list(self):
        out, token = [], None
        while True:
            kw = {"Bucket": self.bucket, "Prefix": PREFIX, **({"ContinuationToken": token} if token else {})}
            r = self.s3.list_objects_v2(**kw)
            out += [o["Key"] for o in r.get("Contents", [])]
            if not r.get("IsTruncated"):
                return out
            token = r["NextContinuationToken"]

    def delete(self, key):
        self.s3.delete_object(Bucket=self.bucket, Key=key)


def upload_verified(store, key, data, sleep=time.sleep):
    want = (len(data), hashlib.sha256(data).hexdigest())
    for wait in (0, *UPLOAD_WAITS_S):
        if wait:
            sleep(wait)
        try:
            store.put(key, data)
            if store.head(key) == want:
                return
        except Exception:  # network and S3 errors alike: retry, then fail the run
            continue
    raise BackupError("upload_failed")


def prune(store, keep=KEEP):
    """Deletes all but the `keep` newest dumps (and their tombstone files). Called only after a verified upload."""
    dumps = sorted(k for k in store.list() if k.endswith(".dump.age"))
    for k in dumps[:-keep]:
        store.delete(k)
        store.delete(k.replace(".dump.age", ".tombstones.txt"))


def tombstones_text(conn):
    return "".join(f"{r['hash']} {r['deleted_on']}\n" for r in conn.execute("select hash, deleted_on from tombstones order by deleted_on"))


def run(conn, settings, store, recipient, spool_dir, sleep=time.sleep, force=False):
    """One nightly run. Returns the outcome: ok, skipped or failed."""
    if not force and not due(conn):
        conn.execute("insert into backup_runs (outcome, finished_at) values ('skipped', now())")
        return "skipped"
    row = conn.execute("insert into backup_runs default values returning id").fetchone()
    spool = Path(spool_dir)
    spool.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        pending = sorted(spool.glob("*.dump.age"))  # a dump a failed run left behind goes first
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        data = encrypt(dump(settings.database_url), recipient)
        path = spool / f"{stamp}.dump.age"
        path.write_bytes(data)
        path.chmod(0o600)
        for p in [*[q for q in pending if q != path], path]:
            key = PREFIX + p.name
            upload_verified(store, key, p.read_bytes(), sleep)
            upload_verified(store, key.replace(".dump.age", ".tombstones.txt"), tombstones_text(conn).encode(), sleep)
            p.unlink()
        prune(store)
        conn.execute("update backup_runs set outcome = 'ok', finished_at = now(), object_key = %s, bytes = %s, sha256 = %s where id = %s",
                     (PREFIX + path.name, len(data), hashlib.sha256(data).hexdigest(), row["id"]))
        return "ok"
    except Exception as e:
        kind = str(e) if isinstance(e, BackupError) else type(e).__name__
        conn.execute("update backup_runs set outcome = 'failed', finished_at = now(), error_class = %s where id = %s", (kind, row["id"]))
        return "failed"


def main():
    settings = config.load()
    store = SpacesStore()
    with db.connect(settings.database_url) as conn:
        outcome = run(conn, settings, store, os.environ["CVWRITE_BACKUP_AGE_RECIPIENT"],
                      Path(settings.data_dir) / "backup-spool", force="--now" in sys.argv)
    print("backup:", outcome)
    sys.exit(0 if outcome in ("ok", "skipped") else 1)


if __name__ == "__main__":
    main()
