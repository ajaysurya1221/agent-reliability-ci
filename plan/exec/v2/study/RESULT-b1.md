# Result, benchmark B1: C1 PASS, C2 PASS, C3 PASS

## Registration and times

On 2026-11-24 UTC, the [registration](PREREGISTRATION-b1.md) was committed at 22:02:52
(`f16ed18`) and the digest list corrected at 22:03:06 (`9bd3e77`). The local reflog
records pushes at 22:02:54 and 22:03:08. The run started at 22:03:34 and exited 0 at
22:10:41. Commit `0df096a` records the summary, evaluation and output digests. The
per-stream journal (104,059,585 bytes, 99.2 MiB) is just under the host's 100 MiB file
limit and over its 50 MiB warning size, so `a073766` adds it compressed:
[results.jsonl.gz](b1-gate-benchmark/output/results.jsonl.gz) (gzip -9 -n).
Decompressed, its SHA-256 matches the one in the [output digests][digests].

The independent recount matched all eight registered file digests, checked the stream
indices and row checksums, and recovered 120,000 primary and 120,000 outage streams.
Across eight rules it found zero ERRORs in 1,920,000 verdicts and confirmed C1–C3.
[Evaluation](b1-gate-benchmark/output/criteria.json) · [Output digests][digests]

## Read this first

The computer generated pass/fail results for an old version and a candidate. The old
version had a 95% chance of passing. The rule asked whether the candidate lost more
than ten percentage points. At 75% the right action was BLOCK. At 95% it was PASS.
At exactly 85%, a rule testing that margin can justify neither PASS nor BLOCK.

Each round paired the versions on 20 tasks, up to 400 pairs over 20 rounds. In I, each
version got its own independent draw. In P, both shared one draw. ARCI 2.4.1 and seven
rival rules saw the same streams. Cost counted only the pairs each rule used. The rivals
were rebuilt from public documentation. The benchmark did not run the vendors' products.

**Across the four clear simulated settings, ARCI took the registered correct action on
92.80% to 100% of streams.** Only the margin confidence sequence qualified for C3. At 75%
with independent draws, ARCI averaged 203.418 pairs versus 399.084 for that rule.
These simulated decisions tell us nothing about real agents, graders or demand.

## Primary results

Each entry below gives independent / shared-draw rates in percent (10,000 streams each).
At 85%, PASS and BLOCK count as directional errors for the first four rules, which test
the ten-point margin. For the last four, these are observed release actions. Threshold
asks whether at least 80% of candidate outcomes passed. McNemar and the two zero-target
rules test for a difference from zero. CS means confidence sequence.

| Gate | PASS at 85% | BLOCK at 85% | Correct BLOCK at 75% | Correct PASS at 95% |
|---|---:|---:|---:|---:|
| ARCI | 1.07 / 1.01 | 1 / 0.64 | 92.8 / 99.86 | 99.98 / 100 |
| Tango | 2.37 / 2.29 | 2.82 / 3.09 | 98.84 / 100 | 100 / 100 |
| Bootstrap, margin | 2.39 / 2.91 | 2.41 / 1.6 | 98.59 / 99.99 | 100 / 100 |
| CS, margin | 0 / 0 | 0 / 0 | 1.62 / 0.55 | 0.03 / 0 |
| Threshold | 99.67 / 99.64 | 0.33 / 0.36 | 98.87 / 98.75 | 100 / 100 |
| McNemar | 0 / 0 | 99.74 / 100 | 100 / 100 | 1.95 / 0 |
| Bootstrap, zero | 0 / 0 | 99.8 / 100 | 100 / 100 | 2.48 / 0 |
| CS, zero | 0 / 0 | 0.84 / 0.04 | 97.48 / 99.11 | 0 / 0 |

Each entry below is the decision rate (% PASS or BLOCK) / mean pairs used. Means include
streams that reached the cap and are rounded to one decimal.

