# B1 draft registration · 25 November 2026

How often does a release gate decide wrongly, how often does it decide at all, and how
many paired trials does it use when the true pass-rate difference is known?

D-31 requires the maintainer to commit and push the protocol, code, criteria and stop rule
before the registered run. Fill the prediction field before that freeze. Development
checks use fixed, hand-made data only. No registered projections or draws before the freeze.

## Design

Twenty tasks per round, at most twenty complete rounds. One pair contains one result per
arm for one task. Cap 400 pairs, or 800 arm results. Baseline pass probability 0.95 on
each task. Candidate p in {0.75, 0.84, 0.85, 0.86, 0.95, 0.98}. Delta 0.10,
alpha 1/20, directional alpha 1/40. Difference means candidate minus baseline.

In I, draw one independent uniform per arm. In P, use one shared uniform U per pair.
An arm passes when its draw is strictly below its pass probability. Pairs are mutually
independent. Exactly 10,000 streams per (p, regime), or 120,000 primary streams.

Repeat this inventory in a separate stress panel. Independently in each round, with
probability 0.05 all twenty pairs yield two failures. Otherwise use the same I or P law.
Use independent stress seeds. Marginal differences are 0.95 times the stated outage-free
differences. Stress cannot change C1, C2, C3 or the stop decision.

Master seed is the ASCII string ARCI-B1-20261125-v1. Join it and the following fields
with literal | characters, without spaces or newline, in this order:
panel (primary/outage), regime (I/P), candidate integer percent, zero-based stream index
(0..9999), purpose (pairs/outage/bootstrap). Integers use decimal with no leading zeros.
Hash the ASCII bytes with SHA-256. Read all 32 digest bytes as an unsigned big-endian
integer. Seed a separate CPython 3.13.12 random.Random with it. Use randrange(100) for
floor(100 U), exact for every threshold. Skip pair draws in an outage. Visit tasks in
task-01 through task-20 order. All gates receive the same full stream, including tails
beyond an early stop. Each gate is charged only for the pairs it consumes.

## Gate definitions

Rivals are rebuilt from the public documentation descriptions cited in the README.
No vendor implementation is used. The specific cutoffs, tails, interval variants and
decision mappings below define this experiment.

1. ARCI 2.4.1 imported outcomes. Rule fixed before runs, alpha 1/20, margin 1/10,
   default stakes (1/4, 1/2), max_rounds 20, max_errored_pairs 0. Feed complete-round
   discordances and agreements to the released walk_rounds function used by arci verdict.
   Take the first terminal verdict, otherwise INCONCLUSIVE at the cap.
2. Fixed threshold, AWS AgentCore / Braintrust style. At 400 pairs PASS when at least
   320 candidate outcomes pass, otherwise BLOCK. This targets absolute performance.
3. Exact two-sided McNemar, NVIDIA NeMo nel compare style. At 400 pairs let w,l be the
   positive and negative discordances. Double the smaller Binomial(w+l, 1/2) tail,
   capped at 1. At p-value <= 0.05 return PASS for w>l, BLOCK for w<l. Otherwise
   INCONCLUSIVE, including zero discordances. It tests for any difference from zero.
4. Paired percentile bootstrap, agent-eval style. At 400 pairs take 2,000 independent
   resamples of 400 pairs with replacement. For binary pairs the mean needs only counts
   of +1, 0, -1; draw these by conditional binomials with their empirical probabilities.
   Use linearly interpolated empirical quantiles at 0.025 and 0.975 (type 7).
   PASS if lower > 0, BLOCK if upper < 0, otherwise INCONCLUSIVE.
5. Confidence sequence, evalsig style. Use the two-sided normal-mixture boundary of
   Howard et al. (2021), doi:10.1214/20-AOS1991. Paired differences in [-1,1] have
   sub-Gaussian variance proxy 1 by Hoeffding's lemma. At n pairs set V=n, rho=20.
   Half-width = sqrt((V+rho)*log((V+rho)/(rho*0.05^2)))/n. Center on the sample mean.
   Check every round end. Stop when lower > 0 (PASS) or upper < 0 (BLOCK), otherwise
   INCONCLUSIVE at 400. This range-based sequence uses no estimated variance.
