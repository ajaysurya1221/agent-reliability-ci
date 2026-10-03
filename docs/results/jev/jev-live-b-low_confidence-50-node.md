# Jev experiment: `jev-live-b-low_confidence-50-node`

Run on 2026-10-03 against the live System One endpoint. A versus B under `decision_low_confidence` at N=50 with the Node agent, which calls the endpoint through the official `@typesafe-ai/sdk` 0.6.0 unchanged (`new TypeSafeClient()`, configured only by `TYPESAFE_BASE_URL` and `TYPESAFE_API_KEY`, which the harness points at its loopback boundary with a per-trial token). Same verdict and the same counts as the Python agent; trials took about 0.07 s longer each.

## Provider and preflight

| Item | Value |
|---|---|
| Endpoint | `https://api.typesafe.ai/v1/systemone` (TypeSafe direct, no gateway) |
| Pinned model | `jev-1.13.0`. Not in the account's `GET /v1/models` list, which carries only the aliases `jev-latest` and `jev-preview`; the smoke request and every recorded response reported it: `jev-1.13.0` x100 |
| Python SDK | not used: the Python agent speaks HTTP with the standard library (`typesafe-sdk` 0.7.1 was installed into the virtualenv only to run `tests/acceptance/test_decisions_sdk.py`, 2 passed, fixture upstream through the boundary) |
| JavaScript SDK | `@typesafe-ai/sdk` 0.6.0, unchanged |
| Preflight receipt | `{"preflight":{"endpoint":"https://api.typesafe.ai/v1/systemone","latency_ms":473.5,"manifest_sha256":"2a1dd8fef3e3d5a102a20fc94fa330cf0128300aeee30f6c409c3387fc31a56f","model":"jev-1.13.0","request_id":"req_01a101c6fa607802a72263fb22ff0916","usage":{"input_tokens":353,"output_tokens":60}}}` |
| Manifest SHA-256 | `d011cd04cb2dd8bc460d7d2bf14f1f6b502ef2e3f5371973cfec25de092966c4` |
| Trials SHA-256 | `d33b5f6d69ff29d9bacb688dd21924da4d3aa9fe6d6ef634f61acc167f2d68f6` |
| Decision record SHA-256 | `fabfdc83f2f4641c94f9891d013c43c7f93d6b9e1dd665c13cea244a2eb2f9bb` |

Answers are sampled. Preflight ran once for the whole sequence with `--allow-unlisted-model`, which is new in this release: without it the pre-registered preflight exits 2 on this account because the pin is not listed. Prior runs sealed in the manifest: none. Note: attempt 1 of this run was invalid (see the index); this is attempt 2, the first in which a decision reached the endpoint.

## Gate configuration

| Alpha | Delta | Method | Looks | K | n per arm | Request rate |
|---:|---:|---|---|---:|---:|---:|
| 0.05 | 0.10 | `clopper_pearson` | fixed, one look at 50 | 1 | 50 | 200 paced trial starts per minute, at most 3 decisions per trial |

## Verdict and bounds

**BLOCK (exit 1)** — the upper bound on the difference is below the -0.10 margin, so B is worse than A under this condition, through the official SDK.

| Condition | Baseline | Candidate | Difference bounds | Verdict |
|---|---:|---:|---|---|
| `low_confidence` | 50/50 | 0/50 | [-1.0000, -0.8322] | BLOCK |

Per-arm Clopper-Pearson at 97.5%: baseline [0.9161, 1.0000], candidate [0.0000, 0.0839]. Candidate hard violations: 0. Reason: regression bound crossed. Mean wall time per trial: baseline 1.23 s, candidate 1.24 s.

## Decisions, tokens and estimated cost

| Recorded decisions | Input tokens | Output tokens | Estimated USD at list price |
|---:|---:|---:|---:|
| 100 | 47488 | 8900 | 0.0019945 |

The estimate uses the list price of USD 0.042 per million input tokens read on 2026-09-22 and is not billed spend. Upstream: 100 with status 200; 100 with `attempts` = 1; no 429 or 529 and no bounded wait (`first_status` null throughout).

## Candidate failure clusters

| Failure fingerprint | Count | Example failure detail |
|---|---:|---|
| `b376c565db2dd4854767ef178cc9faa292faa0562e88e33b51d3bf2c14c57875` | 50 | oracle rejected final state; first_failed_tool=none |

## Limitations

- `decision_low_confidence` is injected by the harness (the boundary caps the served `confidence` at 0.4 on the first decision of each trial), so the low-confidence runs measure how the agents handle low confidence, not how often the live model is uncertain. Under the cap A escalates on every trial and B routes on every trial, so those outcomes are deterministic given the agents; the live model supplies the answers, not the variance.
- One account, one day, one pinned model, three seeded tickets; no gateway route was exercised.
- Answers are sampled; live minimisation is reported as `reduced`, never `1-minimal`.
- Cost is the list price read on 2026-09-22 applied to recorded input tokens, not billed spend.
- Stores keep the served and raw upstream answers and the request state; here the requests are the example's synthetic tickets, never customer data.

## Exact commands

```bash
# From the repository root. The manifests name the agent and the toolset server as
# examples.jev_triage_agent.* modules, which the arci console script cannot see otherwise.
export PYTHONPATH="$PWD"
# Only where outbound HTTPS must go through an HTTP CONNECT proxy (it did here):
# export ARCI_HTTPS_PROXY="http://127.0.0.1:<port>"
.venv/bin/python -m examples.jev_triage_agent.experiment --candidate b --n-per-arm 50 \
    --condition low_confidence --runtime node --base-url https://api.typesafe.ai --model jev-1.13.0 --rpm 200 \
    --out manifest.json
.venv/bin/arci preflight --allow-unlisted-model manifest.json
.venv/bin/arci run manifest.json --out runs/jev-2026-10-03 --workers 4
.venv/bin/arci gate runs/jev-2026-10-03/jev-live-b-low_confidence-50-node --markdown report.md --junit junit.xml
# Re-derive the committed verdict from the committed records (byte-identical decision.json):
.venv/bin/arci gate docs/results/jev/2026-10-03/jev-live-b-low_confidence-50-node
```

