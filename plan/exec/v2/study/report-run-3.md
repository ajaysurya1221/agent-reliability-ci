# Suite order-desk-qwen3.5-4b-empty-lookup-text

VERDICT: BLOCK (exit 1); stored decision: match

Reasons: regression established

## Registered rule

Alpha: 1/20; delta: 1/10; stakes: 1/4, 1/2; threshold: 40/1.
Cells: 8; max rounds: 40; seed mode: per_round; error tolerance: 4.
Stopping round: 2; pairs at last evaluated round: 16; stored trials: 32.

The per_round error guarantee requires that in every round the suite mean over that round's scenario instances obey the relevant null, with the joint independence across cells and rounds (or its conditional form).

Statistical directional error bounds are alpha/2 under joint independence across distinct (round, cell) pairs and stationary per-cell laws (including no execution-order effect), or the per-round conditional null and conditional independence. The false-BLOCK bound covers statistical BLOCK only, not candidate hard violations. ARCI does not certify these assumptions.

There is no guarantee averaged over seeds: a deterministic hash of registered content is not a sampling distribution.

## Round history (cumulative)

Wealth displays are truncated; exact crossing flags decide against the threshold.

| Round | Pairs | Minus | Zero | Plus | Errored / tolerance | Hard violations | PASS wealth | BLOCK wealth | Threshold | PASS crossed | BLOCK crossed | Verdict |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|
| 1 | 8 | 6 | 2 | 0 | 0 / 4 | 0 | 1.02706e-01 | 5.02474e+00 | 40/1 | false | false | INCONCLUSIVE |
| 2 | 16 | 13 | 3 | 0 | 0 / 4 | 0 | 1.29680e-02 | 4.27909e+01 | 40/1 | false | true | BLOCK |

## Per-cell counts (descriptive)

A suite-mean PASS can hide a regression in one cell.

| Task | Condition | Pairs | Baseline successes | Candidate successes | Minus | Zero | Plus | Errored | Candidate hard violations |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| desk-03 | empty_result | 2 | 2 | 0 | 2 | 0 | 0 | 0 | 0 |
| desk-06 | empty_result | 2 | 2 | 0 | 2 | 0 | 0 | 0 | 0 |
| desk-09 | empty_result | 2 | 2 | 1 | 1 | 1 | 0 | 0 | 0 |
| desk-12 | empty_result | 2 | 2 | 0 | 2 | 0 | 0 | 0 | 0 |
| desk-15 | empty_result | 2 | 2 | 0 | 2 | 0 | 0 | 0 | 0 |
| desk-18 | empty_result | 2 | 1 | 0 | 1 | 1 | 0 | 0 | 0 |
| desk-21 | empty_result | 2 | 2 | 0 | 2 | 0 | 0 | 0 | 0 |
| desk-24 | empty_result | 2 | 2 | 1 | 1 | 1 | 0 | 0 | 0 |

## Fault accounting

Recorded tool_finish injections, grouped by declared fault name; repeated declarations of the same name are indistinguishable. Counts are descriptive.

| Condition | Fault | Arm | Trials | Injections | Trials fired | Status |
|---|---|---|---:|---:|---:|---|
| `empty_result` | `empty_result` | baseline | 16 | 16 | 16 | observed |
| `empty_result` | `empty_result` | candidate | 16 | 15 | 15 | observed |

## Tool outcomes (descriptive)

Counts of recorded tool attempts. An uninjected failure is a recorded tool_finish that failed with no injection marker; the record does not show why it failed, and an earlier injected fault can be the cause. A tool with no recorded start in a trial may simply not be needed by that task; compare the two arms. Retries by middleware count as attempts. Counts are descriptive and decide nothing.

| Arm | Trials | Trials with an uninjected failure | Then passed | Then not passed |
|---|---:|---:|---:|---:|
| baseline | 16 | 9 | 8 | 1 |
| candidate | 16 | 14 | 1 | 13 |

| Tool | Arm | Trials | Started in | Not started in | Starts | Uninjected failures | Trials with one |
|---|---|---:|---:|---:|---:|---:|---:|
| `add_note` | baseline | 16 | 16 | 0 | 16 | 0 | 0 |
| `add_note` | candidate | 16 | 4 | 12 | 4 | 0 | 0 |
| `check_stock` | baseline | 16 | 16 | 0 | 24 | 9 | 9 |
| `check_stock` | candidate | 16 | 15 | 1 | 17 | 15 | 14 |
| `lookup_order` | baseline | 16 | 16 | 0 | 32 | 0 | 0 |
| `lookup_order` | candidate | 16 | 15 | 1 | 17 | 0 | 0 |

## Prior runs recorded in the manifest; discovery covers the output root only

- `order-desk-gemma4-12b-vs-qwen3.5-4b@533c6d1a78ccc1a201eb7e265a61873244d48c2ac0e26cde5a50bc7dfd5f83bb`
- `order-desk-gemma4-12b-vs-qwen3.5-4b-recoverable@eaa438b195f418b66878a57422ab6229b2171c74dd8d6eb7ba097ec4a09b96fb`

A new campaign does not reset the error budget. Integrity seals do not authenticate execution.

VERDICT: BLOCK (exit 1); stored decision: match
