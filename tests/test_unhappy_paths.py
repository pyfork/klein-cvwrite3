"""The likeliest unhappy paths the other suites only reach by their happy end: each Claude error kind,
a render that keeps failing, a job left running by a dead worker, a second re-render, and the render-failure pause."""
import threading
import unittest
from unittest import mock

import anthropic
import httpx2

from app import claude as claude_mod, pause, rendering, worker
from render import build_cv
from tests.render_env import needs_render
from tests.support import MASTER, CVCase


class ClaudeErrors(unittest.TestCase):
    def kind(self, exc):
        c = claude_mod.Claude.__new__(claude_mod.Claude)
        c.anthropic = anthropic
        c.client = mock.Mock()
        c.client.messages.create.side_effect = exc
        with self.assertRaises(claude_mod.ClaudeError) as e:
            c._json("call_a", claude_mod.OPUS, "system", "user", {"type": "object"})
        return str(e.exception)

    def test_each_sdk_error_becomes_its_kind(self):
        req = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")

        def resp(code):
            return httpx2.Response(code, request=req)
        for exc, kind in (
            (anthropic.RateLimitError("m", response=resp(429), body=None), "rate_limited"),
            (anthropic.APITimeoutError(request=req), "timeout"),
            (anthropic.APIConnectionError(request=req), "connection"),
            (anthropic.BadRequestError("m", response=resp(400), body=None), "bad_request"),
            (anthropic.APIStatusError("m", response=resp(529), body=None), "overloaded"),
            (anthropic.InternalServerError("m", response=resp(500), body=None), "http_500"),
        ):
            with self.subTest(kind=kind):
                self.assertEqual(self.kind(exc), kind)


class RenderRetry(unittest.TestCase):
    def test_one_retry_then_render_failed(self):
        with mock.patch.object(build_cv, "render_pdf", side_effect=build_cv.RenderError("timeout")) as r:
            with self.assertRaises(rendering.RenderFailed) as e:
                rendering.render("# x", "/nonexistent.pdf")
        self.assertEqual(r.call_count, 2)
        self.assertEqual(str(e.exception), "timeout")

    def test_a_hang_then_a_pass_is_two_tries(self):
        with mock.patch.object(build_cv, "render_pdf", side_effect=[build_cv.RenderError("timeout"), {"pages": 2}]):
            self.assertEqual(rendering.render("# x", "/nonexistent.pdf")["tries"], 2)


class RenderFailure(CVCase):
    def fail_renders(self):
        return mock.patch.object(rendering, "render", side_effect=rendering.RenderFailed("timeout"))

    def test_a_render_that_keeps_failing_fails_the_run_with_no_credit(self):
        with self.fail_renders():
            run_id = self.start()
            self.drain()
        run = self.run_row(run_id)
        self.assertEqual((run["status"], run["failure"]), ("failed", "render_failed"))
        self.assertEqual(self.credits(), 2)
        with self.conn() as c:
            job = c.execute("select status, outcome from jobs where run_id = %s", (run_id,)).fetchone()
        self.assertEqual((job["status"], job["outcome"]), ("failed", "render_failed"))

    def test_one_users_render_failures_dont_pause_everyone(self):
        with self.fail_renders():
            for _ in range(3):
                self.start()
                self.drain()
        with self.conn() as c:
            self.assertIsNone(pause.current(c))

    def test_render_failures_from_two_users_pause(self):
        self.approve("bob@example.com")
        self.agree("bob@example.com")
        self.post("/profile", "bob@example.com", {"master_text": MASTER.read_text(), "name": "Bob"})
        with self.fail_renders():
            for email in (self.EMAIL, "bob@example.com", self.EMAIL):
                self.start(email=email)
                self.drain()
        with self.conn() as c:
            self.assertEqual(pause.current(c)["reason"], "render failures")

    def two_users_fail_once_each(self):
        self.approve("bob@example.com")
        self.agree("bob@example.com")
        self.post("/profile", "bob@example.com", {"master_text": MASTER.read_text(), "name": "Bob"})
        ids = []
        with self.fail_renders():
            for email in (self.EMAIL, "bob@example.com"):
                ids.append(self.start(email=email))
                self.drain()
        return ids

    def test_failures_older_than_30_minutes_dont_count(self):
        ids = self.two_users_fail_once_each()
        with self.conn() as c:
            c.execute("update runs set created_at = now() - interval '31 minutes' where id = any(%s)", (ids,))
        with self.fail_renders():
            self.start()
            self.drain()
        with self.conn() as c:
            self.assertIsNone(pause.current(c))

    def test_other_kinds_of_failure_dont_count_toward_the_render_pause(self):
        ids = self.two_users_fail_once_each()
        with self.conn() as c:
            c.execute("update runs set failure = 'check_failed' where id = %s", (ids[1],))
        with self.fail_renders():
            self.start()
            self.drain()
        with self.conn() as c:
            self.assertIsNone(pause.current(c))


