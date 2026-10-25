"""The web app. Chunk 2: sign-in, the whitelist, request access, admin approval, the notice and consent.

Run (dev): see scripts/dev.py. Prod: uvicorn "app.main:create_app" --factory, behind nginx and Cloudflare. Sign-in: app.signin.
"""
import json
import logging
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import access, auth, config, credits, db, health, mailer, notices, orders, pause, routes_account, routes_cv, routes_ops, routes_pay, signin
from .markdown import section, to_html

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
APP_VERSION = "0.8.0"
log = logging.getLogger("cvwrite3")

# Pages that never ask for consent first: the notice itself, and the signed-out ones.
NO_CONSENT_NEEDED = ("/consent", "/privacy", "/request", "/terms", "/deleted", "/signin")


class Page(Exception):
    """Raised by a guard to answer with a redirect or an error page instead."""

    def __init__(self, response):
        self.response = response


def create_app(settings=None, mail=None):
    settings = settings or config.load()
    if settings.env == "prod" and notices.latest().status != "published":
        raise config.ConfigError(f"privacy notice v{notices.latest().version} is still a draft")
    mail = mail or (mailer.SMTPMailer(settings) if settings.env == "prod" else mailer.Outbox(echo=True))
    if not log.handlers:
        # journald stores one JSON line per request. Run uvicorn with --no-access-log: its own
        # log line carries the full URL.
        h = logging.StreamHandler()
        h.setFormatter(logging.Formatter("%(message)s"))
        log.addHandler(h)
        log.setLevel(logging.INFO)
        log.propagate = False
    templates = Jinja2Templates(directory=str(HERE / "templates"))
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.mount("/static", StaticFiles(directory=str(HERE / "static")), name="static")
    app.mount("/fonts", StaticFiles(directory=str(ROOT / "fonts")), name="fonts")
    app.state.settings = settings

    # ---- plumbing ------------------------------------------------------------
    @app.middleware("http")
    async def request_log(request, call_next):
        # One JSON line per request: never any CV, ad, contact or report text, and no email.
        request.state.id = uuid.uuid4().hex[:12]
        t0 = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as e:  # an unexpected error: record its class and where, then show the error page
            with conn() as c:
                health.record_error(c, e, route=request.url.path, request_id=request.state.id)
            log.info(json.dumps({"request_id": request.state.id, "http.route": request.url.path, "http.status_code": 500,
                                 "error.type": type(e).__name__, "app.version": APP_VERSION}))
            return templates.TemplateResponse(request, "error.html", {
                "app_version": APP_VERSION, "title": "Something went wrong", "signed_out": True, "report_link": True,
                "message": f"We've logged it (ref {request.state.id}). Please try again in a minute."}, status_code=500)
        log.info(json.dumps({
            "request_id": request.state.id, "http.route": request.url.path, "http.status_code": response.status_code,
            "duration_ms": round((time.perf_counter() - t0) * 1000, 1),
            "user": getattr(request.state, "user_hash", None), "app.version": APP_VERSION,
        }))
        return response

    @app.exception_handler(Page)
    async def page_exc(request, exc):
        return exc.response

    def conn():
        return db.connect(settings.database_url)

    def render(request, name, status=200, **ctx):
        if ctx.get("u") and "banner" not in ctx:
            with conn() as c:
                ctx["banner"] = pause.banner(pause.current_with_age(c)) or (
                    "Generating is slower than usual right now." if health.degraded_now(c) else None)
        return templates.TemplateResponse(request, name, {"app_version": APP_VERSION, **ctx}, status_code=status)

    def error(request, status, title, message):
        return Page(render(request, "error.html", status=status, title=title, message=message, signed_out=True))

    def who(request):
        try:
            with conn() as c:
                email = auth.email(c, settings, request)
        except auth.NotSignedIn:
            raise Page(RedirectResponse("/signin", 303)) from None
        request.state.user_hash = auth.hashed_id(email)
        return email

    def user(request, c, consent=True):
        """The signed-in, approved user, who has agreed to the current notice (unless consent=False)."""
        email = who(request)
        row = access.allowed(c, email)
        if not row:
            raise Page(RedirectResponse("/request", 303))
        if consent and notices.needs_consent((notices.latest_consent(c, email) or {}).get("notice_version")):
            raise Page(RedirectResponse("/consent", 303))
        cs = credits.summary(c, row["account_id"])
        return {"email": email, "account_id": row["account_id"], "balance": cs.balance, "expires": cs.earliest_expiry,
                "csrf": auth.csrf_token(settings, email), "is_owner": email == settings.owner_email}

    def owner(request):
        email = who(request)
        if email != settings.owner_email:
            raise error(request, 403, "Owner only", "This page is for the owner of cvwrite3.")
        return {"email": email, "csrf": auth.csrf_token(settings, email), "is_owner": True}

    def check_post(request, email, token):
        if not auth.csrf_ok(settings, request, email, token):
            raise error(request, 403, "That didn't work", "The form expired or came from somewhere else. Go back, reload the page and try again.")

    # ---- sign in: a 6-digit code by email (chunk 7j) ---------------------------------
    def signed_out_post(request):
        if not auth.origin_ok(settings, request):
            raise error(request, 403, "That didn't work", "The form came from somewhere else. Go back, reload the page and try again.")

    @app.get("/signin", response_class=HTMLResponse)
    def signin_page(request: Request):
        with conn() as c:
            if signin.session_email(c, settings, request.cookies.get(auth.cookie_name(settings))):
                return RedirectResponse("/", 303)
        return render(request, "signin.html", signed_out=True)

    @app.post("/signin")
    def signin_post(request: Request, email: str = Form("")):
        signed_out_post(request)
        clean = signin.clean_email(email)
        if not clean:
            return render(request, "signin.html", status=400, signed_out=True, problem="bad", email=email[:254])
        # Only Cloudflare's edge can reach nginx (the 444 gate), so its client-IP header can be trusted.
        ip = request.headers.get("cf-connecting-ip") or (request.client.host if request.client else "")
        try:
            with conn() as c:
                signin.send_code(c, settings, mail, clean, ip)
        except signin.TooMany:
            return render(request, "signin.html", status=429, signed_out=True, problem="many", email=clean)
        except mailer.MailError as e:
            with conn() as c:
                health.record_error(c, e, route=request.url.path, request_id=request.state.id)
            return render(request, "signin.html", status=502, signed_out=True, problem="mail", email=clean)
        r = RedirectResponse("/signin/code", 303)
        auth.set_pending(settings, r, clean)
        return r

    @app.get("/signin/code", response_class=HTMLResponse)
    def code_page(request: Request):
        email = auth.pending_email(settings, request)
        if not email:
            return RedirectResponse("/signin", 303)
        return render(request, "signin_code.html", signed_out=True, email=email)

    @app.post("/signin/code")
    def code_post(request: Request, code: str = Form("")):
        signed_out_post(request)
        email = auth.pending_email(settings, request)
        if not email:
            return RedirectResponse("/signin", 303)
        with conn() as c:
            token = signin.start_session(c, settings, email) if signin.check_code(c, settings, email, code) else None
        if not token:
            return render(request, "signin_code.html", status=400, signed_out=True, email=email, wrong=True)
        r = RedirectResponse("/", 303)
        auth.set_cookie(settings, r, token)
        auth.clear_pending(settings, r)
        return r

    @app.post("/signout")
    def signout(request: Request, csrf: str = Form("")):
        check_post(request, who(request), csrf)
        with conn() as c:
            signin.end_session(c, settings, request.cookies.get(auth.cookie_name(settings)))
        r = RedirectResponse("/signin", 303)
        auth.clear_cookie(settings, r)
        return r

    # ---- user pages ------------------------------------------------------------
    @app.get("/request", response_class=HTMLResponse)
    def request_page(request: Request):
        email = who(request)
        with conn() as c:
            if access.allowed(c, email):
                return RedirectResponse("/", 303)
            pending = access.pending_request(c, email) is not None
        return render(request, "request.html", email=email, pending=pending, csrf=auth.csrf_token(settings, email), signed_out=True)

    @app.post("/request")
    def request_post(request: Request, csrf: str = Form(""), note: str = Form("")):
        email = who(request)
        check_post(request, email, csrf)
        with conn() as c:
            result = access.request_access(c, settings, email, note)
        return RedirectResponse("/" if result in ("allowed", "approved") else "/request", 303)

    @app.get("/consent", response_class=HTMLResponse)
    def consent_page(request: Request, lang: str = "en"):
        with conn() as c:
            u = user(request, c, consent=False)
            prev = notices.latest_consent(c, u["email"])
        need = notices.needs_consent(prev and prev["notice_version"])
        if not need:
            return RedirectResponse("/", 303)
        return consent_form(request, u, need, prev, lang)

    def consent_form(request, u, need, prev, lang, status=200, missing=False):
        v = notices.latest()
        lang = lang if lang in notices.langs(v.version) else "en"
        summary = to_html(section(notices.text(v.version, lang), "In short"))
        changed = notices.changes_since(prev["notice_version"]) if prev else []
        return render(request, "consent.html", status=status, u=u, v=v, lang=lang, summary=summary,
                      need=need, changed=changed, missing=missing)

    @app.post("/consent")
    def consent_post(request: Request, csrf: str = Form(""), agree: str = Form(""), sensitive: str = Form(""),
                     lang: str = Form("en"), version: str = Form("")):
        with conn() as c:
            u = user(request, c, consent=False)
            check_post(request, u["email"], csrf)
            prev = notices.latest_consent(c, u["email"])
            need = notices.needs_consent(prev and prev["notice_version"])
            if not need:
                return RedirectResponse("/", 303)
            if agree != "yes" or version != notices.latest().version:
                return consent_form(request, u, need, prev, lang, status=400, missing=True)
            lang = lang if lang in notices.langs(version) else "en"
            notices.record(c, u["email"], lang, sensitive == "yes")
        return RedirectResponse("/", 303)

    # ---- the notice (no sign-in needed) ----------------------------------------
    def notice_page(request, v, lang):
        if v is None:
            raise error(request, 404, "Not found", "There's no privacy notice with that number.")
        lang = lang if lang in notices.langs(v.version) else "en"
        return render(request, "notice.html", v=v, lang=lang, latest=notices.latest(),
                      body=to_html(notices.text(v.version, lang)), signed_out=True)

    @app.get("/privacy", response_class=HTMLResponse)
    def privacy(request: Request, lang: str = "en"):
        return notice_page(request, notices.latest(), lang)

    @app.get("/privacy/changes", response_class=HTMLResponse)
    def privacy_changes(request: Request):
        return render(request, "changes.html", versions=list(reversed(notices.versions())), signed_out=True)

    @app.get("/privacy/v{version}", response_class=HTMLResponse)
    def privacy_version(request: Request, version: str, lang: str = "en"):
        return notice_page(request, notices.get(version), lang)

    # ---- admin -----------------------------------------------------------------
    @app.get("/admin", response_class=HTMLResponse)
    def admin(request: Request):
        o = owner(request)
        with conn() as c:
            ctx = {"requests": access.pending_requests(c), "wave2": access.wave2_on(c),
                   "users": access.user_count(c), "cap": settings.wave2_cap, "orders": orders.for_admin(c), **admin_health(c),
                   "reports": admin_reports(c), "panel": health.panel(c), "funnel": health.funnel(c),
                   "categories": routes_ops.CATEGORIES, "reasons": routes_ops.REASONS}
        return render(request, "admin.html", o=o, **ctx)

    @app.post("/admin/requests/{request_id}/{decision}")
    def admin_decide(request: Request, request_id: int, decision: str, csrf: str = Form("")):
        o = owner(request)
        check_post(request, o["email"], csrf)
        if decision not in ("approve", "decline"):
            raise error(request, 404, "Not found", "Unknown action.")
        with conn() as c:
            access.decide(c, request_id, decision == "approve")
        return RedirectResponse("/admin", 303)

    @app.post("/admin/wave2")
    def admin_wave2(request: Request, csrf: str = Form(""), on: str = Form("")):
        o = owner(request)
        check_post(request, o["email"], csrf)
        with conn() as c:
            access.set_wave2(c, on == "yes")
        return RedirectResponse("/admin", 303)

    from types import SimpleNamespace
    helpers = SimpleNamespace(conn=conn, render=render, user=user, owner=owner, check_post=check_post, error=error, settings=settings)
    admin_health = routes_cv.register(app, helpers)
    routes_pay.register(app, helpers)
    admin_reports = routes_ops.register(app, helpers, APP_VERSION)
    routes_account.register(app, helpers)

    if settings.env == "dev":
        from . import devlogin
        devlogin.mount(app, settings)

    return app
