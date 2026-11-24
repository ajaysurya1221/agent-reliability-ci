# B1 release-gate benchmark

After the maintainer commits and pushes the completed [registration](../PREREGISTRATION-b1.draft.md)
and code under D-31, run from `plan/exec/v2/study`:

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/ajay/Developer/.arci-worktrees/run4-env/bin/python \
  b1-gate-benchmark/simulate.py --run-registered
```

**Budget about 10–20 minutes on this host, one process.** The measured inputs were three
hand-written streams, each replayed 180 times. Counts per round in the order (both fail,
candidate alone passes, baseline alone passes, both pass) were (6,0,0,14), (4,0,3,13)
and (2,2,4,12). Gate evaluation, integer draws supplied from the fixed fixture, journal
writes and tallying took 0.101, 1.124 and 2.017 ms per stream respectively. Applying the
one-sign and two-sign timings to 120,000 streams each gives 6.3 minutes. The total budget
allows for fresh PRNG draws, different stopping times and discordance counts, disk I/O,
summarization and 12 exact planner processes. Their registered runtimes are unmeasured.
Primary and outage panels each contain 120,000 streams.

## Reproduce the checks without starting B1

```sh
export PYTHONDONTWRITEBYTECODE=1
py=/Users/ajay/Developer/.arci-worktrees/run4-env/bin/python
"$py" -m pytest b1-gate-benchmark/tests -q -p no:cacheprovider
"$py" b1-gate-benchmark/tests/time_handmade.py
shasum -a 256 -c b1-gate-benchmark/digests.sha256
```

The tests feed six specified CSV streams to released `python -m arci verdict` and compare
both decision and stopping pair to `arci.suite_gate.walk_rounds`. This is the function
called by `arci.outcomes._infer`. The fixtures cover unanimous improvements and regressions,
agreements, a stream at the observed margin and reversals after an early decision.
For a deterministic all-improvements stream the released planner independently gives
PASS with probability one and exactly 20 pairs. The test uses baseline 0 and candidate 1.

## Rules and sources

All eight benchmark rules consume the same paired stream. Native threshold and zero-difference
tests answer different statistical questions. Only the score interval and the margin versions
of the bootstrap and confidence sequence enter C3. These are documentation-based rebuilds.
The B1 protocol fixes the numeric settings and verdict mappings. Vendor documentation was
available through local research notes during offline development.

| Gate | Basis for implementation |
|---|---|
| Threshold | Candidate successes >= 320. AWS describes threshold-based automation. Braintrust documents CI runs and a customizable failure policy. [AWS example](https://aws.amazon.com/blogs/machine-learning/automated-agent-evaluation-with-amazon-bedrock-agentcore-and-github-actions/) · [Braintrust CI](https://braintrust.dev/docs/evaluate/run-in-ci) |
| McNemar | Exact doubled binomial tail on discordant pairs. A significant change gets a directional verdict. [NeMo Evaluator regression comparison](https://docs.nvidia.com/nemo/evaluator/deployment/ci-regression.md) |
| Bootstrap, two targets | agent-eval documents bootstrap confidence intervals for baseline–candidate comparisons. B1 resamples 400 paired binary differences 2,000 times and uses a type-7 95% percentile interval. For each target (0 or −0.10), B1 returns PASS if the interval lies strictly above it, BLOCK if strictly below and INCONCLUSIVE otherwise. [agent-eval README](https://github.com/RudrenduPaul/agent-eval#readme) |
| Confidence sequence, two targets | evalsig documents sequential monitoring. B1 uses Howard et al.'s two-sided normal mixture with range-based variance proxy and rho=20. [evalsig](https://github.com/vtensor/evalsig) · [Howard, Ramdas, McAuliffe & Sekhon (2021)](https://doi.org/10.1214/20-AOS1991) |
| Paired score | Tango's asymptotic score interval for paired risk differences, without continuity correction. [Tango (1998), *Statistics in Medicine* 17, 891–908](https://onlinelibrary.wiley.com/toc/10970258/1998/17/8) |

For the bootstrap each resample has the multinomial counts of 400 draws with replacement
from the observed paired differences. First draw the positive count K from Bin(n,w/n).
Given K, draw negatives from Bin(n-K,l/(n-w)). The resampled mean is (K-negatives)/n.
Zero-probability or deterministic categories reduce to one or zero binomial calls.
Calculate both target decisions from the same 2,000 means.

For the confidence sequence, the centered partial sum of independent differences in
[-1,1] is sub-Gaussian with variance proxy V=n. Mixing the exponential bound against
a centered normal precision parameter rho=20 gives half-width
`sqrt((n+rho)*log((n+rho)/(rho*0.05^2)))/n`. The boundary is two-sided at 95% across time.
B1 inspects it only at the 20 registered round ends. The stress model breaks within-round
independence and its results are descriptive.

### Independent numerical check of Tango's interval

In Agresti's worked paired approval example the 2-by-2 table is (794,150;86,570).
Orient the difference as first minus second. There are w=150 wins, l=86 losses and
1,364 ties in n=1,600 pairs. The observed difference is 0.040. The original table is
reproduced in the R manual. [Agresti, *Categorical Data Analysis* (1990), p. 350, via the R manual](https://stat.ethz.ch/R-manual/R-devel/library/stats/html/mcnemar.test.html)

For proposed difference d let s be total discordance. The constrained trinomial
probabilities are ((s+d)/2,(s-d)/2,1-s). With h=(w-l)/n and q=(w+l)/n, the maximizing
s is the larger feasible root of `s²-(q+h*d)*s+h*d-(1-q)*d²=0`, including boundary
solutions on [|d|,1]. Invert `n*(h-d)² <= z(.975)²*(s-d²)`. The implementation bisects
the two endpoints and handles zero discordances and all one-direction pairs.

The test reference was calculated independently on the published table with decimal
arithmetic at 45 digits. Bisect s on [|d|,1] using the derivative
`w/(s+d)+l/(s-d)-(n-w-l)/(1-s)`, then bisect d on either side of 0.040 at score
squared 1.959963984540054². This gives [0.02136156475478724, 0.05899803330569942].
These are independently calculated Tango endpoints for Agresti's data.

## Resume and read the result

Rerun the exact command after interruption. The runner locks `output/results.jsonl`.
It checks a contiguous prefix for stream identity, code/environment identity and row SHA-256,
then resumes at the first missing stream. A final write without a newline is discarded.
A malformed complete record stops the run. Infrastructure exceptions interrupt execution.
A returned gate ERROR is counted in the denominator. No alternate seed or extension is used.

1. Read `output/results.md` for primary rates, costs, exact comparisons, C1–C3 and the
   stop-rule conclusion. `output/stress.md` contains the separate outage report.
2. Use `output/summary.json` for histograms and exact planner records. A rate tuple is
   [event count, proportion, CP lower, CP upper]. Exact projections are rational strings.
   The mean-cost cross-check uses a bounded-mean Hoeffding interval. Each JSONL row has
   a [panel, regime, candidate integer percent, zero-based replicate] key. Each gate value
   is [verdict, pairs consumed]. The registered seed and key reconstruct the input.
3. Inspect `output/criteria.json` for every wrong-direction failure, calibrated rival,
   simultaneous cost interval and correctness comparison. Recompute from the summary alone:

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/ajay/Developer/.arci-worktrees/run4-env/bin/python \
  b1-gate-benchmark/evaluate.py b1-gate-benchmark/output/summary.json
```

The source digest manifest uses paths relative to the study directory. It covers the draft
registration and every delivered file except the manifest itself. After filling the predictions,
refresh the registration digest before committing and pushing the frozen bundle. Runtime output is generated
only by the registered command, which also writes a separate digest manifest for its outputs.
