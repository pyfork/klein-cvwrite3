"""Dev only: sign in as any email without Cloudflare, using a local key that only the dev app trusts.

Mounted by create_app only when CVWRITE_ENV=dev, and config refuses a non-https key URL in prod,
so a token minted here can never be accepted by the real app.
"""
import json
import time

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.responses import HTMLResponse, RedirectResponse

from .auth import DEV_COOKIE

KID = "cvwrite3-dev"


def make_keys(key_path, jwks_path):
    """Writes a private key (0600) and the matching JWKS file the dev verifier reads."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    key_path.chmod(0o600)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    jwk.update(kid=KID, alg="RS256", use="sig")
    jwks_path.write_text(json.dumps({"keys": [jwk]}))


def mint(private_pem, settings, email, ttl=3600):
    now = int(time.time())
    claims = {"email": email, "aud": [settings.access_aud], "iss": settings.access_issuer, "iat": now, "exp": now + ttl, "sub": email}
    return jwt.encode(claims, private_pem, algorithm="RS256", headers={"kid": KID})


def mount(app, settings):
    import os
    key_file = os.environ.get("CVWRITE_DEV_KEY_FILE", "")

    @app.get("/dev/login", response_class=HTMLResponse)
    def dev_login(email: str = ""):
        if not email:
            return HTMLResponse(
                '<form style="font:16px system-ui;margin:40px"><p>Dev sign-in. Any email.</p>'
                '<input name="email" type="email" required> <button>Sign in</button></form>')
        token = mint(open(key_file, "rb").read(), settings, email.strip().lower())
        r = RedirectResponse("/", 303)
        r.set_cookie(DEV_COOKIE, token, httponly=True, samesite="lax")
        return r
