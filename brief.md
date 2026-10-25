<!-- senior-lead-Opus5.5-agent, 2026-10-21 -->
# klein-cvwrite3 brief

## Goal
Serve the cvwrite skill as a web app at **cvwrite3.puascari.com** for whitelisted users, and test demand with real payments.

- One ad in, one CV out (2 pages, MD + PDF, checked).
- The user can edit the CV text and have it re-rendered.
- Paid credits: 2 free, then RM10 = 5 or RM30 = 20, paid by DuitNow QR and credited by the owner.
- PDPA (Malaysia): clear notice and consent at signup, and visible data controls on the account page.

This is a quick build to test demand. It is not a full product: no ad library, no search, no version history.

## Success thresholds (first 30 users)
- At least 60% use both free generations.
- At least 20% of those buy.
- At least 25% of buyers buy a second time.

Below all three: stop. In between: change the price or the product.

## Stack and shape
- **Python:** FastAPI and plain HTML forms. The skill's scripts are reused with three changes:
  - the Chrome path comes from an env var (Chromium on Linux);
  - fonts are self-hosted, so renders don't depend on Google Fonts;
  - contact values come from the user's profile row.
- **Postgres:** its own database and a non-superuser role. PDFs are stored on disk under the app's directory.
- **Hosting:** sk24, behind Cloudflare (a proxied DNS record and an origin certificate), with nginx and a systemd unit. Every box change needs the owner's OK.
- **Claude:**
  - plain Messages API calls with **no tools**;
  - the owner's API key in `.env` (0600);
  - Opus 5.5 (`claude-opus-5-5`) to read the ad and write the CV;
  - Haiku 5.5 (`claude-haiku-5-5`) to re-format edits.

## User flow
1. **Sign in:**
   - Cloudflare Access email PIN;
   - the app checks the `Cf-Access-Jwt-Assertion` header (team keys, AUD tag), then looks the email up in `allowed_users`;
   - an email that isn't on the list gets a request-access page, which writes to `access_requests`.
2. **Privacy notice and consent:** these come before anything is uploaded. See PDPA below.
3. **Profile:**
   - one master CV (`.md`, `.txt` or `.pdf`);
   - contact fields;
   - standing edits.
4. **Generate:**
   - The user pastes the ad and presses Generate. There is no review pause.
   - Progress is shown while each step runs: call A, call B, render, check.
   - **Call A (ad read):**
     - structured output;
     - the ad is sent as delimited data, never as instructions;
     - every quote returned must appear word for word in the ad, and a problem whose quote doesn't is dropped.
   - **Call B (write):**
     - uses the masked master CV, with `{{NAME}}` and `{{CONTACT}}` placeholders;
     - style 1 (Archivo);
     - contact values are merged in only after Claude has written the CV.
   - **Check:** exactly 2 pages, A4, and the top 3 keywords present.
   - **Internal retry:** if the first draft fails the check, Opus gets one retry and is told which check failed. If the retry also fails, **no credit is used**, and the user sees "we couldn't produce a passing CV for this ad".
5. **Result:**
   - MD and PDF downloads;
   - the ad read: the problem the CV leads with, the keywords and where each appears, gaps, red flags;
   - the check result and the balance.
6. **Edit and re-render:**
   - **The edit box:**
     - prefilled with the CV as plain text: CAPS headings, "- " bullets, no `#` or `**`;
     - a "Download .txt" button;
     - no file upload.
   - **Haiku 5.5 only re-formats the text and never rewrites it.**
     - A check in code: at least ~97% of the user's words must come back unchanged and in order.
     - If the check fails, the app keeps the user's text and shows "couldn't format, check your headings".
   - **Contact values are masked** before the Haiku call. Changes to the header in the box are ignored, and the box says "change contact details in Profile".
   - **What a re-render checks:**
     - The 2-page check blocks: "your edit runs to 3 pages, trim and resubmit". A blocked attempt counts toward the limit.
     - The keyword check only warns.
   - **Limit:** up to 3 free re-renders per CV. After that, the user starts a new generation for 1 credit.
   - **Re-analysis** (a new Opus read of the ad and a new write) costs 1 credit.
   - **No AI regeneration** from feedback.
7. **"Not good" feedback:**
   - reasons: wrong main problem, wrong keywords, too long, wording, other;
   - **a signal only**: it feeds the admin funnel and nothing is rewritten.

## Credits and payment
- **`credit_ledger`:**
  - insert-only;
  - +2 on approval;
  - +5 or +20 when the owner approves a payment;
  - −1 when a CV passes the check.
- **Validity:**
  - each grant row has its own `expires_at`, 12 months from the grant (the free 2 included);
  - spending uses the oldest unexpired credits first;
  - the expiry date shows next to the balance, on the pay screen and in the terms.
