"""Dev only: sign in as any email at once, skipping the emailed code.

Mounted by create_app only when CVWRITE_ENV=dev. The real flow also works in dev: the code is printed
to the console instead of being mailed.
"""
from fastapi.responses import HTMLResponse, RedirectResponse

from . import auth, db, signin


def mount(app, settings):
    @app.get("/dev/login", response_class=HTMLResponse)
    def dev_login(email: str = ""):
        email = signin.clean_email(email)
        if not email:
            return HTMLResponse(
                '<form style="font:16px system-ui;margin:40px"><p>Dev sign-in. Any email.</p>'
                '<input name="email" type="email" required> <button>Sign in</button></form>')
        with db.connect(settings.database_url) as c:
            token = signin.start_session(c, settings, email)
        r = RedirectResponse("/", 303)
        auth.set_cookie(settings, r, token)
        return r
