"""Shared test setup: a throwaway Postgres, one fresh database per test, a test signing key, a client.

All emails here are made up.
"""
import atexit
import json
import shutil
import tempfile
import time
import unittest
import uuid
from pathlib import Path

import jwt
import psycopg
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app import config, db

ORIGIN = "https://cvwrite3.test"
OWNER = "owner@example.com"
TEAM = "cvw3-test.cloudflareaccess.com"
AUD = "test-aud-0123456789"

_state = {}


def _server():
    if "uri" not in _state:
        import pgserver
        d = tempfile.mkdtemp(prefix="cvw3-pg-")
        srv = pgserver.get_server(d, cleanup_mode="stop")
        _state.update(srv=srv, dir=d, uri=srv.get_uri())
        with psycopg.connect(_state["uri"], autocommit=True) as c:
            c.execute("create database cvw3_template")
        with db.connect(_with_db("cvw3_template")) as c:
            db.migrate(c)
        atexit.register(lambda: (srv.cleanup(), shutil.rmtree(d, ignore_errors=True)))
    return _state["uri"]


def _with_db(name):
    base, _, query = _server_uri().partition("?")
    head = base.rsplit("/", 1)[0]
    return f"{head}/{name}" + (f"?{query}" if query else "")


def _server_uri():
    return _state["uri"]


def _keys():
    if "key" not in _state:
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
        jwk.update(kid="t1", alg="RS256", use="sig")
        d = Path(tempfile.mkdtemp(prefix="cvw3-keys-"))
        (d / "certs.json").write_text(json.dumps({"keys": [jwk]}))
        _state.update(key=key, certs=(d / "certs.json").as_uri())
        other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        _state["other_key"] = other
    return _state


def token(email, aud=AUD, iss="https://" + TEAM, exp_in=600, key=None, kid="t1"):
    now = int(time.time())
    k = key or _keys()["key"]
    return jwt.encode({"email": email, "aud": [aud], "iss": iss, "iat": now, "exp": now + exp_in}, k, algorithm="RS256", headers={"kid": kid})


class AppCase(unittest.TestCase):
    """Each test gets its own database, cloned from a migrated template."""

    def setUp(self):
        _server()
        self.dbname = "t_" + uuid.uuid4().hex[:10]
        with psycopg.connect(_server_uri(), autocommit=True) as c:
            c.execute(f"create database {self.dbname} template cvw3_template")
        self.settings = config.Settings(
            env="dev", database_url=_with_db(self.dbname), owner_email=OWNER, secret_key="x" * 40,
            access_team=TEAM, access_aud=AUD, access_certs_url=_keys()["certs"], app_origin=ORIGIN,
        )
        from app.main import create_app
        self.app = create_app(self.settings)
        self.client = TestClient(self.app, base_url=ORIGIN, follow_redirects=False)

    def tearDown(self):
        self.client.close()
        with psycopg.connect(_server_uri(), autocommit=True) as c:
            c.execute(f"drop database {self.dbname} with (force)")

    def conn(self):
        return db.connect(self.settings.database_url)

    def as_user(self, email):
        return {"Cf-Access-Jwt-Assertion": token(email)}

    def get(self, path, email=None, **kw):
        return self.client.get(path, headers=self.as_user(email) if email else {}, **kw)

    def post(self, path, email, data=None, origin=ORIGIN, csrf=True):
        from app import auth
        data = dict(data or {})
        if csrf:
            data.setdefault("csrf", auth.csrf_token(self.settings, email.lower()))
        headers = self.as_user(email)
        if origin:
            headers["Origin"] = origin
        return self.client.post(path, data=data, headers=headers)

    def approve(self, email, via="owner"):
        """Request access and have the owner approve it."""
        self.post("/request", email, {"note": ""})
        with self.conn() as c:
            rid = c.execute("select id from access_requests where email = %s and status = 'pending'", (email,)).fetchone()["id"]
        self.post(f"/admin/requests/{rid}/approve", OWNER)

    def agree(self, email, sensitive=False):
        from app import notices
        data = {"agree": "yes", "version": notices.latest().version, "lang": "en"}
        if sensitive:
            data["sensitive"] = "yes"
        return self.post("/consent", email, data)
