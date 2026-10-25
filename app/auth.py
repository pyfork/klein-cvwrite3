"""Who is asking: the session cookie set at sign-in (app.signin), and CSRF checks for forms.

The cookie holds a random token; the database holds only its HMAC. In prod the cookie is `__Host-` prefixed,
Secure, HttpOnly and SameSite=Lax, so only this origin, over https, ever sends it.
"""
import base64
import hashlib
import hmac
import time

from . import signin


class NotSignedIn(Exception):
    pass


def cookie_name(settings):
    return "__Host-cvwrite3" if settings.env == "prod" else "cvwrite3"


def set_cookie(settings, response, token):
    response.set_cookie(cookie_name(settings), token, max_age=signin.SESSION_DAYS * 86400, path="/",
                        secure=settings.env == "prod", httponly=True, samesite="lax")


def clear_cookie(settings, response):
    response.delete_cookie(cookie_name(settings), path="/", secure=settings.env == "prod", httponly=True, samesite="lax")


def _pending_name(settings):
    return "__Host-cvwrite3_pending" if settings.env == "prod" else "cvwrite3_pending"


def set_pending(settings, response, email):
    """Between asking for a code and typing it: which email, signed, for as long as the code lasts."""
    exp = int(time.time()) + signin.CODE_TTL_MIN * 60
    body = f"{exp}.{base64.urlsafe_b64encode(email.encode()).decode().rstrip('=')}"
    sig = hmac.new(settings.secret_key.encode(), b"pending:" + body.encode(), hashlib.sha256).hexdigest()[:32]
    response.set_cookie(_pending_name(settings), f"{body}.{sig}", max_age=signin.CODE_TTL_MIN * 60, path="/",
                        secure=settings.env == "prod", httponly=True, samesite="lax")


def pending_email(settings, request):
    try:
        exp, b64, sig = (request.cookies.get(_pending_name(settings)) or "").split(".")
        good = hmac.new(settings.secret_key.encode(), f"pending:{exp}.{b64}".encode(), hashlib.sha256).hexdigest()[:32]
        if not hmac.compare_digest(sig, good) or int(exp) < time.time():
            return None
        return base64.urlsafe_b64decode(b64 + "=" * (-len(b64) % 4)).decode()
    except ValueError:
        return None


def clear_pending(settings, response):
    response.delete_cookie(_pending_name(settings), path="/", secure=settings.env == "prod", httponly=True, samesite="lax")


def email(conn, settings, request):
    found = signin.session_email(conn, settings, request.cookies.get(cookie_name(settings)))
    if not found:
        raise NotSignedIn()
    return found


def csrf_token(settings, email):
    return hmac.new(settings.secret_key.encode(), b"csrf:" + email.encode(), hashlib.sha256).hexdigest()[:40]


def origin_ok(settings, request):
    """The form was posted from our own pages (the only check a signed-out form can have)."""
    origin = request.headers.get("origin") or ""
    if not origin:
        referer = request.headers.get("referer") or ""
        origin = referer[: len(settings.app_origin)] if referer.startswith(settings.app_origin + "/") else ""
    return origin == settings.app_origin


def csrf_ok(settings, request, email, token):
    """A form POST must carry our token and come from our own origin."""
    return origin_ok(settings, request) and hmac.compare_digest(token or "", csrf_token(settings, email))


def hashed_id(email):
    """For logs: a stable id that isn't the email."""
    return hashlib.sha256(b"cvwrite3:" + email.encode()).hexdigest()[:16]
