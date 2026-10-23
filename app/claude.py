"""The three Claude calls: A (read the ad), B (write the CV), and the Haiku re-format.

Plain Messages API calls with no tools. Every call writes a `usage` row and a `run_steps` row with
tokens and cost; neither holds any content. Prices and settings: docs/README-claude-api.md (private).
"""
import json
import time
from dataclasses import dataclass
from decimal import Decimal

from . import adread, prompts

OPUS = "claude-opus-5-5"
HAIKU = "claude-haiku-5-5"
# USD per 1M tokens (input, output). Haiku's are for prompts up to 100K tokens, which ours always are.
PRICES = {OPUS: (Decimal("4.00"), Decimal("20.00")), HAIKU: (Decimal("0.10"), Decimal("0.50"))}
EFFORT = {"call_a": "medium", "call_b": "medium", "reformat": "low"}
TIMEOUT_S = 180


class ClaudeError(RuntimeError):
    """A call that failed after the SDK's own retries. `kind` is an error class, never content."""

    def __init__(self, kind):
        super().__init__(kind)
        self.kind = kind


@dataclass
class Result:
    data: object
    model: str
    input_tokens: int
    output_tokens: int
    request_id: str = ""


def cost(model, input_tokens, output_tokens):
    pin, pout = PRICES.get(model, PRICES[OPUS])
    return (pin * input_tokens + pout * output_tokens) / Decimal(1_000_000)


WRITE_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["cv_markdown", "gaps"],
    "properties": {
        "cv_markdown": {"type": "string"},
        "gaps": {"type": "array", "items": {"type": "string"},
                 "description": "what the ad asks for that the master CV can't show, one line each"},
    },
}
REFORMAT_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["cv_markdown"],
    "properties": {"cv_markdown": {"type": "string"}},
}


class Claude:
    """The real client. Create once per worker."""

    def __init__(self, api_key=None):
        import anthropic
        self.anthropic = anthropic
        self.client = anthropic.Anthropic(api_key=api_key, timeout=TIMEOUT_S, max_retries=2)

    def _json(self, step, model, system, user, schema, max_tokens=16000):
        a = self.anthropic
        kwargs = dict(model=model, max_tokens=max_tokens, system=system,
                      messages=[{"role": "user", "content": user}],
                      output_config={"effort": EFFORT[step], "format": {"type": "json_schema", "schema": schema}})
        try:
            if model == OPUS:
                # Refusal fallbacks: a declined request is re-run on another model inside the same call.
                r = self.client.beta.messages.create(betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kwargs)
            else:
                r = self.client.messages.create(**kwargs)
        except a.RateLimitError:
            raise ClaudeError("rate_limited") from None
        except a.APITimeoutError:
            raise ClaudeError("timeout") from None
        except a.APIConnectionError:
            raise ClaudeError("connection") from None
        except a.BadRequestError:
            raise ClaudeError("bad_request") from None
        except a.APIStatusError as e:
            raise ClaudeError("overloaded" if e.status_code == 529 else f"http_{e.status_code}") from None
        if r.stop_reason == "refusal":
            raise ClaudeError("refusal")
        if r.stop_reason == "max_tokens":
            raise ClaudeError("max_tokens")
        text = next((b.text for b in r.content if b.type == "text"), "")
        try:
            data = json.loads(text)
        except ValueError:
            raise ClaudeError("bad_json") from None
        return Result(data, r.model, r.usage.input_tokens, r.usage.output_tokens, getattr(r, "_request_id", "") or "")

    def read_ad(self, ad_text):
        return self._json("call_a", OPUS, prompts.get("ad_read"), adread.wrap_ad(ad_text), adread.SCHEMA)

    def write_cv(self, user_message):
        return self._json("call_b", OPUS, prompts.get("write_cv"), user_message, WRITE_SCHEMA)

    def reformat(self, user_message):
        return self._json("reformat", HAIKU, prompts.get("reformat"), user_message, REFORMAT_SCHEMA, max_tokens=8000)


def write_message(masked_master, standing_edits, ad_text, ad_read, feedback=None):
    """Call B's user message. The master CV has its contact values masked; the ad is delimited data."""
    read = {k: ad_read[k] for k in ("job_title", "company", "problems", "keywords_top", "keywords_secondary", "red_flags")}
    parts = [
        "<master_cv>\n" + masked_master + "\n</master_cv>",
        "<standing_edits>\n" + (standing_edits or "(none)") + "\n</standing_edits>",
        adread.wrap_ad(ad_text),
        "<ad_read>\n" + json.dumps(read, ensure_ascii=False, indent=1) + "\n</ad_read>",
    ]
    if feedback:
        parts.append("<check_failed>\nYour last draft failed this check: " + feedback +
                     "\nFix only that. Change nothing else.\n</check_failed>")
    return "\n\n".join(parts)


def reformat_message(previous_md, user_text):
    return ("<previous_cv_markdown>\n" + previous_md + "\n</previous_cv_markdown>\n\n"
            "<edited_plain_text>\n" + user_text + "\n</edited_plain_text>")


def record(conn, step, result_or_error, started, run_id=None, job_id=None, account_id=None, model=None):
    """A run_steps row for any call, and a usage row when tokens were spent."""
    ms = int((time.monotonic() - started) * 1000)
    from datetime import datetime, timedelta, timezone
    at = datetime.now(timezone.utc) - timedelta(milliseconds=ms)
    if isinstance(result_or_error, Result):
        r = result_or_error
        conn.execute(
            "insert into run_steps (run_id, job_id, step, started_at, duration_ms, outcome, model, input_tokens, output_tokens) "
            "values (%s, %s, %s, %s, %s, 'ok', %s, %s, %s)", (run_id, job_id, step, at, ms, r.model, r.input_tokens, r.output_tokens))
        conn.execute(
            "insert into usage (run_id, account_id, step, model, input_tokens, output_tokens, cost_usd, request_id) "
            "values (%s, %s, %s, %s, %s, %s, %s, %s)",
            (run_id, account_id, step, r.model, r.input_tokens, r.output_tokens, cost(r.model, r.input_tokens, r.output_tokens), r.request_id))
    else:
        conn.execute(
            "insert into run_steps (run_id, job_id, step, started_at, duration_ms, outcome, model, error_class) "
            "values (%s, %s, %s, %s, %s, 'error', %s, %s)", (run_id, job_id, step, at, ms, model, getattr(result_or_error, "kind", type(result_or_error).__name__)))
