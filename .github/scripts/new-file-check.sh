#!/usr/bin/env bash
# senior-lead-Opus5.5-agent, 2026-10-28 (senior D23)
# The risk map names files, so a new file is routine unless a line names it.
# This fails a PR that adds a file whose path looks risky (money, sign-in,
# legal text, deploy, secrets) and matches no line of main's risk map: add the
# path to the map (owner-approved) or rename it. It reads only the PR's list
# of added files from the API; no PR code runs.
#   new-file-check.sh <risk-map on main>     (GH_REPO, PR_NUMBER, GH_TOKEN set)
set -euo pipefail
map="$1"
# A word starts a path part, or follows _ - or . (so "signin" counts, "design" doesn't).
risky='(^|[/_.-])(pay|credit|ledger|refund|order|invoice|price|auth|sign|login|session|account|admin|access|consent|notice|terms|privacy|pdpa|deploy|backup|restore|migrat|secret|token|cookie|csrf)'
# Tests, locked checks, plans and specs are never code that runs in production.
skip='^(tests|acceptance|plans|specs)/'

# Each map glob as an anchored regex: ** spans folders, * stays in one.
regexes="$(grep -vE '^[[:space:]]*(#|$)' "$map" | awk '{print $2}' |
  sed -e 's/[.^$+(){}|]/\\&/g' -e 's/\*\*/\x01/g' -e 's/\*/[^\/]*/g' -e 's/\x01/.*/g' -e 's/^/^/' -e 's/$/$/')"
[ -n "$regexes" ] || { echo "NO RISK MAP: docs-public/guard-data/risk-map.txt on main has no lines"; exit 1; }

added="$(gh api "repos/$GH_REPO/pulls/$PR_NUMBER/files" --paginate --jq '.[] | select(.status == "added" or .status == "renamed") | .filename')"
fail=0
while IFS= read -r f; do
  [ -n "$f" ] || continue
  if printf '%s\n' "$f" | grep -qE "$skip"; then continue; fi
  if printf '%s\n' "$f" | grep -qE -f <(printf '%s\n' "$regexes"); then continue; fi
  if printf '%s\n' "$f" | tr '[:upper:]' '[:lower:]' | grep -qE "$risky"; then
    echo "UNMAPPED RISKY FILE: $f is new, looks risky by its name, and matches no line of the risk map. Add it to docs-public/guard-data/risk-map.txt and .github/CODEOWNERS (the owner merges that), or rename it if it isn't risky."
    fail=1
  fi
done <<< "$added"
[ "$fail" = 0 ] && echo "OK: no new file looks risky outside the risk map"
exit "$fail"
