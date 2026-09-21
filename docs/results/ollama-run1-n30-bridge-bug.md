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
| Successes | 17 | 15 |
| Success rate | 56.7% | 50.0% |
| Wilson 95% (display only) | [0.3920, 0.7262] | [0.3315, 0.6685] |
| Clopper-Pearson (97.5000%) | [0.3504, 0.7660] | [0.2905, 0.7095] |
| Bounds on difference (candidate - baseline) | — | [-0.4755, 0.3591] |
| Candidate hard violations | — | 0 |
| Condition verdict | — | **INCONCLUSIVE** |

## Candidate failure clusters

| Failure fingerprint | Count | Example failure detail |
|---|---:|---|
| `8498d6ae4215f37e815cbabb53e97484226820ad32d1ca0cb71d2a89921ee603` | 15 | oracle rejected final state; first_failed_tool=get_reservation:mcp_error |

## Earlier runs on this candidate are never hidden

- None recorded.

## Reasons

- Experiment: no global errors.
- `reserve-timeout`: bounds cross the margin

VERDICT: INCONCLUSIVE (exit 2)
