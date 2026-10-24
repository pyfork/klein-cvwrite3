"""Shared test setup: a throwaway Postgres, one fresh database per test, a client, sessions made directly.

All emails here are made up.
"""
import atexit
import shutil
import tempfile
import unittest
import uuid
from pathlib import Path

import psycopg
from fastapi.testclient import TestClient

from app import config, db, mailer

ORIGIN = "https://cvwrite3.test"
OWNER = "owner@example.com"

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


class AppCase(unittest.TestCase):
    """Each test gets its own database, cloned from a migrated template."""

    def setUp(self):
        _server()
        self.dbname = "t_" + uuid.uuid4().hex[:10]
        with psycopg.connect(_server_uri(), autocommit=True) as c:
            c.execute(f"create database {self.dbname} template cvw3_template")
        self.data_dir = tempfile.mkdtemp(prefix="cvw3-data-")
        self.settings = config.Settings(
            env="dev", database_url=_with_db(self.dbname), owner_email=OWNER, secret_key="x" * 40,
            app_origin=ORIGIN,
            data_dir=self.data_dir, claude="fake",
            qr_path=str(Path(self.data_dir) / "no-qr.png"),  # never the owner's real QR on this machine
        )
        from app.main import create_app
        self.outbox = mailer.Outbox()
        self.app = create_app(self.settings, mail=self.outbox)
        self.sessions = {}
        self.client = TestClient(self.app, base_url=ORIGIN, follow_redirects=False)

    def tearDown(self):
        self.client.close()
        shutil.rmtree(self.data_dir, ignore_errors=True)
        with psycopg.connect(_server_uri(), autocommit=True) as c:
            c.execute(f"drop database {self.dbname} with (force)")

    def conn(self):
        return db.connect(self.settings.database_url)

    def as_user(self, email):
        """A signed-in session for this email, made directly (tests/test_signin.py covers the real flow)."""
        email = email.lower()
        if email not in self.sessions:
            from app import signin
            with self.conn() as c:
                self.sessions[email] = signin.start_session(c, self.settings, email)
        return {"Cookie": f"cvwrite3={self.sessions[email]}"}

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


MASTER = (Path(__file__).resolve().parent / "fixtures" / "master_cv.md")


class CVCase(AppCase):
    """An approved, consented user with a saved profile, and a fake Claude."""
    EMAIL = "nadia@example.com"

    def setUp(self):
        super().setUp()
        from app.fakeclaude import FakeClaude
        self.claude = FakeClaude()
        self.approve(self.EMAIL)
        self.agree(self.EMAIL)
        self.post("/profile", self.EMAIL, {"master_text": MASTER.read_text(), "master_name": "master.md",
                                          "name": "Nadia Hamzah", "email": "nadia@example.com", "phone": "+60 12-345 6789",
                                          "location": "Shah Alam", "links": "", "standing_edits": ""})

    def start(self, ad=None, email=None):
        r = self.post("/generate", email or self.EMAIL, {"ad": ad or AD})
        self.assertEqual(r.status_code, 303, r.text[:300])
        return int(r.headers["location"].rsplit("/", 1)[1])

    def drain(self):
        """Run every queued job now, in this thread."""
        from app import worker
        while True:
            with self.conn() as c:
                job = worker.claim(c)
            if not job:
                return
            worker.run_job(self.settings, self.claude, job)

    def run_row(self, run_id):
        with self.conn() as c:
            return c.execute("select * from runs where id = %s", (run_id,)).fetchone()

    def credits(self):
        with self.conn() as c:
            return c.execute("select coalesce(sum(delta), 0) n from credit_ledger").fetchone()["n"]


AD = """Operations Analyst (Last-Mile Delivery)
FreshRoute Sdn Bhd, Shah Alam, Selangor. Full time.

About us
FreshRoute delivers groceries to 40,000 homes across the Klang Valley every week. We're growing fast, and our on-time rate isn't keeping up.

The role
Right now we need someone who can find out why 1 in 5 deliveries miss their slot, and fix it.

What we're looking for
- Route optimisation for three hubs
- Strong SQL
- Stakeholder reporting for operations and finance
- Power BI or a similar tool
"""
