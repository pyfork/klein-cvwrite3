"""The pre-push guard, against a throwaway repo and a bare remote. Run: python3 -m unittest discover tests"""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

HOOKS = Path(__file__).resolve().parent.parent / "githooks"
# Made up, date-valid IC-shaped numbers. Not anyone's.
FAKE_IC_DASHED = "900101-14-" + "5678"
FAKE_IC_PLAIN = "900101" + "145678"
PRIVATE = "my-private-notes"


def git(cwd, *args, check=True):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=check)


class PrePush(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.remote, self.repo = root / "remote.git", root / "repo"
        git(root, "init", "-q", "--bare", str(self.remote))
        git(root, "init", "-q", "-b", "work", str(self.repo))
        for k, v in (("user.name", "t"), ("user.email", "t@example.com"), ("core.hooksPath", str(HOOKS))):
            git(self.repo, "config", k, v)
        git(self.repo, "remote", "add", "origin", str(self.remote))
        self.strings = self.repo / ".git" / "info" / "private-strings"
        self.strings.write_text(f"# one per line\n{PRIVATE.upper()}\n")
        self.commit("README.md", "hello\n")
        self.assertEqual(self.push().returncode, 0)

    def tearDown(self):
        self.tmp.cleanup()

    def commit(self, path, text):
        f = self.repo / path
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text)
        git(self.repo, "add", "-f", path)
        git(self.repo, "commit", "-q", "-m", f"add {path}")

    def push(self, branch="work"):
        return git(self.repo, "push", "-q", "origin", branch, check=False)

    def assertRefused(self, what):
        r = self.push()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn(what, r.stderr)
        return r

    def test_clean_push_passes(self):
        self.commit("app/main.py", "print('ok')\nphone = '012-345 6789'\n")
        self.assertEqual(self.push().returncode, 0)

    def test_blocked_paths(self):
        for path, label in (
            (".env", ".env file"),
            ("deploy/.env.prod", ".env file"),
            ("prompts/write.md", "prompts/"),
            ("config/qr/duitnow.png", "QR"),
            ("static/my-QR.png", "QR image"),
            ("CLAUDE.md", "CLAUDE*.md"),
            ("docs/CLAUDE.local.md", "CLAUDE*.md"),
            ("docs/README-roadmap.md", "docs/"),
            ("docs/agents/lead.md", "docs/"),
        ):
            with self.subTest(path=path):
                git(self.repo, "reset", "-q", "--hard", "origin/work")
                self.commit(path, "x\n")
                self.assertRefused(label)

    def test_docs_public_and_nested_docs_pass(self):
        self.commit("docs-public/project-rules.md", "x\n")
        self.commit("app/docs/help.md", "x\n")
        self.assertEqual(self.push().returncode, 0)

    def test_missing_private_strings_refuses_every_push(self):
        self.strings.unlink()
        self.commit("ok.txt", "fine\n")
        self.assertRefused("private-strings is missing")

    def test_empty_private_strings_means_none(self):
        self.strings.write_text("")
        self.commit("ok.txt", f"{PRIVATE}\n")
        self.assertEqual(self.push().returncode, 0)

    def test_private_string_in_line_name_and_message(self):
        for how in ("line", "name", "message"):
            with self.subTest(how=how):
                git(self.repo, "reset", "-q", "--hard", "origin/work")
                path = f"{PRIVATE}.txt" if how == "name" else "notes.txt"
                self.commit(path, f"one\nsee {PRIVATE}\n" if how == "line" else "x\n")
                if how == "message":
                    git(self.repo, "commit", "-q", "--amend", "-m", f"from {PRIVATE.title()}")
                want = {"line": "notes.txt:2: private string", "name": "private string in the file name",
                        "message": "private string in the message"}[how]
                r = self.assertRefused(want)
                if how != "name":
                    self.assertNotIn(PRIVATE, r.stderr.lower())

    def test_ic_number_dashed_and_plain(self):
        for n in (FAKE_IC_DASHED, FAKE_IC_PLAIN):
            with self.subTest(n=n):
                git(self.repo, "reset", "-q", "--hard", "origin/work")
                self.commit("notes.txt", f"line one\nIC {n}\n")
                r = self.assertRefused("notes.txt:2: looks like an IC number")
                self.assertNotIn(n, r.stderr)

    def test_not_ic_numbers(self):
        # invalid month, 13 digits, mixed dashes, phone numbers, 12 digits inside a sha256
        self.commit("data.txt", "901301-14-5678\n9001011456789\n900101-145678\n+60 12-345 6789\n"
                    "--hash=sha256:cbd5f73073ed19c378d4c35499db1e3e703a5b1a324e521204065967bfaa7a18\n")
        self.assertEqual(self.push().returncode, 0)

    def test_added_then_removed_still_blocked(self):
        self.commit(".env", "KEY=x\n")
        git(self.repo, "rm", "-q", ".env")
        git(self.repo, "commit", "-q", "-m", "remove")
        self.assertRefused(".env file")

    def test_new_branch_checks_only_unpushed_commits(self):
        git(self.repo, "switch", "-q", "-c", "feature")
        self.commit("ok.txt", "fine\n")
        self.assertEqual(self.push("feature").returncode, 0)



@unittest.skipIf(os.environ.get("CI"), "a CI checkout has no local guard; the push-guard job runs it there")
class ThisClone(unittest.TestCase):
    """The guard only protects a clone that has it switched on. A fresh clone fails here until it does."""

    def test_guard_is_on(self):
        root = HOOKS.parent
        path = git(root, "config", "core.hooksPath", check=False).stdout.strip()
        self.assertEqual(path, "githooks", "run: git config core.hooksPath githooks")
        common = git(root, "rev-parse", "--path-format=absolute", "--git-common-dir").stdout.strip()
        self.assertTrue((Path(common) / "info" / "private-strings").is_file(),
                        "create .git/info/private-strings (one private string per line, or empty)")


if __name__ == "__main__":
    unittest.main()
