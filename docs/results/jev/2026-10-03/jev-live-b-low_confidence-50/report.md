# Experiment jev-live-b-low_confidence-50

BLOCK means the candidate is worse than the baseline by more than the configured delta, or it broke a hard invariant.

## Gate configuration

| Alpha | Delta | K (gating conditions) | Interval method | Per-arm confidence | n_per_arm |
|---:|---:|---:|---|---:|---:|
| 0.0500 | 0.1000 | 1 | clopper_pearson | 97.5000% | 50 |

## Decisions

| Recorded decisions | Input tokens | Output tokens | Estimated cost at list price |
|---:|---:|---:|---:|
| 100 | 47488 | 8900 | USD 0.0019945 |

List price: USD 0.042 per million input tokens (read 2026-09-22).
Fixtures and replays cost nothing; this is an estimate, not billed spend.

## Condition: low_confidence

| Measure | Baseline | Candidate / condition |
|---|---:|---:|
| Role | — | Gating |
| n | 50 | 50 |
| Successes | 50 | 0 |
| Success rate | 100.0% | 0.0% |
| Wilson 95% (display only) | [0.9287, 1.0000] | [0.0000, 0.0713] |
| Clopper-Pearson (97.5000%) | [0.9161, 1.0000] | [0.0000, 0.0839] |
| Bounds on difference, clopper_pearson (candidate - baseline) | — | [-1.0000, -0.8322] |
| Candidate hard violations | — | 0 |
| Condition verdict | — | **BLOCK** |

## Candidate failure clusters

| Failure fingerprint | Count | Example failure detail |
|---|---:|---|
| `b376c565db2dd4854767ef178cc9faa292faa0562e88e33b51d3bf2c14c57875` | 50 | oracle rejected final state; first_failed_tool=none |

## Earlier runs on this candidate are never hidden

- None recorded.

## Reasons

- Experiment: no global errors.
- `low_confidence`: regression bound crossed

VERDICT: BLOCK (exit 1)
