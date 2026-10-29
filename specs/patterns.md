# Shared patterns

<!-- ux-designer-Sonnet5.5-agent, 2026-10-28. First real entries, from redesign S-001 (the page shell and the look every old page gets). The kit's template entry (a command-line error) is removed: it does not apply to this project's screens. Values are the light theme; the dark slice overrides tokens only. Colours are tokens (S-001 AC-9); hex values here are the token values. -->

PATTERN: Text size
RULE:    Body text is Schibsted Grotesk 17 px on 1.55, ink `#13233A`.
         Anything a person reads as a sentence or acts on is 16 px or more at every width: body, lede, hint, meta, note, alert, banner, field label, input text, button, nav link, footer link, table cell, list item. Admin tables too.
         Labels are 14 px or more, never smaller, because they hold a word or a number, never a sentence: eyebrow, kicker, badge, chip, opt, step time, pass mark, the "in use" count, the balance's second line, the footer version.
         Inputs, selects and textareas are 16 px or more, so a phone does not zoom when one gets focus.
         Headings: h1 (`.title`) is 28 px at 320 rising evenly to 40 px at 768 and staying there; h2 is 22 px. A heading wraps and may break inside a very long word; it never truncates.
         Text colours: ink; secondary ink `#3A4960`; muted for hints, meta and labels: `#6A7586` on a white slab (the target), `#566275` on the ground and the quiet slab; coral-for-text `#C2382A`. Never coral `#FF5A47` as a text colour, and nothing paler than muted.
WHY:     Responsive check 2: text never shrinks to fit. 14 px labels stay readable on a phone. 16 px inputs stop the phone zoom. Coral `#FF5A47` is 2.7:1 on the ground and 3.1:1 on white, and the collage's muted `#6A7586` is 4.1:1 on the ground and 4.3:1 on the quiet slab (both fail 4.5:1) but 4.67:1 on white, where it stays (re-plan 2026-10-29).
USED BY: every page
EXCEPTIONS: Headings are the one text that scales with width (28 to 40 px), so a long single word still fits at 320. Nothing else scales.

PATTERN: Slab
RULE:    A slab is a white (`--slab`) block with a 24 px radius and one soft shadow (`--shadow`). It is flat: no gradient, no blur, no second shadow.
         Padding is 20 px below 560 px and 28 px from 560 px.
         Slabs, and the blocks between them, are 20 px apart.
         A slab you can tap (a credit pack, the file drop zone) has a 20 px radius.
         A border appears only where a page names one: the danger zone (error red `#B42318`) and the consent box (ink).
WHY:     Addendum 14: rounded white slabs on the ground, cards only for things you can tap. The padding drops to 20 px below 560 because 28 px each side leaves too little for a form at 320.
USED BY: every page (`.card`, `.notice`, `.pack`, `.drop`)
EXCEPTIONS: In S-001 every old `.card` is a slab, including blocks nobody taps, because the old markup stays. Each page slice replaces those with plain sections where Addendum 14 says "cards only for things you can tap".

PATTERN: Button
RULE:    A button is a pill (fully rounded), 16 px on weight 700, 48 px high at least (`.btn-sm`: 44 px), 44 px wide at least. Its label wraps onto a second line before it would overflow; the button grows in height and never overflows its slab.
         Kinds:
         - Main (`.btn-primary`): coral `#FF5A47` fill, ink text (5.1:1). White text on coral is 3.1:1 and is never used.
         - Every other action (`.btn`, `.btn-ghost`): ink fill, white text.
         - Destructive (`.btn-danger`): error red fill, white text (6.6:1). `.btn-danger-ghost`: transparent, 2 px error-red ring, error-red text.
         Coral fills a control only as the main button, and a screen has one main button. These pages carry more than one `.btn-primary` today and keep them until their page slice: admin, request, run, profile, generate, order.
         A button that changes kind while the page is open (the CV file picker swaps main and navy) changes colour only: same size, same label space, no layout shift.
         Below 560 px, buttons in an `.action-row` fill the row, because two pills side by side do not fit a 288 px slab.
         Hover and press: see Hover and press. Focus: see Focus ring.
         Disabled (`:disabled`): 45% opacity, not-allowed cursor, not focusable, no lift and no press scale. A disabled main button stays coral at that opacity.
WHY:     Addendum 14: navy pill buttons, coral for the main one only. Calm's one-line labels overflowed at 320 ("Keep them for 3 months" needs about 250 px).
USED BY: every page
EXCEPTIONS: none

PATTERN: Focus ring
RULE:    Every link, button, input, select, textarea, summary, checkbox and radio shows a ring on keyboard focus (`:focus-visible`): a 3 px solid outline 3 px outside its edge, following the element's own radius (6 px on square elements): coral where a white slab is behind it, ink on the ground, on the quiet slab and on a coral button; in dark, coral on the ground and slabs, ink on a coral button (S-002 AC-81). A field also takes a 2 px ink edge and a 4 px halo (`--halo`, ink at 18%).
         `outline: none` is never used without this replacement.
         `main` takes programmatic focus from the skip link and shows no ring: it is not a control.
