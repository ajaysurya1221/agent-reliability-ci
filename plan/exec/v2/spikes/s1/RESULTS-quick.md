# S1 suite statistics spike

Run: QUICK SMOKE ONLY, 2.4 seconds including checks.
Standard library only; no network, product edits, or git-state changes.

## Decision and preregistered comparison

Proposed default: equal mixture q=(1/8,1/4,1/2,3/4), with lambda_plus=q/(1-delta)
and lambda_minus=q/(1+delta); alpha=1/20, delta=1/10, batch=10, max_pairs=400.
A final partial batch is a checkpoint. Maximum cost is 800 agent sessions per suite,
not per cell. This is a budget choice, not a guarantee of a verdict or task coverage.
Mixture/adaptive capped mean-cost ratio: min 0.742, max 1.167.
Mixture within 15% at every comparison point: NO.
Recommend the mixture: exact count-based calibration and simple fixed stakes.
It has lower or equal measured capped mean cost at 8/10 comparison points. The 15% condition above is not concealed or relaxed.
The largest disadvantage is the deterministic d=0 positive-coupling case: 70 pairs
versus adaptive's 60. This simplicity/cost tradeoff does not imply universal superiority.
No stake parameters were tuned in response to errors. All three rules and the grids
are constants in the source. Expected pairs below are capped stopping times, including
INCONCLUSIVE at the cap; they are not uncapped expected time to a decision.

| pass condition | result |
|---|---|
| 1_A_exact_error_control | GO |
| 2_B_upper99_le_alpha | NO-GO |
| 3_five_shared_points | GO |
| 4_tests_and_lint | GO |
| 5_frozen | GO |

Quick mode returns nonzero: the full Table B requirement is not satisfied.

## A. Certified error enumeration

| cap | batch | boundary PASS | null BLOCK | no-change-or-above BLOCK | below-boundary PASS supremum | max lost mass |
|---:|---:|---:|---:|---:|---:|---:|
| 50 | 1 | 0.01004181 | 0.01032611 | 0.00247805 | 0.01004181 | 0.00e+00 |
| 50 | 10 | 0.00431995 | 0.00347052 | 0.00047946 | 0.00431995 | 0.00e+00 |
| 50 | 20 | 0.00343241 | 0.00287984 | 0.00038709 | 0.00343241 | 0.00e+00 |
| 100 | 1 | 0.01242724 | 0.01272454 | 0.00261292 | 0.01242724 | 0.00e+00 |
| 100 | 10 | 0.00617301 | 0.00576470 | 0.00053794 | 0.00617301 | 0.00e+00 |
| 100 | 20 | 0.00440802 | 0.00409690 | 0.00035805 | 0.00440802 | 0.00e+00 |

Entries are exact rational probabilities, displayed rounded to eight decimals;
the pass check uses the rationals in results.json. No Monte Carlo in A.
p_zero grid: 0, 1/2, 9/10, 19/20
At Delta=-.10, p_zero=.95 is infeasible (negative p_plus),
so it is recorded as a null-edge point Delta=-.05, not a fabricated boundary point.
For fixed p_zero, increasing Delta increases PASS and decreases BLOCK even with
first-stop absorption (pathwise monotone coupling). Boundary values therefore bound
all smaller means for false PASS and all larger means for false BLOCK. For p_zero<.90,
the strictly-below-boundary supremum equals the boundary value by continuity. At .90,
no smaller mean is feasible; that point is excluded from the below-boundary column.
The no-change line bounds all Delta>=0 at each grid p_zero. Between-grid p_zero
values are covered by the theorem, not an assertion of exhaustive enumeration.

## B. Actual cell-sampling simulations

Every point has suite mean exactly -.10, so BOTH directions count as errors.
Positive/negative mean the maximal feasible positive/negative Bernoulli coupling,
not a universal Pearson correlation coefficient. Cells are sampled with replacement.
99% bounds are one-sided Clopper-Pearson roots enclosed upward on a 2^-20 grid,
using exact integer binomial-tail comparisons. They are pointwise, not simultaneous.
Full B uses 20,000 replications at max_pairs=400, batch=10 at every point.

