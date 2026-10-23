"""Chunk 3 pages: profile, generate, the run (progress and result), downloads, edit and re-render."""
import json

from fastapi import File, Form, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, RedirectResponse

from render import contact as contact_mod

from . import cvtext, ic, pause, pipeline, profile, rendering, upload

STEP_NAMES = {"call_a": "Reading the ad", "call_b": "Writing your CV", "retry": "Fixing the draft",
              "render": "Making the PDF", "check": "Checking: 2 pages, A4, keywords",
              "reformat": "Fixing the layout", "word_check": "Checking every word was kept"}
AD_MIN, AD_MAX, EDIT_MAX = 200, 30000, 30000


def register(app, h):
    """`h` carries the shared helpers from main.create_app: conn, render, user, check_post, error, settings."""

    def own_run(request, c, u, run_id):
        run = c.execute("select * from runs where id = %s and account_id = %s", (run_id, u["account_id"])).fetchone()
        if not run:
            raise h.error(request, 404, "Not found", "There's no CV with that number in your account.")
        return run

    def available(c, u):
        """Credits not already promised to a CV that's still generating."""
        n = c.execute("select count(*) n from runs where account_id = %s and status = 'generating'", (u["account_id"],)).fetchone()["n"]
        return u["balance"] - n

    # ---- profile ---------------------------------------------------------------
    def profile_page(request, c, u, status=200, preview=None, filename=None, error=None, saved=False, form=None):
        p = profile.get(c, u["account_id"])
        text = p["master_text"] if preview is None else preview
        fields = form or {k: p[k] for k in (*profile.CONTACT, "standing_edits")}
        return h.render(request, "profile.html", status=status, u=u, text=text, filename=filename or p["master_name"],
                        fields=fields, ic_hits=ic.find(text), error=error, saved=saved, unsaved=preview is not None,
                        words=len(cvtext.words(text)))

    @app.get("/profile", response_class=HTMLResponse)
    def profile_get(request: Request, saved: int = 0):
        with h.conn() as c:
            u = h.user(request, c)
            return profile_page(request, c, u, saved=bool(saved))

    @app.post("/profile/upload", response_class=HTMLResponse)
    async def profile_upload(request: Request, csrf: str = Form(""), file: UploadFile = File(None)):
        data = await file.read(upload.MAX_BYTES + 1) if file else b""
        with h.conn() as c:
            u = h.user(request, c)
            h.check_post(request, u["email"], csrf)
            try:
                text = upload.read(file.filename if file else "", data)
            except upload.UploadError as e:
                return profile_page(request, c, u, status=400, error=str(e))
            return profile_page(request, c, u, preview=text, filename=file.filename)

    @app.post("/profile")
    def profile_post(request: Request, csrf: str = Form(""), master_text: str = Form(""), master_name: str = Form(""),
                     name: str = Form(""), location: str = Form(""), phone: str = Form(""), email: str = Form(""),
                     links: str = Form(""), standing_edits: str = Form("")):
        form = {"name": name, "location": location, "phone": phone, "email": email, "links": links, "standing_edits": standing_edits}
        text = master_text.replace("\r\n", "\n").strip()
        with h.conn() as c:
            u = h.user(request, c)
            h.check_post(request, u["email"], csrf)
            if len(text) > upload.MAX_CHARS:
                return profile_page(request, c, u, status=400, preview=text, form=form, error="That CV is very long. Keep it under about 8,000 words.")
            if ic.find(text) or ic.find(standing_edits):
                return profile_page(request, c, u, status=400, preview=text, form=form, filename=master_name,
                                    error="Remove the IC number before saving. Nothing has been sent to the AI.")
            profile.save(c, u["account_id"], text, master_name, form)
        return RedirectResponse("/profile?saved=1", 303)

    # ---- generate ----------------------------------------------------------------
    def generate_page(request, c, u, status=200, ad="", error=None):
        p = profile.get(c, u["account_id"])
        runs = c.execute("select r.id, r.status, r.created_at, r.ad_read->>'job_title' as title from runs r "
                         "where account_id = %s order by created_at desc limit 10", (u["account_id"],)).fetchall()
        blocked = None
        if pause.current(c):
            blocked = "Generating is paused, so you can't start a new CV right now. Nothing has been charged."
        elif available(c, u) < 1:
            blocked = "You're out of credits. Buying credits comes soon. RM10 for 5, or RM30 for 20."
        elif profile.ready(p):
            blocked = profile.ready(p)
        return h.render(request, "generate.html", status=status, u=u, ad=ad, error=error, blocked=blocked, runs=runs)

    @app.get("/")
    def home(request: Request):
        with h.conn() as c:
            h.user(request, c)
        return RedirectResponse("/generate", 303)

    @app.get("/generate", response_class=HTMLResponse)
    def generate_get(request: Request):
        with h.conn() as c:
            u = h.user(request, c)
            return generate_page(request, c, u)

    @app.post("/generate")
    def generate_post(request: Request, csrf: str = Form(""), ad: str = Form("")):
        ad = ad.replace("\r\n", "\n").strip()
        with h.conn() as c:
            u = h.user(request, c)
            h.check_post(request, u["email"], csrf)
            if len(ad) < AD_MIN:
                return generate_page(request, c, u, 400, ad, "Paste the whole ad, from the job title to the closing date. This looks too short.")
            if len(ad) > AD_MAX:
                return generate_page(request, c, u, 400, ad, "That's longer than any job ad we've seen. Paste just the ad.")
            with c.transaction():
                c.execute("select pg_advisory_xact_lock(%s)", (u["account_id"],))  # one balance check at a time per user
                if pause.current(c) or available(c, u) < 1 or profile.ready(profile.get(c, u["account_id"])):
                    return generate_page(request, c, u, 409, ad)
                run_id = c.execute("insert into runs (account_id, ad_text) values (%s, %s) returning id", (u["account_id"], ad)).fetchone()["id"]
                c.execute("insert into jobs (run_id, kind) values (%s, 'generate')", (run_id,))
        return RedirectResponse(f"/runs/{run_id}", 303)

    # ---- the run: progress, then the result ------------------------------------------
    @app.get("/runs/{run_id}", response_class=HTMLResponse)
    def run_page(request: Request, run_id: int):
        with h.conn() as c:
            u = h.user(request, c)
            run = own_run(request, c, u, run_id)
            job = c.execute("select * from jobs where run_id = %s and kind = 'generate' order by id desc limit 1", (run_id,)).fetchone()
            steps = c.execute("select step, outcome, duration_ms from run_steps where run_id = %s and job_id = %s and step = any(%s) order by id",
                              (run_id, job["id"], list(STEP_NAMES))).fetchall() if job else []
            read = run["ad_read"] or {}
            places = cvtext.keyword_places(run["draft_md"] or "", read.get("keywords_top", []) + read.get("keywords_secondary", [])[:5]) if run["status"] == "passed" else {}
            return h.render(request, "run.html", u=u, run=run, job=job, read=read, places=places,
                            steps=[{"name": STEP_NAMES[s["step"]], **s} for s in steps], gaps=run["gaps"] or [],
                            refresh=run["status"] == "generating" and job and job["status"] in ("queued", "running"))

    def merged(c, run, u):
        return contact_mod.merge(run["draft_md"], profile.contact(profile.get(c, u["account_id"])))

    def filename(run, ext):
        title = (run["ad_read"] or {}).get("job_title", "") or "cv"
        slug = "".join(ch if ch.isalnum() else "-" for ch in title.lower()).strip("-")[:40] or "cv"
        return f"cv-{slug}.{ext}"

    @app.get("/runs/{run_id}/cv.pdf")
    def run_pdf(request: Request, run_id: int):
        with h.conn() as c:
            u = h.user(request, c)
            run = own_run(request, c, u, run_id)
        if run["status"] != "passed":
            raise h.error(request, 404, "Not ready", "This CV hasn't passed its check, so there's nothing to download.")
        return FileResponse(rendering.pdf_path(h.settings.data_dir, run_id, run["pdf_rev"]), media_type="application/pdf", filename=filename(run, "pdf"))

    @app.get("/runs/{run_id}/cv.md")
    def run_md(request: Request, run_id: int):
        with h.conn() as c:
            u = h.user(request, c)
            run = own_run(request, c, u, run_id)
            if run["status"] != "passed":
                raise h.error(request, 404, "Not ready", "This CV hasn't passed its check, so there's nothing to download.")
            body = merged(c, run, u)
        return PlainTextResponse(body, media_type="text/markdown; charset=utf-8",
                                 headers={"Content-Disposition": f'attachment; filename="{filename(run, "md")}"'})

    @app.get("/runs/{run_id}/cv.txt")
    def run_txt(request: Request, run_id: int):
        with h.conn() as c:
            u = h.user(request, c)
            run = own_run(request, c, u, run_id)
            if run["status"] != "passed":
                raise h.error(request, 404, "Not ready", "This CV hasn't passed its check, so there's nothing to download.")
            p = profile.get(c, u["account_id"])
        text = cvtext.to_plain(run["draft_md"]).replace("[NAME]", p["name"]).replace("[CONTACT]", contact_mod.contact_line(profile.contact(p)))
        text = text.replace("(Change your name and contact details in Profile.)\n", "")
        return PlainTextResponse(text, headers={"Content-Disposition": f'attachment; filename="{filename(run, "txt")}"'})

    # ---- edit and re-render ----------------------------------------------------------------
    def edit_page(request, c, u, run, status=200, text=None, error=None, job_id=None):
        job = None
        if job_id:
            job = c.execute("select * from jobs where id = %s and run_id = %s and kind = 'rerender'", (job_id, run["id"])).fetchone()
        busy = c.execute("select 1 from jobs where run_id = %s and kind = 'rerender' and status in ('queued', 'running')", (run["id"],)).fetchone()
        return h.render(request, "edit.html", status=status, u=u, run=run, text=text if text is not None else cvtext.to_plain(run["draft_md"]),
                        left=pipeline.MAX_RERENDERS - run["rerenders_used"], error=error, job=job, busy=bool(busy),
                        paused=bool(pause.current(c)), refresh=bool(busy))

    @app.get("/runs/{run_id}/edit", response_class=HTMLResponse)
    def edit_get(request: Request, run_id: int, job: int = 0):
        with h.conn() as c:
            u = h.user(request, c)
            run = own_run(request, c, u, run_id)
            if run["status"] != "passed":
                return RedirectResponse(f"/runs/{run_id}", 303)
            return edit_page(request, c, u, run, job_id=job)

    @app.post("/runs/{run_id}/edit")
    def edit_post(request: Request, run_id: int, csrf: str = Form(""), text: str = Form("")):
        text = text.replace("\r\n", "\n")
        with h.conn() as c:
            u = h.user(request, c)
            h.check_post(request, u["email"], csrf)
            run = own_run(request, c, u, run_id)
            if run["status"] != "passed":
                return RedirectResponse(f"/runs/{run_id}", 303)
            if len(text) > EDIT_MAX:
                return edit_page(request, c, u, run, 400, text, "That's much longer than a 2-page CV. Trim it and try again.")
            if ic.find(text):
                return edit_page(request, c, u, run, 400, text, "This looks like an IC number. Please remove it, then re-render. Nothing has been sent.")
            if pause.current(c):
                return edit_page(request, c, u, run, 409, text, "Re-rendering is paused. Your text is kept, and this didn't use a re-render.")
            if run["rerenders_used"] >= pipeline.MAX_RERENDERS:
                return edit_page(request, c, u, run, 409, text, "You've used the 3 free re-renders for this CV. Start a new CV for 1 credit.")
            with c.transaction():
                if c.execute("select 1 from jobs where run_id = %s and kind = 'rerender' and status in ('queued', 'running') for update", (run_id,)).fetchone():
                    return edit_page(request, c, u, run, 409, text, "A re-render is already running for this CV. Wait for it to finish.")
                job_id = c.execute("insert into jobs (run_id, kind, input_text) values (%s, 'rerender', %s) returning id", (run_id, text)).fetchone()["id"]
        return RedirectResponse(f"/runs/{run_id}/edit?job={job_id}", 303)

    # ---- admin: the pause ------------------------------------------------------------------
    @app.post("/admin/pause")
    def admin_pause(request: Request, csrf: str = Form("")):
        o = h.owner(request)
        h.check_post(request, o["email"], csrf)
        with h.conn() as c:
            pause.pause(c, "paused by the owner", "owner")
        return RedirectResponse("/admin", 303)

    @app.post("/admin/resume")
    def admin_resume(request: Request, csrf: str = Form("")):
        o = h.owner(request)
        h.check_post(request, o["email"], csrf)
        with h.conn() as c:
            pause.resume(c)
        return RedirectResponse("/admin", 303)

    @app.post("/admin/test-render")
    def admin_test(request: Request, csrf: str = Form("")):
        o = h.owner(request)
        h.check_post(request, o["email"], csrf)
        with h.conn() as c:
            c.execute("insert into jobs (kind) values ('test_render')")
        return RedirectResponse("/admin", 303)

    def admin_health(c):
        p = pause.current_with_age(c)
        test = c.execute("select * from jobs where kind = 'test_render' order by id desc limit 1").fetchone()
        errors = c.execute("select s.error_class, s.run_id, s.step from run_steps s where s.outcome <> 'ok' "
                           "order by s.id desc limit 10").fetchall()
        held = c.execute("select count(*) n, min(held_at) oldest from jobs where status = 'held'").fetchone()
        return {"pause_row": p, "test": test, "errors": errors, "held": held}

    return admin_health
