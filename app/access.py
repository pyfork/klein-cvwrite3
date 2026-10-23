"""The whitelist: access requests, approval (by the owner or by wave 2), and the 2 free credits."""
import json
import secrets

TAG_CHARS = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
WAVE2_LOCK = 3_200_001  # pg_advisory_xact_lock key: one approval at a time, so the cap holds


def allowed(conn, email):
    return conn.execute(
        "select email, account_id, approved_at, approved_via from allowed_users where email = %s", (email,)
    ).fetchone()


def pending_request(conn, email):
    return conn.execute(
        "select id, created_at from access_requests where email = %s and status = 'pending'", (email,)
    ).fetchone()


def wave2_on(conn):
    row = conn.execute("select value from settings where key = 'wave2_auto_approve'").fetchone()
    return bool(row and row["value"])


def set_wave2(conn, on):
    conn.execute("update settings set value = %s where key = 'wave2_auto_approve'", (json.dumps(bool(on)),))


def user_count(conn):
    return conn.execute("select count(*) as n from allowed_users").fetchone()["n"]


def deleted_recently(conn, email):
    """True if this email deleted an account in the last 12 months (its consent record is kept that long)."""
    return conn.execute(
        "select 1 from consents where email = %s and account_deleted_at > now() - interval '12 months' limit 1", (email,)
    ).fetchone() is not None


def _new_account(conn):
    while True:
        tag = "".join(secrets.choice(TAG_CHARS) for _ in range(6))
        row = conn.execute(
            "insert into accounts (tag) values (%s) on conflict (tag) do nothing returning id", (tag,)
        ).fetchone()
        if row:
            return row["id"]


def _approve(conn, email, via):
    """Adds the email to the whitelist. The 2 free credits are skipped for a recent deleter."""
    account_id = _new_account(conn)
    conn.execute(
        "insert into allowed_users (email, account_id, approved_via) values (%s, %s, %s)", (email, account_id, via)
    )
    free = not deleted_recently(conn, email)
    if free:
        conn.execute(
            "insert into credit_ledger (account_id, delta, kind, expires_at) values (%s, 2, 'free', now() + interval '12 months')",
            (account_id,),
        )
    conn.execute(
        "update access_requests set status = 'approved', decided_at = now() where email = %s and status = 'pending'", (email,)
    )
    return free


def request_access(conn, settings, email, note):
    """Returns 'allowed', 'pending' or 'approved' (wave 2 let them straight in)."""
    note = " ".join(note.split())[:200]
    with conn.transaction():
        conn.execute("select pg_advisory_xact_lock(%s)", (WAVE2_LOCK,))
        if allowed(conn, email):
            return "allowed"
        if not pending_request(conn, email):
            conn.execute("insert into access_requests (email, note) values (%s, %s)", (email, note))
        if wave2_on(conn) and user_count(conn) < settings.wave2_cap:
            _approve(conn, email, "wave2")
            return "approved"
    return "pending"


def decide(conn, request_id, approve):
    """The owner's approve or decline. Returns (email, free_credits_granted), or None if already decided."""
    with conn.transaction():
        conn.execute("select pg_advisory_xact_lock(%s)", (WAVE2_LOCK,))
        row = conn.execute(
            "select email from access_requests where id = %s and status = 'pending' for update", (request_id,)
        ).fetchone()
        if not row:
            return None
        if not approve:
            conn.execute("update access_requests set status = 'declined', decided_at = now() where id = %s", (request_id,))
            return row["email"], False
        if allowed(conn, row["email"]):
            conn.execute("update access_requests set status = 'approved', decided_at = now() where id = %s", (request_id,))
            return row["email"], False
        return row["email"], _approve(conn, row["email"], "owner")


def pending_requests(conn):
    return conn.execute(
        """select r.id, r.email, r.note, r.created_at,
                  exists (select 1 from consents c where c.email = r.email
                          and c.account_deleted_at > now() - interval '12 months') as deleted_recently
           from access_requests r where r.status = 'pending' order by r.created_at"""
    ).fetchall()
