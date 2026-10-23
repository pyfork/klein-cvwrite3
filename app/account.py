"""The account: download my data, delete my account, the 30-day purge, and tombstones.

Deleting is the user's own action only; agents never run it. What goes and what stays
(docs/README-pdpa-deletion-strategy.md, private):
- deleted now: profile, master CV, every run's ad, ad read and CV text, PDFs, re-render text,
  problem reports, the whitelist row and access requests;
- kept, with no CV content: orders and the credit ledger, under the account's random tag;
- kept 12 months: the consent records (proof of consent, and no repeat free credits);
- backups: gone within 14 days. A tombstone stops a restore from bringing the account back.
"""
import hashlib
import io
import json
import zipfile
from datetime import date, datetime

from render import contact as contact_mod

from . import credits, cvtext, profile, rendering


class DeleteError(ValueError):
    pass


def tombstone_hash(account_id):
    return hashlib.sha256(f"cvwrite3-tombstone:{account_id}".encode()).hexdigest()


# ---- the 30-day purge, and purging one run -----------------------------------------------------
def purge_run(conn, data_dir, run):
    """Removes a run's content and its PDF. The row stays, empty, because the ledger points at it."""
    conn.execute(
        "update runs set ad_text = null, ad_read = null, draft_md = null, gaps = null, checks = null, keyword_status = null, "
        "purged_at = now() where id = %s", (run["id"],))
    conn.execute("update jobs set input_text = null where run_id = %s", (run["id"],))
    if run.get("pdf_rev"):
        rendering.pdf_path(data_dir, run["id"], run["pdf_rev"]).unlink(missing_ok=True)


def purge_old_runs(conn, data_dir, days=30):
    rows = conn.execute(
        "select id, pdf_rev from runs where purged_at is null and status <> 'generating' "
        "and created_at < now() - make_interval(days => %s)", (days,)).fetchall()
    for r in rows:
        purge_run(conn, data_dir, r)
    return len(rows)


# ---- download my data ----------------------------------------------------------------------------
def _json(obj):
    def default(o):
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        return str(o)
    return json.dumps(obj, indent=2, ensure_ascii=False, default=default)


def export_zip(conn, data_dir, account_id, email):
    """Everything we hold about the user, as a zip (access and portability)."""
    p = profile.get(conn, account_id)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("README.txt", "Your data from cvwrite3, as of " + datetime.now().strftime("%d %b %Y %H:%M") +
                   ".\nruns/ holds each CV we still have (we keep CVs for 30 days).\n")
        z.writestr("profile.json", _json({"email": email, **{k: p[k] for k in (*profile.CONTACT, "standing_edits")},
                                          "master_cv_file": p["master_name"]}))
        z.writestr("master_cv.txt", p["master_text"])
        data = profile.contact(p)
        for r in conn.execute("select * from runs where account_id = %s and purged_at is null order by id", (account_id,)):
            d = f"runs/{r['id']}"
            z.writestr(f"{d}/ad.txt", r["ad_text"] or "")
            if r["ad_read"]:
                z.writestr(f"{d}/ad_read.json", _json(r["ad_read"]))
            if r["status"] == "passed" and r["draft_md"]:
                try:
                    md = contact_mod.merge(r["draft_md"], data)
                except contact_mod.MergeError:
                    md = r["draft_md"]
                z.writestr(f"{d}/cv.md", md)
                z.writestr(f"{d}/cv.txt", cvtext.to_plain(r["draft_md"]))
                pdf = rendering.pdf_path(data_dir, r["id"], r["pdf_rev"])
                if pdf.exists():
                    z.write(pdf, f"{d}/cv.pdf")
        z.writestr("credit_ledger.json", _json(conn.execute(
            "select delta, kind, expires_at, created_at, run_id, order_id from credit_ledger where account_id = %s order by id",
            (account_id,)).fetchall()))
        z.writestr("orders.json", _json(conn.execute(
            "select ref, credits, amount_rm, status, paid_at, decided_at, reason, created_at from orders where account_id = %s order by id",
            (account_id,)).fetchall()))
        z.writestr("consents.json", _json(conn.execute(
            "select notice_version, text_hash, lang, sensitive, created_at from consents where email = %s order by id", (email,)).fetchall()))
        z.writestr("problem_reports.json", _json(conn.execute(
            "select category, body, status, reply, created_at, answered_at from problem_reports where account_id = %s order by id",
            (account_id,)).fetchall()))
    return buf.getvalue()


