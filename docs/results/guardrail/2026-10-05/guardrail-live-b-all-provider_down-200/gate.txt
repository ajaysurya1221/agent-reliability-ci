# Experiment guardrail-live-b-all-provider_down-200

BLOCK means the candidate is worse than the baseline by more than the configured delta, or it broke a hard invariant.

## Gate configuration

| Alpha | Delta | K (gating conditions) | Interval method | Per-arm confidence | n_per_arm |
|---:|---:|---:|---|---:|---:|
| 0.0500 | 0.1000 | 1 | clopper_pearson | 97.5000% | 200 |

## Decisions

| Recorded decisions | Input tokens | Output tokens | Estimated cost at list price |
|---:|---:|---:|---:|
| 400 | 0 | 0 | USD 0.0000000 |

List price: USD 0.042 per million input tokens (read 2026-09-22).
Fixtures and replays cost nothing; this is an estimate, not billed spend.

## Condition: provider_down

| Measure | Baseline | Candidate / condition |
|---|---:|---:|
| Role | — | Gating |
| n | 200 | 200 |
| Successes | 187 | 138 |
| Success rate | 93.5% | 69.0% |
| Wilson 95% (display only) | [0.8920, 0.9616] | [0.6228, 0.7500] |
| Clopper-Pearson (97.5000%) | [0.8847, 0.9681] | [0.6111, 0.7616] |
| Bounds on difference, clopper_pearson (candidate - baseline) | — | [-0.3570, -0.1231] |
| Candidate hard violations | — | 0 |
| Condition verdict | — | **BLOCK** |

## Candidate failure clusters

| Failure fingerprint | Count | Example failure detail |
|---|---:|---|
| `d6f37728a2478b3bc05e5a2e3a7d58f189548565d3ef658cd00b9352cd18036f` | 62 | oracle rejected final state; first_failed_tool=decision:systemone:http_529 |

## Earlier runs on this candidate are never hidden

- `guardrail-live-b-ask-clean-1`
- `guardrail-live-b-ask-provider_down-50`
- `guardrail-live-b-ask-low_confidence-50`
- `guardrail-live-c-ask-clean-50`
- `guardrail-live-b-ask-provider_down-200`

## Reasons

- Experiment: no global errors.
- `provider_down`: regression bound crossed

VERDICT: BLOCK (exit 1)
