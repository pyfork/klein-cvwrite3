"""Our own observability: errors, /healthz, uptime checks, degraded events, the health panel and the funnel.
Nothing leaves sk24, and nothing here holds CV, ad, contact or report text."""
import os
import shutil
import traceback
from decimal import Decimal
from pathlib import Path

from render import build_cv

# Starting ceilings (brief: tune after 2 weeks of real data).
CEILINGS = {
    "generation_p95": ("generation", 120.0),   # seconds from the click to passed
    "rerender_p95": ("rerender", 30.0),
    "queue_wait": ("queue_wait", 20.0),
    "failure_rate": ("generation", 0.05),      # share of generations failing in the last hour
}
MIN_SAMPLES = 5   # don't call a ceiling breached on one or two runs


def record_error(conn, exc, route="", run_id=None, request_id=""):
    """Error class and a traceback of file:line in function only: no messages, no locals, no content."""
    frames = traceback.extract_tb(exc.__traceback__)
    tb = "\n".join(f"{Path(f.filename).name}:{f.lineno} in {f.name}" for f in frames[-12:])
    try:
        conn.execute("insert into errors (error_class, route, run_id, request_id, traceback) values (%s, %s, %s, %s, %s)",
                     (type(exc).__name__, route[:200], run_id, request_id, tb))
    except Exception:  # recording an error must never raise a second one
        pass


def healthz(conn, data_dir):
    """{ok, checks}: the database, disk space, Chrome present, queue depth."""
    checks = {}
    try:
        checks["queue"] = conn.execute("select count(*) n from jobs where status in ('queued', 'running')").fetchone()["n"]
        checks["db"] = True
    except Exception:
        checks["db"], checks["queue"] = False, None
    Path(data_dir).mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(data_dir).free
    checks["disk_free_gb"] = round(free / 1e9, 1)
    checks["chrome"] = os.access(build_cv.CHROME, os.X_OK)
    ok = checks["db"] and free > 1e9 and checks["chrome"] and (checks["queue"] or 0) < 50
    return ok, checks


def p95(values):
    if not values:
        return None
    v = sorted(values)
    return v[min(len(v) - 1, int(round(0.95 * (len(v) - 1))))]


