"""Chunk 7v (Addendum 8): your applications. One row per job (the same ad is the same job), newest first, with the ad and
the latest CV. Kept 30 days; if the user ticks "Keep my applications for 3 months", 3 months. The tick exists once the
v2.0 notice, which says so, is the latest (notices.keeps_choice)."""
from fastapi import Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from . import cvtext, notices

LIST_MAX = 100
KEY = "coalesce(r.ad_hash, 'run:' || r.id::text)"   # CVs made from the same ad are one job; a run with no hash stands alone


def jobs(c, account_id):
    """[{id, status, title, created_at, working, problem, keywords, prep}], newest first: per job, its latest passed CV (else its latest run)."""
    rows = c.execute(
        f"""with x as (
              select r.id, r.status, r.created_at, r.ad_read->>'job_title' as title, left(r.ad_text, 200) as ad_start, {KEY} as g,
                     r.ad_read->'problems'->0->>'problem' as problem, r.ad_read->'keywords_top' as keywords, r.interview_prep as prep,
                     bool_or(r.status = 'generating') over (partition by {KEY}) as working
              from runs r where r.account_id = %s and r.purged_at is null)
            select distinct on (g) id, status, created_at, title, ad_start, working, problem, keywords, prep
            from x order by g, (status = 'passed') desc, created_at desc""", (account_id,)).fetchall()
    rows.sort(key=lambda r: r["created_at"], reverse=True)
    return [{**r, "title": r["title"] or cvtext.ad_title(r["ad_start"])} for r in rows]


def older_than_30_days(c, account_id):
    """How many jobs have nothing newer than 30 days: what unticking the choice would delete at the next clean-up."""
    return c.execute(
        f"""select count(*) n from (
              select {KEY} g from runs r where r.account_id = %s and r.purged_at is null and r.status <> 'generating'
              group by g having max(r.created_at) < now() - interval '30 days') t""", (account_id,)).fetchone()["n"]


def register(app, h):
    def keep_flag(c, account_id):
        return c.execute("select keep_applications from accounts where id = %s", (account_id,)).fetchone()["keep_applications"]

    def page(request, c, u, saved="", confirm=0, status=200):
        rows = jobs(c, u["account_id"])
        return h.render(request, "applications.html", status=status, u=u, jobs=rows[:LIST_MAX], total=len(rows), more=len(rows) > LIST_MAX,
                        keep=keep_flag(c, u["account_id"]), choice=notices.keeps_choice(), saved=saved, confirm=confirm)

    @app.get("/applications", response_class=HTMLResponse)
    def applications(request: Request, saved: str = ""):
        with h.conn() as c:
            u = h.user(request, c)
            return page(request, c, u, saved=saved if saved in ("on", "off") else "")

    @app.post("/applications/keep")
    def applications_keep(request: Request, csrf: str = Form(""), keep: str = Form(""), confirm: str = Form("")):
        with h.conn() as c:
            u = h.user(request, c)
            h.check_post(request, u["email"], csrf)
            if not notices.keeps_choice():
                raise h.error(request, 404, "Not available yet", "Applications are kept for 30 days for now. Nothing was changed.")
            want = keep == "yes"
            if want == keep_flag(c, u["account_id"]):
                return RedirectResponse("/applications", 303)
            older = 0 if want else older_than_30_days(c, u["account_id"])
            if older and confirm != "yes":   # unticking deletes what is older than 30 days: say so first (Addendum 8)
                return page(request, c, u, confirm=older)
            c.execute("update accounts set keep_applications = %s where id = %s", (want, u["account_id"]))
        return RedirectResponse(f"/applications?saved={'on' if want else 'off'}", 303)