6. At 400 pairs use Tango's uncorrected 95% paired score interval, inverting the
   trinomial score with nuisance discordance fitted under each proposed difference.
   Method and worked table are in the README. PASS if lower > -0.10, BLOCK if
   upper < -0.10, otherwise INCONCLUSIVE.
7. Repeat gates 4 and 5 at -0.10 with the same strict inequalities. Reuse the very same
   bootstrap interval and confidence sequence. These count as two distinct rivals.

## Measures and cross-check

For every gate and cell report PASS, BLOCK, INCONCLUSIVE, ERROR and PASS-or-BLOCK.
Report mean and median pairs including capped runs at 400. All simulated rates divide by
all 10,000 streams and carry two-sided equal-tailed 95% Clopper-Pearson intervals.
For margin gates count wrong PASS when true difference <= -0.10 and wrong BLOCK when
it is >= -0.10. Both nulls hold at equality. Ineligible directions have zero events.
Report correct release actions for every gate at 0.75 (BLOCK) and 0.95 (PASS).
For native zero/absolute-target gates these two columns describe release actions only.

For each primary cell run python -m arci plan on a sealed suite manifest carrying the
identical rule. Supply exact rational marginals and agreement 0.95*p+0.05*(1-p) in I,
or 1-abs(0.95-p) in P. Save full rational PASS, BLOCK, INCONCLUSIVE and expected pairs.
Compare to observed values, show signed differences and whether each projection lies
inside its marginal Monte Carlo interval (CP for rates, two-sided Hoeffding for mean
pairs over [20,400]). Flag differences descriptively. No replacing streams or reruns
to clear flags. Within-round dependence excludes the stress panel from this projection.

## Registered criteria

C1 calibration: in both regimes, at p_c in {0.75, 0.84, 0.85}, ARCI's wrong-PASS rate must
not be clearly above 2.5% (fail if the Clopper-Pearson 95% LOWER bound exceeds 0.025); at
p_c in {0.85, 0.86, 0.95, 0.98}, the same for the wrong-BLOCK rate.

C2 usefulness: in both regimes, ARCI's correct-decision rate is at least 0.80 at p_c = 0.75
and at p_c = 0.95.

C3 efficiency claim: ARCI may claim to be cheaper only if, in both clear cases (0.75 and
0.95) and both regimes, against every rival that passes C1 and tests the same
margin (gates 6 and 7), ARCI's mean pairs are at least 20% lower with simultaneous 95%
intervals supporting it, and its correct-decision rate is at most 5 points lower. Otherwise
the efficiency claim is dropped.

Stop rule for this direction: if a calibrated margin-matched rival matches or beats ARCI
on C2 and C3 is not met, the benchmark gives no support for continuing the "release
decision" direction; say so in the result.

Use unrounded estimates. Each eligible rival must pass C1 across the full primary grid.
With no eligible rival, drop the efficiency claim. For each stream form the cost contrast
A - 0.8*R from paired gate costs. Its range width W is 380 for fixed rivals and 684
for the sequential rival. Around its sample mean use a two-sided Hoeffding interval with
half-width W*sqrt(log(2*12/0.05)/(2*10000)). Bonferroni covers all 4 cells x 3 rivals
regardless of eligibility. Require upper <= 0 and observed correct-rate gap A-R >= -0.05
for every eligible rival in every clear cell. For the stop rule, the same eligible rival must
equal or exceed ARCI's observed correct rate separately in all four clear cells.

## Execution and disclosure

From plan/exec/v2/study, after registration, run exactly:

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/ajay/Developer/.arci-worktrees/run4-env/bin/python \
  b1-gate-benchmark/simulate.py --run-registered
```

Publish the frozen protocol, predictions, source, tests, digests, per-stream decisions
and costs, full summary, exact projections and discrepancies, criteria, eligibility,
comparisons, primary and stress tables. Publish failures, partial coverage and errors
if execution fails. A restart may complete the same seeded inventory. No seed replacement,
selective reporting or post hoc choice of estimator. The result concerns simulated rules.
It supports no claims about real agents, graders, vendor products or buyer demand.

## Predictions

The consultant (Astra): C1 passes, C2 passes, C3 passes as drafted but fails the corrected correctness guardrail for independent arms at 0.75.

The orchestrator (Claude): C1 passes, C2 passes, C3 fails.
The maintainer: none supplied before registration.

Both were stated before any registered stream or exact projection ran.
