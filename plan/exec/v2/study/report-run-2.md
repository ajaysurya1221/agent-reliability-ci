# Suite order-desk-gemma4-12b-vs-qwen3.5-4b-recoverable

VERDICT: INCONCLUSIVE (exit 2); stored decision: match

Reasons: no test crossed

## Registered rule

Alpha: 1/20; delta: 1/10; stakes: 1/4, 1/2; threshold: 40/1.
Cells: 96; max rounds: 5; seed mode: per_round; error tolerance: 5.
Stopping round: 5; pairs at last evaluated round: 480; stored trials: 960.

The per_round error guarantee requires that in every round the suite mean over that round's scenario instances obey the relevant null, with the joint independence across cells and rounds (or its conditional form).

Statistical directional error bounds are alpha/2 under joint independence across distinct (round, cell) pairs and stationary per-cell laws (including no execution-order effect), or the per-round conditional null and conditional independence. The false-BLOCK bound covers statistical BLOCK only, not candidate hard violations. ARCI does not certify these assumptions.

There is no guarantee averaged over seeds: a deterministic hash of registered content is not a sampling distribution.

## Round history (cumulative)

Wealth displays are truncated; exact crossing flags decide against the threshold.

| Round | Pairs | Minus | Zero | Plus | Errored / tolerance | Hard violations | PASS wealth | BLOCK wealth | Threshold | PASS crossed | BLOCK crossed | Verdict |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|
| 1 | 96 | 11 | 85 | 0 | 0 / 5 | 0 | 2.40993e-01 | 9.65619e-01 | 40/1 | false | false | INCONCLUSIVE |
| 2 | 192 | 21 | 171 | 0 | 0 / 5 | 0 | 1.31301e-01 | 7.24058e-01 | 40/1 | false | false | INCONCLUSIVE |
| 3 | 288 | 31 | 257 | 0 | 0 / 5 | 0 | 7.68064e-02 | 5.68042e-01 | 40/1 | false | false | INCONCLUSIVE |
| 4 | 384 | 44 | 340 | 0 | 0 / 5 | 0 | 1.76794e-02 | 9.66984e-01 | 40/1 | false | false | INCONCLUSIVE |
| 5 | 480 | 52 | 428 | 0 | 0 / 5 | 0 | 1.97265e-02 | 4.87762e-01 | 40/1 | false | false | INCONCLUSIVE |

## Per-cell counts (descriptive)

A suite-mean PASS can hide a regression in one cell.

