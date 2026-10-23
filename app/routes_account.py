"""Chunk 7a pages: the account page, download my data, delete my account, the deleted page, the terms."""
from pathlib import Path

from fastapi import Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from . import account, credits, notices
from .markdown import to_html

TERMS = Path(__file__).resolve().parent / "content" / "terms.md"


def register(app, h):
    @app.get("/account", response_class=HTMLResponse)
    def account_page(request: Request):
        with h.conn() as c:
            u = h.user(request, c)
            consents = c.execute(
                "select notice_version, lang, sensitive, created_at from consents where email = %s and account_deleted_at is null "
                "order by created_at desc, id desc", (u["email"],)).fetchall()
            reports = c.execute("select count(*) filter (where status = 'answered') answered, count(*) n from problem_reports "
                                "where account_id = %s", (u["account_id"],)).fetchone()
            s = credits.summary(c, u["account_id"])
        latest = notices.latest()
        current = consents[0] if consents else None
        newer_minor = current and notices.parse(latest.version) > notices.parse(current["notice_version"])
        return h.render(request, "account.html", u=u, nav="account", consents=consents, current=current, latest=latest,
                        newer_minor=newer_minor, reports=reports, refundable_n=s.refundable_n, refundable_rm=s.refundable_rm)

    @app.get("/account/download")
    def download(request: Request):
        with h.conn() as c:
            u = h.user(request, c)
            data = account.export_zip(c, h.settings.data_dir, u["account_id"], u["email"])
        return Response(data, media_type="application/zip",
                        headers={"Content-Disposition": 'attachment; filename="cvwrite3-my-data.zip"', "Cache-Control": "private, no-store"})

    @app.post("/account/delete")
    def delete(request: Request, csrf: str = Form(""), confirm: str = Form(""), refund: str = Form("")):
        with h.conn() as c:
            u = h.user(request, c, consent=False)
            h.check_post(request, u["email"], csrf)
            if confirm.strip() != "DELETE":
                raise h.error(request, 400, "Not deleted", "Type DELETE in capitals to confirm. Nothing was changed.")
            refund_rm = credits.summary(c, u["account_id"]).refundable_rm if refund == "yes" else None
            account.delete_account(c, h.settings.data_dir, u["account_id"], u["email"], refund_requested=refund == "yes")
        url = "/deleted" + (f"?refund={refund_rm:.2f}" if refund_rm else "")
        return RedirectResponse(url, 303)

    @app.get("/deleted", response_class=HTMLResponse)
    def deleted(request: Request, refund: str = ""):
        return h.render(request, "deleted.html", signed_out=True, refund=refund[:10])

    @app.get("/terms", response_class=HTMLResponse)
    def terms(request: Request):
        return h.render(request, "terms.html", signed_out=True, body=to_html(TERMS.read_text(encoding="utf-8")))
