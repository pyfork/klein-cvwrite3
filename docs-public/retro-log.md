# Retro log

## redesign, slice 1 (2026-10-29)
- **Watched:** any 404 on `/static/betterjobs.css` or `/fonts/` in the request log after the deploy → not deployed yet (`flow-numbers.sh`: no deploy run on `1dfdf53`).
- **Assumption:** not tested in production yet (not deployed). In the build, the old class names styled every existing page under the new sheet: `locked-checks` passed on the checker on #60 at `27bdaf8` (CHECK 1 to 3, REGRESSION A to C).
- **Flow:** lead time 19.4 h to merge, not deployed; longest wait tech review and fixes, draft (agents, owner), 12.2 h; reviewer runs 0 after ready (1 is a first-time PASS). Pasted from `bash docs/claude-pkg/flow-numbers.sh 59 60`.
- **Bugs traced:** none found since the merge (not deployed).
- **Went wrong:** (1) a locked case measured a focus ring against the element's own fill (AC-17), re-planned in #61; count 1. (2) The locked check scripts failed on the checker: venv location (#71), working directory (#76); count 2, the same root (scripts written for a local run only). (3) slice-review FAIL round 1: a stale note and no screenshots attached; count 1.
- **Check proposed:** none. (2) is now caught by `locked-checks` on the checker, which runs every newly locked script on the plan PR.

## redesign, slice 2 (2026-10-29)
- **Watched:** none new (a colour leaves no trace in the request log); slice 1's 404 signal → not deployed yet (`flow-numbers.sh`: no deploy run on `d7c6ec0`).
- **Flow:** lead time 8.3 h to merge, not deployed; longest wait tech review and fixes, draft (agents, owner), 5.8 h; reviewer runs 0 after ready (1 is a first-time PASS). Pasted from `bash docs/claude-pkg/flow-numbers.sh 99 100`.
- **Bugs traced:** none found since the merge (not deployed).
- **Went wrong:** (1) #100 merged on a `slice-review` FAIL at `f7f3be6`: one blocking finding, the screen checks' screenshots were not attached; the images existed locally because `gh` cannot upload images; count 1 (slice 1's FAIL round 1 also lacked screenshots: count 2, the same root). (2) The reviewer's suite run showed 10 skipped where the PR stated 1; count 1.
- **Check proposed:** none yet. (1) is seen twice; the gap test (`docs/guards/README-GUARDS.md`) decides whether a merge gate on `slice-review` is proposed in its own PR.
