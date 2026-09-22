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

Supported range: `alpha` in [1e-6, 0.5], and the per-arm tail `alpha / (4K)` must be at least
2.5e-7, that is `alpha >= K x 1e-6`. Outside it the gate returns `ERROR`; it never raises.

## Rule

For each condition, with `x_A`, `x_B` = number of trials whose outcome is `PASS`:

0. A condition containing any `ceiling` fault is descriptive only: it is reported with
   `is_gating = false`, excluded from K and from the statistical verdict below. ERROR and
   hard-invariant overrides still apply to it. K counts gating conditions only, and an experiment
   with no gating condition is `ERROR`.
1. Per-arm confidence `c = 1 - alpha / (2K)`.
2. Two-sided Clopper-Pearson interval at confidence `c` for each arm: `[L_A, U_A]`, `[L_B, U_B]`.
3. Bounds on `D = p_B - p_A`: `[L, U] = [L_B - U_A, U_B - L_A]`. By Bonferroni these cover D with
   probability at least `1 - alpha/K`, and all K conditions simultaneously with at least `1 - alpha`.
4. Condition verdict (`arci.gate.classify(L, U, delta)`): `PASS` iff `L > -delta`. `BLOCK` iff
   `U < -delta`. Otherwise `INCONCLUSIVE`. Both inequalities are strict.

Steps 1 to 3 are the default, `interval_method: clopper_pearson`. The optional
`interval_method: newcombe` replaces them: per-arm Wilson intervals `[l_A, u_A]`, `[l_B, u_B]` at
confidence `1 - alpha/K` (`z` at `1 - alpha/(2K)`), no continuity correction; with `a = x_A/n`,
`b = x_B/n`, `d = b - a`: `L = d - sqrt((b - l_B)^2 + (u_A - a)^2)` and
`U = d + sqrt((u_B - b)^2 + (a - l_A)^2)` (Newcombe's hybrid score interval, method 10). Step 4 and
everything after it are unchanged. The method is frozen in the manifest before execution and is
printed in every decision and report. It is an approximate interval whose calibration is checked
by exact enumeration (below), not proved. The claim is exactly this: both directional errors were
<= 0.05 at the enumerated points with alpha 0.05, delta 0.10, K=1 and N in {20, 50, 100, 200, 400},
for independent arms, plus the seeded correlated-arm simulation at N=200. Other alpha, delta, K,
N, probabilities between grid points and stronger dependence are not validated. Under strong
between-arm dependence, or outside that domain, keep the default.
5. Any candidate trial with a hard invariant violation makes that condition `BLOCK`, whatever the
   rates say.

Experiment verdict, in priority order:

1. `ERROR` if the manifest's own seal is invalid; if any trial has outcome `ERROR`; if the trial set is not exactly the schedule
   `arci.schedule.build_schedule(manifest)` (missing, duplicated or unknown trial ids; a trial whose
   experiment id, task id, arm, pair id, condition id, seed or `spec_sha256` differs from its
   scheduled spec); if any trial's seal is invalid; or if there is no gating condition. An invalid
   experiment can never PASS.
2. `BLOCK` if any condition is `BLOCK`.
3. `INCONCLUSIVE` if any condition is `INCONCLUSIVE`.
4. `PASS` only if every gating condition is `PASS` and no ERROR or candidate hard-invariant
   override applies. Descriptive (ceiling) conditions never decide this.

Exit codes: PASS 0, BLOCK 1, INCONCLUSIVE 2, ERROR 3.

## What the verdicts mean

- `PASS`: the candidate is non-inferior to the baseline within `delta`. It says nothing about
  absolute reliability.
- `BLOCK`: the candidate is worse than the baseline by more than `delta`, or broke a hard invariant.
- `INCONCLUSIVE`: not enough evidence either way. CI stays non-green. No regression is claimed.

## Discipline

- The decision rule (`alpha`, `delta`, `interval_method`) is bound into every trial's identity
  (`spec_sha256`), so a manifest resealed after the run with a different rule no longer matches its
  trials and the gate returns `ERROR`. Choosing the rule after the data is not merely forbidden; it
  is detected.
- Evaluate once, at the frozen `n_per_arm`. No peeking, no outcome-dependent extension.
- Every run is kept. A new experiment id does not reset error control and does not license
  retrying an unchanged candidate until it passes. The manifest author supplies
  `Manifest.prior_runs`; those ids are copied into the decision and the Markdown report (not the
  JUnit file). v0.1 does not discover earlier runs by itself and does not enforce a cross-run error
  budget: that discipline is the author's.
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

For `newcombe`, `bench/selfcheck.py --method newcombe` additionally sweeps the boundary
`p_B = p_A - delta` and the no-change line `p_B = p_A` (with offsets of 0.001 and 0.01 on both
sides) for `p_A` from 0.5 to 0.99 in steps of 0.01 and N in {50, 100, 200, 400}, enumerating every
count pair, and reports the maximum false-PASS on and below the boundary and the maximum
false-BLOCK on and above it. Both must be `<= alpha`; the bench exits non-zero otherwise.

Reference points (exact enumeration, alpha 0.05, delta 0.10, K=1), as (PASS, BLOCK, INCONCLUSIVE):
0.95 vs 0.95 at N=200: (0.889, 0.000, 0.111). 0.95 vs 0.65 at N=200: (0.000, 0.985, 0.015).
0.95 vs 0.75 at N=200: (0.000, 0.365, 0.635). 0.95 vs 0.85 at N=200: (0.001, 0.000, 0.999).
0.80 vs 0.80 at N=200: (0.218, 0.000, 0.782). At p_A=0.95, p_B=0.65 and N=20,
P(INCONCLUSIVE) = 0.992: small runs of realistic agents almost never decide. (A total collapse
still does: 1.0 vs 0.0 at N=20 is BLOCK with probability 1.) The rule is conservative by design: mid-range success rates need larger N to reach PASS.

## The two methods side by side (exact enumeration, alpha 0.05, delta 0.10, K=1)

| baseline -> candidate | N | Clopper-Pearson: PASS / BLOCK | Newcombe: PASS / BLOCK |
|---|---:|---|---|
| 0.95 -> 0.95 | 200 | .889 / .000 | .989 / .000 |
| 0.95 -> 0.95 | 100 | .443 / .000 | .832 / .000 |
| 0.80 -> 0.80 | 200 | .218 / .000 | .706 / .000 |
| 0.95 -> 0.75 | 200 | .000 / .365 | .000 / .838 |
| 0.95 -> 0.65 | 50 | .000 / .205 | .000 / .752 |
| 0.94 -> 0.77 (the real run) | 400 | .000 / .372 | .000 / .829 |
| 0.95 -> 0.85 (the margin) | 200 | .001 / .000 | .025 / .022 |

Worst directional errors over the boundary sweep (N 20 to 400): Clopper-Pearson false-PASS 0.004,
false-BLOCK 0.001; Newcombe false-PASS 0.031 (N=20) and 0.026 (N >= 200), false-BLOCK 0.027. So
Clopper-Pearson spends about a tenth of the alpha it is allowed, which is where its low power comes
from; Newcombe spends a little over half. Newcombe's directional errors sit slightly above the
one-sided nominal 0.025: it is calibrated to alpha, not exact.

## Not in v0.1

Adaptive or sequential stopping (needs confidence sequences), Newcombe and Fisher procedures,
Bayesian posteriors, bootstrap, task-clustered hierarchical aggregation.