# ---- delete my account -------------------------------------------------------------------------------
def delete_account(conn, data_dir, account_id, email, refund_requested=False):
    """The user's own action. Returns the account's tag (what orders and the ledger now show)."""
    with conn.transaction():
        conn.execute("select pg_advisory_xact_lock(%s)", (account_id,))
        acct = conn.execute("select * from accounts where id = %s and deleted_at is null", (account_id,)).fetchone()
        if not acct:
            raise DeleteError("already deleted")
        refund_rm = credits.summary(conn, account_id).refundable_rm if refund_requested else None
        # Stop any running work first, so no -1 can land after the delete.
        conn.execute("update runs set status = 'cancelled' where account_id = %s and status = 'generating'", (account_id,))
        conn.execute("update jobs set status = 'cancelled', finished_at = now() where status in ('queued', 'running', 'held') "
                     "and run_id in (select id from runs where account_id = %s)", (account_id,))
        for r in conn.execute("select id, pdf_rev from runs where account_id = %s", (account_id,)).fetchall():
            purge_run(conn, data_dir, r)
        conn.execute("delete from profiles where account_id = %s", (account_id,))
        conn.execute("delete from problem_reports where account_id = %s", (account_id,))
        conn.execute("delete from access_requests where email = %s", (email,))
        conn.execute("delete from allowed_users where account_id = %s", (account_id,))
        conn.execute("update orders set flag = 'account deleted: refund if received' where account_id = %s and status = 'pending'", (account_id,))
        conn.execute("update consents set account_deleted_at = now() where email = %s and account_deleted_at is null", (email,))
        conn.execute("update accounts set deleted_at = now(), refund_requested_rm = %s where id = %s", (refund_rm, account_id))
        conn.execute("insert into tombstones (hash) values (%s) on conflict do nothing", (tombstone_hash(account_id),))
    return acct["tag"]


def replay_tombstones(conn, data_dir):
    """After a restore from backup: delete again every account that was deleted after the backup was made."""
    stones = {r["hash"] for r in conn.execute("select hash from tombstones")}
    n = 0
    for a in conn.execute("select a.id, u.email from accounts a join allowed_users u on u.account_id = a.id").fetchall():
        if tombstone_hash(a["id"]) in stones:
            delete_account(conn, data_dir, a["id"], a["email"])
            n += 1
    return n


if __name__ == "__main__":
    # python -m app.account tombstones          prints every tombstone hash (the backup job saves this next to the dump)
    # python -m app.account replay FILE         after a restore: load the saved hashes, then delete those accounts again
    import sys
    from . import config, db
    settings = config.load()
    with db.connect(settings.database_url) as c:
        if sys.argv[1:] == ["tombstones"]:
            for r in c.execute("select hash, deleted_on from tombstones order by deleted_on"):
                print(r["hash"], r["deleted_on"])
        elif len(sys.argv) == 3 and sys.argv[1] == "replay":
            for line in open(sys.argv[2], encoding="utf-8"):
                parts = line.split()
                if parts:
                    c.execute("insert into tombstones (hash, deleted_on) values (%s, %s) on conflict do nothing", (parts[0], parts[1]))
            print("deleted again:", replay_tombstones(c, settings.data_dir))
        else:
            sys.exit("usage: python -m app.account tombstones | replay FILE")
