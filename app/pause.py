"""The MVP pause: one open system_pause row means generating is paused. Auto-pause, manual resume.

Auto-pause when (brief, Addendum 1):
- 3 runs failed both render attempts, from at least 2 users, within 30 minutes;
- the last 5 Claude calls failed after the SDK's retries, across at least 2 users;
- the test render failed twice in a row.
"""


def current(conn):
    return conn.execute("select * from system_pause where resumed_at is null").fetchone()


def pause(conn, reason, source):
    conn.execute(
        "insert into system_pause (reason, source) values (%s, %s) on conflict ((true)) where resumed_at is null do nothing",
        (reason, source))


def resume(conn):
    with conn.transaction():
        conn.execute("update system_pause set resumed_at = now() where resumed_at is null")
        conn.execute("update jobs set status = 'queued', held_at = null where status = 'held'")


def after_render_failure(conn):
    row = conn.execute(
        """select count(*) as runs, count(distinct account_id) as users from runs
           where failure = 'render_failed' and created_at > now() - interval '30 minutes'""").fetchone()
    if row["runs"] >= 3 and row["users"] >= 2:
        pause(conn, "render failures", "auto")


def after_claude_failure(conn):
    rows = conn.execute(
        """select s.outcome, r.account_id from run_steps s left join runs r on r.id = s.run_id
           where s.step in ('call_a', 'call_b', 'retry', 'reformat') order by s.id desc limit 5""").fetchall()
    if len(rows) == 5 and all(r["outcome"] == "error" for r in rows) and len({r["account_id"] for r in rows}) >= 2:
        pause(conn, "Claude API errors", "auto")


def after_test_render(conn):
    rows = conn.execute("select outcome from run_steps where step = 'test_render' order by id desc limit 2").fetchall()
    if len(rows) == 2 and all(r["outcome"] != "ok" for r in rows):
        pause(conn, "test render failed twice", "auto")


def banner(row):
    if not row:
        return None
    hours = row["age_h"] if "age_h" in row else 0
    text = ("Generating is paused. We know about the problem and we're on it. Requests already saved will "
            "finish once it's fixed. You don't need to do anything.")
    if hours >= 4:
        text += f" Paused since {row['paused_at']:%H:%M}: this is taking longer than usual."
    return text


def current_with_age(conn):
    return conn.execute(
        "select *, extract(epoch from now() - paused_at) / 3600 as age_h from system_pause where resumed_at is null").fetchone()
