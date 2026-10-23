"""What the worker does for one job: a generation (call A, call B, render, check, one internal retry)
or a re-render (Haiku re-format, word check, render, check). Checkpoints on the run mean a crash never
pays Claude twice. A credit is used only in the same transaction that marks the run passed."""
import json
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from render import contact as contact_mod

from . import adread, claude as claude_mod, cvtext, pause, profile, rendering

MAX_DRAFTS = 2  # the first draft and one internal retry
MAX_RERENDERS = 3

MSG = {
    "paused": "Generating is paused, so this CV wasn't started. No credit used.",
    "ad_read_failed": "We couldn't read this ad well enough to write a CV for it. No credit used. Check that you pasted the whole ad.",
    "claude_failed": "The AI service didn't answer. No credit used. Please try again in a few minutes.",
    "render_failed": "We couldn't turn this CV into a PDF. No credit used.",
    "check_failed": "We couldn't produce a passing CV for this ad. No credit used.",
    "cancelled": "This CV was cancelled. No credit used.",
    "expired": "We couldn't finish this one in time. No credit used.",
    "too_many_attempts": "This CV kept failing, so we stopped. No credit used.",
}


class Stop(Exception):
    """End the job with this outcome (a key of MSG, or a re-render outcome)."""

    def __init__(self, outcome, message=None):
        super().__init__(outcome)
        self.outcome = outcome
        self.message = message or MSG.get(outcome, "")


class Hold(Exception):
    """Generating is paused and this job is past call B: keep it, finish it after the resume."""


def _step(conn, run_id, job_id, step, started, outcome, **extra):
    ms = int((time.monotonic() - started) * 1000)
    at = datetime.now(timezone.utc) - timedelta(milliseconds=ms)
    cols = ["run_id", "job_id", "step", "started_at", "duration_ms", "outcome", *extra]
    conn.execute(f"insert into run_steps ({', '.join(cols)}) values ({', '.join(['%s'] * len(cols))})",
                 (run_id, job_id, step, at, ms, outcome, *extra.values()))


def _call(conn, step, fn, run, job):
    t0 = time.monotonic()
    try:
        res = fn()
    except claude_mod.ClaudeError as e:
        claude_mod.record(conn, step, e, t0, run["id"], job["id"], run["account_id"], claude_mod.OPUS if step != "reformat" else claude_mod.HAIKU)
        pause.after_claude_failure(conn)
        raise Stop("claude_failed" if step != "reformat" else "format_failed",
                   None if step != "reformat" else "We couldn't format this. Please check your headings. Your text is kept as you wrote it, and this didn't use a re-render.") from None
    claude_mod.record(conn, step, res, t0, run["id"], job["id"], run["account_id"])
    return res


def _render_and_check(conn, settings, run, job, md, keywords):
    tmp = Path(tempfile.mkdtemp(prefix="cvw3-")) / "cv.pdf"
    t0 = time.monotonic()
    try:
        info = rendering.render(md, tmp)
    except rendering.RenderFailed as e:
        _step(conn, run["id"], job["id"], "render", t0, "fail", error_class=e.kind)
        return None, None
    _step(conn, run["id"], job["id"], "render", t0, "ok", memory_peak=info["memory_peak"])
    if info["wait_ms"]:
        conn.execute("insert into run_steps (run_id, job_id, step, started_at, duration_ms, outcome) values (%s, %s, 'admission_wait', now(), %s, 'ok')",
                     (run["id"], job["id"], info["wait_ms"]))
    t0 = time.monotonic()
    try:
        result = rendering.check(tmp, keywords)
    except rendering.RenderFailed as e:
        _step(conn, run["id"], job["id"], "check", t0, "error", error_class=e.kind)
        return None, None
    why = None if result["passed"] else ",".join(
        [f"pages_{result['pages']}"] * (result["pages"] != 2) + ["not_a4"] * (not result["a4"])
        + [f"keywords_missing_{sum(not v for v in result['keywords'].values())}"] * (not all(result["keywords"].values())))
    _step(conn, run["id"], job["id"], "check", t0, "ok" if result["passed"] else "fail", error_class=why)
    return tmp, result


def keyword_status(top, reported):
    """{keyword: backed|bridged|missing} for each top-3 keyword. Anything not reported counts as backed,
    so a keyword is only ever let off the check when call B says it's missing."""
    said = {str(k.get("keyword", "")).strip().lower(): k.get("status") for k in reported if isinstance(k, dict)}
    return {kw: said.get(kw.lower()) if said.get(kw.lower()) in ("backed", "bridged", "missing") else "backed" for kw in top}


