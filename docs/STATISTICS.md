# The gate's statistical contract (v0.1)

FROZEN. This is the decision procedure `arci.gate.decide` implements. Nothing else decides.

## Unit of analysis

One prespecified task under one prespecified fault condition. Success is binary and graded by an
oracle that is independent of the agent's own claim. Trials are independent across trial ids and
start from reset state. Baseline and candidate may share scenario seeds (pairs); the rule below
stays valid under that dependence.

## Frozen before execution (the manifest)

`alpha` (default 0.05), non-inferiority margin `delta` (default 0.10), `n_per_arm` (default 200,
supported range 1 to 10000, no extension after the fact), the K conditions, seeds, fixture hashes.
The margin is deliberately coarse. It is not a universal production tolerance.

## Rule

For each condition, with `x_A`, `x_B` = number of trials whose outcome is `PASS`:

1. Per-arm confidence `c = 1 - alpha / (2K)`.
2. Two-sided Clopper-Pearson interval at confidence `c` for each arm: `[L_A, U_A]`, `[L_B, U_B]`.
3. Bounds on `D = p_B - p_A`: `[L, U] = [L_B - U_A, U_B - L_A]`. By Bonferroni these cover D with
   probability at least `1 - alpha/K`, and all K conditions simultaneously with at least `1 - alpha`.
4. Condition verdict: `PASS` iff `L > -delta`. `BLOCK` iff `U < -delta`. Otherwise `INCONCLUSIVE`.
5. Any candidate trial with a hard invariant violation makes that condition `BLOCK`, whatever the
   rates say.

Experiment verdict, in priority order:

1. `ERROR` if any trial has outcome `ERROR`, if any scheduled trial is missing, if any trial id is
   duplicated or unknown, or if an arm's trial count differs from `n_per_arm`. An invalid
   experiment can never PASS.
2. `BLOCK` if any condition is `BLOCK`.
3. `INCONCLUSIVE` if any condition is `INCONCLUSIVE`.
4. `PASS` only if every condition is `PASS`.

Exit codes: PASS 0, BLOCK 1, INCONCLUSIVE 2, ERROR 3.

## What the verdicts mean

- `PASS`: the candidate is non-inferior to the baseline within `delta`. It says nothing about
  absolute reliability.
- `BLOCK`: the candidate is worse than the baseline by more than `delta`, or broke a hard invariant.
- `INCONCLUSIVE`: not enough evidence either way. CI stays non-green. No regression is claimed.

## Discipline

- Evaluate once, at the frozen `n_per_arm`. No peeking, no outcome-dependent extension.
- Every run is kept. A new experiment id does not reset error control and does not license
  retrying an unchanged candidate until it passes. `Manifest.prior_runs` lists earlier experiments
  on the same candidate and is copied into the decision and the report.
- Unplanned slices are descriptive only. Never pool different tasks as if they were IID trials.
- Wilson intervals appear in reports for readability. They never decide.
- Small-N honesty: zero violations in 20 trials still allows a 13.9% one-sided 95% upper bound;
  showing a rate below 0.5% needs at least 598 clean trials. Runs with N=20 are exploratory.

## Calibration

`bench/selfcheck.py` reports, by exact enumeration over independent binomial arms (and by seeded
simulation for positively correlated arms), the probability of PASS, BLOCK and INCONCLUSIVE for a
grid of `(p_A, p_B, N)`, including the boundary `p_B = p_A - delta`. At the boundary, P(PASS) is the
false-PASS rate and must not exceed `alpha`; for `p_B >= p_A`, P(BLOCK) is the false-BLOCK rate and
must not exceed `alpha`. We publish measured numbers. We promise none in advance.

## Not in v0.1

Adaptive or sequential stopping (needs confidence sequences), Newcombe and Fisher procedures,
Bayesian posteriors, bootstrap, task-clustered hierarchical aggregation.
