# L8b: one streaky measure stops the comparison; self-check re-run

Read `/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/tasks/L-CONTRACT.md` and follow
its rules. The statistics contract changed (decision D-15): read its sections "Streak check",
"Result for a tool" (the ladder has eight steps now) and "What the method cannot see", and
record 0016 "Fixed texts" F6, in their current text. The copy of the acceptance tests at
`tests/acceptance/test_logs.py` still states the old ladder in a few tests; do not edit it,
and list the acceptance tests that fail because of this change (the orchestrator has them
updated).

## You own

`src/arci/logs/decide.py`, `src/arci/logs/schema.py` (only if a validator encodes the old
ladder), `src/arci/logs/report.py` and `src/arci/logs/html.py` (only the row rendering of
F6), `bench/selfcheck_logs.py`, `docs/results/logs-selfcheck.md`, and the unit tests and
snapshots of those files under `tests/unit/logs/`.

## Changes

1. `decide.ladder`: after `too_few_days`, CANNOT TELL (`streaky_days`) when any finding is
   `streaky`; then REAL DROP, NO DROP, `not_enough_evidence`. Per-measure findings and
   their stored test fields do not change.
2. Rendering (text, Markdown, HTML): when the tool's reason is `streaky_days`, every row
   whose finding is not `streaky` or `too_few_days` shows `not used`; the record keeps the
   finding.
3. `bench/selfcheck_logs.py`, section 4 ("Days that come in streaks"): report three
   variants side by side for wrong REAL DROP and wrong NO DROP: no check, a per-measure
   check (the previous rule, computed from the findings), and the rule as built. Use at
   least 2,000 histories in every cell of the 5/10, 7/21 and 14/42 designs and at least
   1,000 at 28/84 (the first run had cells with under 100, which is too few to read); if
   that needs speed, cache the reference distributions or build day tables directly
   instead of through full `ReadResult`s for this section only, and say what you did. Add a
   row for correlation 0 (independent days) so the cost of the check is visible, and for
   the power cell (a 45% drop at 14/42, log standard deviation 0.40) report REAL DROP under
   the three variants. Sections 2 and 3 are re-run with the rule as built; the gates are
   unchanged.
4. Re-run the full self-check and rewrite `docs/results/logs-selfcheck.md`.

## Done when

`.venv/bin/pytest tests/unit/logs -q` passes; the full self-check has run and its gates
pass; ruff format, ruff check and basedpyright are clean on your files;
`shasum -a 256 -c FROZEN.sha256` passes. Final message: the gate table, the three-variant
streak table, the list of acceptance tests that now fail and why, files changed.
