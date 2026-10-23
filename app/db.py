"""Postgres access and the migration runner. Plain SQL, numbered files in migrations/.

Run migrations: python -m app.db migrate   (reads CVWRITE_DATABASE_URL)
"""
import os
import sys
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

MIGRATIONS = Path(__file__).resolve().parent.parent / "migrations"


def connect(url):
    """Autocommit: a single statement commits on its own; multi-step work uses conn.transaction()."""
    return psycopg.connect(url, row_factory=dict_row, autocommit=True)


def migrate(conn):
    """Applies every migration not yet applied, each in its own transaction. Returns their names."""
    conn.execute("create table if not exists schema_migrations (name text primary key, applied_at timestamptz not null default now())")
    done = {r["name"] for r in conn.execute("select name from schema_migrations")}
    applied = []
    for path in sorted(MIGRATIONS.glob("[0-9][0-9][0-9]_*.sql")):
        if path.name in done:
            continue
        with conn.transaction():
            conn.execute(path.read_text())
            conn.execute("insert into schema_migrations (name) values (%s)", (path.name,))
        applied.append(path.name)
    return applied


if __name__ == "__main__":
    if sys.argv[1:] != ["migrate"]:
        sys.exit("usage: python -m app.db migrate")
    with connect(os.environ["CVWRITE_DATABASE_URL"]) as c:
        names = migrate(c)
    print("applied:", ", ".join(names) if names else "nothing new")