def p50(values):
    if not values:
        return None
    v = sorted(values)
    return v[len(v) // 2]


def measure(conn):
    """The last hour's numbers behind each ceiling: {kind: (value, samples)}."""
    gen = [r["s"] for r in conn.execute(
        "select extract(epoch from passed_at - created_at)::float s from runs where passed_at > now() - interval '1 hour'")]
    rer = [r["s"] for r in conn.execute(
        "select extract(epoch from finished_at - created_at)::float s from jobs where kind = 'rerender' and finished_at > now() - interval '1 hour'")]
    wait = [r["ms"] / 1000 for r in conn.execute(
        "select duration_ms ms from run_steps where step = 'queue_wait' and started_at > now() - interval '1 hour'")]
    done = conn.execute(
        "select count(*) filter (where status = 'failed') f, count(*) n from runs where status in ('passed', 'failed') "
        "and created_at > now() - interval '1 hour'").fetchone()
    return {
        "generation_p95": (p95(gen), len(gen)),
        "rerender_p95": (p95(rer), len(rer)),
        "queue_wait": (p95(wait), len(wait)),
        "failure_rate": ((done["f"] / done["n"]) if done["n"] else None, done["n"]),
    }


def evaluate_degraded(conn):
    """Opens an event when a ceiling is breached, closes it when the number is back under."""
    for kind, (value, n) in measure(conn).items():
        step, ceiling = CEILINGS[kind]
        breached = value is not None and n >= MIN_SAMPLES and value > ceiling
        if breached:
            conn.execute("insert into degraded_events (kind, step, value, ceiling) values (%s, %s, %s, %s) "
                         "on conflict (kind) where ended_at is null do update set value = excluded.value",
                         (kind, step, value, ceiling))
        else:
            conn.execute("update degraded_events set ended_at = now() where kind = %s and ended_at is null", (kind,))


def degraded_now(conn):
    return conn.execute("select * from degraded_events where ended_at is null order by started_at").fetchall()


def uptime(conn, hours):
    """Share of minutes in the window with a passing check. Missing minutes count as down."""
    row = conn.execute(
        "select count(distinct date_trunc('minute', checked_at)) filter (where ok) up from uptime_checks "
        "where checked_at > now() - make_interval(hours => %s)", (hours,)).fetchone()
    return min(100.0, 100.0 * row["up"] / (hours * 60))


def panel(conn):
    last = conn.execute("select * from uptime_checks order by checked_at desc limit 1").fetchone()
    steps = {}
    for r in conn.execute("select step, duration_ms from run_steps where started_at > now() - interval '7 days' "
                          "and step in ('queue_wait', 'call_a', 'call_b', 'retry', 'render', 'check', 'reformat')"):
        steps.setdefault(r["step"], []).append(r["duration_ms"] / 1000)
    errors_24h = conn.execute("select count(*) n from errors where created_at > now() - interval '24 hours'").fetchone()["n"]
    fails = conn.execute("select count(*) filter (where status = 'failed') f, count(*) n from runs "
                         "where status in ('passed', 'failed') and created_at > now() - interval '24 hours'").fetchone()
    incidents = conn.execute(
        """select min(checked_at) started, max(checked_at) ended, count(*) n from (
             select checked_at, ok, sum(case when ok then 1 else 0 end) over (order by checked_at) grp from uptime_checks
             where checked_at > now() - interval '7 days') t where not ok group by grp order by started desc limit 5""").fetchall()
    from . import caps
    return {
        "up": bool(last and last["ok"]), "last_check": last,
        "uptime": {"24 h": uptime(conn, 24), "7 days": uptime(conn, 24 * 7), "30 days": uptime(conn, 24 * 30)},
        "steps": {k: (p50(v), p95(v), len(v)) for k, v in sorted(steps.items())},
        "errors_24h": errors_24h,
        "claude_errors": conn.execute(
            "select coalesce(model, '?') model, error_class, count(*) n from run_steps where outcome = 'error' "
            "and step in ('call_a', 'call_b', 'retry', 'reformat') and started_at > now() - interval '24 hours' "
            "group by 1, 2 order by n desc").fetchall(),
        "fail_rate_24h": (fails["f"] / fails["n"]) if fails["n"] else None,
        "queue": conn.execute("select count(*) n from jobs where status in ('queued', 'running')").fetchone()["n"],
        "degraded": degraded_now(conn),
        "incidents": incidents,
        "backup_days": conn.execute("select extract(epoch from now() - max(finished_at)) / 86400 d from backup_runs "
                                    "where outcome = 'ok'").fetchone()["d"],
        "spend": caps.month_spend(conn), "spend_warn": caps.MONTHLY_WARN_USD, "spend_stop": caps.MONTHLY_STOP_USD,
        "orders_waiting": conn.execute("select count(*) n from orders where status = 'pending' and paid_at < now() - interval '2 hours'").fetchone()["n"],
        "privacy_due": conn.execute("select count(*) n from problem_reports where category = 'privacy' and status = 'open' "
                                    "and created_at < now() - interval '14 days'").fetchone()["n"],
    }


THRESHOLDS = {"both_free": 0.60, "bought": 0.20, "repeat": 0.25}


def funnel(conn):
    q = lambda sql: conn.execute(sql).fetchone()  # noqa: E731
    requests = q("select count(*) n from access_requests")["n"]
    approved = q("select count(*) n from allowed_users")["n"]
    both_free = q("""select count(*) n from (select account_id from credit_ledger where kind = 'spend' group by account_id
                     having count(*) >= 2) t""")["n"]
    buyers = q("select count(distinct account_id) n from orders where status = 'approved'")["n"]
    repeat = q("""select count(*) n from (select account_id from orders where status = 'approved' group by account_id
                  having count(*) >= 2) t""")["n"]
    wait = q("""select percentile_cont(0.5) within group (order by extract(epoch from decided_at - paid_at) / 3600) h
                from orders where status = 'approved' and paid_at is not null""")["h"]
    spend = q("select coalesce(sum(cost_usd), 0) s from usage")["s"]
    passed = q("select count(*) n from runs where passed_at is not null")["n"]
    revenue = q("select coalesce(sum(amount_rm), 0) rm from orders where status = 'approved'")["rm"]
    packs = conn.execute("select credits, count(*) n from orders where status = 'approved' group by credits order by credits").fetchall()
    edited = q("select count(*) filter (where rerenders_used > 0) e, coalesce(avg(rerenders_used), 0) a from runs where passed_at is not null")
    reasons = conn.execute("select reason, count(*) n from feedback group by reason order by n desc").fetchall()
    gen_cost = q("""select coalesce(sum(u.cost_usd), 0) / nullif(count(distinct u.run_id), 0) c from usage u
                    where u.step in ('call_a', 'call_b', 'retry')""")["c"]
    share = lambda a, b: (a / b) if b else None  # noqa: E731
    return {
        "requests": requests, "approved": approved, "both_free": both_free, "buyers": buyers, "repeat": repeat,
        "both_free_share": share(both_free, approved), "bought_share": share(buyers, both_free), "repeat_share": share(repeat, buyers),
        "thresholds": THRESHOLDS, "median_wait_h": wait,
        "spend_usd": spend, "revenue_rm": revenue, "cost_per_generation_usd": gen_cost or Decimal(0),
        "passed": passed, "packs": packs,
        "edited_share": share(edited["e"], passed), "rerenders_per_cv": edited["a"],
        "reasons": reasons, "feedback_n": sum(r["n"] for r in reasons),
    }


def retention(conn, data_dir=None):
    """Daily: request logs live in journald (90 days, set in chunk 7). Here: CVs, ads and PDFs 30 days; step rows
    90 days; errors, degraded events and uptime checks 12 months; closed problem reports 12 months after closing;
    consent records 12 months after the account was deleted."""
    if data_dir:
        from . import account
        account.purge_old_runs(conn, data_dir)
    conn.execute("delete from consents where account_deleted_at < now() - interval '12 months'")
    conn.execute("delete from run_steps where started_at < now() - interval '90 days'")
    conn.execute("delete from errors where created_at < now() - interval '12 months'")
    conn.execute("delete from degraded_events where ended_at < now() - interval '12 months'")
    conn.execute("delete from uptime_checks where checked_at < now() - interval '12 months'")
    conn.execute("delete from problem_reports where status = 'closed' and closed_at < now() - interval '12 months'")
