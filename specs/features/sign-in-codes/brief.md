<!-- senior-lead-Sonnet5.5-agent, 2026-10-31. Feature brief from the template, drafted from the owner's request (findings 1 and 2 of the 2026-10-31 audit; Addendum 19 of brief.md); the Shape drafted on the same branch. -->
# Brief: sign-in codes

## Who it's for
Anyone who signs in to Better Jobs with the emailed 6-digit code, and the owner, who must be able to trust that only the email's owner gets in.

## The problem
Two flaws in `app/signin.py`, which is ACCESS in the risk map:
1. A stranger who asks for a code for your email kills the code you were about to type, because a new code retires the old one. Addendum 19 of `brief.md` (merged 2026-10-30) settles the new rule; the code does not follow it yet.
2. The guess budget is loose. A code allows 5 tries and an email may ask for 3 codes per 15 minutes: 12 codes an hour, 60 guesses an hour, about 1,400 a day, against 1,000,000 possible codes on one email.

## End goal
Checked by tests that run on a throwaway database:
1. Asking for a new code cuts each older unused code of that email to 5 minutes left, and never lengthens a code that has less. The old code is not killed (Addendum 19).
2. Any live code of the email signs in. A wrong guess counts against every live code of that email, so extra codes do not add guesses.
3. Once an email has 10 failed tries on codes asked for in the last hour, a further try is refused whether or not the code is right, until those codes are an hour old. [lean: the number and the window are the Lead's proposal, see Open questions]
4. The reply never shows whether an email is on the list, and no email address goes into a log (both as in Addendum 5).
5. The unchanged limits still hold: a code lasts 10 minutes and allows 5 tries; 3 codes per email per 15 minutes, 10 per IP an hour, 300 a day.

## Out of scope
- The 300-a-day cap being global, so one bot can block every sign-in for a day [lean]: safe because it is the ceiling on what the mail account can be made to send (Addendum 5) and changing it trades mail cost against availability, which is the owner's call; revisit when a day's cap is hit by one source.
- Check-then-insert race in `send_code` (take an advisory lock on the email hash) [lean]: safe because the worst case is one extra code past the 3-per-15-minutes limit, and the guess limit in End goal 3 does not depend on it; revisit when a log shows more than 3 codes for one email in 15 minutes.
- The CSRF token being the same for a user's whole session [lean]: safe because it is a different part of the app (forms, not sign-in codes); revisit when a feature adds or changes a form.
- The temp directory in `app/pipeline.py` that is never removed [lean]: safe because it is not sign-in; revisit when a render fails on a full `/tmp` or on a move between disks.
- Changing the code length, the 10-minute life, the 5 tries, or the 30-day session: safe because Addendum 19 says they are unchanged; revisit only by a new addendum.

## Limits it must respect
- `brief.md` Addendum 5 (sign-in by emailed code, codes and tokens stored hashed, no email in a log, every email gets a code) and Addendum 19 (the 5-minute rule).
- Project rules: `specs/adr/project-rules.md` (Postgres, plain SQL, no new dependency).
- `app/signin.py` is ACCESS in `docs-public/guard-data/risk-map.txt`: every slice here is risky, needs a TECH REVIEW and a tested undo, and the owner merges after the explain-back.
- No new table or column is wanted: the guess limit should read what `login_codes` already holds.
- Privacy notice: collects nothing new, so no notice change.

## Anything to match
The open PR for the code half, `sign-in-old-codes` (#105), is a starting point for slice 1, not an approved plan. None else.

## Rough slice list
1. **A new code cuts older codes to 5 minutes** (ACCESS, riskiest: it changes who can sign in and when, so a wrong idea fails first). It also makes any live code sign in and spreads wrong guesses over every live code. It gives users something: the stranger can no longer kill your code.
2. **The failed-tries limit** (ACCESS): refuse once an email has 10 failed tries in the last hour. It waits for slice 1 because it counts across live codes, which slice 1 defines.

## Open questions
1. Should 10 failed tries an hour per email be the limit? The lean is yes: at 240 guesses a day a stranger has about a 0.024% chance a day against one email (240 in 1,000,000), against about 0.14% now. The cost: a stranger can lock your email out of sign-in for up to an hour by burning 10 wrong tries. That is the same shape of harm Addendum 19 removes for codes. Other options: count per email and per IP together (an attacker with many IPs defeats it), or a lower number with the same cost.
2. Is a lock-out of up to an hour acceptable, or must the real owner of an email always get in? If always, the limit in End goal 3 cannot be a refusal on the email alone.

## Shape

### Entities and invariants
No entity is added, so there is nothing to add to `specs/architecture.md` (the file does not exist yet).

| Entity | Invariants (what must always be true) |
|---|---|
| `login_codes` (keyed by a hash of the email) | Holds only HMACs, never the code or the email. One row per code asked for. `expires_at` only ever moves earlier for an unused code, never later, once the row exists. A row used or past `expires_at` never signs anyone in. `attempts` counts every try made while the row was live. Rows are purged after a day. |
| `sessions` | Unchanged. A session starts only after a code matches. |

### API sketch
- `POST` request-a-code (`send_code`, `app/main.py:165`): any visitor. Mails a code or refuses when the email, IP or daily limit is hit; the reply is the same for every email. Writes one `login_codes` row and cuts the email's older unused rows to 5 minutes left.
- `POST` check-a-code (`check_code`, `app/main.py:190`): any visitor. True once for a live code that matches; every try counts against every live code of the email. Slice 2 adds: refused while the email has 10 or more failed tries in the last hour.
- No route is added or changed. The change is inside `app/signin.py`.

### States
A code: `live` (unused, not expired, under 5 tries) → `used` (matched), `expired` (time ran out), or `spent` (5 tries). A new code request moves each older live code's expiry to the earlier of its own and 5 minutes from now. Nothing moves a code later.

### Expected load
| What | Number | Where the number came from | Budget it touches |
|---|---|---|---|
| Guesses against one email, now | about 1,440 a day | 3 codes per 15 min = 12 an hour = 288 a day, × 5 tries each = 1,440; constants `PER_EMAIL` and `MAX_TRIES` in `app/signin.py` | Guess budget (this feature) |
| Guesses against one email, after slice 2 | 240 a day | 10 an hour × 24 (the proposed limit) | Guess budget |
| Sign-in requests | not measured | no figure in the brief; the daily cap is 300 codes (`PER_DAY`) | 300 codes a day |
| Extra read for the failed-tries count | one indexed query per try | `login_codes_email (email_hash, created_at)` already exists | none new |

### Trust boundaries crossed
Browser to server on both sign-in routes; the email address and the typed code come from anyone and are not trusted. Server to the mail provider (SES) for the code; unchanged. One user's data to another's: a stranger's request for a code for your email touches your `login_codes` rows. That is the boundary Addendum 19 and slice 2 are about.

### Key choices
| The choice | The option not taken | Why |
|---|---|---|
| Cut older codes to 5 minutes, never lengthen | Kill the older code (today) | Owner decision, Addendum 19: a stranger could otherwise kill the code you were about to type |
| A wrong guess counts against every live code | Count only the newest code | Otherwise each extra code adds 5 guesses, and the 3-per-15-minutes limit stops bounding them |
| The failed-tries count reads `login_codes.attempts` of the email's rows from the last hour | A new table or column | No migration, so no DATA risk; a code lives 10 minutes, so its tries fall inside the hour its row was created in |
| Slice 1 and slice 2 separate | One slice | Each has one outcome and one assumption; slice 2's count depends on slice 1's rule |

### Risky slices
| Slice | Class (DATA, ACCESS or SHARED) | The assumption it tests | What changes if it is wrong |
|---|---|---|---|
| 1. A new code cuts older codes | ACCESS | Any live code signing in does not let a guesser use two codes' tries for one guess | If wrong, each live code adds guesses again: slice 2's limit becomes the only bound |
| 2. The failed-tries limit | ACCESS | A refusal on the email alone is acceptable (Open question 2) | If wrong, the real owner can be locked out by a stranger; the limit moves to email plus IP, or is dropped |

### Shared standards still missing
None. The refusal reply reuses the existing wrong-code reply, so the page does not show why it refused.
