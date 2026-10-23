"""The worker: takes jobs from Postgres (FOR UPDATE SKIP LOCKED), up to 3 at once, one Chrome at a time.

Run: python -m app.worker   (systemd: cvwrite3-worker.service, Restart=always)
- On start, every `running` job goes back to `queued` and resumes from its run's checkpoints.
- A test render runs once after start, then hourly unless a real CV passed in the last 2 hours.
- SIGTERM: stop taking jobs, let the running ones finish (TimeoutStopSec=90), then exit.
"""
import logging
import signal
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from . import config, db, pipeline

log = logging.getLogger("cvwrite3.worker")
SLOTS = 3
MAX_STARTS = 3
GIVE_UP_AFTER_MIN = 10   # from the click, while not paused
HELD_FOR_H = 24


def claim(conn):
    return conn.execute(
        """update jobs set status = 'running', started_at = now(), attempts = attempts + 1
           where id = (select id from jobs where status = 'queued' order by created_at for update skip locked limit 1)
           returning *""").fetchone()


def requeue_running(conn):
    return conn.execute("update jobs set status = 'queued' where status = 'running'").rowcount


def expire(conn):
    """Held jobs wait up to 24 h; then the run fails with no credit used."""
    rows = conn.execute(
        """update jobs set status = 'expired', finished_at = now(), outcome = 'expired', message = %s
           where status = 'held' and held_at < now() - interval '24 hours' returning run_id""",
        (pipeline.MSG["expired"],)).fetchall()
    for r in rows:
        conn.execute("update runs set status = 'failed', failure = 'expired' where id = %s and status = 'generating'", (r["run_id"],))


def finish(conn, job, status, outcome, message):
    conn.execute("update jobs set status = %s, outcome = %s, message = %s, finished_at = now() where id = %s",
                 (status, outcome, message, job["id"]))


def run_job(settings, claude, job):
    with db.connect(settings.database_url) as conn:
        if job["kind"] == "generate":
            conn.execute(
                "insert into run_steps (run_id, job_id, step, started_at, duration_ms, outcome) "
                "select %s, %s, 'queue_wait', created_at, (extract(epoch from now() - created_at) * 1000)::int, 'ok' from jobs where id = %s",
                (job["run_id"], job["id"], job["id"]))
        too_old = job["kind"] == "generate" and conn.execute(
            "select now() - created_at > interval '%s minutes' as old from jobs where id = %%s" % GIVE_UP_AFTER_MIN, (job["id"],)
        ).fetchone()["old"] and job["attempts"] > 1
        try:
            if job["attempts"] > MAX_STARTS or too_old:
                raise pipeline.Stop("too_many_attempts")
            if job["kind"] == "generate":
                outcome, message = pipeline.generate(conn, settings, claude, job)
            elif job["kind"] == "rerender":
                outcome, message = pipeline.rerender(conn, settings, claude, job)
            else:
                ok, summary = pipeline.test_render(conn, settings)
                outcome, message = ("passed" if ok else "failed"), summary
            finish(conn, job, "done", outcome, message)
        except pipeline.Hold:
            conn.execute("update jobs set status = 'held', held_at = coalesce(held_at, now()) where id = %s", (job["id"],))
        except pipeline.Stop as s:
            finish(conn, job, "failed" if job["kind"] == "generate" else "done", s.outcome, s.message)
            if job["kind"] == "generate":
                conn.execute("update runs set status = 'failed', failure = coalesce(failure, %s) where id = %s and status = 'generating'",
                             (s.outcome, job["run_id"]))
        except Exception as e:  # a bug: leave the job queued for another start; MAX_STARTS bounds it
            log.exception("job %s crashed: %s", job["id"], type(e).__name__)
            conn.execute("update jobs set status = 'queued' where id = %s and status = 'running'", (job["id"],))
            time.sleep(2)


def due_test_render(conn):
    """True when no test or real render has passed in the last 2 hours."""
    return conn.execute(
        """select not exists (select 1 from run_steps where step in ('render', 'test_render') and outcome = 'ok'
                              and started_at > now() - interval '2 hours') as due""").fetchone()["due"]


def enqueue_test(conn):
    conn.execute("insert into jobs (kind) select 'test_render' where not exists "
                 "(select 1 from jobs where kind = 'test_render' and status in ('queued', 'running'))")


def make_claude(settings):
    if settings.claude == "fake":
        from .fakeclaude import FakeClaude
        return FakeClaude()
    from .claude import Claude
    return Claude()


def serve(settings, claude=None, stop=None, poll_s=1.0):
    claude = claude or make_claude(settings)
    stop = stop or threading.Event()
    with db.connect(settings.database_url) as conn:
        n = requeue_running(conn)
        if n:
            log.info("requeued %s jobs after a restart", n)
        enqueue_test(conn)  # once right after every start
    busy = threading.Semaphore(SLOTS)
    last_hourly = time.monotonic()
    with ThreadPoolExecutor(SLOTS) as pool:
        while not stop.is_set():
            with db.connect(settings.database_url) as conn:
                expire(conn)
                if time.monotonic() - last_hourly > 3600:
                    last_hourly = time.monotonic()
                    if due_test_render(conn):
                        enqueue_test(conn)
                while busy.acquire(blocking=False):
                    job = claim(conn)
                    if not job:
                        busy.release()
                        break

                    def done(_f, b=busy):
                        b.release()
                    pool.submit(run_job, settings, claude, job).add_done_callback(done)
            stop.wait(poll_s)


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    settings = config.load()
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    serve(settings, stop=stop)


if __name__ == "__main__":
    main()
