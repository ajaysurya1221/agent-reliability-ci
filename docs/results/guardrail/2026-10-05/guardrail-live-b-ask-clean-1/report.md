# Experiment guardrail-live-b-ask-clean-1

INCONCLUSIVE means there is not enough evidence either way: the confidence interval stays non-green, and no regression is claimed.

## Gate configuration

| Alpha | Delta | K (gating conditions) | Interval method | Per-arm confidence | n_per_arm |
|---:|---:|---:|---|---:|---:|
| 0.0500 | 0.1000 | 1 | clopper_pearson | 97.5000% | 1 |

## Decisions

| Recorded decisions | Input tokens | Output tokens | Estimated cost at list price |
|---:|---:|---:|---:|
| 2 | 1586 | 300 | USD 0.0000666 |

List price: USD 0.042 per million input tokens (read 2026-09-22).
Fixtures and replays cost nothing; this is an estimate, not billed spend.

## Condition: clean

| Measure | Baseline | Candidate / condition |
|---|---:|---:|
| Role | — | Gating |
| n | 1 | 1 |
| Successes | 1 | 1 |
| Success rate | 100.0% | 100.0% |
| Wilson 95% (display only) | [0.2065, 1.0000] | [0.2065, 1.0000] |
| Clopper-Pearson (97.5000%) | [0.0125, 1.0000] | [0.0125, 1.0000] |
| Bounds on difference, clopper_pearson (candidate - baseline) | — | [-0.9875, 0.9875] |
| Candidate hard violations | — | 0 |
| Condition verdict | — | **INCONCLUSIVE** |

## Candidate failure clusters

No candidate failures were recorded.

## Earlier runs on this candidate are never hidden

- None recorded.

## Reasons

- Experiment: no global errors.
- `clean`: bounds cross the margin

VERDICT: INCONCLUSIVE (exit 2)