WHY:     The target's ring is coral. Coral passes 3:1 on a white slab (3.09:1) but not on the ground (2.73:1) or the quiet slab (2.85:1), and vanishes on a coral button; ink there is 14:1 (re-plan 2026-10-29, README-brief-amended.md).
USED BY: every page
EXCEPTIONS: none

PATTERN: Touch target
RULE:    Every control is 44 by 44 px at least, with 8 px or more between it and the next control. This covers the brand, the balance, every nav item, the banner link, every footer link and Sign out, every button, every checkbox and radio row (the whole row is the target), every `summary`, every pack, the drop zone, and the language links on the notice and consent pages.
         A link inside a sentence is exempt from the 44 px height (hints, meta, notes, alerts, prose and table text), because stretching it would break the line. It is underlined so it can be found. The language links are not exempt.
WHY:     Responsive check 4. The language links pick the language of the consent, so they are controls, not sentence links.
USED BY: every page
EXCEPTIONS: the sentence links above, named.

PATTERN: Hover and press
RULE:    Hover styles sit inside `@media (hover: hover)`, so a touch screen never keeps a stuck hover. Each hover has a press (`:active`) twin, so a touch gets the same feedback.
         - Button: hover lifts 2 px with a soft shadow; press scales to 0.98.
         - Nav item: hover takes a tint (`--hover`, `#E6E5E0`); press scales to 0.98.
         - Pack: hover takes a 2 px ink edge and lifts 2 px; press scales to 0.98.
         - Drop zone: hover and press fill with `--hover`.
         Nothing is shown only on hover, and no information is only in a `title` tooltip.
WHY:     Responsive check 4: nothing depends on hover.
USED BY: every page
EXCEPTIONS: none

PATTERN: Motion
RULE:    A transition lasts 300 ms at most, on transform, opacity or colour only, with the easing `cubic-bezier(.2, .8, .2, 1)`. Nothing loops: no `infinite` animation, no pulse. One thing moves at a time, and in S-001 that is only the hover lift and the press scale.
         With reduced motion, every transition and transform is off and a state changes at once. The state still shows.
WHY:     Addendum 14: restrained and slow, no loops, no endless pulses, reduced motion shows the final state. Calm's pulsing step dot goes.
USED BY: every page
EXCEPTIONS: none

PATTERN: Field
RULE:    The label sits above the field, 16 px on weight 700. The field is 48 px high at least, 16 px text, a 16 px radius and a 2 px edge in `#7D8798` (3.6:1 on a slab, 3.2:1 on the ground). The placeholder is muted. A textarea grows taller only; it never grows wider.
         - Focus: the edge turns ink, with the halo (see Focus ring).
         - Invalid: only after the person has touched the field (`:user-invalid`), the edge turns error red. The words come from the page's own note; the field adds none. An untouched empty required field is never red.
         - Read-only: `--slab-2` fill, the same edge, full-contrast ink text, still reachable by keyboard, default cursor. It looks different from an editable field so the person can tell.
         - Disabled: 45% opacity, not-allowed cursor.
         - The tags `.opt` (optional) and `.opt.need` (needed): a 14 px label pill; "needed" uses the warn tint.
         - The CV text box (`#cvtext`) is Geist Mono 16 px on 1.6.
WHY:     The edge needs 3:1 to be seen (WCAG 1.4.11); the collage's rule colour is about 1.4:1. Addendum 10 makes the ad box read-only while generating is paused.
USED BY: sign-in, profile, generate, edit, report, request, applications, admin
EXCEPTIONS: none

PATTERN: Choice row
RULE:    A checkbox or radio is 24 px, accent ink, and its label sits beside it and wraps. The whole row is the target: 44 px high at least, 8 px between rows. Checked shows an ink fill with a white tick (or dot). Disabled is 45% opacity.
         The ring goes around the box (Focus ring).
WHY:     Calm's 18 px box in a 20 px row missed 44 px (check 4).
USED BY: profile, applications, account, consent, request, run, admin
EXCEPTIONS: none

PATTERN: Status note
RULE:    A note is 16 px ink text on a tinted block with a 20 px radius, a 4 px left edge in the kind's colour, and a Heroicons outline icon (24 px, ink) in the left gutter. The text block is indented 52 px to clear the icon, whatever the note holds (paragraphs, a list, bold, links, a row of buttons).
         Kinds (tint / edge / icon):
         - warn: `#FBE7B0` / marigold `#F3B43C` / exclamation-triangle
         - error: `#FADDD7` / error red `#B42318` / x-circle
         - ok: `#D9EEE9` / teal `#26968A` / check-circle
         - info: `#DCEBF7` / sky `#A0CDEC` / information-circle
         Ink text on every tint is 12:1 or more. The words say what happened; the colour and the icon add to them and never replace them.
         Text wraps and breaks inside a long word; a note never clips and never has a fixed height. A link inside a note is bold and underlined.
         A note has no close button and does not animate in: it appears with the page. It sits above the form it concerns, and the form stays below it with what the person typed. The announcement is the page's own: `role="alert"` for errors, `role="status"` for the rest.
         The icons are embedded in the stylesheet as SVG data URIs, and the stylesheet's top comment holds Heroicons' MIT notice.
