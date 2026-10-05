# Experiment guardrail-live-b-ask-low_confidence-50

PASS means the candidate is non-inferior to the baseline within the configured delta; it says nothing about absolute reliability.

## Gate configuration

| Alpha | Delta | K (gating conditions) | Interval method | Per-arm confidence | n_per_arm |
|---:|---:|---:|---|---:|---:|
| 0.0500 | 0.1000 | 1 | clopper_pearson | 97.5000% | 50 |

## Decisions

| Recorded decisions | Input tokens | Output tokens | Estimated cost at list price |
|---:|---:|---:|---:|
| 100 | 79164 | 14982 | USD 0.0033249 |

List price: USD 0.042 per million input tokens (read 2026-09-22).
Fixtures and replays cost nothing; this is an estimate, not billed spend.

## Condition: low_confidence

| Measure | Baseline | Candidate / condition |
|---|---:|---:|
| Role | — | Gating |
| n | 50 | 50 |
| Successes | 50 | 50 |
| Success rate | 100.0% | 100.0% |
| Wilson 95% (display only) | [0.9287, 1.0000] | [0.9287, 1.0000] |
| Clopper-Pearson (97.5000%) | [0.9161, 1.0000] | [0.9161, 1.0000] |
| Bounds on difference, clopper_pearson (candidate - baseline) | — | [-0.0839, 0.0839] |
| Candidate hard violations | — | 0 |
| Condition verdict | — | **PASS** |

## Candidate failure clusters

No candidate failures were recorded.

## Earlier runs on this candidate are never hidden

- None recorded.

## Reasons

- Experiment: no global errors.
- `low_confidence`: non-inferiority bound passed

VERDICT: PASS (exit 0)
