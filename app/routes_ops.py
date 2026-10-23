"""Chunk 6 pages: "not good" feedback, report a problem (user and admin), and /healthz."""
from fastapi import Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from . import health, pause

CATEGORIES = {"broke": "Something broke", "paid": "I paid but have no credits", "output": "The CV is wrong",
              "privacy": "A privacy or data request", "other": "Something else"}
REASONS = {"problem": "Wrong main problem", "keywords": "Wrong keywords", "long": "Too long", "wording": "Wording", "other": "Other"}
LOOPBACK = ("127.0.0.1", "::1")


def register(app, h, app_version):
    @app.post("/runs/{run_id}/feedback")
    def feedback(request: Request, run_id: int, csrf: str = Form(""), reason: str = Form("")):
        with h.conn() as c:
            u = h.user(request, c)
            h.check_post(request, u["email"], csrf)
            if reason not in REASONS:
                raise h.error(request, 400, "Pick a reason", "Choose what's wrong with the CV, then send.")
            if not c.execute("select 1 from runs where id = %s and account_id = %s and status = 'passed'", (run_id, u["account_id"])).fetchone():
                raise h.error(request, 404, "Not found", "There's no finished CV with that number in your account.")
            c.execute("insert into feedback (run_id, account_id, reason) values (%s, %s, %s) on conflict (run_id) do nothing",
                      (run_id, u["account_id"], reason))
        return RedirectResponse(f"/runs/{run_id}?feedback=1", 303)

    # ---- report a problem ---------------------------------------------------------------
    @app.get("/report", response_class=HTMLResponse)
    def report_form(request: Request, run: int = 0, order: str = "", page: str = "", category: str = ""):
        with h.conn() as c:
            u = h.user(request, c, consent=False)
            paused = pause.current(c)
        return h.render(request, "report.html", u=u, run=run or "", order=order[:12], page=page[:200],
                        category=category if category in CATEGORIES else "", categories=CATEGORIES, paused=bool(paused))

    @app.post("/report")
    def report_post(request: Request, csrf: str = Form(""), category: str = Form(""), body: str = Form(""),
                    run: str = Form(""), order: str = Form(""), page: str = Form("")):
        with h.conn() as c:
            u = h.user(request, c, consent=False)
            h.check_post(request, u["email"], csrf)
            if category not in CATEGORIES:
                raise h.error(request, 400, "Pick a category", "Choose what happened, then send.")
            if category == "broke" and pause.current(c):
                return RedirectResponse("/reports?known=1", 303)  # we already know; no duplicate reports during a pause
            run_id = int(run) if run.isdigit() and c.execute(
                "select 1 from runs where id = %s and account_id = %s", (int(run), u["account_id"])).fetchone() else None
            o = c.execute("select id from orders where ref = %s and account_id = %s", (order, u["account_id"])).fetchone() if order else None
            if category == "paid" and not o:  # link a payment report to the user's latest order
                o = c.execute("select id from orders where account_id = %s and status <> 'cancelled' order by created_at desc limit 1",
                              (u["account_id"],)).fetchone()
            c.execute(
                "insert into problem_reports (account_id, email, category, body, run_id, order_id, page, request_id, app_version) "
                "values (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (u["account_id"], u["email"], category, body.strip()[:2000], run_id, o["id"] if o else None,
                 page[:200], request.state.id, app_version))
        return RedirectResponse("/reports?sent=1", 303)

    @app.get("/reports", response_class=HTMLResponse)
    def my_reports(request: Request, sent: int = 0, known: int = 0):
        with h.conn() as c:
            u = h.user(request, c, consent=False)
            rows = c.execute("select * from problem_reports where account_id = %s order by created_at desc", (u["account_id"],)).fetchall()
        return h.render(request, "reports.html", u=u, reports=rows, categories=CATEGORIES, sent=bool(sent), known=bool(known))

    @app.post("/admin/reports/{report_id}/reply")
    def admin_reply(request: Request, report_id: int, csrf: str = Form(""), reply: str = Form("")):
        o = h.owner(request)
        h.check_post(request, o["email"], csrf)
        if not reply.strip():
            raise h.error(request, 400, "Write a reply", "The user sees this reply on their reports page.")
        with h.conn() as c:
            c.execute("update problem_reports set reply = %s, status = 'answered', answered_at = now() where id = %s and status <> 'closed'",
                      (reply.strip()[:2000], report_id))
        return RedirectResponse("/admin#reports", 303)

    @app.post("/admin/reports/{report_id}/close")
    def admin_close(request: Request, report_id: int, csrf: str = Form("")):
        o = h.owner(request)
        h.check_post(request, o["email"], csrf)
        with h.conn() as c:
            c.execute("update problem_reports set status = 'closed', closed_at = now() where id = %s", (report_id,))
        return RedirectResponse("/admin#reports", 303)

    # ---- /healthz: for the local timer only ---------------------------------------------------
    @app.get("/healthz")
    def healthz(request: Request):
        # Only a direct call on the box: nginx adds X-Forwarded-For to everything it proxies.
        if (request.client and request.client.host) not in LOOPBACK or request.headers.get("x-forwarded-for"):
            return Response(status_code=404)
        with h.conn() as c:
            ok, checks = health.healthz(c, h.settings.data_dir)
        return JSONResponse({"ok": ok, **checks}, status_code=200 if ok else 503)

    def admin_reports(c):
        return c.execute(
            """select r.*, o.ref as order_ref, 21 - extract(day from now() - r.created_at)::int as days_left
               from problem_reports r left join orders o on o.id = r.order_id
               where r.status <> 'closed' order by r.status = 'answered', r.created_at""").fetchall()

    return admin_reports