| Gate | Draws | 75% | 84% | 85% | 86% | 95% | 98% |
|---|---|---:|---:|---:|---:|---:|---:|
| ARCI | I | 92.8/203.4 | 2.69/395.3 | 2.07/396 | 2.86/394.5 | 99.98/126.1 | 100/83 |
| ARCI | P | 99.86/153 | 2.6/396.6 | 1.65/397.4 | 3.73/394.3 | 100/80 | 100/74.6 |
| Tango | I | 98.84/400 | 7.53/400 | 5.19/400 | 7.56/400 | 100/400 | 100/400 |
| Tango | P | 100/400 | 12.33/400 | 5.38/400 | 10.26/400 | 100/400 | 100/400 |
| Bootstrap, margin | I | 98.59/400 | 6.53/400 | 4.8/400 | 7.47/400 | 100/400 | 100/400 |
| Bootstrap, margin | P | 99.99/400 | 7.73/400 | 4.51/400 | 11.7/400 | 100/400 | 100/400 |
| CS, margin | I | 1.62/399.1 | 0/400 | 0/400 | 0/400 | 0.03/400 | 3.48/399 |
| CS, margin | P | 0.55/399.7 | 0/400 | 0/400 | 0/400 | 0/400 | 0.57/399.9 |
| Threshold | Both | 100/400 | 100/400 | 100/400 | 100/400 | 100/400 | 100/400 |
| McNemar | I | 100/400 | 99.97/400 | 99.74/400 | 98.99/400 | 3.44/400 | 56.56/400 |
| McNemar | P | 100/400 | 100/400 | 100/400 | 100/400 | 0/400 | 98.15/400 |
| Bootstrap, zero | I | 100/400 | 99.98/400 | 99.8/400 | 99.16/400 | 4.43/400 | 62.52/400 |
| Bootstrap, zero | P | 100/400 | 100/400 | 100/400 | 100/400 | 0/400 | 99.82/400 |
| CS, zero | I | 97.48/245.1 | 2.43/398.8 | 0.84/399.6 | 0.14/399.9 | 0/400 | 0/400 |
| CS, zero | P | 99.11/244.5 | 0.38/399.8 | 0.04/400 | 0/400 | 0/400 | 0/400 |

The [full primary table][primary] gives every verdict rate with its two-sided,
equal-tailed 95% Clopper-Pearson interval, plus mean and median pairs.

## Registered criteria and stop rule

**C1 PASS.** ARCI passed all 14 directional checks. Wrong PASS counted at 75%, 84% and
85%. Wrong BLOCK counted at 85%, 86%, 95% and 98%. Failure required a 95% lower
bound above 2.5%. The largest wrong PASS was 107/10,000 (1.07%, interval 0.88–1.29%).
The largest wrong BLOCK was 100/10,000 (1.00%, 0.81–1.21%). Both occurred at I, 85%.

**C2 PASS.** All four correct rates cleared 80%. The lowest was 92.80% at I, 75%
(9,280 correct BLOCKs, 95% interval 92.28–93.30%).

**C3 PASS against one eligible rival.** The margin CS had zero wrong decisions on the
primary grid. At 85%, Tango failed C1 on wrong BLOCK in both regimes (95% lower bounds
2.5043% in I and 2.7596% in P). The margin bootstrap failed on wrong PASS in P (lower
bound 2.5893%). Eligibility used unrounded bounds across the full registered grid.

C3 required at least 20% fewer mean pairs and a correct-rate gap of at least −5 points
in all four cases. For ARCI minus 0.8 times rival pairs, each upper bound had to be ≤0.
The simultaneous 95% Hoeffding intervals account for all 12 planned comparisons.

| Draws, rate | Mean pairs, ARCI / CS | Cost difference [95% interval] | Correct-rate gap |
|---|---:|---:|---:|
| I, 75% | 203.418 / 399.084 | −115.85 [−127.87, −103.83] | +91.18 points |
| P, 75% | 153.004 / 399.726 | −166.78 [−178.79, −154.76] | +99.31 points |
| I, 95% | 126.102 / 399.994 | −193.89 [−205.91, −181.88] | +99.95 points |
| P, 95% | 80 / 400 | −240.00 [−252.02, −227.98] | +100.00 points |

