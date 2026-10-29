<!-- senior-lead-Opus5.5-agent, 2026-10-29. The ledger beside brief.md: every change against the target design and its basis. Rides in the slice-plan PR that writes the rule. -->
# Brief amended: changes against the target

Target for the redesign feature: the accepted collage homepage v2 (Addendum 14). The default is the target. Each change is in exactly one section:

1. **Real departures:** v2 shows it and the rule differs. The reasoning is a fix (the problem v2 causes, for whom) or an improvement (the gain). The owner answers each; "asked" means not answered yet. The approved rows change S-001's rules and locked cases; that re-plan rides in the slice 2 plan PR.
2. **Gaps filled under the responsive rules:** v2 doesn't show it (it is the home only: no app page, no app nav). Not asked; the responsive rules govern it and the reviewer judges it.

A rule that differs from v2 and is in neither section is a defect.

## 1. Real departures

| date | feature, slice | rule | before (target) | after | fix or improvement: reasoning | owner's answer, date |
|---|---|---|---|---|---|---|
| 2026-10-29 | redesign, S-001 | AC-27 brand mark | coral 26 px square, ink wordmark | ink mark (built in S-001) | Neither: built ink only kept coral for "after" and the main button. Lean: **back to the target** (coral), with a one-line exception in Addendum 14's coral list. | approved, 2026-10-29 |
| 2026-10-29 | redesign, S-001 | AC-9 muted text | `#6A7586` everywhere | `#6A7586` on white slabs (the target); `#566275` on the ground only | **Fix.** On the ground `#F2F1ED`, v2's grey is 4.13:1, under the 4.5:1 text floor (AC-16, WCAG AA 1.4.3): hints and "optional" labels are hard to read with low vision or on a phone in sunlight. `#566275` is 5.47:1. On white slabs v2 passes (4.67:1) and stays. Look change: lightness 49 to 41, on the ground only. | approved, 2026-10-29 |
| 2026-10-29 | redesign, S-001 | AC-44 focus ring | coral ring, 3 px | coral on slabs (the target); ink on the ground and on coral buttons | **Fix.** On the ground, coral is 2.73:1, under the 3:1 floor (AC-17, WCAG AA 1.4.11): a keyboard user can lose track of focus. A coral ring on a coral button disappears. On white slabs coral passes (3.09:1) and stays. Seen by keyboard users only. | approved, 2026-10-29 |
| 2026-10-29 | redesign, S-002 | AC-75, AC-76 dark selector | dark tokens under `:root:not([data-theme="light"])` plus a `:root[data-theme="dark"]` block, so a page can force a theme | dark tokens under `@media (prefers-color-scheme: dark){:root{…}}` only; no `data-theme` selectors | **Fix.** v2's override hooks need a switch, a stored choice or a script to set them; Addendum 14 says the theme follows the device, and AC-75 forbids all three. With no setter the extra selectors are dead code. Look change: none; dark values are v2's exactly. Lean: **the proposal**. | approved, 2026-10-29 |

## 2. Gaps filled under the responsive rules

| date | feature, slice | rule | what the target doesn't show | what the rule does | responsive rule or check it follows |
|---|---|---|---|---|---|
| 2026-10-29 | redesign, S-001 | AC-19 content width | app pages (v2's `.wrap` up to 1240 px is the home) | app pages: `main` up to 880 px, centred; the home (S-005) keeps v2's 1240 px | Maximum: content stops growing at 1280 px; check 2: min and max widths, no fixed widths; check 6: priorities decided |
| 2026-10-29 | redesign, S-001 | AC-23 nav at narrow widths | the app's tabs (v2's nav is the home's section links, hidden below 900 px) | app tabs and balance wrap to two lines below 840 px, nothing hidden; the home (S-005) hides its section links as v2 does | "When the layout changes": at the width the content stops fitting; check 6: nothing needed to understand the screen is hidden, navigation specified at each width |
| 2026-10-29 | redesign, S-002 | AC-77 dark values for app-only tokens | `--error`, `--edge`, `--hover`, the four tints, `--halo`, the alert icons (v2 has no forms, alerts or badges) | values picked from v2's dark palette, each measured: text 4.5:1+, borders and marks 3:1+ | Check 4: contrast in every state; AC-16, AC-17 |
| 2026-10-29 | redesign, S-002 | AC-79 `--on-accent` | the app's primary button and admin marker (v2 writes navy on coral as a literal in `.pill.coral`) | a token, navy in both themes; v2's look kept without a literal (AC-10) | Check 4: contrast; AC-10 |
| 2026-10-29 | redesign, S-002 | AC-80 QR frame | the QR (v2 has none) | stays white in dark, like paper (Addendum 14), so it scans | Check 6: nothing needed is lost; Addendum 14 |
| 2026-10-29 | redesign, S-002 | AC-81 focus ring in dark | rings on dark app surfaces | coral on ground and slabs (the target; passes in dark), ink on coral buttons (S-001 AC-44) | AC-17; check 4 |
| 2026-10-29 | redesign, S-002 | AC-83 app pages in dark | app pages and their states at each width (v2 is the home only) | colour only changes; widths 320 to 1440 checked in every state | Check 1: widths; check 4: states |
