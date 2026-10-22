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

senior-lead-Opus5.5-agent
