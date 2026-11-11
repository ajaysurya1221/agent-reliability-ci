# TASK P1b: suite gate, calibration bench and statistics document

Lane A. Worktree: `/Users/ajay/Developer/.arci-worktrees/wt-v2-suite` (branch `v2/suite`).
Work only there. Task P1a is done and reviewed: `src/arci/suite_schema.py`,
`src/arci/suite_schedule.py`, `src/arci/suite_stats.py` and `tests/unit/suite/` exist and
pass. Build on them.

## Read first

1. `AGENTS.md` in the worktree.
2. `/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/tasks/P1-CONTRACT.md`,
   sections 5 and 6. Section 5 was revised twice after your read-only reviews
   (normalise first, eight ordered checks, field rules, last resort). Read it afresh.
3. `/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/adr-0011-draft.md` (accepted).
4. `src/arci/gate.py` (v1 gate: the shape to follow, not to edit), `bench/selfcheck.py`,
   `tests/unit/selfcheck/`, `docs/STATISTICS.md` (style and level of the frozen v1 document).
5. `/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/spikes/s1c/PROOF.md`,
   `RESULTS.md`, `results.json`, and `plan/exec/v2/reviews/S1c-review.md`.

## You own

- `src/arci/suite_gate.py` (new)
- `bench/selfcheck_suite.py` (new)
- `docs/STATISTICS_SUITE.md` (new)
- `tests/unit/suite/test_gate.py`, `tests/unit/selfcheck/test_selfcheck_suite.py` (new);
  you may add builders to `tests/unit/suite/helpers.py`
- `src/arci/suite_schema.py`, `suite_schedule.py`, `suite_stats.py`: only if this task
  shows a defect in them. Say exactly what and why in the report.

## What done looks like

1. **`suite_gate.py`** implements contract section 5 exactly: `evaluate_rounds`,
   `decide_suite`, `replay_suite_decision`, the reason strings character for character, the
   check order and skip rules, the field rules and the last resort. It imports no v1 gate
   internals.
2. **Unit tests** (`tests/unit/suite/test_gate.py`) cover every row of both tables in
   section 5, every round-verdict rule, the errored-pair scoring, each skip rule, the fixed
   template, the lone-surrogate cases, determinism, order-independence of the supplied
   trials, and replay of a decision. Build stores from `build_suite_schedule` with
   synthetic sealed envelopes; no process is spawned.
3. **A performance guard:** `decide_suite` on a full 100,000-pair store is out of scope for
   a unit test, but a 20-cell, 20-round store must decide in well under a second, and the
   per-round wealth must come from cumulative counts, not from re-multiplying pairs.
4. **`bench/selfcheck_suite.py`**: `python -m bench.selfcheck_suite` exits 0 only if every
   check holds and prints one table per check, in the manner of `bench/selfcheck.py`. All
   arithmetic exact. Checks:
   - both directional errors at most `alpha / 2` on the margin (suite mean difference
     exactly `-delta`) for grids of 1, 2, 5, 10 and 20 cells, with homogeneous laws and
     with laws that differ strongly between cells (some cells far below the margin, others
     above), and for arms that are positively and negatively dependent within a pair;
   - the same just inside each null (a mean slightly worse than `-delta` for PASS, slightly
     better for BLOCK);
   - the rows of ADR 0011's operating-characteristics table reproduce as the exact
     fractions in `spikes/s1c/results.json` (copy the fractions into the bench as
     literals);
   - the floors: 79 pairs, and the earliest rounds stated in the contract;
   - the gate and the enumeration agree: for a tiny grid, enumerate every outcome path by
     brute force through `decide_suite` on synthetic stores and compare the verdict
     probabilities with `operating_characteristics`;
   - a report-only table (no threshold asserted) of PASS and BLOCK power for 50, 100, 200
     and 400 cells under the default budget, at 0.95 against 0.95 and 0.95 against 0.75,
     if it computes in reasonable time; if a row is too slow, print that it was skipped
     and why. This answers ADR 0011 open point 3.
   A `--quick` flag may trim the grids for the unit test; the default run is the full one
   and must finish in under ten minutes on a laptop. Print the run time.
5. **`docs/STATISTICS_SUITE.md`** is the statistical contract for suite experiments, to be
   frozen. Plain, exact, and self-contained: the estimand; cells and balanced rounds; the
   two wealth processes and the verdict rule with the round-end priority; the proof
   written out in full (AM-GM step, supermartingale, Ville, the mixture, stopping and the
   cap, why both cannot cross), not cited away; every assumption of ADR 0011 item 6 with
   what breaks it, the common-mode limit stated plainly; the two seed modes and the exact
   per-round condition for `per_round`; errored pairs and why worst-case scoring keeps
   both bounds; hard invariants and what the false-BLOCK statement covers; the limits
   enforced before a run; measured operating characteristics with their source; what a
   release may and must not say (ADR 0011). It must not change or contradict
   `docs/STATISTICS.md`. Reference: Waudby-Smith and Ramdas, arXiv:2010.09686v7, section
   2.2 (Theorem 1) and section 4 (equation 23); say that the mixture and round steps are
   this project's own derivations. No claim that is not proved here or measured in the
   bench.
6. These all pass, from the worktree root:
   ```sh
   .venv/bin/pytest tests/unit/suite tests/unit/selfcheck -q
   .venv/bin/python -m bench.selfcheck_suite
   .venv/bin/pytest -q
   .venv/bin/ruff format --check .
   .venv/bin/ruff check .
   .venv/bin/basedpyright
   shasum -a 256 -c FROZEN.sha256
   ```

## Rules specific to this task

- Edit no existing tracked file. No git command that changes state. No network.
- No floating-point arithmetic in any decision or any bench assertion. Floats may appear
  only in printed tables.
- Where the contract is silent on something a caller could observe, stop and report it.
- If you believe the contract or the proof is wrong, do not silently fix it: keep a failing
  test or bench check that shows the problem and put it first in your report.

## Sandbox note

You run in a sandbox without network. Some existing tests open loopback sockets or call
`ps`. If a test outside your files fails only for that reason, say so with the test name;
the orchestrator re-runs the whole suite outside the sandbox. Do not skip, edit or mark any
existing test.

## Report (your final message, under 60 lines)

Files created or changed; the last lines of each command in item 6; the bench's run time
and its largest observed directional error per grid size; any place the contract was
silent; anything in the contract or proof you think is wrong; risks.