def required(run):
    """The keywords the check requires: backed and bridged. Missing ones only warn."""
    status = run.get("keyword_status") or {}
    return [kw for kw in run["ad_read"]["keywords_top"] if status.get(kw, "backed") != "missing"]


def _pre_render(draft):
    """Checks on the Markdown before Chrome starts. Returns a problem for the retry, or None."""
    for marker in ("{{NAME}}", "{{CONTACT}}"):
        if draft.count(marker) != 1:
            return f"the draft must contain {marker} exactly once; it has {draft.count(marker)}"
    n = cvtext.summary_words(draft)
    if n == 0:
        return f"the draft has no ## {cvtext.SUMMARY} section"
    if n > cvtext.SUMMARY_MAX_WORDS:
        return f"summary is {n} words, cut to {cvtext.SUMMARY_MAX_WORDS}, change nothing else"
    return None


def _describe(check):
    bits = []
    if check["pages"] != 2:
        bits.append(f"the PDF is {check['pages']} pages, it must be exactly 2: {'cut' if check['pages'] > 2 else 'add'} content, change nothing else")
    if not check["a4"]:
        bits.append("the page size isn't A4")
    missing = [k for k, ok in check["keywords"].items() if not ok]
    if missing:
        bits.append("these keywords must appear exactly as worded: " + ", ".join(f'"{k}"' for k in missing))
    return "; ".join(bits) or "the text layer is empty"


def generate(conn, settings, claude, job):
    run = conn.execute("select * from runs where id = %s", (job["run_id"],)).fetchone()
    if run["status"] != "generating":
        raise Stop("cancelled")
    paused = pause.current(conn)
    if paused and run["draft_md"] is None:
        raise Stop("paused")
    prof = profile.get(conn, run["account_id"])
    data = profile.contact(prof)

    if run["ad_read"] is None:
        res = _call(conn, "call_a", lambda: claude.read_ad(run["ad_text"]), run, job)
        try:
            read = adread.verify(res.data, run["ad_text"])
        except adread.AdReadError as e:
            conn.execute("update runs set failure = %s where id = %s", (str(e), run["id"]))
            raise Stop("ad_read_failed") from None
        conn.execute("update runs set ad_read = %s where id = %s", (json.dumps(read), run["id"]))
        run["ad_read"] = read
    read = run["ad_read"]
    masked, _ = contact_mod.mask(prof["master_text"], data)

    def write(feedback, step):
        r = _call(conn, step, lambda: claude.write_cv(claude_mod.write_message(masked, prof["standing_edits"], run["ad_text"], read, feedback)), run, job)
        draft = str(r.data.get("cv_markdown", ""))
        gaps = [str(g)[:200] for g in r.data.get("gaps", [])][:8]
        status = keyword_status(read["keywords_top"], r.data.get("keyword_status", []))
        conn.execute("update runs set draft_md = %s, gaps = %s, keyword_status = %s, drafts = drafts + 1 where id = %s",
                     (draft, json.dumps(gaps), json.dumps(status), run["id"]))
        run["draft_md"], run["drafts"], run["keyword_status"] = draft, run["drafts"] + 1, status

    if run["draft_md"] is None:
        if paused:
            raise Stop("paused")
        write(None, "call_b")

    while True:
        if pause.current(conn):
            raise Hold()
        problem = _pre_render(run["draft_md"])
        check = None
        if problem is None:
            try:
                md = contact_mod.merge(run["draft_md"], data)
            except contact_mod.MergeError as e:
                problem = str(e)
            else:
                pdf, check = _render_and_check(conn, settings, run, job, md, required(run))
                if check is None:
                    conn.execute("update runs set failure = 'render_failed' where id = %s", (run["id"],))
                    pause.after_render_failure(conn)
                    raise Stop("render_failed")
                if check["passed"]:
                    return _pass(conn, settings, run, job, pdf, check)
                problem = _describe(check)
        if run["drafts"] >= MAX_DRAFTS:
            conn.execute("update runs set failure = 'check_failed', checks = %s where id = %s", (json.dumps(check), run["id"]))
            raise Stop("check_failed")
        if pause.current(conn):
            raise Hold()
        write(problem, "retry")


def _pass(conn, settings, run, job, tmp_pdf, check):
    with conn.transaction():
        row = conn.execute(
            "update runs set status = 'passed', checks = %s, pdf_rev = pdf_rev + 1, passed_at = now(), failure = null "
            "where id = %s and status = 'generating' returning pdf_rev", (json.dumps(check), run["id"])).fetchone()
        if not row:
            raise Stop("cancelled")
        conn.execute("insert into credit_ledger (account_id, delta, kind, run_id) values (%s, -1, 'spend', %s)",
                     (run["account_id"], run["id"]))
        rendering.replace_pdf(settings.data_dir, run["id"], 0, tmp_pdf, row["pdf_rev"])
    return "passed", ""


