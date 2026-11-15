# B2: the 2.4.0 self-check for `arci-logs/2`

Read `AGENTS.md` in the worktree `/Users/ajay/Developer/.arci-worktrees/wt-v2-logs`
(branch `v2/logs2`). Work only there. Change no git state. No network, do not call `uv`.
Never open anything under `~/.claude` or `~/.codex`, and search no memory registry. Use
only synthetic data. Plain words, short sentences, no sales wording, no em dashes. You are
the only agent editing the worktree.

## Read first

- `docs/STATISTICS_LOGS.md`, all of it. The section "Checks that agents run" lists what
  the self-check does; its part "The 2.4.0 self-check adds" (items 7 to 16) is this task.
- `docs/design/0017-logs-2.md`: decision 5 and the section "Coverage of the bound".
- `bench/selfcheck_logs.py`, `docs/results/logs-selfcheck.md` (the 2.3.0 run),
  `tests/unit/logs/test_selfcheck_quick.py`, `tests/unit/docs/test_logs_docs.py`.
- `/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/spikes/S0-logs2/` (REPORT.md
  and the three scripts): the spike already built generators for setting changes, the
  newly adopted setting and the kept-row rules. Reuse the ideas; the product code now has
  the setting rule and `src/arci/logs/kept.py`, so call those, not the spike's copies.

## You own

`bench/selfcheck_logs.py`, `tests/unit/logs/test_selfcheck_quick.py`,
`docs/results/logs-selfcheck.md`, the tables and self-check figures inside
`docs/STATISTICS_LOGS.md` (a pinned file released for change by decision D-18; change
nothing else in it), the two constants `RATE_5_10` and `RATE_7_21` in
`src/arci/logs/report.py`, the snapshots that carry those two figures, and
`tests/unit/docs/test_logs_docs.py` where the new tables need a test.

Not yours: any other product code, `README.md`, `docs/recipes/`, `tests/acceptance/`,
`.github/`, version numbers, `FROZEN.sha256`.

## What to do

1. **Make the script build `arci-logs/2` records** and get
   `tests/unit/logs/test_selfcheck_quick.py` passing again (14 tests fail today because
   their builders lack the new record fields). Keep every existing gate and table.
2. **Add items 7 to 16** of "The 2.4.0 self-check adds", exactly as written there: the two
   new gates (setting changes; a competitive choice) with separate null and per-measure
   exact-margin cells of exactly 20,000 histories each and the bound 0.0283; the two
   report-only cells that break A1, each naming the assumption it breaks; rates
   conditional on passing the streak check; power cells that run until the stated number
   of tested histories; the design 14 after against 16 before in the null, correlation and
   power tables; the weekly-cycle and regime-switching generators; the kept-table checks
   under every condition of the promise, with the boundary-spanning file and the day never
   captured whole; the relabelled counterexample.
3. **Seeds:** base `18112026`. Every row names its seed. No unseeded randomness. Rates as
   `k/n = value` with a Wilson 95% interval, copied without rounding, as now.
4. **Run the full self-check** and write `docs/results/logs-selfcheck.md` from it (date,
   seed base, elapsed time, every table, the gate summary). The 2.3.0 run took about 110
   minutes; use processes in parallel as the script already does. If the full run cannot
   finish in your session, run every gated cell in full, say exactly which report-only
   cells were not run, and leave the command to finish them.
5. **If a gate fails: stop and report.** Do not change a threshold, a seed, a generator or
   the product to make it pass. Say which cell, the count, and what you think it means.
6. **Replace the tables and figures in `docs/STATISTICS_LOGS.md`** with the new run, row
   for row with every column, and remove each marker line "figures from the 2.3.0
   self-check; replaced at the 2.4.0 self-check". Check every figure quoted in the prose
   of "What the method cannot see" and "How far the bound can fail" against the new file
   and correct it. The S0 figures (535 and 415 of 20,000) stay, cited to the spike, beside
   the new run's own figures for the same cells.
7. **Set `RATE_5_10` and `RATE_7_21`** from the new file by the rule in the record's
   "Coverage of the bound" section, and regenerate the snapshots that carry them.

## Done when

- The full self-check has run and every gate passed (give the count of gates), or you
  stopped at a failed gate as item 5 says.
- `.venv/bin/pytest -o addopts='' -q tests/unit/logs tests/unit/docs` passes except
  `test_example_output_is_real_and_labelled` (the recipe; another task).
- `.venv/bin/ruff format --check .`, `.venv/bin/ruff check .`, `.venv/bin/basedpyright` clean.
- `.venv/bin/python bench/make_log_example.py --check` passes.
- `shasum -a 256 -c FROZEN.sha256` reports only `docs/STATISTICS_LOGS.md` and
  `src/arci/logs/schema.py`.

## Final message

The gate summary line; one table: each new gate cell with its count; the worst
report-only cells; the two rate constants and the rows they come from; elapsed time; the
commands with their last lines; anything not run; anything in the statistics document
that the run contradicts. No long logs.