| Task | Condition | Pairs | Baseline successes | Candidate successes | Minus | Zero | Plus | Errored | Candidate hard violations |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| desk-01 | clean | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-01 | empty_result | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-01 | tool_error_once | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-01 | tool_timeout | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-02 | clean | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-02 | empty_result | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-02 | tool_error_once | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-02 | tool_timeout | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-03 | clean | 5 | 5 | 4 | 1 | 4 | 0 | 0 | 0 |
| desk-03 | empty_result | 5 | 5 | 1 | 4 | 1 | 0 | 0 | 0 |
| desk-03 | tool_error_once | 5 | 5 | 3 | 2 | 3 | 0 | 0 | 0 |
| desk-03 | tool_timeout | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-04 | clean | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-04 | empty_result | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-04 | tool_error_once | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-04 | tool_timeout | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-05 | clean | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-05 | empty_result | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-05 | tool_error_once | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-05 | tool_timeout | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-06 | clean | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-06 | empty_result | 5 | 5 | 1 | 4 | 1 | 0 | 0 | 0 |
| desk-06 | tool_error_once | 5 | 5 | 4 | 1 | 4 | 0 | 0 | 0 |
| desk-06 | tool_timeout | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-07 | clean | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-07 | empty_result | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-07 | tool_error_once | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-07 | tool_timeout | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-08 | clean | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-08 | empty_result | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-08 | tool_error_once | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-08 | tool_timeout | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-09 | clean | 5 | 5 | 4 | 1 | 4 | 0 | 0 | 0 |
| desk-09 | empty_result | 5 | 5 | 4 | 1 | 4 | 0 | 0 | 0 |
| desk-09 | tool_error_once | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-09 | tool_timeout | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-10 | clean | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-10 | empty_result | 5 | 5 | 4 | 1 | 4 | 0 | 0 | 0 |
| desk-10 | tool_error_once | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-10 | tool_timeout | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-11 | clean | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-11 | empty_result | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-11 | tool_error_once | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-11 | tool_timeout | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-12 | clean | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-12 | empty_result | 5 | 5 | 0 | 5 | 0 | 0 | 0 | 0 |
| desk-12 | tool_error_once | 5 | 5 | 4 | 1 | 4 | 0 | 0 | 0 |
| desk-12 | tool_timeout | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-13 | clean | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-13 | empty_result | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-13 | tool_error_once | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-13 | tool_timeout | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-14 | clean | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-14 | empty_result | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-14 | tool_error_once | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-14 | tool_timeout | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-15 | clean | 5 | 5 | 4 | 1 | 4 | 0 | 0 | 0 |
| desk-15 | empty_result | 5 | 5 | 1 | 4 | 1 | 0 | 0 | 0 |
| desk-15 | tool_error_once | 5 | 5 | 4 | 1 | 4 | 0 | 0 | 0 |
| desk-15 | tool_timeout | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-16 | clean | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-16 | empty_result | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-16 | tool_error_once | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-16 | tool_timeout | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-17 | clean | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-17 | empty_result | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-17 | tool_error_once | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-17 | tool_timeout | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-18 | clean | 5 | 5 | 4 | 1 | 4 | 0 | 0 | 0 |
| desk-18 | empty_result | 5 | 5 | 0 | 5 | 0 | 0 | 0 | 0 |
| desk-18 | tool_error_once | 5 | 5 | 4 | 1 | 4 | 0 | 0 | 0 |
| desk-18 | tool_timeout | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-19 | clean | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-19 | empty_result | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-19 | tool_error_once | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-19 | tool_timeout | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-20 | clean | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-20 | empty_result | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-20 | tool_error_once | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-20 | tool_timeout | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-21 | clean | 5 | 5 | 4 | 1 | 4 | 0 | 0 | 0 |
| desk-21 | empty_result | 5 | 5 | 0 | 5 | 0 | 0 | 0 | 0 |
| desk-21 | tool_error_once | 5 | 5 | 3 | 2 | 3 | 0 | 0 | 0 |
| desk-21 | tool_timeout | 5 | 5 | 4 | 1 | 4 | 0 | 0 | 0 |
| desk-22 | clean | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-22 | empty_result | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-22 | tool_error_once | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-22 | tool_timeout | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-23 | clean | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-23 | empty_result | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-23 | tool_error_once | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-23 | tool_timeout | 5 | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| desk-24 | clean | 5 | 5 | 4 | 1 | 4 | 0 | 0 | 0 |
| desk-24 | empty_result | 5 | 5 | 0 | 5 | 0 | 0 | 0 | 0 |
| desk-24 | tool_error_once | 5 | 5 | 3 | 2 | 3 | 0 | 0 | 0 |
| desk-24 | tool_timeout | 5 | 5 | 4 | 1 | 4 | 0 | 0 | 0 |

## Fault accounting

Recorded tool_finish injections, grouped by declared fault name; repeated declarations of the same name are indistinguishable. Counts are descriptive.

| Condition | Fault | Arm | Trials | Injections | Trials fired | Status |
|---|---|---|---:|---:|---:|---|
| `empty_result` | `empty_result` | baseline | 120 | 120 | 120 | observed |
| `empty_result` | `empty_result` | candidate | 120 | 119 | 119 | observed |
| `tool_error_once` | `tool_error_once` | baseline | 120 | 120 | 120 | observed |
| `tool_error_once` | `tool_error_once` | candidate | 120 | 120 | 120 | observed |
| `tool_timeout` | `tool_timeout` | baseline | 120 | 120 | 120 | observed |
| `tool_timeout` | `tool_timeout` | candidate | 120 | 120 | 120 | observed |

## Prior runs recorded in the manifest; discovery covers the output root only

- None recorded.

A new campaign does not reset the error budget. Integrity seals do not authenticate execution.

VERDICT: INCONCLUSIVE (exit 2); stored decision: match
