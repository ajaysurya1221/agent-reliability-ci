# TASK S1: suite statistics spike (phase 0, no product code)

You are the implementer. The orchestrator re-runs everything you report; your report is not
acceptance evidence. Read `AGENTS.md` first and obey its hard rules.

## Owned files

Only `plan/exec/v2/spikes/s1/`. Create nothing and edit nothing anywhere else. No changes under
`src/`, `tests/`, `docs/` or `bench/`. No git commands that change state. No network. Standard
library only. Run Python as `.venv/bin/python`.

## Read first

`docs/STATISTICS.md` (the v1 rule and its published operating characteristics),
`bench/selfcheck.py` (how v1 calibrates by exact enumeration), `src/arci/stats.py` (integer
and exact arithmetic style), `plan/exec/v2/PLAN.md` section 2 "Statistical design".

## What is being tested

A pre-registered suite gate for v2. Proposed contract:

- A grid of T tasks by K fault conditions. Pair i draws one cell uniformly and independently
  from the grid. Both arms run on that cell. `d_i = candidate_success - baseline_success`, so
  `d_i` is in {-1, 0, +1}. Estimand: `Delta = E[d]`, the uniform-weight suite-mean difference.
- Margin `delta` (default 0.10), `alpha` (default 0.05).
- Two one-sided betting tests, each at level `alpha/2`, error control by Ville's inequality:
  - PASS test, null `Delta <= -delta`: wealth `W_plus = prod(1 + lam_plus_i * (d_i + delta))`,
    `lam_plus_i` in `[0, 1/(1 - delta)]`, predictable. PASS when `W_plus >= 2/alpha`.
  - BLOCK test, null `Delta >= -delta`: wealth `W_minus = prod(1 - lam_minus_i * (d_i + delta))`,
    `lam_minus_i` in `[0, 1/(1 + delta)]`, predictable. BLOCK when `W_minus >= 2/alpha`.
- Checked in schedule order at checkpoints every `batch` pairs. Stop at the first decisive
  checkpoint. INCONCLUSIVE only at the pre-registered `max_pairs`.
- The decision path must be bit-reproducible across platforms: rational stakes, `Fraction` or
  integer arithmetic, integer threshold comparison. No `math.log`, `math.sqrt` or float
  comparison in the decision path. A float fast path is allowed inside the simulator only if a
  test shows it agrees with the exact path on every decision in a golden-vector set.

Challenge any part of this contract that is wrong. If the algebra above has an error, say so
and fix it in your deliverables.

## Key simplification to verify or refute

Under uniform independent cell draws, the `d_i` are i.i.d. trinomial with probabilities
`(p_minus, p_zero, p_plus)` that are mixtures over cells. If that holds, task heterogeneity
and between-arm correlation enter only through those three numbers, and for a fixed stake the
wealth depends only on the counts of +1 and -1. Then every operating characteristic is
computable exactly by dynamic programming over counts with absorbing states, as
`bench/selfcheck.py` does for v1. State clearly whether this holds, and what breaks it.

## Deliverables (all inside the owned directory)

1. `suite_stats.py`: the reference decision procedure. Pure functions, standard library,
   exact arithmetic. Input: `alpha`, `delta`, `batch`, `max_pairs`, the stake rule, and the
   ordered list of `d_i`. Output: verdict, stopping pair count, and the wealth history at
   checkpoints as exact rationals.
2. `suite_stats_sim.py`: exact enumeration and seeded simulation. Flags: `--quick` (finishes
   in under 60 seconds) and the full run (target under 30 minutes on 15 cores; use
   `multiprocessing`). Writes `results.json` and prints the tables. Exits non-zero if any pass
   condition below fails.
3. `CONTRACT.md`: one page. Each assumption the validity argument needs, stated as a
   requirement on the future schedule and runner, with what detects a violation or the
   statement that nothing does. Cite the published results you rely on by author, year and
   theorem or section. Mark each line PROVED-BY-CITATION, CHECKED-BY-ENUMERATION,
   CHECKED-BY-SIMULATION or ASSUMED.
4. `RESULTS.md`: the tables below, the recommended stake rule and defaults for `batch` and
   `max_pairs`, and a plain go / no-go against each pass condition.
5. `test_suite_stats.py`: pytest tests for the reference procedure, including golden vectors
   and the float-versus-exact agreement test if a float path exists.

## Stake rules to compare

At least: (a) one fixed rational stake per test; (b) a small pre-registered mixture of fixed
stakes (average of several wealth processes, still exact); (c) one predictable adaptive rule
that uses only past observations and stays rational. Recommend one. Simplicity counts: if the
mixture is within about 15 percent of the adaptive rule on expected pairs, prefer the mixture.

## Tables required

A. Error control, exact where possible. On the boundary `Delta = -delta`, sweep `p_zero` from
   0.0 to 0.95 and report max P(PASS). On and above no-change (`Delta >= 0`), and anywhere
   `Delta >= -delta`, report max P(BLOCK). Below the boundary report max P(PASS). For
   `max_pairs` in {50, 100, 200, 400, 1000} and `batch` in {1, 10, 20}.
B. Sampling-implementation check by seeded simulation: T in {10, 20, 50, 100}, K in {1, 3};
   equal and mixed task difficulty; independent, positively correlated and negatively
   correlated arms; a regression concentrated in a few tasks with the suite mean exactly on
   the boundary. At least 20,000 replications per point. Report the simulated error with an
   exact binomial 99 percent upper bound.
C. Power and cost: for (baseline, candidate) in (0.95, 0.95), (0.95, 0.75), (0.95, 0.65),
   (0.80, 0.80), (0.95, 0.85): P(PASS), P(BLOCK), P(INCONCLUSIVE), and mean, median and 90th
   percentile stopping pairs, for independent arms and for a strongly positively correlated
   case, at `max_pairs` in {100, 200, 400}.
D. Side by side with v1 at 200 pairs per condition, using the numbers published in
   `docs/STATISTICS.md` for Clopper-Pearson and Newcombe (fixed and sequential). Say exactly
   where v2 is better, equal or worse. Count cost in agent sessions (two per pair).

## Pass conditions

1. Table A: every directional error is at or below `alpha/2` for the recommended rule (exact).
2. Table B: every 99 percent upper bound is at or below `alpha`.
3. The exact enumeration and the simulation agree within Monte Carlo error on at least five
   shared points.
4. `.venv/bin/pytest plan/exec/v2/spikes/s1 -q` passes; `.venv/bin/ruff format --check` and
   `.venv/bin/ruff check` are clean on the owned directory.
5. `shasum -a 256 -c FROZEN.sha256` still passes.

A failed pass condition is a valid result. Report it plainly; do not tune until it passes
without saying what you changed.

## Final message

Files created, the exact commands you ran with their last lines, the go / no-go per pass
condition, anything you could not do, and risks. No long logs.