| T | K | difficulty | dependence | reps | false PASS | upper99 | false BLOCK | upper99 |
|---:|---:|---|---|---:|---:|---:|---:|---:|
| 10 | 1 | equal | independent | 1000 | 0.00600 | 0.014509 | 0.00700 | 0.015928 |
| 10 | 1 | equal | positive | 1000 | 0.00300 | 0.010011 | 0.00200 | 0.008380 |
| 10 | 1 | equal | negative | 1000 | 0.00500 | 0.013056 | 0.00700 | 0.015928 |
| 10 | 1 | mixed | independent | 1000 | 0.00700 | 0.015928 | 0.00900 | 0.018692 |
| 10 | 1 | mixed | positive | 1000 | 0.00400 | 0.011561 | 0.00000 | 0.004595 |
| 10 | 1 | mixed | negative | 1000 | 0.00500 | 0.013056 | 0.00600 | 0.014509 |
| 10 | 1 | concentrated | independent | 1000 | 0.00500 | 0.013056 | 0.00900 | 0.018692 |
| 10 | 1 | concentrated | positive | 1000 | 0.00500 | 0.013056 | 0.00000 | 0.004595 |
| 10 | 1 | concentrated | negative | 1000 | 0.00800 | 0.017322 | 0.01100 | 0.021378 |

## C. Power and cost, and stake comparison

Seeded Monte Carlo; each full-run row has 20,000 replications. Maximum Bernoulli
standard error is 0.00354 (roughly +/-0.00693 at 95%); means/quantiles are empirical.
Seeds and exact trinomial inputs are reproducible from source/results.json.
Positive uses the Frechet upper coupling (d=0 deterministically for equal arms).
The fixed comparator uses q=1/2. Adaptive uses ONLY previous outcomes, rational
mean/second-moment stakes damped by 1/2, clipped at 3/4 of the legal cap and rounded
down to 1/64-cap increments. No superiority claim beyond these scenarios.