- **Balance and paywall:**
  - the balance shows on every screen;
  - at 0, the next generation is blocked and the paywall shows the two packs.
- **Paying:**
  - the user picks a pack, and the app creates an `orders` row: a unique reference (e.g. `CV3-7K2Q`), the amount, status `pending`;
  - the pay screen shows the DuitNow QR image (a config file outside git), the exact amount and "put this reference in the transfer note", then an "I've paid" button.
- **Owner approval:**
  - the admin page lists orders by status;
  - the owner checks the reference and amount in the bank app, then approves (which writes the ledger row linked to the order) or rejects with a reason the user sees;
  - an order can be approved once only;
  - **credits are added only after the money is seen in the bank, never because the user clicked "I've paid"**;
  - agents never approve orders or touch the ledger.
- **What isn't sent or stored:** no emails, no receipt uploads, no payer names. The user sees "pending" until the order is approved.
- **Refunds:** unused credits are refunded by bank transfer on request; used credits are not refunded.

## PDPA (Malaysia)
**Not legal advice.** Check the current Act, the 2024 amendment and the Commissioner's guidelines before go-live.

### Notice (shown at signup, before any upload)
- **Languages:** Malay and English.
- **What it covers:**
  - what is collected: email, master CV, contact details, ads, generated CVs, payment references, problem reports;
  - why it is collected;
  - the data user (the owner's business; name to be supplied);
  - recipients: Anthropic (AI processing, outside Malaysia) and Cloudflare (sign-in and proxy);
  - the server's country;
  - retention;
  - how to make a request, and the response time;
  - that giving data is voluntary, and that the service can't run without it.
- **Anthropic API terms:** confirm the training and retention terms, and whether zero retention is available, and state them in the notice.

### Versioning (API-style)
- **Version ids are `MAJOR.MINOR`, starting at `v1.0`.**
  - **Major:** what is collected, why, who receives it, where it goes, or how long it is kept changes. The user is asked to consent again at their next sign-in, before any action.
  - **Minor:** wording, a typo or the contact email changes. No new consent is asked for. The account page shows "notice updated" with a link to what changed.
- **Published versions are immutable.**
  - Each version is stored as `notices/vX.Y.en.md` and `notices/vX.Y.ms.md`.
  - A test pins a hash of each published file and fails if one is edited.
- **URLs:**
  - `/privacy/vX.Y` always serves that exact text;
  - `/privacy` serves the latest version;
  - `/privacy/changes` is the changelog: each version, its date, what changed and why.

### Consent
- One **unticked** box: "I've read the privacy notice and agree".
- A **separate explicit line** for sensitive data (race, religion, health, an IC number).
- A warning at master-CV upload: don't include your IC number, religion or health details.
- **IC-number flag:**
  - the app detects anything that looks like a Malaysian IC number (`YYMMDD-PB-###G`, with or without dashes) in the master CV or in an edit;
  - the user is asked to remove it **before anything is sent to Claude**.
- **The `consents` table:** email, notice version, a hash of the text shown, language, sensitive-data line yes/no, timestamp.

### Account page (always visible)
- **Consent status:**
  - "You consented to **Privacy Notice vX.Y** on **{date}** ({language}). [View vX.Y]", plus the sensitive-data line;
  - if a newer minor version exists, "The current notice is vX.Z. [What changed]";
  - older consents are listed below, newest first.
- **Download my data:** a zip of the profile, runs, CVs (MD/TXT/PDF), the credit ledger, consent records and problem reports. This covers access and portability.
- **Correct:** profile edits take effect at once, and the page says so.
- **Withdraw consent and delete my account:**
  - deletes the profile, runs, files, edit history and problem reports;
  - keeps only the ledger and order rows, with no CV content, for accounting;
  - the screen says this, and that the delete is final, before the user confirms;
  - unused credits are refundable on request;
  - this is the user's own action only: agents never run a delete for a user.
- **Make a request:** a contact email, and a promise to respond **within 21 days**.

### Behind the scenes
- **Breach runbook:**
  - notify the Commissioner within 72 hours of finding a breach;
  - notify affected users promptly when they could be significantly harmed;
  - keep a breach log.
- **Cross-border transfer:** check the 2024 amendment's rules and guideline, and state them in the notice.
- **Logs:** no CV text, ad text, contact values or report text, ever.
- **Owner checks:**
  - whether the service falls under a registration class;
  - the DPO threshold;
  - the data user's name and the request email;
  - the BM text (the agent drafts it; a native speaker reviews it).

## Report a problem (user experience)
- **Where:** a link in the footer of every signed-in page, and next to the result, the pay screen and any error.
- **Form:**
  - category: something broke / I paid but have no credits / the CV output is wrong / a privacy or data request / other;
  - free text, with "don't paste your CV or IC number here";
  - attached automatically: the request id, run or order id, page, time and app version. Never any CV, ad or contact text.
- **The `problem_reports` table:**
  - email, category, text, linked ids;
  - status (`open` / `answered` / `closed`);
  - the owner's reply;
  - timestamps.
- **Admin page:**
  - open reports, oldest first;
  - privacy requests show a 21-day countdown;
  - payment reports link to their order.
- **The user** sees their reports, statuses and replies on the account page. No email is sent.
- **Signed-out problems:** the request-access and privacy pages show the contact email.
- **Retention:** reports are deleted with the account; closed reports are deleted after 12 months.

## Observability (our own)
Data stays in Postgres and journald on sk24. **Nothing goes to a third-party service.** Field and step names follow OpenTelemetry conventions, so an exporter can be added later.

### What is recorded
None of it contains CV, ad or contact text.
- **Request log:** one JSON line per request in journald: request id, route, status, duration, hashed user id, app version.
- **`run_steps`:**
  - one row per step of each generation and re-render;
  - steps: queue wait, call A, call B, internal retry, render, check, Haiku re-format;
  - each row: start, duration, outcome, model, tokens, error class.
- **Claude API health:** latency, 429 and 529 counts, and retries, per model.
- **`errors`:** error class, route, run id, and a scrubbed traceback.

### Degraded
Starting ceilings, to be tuned after 2 weeks of real data:
- generation p95 over 120 s;
- re-render p95 over 30 s;
- render queue wait over 20 s;
- more than 5% of generations failing in an hour.

A breach writes a `degraded_events` row: start, end, the step to blame, and the p95 against the baseline.

### Uptime (minimal, admin page only)
- A systemd timer calls `/healthz` every minute and writes an `uptime_checks` row.
  - `/healthz` checks the database, disk space, that Chromium is present, and queue depth.
- **Missing minutes count as down,** so time the box itself was down shows up afterwards as a gap.
- **Admin health panel:**
  - up or down now, and the last check;
  - uptime % for 24 hours, 7 days and 30 days;
  - recent incidents;
  - p50 and p95 per step;
  - error rate, queue depth and open degraded events.
- **Users** see a banner while an event is degraded: "Generating is slower than usual right now".
- **No push alerts for now.** The admin page also shows the $20 spend warning, orders waiting more than 2 hours, and privacy requests from day 14 on.
  - Revisit push alerts at wave 2, or once orders are waiting more than 12 hours.

### Retention
- Request logs and step rows: 90 days.
- Daily rollups: 12 months.
- Degraded events, uptime incidents and errors: 12 months.

## Caps and spend
- **Per user:** an anti-abuse cap of 20 generations a day, paid ones included. Haiku re-renders count toward it.
- **Global:** a monthly stop at $50, with a warning at $20. **It blocks free generations only, never paid ones.**
- **Before every generation:** a balance check and a spend check.
- **`usage`:** one row per Claude call: tokens, cost, model.

## Admin page (owner's email only)
- **Access:**
  - approve requests, which adds the user to `allowed_users` and grants 2 free credits;
  - the wave 2 auto-approve switch, with a cap of 50 users.
- **Orders:** approve or reject.
- **Problem reports** and the **health panel.**
- **Funnel:**
  - requests, approved users, users who used both free generations, buyers, repeat buyers;
  - time from "I've paid" to approval;
  - cost per generation, revenue against Claude spend;
  - re-renders per CV and the share of CVs edited;
  - "not good" reasons, compared with the thresholds.

## Rollout
- **Wave 1:** invited users.
- **Wave 2:** requests are approved automatically, up to 50 users in total.

## Retention
- Runs and PDFs: 30 days.
- The profile: until the user deletes it.
- The ledger and orders: as long as accounting needs, with no CV content.

## Out of scope
- A card or FPX gateway, automatic payment matching, invoices and tax handling.
- Emails of any kind, and push alerts (for now).
- More than one master file per user.
- An ad library, search or version history.
- A review pause, and AI regeneration from feedback.
- Prompt caching or a cheaper model for the write step, until there is real cost data.

## Chunks (riskiest first; each one is a branch and a PR the owner merges)
0. **Repo and brief:** this file.
1. **Runs on Linux:**
   - Chromium and poppler on sk24 (owner's OK);
   - the scripts render the same 2-page PDF with self-hosted fonts embedded;
   - a throwaway check;
   - a pre-push guard that refuses `.env`, `prompts/`, QR files, `CLAUDE*.md` and anything that looks like an IC number.
2. **Signed in:**
   - Access, the JWT check, the whitelist, request access, admin approval, the wave 2 switch;
   - the BM/EN notice screen, the consent boxes, `consents`, versioning and asking again.
3. **Profile, one-shot generate, edit and re-render:**
   - calls A and B, the quote check, render, check, the internal retry;
   - the edit box, the Haiku re-format and word check, contact masking, the limit of 3;
   - the IC-number flag and the upload warning;
   - `run_steps` timings from the first line of code.
4. **Credits:** the ledger with `expires_at`, oldest first, balance and expiry shown, the paywall.
5. **QR payment:** orders, the reference, the pay screen, admin approve and reject, approve once.
6. **Caps, numbers and health:**
   - usage rows, the caps, the admin funnel, "not good" feedback;
   - report a problem;
   - `degraded_events`, `uptime_checks`, the health panel, the banner.
7. **Deploy and pages:**
   - systemd, nginx, the origin certificate, DNS, Postgres, `/healthz` and its timer, log retention;
   - the account-page controls, the BM/EN notice text, the terms page, the breach runbook;
   - a smoke test.

## To check before chunk 3
- Does Haiku 5.5 take an effort setting? Use the model docs, and its default if not.
- Haiku and Opus 5.5 prices: take them from the docs, not from memory.

## Risks to watch
- **Margin on the RM30 pack:** about RM0.90 per generation (an estimate), or about RM1.40 with the retry. Revisit if the real cost is over RM1.20 for a week.
- **Slow manual approval:** revisit if the median wait is over 12 hours, or more than 10 orders arrive a week.
- **A wrong problem #1 with no pause:** revisit adding a pause, or "use problem #2", if "wrong main problem" feedback is over 20%.
- **The account behind the QR:** check that the bank allows business receipts on it.
- **Free generations are a cost:** about RM1.80 per approved user. The global stop limits runaway spend.

## Owner actions (agents can't do these)
- The DuitNow QR image.
- The Cloudflare Access app and team settings, and the DNS record.
- OK for the sk24 changes in chunks 1 and 7.
- The Claude API key, typed into a hidden prompt on the server.
- The PDPA checks above, and the name of the data user and the request email.

## Data rules for this repo
**This repo is public, with no license: the code is all rights reserved.** It can be read, as a portfolio item, but not reused.
- **Prompts stay out of git.**
  - The system prompts for the ad read, the write and the re-format live in a git-ignored `prompts/` folder.
  - They are deployed to sk24 at 0640.
  - Tests use stub prompts.
  - The loader is public; the prompt text is not.
- None of the owner's own CV, contact details, standing edits or QR image goes into the repo, a seed, a fixture or a prompt file. Tests use a made-up master CV and a placeholder QR.
- Secrets are typed into hidden prompts, never in chat, on a command line, or in a file in git.

## Addendum 1 (2026-10-22): owner decisions from the chunk 1 session
Where this addendum and the sections above disagree, the addendum wins.

### Rendering (chunks 1, 3, 7)
- **Chrome:** sk24's existing Chrome is reused through `CVWRITE_CHROME`. Lean flags come from `CVWRITE_CHROME_FLAGS`, plus network-blocking flags (`--proxy-server=127.0.0.1:9 --host-resolver-rules="MAP * ~NOTFOUND"`), so a render can't fetch or leak anything. Never `--single-process` (it gives no PDF).
- **Fonts:** static TrueType cuts only. The render check fails on any Type 3, fallback or unembedded font.
- **Limits:** a 30 s Chrome timeout, Chrome in its own process group (the whole group is killed), one render retry, one Chrome at a time, and `oom_score_adj=1000` on Chrome.
- **Admission:** before each render the worker reads `MemAvailable`; under 500 MB it waits, and the wait counts as queue wait.
- **`run_steps`** also records each render's `memory.peak` and CPU time.

### Jobs and the worker (chunk 3)
- Jobs are Postgres rows, claimed with `FOR UPDATE SKIP LOCKED` by one worker unit. The app only enqueues and shows status.
- **Checkpoints:** call A and call B outputs are saved on the run, so a crash never pays Claude twice.
- **The −1 ledger row** is written in the same transaction that marks the run `passed`, with a unique `run_id`. Downloads are served only for `passed` runs.
- **Worker restart:** on startup, every `running` job goes back to `queued` and resumes from its checkpoint. A deploy's `SIGTERM` lets the current job finish (up to 90 s).
- **Poison jobs:** at most 3 starts per job, within 10 min of the click while not paused; then `failed`, no credit used.
- A delete stops any running job for that user first, so no −1 row can land afterwards.

### Pause (chunks 3 and 6)
- **One `system_pause` row** (`paused_at`, `reason`, `source` auto/owner, `resumed_at`). An open row means paused.
- **Auto-pause:**
  - render: 3 runs fail both render attempts, from at least 2 different users, within 30 min;
  - Claude: 5 calls in a row fail after the SDK's retries, across at least 2 users;
  - test render: fails twice in a row;
  - owner: a "Pause generating" button.
- **Test render:** a made-up fixture is rendered once after every worker start, then hourly, **skipped if a real CV rendered in the last 2 h**, and skipped while `MemAvailable` is under 500 MB.
- **While paused:** Generate is refused before call A (no Claude spend, no credit used); jobs past call B are held; the degraded banner shows; re-render reads "Re-rendering is paused" and doesn't use one of the 3.
- **Resume is manual:** the owner presses "Test render" (PASS/FAIL with the fingerprint), then "Resume". Held jobs finish in arrival order.
- **Ladder, timed from `paused_at`:**
  - 0–4 h: banner, buying open;
  - 4–24 h: "taking longer than usual", **buying closed** (credits already held are safe);
  - 24 h: held jobs expire with "No credit used";
  - over 72 h: the owner may extend credit expiry by the length of the pause (owner's button, never agents).
- **Copy rules:** no ETA; every failure message says the money part; a content failure offers "try again" at most 2 times per ad, then "Report this problem"; during a pause, "something broke" reports show "We already know about this problem".
- The 20-a-day cap counts only runs that reached call A.
- **Deferred, with triggers:** canary and auto-resume (over 2 auto-pauses a month, or a median "paused → owner looked" over 4 h); self-heal steps; split render/Claude breakers; push alerts.

### Process layout on sk24 (chunk 7, each unit needs the owner's OK)
- `cvwrite3.slice`: `MemoryHigh=600M`, `MemoryMax=750M`, `CPUWeight=50`, `CPUQuota=150%`.
- `cvwrite3-app.service`: uvicorn, 1 worker, `MemoryMax=250M`.
- `cvwrite3-worker.service`: `MemoryMax=550M`, `OOMPolicy=continue`, `Restart=always`, `PrivateTmp=yes`, `TimeoutStopSec=90`. Up to 3 jobs at once, one Chrome at a time.
- **Gold standard, before wave 2:** a separate render unit with `IPAddressDeny=any`, its own user and `ProtectSystem=strict`.

### Profile upload (chunk 3)
- **`.docx` is accepted** as well as `.md`, `.txt` and `.pdf` (python-docx, imported only on upload). Not the old `.doc`.
- The upload size and the unzipped size are both capped.
- The user sees a **text preview** of what was read before saving, so content the parser missed (text boxes, tables) is caught.

### Backups (chunk 7)
- The `cvwrite3` database only (`pg_dump`); PDFs are never backed up.
- **Every 2 days at 2:30 AM** (box time). The timer runs nightly but only backs up when the last good copy is over 44 h old, so a failure retries the next night. `Persistent=true`.
- Encrypted on the server before upload (`age`; the private key stays offline with the owner), to cvwrite3's own DO Spaces bucket (Singapore) with its own key.
- **4 good copies kept.** Old copies are deleted only after a newer one has uploaded and been verified (size and checksum).
- In-run retries: upload 3 times (1, 5, 15 min), dump once. A failed dump stays on the server (0600) for the next run. Each run writes a `backup_runs` row.
- The health panel shows "Last good backup: N days ago", amber past 2.5 days, red past 4.
- **Tombstones:** each account deletion writes a hash of the user id and the date (no personal data), in the database and next to the backups. Every restore replays them before the app starts. A test covers backup → delete → restore → user gone.
- Monthly restore test into a scratch database.

### Deletion and retention (chunks 2, 4, 7)
- **Deleted at once:** profile, master CV, runs, PDFs, edit history, problem reports, `allowed_users` and `access_requests` rows.
- **Ledger and orders are kept** with no CV content; the link to the person is replaced by **one random tag per deleted user** (e.g. `deleted-8F3K`).
- **Consent records are kept 12 months after deletion** (email, notice version, text hash, language, sensitive-data line, date), for two stated purposes: proof of consent, and blocking repeat free credits. Then the retention job deletes them.
- Request logs and `run_steps`: 90 days.
- **Backups:** gone within about 8 days; the notice says **within 14 days**.
- **The v1.0 notice** also names DigitalOcean (Spaces, Singapore) as a recipient, and the 12-month consent-record rule.

### Refunds (chunks 4 and 7, and the terms page)
1. Free credits are never refundable.
2. Unused, unexpired paid credits are refundable at their pack's price: RM2 per credit (RM10 pack) or RM1.50 (RM30 pack). Spending is oldest first, so the unused credits are always from the newest pack(s).
3. Expired credits aren't refundable.
4. Refunds go only back to the bank account that paid, found by the order reference.
5. Deleting an account is never blocked. A pending order is kept under the deleted-user tag and flagged "account deleted: refund if received".
6. If the service closes, everyone with unused paid credits is refunded without being asked.

- An email that deleted its account in the last 12 months gets **no new free credits** on signing up again (checked against the kept consent record). Paid credits work as normal.
- **The build:** an admin view of the refundable amount per user or tag (chunk 4); an owner-only "refund" ledger row type (chunk 4); "Request refund before deleting" on the delete screen (chunk 7).

### Before go-live (senior review)
- A CI check on every PR that runs the pre-push guard, plus GitHub secret scanning and push protection.
- Python 3.10 parity with sk24 (CI on 3.10, or a pinned local 3.10).
- A pinned `chrome-headless-shell` under the app's directory, so another tenant's `apt upgrade` can't change the layout.

## Addendum 2 (2026-10-22): the design pass and the summary length
Where this addendum and the sections above disagree, this addendum wins.

### Design (chunks 2 to 7)
- **The design is "Calm":** white rounded cards on a pale ground, Manrope, one teal accent, and a numbered page stepper. The admin page uses the same tokens in a plainer, denser layout.
- **One small stylesheet** (`calm.css`, about 20 KB, no framework) and the repo's self-hosted fonts. Chunk 2 copies it into the app as its only stylesheet.
- The clickable prototype and its sources stay private (git-ignored `docs/design/`). Every screen is built from it, with its wording.
- **English first.** Every screen is built and finished in English. Malay comes after, and the BM/EN notice is still needed before go-live.
- **Screens covered:**
  - request access, the privacy notice and consent, profile, generate (progress and result), edit and re-render, credits and pay;
  - the account page, the "account deleted" page, the full notice and its changelog, the terms;
  - the admin page: access, orders, reports, health and the funnel.

### Behaviour the prototype settled
- **A failed re-format** (Haiku's output fails the word check) **doesn't use one of the 3 free re-renders.** A 3-page or 1-page result does.
- **While a CV is generating,** the user can leave the page. The run carries on, and the result is there when they come back.
- **Rejecting an order** needs a reason the user will see; the Reject button does nothing without one.
- **A major notice version** (e.g. v2.0) sends every page except the notice, its changelog and the terms to the consent screen, which says what changed, until the user agrees. A minor version shows a banner and an account-page note, and asks nothing.

### Professional summary: 2 to 3 lines (chunk 3)
The skill's `references/cv-format.md` says 3 to 4 lines. The app uses **2 to 3**. The top 3 keywords still go in the first two lines, and problem #1 still comes first.
- **Prompt:** call B asks for "2 to 3 lines, at most 50 words, 2 sentences".
- **Pre-render check:** the words in the paragraph under `## PROFESSIONAL SUMMARY` are counted in the Markdown. Over 50 fails before Chrome starts. That failure uses the same single internal retry as the page and keyword checks, and the retry is told the exact problem ("summary is 62 words, cut to 50, change nothing else").
- **On a user's re-render,** a summary over 50 words only warns ("summary is N words, aim for 50 or fewer"). It never blocks, because it's the user's text.
- **Not built:** measuring the summary's lines in the PDF. Revisit if 50-word summaries still wrap to 4 lines. Never clamp or cut the summary in CSS or code.

## Addendum 3 (2026-10-23): keywords the candidate lacks, and the models
Where this addendum and the sections above disagree, this addendum wins.

### Top-3 keywords: backed, bridged or missing (chunk 3)
This replaces "the top 3 keywords present" in the check.
- **Call B reports a status for each top-3 keyword:**
  - **backed:** the master CV shows the skill. The CV uses the keyword as the ad words it;
  - **bridged:** the master CV shows an adjacent skill of the same kind (another tool for the same job). The CV names the real skill and bridges to the keyword honestly, e.g. "Tableau dashboards (transferable to Power BI)", and never implies the candidate has used the keyword's skill itself;
  - **missing:** nothing related. The keyword is left out and listed under Gaps. It's never invented.
- **The check requires backed and bridged keywords only.** A missing keyword is a warning, never a failure, so no internal retry is spent forcing it. A keyword call B doesn't report stays required.
- **No question mid-run** (the brief has no review pause). The result page names each bridged or missing keyword: "If you do have it, add it with Edit the text (free) and to your master CV in Profile."
- **On a re-render,** the keyword warning covers the required keywords only.

### Models and limits
- **Only Opus 5.5 and Haiku 5.5 ever run.** There's no server-side refusal fallback: a refusal fails the run, and no credit is used.
- **Effort:** call A and call B at `medium` (the Opus 5.5 default, set explicitly); the Haiku re-format at `low`.
- **The owner's Console workspace for cvwrite3 has its own key and limits:**
  - Opus 20 requests, 200K input and 50K output tokens a minute;
  - Haiku 10 requests, 50K input and 20K output tokens a minute;
  - other models off;
  - a monthly spend limit: $20 while testing, about $75 at launch, so it sits above the app's own $50 stop on free generations.

### First real run (for the cost risk above)
One generation on a made-up master CV passed after one internal retry, in 67 s, for $0.18 (about RM0.80). Without the retry it's about RM0.48. The RM1.20 revisit trigger still applies to the first week of real use.

senior-lead-Opus5.5-agent

## Addendum 4 (2026-10-23): security decisions before go-live, and matching payments
Where this addendum and the sections above disagree, this addendum wins.

### Deploys
- **Dependencies are locked with hashes.** The server installs from `requirements.lock` with `--require-hashes` and wheels only. `scripts/lock.py` regenerates it with plain pip (no lock tool), and a test fails if it drifts from `requirements.txt`.
- **Every deploy is a git tag** (`v` + the app version), never a branch tip. **Rollback** checks out the previous tag; the schema stays.
- **Migrations are additive only,** so a rollback runs on the newer schema. A test refuses drops, renames, type changes, `set not null`, deletes and a new not-null column without a default. A deliberate destructive change carries a `-- contract:` line and ships in a later deploy.
- **A restore is tested** before the first real user, then monthly. A restore replays the **newest** tombstones file, not the one saved next to an older dump, so deleted accounts stay deleted. A test proves both.

### The render
- Link addresses are fully escaped, and the featured-project link is `http(s)` only, so a URL the ad steers can't add attributes or hidden text.
- The page runs no JavaScript: a `script-src 'none'` policy comes first in the page head. (A Chrome flag was tried: one doesn't stop scripts, the other stops printing.)

### Keys and access
- **The Anthropic key is new at go-live,** typed into a hidden prompt. The development key is revoked after the smoke test. A usage notification goes to the owner below the monthly cap.
- **The shared server:** its administrators can technically read cvwrite3's data. Accepted for wave 1. The privacy notice will say so plainly (wording approved with its other fill-ins before go-live), and access is logged. A server of its own, or encryption at rest, is a later decision if the demand test passes.
- **Secret scanning:** GitHub's own (an owner setting). No extra CI check for now.

### Matching a DuitNow payment to an order
- **Paid credits exist only once the owner approves** an order. "I've paid" adds nothing.
- **The owner approves only when one pending order fits the payment** on amount (exactly the pack price), time (paid after the order was made) and reference. With a reference typo or no reference, approve only if there's a single candidate; otherwise reject and ask the user to report the time they paid.
- **Money is refunded to the paying account, without being asked,** for:
  - a partial payment (the order is rejected);
  - the excess of an overpayment (the order is approved);
  - a second payment for the same order;
  - a payment for a cancelled or already-approved order;
  - money that matches no order, after 30 days.
- **"I've paid" with no money after 48 hours** is rejected with a reason the user sees.
- A copied reference gains nothing: it can only credit the other person's order, and refunds go back only to the account that paid.

build-engineer-Opus5.5-agent

## Addendum 5 (2026-10-25): sign-in in the app, its one email, and how deploys are named
Where this addendum and the sections above disagree, this addendum wins.

### Sign-in (replaces Cloudflare Access in "User flow" step 1, chunk 2 and "Owner actions")
- **No Cloudflare Access.** Its free plan counts every email that signs in, requesters included, against 50 seats, and wave 2 alone is 50 users. Cloudflare stays as the proxy, the origin certificate and the gate that refuses traffic not from Cloudflare.
- **An emailed 6-digit code** (chunk 7j): it works across devices, and link scanners can't use it up.
  - A code lasts 10 minutes and allows 5 tries. Asking for a new one retires the old one.
  - Limits: 3 codes per email per 15 minutes, 10 per IP an hour, 300 a day for everyone (a ceiling on what the mail account can be made to send).
  - Codes and session tokens are stored hashed. Sessions are server-side and last 30 days.
  - Every email gets a code, so the reply never shows whether an email is on the list. After sign-in, the app looks the email up in `allowed_users` as before; one that isn't there gets the request-access page.
  - No email address goes into a log.
- **Sent over SMTP with the standard library,** so no new dependency.

### The one email (an exception to "no emails" in "What isn't sent or stored" and "Out of scope")
- **Sign-in codes are the only email the app sends.** Receipts, reminders, replies to problem reports and marketing are still out.
- **Amazon SES, Singapore (`ap-southeast-1`),** the same country as the backups. Domain `puascari.com` (its sender reputation is shared with the owner's later projects; accepted), From `signin@puascari.com`.
- **cvwrite3 has its own SMTP credentials:** an IAM user that may only send, and only from `signin@puascari.com`. Never the box's own AWS key or another tenant's.
- **The v1.0 notice names Amazon Web Services (SES, Singapore)** as a recipient, for the sign-in email only, and no longer names Cloudflare for sign-in. v1.0 is still unpublished, so this is part of v1.0 and needs no new consent.

### Deploys (replaces "every deploy is a git tag" in Addendum 4)
- **Every deploy is a commit SHA on `main`.** Each one adds a line to `/sites/cvwrite3/DEPLOYS` on the box: UTC time, the full SHA, who, a note. **Rollback** is the line before; the schema stays.
- **One GitHub release, `v1.0.0`,** when wave 1 opens.
- **Every box step has a written undo** (the runbook, and `/sites/cvwrite3/README-BOX-CHANGES.md` on the box). Once real users exist, the user and database steps hold their data: restore from backup instead of undoing them.

### CI on sk24's platform (closes "Python 3.10 parity" in Addendum 1)
- **One CI workflow on every PR:** Ubuntu 22.04 and its own Python 3.10, the hash-locked, wheels-only install exactly as the server runs it, and the full test suite. `ci / test` is a required check on `main` (an owner setting).
- **Tests never read the wall clock.** One test runs at 23:30 UTC (07:30 the next day in Malaysia) across the pages that show dates.
- **Every database connection uses `Asia/Kuala_Lumpur`,** so dates are right whatever the server's own time zone.
- **A dependency released in the last few days is held back** until it has been out for a while (`jiter` at 0.17.0 for the first deploy).

build-engineer-Opus5.5-agent

## Addendum 6 (2026-10-25): where the data is, who runs it, and who gets in
Where this addendum and the sections above disagree, this addendum wins.

### Where the data is
- **sk24 is in Seoul, South Korea** (AWS Lightsail, `ap-northeast-2`). Everything cvwrite3 stores is outside Malaysia. Its clock and every database connection still use Malaysian time.
- **Anthropic** stores what it receives in the United States and may run the AI in other countries (its default, "global"). US-only processing costs 1.1x, so it isn't used. Opus 5.5 and Haiku 5.5 keep inputs and outputs up to 30 days (up to 2 years if flagged) and don't train on them.

### The privacy notice v1.0 (fills the brief's open items)
- **The data user:** KIP ADVISORS (Registration No. 201803365653, Company No. 002900789-V), registered in Malaysia.
- **The request email:** `privacy@puascari.com`, forwarded by Cloudflare Email Routing to the owner's inbox. The destination is never in git.
- **Middle level of detail:** the summary names classes of providers and the countries; one plain line per provider (AWS, Anthropic, Cloudflare, DigitalOcean) in the body.
- **The shared server** (replaces "say so plainly" in Addendum 4): "The server is shared with other projects; admin access to it is logged."
- **Access is logged by Ubuntu's existing `sudo` log** (who took admin rights, and when; about 5 weeks kept). No `auditd`, no new package. Revisit with the "server of its own" question.
- **Both languages, as PDPA s.7(3) and the brief ask:** the Malay is from the owner's translator (`notices/v1.0.ms.md`), with an English / Bahasa Malaysia switch on the notice and the consent screen. A test holds the Malay to the same headings, bullets, numbers and names as the English. A few short page strings are an agent draft for the translator to check.

### Who gets in (replaces "Rollout")
- **Open sign-ups from go-live, up to 30 users** (the old wave-2 switch, now with a cap of 30). Then a **waitlist**.
- **A waitlisted person may ask for one email when there's room** (an unticked box). The owner's "Email the waitlist" button sends it once per person. This is the **second exception to "no emails"**, after sign-in codes (Addendum 5).
- **Retention:** waitlist entries until the person joins, 30 days after their email, or 12 months, whichever is first; declined requests 12 months after the decision.

### Security fixes before go-live
- **Every response is `Cache-Control: private, no-store`,** except the stylesheet and fonts. Cloudflare caches `.pdf` by default, and run ids are sequential, so a CV could otherwise be served to another user from the edge.

### Keys and backups
- **The backup bucket** is `cvwrite3-backups` (DigitalOcean, Singapore). DigitalOcean has no write-only key, so cvwrite3's key is Read/Write/Delete on that bucket only. The offline copy is the dump the monthly restore test downloads.

build-engineer-Opus5.5-agent
