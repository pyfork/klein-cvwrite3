<!-- senior-lead-Opus5.5-agent, 2026-10-29. The deviation ledger: every departure from a target design, approved or not, with its reasoning. Beside brief.md; rides in the slice-plan PR that writes the rule. -->
# Brief amended: deviations from the target

Target for the redesign feature: the accepted collage homepage v2 (Addendum 14). One row per deviation. "Asked" means the owner has not answered yet; a rule that differs from the target with no approved row is a defect.

| date | feature, slice | rule | before (target) | after | reasoning | owner's answer, date |
|---|---|---|---|---|---|---|
| 2026-10-29 | redesign, S-001 | AC-27 brand mark | coral 26 px square, ink wordmark | ink mark, ink wordmark (built) | Lean: coral, as v2. No rule broken; a logo does not weaken coral's meaning ("after", the main button). Coral needs a one-line exception to Addendum 14's coral list. | asked |
| 2026-10-29 | redesign, S-001 | AC-9 muted text | `#6A7586` | `#566275` (built); lean: `#6A7586` on white slabs, `#566275` on the ground | `#6A7586` is 4.13:1 on the ground `#F2F1ED`, under the 4.5:1 text floor (AC-16, WCAG AA 1.4.3); 4.67:1 on white passes. Lightness 49 (v2) vs 41 (built). | asked |
| 2026-10-29 | redesign, S-001 | AC-44 focus ring | coral, 3 px | ink, 3 px (built); lean: coral on slabs, ink on the ground and on coral buttons | Coral is 2.73:1 on the ground, under the 3:1 floor (AC-17, WCAG AA 1.4.11); 3.09:1 on white passes. A coral ring on a coral button would not show. | asked |
| 2026-10-29 | redesign, S-001 | AC-19 content width | `.wrap` up to 1240 px | `main` up to 880 px on app pages (built); lean: keep for app pages, 1240 px on the home (S-005) | v2 is the marketing home and has no app page. At 1240 px a form's text line would run past the usual 60 to 80 characters (estimate, not measured). | asked |
| 2026-10-29 | redesign, S-001 | AC-23 nav at narrow widths | section links hidden below 900 px | app tabs wrap to two lines below 840 px (built); lean: keep; the home (S-005) follows v2 | v2's nav links to the home's own sections. The app's tabs and the balance cannot hide: AC-71 puts nothing behind a menu. | asked |