| A -> B | dependence | rule | cap | PASS | BLOCK | INC | ERROR | mean pairs | median | p90 |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.95->0.95 | independent | fixed | 100 | 0.58900 | 0.00000 | 0.41100 | 0.00000 | 86.01 | 100 | 100 |
| 0.95->0.95 | independent | mixture | 100 | 0.51300 | 0.00000 | 0.48700 | 0.00000 | 84.92 | 100 | 100 |
| 0.95->0.95 | independent | adaptive | 100 | 0.32100 | 0.00000 | 0.67900 | 0.00000 | 91.83 | 100 | 100 |
| 0.95->0.95 | positive | fixed | 100 | 1.00000 | 0.00000 | 0.00000 | 0.00000 | 70.00 | 70 | 70 |
| 0.95->0.95 | positive | mixture | 100 | 1.00000 | 0.00000 | 0.00000 | 0.00000 | 70.00 | 70 | 70 |
| 0.95->0.95 | positive | adaptive | 100 | 1.00000 | 0.00000 | 0.00000 | 0.00000 | 60.00 | 60 | 60 |
| 0.95->0.75 | independent | fixed | 100 | 0.00000 | 0.27400 | 0.72600 | 0.00000 | 93.85 | 100 | 100 |
| 0.95->0.75 | independent | mixture | 100 | 0.00000 | 0.23100 | 0.76900 | 0.00000 | 93.58 | 100 | 100 |
| 0.95->0.75 | independent | adaptive | 100 | 0.00000 | 0.05000 | 0.95000 | 0.00000 | 99.21 | 100 | 100 |
| 0.95->0.75 | positive | fixed | 100 | 0.00000 | 0.35100 | 0.64900 | 0.00000 | 93.34 | 100 | 100 |
| 0.95->0.75 | positive | mixture | 100 | 0.00000 | 0.39700 | 0.60300 | 0.00000 | 91.22 | 100 | 100 |
| 0.95->0.75 | positive | adaptive | 100 | 0.00000 | 0.08300 | 0.91700 | 0.00000 | 98.90 | 100 | 100 |
| 0.95->0.65 | independent | fixed | 100 | 0.00000 | 0.87600 | 0.12400 | 0.00000 | 66.67 | 60 | 100 |
| 0.95->0.65 | independent | mixture | 100 | 0.00000 | 0.83200 | 0.16800 | 0.00000 | 67.54 | 60 | 100 |
| 0.95->0.65 | independent | adaptive | 100 | 0.00000 | 0.56400 | 0.43600 | 0.00000 | 85.39 | 100 | 100 |
| 0.95->0.65 | positive | fixed | 100 | 0.00000 | 0.97700 | 0.02300 | 0.00000 | 59.33 | 60 | 90 |
| 0.95->0.65 | positive | mixture | 100 | 0.00000 | 0.97300 | 0.02700 | 0.00000 | 57.73 | 60 | 80 |
| 0.95->0.65 | positive | adaptive | 100 | 0.00000 | 0.80000 | 0.20000 | 0.00000 | 77.81 | 80 | 100 |
| 0.80->0.80 | independent | fixed | 100 | 0.22000 | 0.00000 | 0.78000 | 0.00000 | 92.07 | 100 | 100 |
| 0.80->0.80 | independent | mixture | 100 | 0.15600 | 0.00100 | 0.84300 | 0.00000 | 94.50 | 100 | 100 |
| 0.80->0.80 | independent | adaptive | 100 | 0.04700 | 0.00000 | 0.95300 | 0.00000 | 98.90 | 100 | 100 |
| 0.80->0.80 | positive | fixed | 100 | 1.00000 | 0.00000 | 0.00000 | 0.00000 | 70.00 | 70 | 70 |
| 0.80->0.80 | positive | mixture | 100 | 1.00000 | 0.00000 | 0.00000 | 0.00000 | 70.00 | 70 | 70 |
| 0.80->0.80 | positive | adaptive | 100 | 1.00000 | 0.00000 | 0.00000 | 0.00000 | 60.00 | 60 | 60 |
| 0.95->0.85 | independent | fixed | 100 | 0.00400 | 0.00400 | 0.99200 | 0.00000 | 99.86 | 100 | 100 |
| 0.95->0.85 | independent | mixture | 100 | 0.00300 | 0.00200 | 0.99500 | 0.00000 | 99.80 | 100 | 100 |
| 0.95->0.85 | independent | adaptive | 100 | 0.00100 | 0.00000 | 0.99900 | 0.00000 | 99.95 | 100 | 100 |
| 0.95->0.85 | positive | fixed | 100 | 0.00300 | 0.00000 | 0.99700 | 0.00000 | 99.97 | 100 | 100 |
| 0.95->0.85 | positive | mixture | 100 | 0.00700 | 0.00000 | 0.99300 | 0.00000 | 99.88 | 100 | 100 |
| 0.95->0.85 | positive | adaptive | 100 | 0.00400 | 0.00000 | 0.99600 | 0.00000 | 99.90 | 100 | 100 |

## D. Published v1 comparison, K=1

v1 inputs below are the rounded published values in docs/STATISTICS.md, not reruns.
Fixed v1 costs 400 sessions. Sequential v1 uses looks 50/100/200. v2 rows use the
same 200-pair cap, independent arms, batch=10. Multi-task suite-mean and per-condition
v1 claims differ; this homogeneous K=1 comparison does not equate their guarantees.
At the margin both decisions are errors; fewer decisions there is better error control.
Higher/lower labels compare measured point estimates with the published rounded numbers;
they are not significance tests. Table C states Monte Carlo uncertainty.

