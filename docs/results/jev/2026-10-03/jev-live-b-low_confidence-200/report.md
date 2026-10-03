# Experiment jev-live-b-low_confidence-200

BLOCK means the candidate is worse than the baseline by more than the configured delta, or it broke a hard invariant.

## Gate configuration

| Alpha | Delta | K (gating conditions) | Interval method | Per-arm confidence | n_per_arm |
|---:|---:|---:|---|---:|---:|
| 0.0500 | 0.1000 | 1 | clopper_pearson | 97.5000% | 200 |

## Decisions

| Recorded decisions | Input tokens | Output tokens | Estimated cost at list price |
|---:|---:|---:|---:|
| 400 | 189888 | 35600 | USD 0.0079753 |

List price: USD 0.042 per million input tokens (read 2026-09-22).
Fixtures and replays cost nothing; this is an estimate, not billed spend.

## Condition: low_confidence

| Measure | Baseline | Candidate / condition |
|---|---:|---:|
| Role | — | Gating |
| n | 200 | 200 |
| Successes | 200 | 0 |
| Success rate | 100.0% | 0.0% |
| Wilson 95% (display only) | [0.9812, 1.0000] | [0.0000, 0.0188] |
| Clopper-Pearson (97.5000%) | [0.9783, 1.0000] | [0.0000, 0.0217] |
| Bounds on difference, clopper_pearson (candidate - baseline) | — | [-1.0000, -0.9567] |
| Candidate hard violations | — | 0 |
| Condition verdict | — | **BLOCK** |

## Candidate failure clusters

| Failure fingerprint | Count | Example failure detail |
|---|---:|---|
| `b376c565db2dd4854767ef178cc9faa292faa0562e88e33b51d3bf2c14c57875` | 200 | oracle rejected final state; first_failed_tool=none |

## Earlier runs on this candidate are never hidden

- `jev-live-b-clean-1`
- `jev-live-b-low_confidence-50`
- `jev-live-a-low_confidence-50`
- `jev-live-c-low_confidence-50`
- `jev-live-b-low_confidence-50-node`

## Reasons

- Experiment: no global errors.
- `low_confidence`: regression bound crossed

VERDICT: BLOCK (exit 1)
