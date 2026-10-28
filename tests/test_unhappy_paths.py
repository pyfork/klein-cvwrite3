"""The likeliest unhappy paths the other suites only reach by their happy end: each Claude error kind,
a render that keeps failing, a job left running by a dead worker, a second re-render, and the render-failure pause."""
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


@needs_render
class DeadWorker(CVCase):
    def test_a_job_left_running_is_requeued_finished_and_charged_once(self):
        run_id = self.start()
        with self.conn() as c:
            worker.claim(c)                                     # the worker took it, then died
            self.assertEqual(worker.requeue_running(c), 1)      # what serve() does on start
        self.drain()
        self.assertEqual(self.run_row(run_id)["status"], "passed")
        self.assertEqual(self.credits(), 1)

    def test_a_second_rerender_while_one_is_queued_is_refused(self):
        run_id = self.start()
        self.drain()
        with self.conn() as c:
            c.execute("insert into jobs (run_id, kind, input_text) values (%s, 'rerender', 'x')", (run_id,))
        r = self.post(f"/runs/{run_id}/edit", self.EMAIL, {"text": "SUMMARY\nA line."})
        self.assertEqual(r.status_code, 409)
        self.assertIn("already running", r.text)


if __name__ == "__main__":
    unittest.main()
