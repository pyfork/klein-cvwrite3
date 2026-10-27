"""Cost and credits per CV, for the owner: every run that spent tokens, newest first. Numbers only, never content.
The admin page shows the latest 20; the CSV has them all."""
import csv
import io

COLUMNS = ("run_id", "created_at", "status", "input_tokens", "output_tokens", "cost_usd", "rerender_cost_usd", "credits_used", "interview_prep")


def rows(conn, limit=None):
    return conn.execute(
        """select r.id run_id, r.created_at, r.status,
                  coalesce(sum(u.input_tokens), 0) input_tokens, coalesce(sum(u.output_tokens), 0) output_tokens,
                  coalesce(sum(u.cost_usd) filter (where u.step <> 'reformat'), 0) cost_usd,
                  coalesce(sum(u.cost_usd) filter (where u.step = 'reformat'), 0) rerender_cost_usd,
                  (select coalesce(-sum(l.delta), 0) from credit_ledger l where l.run_id = r.id and l.kind = 'spend') credits_used,
                  r.interview_prep is not null interview_prep
           from runs r join usage u on u.run_id = r.id
           group by r.id order by r.created_at desc, r.id desc""" + (" limit %s" if limit else ""),
        (limit,) if limit else ()).fetchall()


def to_csv(conn):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(COLUMNS)
    for r in rows(conn):
        w.writerow([r["created_at"].isoformat() if k == "created_at" else r[k] for k in COLUMNS])
    return buf.getvalue()
