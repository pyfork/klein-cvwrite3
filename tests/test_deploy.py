"""Chunk 7b: the deploy files agree with the app. Static checks; nothing here touches a server."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UNITS = sorted((ROOT / "deploy" / "systemd").glob("*.service"))


class Deploy(unittest.TestCase):
    def test_units_run_real_modules_as_cvwrite3(self):
        self.assertEqual(len(UNITS), 4)
        for u in UNITS:
            text = u.read_text()
            for key in ("User=cvwrite3", "Slice=cvwrite3.slice", "LogNamespace=cvwrite3", "EnvironmentFile=/sites/cvwrite3/.env",
                        "ProtectSystem=strict", "ReadWritePaths=/sites/cvwrite3/data", "NoNewPrivileges=yes"):
                self.assertIn(key, text, f"{u.name}: {key}")
            for mod in re.findall(r"python -m (app\.\w+)", text) + re.findall(r"uvicorn (app\.\w+):", text):
                self.assertTrue((ROOT / (mod.replace(".", "/") + ".py")).exists(), f"{u.name}: {mod}")

    def test_worker_limits_match_the_brief(self):
        w = (ROOT / "deploy/systemd/cvwrite3-worker.service").read_text()
        for key in ("MemoryMax=550M", "OOMPolicy=continue", "Restart=always", "TimeoutStopSec=90", "PrivateTmp=yes"):
            self.assertIn(key, w)
        self.assertNotIn("\nPrivateDevices=yes", w)  # Chrome needs /dev/shm
        s = (ROOT / "deploy/systemd/cvwrite3.slice").read_text()
        for key in ("MemoryHigh=600M", "MemoryMax=750M", "MemorySwapMax=0", "CPUWeight=50", "CPUQuota=150%"):
            self.assertIn(key, s)

    def test_timers(self):
        self.assertIn("Persistent=true", (ROOT / "deploy/systemd/cvwrite3-backup.timer").read_text())
        self.assertIn("02:30:00", (ROOT / "deploy/systemd/cvwrite3-backup.timer").read_text())
        self.assertIn("*:*:00", (ROOT / "deploy/systemd/cvwrite3-uptime.timer").read_text())
        self.assertIn("MaxRetentionSec=90day", (ROOT / "deploy/systemd/journald@cvwrite3.conf").read_text())

    def test_nginx(self):
        n = (ROOT / "deploy/nginx/cvwrite3.conf").read_text()
        self.assertIn("proxy_set_header X-Forwarded-For", n)   # /healthz tells proxied calls apart by this
        self.assertIn("location = /healthz { return 404; }", n)
        self.assertIn("$from_cloudflare = 0", n)
        self.assertIn("proxy_pass http://127.0.0.1:8000", n)
        self.assertIn("127.0.0.1 --port 8000", (ROOT / "deploy/systemd/cvwrite3-app.service").read_text())

    def test_one_address_for_the_app(self):
        """The app takes POSTs from one origin: nginx serves the app there and redirects the first address to it."""
        n = (ROOT / "deploy/nginx/cvwrite3.conf").read_text()
        host = re.search(r"^CVWRITE_APP_ORIGIN=https://(\S+)$", (ROOT / "env.example").read_text(), re.M).group(1)
        self.assertIn(f"server_name {host};", n)
        self.assertIn(f"ssl_certificate     /etc/ssl/cloudflare/{host}.pem;", n)
        self.assertIn(f"return 301 https://{host}$request_uri;", n)
        self.assertIn(f"https://{host}/generate", (ROOT / "deploy/smoke.sh").read_text())

    def test_every_setting_the_code_reads_is_in_the_template(self):
        names = set()
        for f in list((ROOT / "app").glob("*.py")) + list((ROOT / "render").glob("*.py")):
            names |= set(re.findall(r'["\'](CVWRITE_[A-Z_]+|ANTHROPIC_API_KEY)["\']', f.read_text()))
        dev_only = {"CVWRITE_CLAUDE", "CVWRITE_FONTS", "CVWRITE_HEALTHZ_URL"}
        template = (ROOT / "env.example").read_text()
        for n in sorted(names - dev_only):
            self.assertIn(f"\n{n}=", template, n)

    def test_template_holds_no_values_for_secrets(self):
        for line in (ROOT / "env.example").read_text().splitlines():
            if re.match(r"^(CVWRITE_SECRET_KEY|ANTHROPIC_API_KEY|CVWRITE_BACKUP_SECRET|CVWRITE_BACKUP_KEY_ID|CVWRITE_SMTP_PASSWORD)=", line):
                self.assertTrue(line.endswith("="), line)


if __name__ == "__main__":
    unittest.main()
