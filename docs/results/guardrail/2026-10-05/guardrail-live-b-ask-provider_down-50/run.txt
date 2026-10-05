# Experiment guardrail-live-b-ask-provider_down-50

INCONCLUSIVE means there is not enough evidence either way: the confidence interval stays non-green, and no regression is claimed.

## Gate configuration

| Alpha | Delta | K (gating conditions) | Interval method | Per-arm confidence | n_per_arm |
|---:|---:|---:|---|---:|---:|
| 0.0500 | 0.1000 | 1 | clopper_pearson | 97.5000% | 50 |

## Decisions

| Recorded decisions | Input tokens | Output tokens | Estimated cost at list price |
|---:|---:|---:|---:|
| 100 | 0 | 0 | USD 0.0000000 |

List price: USD 0.042 per million input tokens (read 2026-09-22).
Fixtures and replays cost nothing; this is an estimate, not billed spend.

## Condition: provider_down

| Measure | Baseline | Candidate / condition |
|---|---:|---:|
| Role | — | Gating |
| n | 50 | 50 |
| Successes | 50 | 38 |
| Success rate | 100.0% | 76.0% |
| Wilson 95% (display only) | [0.9287, 1.0000] | [0.6259, 0.8570] |
| Clopper-Pearson (97.5000%) | [0.9161, 1.0000] | [0.5984, 0.8813] |
| Bounds on difference, clopper_pearson (candidate - baseline) | — | [-0.4016, -0.0348] |
| Candidate hard violations | — | 0 |
| Condition verdict | — | **INCONCLUSIVE** |

## Candidate failure clusters

| Failure fingerprint | Count | Example failure detail |
|---|---:|---|
| `d6f37728a2478b3bc05e5a2e3a7d58f189548565d3ef658cd00b9352cd18036f` | 12 | oracle rejected final state; first_failed_tool=decision:systemone:http_529 |

## Earlier runs on this candidate are never hidden

- None recorded.

## Reasons

- Experiment: no global errors.
- `provider_down`: bounds cross the margin

VERDICT: INCONCLUSIVE (exit 2)
