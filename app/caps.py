"""The caps checked before every generation and re-render (brief, Caps and spend; Addendum 1).

- Per user: 20 a day (Malaysia time), paid ones included. A generation counts once it reached call A;
  each Haiku re-render counts too.
- Global: a $50 monthly stop with a $20 warning. It blocks free generations only, never paid ones.
"""
from datetime import datetime, timezone
from decimal import Decimal

from . import credits, db

DAILY_CAP = 20
MONTHLY_STOP_USD = Decimal("50")
MONTHLY_WARN_USD = Decimal("20")
TZ = db.TZ


def used_today(conn, account_id):
    return conn.execute(
        f"""select count(*) n from usage where account_id = %s and step in ('call_a', 'reformat')
            and (created_at at time zone '{TZ}')::date = (now() at time zone '{TZ}')::date""",
        (account_id,)).fetchone()["n"]


def month_spend(conn):
    return conn.execute(
        f"""select coalesce(sum(cost_usd), 0) s from usage
            where date_trunc('month', created_at at time zone '{TZ}') = date_trunc('month', now() at time zone '{TZ}')""").fetchone()["s"]


def next_credit_is_free(conn, account_id, reserved=0):
    """Would the next CV be paid for with a free credit? Credits are spent oldest first, so look past the
    `reserved` ones already promised to CVs still generating."""
    s = credits.summary(conn, account_id)
    now = datetime.now(timezone.utc)
    for g in s.grants:
        if g.expires_at <= now or not g.left:
            continue
        if reserved >= g.left:
            reserved -= g.left
            continue
        return g.kind == "free"
    return False


def queued_before_call_a(conn, account_id):
    """CVs started but not yet at call A: they'll count toward today's cap once they get there."""
    return conn.execute("select count(*) n from runs where account_id = %s and status = 'generating' and ad_read is null",
                        (account_id,)).fetchone()["n"]


def generation_blocked(conn, account_id, reserved=0):
    """A user message, or None. `reserved` = CVs still generating, which hold credits."""
    if used_today(conn, account_id) + queued_before_call_a(conn, account_id) >= DAILY_CAP:
        return f"You've reached today's limit of {DAILY_CAP} CVs and re-renders. It resets at midnight, Malaysia time."
    if month_spend(conn) >= MONTHLY_STOP_USD and next_credit_is_free(conn, account_id, reserved):
        return "Free CVs are paused for the rest of this month. CVs from paid credits still work."
    return None


def rerender_blocked(conn, account_id):
    if used_today(conn, account_id) >= DAILY_CAP:
        return f"You've reached today's limit of {DAILY_CAP} CVs and re-renders. It resets at midnight, Malaysia time. Your text is kept."
    return None
