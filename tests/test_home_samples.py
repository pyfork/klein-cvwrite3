"""app/home.py: the counts the home shows are worked out from the samples' words (redesign S-010).
Made-up stand-in content only. senior-lead-Opus5.5-agent"""
import json
import tempfile
import unittest
from pathlib import Path

from app import home

FILLER = " ".join(f"w{i}" for i in range(200))


def sample(**cv):
    c = {"title": "Sample Role", "kw": "Alpha · Beta", "summary": "Sample summary.", "featured": {"head": "H", "line": "L", "stats": [["1", "x"]]},
         "comp": [["Alpha", "one"]], "ach": [["A", "two"]], "exp": [{"role": "R", "dates": "D", "b": [["K", "V"]]}], "edu": ["E"]}
    c.update(cv)
    return {"id": "s1", "colour": "lilac", "short": "S", "person": "P", "personLine": "L",
            "ad": {"title": "Sample Role", "company": "Sample Co", "meta": "M", "lines": 10},
            "problems": [["p1", "q1"], ["p2", "q2"]],
            "top": [["alpha", "alpha", "backed"], ["gamma", "gamma", "bridged"], ["beta", "beta", "backed"]],
            "master": {"name": "Sample Person", "intro": "Intro.", "jobs": [{"head": "Job", "b": [FILLER + " beta"]}], "tail": []},
            "cv": c}


def load(*samples):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "s.json"
        p.write_text(json.dumps({"samples": list(samples)}), encoding="utf-8")
        return home.load(p)


class Counts(unittest.TestCase):
    def test_places_missing_and_counts(self):
        d = load(sample())
        s = d["samples"][0]
        self.assertEqual([r["m"] for r in s["rows"]], [None, None, 204])   # "beta" after 4 words and the filler
        self.assertEqual([r["c"] for r in s["rows"]], [4, None, 6])        # "Sample Person Sample Role Alpha · Beta": the dot is a word
        self.assertEqual((s["before_n"], s["after_n"], s["from_word"], s["in_zone"]), (1, 2, 5, 2))
        self.assertEqual(s["missing"], ["alpha", "gamma"])
        self.assertEqual(s["more_lines"], 8)
        self.assertEqual(s["chips"][1], ("gamma", "good match"))
        self.assertEqual((d["before"], d["after"], d["after_in_zone"], d["total"]), (1, 2, 2, 3))
        self.assertEqual(s["before_page"]["zone"], [])
        self.assertEqual([x["k"] for x in s["before_page"]["out"]], ["beta"])
        self.assertEqual([x["k"] for x in s["after_page"]["zone"]], ["alpha", "beta"])

    def test_late_stickers_never_sit_on_each_other(self):
        d = load(sample(edu=[FILLER + " alpha gamma beta"], kw="none", comp=[], title="x"))
        ys = [float(x["y"].rstrip("%")) for x in d["samples"][0]["after_page"]["out"]]
        self.assertEqual(len(ys), 3)
        self.assertTrue(all(b - a >= 10.95 for a, b in zip(ys, ys[1:])), ys)
        self.assertTrue(all(y <= 94 for y in ys), ys)   # none pushed off the page's foot

    def test_a_cv_with_no_top_keyword_fails_at_load(self):
        with self.assertRaises(ValueError):
            load(sample(kw="none", comp=[], title="x"))

    def test_highlight_escapes_then_marks(self):
        hi = load(sample())["samples"][0]["hi"]
        self.assertEqual(str(hi("<b>Alpha</b> & beta")), "&lt;b&gt;<mark>Alpha</mark>&lt;/b&gt; &amp; <mark>beta</mark>")

    def test_highlight_never_matches_inside_entities_or_marks(self):
        s = sample()
        s["top"] = [["alpha", "alpha", "backed"], ["mark", "mark", "backed"], ["a&b", "a&b", "backed"]]
        hi = load(s)["samples"][0]["hi"]
        self.assertEqual(str(hi("a&b mark <amp>")), "<mark>a&amp;b</mark> <mark>mark</mark> &lt;amp&gt;")

    def test_the_real_samples_load(self):
        d = home.load()
        self.assertEqual(len(d["samples"]), 3)
        self.assertEqual(d["total"], 9)


if __name__ == "__main__":
    unittest.main()
