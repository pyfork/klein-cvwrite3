<!-- senior-lead-Sonnet5.5-agent, 2026-10-31. Feature brief from the template, drafted from the owner's request (audit findings 1 and 2; Addendum 19 of brief.md); the Shape drafted on the same branch.
     senior-lead-Sonnet5.5-agent, 2026-11-01: revised after the owner's design answers in chat (a failed-tries lockout was dropped for a link that only an inbox owner holds; per-IP caps left as they are). -->
# Brief: sign-in codes

## Who it's for
Anyone who signs in to Better Jobs with the emailed 6-digit code, and the owner, who must be able to trust that only the email's owner gets in.

## The problem
Three flaws in `app/signin.py`, which is ACCESS in the risk map. All three work with only a victim's email address, which is not secret:
1. **A stranger kills your code.** Asking for a new code retires the old one. Addendum 19 of `brief.md` (merged 2026-10-30) settles the new rule; the code does not follow it yet.
2. **A stranger burns your tries.** They type wrong codes on your email until your live code has used its 5 tries. They can repeat this on every new code, so you cannot sign in.
3. **A stranger blocks your asks.** Three asks for your email in 15 minutes and your own ask is refused.

A plain failed-tries lockout would guard against guessing but would make flaws 2 and 3 worse, because it locks the real owner out too.

## End goal
Checked by tests that run on a throwaway database:
1. Asking for a new code cuts each older unused code of that email to 5 minutes left and never lengthens one. Any live code of the email signs in (Addendum 19).
2. **Ask caps, one rolling hour per email.** The web accepts up to 5 codes asked for. Ten in all are allowed, and asks 6 to 10 come only through a link. Link asks count toward the 10 per email and the daily 300, not toward the per-IP cap.
3. **The main page suspends at the 5th ask.** From then until the count drops below 5, the main sign-in page refuses both asking and typing for that email, with one plain message that is the same for every email: "Too many requests. Try again later." It does not mention the link.
4. **Every sign-in email carries a link** that works only for that email, for 1 hour. It opens a page with a "Send my OTP" button and the box to type the code. A stranger without the link cannot ask or type there. Opening the link sends nothing; only the button does.
5. **The inbox owner can always sign in.** With a script burning every try on the main page, a test shows the owner still signs in through the link, and a stranger gets nothing from the link page.
6. Replies never show whether an email is on the list. No email address and no link token goes into a log.
7. Unchanged: a code is 6 digits, lasts 10 minutes and allows 5 tries; the daily cap of 300 codes; the per-IP cap on web asks (10 an hour).

## Out of scope
- Longer codes (8 digits): safe because a stranger gets at most 5 asks × 5 tries = 25 guesses an hour, 600 a day, 0.06% a day at 6 digits (arithmetic on the caps above); revisit when the per-email ask cap is raised.
- Per-IP cap on web asks (10 an hour, hard on shared networks): safe because it is today's behaviour, not added here, and the owner chose to leave it; revisit when a real user reports being blocked on a shared network.
- The global 300-a-day cap letting one source block every sign-in [lean]: safe because it is the ceiling on what the mail account can be made to send (Addendum 5); revisit when a day's cap is hit by one source.
- A link that signs you in directly [lean]: safe because the owner chose a link that only lets you ask for a code, so a leaked link alone gets a stranger nothing; revisit when users report the extra step as a reason they do not finish signing in.
- Passkeys [lean]: safe because the link closes both lockouts without a new dependency; revisit when a user reports sign-in failing even with the link.
- Alerts when someone floods an email [lean]: safe because the inbox owner sees the flood in their mail; revisit when the first flood is reported.
- The CSRF token being the same for a user's whole session [lean]: safe because it is the signed-in forms, not sign-in; revisit when a feature adds or changes a form.
- The temp directory in `app/pipeline.py` that is never removed [lean]: safe because it is not sign-in; revisit when a render fails on a full `/tmp` or on a move between disks.

## Limits it must respect
- `brief.md` Addendum 5 (emailed code, codes and tokens stored hashed, no email in a log, every email gets a code) and Addendum 19. This feature replaces Addendum 5's "3 codes per email per 15 minutes"; the owner writes that addendum first.
- `specs/adr/project-rules.md`: Postgres, plain SQL, no new dependency.
- `app/signin.py` is ACCESS in `docs-public/guard-data/risk-map.txt`: every slice is risky, needs a TECH REVIEW and a tested undo on a copy that is not live, and the owner merges after the explain-back.
- The link and "try again later" pages are screens: the designer takes the slice that adds them. Plain English, reading level A2 to B1 (copy rules).
- The link page is `private, no-store` (Addendum 6) and sends no referrer. The sign-in email stays plain text. Link domain matches the From domain.
- No new table or column if the link can be derived from the code row, the email and the app secret (Open question 1).
- Privacy notice: collects nothing new, but the email text changes (Open question 4).