| rates | method | PASS | BLOCK | expected sessions | comparison with v2 |
|---|---|---:|---:|---:|---|
| 0.95->0.95 | CP fixed | 0.889 | 0.0 | 400 | not in quick subset |
| 0.95->0.95 | Newcombe fixed | 0.989 | 0.0 | 400 | not in quick subset |
| 0.95->0.75 | CP fixed | 0.0 | 0.365 | 400 | not in quick subset |
| 0.95->0.75 | Newcombe fixed | 0.0 | 0.838 | 400 | not in quick subset |
| 0.95->0.65 | CP fixed | 0.0 | 0.985 | 400 | not in quick subset |
| 0.95->0.65 | Newcombe fixed | not published | 0.9998 | 400 | not in quick subset |
| 0.80->0.80 | CP fixed | 0.218 | 0.0 | 400 | not in quick subset |
| 0.80->0.80 | Newcombe fixed | 0.706 | 0.0 | 400 | not in quick subset |
| 0.95->0.85 | CP fixed | 0.001 | 0.0 | 400 | not in quick subset |
| 0.95->0.85 | Newcombe fixed | 0.025 | 0.022 | 400 | not in quick subset |
| 0.95->0.95 | CP sequential | 0.735 | not published | 350 | not in quick subset |
| 0.95->0.95 | Newcombe sequential | 0.969 | not published | 239 | not in quick subset |
| 0.95->0.65 | CP sequential | not published | 0.943 | 302 | not in quick subset |
| 0.95->0.65 | Newcombe sequential | not published | 0.9989 | 159 | not in quick subset |

Other v1 sequential scenarios are not published; no values were invented.
The full C table shows how increasing v2's cap to 400 trades additional sessions
for decisions. Strong-positive v2 cases are not compared with independent v1 numbers.

## Independent implementation checks

Float/reference corpus: 351 exact verdict/stopping-count agreements.
Five shared points use unrounded rational DP mass (not the enclosure optimization),
and independently generated cell simulations. Prespecified tolerance: five binomial
standard errors plus 1/reps, for each of PASS/BLOCK/INCONCLUSIVE.

| trinomial (-,0,+) | reps | exact PASS/BLOCK | simulated PASS/BLOCK | check |
|---|---:|---|---|---|
| 19/400, 181/200, 19/400 | 1000 | 0.498305/0.000000 | 0.513000/0.000000 | GO |
| 19/80, 29/40, 3/80 | 1000 | 0.000025/0.235352 | 0.000000/0.215000 | GO |
| 133/400, 127/200, 13/400 | 1000 | 0.000000/0.833916 | 0.000000/0.830000 | GO |
| 4/25, 17/25, 4/25 | 1000 | 0.147184/0.000045 | 0.156000/0.000000 | GO |
| 57/400, 163/200, 17/400 | 1000 | 0.004900/0.002714 | 0.006000/0.001000 | GO |

## Verification and limits

- pytest: exit 0; last lines: `['.............................                                            [100%]']`
- ruff_format: exit 0; last lines: `['6 files already formatted']`
- ruff_check: exit 0; last lines: `['All checks passed!']`
- basedpyright: exit 0; last lines: `['0 errors, 0 warnings, 0 notes']`
- frozen: exit 0; last lines: `['tests/acceptance/test_schedule.py: OK', 'tests/acceptance/test_schema.py: OK', 'tests/acceptance/test_sequential.py: OK', 'tests/acceptance/test_stats_gate.py: OK', 'uv.lock: OK']`

A uses exact integer decision frontiers and exact common-denominator probability mass.
Its lost-mass column is zero. Full rational numerators/denominators are in results.json.
An optional faster dyadic-enclosure implementation is included and tested against exact
probabilities, but is not used for Table A or the five shared exact/simulation points.
No provider stationarity, future runner implementation, cross-platform CI, or suite
sampling independence is established by this spike. Golden vectors ran on this host.
A hard-invariant BLOCK is outside these statistical false-BLOCK rates.
