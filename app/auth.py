"""Who is asking: the Cloudflare Access token, checked against the team's keys and the app's AUD tag.

Cloudflare Access sits in front of the app and adds `Cf-Access-Jwt-Assertion` to every request
it lets through. A request without a valid token never reached us through Access, so it's refused.
"""
import hashlib
import hmac

import jwt

HEADER = "Cf-Access-Jwt-Assertion"
DEV_COOKIE = "cvwrite_dev_token"  # dev only: lets a browser carry a token minted by app.devlogin


class NotSignedIn(Exception):
    pass


class Verifier:
    def __init__(self, settings):
        self.settings = settings
        url = settings.access_certs_url
        if url.startswith("file://"):
            # Dev and tests: keys from a local file (config allows this only outside prod).
            self.keys = _FileKeys(url)
        else:
            self.keys = jwt.PyJWKClient(url, cache_keys=True, lifespan=3600)

    def email(self, request):
        token = request.headers.get(HEADER)
        if not token and self.settings.env == "dev":
            token = request.cookies.get(DEV_COOKIE)
        if not token:
            raise NotSignedIn("no token")
        try:
            key = self.keys.get_signing_key_from_jwt(token).key
            claims = jwt.decode(
                token, key, algorithms=["RS256"],
                audience=self.settings.access_aud, issuer=self.settings.access_issuer,
                options={"require": ["exp", "iat", "aud", "iss", "email"]}, leeway=30,
            )
        except (jwt.PyJWTError, jwt.PyJWKClientError) as e:
            raise NotSignedIn(type(e).__name__) from None
        email = str(claims["email"]).strip().lower()
        if "@" not in email:
            raise NotSignedIn("bad email claim")
        return email


class _FileKeys:
    def __init__(self, url):
        from urllib.parse import urlparse
        from urllib.request import url2pathname
        with open(url2pathname(urlparse(url).path), encoding="utf-8") as f:
            self.keyset = jwt.PyJWKSet.from_json(f.read())

    def get_signing_key_from_jwt(self, token):
        kid = jwt.get_unverified_header(token).get("kid")
        for key in self.keyset.keys:
            if key.key_id == kid:
                return key
        raise jwt.PyJWKClientError("no matching key")


def csrf_token(settings, email):
    return hmac.new(settings.secret_key.encode(), b"csrf:" + email.encode(), hashlib.sha256).hexdigest()[:40]


def csrf_ok(settings, request, email, token):
    """A form POST must carry our token and come from our own origin."""
    origin = request.headers.get("origin") or ""
    if not origin:
        referer = request.headers.get("referer") or ""
        origin = referer[: len(settings.app_origin)] if referer.startswith(settings.app_origin + "/") else ""
    return origin == settings.app_origin and hmac.compare_digest(token or "", csrf_token(settings, email))


def hashed_id(email):
    """For logs: a stable id that isn't the email."""
    return hashlib.sha256(b"cvwrite3:" + email.encode()).hexdigest()[:16]
