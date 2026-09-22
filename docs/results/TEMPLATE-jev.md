# Jev experiment: `<experiment_id>`

This write-up reports one frozen run. Replace every placeholder; keep invalid and inconclusive runs.

## Provider and preflight

| Item | Value |
|---|---|
| Endpoint | `<base_url>/v1/systemone` |
| Pinned model | `<versioned model id>` |
| Python SDK | `typesafe-sdk <version or not used>` |
| JavaScript SDK | `@typesafe-ai/sdk <version or not used>` |
| Preflight receipt | `<credential-free JSON receipt>` |
| Manifest SHA-256 | `<sha256>` |

Answers are sampled. State whether the endpoint is TypeSafe direct or a gateway, and whether the
reported model differed from an alias used during development.

## Gate configuration

| Alpha | Delta | Method | Looks | K | n per arm | Request rate |
|---:|---:|---|---|---:|---:|---:|
| `<alpha>` | `<delta>` | `<interval_method>` | `<looks or fixed>` | `<K>` | `<N>` | `<per minute>` |

## Verdict and bounds

**`<PASS | BLOCK | INCONCLUSIVE | ERROR>` (exit `<code>`)** — `<one exact interpretation>`

| Condition | Baseline | Candidate | Difference bounds | Verdict |
|---|---:|---:|---|---|
| `<condition>` | `<x/n>` | `<x/n>` | `<lower, upper>` | `<verdict>` |

## Decisions, tokens and estimated cost

| Recorded decisions | Input tokens | Output tokens | Estimated USD at list price |
|---:|---:|---:|---:|
| `<count>` | `<count>` | `<count>` | `<estimate>` |

The estimate uses the list price read on `<date>` and is not billed spend. Fixtures and replays
cost nothing. Note any bounded 429/529 wait from `upstream.attempts` and `first_status`.

## Candidate failure clusters

| Failure fingerprint | Count | Example failure detail |
|---|---:|---|
| `<sha256>` | `<count>` | `<deterministic detail>` |

## Limitations

- `<sampling, model alias/version, task coverage, privacy, invalid trials, or untested assumption>`
- `<live minimisation is reduced, not 1-minimal, when applicable>`

## Exact commands

```bash
arci preflight path/to/manifest.json
arci run path/to/manifest.json --out path/to/runs
arci report path/to/runs/experiment-id
```