## Anything to match
The open PR for the code half, `sign-in-old-codes` (#105), is a starting point for slice 1, not an approved plan. None else.

## Rough slice list
Not riskiest first: slice 1 is the finished code of #105 and the others count rows it defines. Slice 2 comes before 3 so the escape exists before anything is suspended.
1. **A new code cuts older codes to 5 minutes** (ACCESS): any live code signs in, wrong guesses count against every live code.
2. **The link and its page** (ACCESS, screens): the link in every email, the "Send my OTP" page and its code box, the email wording. Subject to today's ask cap until slice 3.
3. **The ask caps and the suspension** (ACCESS): 5 web and 10 in all per rolling hour, the main page suspended from the 5th ask, one plain message, a lock on the email so two fast asks cannot pass the cap.

## Open questions
1. Can the link be derived from the code row, the email and the app secret, with nothing stored? If not, there is a column and the slice is DATA as well as ACCESS. Slice 2's plan answers it with a test.
2. Can a link be used for more than one ask in its hour (asks 6 to 10), or one ask each? Lean: reusable up to the cap, since the cap is the limit.
3. Does Addendum 19's "a wrong guess counts against every live code" stay now that the link rescues a burned code? Lean: stay; it is the owner's decision.
4. Does the privacy notice need a line for the link in the email? Slice 2's plan checks the notice.
5. Does the link domain match the From domain (`puascari.com`)? Slice 2's plan checks.

## Shape

### Entities and invariants
No entity is added, so there is nothing to add to `specs/architecture.md` (the file does not exist yet). The link is derived, not stored (Open question 1).

| Entity | Invariants (what must always be true) |
|---|---|
| `login_codes` (keyed by a hash of the email) | Holds only HMACs. One row per code asked for. An unused row's `expires_at` only moves earlier. The count of an email's rows in the last rolling hour is the one count that decides open (0 to 4), suspended (5 to 9) or closed (10). |
| The link (derived) | Tied to one email: a token made for one email never works for another. Valid 1 hour. Opening it sends nothing; only its button asks for a code. Never written to a log. |
| `sessions` | Unchanged. A session starts only after a code matches. |

### API sketch
- Request-a-code (`app/main.py:165`) and check-a-code (`app/main.py:190`): any visitor. Both refuse an email with 5 or more rows in the last hour, with the same message for every email. Slice 3.
- Link page: GET shows the button only; POST "Send my OTP" asks a code for the token's email (asks 6 to 10); POST on the code box checks the code. The token in the URL is the credential. Slice 2.
- No other route changes.

### States
An email, by its rows in the last rolling hour: open (0 to 4), suspended (5 to 9, link only), closed (10, until the oldest row is an hour old). A code: live, then used, expired or spent (5 tries).

### Expected load
| What | Number | Where the number came from | Budget it touches |
|---|---|---|---|
| Guesses a stranger gets per email | 25 an hour, 600 a day | 5 web asks × 5 tries (`MAX_TRIES`), from this brief's caps | Guess budget |
| Same, today | 60 an hour, 1,440 a day | 12 asks an hour (`PER_EMAIL` 3 per 15 min) × 5 tries | Guess budget |
| Chance a stranger gets in, per day | 0.06% | 600 ÷ 1,000,000, arithmetic | Guess budget |
| Emails to one inbox | at most 10 an hour | the caps above | Mail ceiling of 300 codes a day (`PER_DAY`) |
| One extra count per try | one indexed query | `login_codes_email (email_hash, created_at)` exists | none new |

### Trust boundaries crossed
Browser to server on both sign-in routes and the new link page: the email and typed code come from anyone. The link token is the new credential and travels in a URL, so it can reach logs and the Referer header. A stranger and the inbox owner differ only in who holds the link; that is the boundary this feature builds. Server to the mail provider: unchanged.

### Key choices
| The choice | The option not taken | Why |
|---|---|---|
| A link that lets you ask a code | A link that signs you in | A leaked link alone gets a stranger nothing; the owner's choice |
| The main page suspends at 5 asks | Leave typing open | Otherwise a stranger burns the 5th code's tries |
| The link in every email | The link only in the 5th | Otherwise codes 1 to 4 can be burned before the link exists |
| One rolling-hour row count drives all states | A new counter or column | No migration, and web and link asks cannot drift apart |
| Keep 6 digits | 8 digits | The caps already bound guesses to 600 a day |
| Keep the per-IP cap as is | Raise or drop it | Not this feature's problem; trigger written above |
| Slice 2 (link) before slice 3 (suspension) | The other order | Never ship a suspension with no way in |

### Risky slices
| Slice | Class (DATA, ACCESS or SHARED) | The assumption it tests | What changes if it is wrong |
|---|---|---|---|
| 1. A new code cuts older codes | ACCESS | Any live code signing in adds no guesses | If wrong, slice 3's caps are the only bound |
| 2. The link and its page | ACCESS (DATA if a column is needed) | The link can be derived and stays out of logs and referrers | If wrong, add a column and a log scrub; or drop the link |
| 3. The ask caps and the suspension | ACCESS | The one row count is enough, and a lock stops the race | If wrong, a stranger gets a 6th web ask; add a lock or a unique key |

### Shared standards still missing
A signed-out page that changes state needs its own protection against forged requests. The link page's token in the URL serves; slice 2's plan confirms.