**Stop rule did not trigger.** B1 would give no support for continuing this direction if
C3 failed and one eligible rival matched or beat ARCI's correct rate in all four cases.
C3 passed, and the margin CS matched or beat ARCI in zero of four.

## Exact-projection cross-check

The verifier recomputed `arci plan` for the 12 primary settings. Its exact projection
fell inside the marginal 95% simulation intervals for 33/36 verdict rates and all 12
mean costs (Hoeffding half-width 5.161 pairs). All four measures agreed within those
bounds in 10/12 settings. The three exceptions all used shared draws.

| Candidate, verdict | Exact % | Observed % [95% interval] | Observed − exact, points |
|---|---:|---:|---:|
| 84%, PASS | 0.2261 | 0.33 [0.2273, 0.4631] | +0.1039 |
| 85%, BLOCK | 0.4849 | 0.64 [0.4932, 0.8165] | +0.1551 |
| 85%, INCONCLUSIVE | 98.6116 | 98.35 [98.0808, 98.5905] | −0.2616 |

The flags are descriptive. [Signed differences][primary] · [Exact projections][summary]

## Outage stress report

In a separate 120,000 streams, each round had a 5% chance that both versions failed all
20 tasks together. This shrank each true difference by a factor of 0.95. At the 85%
label the candidate trailed by 9.5 points, so only BLOCK counted as wrong. Dependence
within rounds rules out the primary projection. The stress panel was descriptive.

| Candidate, ARCI verdict | Rate %, I / P | Mean pairs, I / P |
|---|---:|---:|
| 75%, correct BLOCK | 86.63 / 98.60 | 225.756 / 173.658 |
| 85%, wrong BLOCK | 0.59 / 0.40 | 394.472 / 395.108 |
| 95%, correct PASS | 99.97 / 100 | 123.070 / 80 |

At 75%, outages reduced ARCI's correct BLOCK rate and raised its mean cost in I and P.
[All outage verdicts, intervals and costs](b1-gate-benchmark/output/stress.md)

## Predictions

Astra predicted C1 and C2 would pass. Both matched. Astra predicted C3 would pass as
drafted but fail the corrected five-point guardrail at I, 75%. ARCI did trail Tango by
6.04 points and margin bootstrap by 5.79 there. Both failed C1, so those gaps did not
decide the registered C3. Astra's prediction for the corrected rule missed.

The orchestrator predicted PASS, PASS, FAIL. Only C3 missed. The maintainer did not predict.

## What weakens this

**C3 passed against a rival that almost never decides.** The sole eligible rival
correctly blocked at most 1.62% at 75% and correctly passed at most 0.03% at 95%.
Tango and the margin bootstrap, which narrowly failed C1, decide far more often. Against
them at I, 75%, ARCI used about half the pairs (203.4 against 400) but was 6.04 and 5.79
points less often correct. Had either passed C1, C3 would have failed in that cell.
Tango failed C1 clearly in P (lower bound 2.7596%). The margin bootstrap failed only at
P, 85%, by 0.0893 points (lower bound 2.5893%). The C3 PASS rests on that one check.
Near the margin (84–86%), ARCI returned INCONCLUSIVE on 96.27–98.35% of streams.

All tasks had the same success probabilities, one baseline and a 400-pair cap.
The two pairing schemes and one outage model cover few of the ways real runs can vary.

## What is not claimed

B1 measures decision rules on made-up data. It establishes no real agent's reliability,
grader accuracy, vendor product ranking or buyer demand. Pairs measure sample cost.
B1 measured neither wall-clock savings nor money saved on a deployment.

## Errata

Before the run, `9bd3e77` removed the obsolete draft registration filename from the
digest list after the file was renamed. Commit `f16ed18` binds the sealed registration.
A separate evaluator call omitted the summary argument and exited 2. The completed run
wrote the evaluation above. No other errata were found.

[primary]: b1-gate-benchmark/output/results.md
[summary]: b1-gate-benchmark/output/summary.json
[digests]: b1-gate-benchmark/output/digests.sha256
