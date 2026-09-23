# Retry demo, N=200 per arm (the README's headline numbers)

Recorded 2026-09-23 on a 15-core laptop with `examples/retry_agent/experiment.py`'s frozen manifests
(`build_manifest(candidate=...)`, condition `reserve_timeout`, `alpha` 0.05, `delta` 0.10,
Clopper-Pearson). Seeded fixture agents; no model calls. These are the three gate reports the
README quotes, unedited.

| Candidate | Baseline A | Candidate | Bounds on the difference | Verdict | Exit |
|---|---:|---:|---|---|---:|
| B (retry removed) | 192/200 | 132/200 | [-0.405, -0.183] | BLOCK | 1 |
| A (against itself) | 192/200 | 192/200 | [-0.068, 0.068] | PASS | 0 |
| C (repaired) | 192/200 | 192/200 | [-0.068, 0.068] | PASS | 0 |

Re-create them with `.venv/bin/python examples/retry_agent/hero_demo.py`, or:

```python
from arci.gate import decide
from arci.runner import run_experiment
from examples.retry_agent.experiment import build_manifest

manifest = build_manifest(candidate="agent_b")
trials = run_experiment(manifest, "runs", max_workers=8)
print(decide(manifest, trials).verdict)
```

---

## A versus B

# Experiment retry-agent-agent_b-reserve-timeout-200

BLOCK means the candidate is worse than the baseline by more than the configured delta, or it broke a hard invariant.

## Gate configuration

| Alpha | Delta | K (gating conditions) | Interval method | Per-arm confidence | n_per_arm |
|---:|---:|---:|---|---:|---:|
| 0.0500 | 0.1000 | 1 | clopper_pearson | 97.5000% | 200 |

## Condition: reserve-timeout

| Measure | Baseline | Candidate / condition |
|---|---:|---:|
| Role | — | Gating |
| n | 200 | 200 |
| Successes | 192 | 132 |
| Success rate | 96.0% | 66.0% |
| Wilson 95% (display only) | [0.9231, 0.9796] | [0.5919, 0.7221] |
| Clopper-Pearson (97.5000%) | [0.9168, 0.9847] | [0.5799, 0.7340] |
| Bounds on difference, clopper_pearson (candidate - baseline) | — | [-0.4048, -0.1829] |
| Candidate hard violations | — | 0 |
| Condition verdict | — | **BLOCK** |

## Candidate failure clusters

| Failure fingerprint | Count | Example failure detail |
|---|---:|---|
| `0d615ea1bb2e632e688ba1bd75deaaa73bdea58aeffbc010003b9a535a0cfbe5` | 65 | oracle rejected final state; first_failed_tool=reserve:timeout |
| `25667ce58569500f65dbe0208190529a5e130dca823ec257ed2eff7879fee08c` | 3 | oracle rejected final state; first_failed_tool=confirm:error |

## Earlier runs on this candidate are never hidden

- None recorded.

## Reasons

- Experiment: no global errors.
- `reserve-timeout`: regression bound crossed

VERDICT: BLOCK (exit 1)

---

## A versus A

# Experiment retry-agent-agent_a-reserve-timeout-200

PASS means the candidate is non-inferior to the baseline within the configured delta; it says nothing about absolute reliability.

## Gate configuration

| Alpha | Delta | K (gating conditions) | Interval method | Per-arm confidence | n_per_arm |
|---:|---:|---:|---|---:|---:|
| 0.0500 | 0.1000 | 1 | clopper_pearson | 97.5000% | 200 |

## Condition: reserve-timeout

| Measure | Baseline | Candidate / condition |
|---|---:|---:|
| Role | — | Gating |
| n | 200 | 200 |
| Successes | 192 | 192 |
| Success rate | 96.0% | 96.0% |
| Wilson 95% (display only) | [0.9231, 0.9796] | [0.9231, 0.9796] |
| Clopper-Pearson (97.5000%) | [0.9168, 0.9847] | [0.9168, 0.9847] |
| Bounds on difference, clopper_pearson (candidate - baseline) | — | [-0.0679, 0.0679] |
| Candidate hard violations | — | 0 |
| Condition verdict | — | **PASS** |

## Candidate failure clusters

| Failure fingerprint | Count | Example failure detail |
|---|---:|---|
| `0d615ea1bb2e632e688ba1bd75deaaa73bdea58aeffbc010003b9a535a0cfbe5` | 5 | oracle rejected final state; first_failed_tool=reserve:timeout |
| `25667ce58569500f65dbe0208190529a5e130dca823ec257ed2eff7879fee08c` | 3 | oracle rejected final state; first_failed_tool=confirm:error |

## Earlier runs on this candidate are never hidden

- None recorded.

## Reasons

- Experiment: no global errors.
- `reserve-timeout`: non-inferiority bound passed

VERDICT: PASS (exit 0)

---

## A versus C

# Experiment retry-agent-agent_c-reserve-timeout-200

PASS means the candidate is non-inferior to the baseline within the configured delta; it says nothing about absolute reliability.

## Gate configuration

| Alpha | Delta | K (gating conditions) | Interval method | Per-arm confidence | n_per_arm |
|---:|---:|---:|---|---:|---:|
| 0.0500 | 0.1000 | 1 | clopper_pearson | 97.5000% | 200 |

## Condition: reserve-timeout

| Measure | Baseline | Candidate / condition |
|---|---:|---:|
| Role | — | Gating |
| n | 200 | 200 |
| Successes | 192 | 192 |
| Success rate | 96.0% | 96.0% |
| Wilson 95% (display only) | [0.9231, 0.9796] | [0.9231, 0.9796] |
| Clopper-Pearson (97.5000%) | [0.9168, 0.9847] | [0.9168, 0.9847] |
| Bounds on difference, clopper_pearson (candidate - baseline) | — | [-0.0679, 0.0679] |
| Candidate hard violations | — | 0 |
| Condition verdict | — | **PASS** |

## Candidate failure clusters

| Failure fingerprint | Count | Example failure detail |
|---|---:|---|
| `0d615ea1bb2e632e688ba1bd75deaaa73bdea58aeffbc010003b9a535a0cfbe5` | 5 | oracle rejected final state; first_failed_tool=reserve:timeout |
| `25667ce58569500f65dbe0208190529a5e130dca823ec257ed2eff7879fee08c` | 3 | oracle rejected final state; first_failed_tool=confirm:error |

## Earlier runs on this candidate are never hidden

- None recorded.

## Reasons

- Experiment: no global errors.
- `reserve-timeout`: non-inferiority bound passed

VERDICT: PASS (exit 0)

