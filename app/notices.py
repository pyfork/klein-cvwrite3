"""Privacy notice versions (MAJOR.MINOR) and what each user still has to agree to.

Each version is notices/vX.Y.<lang>.md, listed in notices/versions.json. A published version never
changes: tests/test_notices.py pins its hash. A draft can still be edited, and prod refuses to start
while the latest version is a draft.
"""
import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

NOTICES = Path(__file__).resolve().parent.parent / "notices"
LANGS = ("en", "ms")


@dataclass(frozen=True)
class Version:
    version: str
    date: str
    status: str
    what: str
    why: str

    @property
    def key(self):
        major, minor = self.version.split(".")
        return int(major), int(minor)

    @property
    def major(self):
        return self.key[0]


def parse(version):
    major, minor = version.split(".")
    return int(major), int(minor)


@lru_cache(maxsize=1)
def versions():
    """Oldest first."""
    raw = json.loads((NOTICES / "versions.json").read_text())
    return tuple(sorted((Version(**v) for v in raw), key=lambda v: v.key))


def latest():
    return versions()[-1]


def keeps_choice():
    """The "keep my applications for 3 months" choice exists once the latest notice is v2.0 or newer, the version that
    says so (Addendum 8). Prod never runs on a draft latest notice, so there it means: v2.0 is published."""
    return latest().key >= (2, 0)


def get(version):
    return next((v for v in versions() if v.version == version), None)


def path(version, lang):
    return NOTICES / f"v{version}.{lang}.md"


def langs(version):
    return [lang for lang in LANGS if path(version, lang).exists()]


def text(version, lang):
    return path(version, lang).read_text(encoding="utf-8")


def text_hash(version, lang):
    return hashlib.sha256(path(version, lang).read_bytes()).hexdigest()


def latest_consent(conn, email):
    return conn.execute(
        "select notice_version, lang, sensitive, created_at from consents "
        "where email = %s and account_deleted_at is null order by created_at desc, id desc limit 1",
        (email,),
    ).fetchone()


def needs_consent(consented_version):
    """'first' if never agreed, 'major' if the latest notice is a newer major version, else None."""
    if consented_version is None:
        return "first"
    if latest().major > parse(consented_version)[0]:
        return "major"
    return None


def changes_since(consented_version):
    """Versions after the one the user agreed to, newest first (for "what changed")."""
    have = parse(consented_version)
    return [v for v in reversed(versions()) if v.key > have]


def record(conn, email, lang, sensitive):
    v = latest()
    conn.execute(
        "insert into consents (email, notice_version, text_hash, lang, sensitive) values (%s, %s, %s, %s, %s)",
        (email, v.version, text_hash(v.version, lang), lang, bool(sensitive)),
    )
    return v.version
