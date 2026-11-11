# Suite suite-acceptance

VERDICT: ERROR (exit 3); stored decision: absent

Reasons: errored pairs exceed max_errored_pairs

## Registered rule

Alpha: 1/20; delta: 1/10; stakes: 1/4, 1/2; threshold: 40/1.
Cells: 20; max rounds: 4; seed mode: fixed; error tolerance: 0.
Stopping round: 0; pairs at last evaluated round: 20; stored trials: 40.

The claim is for the registered scenarios over outcome randomness.

Statistical directional error bounds are alpha/2 under joint independence across distinct (round, cell) pairs and stationary per-cell laws (including no execution-order effect), or the per-round conditional null and conditional independence. The false-BLOCK bound covers statistical BLOCK only, not candidate hard violations. ARCI does not certify these assumptions.

## Round history (cumulative)

Wealth displays are truncated; exact crossing flags decide against the threshold.

| Round | Pairs | Minus | Zero | Plus | Errored / tolerance | Hard violations | PASS wealth | BLOCK wealth | Threshold | PASS crossed | BLOCK crossed | Verdict |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|
| 1 | 20 | 0 | 19 | 0 | 1 / 0 | 0 | 1.32948e+00 | 3.45581e-01 | 40/1 | false | false | ERROR |

## Per-cell counts (descriptive)

A suite-mean PASS can hide a regression in one cell.

| Task | Condition | Pairs | Baseline successes | Candidate successes | Minus | Zero | Plus | Errored | Candidate hard violations |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| t0 | clean | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 |
| t0 | empty_log | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 |
| t0 | fetch_timeout | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 |
| t0 | store_error_late | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 |
| t1 | clean | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 |
| t1 | empty_log | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 |
| t1 | fetch_timeout | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 |
| t1 | store_error_late | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 |
| t2 | clean | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 |
| t2 | empty_log | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 |
| t2 | fetch_timeout | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 |
| t2 | store_error_late | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 |
| t3 | clean | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 |
| t3 | empty_log | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 |
| t3 | fetch_timeout | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 |
| t3 | store_error_late | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 |
| t4 | clean | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 |
| t4 | empty_log | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 |
| t4 | fetch_timeout | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 |
| t4 | store_error_late | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 |

## Fault accounting

Recorded tool_finish injections, grouped by declared fault name; repeated declarations of the same name are indistinguishable. Counts are descriptive.

| Condition | Fault | Arm | Trials | Injections | Trials fired | Status |
|---|---|---|---:|---:|---:|---|
| `empty_log` | `empty_result` | baseline | 5 | 0 | 0 | declared, never fired |
| `empty_log` | `empty_result` | candidate | 5 | 0 | 0 | declared, never fired |
| `fetch_timeout` | `tool_timeout` | baseline | 5 | 0 | 0 | declared, never fired |
| `fetch_timeout` | `tool_timeout` | candidate | 5 | 0 | 0 | declared, never fired |
| `store_error_late` | `tool_error_once` | baseline | 5 | 0 | 0 | declared, never fired |
| `store_error_late` | `tool_error_once` | candidate | 5 | 0 | 0 | declared, never fired |

## Prior runs recorded in the manifest; discovery covers the output root only

- `earlier`

A new campaign does not reset the error budget. Integrity seals do not authenticate execution.

VERDICT: ERROR (exit 3); stored decision: absent
