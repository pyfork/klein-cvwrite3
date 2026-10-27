<!-- senior-lead-Sonnet5.5-agent, 2026-10-28. Feature brief from the template; the Shape drafted on the same branch. -->
# Brief: redesign

## Who it's for
Anyone using Better Jobs: a job seeker, mostly young and on a phone, who wants one CV made for one ad. Also the owner, on the admin page.

## The problem
Addendum 14 settled the new look (cut paper), but the app still wears Calm: no page has the new look. A visitor who is signed out has no home page; `/` sends them to the sign-in form. Calm also has no dark mode.

## End goal
Checked by tests and by the six responsive checks, 320 to 1440 px, light and dark:
1. Every page the app serves has the new look, and no template links `calm.css`. A test renders each route once per theme. Once the last page slice has merged, no template uses an old Calm class name.
2. A signed-out visitor at `/` sees the home page. A signed-in one is sent to Profile or Generate, as now.
3. Every behaviour, check, price and wording rule in `brief.md` works as before. The tests that passed before still pass; only the tests that pin the old stylesheet's name change.
4. The CV PDF is unchanged: same style, same render fingerprint after a deploy.
5. No page asks a third party for anything. Fonts, art and scripts are served by the app.
6. Motion plays once, then waits. With reduced motion, or with scripts off, every page works and shows its final state (the compare slider on "After").

## Out of scope
- Malay copy: safe because the brief says English first, and the translator works from the finished English; revisit when a slice's English pages are final.
- CV PDF style (Archivo): safe because the PDF is what employers see and the 2-page check is tuned to it; revisit when the owner wants a new CV template.
- The Go/chi move: safe because it isn't scoped and doing both at once doubles the risk; revisit before the third page slice. If the move is likely soon, the order flips: port first, then restyle, so each template is done once.
- Styled emails: safe because Addendum 11 fixes the payment email as plain text, so there is nothing to style; revisit if an email ever needs layout (an HTML part, system fonts, no images, no tracking), which amends Addendum 11 first.
- The animated teaser on the home: safe because the home's sections already carry its content and its autoplay breaks the motion rule; revisit if a tour is wanted, as a button that plays only when pressed, with its script hosted by the app.
- New features, the CV options included [lean]: safe because Addendum 14 calls this "a new look, not new features", so a regression has one cause; revisit when the look has shipped.

## Limits it must respect
- **Adds no entity, state or container.** No table, no migration, no new process or unit, no box change. The stylesheet, fonts, art and scripts are static files on the app's existing `/static` and `/fonts` mounts. The signed-out home is a new page, not a new entity.
- Project rules: server-rendered Jinja, plain forms, one stylesheet, self-hosted fonts, no JS framework, no build step. Their Screens line says "one small script"; Addendum 15 needs a few, so the owner changes that line first, in a PR of its own, before the first slice that adds a script.
- Scripts: a few small plain-JS files, each loaded only by the pages that use it. A test lists the allowed scripts and fails on any other.
- The PDF render reads `fonts/` by file name. The Archivo, Source Serif 4, IBM Plex Mono and Manrope files stay; new fonts are added beside them, each with its licence file.
- Caching (Addendum 6): every response is `private, no-store` except `/static/` and `/fonts/`. The stylesheet and art are cached, so their URLs carry `?v=<app version>` (pinned in `tests/test_ux.py`).
- Published notices are immutable and hash-pinned: the notice and consent pages change around the text, never in it.
- Responsive rules (320 to 1440 px, six checks, body text 16 px or more) and content rules (the home shows invented samples only).
- CI: `test` and `push-guard` stay green. The art script's packages (OpenCV, numpy, Pillow) are dev-only, pinned in `gen/requirements.txt`; CI never installs them, and they never enter `requirements.lock` or the server.
- Collects nothing new and sets no cookie, so no privacy-notice change.
- Phone weight: slice 2's plan sets a budget for the home.
- `specs/adr/` is empty and there is no PRD, so there is nothing else to cite.

## Anything to match
Brief Addendums 14 and 15 (tokens, type, shape, motion, copy, and what is settled), and the owner-accepted collage homepage v2 (a private design spike kept out of git). Samples: the three invented sample roles.

## Rough slice list
1. **Foundation** (SHARED, risky: every page): a new stylesheet with tokens and dark mode in place of `calm.css`; web fonts in `fonts/`; the `base.html` shell (nav, slabs, pill buttons, torn-edge bands); the art in `app/static/`, with its generator moved into the repo. The new stylesheet keeps the old class names, so this slice edits only `base.html` and the stylesheet. Each later page slice rewrites its own markup and drops the old names; the last page slice deletes what is left.
2. **The signed-out home:** the v2 page.
3. **Profile, Generate and the result:** the ad read, drag-to-compare before and after, the interview prep panel.
4. **Edit and re-render:** "You are in control".
5. **Your applications,** with the "before the interview" panel.
6. **Credits and pay.**
7. **Account, notice, consent, terms, deleted, error and report pages.**
8. **Admin,** plainer.

Why this order: every page shares the foundation, so it is the riskiest and goes first. It still gives users something: every existing page gets the new shell at once. SHARED changes get their own slice.

## Open questions
None. Addendum 15 settles the open items of Addendum 14.

## Shape

### Entities and invariants
No entity is added, so there is nothing to add to `specs/architecture.md` (the file does not exist yet). The shared pieces the slices change, and what must stay true of each:

