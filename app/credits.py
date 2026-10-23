"""Credits, worked out from the insert-only ledger.

- Each grant (`free` +2, `pack` +5 or +20) has its own `expires_at`, 12 months after it was added.
- A spend uses the oldest grant that was still valid at that moment (so the free 2 go first).
- A refund takes back unused paid credits from the newest pack first, which is where unused credits are.
- Refundable = unused, unexpired paid credits, at the price of the pack they came from.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

PACKS = {5: Decimal("10.00"), 20: Decimal("30.00")}   # credits -> RM
PRICE_PER_CREDIT = {n: rm / n for n, rm in PACKS.items()}  # 5 -> RM2.00, 20 -> RM1.50


@dataclass
class Grant:
    id: int
    kind: str
    n: int
    expires_at: datetime
    created_at: datetime
    left: int = 0

    @property
    def price(self):
        return PRICE_PER_CREDIT.get(self.n, Decimal(0)) if self.kind == "pack" else Decimal(0)


@dataclass
class Summary:
    balance: int
    earliest_expiry: datetime = None
    grants: list = field(default_factory=list)
    refundable_n: int = 0
    refundable_rm: Decimal = Decimal(0)
    overdrawn: int = 0   # spends no valid credit covered (only by a race); never shown as a negative balance


def rows(conn, account_id):
    return conn.execute(
        "select id, delta, kind, expires_at, created_at, run_id from credit_ledger where account_id = %s order by created_at, id",
        (account_id,)).fetchall()


def compute(ledger, now=None):
    now = now or datetime.now(timezone.utc)
    grants, overdrawn = [], 0
    for r in ledger:
        if r["delta"] > 0:
            grants.append(Grant(r["id"], r["kind"], r["delta"], r["expires_at"], r["created_at"], r["delta"]))
            continue
        need = -r["delta"]
        at = r["created_at"]
        if r["kind"] == "refund":
            pool = [g for g in reversed(grants) if g.kind == "pack" and g.expires_at > at]
        else:
            pool = [g for g in grants if g.expires_at > at]
        for g in pool:
            take = min(g.left, need)
            g.left -= take
            need -= take
            if not need:
                break
        overdrawn += need
    live = [g for g in grants if g.left and g.expires_at > now]
    balance = max(0, sum(g.left for g in live) - overdrawn)
    paid = [g for g in live if g.kind == "pack"]
    return Summary(
        balance=balance,
        earliest_expiry=min((g.expires_at for g in live), default=None),
        grants=grants,
        refundable_n=sum(g.left for g in paid),
        refundable_rm=sum((g.left * g.price for g in paid), Decimal(0)).quantize(Decimal("0.01")),
        overdrawn=overdrawn,
    )


def summary(conn, account_id):
    return compute(rows(conn, account_id))


def record_refund(conn, account_id, n):
    """The owner's action, after paying the refund from the bank. Takes back n unused paid credits."""
    with conn.transaction():
        conn.execute("select pg_advisory_xact_lock(%s)", (account_id,))
        s = summary(conn, account_id)
        if not 1 <= n <= s.refundable_n:
            raise ValueError(f"can refund 1 to {s.refundable_n} credits")
        conn.execute("insert into credit_ledger (account_id, delta, kind) values (%s, %s, 'refund')", (account_id, -n))
    refund_rm = Decimal(0)
    left = n
    for g in reversed([g for g in s.grants if g.kind == "pack" and g.left and g.expires_at > datetime.now(timezone.utc)]):
        take = min(g.left, left)
        refund_rm += take * g.price
        left -= take
        if not left:
            break
    return refund_rm.quantize(Decimal("0.01"))