def rerender(conn, settings, claude, job):
    run = conn.execute("select * from runs where id = %s", (job["run_id"],)).fetchone()
    if run["status"] != "passed":
        raise Stop("cancelled")
    if pause.current(conn):
        raise Stop("paused", "Re-rendering is paused. Your text is kept, and this didn't use a re-render.")
    if run["rerenders_used"] >= MAX_RERENDERS:
        raise Stop("limit", "You've used the 3 free re-renders for this CV. Start a new CV for 1 credit.")
    prof = profile.get(conn, run["account_id"])
    header, old_body = cvtext.header_and_body(run["draft_md"])
    body_text, header_changed = cvtext.plain_body(job["input_text"])
    res = _call(conn, "reformat", lambda: claude.reformat(claude_mod.reformat_message(old_body, body_text)), run, job)
    new_body = cvtext.header_and_body(str(res.data.get("cv_markdown", "")))[1]
    new_md = header + new_body
    ok, kept = cvtext.word_check(body_text, new_md)
    t0 = time.monotonic()
    _step(conn, run["id"], job["id"], "word_check", t0, "ok" if ok else "fail")
    if not ok:
        raise Stop("format_failed", "We couldn't format this. Please check your headings. Your text is kept as you wrote it, and this didn't use a re-render.")
    md = contact_mod.merge(new_md, profile.contact(prof))
    pdf, check = _render_and_check(conn, settings, run, job, md, required(run))
    if check is None:
        raise Stop("render_failed", "We couldn't turn this into a PDF. Your text is kept, and this didn't use a re-render.")
    if check["pages"] != 2 or not check["a4"]:
        conn.execute("update runs set rerenders_used = rerenders_used + 1 where id = %s", (run["id"],))
        n = check["pages"]
        raise Stop("blocked_pages", f"Your edit runs to {n} page{'s' if n != 1 else ''}. "
                   + ("Trim it and try again." if n > 2 else "A CV here needs to fill 2 pages.") + " This used 1 re-render.")
    notes = []
    missing = [k for k, v in check["keywords"].items() if not v]
    if missing:
        notes.append(("No longer in your CV: " + ", ".join(f"“{k}”" for k in missing) + ". It still passed."))
    n = cvtext.summary_words(new_md)
    if n > cvtext.SUMMARY_MAX_WORDS:
        notes.append(f"Your summary is {n} words. Aim for {cvtext.SUMMARY_MAX_WORDS} or fewer.")
    if header_changed:
        notes.append("We ignored changes above the first heading: change your name and contact details in Profile.")
    with conn.transaction():
        row = conn.execute(
            "update runs set draft_md = %s, checks = %s, pdf_rev = pdf_rev + 1, rerenders_used = rerenders_used + 1 "
            "where id = %s and status = 'passed' returning pdf_rev", (new_md, json.dumps(check), run["id"])).fetchone()
        if not row:
            raise Stop("cancelled")
        rendering.replace_pdf(settings.data_dir, run["id"], run["pdf_rev"], pdf, row["pdf_rev"])
    return "passed", " ".join(notes)


TEST_DRAFT = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "sample_draft.md"
TEST_CONTACT = {"name": "Test Candidate", "location": "Shah Alam", "phone": "+60 12-000 0000", "email": "test@example.com"}
TEST_KEYWORDS = ["payroll", "HRIS", "employee relations"]


def test_render(conn, settings):
    """Renders the made-up fixture through the same render and check. Returns (passed, summary)."""
    md = contact_mod.merge(TEST_DRAFT.read_text(encoding="utf-8"), TEST_CONTACT)
    tmp = Path(tempfile.mkdtemp(prefix="cvw3-test-")) / "test.pdf"
    t0 = time.monotonic()
    try:
        info = rendering.render(md, tmp)
        check = rendering.check(tmp, TEST_KEYWORDS)
        ok = check["pages"] == 2 and check["a4"] and check["text_ok"] and all(check["keywords"].values())
        _step(conn, None, None, "test_render", t0, "ok" if ok else "fail", memory_peak=info["memory_peak"])
        summary = f"{check['pages']} pages · {'A4' if check['a4'] else 'not A4'} · keywords {sum(check['keywords'].values())} of 3"
    except rendering.RenderFailed as e:
        _step(conn, None, None, "test_render", t0, "fail", error_class=e.kind)
        ok, summary = False, e.kind
    finally:
        tmp.unlink(missing_ok=True)
    pause.after_test_render(conn)
    return ok, summary
