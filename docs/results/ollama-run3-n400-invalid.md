# Experiment ollama-retry-b-400-confirmatory

ERROR means the experiment is invalid or the harness or grader failed, so no reliability conclusion can be drawn.

## Gate configuration

| Alpha | Delta | K (gating conditions) | Per-arm confidence | n_per_arm |
|---:|---:|---:|---:|---:|
| 0.0500 | 0.1000 | 1 | 97.5000% | 400 |

## Condition: reserve-timeout

| Measure | Baseline | Candidate / condition |
|---|---:|---:|
| Role | — | Gating |
| n | 400 | 400 |
| Successes | 172 | 143 |
| Success rate | 43.0% | 35.8% |
| Wilson 95% (display only) | [0.3824, 0.4790] | [0.3121, 0.4056] |
| Clopper-Pearson (97.5000%) | [0.3741, 0.4872] | [0.3041, 0.4136] |
| Bounds on difference (candidate - baseline) | — | [-0.1831, 0.0395] |
| Candidate hard violations | — | 0 |
| Condition verdict | — | **ERROR** |

## Candidate failure clusters

| Failure fingerprint | Count | Example failure detail |
|---|---:|---|
| `b641a1a968f0d962607c9145a76f070f84b3f641751407f569888f504b755dfa` | 217 | command exited non-zero |
| `0d615ea1bb2e632e688ba1bd75deaaa73bdea58aeffbc010003b9a535a0cfbe5` | 36 | oracle rejected final state; first_failed_tool=reserve:timeout |
| `55fb3f409155c035a8934a318c30fdcb987dfd35e2451ff9c2fe776c045d2cb9` | 2 | oracle rejected final state; first_failed_tool=confirm:tool_error |
| `b376c565db2dd4854767ef178cc9faa292faa0562e88e33b51d3bf2c14c57875` | 2 | oracle rejected final state; first_failed_tool=none |

## Earlier runs on this candidate are never hidden

- `ollama-retry-b-30 (run 1, bridge advertised no tool parameters)`
- `ollama-retry-b-30 (run 2, exploratory, INCONCLUSIVE 29/30 vs 23/30)`

## Reasons

- Experiment: trial outcome ERROR
- `reserve-timeout`: trial outcome ERROR

VERDICT: ERROR (exit 3)
