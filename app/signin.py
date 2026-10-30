"""Sign-in by a 6-digit code sent to the user's email (chunk 7j; replaces Cloudflare Access).

A code lasts 10 minutes and allows 5 tries; asking for a new one cuts the old ones down to 5 minutes left
(never longer than they had), so a stranger asking can't kill your code. Codes and session
tokens are stored only as HMACs under the app's secret key. A session lasts 30 days from its last use.
Any email can get a code: the whitelist (app.access) decides what a signed-in email can do.
"""
import hashlib
import hmac
import re
import secrets

CODE_TTL_MIN = 10
OLD_CODE_MIN = 5   # what an older unused code keeps when a newer one is asked for
MAX_TRIES = 5
PER_EMAIL = 3      # codes per email per 15 minutes
PER_IP = 10        # codes per IP per hour
PER_DAY = 300      # codes for everyone per day: a ceiling on what the mail account can be made to send
SESSION_DAYS = 30
EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")


class TooMany(Exception):
    pass


def _mac(settings, kind, value):
    return hmac.new(settings.secret_key.encode(), f"{kind}:{value}".encode(), hashlib.sha256).hexdigest()


def clean_email(raw):
    email = (raw or "").strip().lower()
    return email if len(email) <= 254 and EMAIL.match(email) else None


def send_code(conn, settings, mailer, email, ip):
    """Mails a fresh code, or raises TooMany. The row is committed before sending, so a failed send still counts."""
    eh, ih = _mac(settings, "email", email), _mac(settings, "ip", ip or "-")
    with conn.transaction():
        n = conn.execute("""select count(*) filter (where email_hash = %s and created_at > now() - interval '15 minutes') e,
                                   count(*) filter (where ip_hash = %s and created_at > now() - interval '1 hour') i,
                                   count(*) filter (where created_at > now() - interval '1 day') d
                            from login_codes where created_at > now() - interval '1 day'""", (eh, ih)).fetchone()
        if n["e"] >= PER_EMAIL or n["i"] >= PER_IP or n["d"] >= PER_DAY:
            raise TooMany()
        code = f"{secrets.randbelow(10 ** 6):06d}"
        conn.execute("update login_codes set expires_at = least(expires_at, now() + make_interval(mins => %s)) "
                     "where email_hash = %s and used_at is null", (OLD_CODE_MIN, eh))
        conn.execute("insert into login_codes (email_hash, ip_hash, code_hash, expires_at) "
                     "values (%s, %s, %s, now() + make_interval(mins => %s))",
                     (eh, ih, _mac(settings, "code", f"{email}:{code}"), CODE_TTL_MIN))
    mailer.send_code(email, code)


def check_code(conn, settings, email, code):
    """True once for the right code; every try counts, and the 6th try fails even when right.
    Any live code of this email can match, so a newer request doesn't kill an older code."""
    code = re.sub(r"\D", "", code or "")
    with conn.transaction():
        rows = conn.execute("select id, code_hash, attempts from login_codes where email_hash = %s and used_at is null "
                            "and expires_at > now() order by id desc for update", (_mac(settings, "email", email),)).fetchall()
        rows = [r for r in rows if r["attempts"] < MAX_TRIES]
        if not rows:
            return False
        want = _mac(settings, "code", f"{email}:{code}")
        hit = next((r for r in rows if len(code) == 6 and hmac.compare_digest(r["code_hash"], want)), None)
        conn.execute("update login_codes set attempts = attempts + 1 where id = any(%s)", ([r["id"] for r in rows],))
        if hit:
            conn.execute("update login_codes set used_at = now() where id = %s", (hit["id"],))
    return hit is not None


def start_session(conn, settings, email):
    token = secrets.token_urlsafe(32)
    conn.execute("insert into sessions (token_hash, email, expires_at) values (%s, %s, now() + make_interval(days => %s))",
                 (_mac(settings, "session", token), email, SESSION_DAYS))
    return token


def session_email(conn, settings, token):
    """The email a live session belongs to, or None. Use pushes the expiry out (at most once an hour)."""
    if not token:
        return None
    th = _mac(settings, "session", token)
    row = conn.execute("select email, last_seen_at < now() - interval '1 hour' stale from sessions "
                       "where token_hash = %s and expires_at > now()", (th,)).fetchone()
    if not row:
        return None
    if row["stale"]:
        conn.execute("update sessions set last_seen_at = now(), expires_at = now() + make_interval(days => %s) "
                     "where token_hash = %s", (SESSION_DAYS, th))
    return row["email"]


def end_session(conn, settings, token):
    if token:
        conn.execute("delete from sessions where token_hash = %s", (_mac(settings, "session", token),))


def purge(conn):
    """Daily: codes after a day (they hold only HMACs), expired sessions at once. Account deletion ends the
    user's sessions itself (app.account)."""
    conn.execute("delete from login_codes where created_at < now() - interval '1 day'")
    conn.execute("delete from sessions where expires_at < now()")
