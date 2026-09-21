# Experiment ollama-retry-b-400-confirmatory-2

INCONCLUSIVE means there is not enough evidence either way: the confidence interval stays non-green, and no regression is claimed.

## Gate configuration

| Alpha | Delta | K (gating conditions) | Per-arm confidence | n_per_arm |
|---:|---:|---:|---:|---:|
| 0.0500 | 0.1000 | 1 | 97.5000% | 400 |

## Condition: reserve-timeout

| Measure | Baseline | Candidate / condition |
|---|---:|---:|
| Role | — | Gating |
| n | 400 | 400 |
| Successes | 376 | 308 |
| Success rate | 94.0% | 77.0% |
| Wilson 95% (display only) | [0.9123, 0.9594] | [0.7263, 0.8086] |
| Clopper-Pearson (97.5000%) | [0.9078, 0.9637] | [0.7192, 0.8157] |
| Bounds on difference (candidate - baseline) | — | [-0.2445, -0.0921] |
| Candidate hard violations | — | 0 |
| Condition verdict | — | **INCONCLUSIVE** |

## Candidate failure clusters

| Failure fingerprint | Count | Example failure detail |
|---|---:|---|
| `0d615ea1bb2e632e688ba1bd75deaaa73bdea58aeffbc010003b9a535a0cfbe5` | 68 | oracle rejected final state; first_failed_tool=reserve:timeout |
| `b641a1a968f0d962607c9145a76f070f84b3f641751407f569888f504b755dfa` | 17 | command exited non-zero |
| `b376c565db2dd4854767ef178cc9faa292faa0562e88e33b51d3bf2c14c57875` | 6 | oracle rejected final state; first_failed_tool=none |
| `55fb3f409155c035a8934a318c30fdcb987dfd35e2451ff9c2fe776c045d2cb9` | 1 | oracle rejected final state; first_failed_tool=confirm:tool_error |

## Earlier runs on this candidate are never hidden

- `ollama-retry-b-30 run 1: invalid, bridge advertised no tool parameters (17/30 vs 15/30)`
- `ollama-retry-b-30 run 2: exploratory, INCONCLUSIVE (29/30 vs 23/30)`
- `ollama-retry-b-400-confirmatory: invalid, ERROR; model server died at pair 182 of 400 (172/182 vs 143/183 before that)`

## Reasons

- Experiment: no global errors.
- `reserve-timeout`: bounds cross the margin

VERDICT: INCONCLUSIVE (exit 2)
