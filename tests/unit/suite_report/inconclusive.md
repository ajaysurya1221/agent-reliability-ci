# Suite suite-acceptance

VERDICT: INCONCLUSIVE (exit 2); stored decision: absent

Reasons: no test crossed

## Registered rule

Alpha: 1/20; delta: 1/10; stakes: 1/4, 1/2; threshold: 40/1.
Cells: 20; max rounds: 4; seed mode: fixed; error tolerance: 0.
Stopping round: 4; pairs at last evaluated round: 80; stored trials: 160.

The claim is for the registered scenarios over outcome randomness.

Statistical directional error bounds are alpha/2 under joint independence across distinct (round, cell) pairs and stationary per-cell laws (including no execution-order effect), or the per-round conditional null and conditional independence. The false-BLOCK bound covers statistical BLOCK only, not candidate hard violations. ARCI does not certify these assumptions.

## Round history (cumulative)

Wealth displays are truncated; exact crossing flags decide against the threshold.

| Round | Pairs | Minus | Zero | Plus | Errored / tolerance | Hard violations | PASS wealth | BLOCK wealth | Threshold | PASS crossed | BLOCK crossed | Verdict |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|
| 1 | 20 | 2 | 18 | 0 | 0 / 0 | 0 | 7.91355e-01 | 9.09344e-01 | 40/1 | false | false | INCONCLUSIVE |
| 2 | 40 | 4 | 36 | 0 | 0 / 0 | 0 | 6.43077e-01 | 8.29398e-01 | 40/1 | false | false | INCONCLUSIVE |
| 3 | 60 | 6 | 54 | 0 | 0 / 0 | 0 | 5.35547e-01 | 7.58738e-01 | 40/1 | false | false | INCONCLUSIVE |
| 4 | 80 | 8 | 72 | 0 | 0 / 0 | 0 | 4.55719e-01 | 6.96138e-01 | 40/1 | false | false | INCONCLUSIVE |

## Per-cell counts (descriptive)

A suite-mean PASS can hide a regression in one cell.

| Task | Condition | Pairs | Baseline successes | Candidate successes | Minus | Zero | Plus | Errored | Candidate hard violations |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| t0 | clean | 4 | 4 | 0 | 4 | 0 | 0 | 0 | 0 |
| t0 | empty_log | 4 | 4 | 0 | 4 | 0 | 0 | 0 | 0 |
| t0 | fetch_timeout | 4 | 4 | 4 | 0 | 4 | 0 | 0 | 0 |
| t0 | store_error_late | 4 | 4 | 4 | 0 | 4 | 0 | 0 | 0 |
| t1 | clean | 4 | 4 | 4 | 0 | 4 | 0 | 0 | 0 |
| t1 | empty_log | 4 | 4 | 4 | 0 | 4 | 0 | 0 | 0 |
| t1 | fetch_timeout | 4 | 4 | 4 | 0 | 4 | 0 | 0 | 0 |
| t1 | store_error_late | 4 | 4 | 4 | 0 | 4 | 0 | 0 | 0 |
| t2 | clean | 4 | 4 | 4 | 0 | 4 | 0 | 0 | 0 |
| t2 | empty_log | 4 | 4 | 4 | 0 | 4 | 0 | 0 | 0 |
| t2 | fetch_timeout | 4 | 4 | 4 | 0 | 4 | 0 | 0 | 0 |
| t2 | store_error_late | 4 | 4 | 4 | 0 | 4 | 0 | 0 | 0 |
| t3 | clean | 4 | 4 | 4 | 0 | 4 | 0 | 0 | 0 |
| t3 | empty_log | 4 | 4 | 4 | 0 | 4 | 0 | 0 | 0 |
| t3 | fetch_timeout | 4 | 4 | 4 | 0 | 4 | 0 | 0 | 0 |
| t3 | store_error_late | 4 | 4 | 4 | 0 | 4 | 0 | 0 | 0 |
| t4 | clean | 4 | 4 | 4 | 0 | 4 | 0 | 0 | 0 |
| t4 | empty_log | 4 | 4 | 4 | 0 | 4 | 0 | 0 | 0 |
| t4 | fetch_timeout | 4 | 4 | 4 | 0 | 4 | 0 | 0 | 0 |
| t4 | store_error_late | 4 | 4 | 4 | 0 | 4 | 0 | 0 | 0 |

## Fault accounting

Recorded tool_finish injections, grouped by declared fault name; repeated declarations of the same name are indistinguishable. Counts are descriptive.

| Condition | Fault | Arm | Trials | Injections | Trials fired | Status |
|---|---|---|---:|---:|---:|---|
| `empty_log` | `empty_result` | baseline | 20 | 0 | 0 | declared, never fired |
| `empty_log` | `empty_result` | candidate | 20 | 0 | 0 | declared, never fired |
| `fetch_timeout` | `tool_timeout` | baseline | 20 | 0 | 0 | declared, never fired |
| `fetch_timeout` | `tool_timeout` | candidate | 20 | 0 | 0 | declared, never fired |
| `store_error_late` | `tool_error_once` | baseline | 20 | 0 | 0 | declared, never fired |
| `store_error_late` | `tool_error_once` | candidate | 20 | 0 | 0 | declared, never fired |

## Tool outcomes (descriptive)

Counts of recorded tool attempts. An uninjected failure is a recorded tool_finish that failed with no injection marker; the record does not show why it failed, and an earlier injected fault can be the cause. A tool with no recorded start in a trial may simply not be needed by that task; compare the two arms. Retries by middleware count as attempts. Counts are descriptive and decide nothing.

| Arm | Trials | Trials with an uninjected failure | Then passed | Then not passed |
|---|---:|---:|---:|---:|
| baseline | 80 | 0 | 0 | 0 |
| candidate | 80 | 0 | 0 | 0 |

No tool starts recorded.

## Prior runs recorded in the manifest; discovery covers the output root only

- `earlier`

A new campaign does not reset the error budget. Integrity seals do not authenticate execution.

VERDICT: INCONCLUSIVE (exit 2); stored decision: absent
