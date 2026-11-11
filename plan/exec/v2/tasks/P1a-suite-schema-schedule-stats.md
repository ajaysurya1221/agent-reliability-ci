# TASK P1a: suite schema, schedule and statistics

Lane A. Worktree: `/Users/ajay/Developer/.arci-worktrees/wt-v2-suite` (branch `v2/suite`,
cut from `main` at v1.0.0). Work only there.

## Read first

1. `AGENTS.md` in the worktree. Its hard rules bind you.
2. `/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/tasks/P1-CONTRACT.md`: the
   contract. Sections 1 to 4 are this task. Sections 5 and 6 are the next task; read them
   so your code fits, but do not build them.
3. `/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/adr-0011-draft.md`: the accepted
   design record the contract comes from.
4. `src/arci/schema.py`, `src/arci/schedule.py`, `src/arci/hashing.py`, `src/arci/stats.py`.
5. Reference code, reviewed in phase 0, under
   `/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/spikes/`: `s1/suite_stats.py`,
   `s1c/balanced.py`, `s1c/PROOF.md`, `s1c/RESULTS.md`, `s1c/results.json`. Port ideas; the
   product code imports nothing from there.

## You own (create; touch nothing else)

- `src/arci/suite_schema.py`
- `src/arci/suite_schedule.py`
- `src/arci/suite_stats.py`
- `tests/unit/suite/` (with `__init__.py`)

## What done looks like

1. The three modules implement sections 2, 3 and 4 of the contract exactly: names,
   signatures, error types, and the arithmetic. Where the contract is silent on something
   a caller could observe, stop and report the ambiguity; do not guess.
2. Unit tests under `tests/unit/suite/` cover at least:
   - every validation rule of section 2, one failing case each;
   - the digest: unchanged under reordering of tasks and conditions and under a change to
     `created_at`, `experiment_id` or `record_sha256`; changed by a change to any other
     field (parametrise over every other field);
   - seeds and arm order recomputed in the test with `hashlib` directly; `fixed` gives one
     seed per cell in every round; `per_round` differs between rounds; both arms share it;
   - `build_suite_round` and `build_suite_schedule`: counts, order, ids, uniqueness of
     `spec_sha256`, and that a changed rule changes every `spec_sha256`;
   - `wealth` against a pair-by-pair `Fraction` product on random count triples (seeded
     `random` in tests is fine), and against the spike's known values;
   - the floors: 79 pairs at the defaults; `check_suite_plan` cases (a) and (b) and the
     warning;
   - `wealth_text` on values below 1, between 1 and 10, large, and exact powers of ten;
   - `operating_characteristics`: mass sums to 1; the two 20-cell rows in section 4 as exact
     fractions from the two matching Table C records in `s1c/results.json`; error at most `alpha / 2` on the margin for a
     heterogeneous grid; agreement with brute-force enumeration on a tiny grid (2 cells,
     2 or 3 rounds).
3. These all pass, run from the worktree root:
   ```sh
   .venv/bin/pytest tests/unit/suite -q
   .venv/bin/pytest -q                      # the whole existing suite, unchanged
   .venv/bin/ruff format --check .
   .venv/bin/ruff check .
   .venv/bin/basedpyright
   shasum -a 256 -c FROZEN.sha256
   ```
4. `import arci.suite_schema` must not import `arci.suite_stats`. No new dependency.
   Python 3.11 syntax and typing (the project supports 3.11 to 3.14).

## Rules specific to this task

- Do not edit any existing file. If an existing file blocks you, stop and report it.
- No git command that changes state. No network.
- No floating-point arithmetic in any statistical decision: wealth, thresholds, crossings,
  floors and operating characteristics are exact. Existing finite JSON floats (budgets,
  task content, fault parameters) pass through canonical hashing untouched, and the two
  inert mirror fields `TrialSpec.alpha` and `TrialSpec.delta` are floats by the frozen
  schema.
- If you believe the contract is wrong, do not silently fix it: implement the contract
  where you can, keep a failing test that shows the problem, and put it first in your
  report.

## Report (your final message, under 60 lines)

Files created; the last lines of each command in item 3; every place the contract was
silent and what you did there; anything in the contract you think is wrong or ambiguous; run time of
`operating_characteristics` for 20 cells and 400 pairs; risks.

## Sandbox note

You run in a sandbox without network. Some existing tests open loopback sockets. If a test
outside your files fails only because the sandbox refuses a socket, say so in the report
with the test name and the error line; the orchestrator re-runs the whole suite outside the
sandbox. Do not skip, edit or mark any existing test.