| Shared piece | Invariants (what must always be true) |
|---|---|
| The page shell (`base.html`) | Every page keeps the skip link, the balance with its expiry, the nav (two steps, two tabs, Admin for the owner), the pause or slow banner, the CV bar, and the footer (report a problem, notice, terms, sign out, version). |
| The stylesheet | One file, no framework. Its URL carries `?v=<app version>`. Light and dark both work. Paper and CV previews stay light in dark mode. |
| `fonts/` | Every file the PDF render names stays. New fonts sit beside them, each with its licence file. |
| Scripts | Only those on the allow-list. Each loads only on the pages that use it. Every page works with scripts off. |
| Published notices | Not edited. |

### API sketch
- `GET /`: a signed-out visitor gets the home (200). A signed-in visitor gets 303 to `/generate`, or to `/profile` until the profile is ready, as now. Anyone may call it. It writes nothing.
- No other route is added or changed. Every other page still sends a signed-out visitor to sign-in.
- New static files, public and cached, with no personal data: the stylesheet and art (WebP) in `app/static/`, a few scripts, new fonts in `fonts/`.
- Not part of the app: the art script under `gen/` (dev-only) and a test that lists the allowed scripts.

### States
None. The home's motion plays once per page view in the browser and keeps no state.

### Expected load
| What | Number | Where the number came from | Budget it touches |
|---|---|---|---|
| Users with accounts | up to 30, then a waitlist | brief Addendum 6 | none; static files cost the app almost nothing |
| Visitors to the public home | unknown; `/` is `no-store`, so every view reaches the app | no measurement yet | the app unit (one worker, `MemoryMax=250M`, Addendum 1) |
| Home page weight | page about 93 KB plus about 30 KB of sample data; the whole art folder is 668 KB for 25 images, and the home uses a subset | the design spike's files, measured 2026-10-27 | phone data; slice 2's plan sets the budget |
| Stylesheet | 21 KB today | `calm.css`, 21,023 bytes | slice 1's plan sets the budget |
| Screens to check | 24 templates; each page at 7 widths (320, 360, 390, 768, 1024, 1280, 1440), light and dark | the templates and the responsive rules | review time, not run time |

### Trust boundaries crossed
- **Browser to server:** `/` becomes the first public page that is not a form or an error. It is the same for every visitor. It needs a soft sign-in check that does not redirect, the one place that reads the session without requiring it.
- **Server to a third party:** none added. Fonts, art and scripts come from the app, so no page asks another host for anything. The AI, mail, hosting and backup providers are unchanged.
- **One user's data to another's:** none. The home shows invented samples, and its employers and people are labelled as made up. The CV previews on signed-in pages are unchanged.

### Key choices
| The choice | The option not taken | Why |
|---|---|---|
| The emails stay plain text | An HTML part with the tokens | Addendum 11 fixes plain text, so there is nothing to style. |
| The new stylesheet keeps the old class names in slice 1 | Rewrite all 24 templates in slice 1 | One reviewable diff, and every page looks new at once. The old names go page by page. |
| Small plain-JS files, an allow-list test, pages work with scripts off | Any script allowed with no test, or a framework | Project rules ban a framework and a build step; the test makes the rule hold; scripts-off keeps pages usable. |
| No teaser on the home | A click-to-play tour with a self-hosted animation library | The motion rule, and the sections already say what it says. |
| `/` shows the home to a signed-out visitor, tested as ordinary behaviour | Extra tests that pin "identical for every visitor" and "no database read" | The home holds no personal data. Revisit if it ever gains a personal part. |
| The home keeps `private, no-store` | Public caching at the edge | `/` answers differently by sign-in, so a cached answer could show the wrong one. |
| The art is committed as WebP, and CI does not regenerate it | CI regenerates and diffs | OpenCV output can differ by version and platform. |
| Sample employers are invented and labelled as made up, with no name search | A web and company-register check | The owner's choice. The label on the page says they are made up. |

### Risky slices
| Slice | Class (DATA, ACCESS or SHARED) | The assumption it tests | What changes if it is wrong |
|---|---|---|---|
| 1 Foundation | SHARED | The old class names still style every existing page acceptably under the new stylesheet; the versioned URL keeps old markup from meeting old CSS; the PDF render is untouched. Every feature relies on it: every page extends `base.html`. | Every page breaks at once, the consent form included, and that blocks sign-in for everyone. The undo is a revert (static files and templates, no schema), run on a non-live copy. |
| 2 The signed-out home | ACCESS | `/` can show a public page without weakening any other redirect or exposing account data, and the soft sign-in check does not start a session. | A signed-out visitor sees the wrong page, or a signed-in one sees the home. The undo is a revert to the redirect. No `specs/threat-model.md` exists yet; the slice plan says so on its Threat model line. |

Slice 7 holds the consent form, which gates every sign-in. It is not a class (who gets in does not change), but its tests run in full.

### Shared standards still missing
- Dark mode: one token set for both themes (slice 1).
- The scripts allow-list test (slice 1).
- A test that renders every route once per theme (slice 1).
- The no-script and reduced-motion convention: each motion has an end state that shows without scripts (set in slice 1, first used in slice 2).
- Evidence for the six responsive checks: run on a local browser per slice, with screenshots attached to the PR. CI has no screenshot step.

senior-lead-Sonnet5.5-agent