WHY:     Colour alone is not a cue. A CSS-drawn English label would be wrong on the Malay consent page, so the icon carries no text.
USED BY: every page (`.alert-*`, the shell's `.banner` and `.banner-info`)
EXCEPTIONS: none

PATTERN: Status label
RULE:    A badge, chip or meter pill is a 14 px Geist Mono label in a pill, ink on the kind's tint from Status note: ok (teal tint), wait (warn tint), bad (error tint), info (info tint). `.badge-off` is the photocopy pair: `#5A585E` on `#D6D4CE` (4.7:1). The label always holds the status in words.
         A step or checklist dot (`.dot`) is an 18 px circle whose shape changes with its state, not only its colour: waiting is an empty ring; running is a ring with a filled centre (ink); done is a teal circle with a white tick; failed is an error-red circle with a white cross. None of them animates.
WHY:     Photocopy grey means "before" or "off". The dot used to pulse (Calm), which the motion rule forbids; the run page reloads every 2 seconds, so a still dot is enough.
USED BY: run, admin, credits, applications, profile, generate
EXCEPTIONS: none

PATTERN: Page nav
RULE:    One `nav` (label "Pages") in a white rail (24 px radius, 8 px padding, `--shadow`). It holds the two steps (Profile 1, Generate 2), a 1 px divider, and the tabs (Applications, Credits, Account, then Admin for the owner).
         Items are pills, 44 px high at least, 16 px on weight 700, 8 px apart, with a visible label that is never truncated. No item is in a menu, and the rail never scrolls.
         - From 840 px: one line.
         - Below 840 px: two lines. Line 1 holds the two steps, half the width each. Line 2 holds the tabs, each growing to fill the line, and the tabs wrap onto a further line only when they do not fit (at 320: Applications and Credits, then Account and Admin).
         Current page: the link with `aria-current="page"` is an ink pill with white text. A page whose section matches no item marks none.
         Step marker: a 24 px circle before the label, at every width. It shows the number, or a tick once the profile is ready (screen readers still hear "(done)"). It is outlined in ink; on the current item it flips to a white fill with an ink mark.
         Admin carries a 24 px marigold circle with an ink "A".
         No item is ever disabled, greyed or removed because a step is not done or the balance is 0. Generate is a normal link before the profile is ready; the page says what is missing (Addendum 10).
         The header is not sticky.
WHY:     Addendum 10: all labels show on a phone. Six 44 px items with 8 px gaps need about 700 px in one line; below 840 px the margin is too thin for the longest labels. Calm hid the step numbers below 560 and let the nav scroll sideways; both hid things (check 6). Not sticky because a two-line header would take a third of a 375 px landscape screen (check 5).
USED BY: every signed-in page
EXCEPTIONS: none

PATTERN: Balance
RULE:    The balance is one link to `/credits`, a white pill with `--shadow`, 44 px high at least, two lines:
         - line 1: the count (weight 800) and "credit" or "credits", then "· N in use" in muted text when N is above 0;
         - line 2: "earliest expire D Mon YYYY", or "buy more" when there is no expiry. 14 px, muted, shown at every width.
         From 480 px it sits at the right of the brand's row; below 480 it takes its own row under the brand, the full column width, left-aligned.
         It never changes colour for a low or zero count: no red, no icon, no pulse.
WHY:     Brief: the balance and its expiry show on every screen. Addendum 10: a credit held by a CV in progress is "in use", never "out of credits". The pill needs about 200 px, the brand about 160, so at 320 (288 usable) they cannot share a row.
USED BY: every signed-in page
EXCEPTIONS: none

PATTERN: Table
RULE:    From 561 px a table stays a table: header cells are 14 px muted labels, cells 16 px, 1 px dividers, the first column bold, numbers in tabular figures.
         Below 560 px each row becomes a block, with its first cell bold on its own line. The header row stays in the markup, hidden from the eye but not from screen readers.
         The admin page's tables are the one table allowed to scroll sideways, and only inside their slab, at 561 to 880 px; the page itself never scrolls sideways.
WHY:     Below 560 a header row stacked once above every row would repeat nothing useful; each page slice adds a label to every cell when it rewrites its markup (a gap left on purpose). Admin tables hold ids and numbers that cannot be stacked or wrapped without losing which column a value belongs to.
USED BY: credits, generate, run, applications, admin
EXCEPTIONS: the admin sideways scroll, named.
