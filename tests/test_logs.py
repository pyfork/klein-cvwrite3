"""Senior S4: no CV, ad, contact or report text ever reaches a log line or stdout/stderr.

A marker goes into every field a user types (the ad, the master CV, contact, standing edits, the edit box,
a problem report, the access-request note, the sign-in email) and into the message of an exception raised
mid-run. Every log record from every logger, at DEBUG, plus anything printed, must be free of it.
"""
import contextlib
import io
import logging
import unittest

from app import cvtext, pipeline, worker
from tests.support import AD, MASTER, CVCase, OWNER
from tests.render_env import needs_render

MARK = "zqx7731mark"


class Capture(logging.Handler):
    def __init__(self):
        super().__init__(logging.DEBUG)
        self.setFormatter(logging.Formatter("%(name)s %(levelname)s %(message)s"))
        self.lines = []

    def emit(self, record):
        self.lines.append(self.format(record))  # includes any traceback and exception message


class NoContentInLogs(CVCase):
    EMAIL = f"{MARK}@example.com"

    def setUp(self):
        self.cap = Capture()
        self.out, self.err = io.StringIO(), io.StringIO()
        self._streams = contextlib.ExitStack()
        self._streams.enter_context(contextlib.redirect_stdout(self.out))
        self._streams.enter_context(contextlib.redirect_stderr(self.err))
        self._levels = {}
        self._watch(logging.getLogger())
        super().setUp()
        # loggers that don't propagate (the app's request log) get the handler directly
        for name in list(logging.root.manager.loggerDict):
            lg = logging.getLogger(name)
            if not lg.propagate:
                self._watch(lg)
        self.post("/profile", self.EMAIL, {
            "master_text": MASTER.read_text() + f"\nVolunteer: {MARK} food bank, weekly routes.\n", "master_name": "master.md",
            "name": f"Nadia {MARK}", "email": f"{MARK}@example.net", "phone": "+60 12-345 6789",
            "location": f"Shah Alam {MARK}", "links": f"https://example.com/{MARK}", "standing_edits": f"Never mention {MARK}."})

    def _watch(self, lg):
        self._levels[lg] = lg.level
        lg.setLevel(logging.DEBUG)
        lg.addHandler(self.cap)

    def tearDown(self):
        super().tearDown()
        for lg, level in self._levels.items():
            lg.removeHandler(self.cap)
            lg.setLevel(level)
        self._streams.close()

    def approve(self, email, via="owner"):
        self.post("/request", email, {"note": f"please, {MARK}"})
        with self.conn() as c:
            rid = c.execute("select id from access_requests where email = %s and status = 'pending'", (email,)).fetchone()["id"]
        self.post(f"/admin/requests/{rid}/approve", OWNER)

    def assertClean(self):
        text = "\n".join(self.cap.lines) + self.out.getvalue() + self.err.getvalue()
        self.assertNotIn(MARK, text.lower())
        self.assertNotIn("nadia", text.lower())

    @needs_render
    def test_a_whole_run(self):
        run_id = self.start(AD + f"\nNice to have: {MARK} certification.\n")
        self.drain()
        self.assertEqual(self.run_row(run_id)["status"], "passed")
        for path in (f"/runs/{run_id}", f"/runs/{run_id}/cv.md", f"/runs/{run_id}/edit", "/account", "/account/download"):
            self.assertEqual(self.get(path, self.EMAIL).status_code, 200, path)
        box = cvtext.to_plain(self.run_row(run_id)["draft_md"])
        self.post(f"/runs/{run_id}/edit", self.EMAIL, {"text": box + f"\n- Ran the {MARK} pilot.\n"})
        self.drain()
        self.post(f"/runs/{run_id}/feedback", self.EMAIL, {"reason": "wording"})
        self.post("/report", self.EMAIL, {"category": "privacy", "body": f"Remove {MARK} please.", "page": "/generate"})
        self.get("/admin", OWNER)
        self.assertTrue(any('"http.route"' in l for l in self.cap.lines))  # the request log was captured
        self.assertClean()

    def test_a_crash_in_the_worker(self):
        def boom(*a, **k):
            raise ValueError(f"cannot parse line: Nadia {MARK}")
        run_id = self.start(AD)
        orig, pipeline.generate = pipeline.generate, boom
        try:
            with self.conn() as c:
                worker.run_job(self.settings, self.claude, worker.claim(c))
        finally:
            pipeline.generate = orig
        self.assertTrue(any("ValueError" in l for l in self.cap.lines))  # the crash is still logged, by class
        self.assertClean()
        self.assertEqual(self.run_row(run_id)["status"], "generating")  # left for another start

    def test_a_crash_in_a_route(self):
        run_id = self.start(AD)
        orig, cvtext.to_plain = cvtext.to_plain, lambda md: (_ for _ in ()).throw(KeyError(f"Nadia {MARK}"))
        try:
            with self.conn() as c:
                c.execute("update runs set status = 'passed', draft_md = 'x' where id = %s", (run_id,))
            self.assertEqual(self.get(f"/runs/{run_id}/edit", self.EMAIL).status_code, 500)
        finally:
            cvtext.to_plain = orig
        self.assertTrue(any("KeyError" in l for l in self.cap.lines))
        self.assertClean()


if __name__ == "__main__":
    unittest.main()
