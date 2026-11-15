# S0: spike for `arci-logs/2` (go or no-go before product code)

Read `AGENTS.md` in the worktree `/Users/ajay/Developer/.arci-worktrees/wt-v2-logs`
(branch `v2/logs2`). Then read, in this order:

1. `/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/logs2/DESIGN-MEMO.md` (the
   decisions; M2 and M4 are what this spike tests);
2. `docs/STATISTICS_LOGS.md` and `docs/results/logs-selfcheck.md` in the worktree;
3. `src/arci/logs/measures.py`, `decide.py`, `rank_test.py`, `records.py`, and
   `bench/selfcheck_logs.py`.

## Rules

- **Change nothing in the worktree.** No product code, no tests, no docs. No git command
  that changes state. Never open anything under `~/.claude` or `~/.codex`. No network.
- All scratch code and the report go under
  `/private/tmp/claude-501/-Users-ajay-Developer-agent-reliability-ci/39ca2335-7a5a-47d9-a374-69d92a47e1d0/scratchpad/s0/`
  (create it). Import the package from the worktree with
  `/Users/ajay/Developer/.arci-worktrees/wt-v2-logs/.venv/bin/python` run from the worktree.
- Seeds: base `17112026`; every row of every table names its seed. No unseeded randomness.
- Counts are exact; give each rate as `k/n = value` with a Wilson 95% interval, the way
  the existing self-check does. Reuse its generator and helpers by import where you can.
- Keep total compute under about 60 minutes; use processes in parallel as the existing
  self-check does. If a gate needs more, run what fits, say what was cut, and do not
  shrink a gated cell below 20,000.

## What to build in scratch

**The M2 choice.** A function that, from response records and the window, returns the
setting with the most main-thread responses in the after period (ties: the raw pair that
sorts first as text). Then the production path decides that setting (use the existing
override the code has for `--model` and `--effort`; do not copy the decision rule).

**History generator with setting changes.** A 98-day window. Two or three settings:
an old one used on early days until a change day, the current one from a change day that
lies inside the before period, and in half of the histories a third, minor setting with a
few responses on some after-days. Each setting has its own fixed level (for example
medians near 1000, 500 and 250 reasoning tokens) and its own share of zero counts.
Responses per day vary (for example 20 to 120). The current setting has `b` usable
before-days and `a` usable after-days for the designs `a/b` in 5/10, 7/21, 14/16, 14/42.
Day-to-day spread on the log scale 0.45, days independent, unless a gate says otherwise.

## Gates (go needs G1 and G4)

**G1. Error rates with setting changes, independent days.** 20,000 histories per design.

- Null: nothing changes inside any setting. Count histories whose tool result is REAL
  DROP. Gate: at most 566 of 20,000 (2.83%) in every design.
- Margin: in the current setting, one measure's after-days are moved toward worse by
  exactly its margin. Count NO DROP. Gate: at most 566 of 20,000 in every design. Do it
  for the token measure and for one share measure.
- You may build the day tables of the chosen setting straight from the generator for the
  20,000, as the existing self-check does, **if** you also run at least 500 histories per
  design through response records, the M2 choice and the production path, and show that
  the chosen setting is the current one every time and that day table and result agree.
- Report how often the old rule (most responses over both periods) would have picked the
  old setting in these histories.

**G2. Report only: where the restated assumption can fail.**

- G2a: within the current setting, busy days have lower reasoning medians (a clear
  correlation between responses per day and the day value), same in both periods. Wrong
  REAL DROP at 14/16 and 7/21, 20,000 each.
- G2b: the first five days of the current setting are 15% higher than its later days
  ("new model" behaviour). Wrong REAL DROP at 14/16 and 7/21, 20,000 each. This breaks
  the assumption on purpose; the number goes into the docs as a stated limit.

**G3. Report only: power.** Designs 5/10, 14/16, 14/42; drops of 33%, 45% and 55% in
reasoning tokens; spread 0.40 and 0.45; rule as built. Run each cell until 2,000
histories have been tested, and report tested and generated counts separately.

**G4. The kept day table (M4).** Implement the write rule and the use rule as pure
functions over rows `(tool, offset, setting, day) -> counts`. Property test, at least 500
random histories: runs happen on random days; between runs, responses older than 30 days
are deleted, sometimes a whole day and sometimes only part of a day. Assert: when no gap
between runs is longer than 29 days, the day table used on the last run equals the table
computed from the full, undeleted history for every day from the first run on. Report
what differs when gaps are longer. Also test: a change of UTC offset makes the old rows
ignored and counted, never mixed.

## Report

`REPORT.md` in the scratch directory, plain words, no em dashes: one table per gate with
counts, seeds and intervals; GO or NO-GO with the reason in the first line; the commands
to re-run each table and their run times; anything that surprised you; anything in the
memo that turned out unclear or wrong. Your final message: the first line of the report,
the worst cell of each gate, what you could not do.
