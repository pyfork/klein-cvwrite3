"""Orders paid by DuitNow QR. The owner checks the reference and amount in the bank app, then approves
(which writes the +5 or +20 ledger row, once) or rejects with a reason the user sees.

Credits are added only when the owner approves, never because the user pressed "I've paid".
No receipts, payer names or emails are taken or stored.
"""
import secrets

from . import credits

REF_CHARS = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no 0/O, 1/I/L


class OrderError(ValueError):
    """The message is shown to the user or the owner."""


def new_ref():
    return "CV3-" + "".join(secrets.choice(REF_CHARS) for _ in range(4))


def create(conn, account_id, n):
    if n not in credits.PACKS:
        raise OrderError("Pick one of the two packs.")
    with conn.transaction():
        conn.execute("select pg_advisory_xact_lock(%s)", (account_id,))
        if conn.execute("select 1 from orders where account_id = %s and status = 'pending' and paid_at is null", (account_id,)).fetchone():
            raise OrderError("You already have an order waiting for payment. Pay it or cancel it first.")
        while True:
            row = conn.execute(
                "insert into orders (account_id, ref, credits, amount_rm) values (%s, %s, %s, %s) on conflict (ref) do nothing returning *",
                (account_id, new_ref(), n, credits.PACKS[n])).fetchone()
            if row:
                return row


def get(conn, account_id, ref):
    return conn.execute("select * from orders where account_id = %s and ref = %s", (account_id, ref)).fetchone()


def mark_paid(conn, order):
    conn.execute("update orders set paid_at = coalesce(paid_at, now()) where id = %s and status = 'pending'", (order["id"],))


def cancel(conn, order):
    """Only before "I've paid": after that, money may already be on its way, so the owner decides."""
    n = conn.execute("update orders set status = 'cancelled', decided_at = now() where id = %s and status = 'pending' and paid_at is null",
                     (order["id"],)).rowcount
    if not n:
        raise OrderError("This order can't be cancelled now. If you've paid, we'll check it in the bank.")


def approve(conn, order_id):
    """The owner saw the money in the bank. Approves once: a second call does nothing and returns None."""
    with conn.transaction():
        o = conn.execute(
            "update orders set status = 'approved', decided_at = now() where id = %s and status = 'pending' returning *",
            (order_id,)).fetchone()
        if not o:
            return None
        conn.execute(
            "insert into credit_ledger (account_id, delta, kind, expires_at, order_id) values (%s, %s, 'pack', now() + interval '12 months', %s)",
            (o["account_id"], o["credits"], o["id"]))
    return o


def thank(conn, order, mail, origin):
    """Addendum 11: one thank-you email per approved order, to the account that paid. A failed send never undoes the
    approval: it's recorded without the address and not tried again (the credits already show on the page)."""
    if order is None or order.get("thanked_at"):
        return False
    row = conn.execute("select email from allowed_users where account_id = %s", (order["account_id"],)).fetchone()
    if not row:
        return False
    try:
        mail.send_thanks(row["email"], order["credits"], order["ref"], origin)
    except Exception as e:  # MailError, or anything else: nothing about the address is logged
        from . import health
        health.record_error(conn, e, route="orders.thank")
        return False
    conn.execute("update orders set thanked_at = now() where id = %s and thanked_at is null", (order["id"],))
    return True


def reject(conn, order_id, reason):
    reason = " ".join((reason or "").split())[:300]
    if not reason:
        raise OrderError("Write the reason the user will see.")
    n = conn.execute(
        "update orders set status = 'rejected', reason = %s, decided_at = now() where id = %s and status = 'pending'",
        (reason, order_id)).rowcount
    if not n:
        raise OrderError("That order was already decided.")


def for_account(conn, account_id):
    return conn.execute("select * from orders where account_id = %s and status <> 'cancelled' order by created_at desc limit 20",
                        (account_id,)).fetchall()


def for_admin(conn):
    return conn.execute(
        """select o.*, coalesce(u.email, 'deleted-' || a.tag) as who from orders o join accounts a on a.id = o.account_id
           left join allowed_users u on u.account_id = o.account_id
           where o.status <> 'cancelled'
           order by (o.status = 'pending') desc, o.paid_at is null, coalesce(o.paid_at, o.created_at), o.id desc limit 100""").fetchall()


def buying_closed(pause_row):
    """Buying closes once generating has been paused for 4 hours (brief, Addendum 1)."""
    return bool(pause_row) and float(pause_row["age_h"]) >= 4
