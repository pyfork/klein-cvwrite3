#!/usr/bin/env bash
# Read-only checks after a deploy on sk24. Run as: sudo bash /sites/cvwrite3/app/deploy/smoke.sh
# It changes nothing. Exit 0 = every check passed.
set -u
fail=0
ok()  { printf 'PASS  %s\n' "$1"; }
bad() { printf 'FAIL  %s\n' "$1"; fail=1; }

for u in cvwrite3-app cvwrite3-worker; do
  systemctl is-active --quiet "$u" && ok "$u running" || bad "$u not running"
done
for t in cvwrite3-uptime.timer cvwrite3-backup.timer; do
  systemctl is-active --quiet "$t" && ok "$t armed" || bad "$t not armed"
done

h=$(curl -s -m 5 http://127.0.0.1:8000/healthz)
echo "$h" | grep -q '"ok":true' && ok "/healthz: $h" || bad "/healthz: ${h:-no answer}"
code=$(curl -s -o /dev/null -w '%{http_code}' -m 5 -H 'X-Forwarded-For: 1.2.3.4' http://127.0.0.1:8000/healthz)
[ "$code" = 404 ] && ok "/healthz refuses proxied calls" || bad "/healthz answered a proxied call ($code)"

code=$(curl -s -o /dev/null -w '%{http_code}' -m 10 https://betterjobs.puascari.com/generate)
case "$code" in 302|303|401|403) ok "public URL asks for sign-in first ($code)";; *) bad "public URL answered $code without sign-in";; esac
code=$(curl -s -o /dev/null -w '%{http_code}' -m 10 https://cvwrite3.puascari.com/generate)
[ "$code" = 301 ] && ok "the first address redirects ($code)" || bad "the first address answered $code, not a redirect"

stat -c '%a %U' /sites/cvwrite3/.env | grep -q '^600 cvwrite3$' && ok ".env is 0600 cvwrite3" || bad ".env permissions"
[ -z "$(find /sites/cvwrite3/prompts -type f ! -perm 640 2>/dev/null)" ] && ok "prompts are 0640" || bad "prompts permissions"
[ -f /sites/cvwrite3/config/qr/duitnow.png ] && ok "QR image in place" || bad "QR image missing"

journalctl --namespace=cvwrite3 -n 1 --no-pager >/dev/null 2>&1 && ok "journal namespace cvwrite3" || bad "journal namespace cvwrite3"
nginx -t >/dev/null 2>&1 && ok "nginx config" || bad "nginx config"

# One array item per .env line: CVWRITE_CHROME_FLAGS holds spaces, and an unquoted $(...) split it into words.
mapfile -t chrome_env < <(grep -E '^CVWRITE_CHROME(_FLAGS)?=' /sites/cvwrite3/.env)
out=$(sudo -u cvwrite3 env "${chrome_env[@]}" HOME=/sites/cvwrite3/data/chrome-home \
  /sites/cvwrite3/venv/bin/python /sites/cvwrite3/app/checks/render_check.py /tmp/cvw3-smoke 2>&1)
echo "$out" | grep -E '^FINGERPRINT'
echo "$out" | grep -q 'RESULT: PASS' && ok "render check (compare the fingerprint with the Mac's)" || bad "render check"
rm -rf /tmp/cvw3-smoke

[ "$fail" = 0 ] && echo "SMOKE: PASS" || echo "SMOKE: FAIL"
exit "$fail"
