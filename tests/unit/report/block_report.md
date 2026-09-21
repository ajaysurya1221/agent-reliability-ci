# Experiment exp-acceptance

BLOCK means the candidate is worse than the baseline by more than the configured delta, or it broke a hard invariant.

## Gate configuration

| Alpha | Delta | K (gating conditions) | Per-arm confidence | n_per_arm |
|---:|---:|---:|---:|---:|
| 0.0500 | 0.1000 | 1 | 97.5000% | 12 |

## Condition: fetch_timeout

| Measure | Baseline | Candidate / condition |
|---|---:|---:|
| Role | — | Gating |
| n | 12 | 12 |
| Successes | 12 | 0 |
| Success rate | 100.0% | 0.0% |
| Wilson 95% (display only) | [0.7575, 1.0000] | [0.0000, 0.2425] |
| Clopper-Pearson (97.5000%) | [0.6941, 1.0000] | [0.0000, 0.3059] |
| Bounds on difference (candidate - baseline) | — | [-1.0000, -0.3882] |
| Candidate hard violations | — | 0 |
| Condition verdict | — | **BLOCK** |

## Candidate failure clusters

| Failure fingerprint | Count | Example failure detail |
|---|---:|---|
| `ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff` | 12 | No detail recorded. |

## Earlier runs on this candidate are never hidden

- `exp-earlier`

## Reasons

- Experiment: no global errors.
- `fetch_timeout`: regression bound crossed

VERDICT: BLOCK (exit 1)