@needs_render
class DeadWorker(CVCase):
    def restart(self):
        """What a worker start does: serve() with its stop flag already set runs the start-up and exits."""
        stop = threading.Event()
        stop.set()
        worker.serve(self.settings, self.claude, stop=stop)

    def spends(self, run_id):
        with self.conn() as c:
            return c.execute("select count(*) n from credit_ledger where run_id = %s and kind = 'spend'", (run_id,)).fetchone()["n"]

    def job_status(self, run_id):
        with self.conn() as c:
            return c.execute("select status from jobs where run_id = %s and kind = 'generate'", (run_id,)).fetchone()["status"]

    def test_a_job_left_running_is_requeued_finished_and_charged_once(self):
        dead = self.start()
        with self.conn() as c:
            worker.claim(c)                                     # the worker took it, then died
        other = self.start()
        self.drain()                                            # a different job finishes normally: done
        self.assertEqual(self.job_status(dead), "running")
        self.assertEqual(self.job_status(other), "done")
        self.restart()
        self.assertEqual(self.job_status(dead), "queued")
        self.assertEqual(self.job_status(other), "done")       # a restart touches only running jobs
        self.drain()
        self.assertEqual(self.run_row(dead)["status"], "passed")
        self.assertEqual((self.spends(dead), self.spends(other)), (1, 1))

    def test_a_restart_after_the_run_passed_does_not_charge_again(self):
        run_id = self.start()
        self.drain()
        with self.conn() as c:                                  # died after the pass, before the job was marked done
            c.execute("update jobs set status = 'running' where run_id = %s", (run_id,))
        self.restart()
        self.drain()
        self.assertEqual(self.run_row(run_id)["status"], "passed")
        self.assertEqual(self.spends(run_id), 1)

    def edit(self, run_id):
        return self.post(f"/runs/{run_id}/edit", self.EMAIL, {"text": "SUMMARY\nA line."})

    def rerender_jobs(self, run_id):
        with self.conn() as c:
            return c.execute("select count(*) n from jobs where run_id = %s and kind = 'rerender'", (run_id,)).fetchone()["n"]

    def test_a_second_rerender_while_one_is_queued_or_running_is_refused(self):
        for status in ("queued", "running"):
            with self.subTest(status=status):
                run_id = self.start()
                self.drain()
                with self.conn() as c:
                    c.execute("insert into jobs (run_id, kind, input_text, status) values (%s, 'rerender', 'x', %s)", (run_id, status))
                r = self.edit(run_id)
                self.assertEqual(r.status_code, 409)
                self.assertIn("already running", r.text)
                self.assertEqual(self.rerender_jobs(run_id), 1)  # and no second job was made

    def test_a_rerender_on_another_run_or_a_finished_one_is_not_blocked(self):
        busy, free = self.start(), self.start()
        self.drain()
        with self.conn() as c:
            c.execute("insert into jobs (run_id, kind, input_text, status) values (%s, 'rerender', 'x', 'queued')", (busy,))
            c.execute("insert into jobs (run_id, kind, input_text, status) values (%s, 'rerender', 'x', 'done')", (free,))
        self.assertEqual(self.edit(free).status_code, 303)
        self.assertEqual(self.rerender_jobs(free), 2)


if __name__ == "__main__":
    unittest.main()
