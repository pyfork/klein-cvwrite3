"""Senior S5: every migration is additive, so a rollback (the previous tag's code on the newer schema)
keeps working. Run: python3 -m unittest discover tests

Refused: dropping a table, column or other object; renames; changing a column's type; set not null;
truncate; delete from; a new not-null column without a default. A destructive change ("contract") is
allowed only in a later deploy, once no running code uses the old shape, and its file says so on a line
of its own: `-- contract: <why, and which earlier deploy stopped using it>`.
Not caught: a new check constraint that old code would break. Review those by hand.
"""
import re
import unittest
from pathlib import Path

from app.db import MIGRATIONS

RULES = [
    (re.compile(r"^drop\s+(table|view|materialized|schema|type|function|sequence|index|extension)\b"), "drops an object"),
    (re.compile(r"\bdrop\s+column\b"), "drops a column"),
    (re.compile(r"\brename\b"), "renames"),
    (re.compile(r"\balter\s+column\s+\S+\s+(set\s+data\s+)?type\b"), "changes a column type"),
    (re.compile(r"\bset\s+not\s+null\b"), "sets not null"),
    (re.compile(r"^truncate\b"), "truncates"),
    (re.compile(r"^delete\s+from\b"), "deletes rows"),
    (re.compile(r"\badd\s+column\b(?:(?!\bdefault\b)[^,])*\bnot\s+null\b(?:(?!\bdefault\b)[^,])*$"), "adds a not-null column without a default"),
]
CONTRACT = re.compile(r"^--\s*contract:\s*\S", re.M)


def statements(sql):
    sql = re.sub(r"--[^\n]*", "", sql).lower()
    return [" ".join(s.split()) for s in sql.split(";") if s.strip()]


def problems(sql):
    if CONTRACT.search(sql):
        return []
    found = []
    for stmt in statements(sql):
        # a column clause at a time, so one column's default doesn't excuse another's not null
        for part in [stmt, *stmt.split(",")]:
            found += [label for rx, label in RULES if rx.search(part.strip())]
    return sorted(set(found))


class Additive(unittest.TestCase):
    def test_every_migration_is_additive(self):
        for path in sorted(MIGRATIONS.glob("[0-9][0-9][0-9]_*.sql")):
            with self.subTest(migration=path.name):
                self.assertEqual(problems(path.read_text()), [])

    def test_the_rules_catch_destructive_changes(self):
        for sql in ("drop table runs;", "alter table runs drop column ad_text;", "alter table runs rename to r;",
                    "alter table runs alter column drafts type bigint;", "alter table runs alter column ad_text set not null;",
                    "truncate runs;", "delete from runs where true;", "alter table runs add column x int not null;"):
            with self.subTest(sql=sql):
                self.assertNotEqual(problems(sql), [])

    def test_additive_changes_pass(self):
        for sql in ("alter table runs add column x int;", "alter table runs add column x int not null default 0;",
                    "alter table runs alter column ad_text drop not null;", "create index runs_x on runs (x);",
                    "create trigger t before truncate on runs for each statement execute function f();"):
            with self.subTest(sql=sql):
                self.assertEqual(problems(sql), [])

    def test_a_marked_contract_is_allowed(self):
        self.assertEqual(problems("-- contract: runs.old unused since v0.8.0\nalter table runs drop column old;"), [])


if __name__ == "__main__":
    unittest.main()
