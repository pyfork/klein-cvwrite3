"""A stand-in for Claude in tests and dev (CVWRITE_CLAUDE=fake). Deterministic, no network, no cost.

It reads an ad with simple rules, quoting the ad word for word, and writes a CV from the made-up
fixture (tests/fixtures/sample_draft.md) with the ad's keywords put in. `script` can make the next
calls fail, to test the retry, failure and pause paths.
"""
import re
from pathlib import Path

from .claude import HAIKU, OPUS, ClaudeError, Result

FIXTURE = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "sample_draft.md"


class FakeClaude:
    def __init__(self):
        self.script = []   # e.g. ["write:3pages", "read:error"]; consumed in order by matching calls
        self.calls = []

    def _next(self, kind):
        for i, s in enumerate(self.script):
            if s.split(":")[0] == kind:
                return self.script.pop(i).split(":", 1)[1]
        return None

    def read_ad(self, ad_text):
        self.calls.append("read")
        if self._next("read") == "error":
            raise ClaudeError("overloaded")
        lines = [l.strip() for l in ad_text.splitlines() if l.strip()]
        title = lines[0][:80]
        sentences = re.split(r"(?<=[.!?])\s+", " ".join(lines))
        problem_q = next((s for s in sentences if re.search(r"\b(need|problem|fix|struggl|keeping up|late)\b", s, re.I)), sentences[1] if len(sentences) > 1 else sentences[0])
        quote = problem_q.strip()[:160]
        bullets = [re.sub(r"^[-•*]\s*", "", l) for l in lines if re.match(r"^[-•*]\s", l)]
        kws = []
        for b in bullets:
            for chunk in re.split(r"[,.;()]| with | and | or ", b):
                c = chunk.strip()
                if 2 <= len(c) <= 30 and 1 <= len(c.split()) <= 3 and c.lower() not in [k.lower() for k in kws]:
                    kws.append(c)
        kws = kws or [w for w in re.findall(r"\b[A-Z][A-Za-z]{2,}\b", ad_text)][:6]
        return Result({
            "job_title": title, "company": "",
            "problems": [{"problem": "the work isn't keeping up", "quote": quote}],
            "keywords_top": kws[:3], "keywords_secondary": kws[3:8],
            "red_flags": [{"flag": "made-up quote, dropped by the check", "quote": "this sentence is not in the ad"}],
        }, OPUS, 2100, 900, "req_fake_a")

    def write_cv(self, user_message):
        self.calls.append("write")
        mode = self._next("write")
        if mode == "error":
            raise ClaudeError("overloaded")
        kws = re.search(r'"keywords_top": \[(.*?)\]', user_message, re.S)
        keywords = re.findall(r'"([^"]+)"', kws.group(1)) if kws else []
        md = FIXTURE.read_text(encoding="utf-8")
        summary = ("Operations lead who fixes the problems behind the numbers, with " +
                   ", ".join(keywords[:3]) + " at the centre of the work. Eleven years of steady delivery for growing teams.")
        md = re.sub(r"(## PROFESSIONAL SUMMARY\n).*?\n", lambda m: m.group(1) + summary + "\n", md, count=1, flags=re.S)
        if mode == "3pages":
            md = md.replace("## KEY ACHIEVEMENTS", "## KEY ACHIEVEMENTS\n" + "\n".join(
                f"- **Extra {i}:** a long line that pushes the CV onto a third page, repeated to fill the space." for i in range(60)), 1)
        if mode == "longsummary":
            md = md.replace(summary, summary + " " + "More words to run the summary well past its limit." * 3)
        return Result({"cv_markdown": md, "gaps": ["The ad asks for Power BI; the master CV shows another tool."]},
                      OPUS, 6200, 3100, "req_fake_b")

    def reformat(self, user_message):
        self.calls.append("reformat")
        mode = self._next("reformat")
        if mode == "error":
            raise ClaudeError("overloaded")
        prev = re.search(r"<previous_cv_markdown>\n(.*?)\n</previous_cv_markdown>", user_message, re.S).group(1)
        text = re.search(r"<edited_plain_text>\n(.*?)\n</edited_plain_text>", user_message, re.S).group(1)
        header = prev[: prev.index("## ")] if "## " in prev else ""
        headings = {l[3:].strip() for l in prev.splitlines() if l.startswith("## ")}
        out = []
        for line in text.splitlines():
            s = line.strip()
            if s in headings or (s and s == s.upper() and re.fullmatch(r"[A-Z][A-Z0-9 &/·,()+-]+", s)):
                out.append("## " + s)
            else:
                out.append(line)
        md = header + "\n".join(out)
        if mode == "rewrite":
            md = header + "## PROFESSIONAL SUMMARY\nA completely different text written by the model.\n"
        return Result({"cv_markdown": md}, HAIKU, 3000, 2500, "req_fake_r")
