# Experiment ollama-retry-b-30

INCONCLUSIVE means there is not enough evidence either way: the confidence interval stays non-green, and no regression is claimed.

## Gate configuration

| Alpha | Delta | K (gating conditions) | Per-arm confidence | n_per_arm |
|---:|---:|---:|---:|---:|
| 0.0500 | 0.1000 | 1 | 97.5000% | 30 |

## Condition: reserve-timeout

| Measure | Baseline | Candidate / condition |
|---|---:|---:|
| Role | — | Gating |
| n | 30 | 30 |
| Successes | 29 | 23 |
| Success rate | 96.7% | 76.7% |
| Wilson 95% (display only) | [0.8333, 0.9941] | [0.5907, 0.8821] |
| Clopper-Pearson (97.5000%) | [0.8054, 0.9996] | [0.5511, 0.9134] |
| Bounds on difference (candidate - baseline) | — | [-0.4484, 0.1080] |
| Candidate hard violations | — | 0 |
| Condition verdict | — | **INCONCLUSIVE** |

## Candidate failure clusters

| Failure fingerprint | Count | Example failure detail |
|---|---:|---|
| `0d615ea1bb2e632e688ba1bd75deaaa73bdea58aeffbc010003b9a535a0cfbe5` | 6 | oracle rejected final state; first_failed_tool=reserve:timeout |
| `b376c565db2dd4854767ef178cc9faa292faa0562e88e33b51d3bf2c14c57875` | 1 | oracle rejected final state; first_failed_tool=none |

## Earlier runs on this candidate are never hidden

- None recorded.

## Reasons

- Experiment: no global errors.
- `reserve-timeout`: bounds cross the margin

VERDICT: INCONCLUSIVE (exit 2)
