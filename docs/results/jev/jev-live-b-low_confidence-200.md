# Jev experiment: `jev-live-b-low_confidence-200`

Run on 2026-10-03 against the live System One endpoint. The pre-registered design (`docs/design/0004-day-one.md`): A versus B under `decision_low_confidence` at N=200 per arm, listing the five earlier live runs as prior runs in its sealed manifest. The first B failure with a passing A pair was diffed against its baseline, minimised and replayed from the bundle (see below).

## Provider and preflight

| Item | Value |
|---|---|
| Endpoint | `https://api.typesafe.ai/v1/systemone` (TypeSafe direct, no gateway) |
| Pinned model | `jev-1.13.0`. Not in the account's `GET /v1/models` list, which carries only the aliases `jev-latest` and `jev-preview`; the smoke request and every recorded response reported it: `jev-1.13.0` x400 |
| Python SDK | not used: the Python agent speaks HTTP with the standard library (`typesafe-sdk` 0.7.1 was installed into the virtualenv only to run `tests/acceptance/test_decisions_sdk.py`, 2 passed, fixture upstream through the boundary) |
| JavaScript SDK | not used in this run (see the `-node` run) |
| Preflight receipt | `{"preflight":{"endpoint":"https://api.typesafe.ai/v1/systemone","latency_ms":473.5,"manifest_sha256":"2a1dd8fef3e3d5a102a20fc94fa330cf0128300aeee30f6c409c3387fc31a56f","model":"jev-1.13.0","request_id":"req_01a101c6fa607802a72263fb22ff0916","usage":{"input_tokens":353,"output_tokens":60}}}` |
| Manifest SHA-256 | `9401c00021f7acdc7e0c915c2cd8a700de30248e33a5a4c4d5e97dd2bf3e21ce` |
| Trials SHA-256 | `89f883ac64b17a2637bbf6b2b7de31794128c8936db30a53dd727614dc67ea4d` |
| Decision record SHA-256 | `a815720937fe04babe41d5de1993064d547ed1df808f35e4493256d0245ddd76` |

Answers are sampled. Preflight ran once for the whole sequence with `--allow-unlisted-model`, which is new in this release: without it the pre-registered preflight exits 2 on this account because the pin is not listed. Prior runs sealed in the manifest: `jev-live-b-clean-1`, `jev-live-b-low_confidence-50`, `jev-live-a-low_confidence-50`, `jev-live-c-low_confidence-50`, `jev-live-b-low_confidence-50-node`. Note: attempt 1 of this run was invalid (see the index); this is attempt 2, the first in which a decision reached the endpoint.

## Gate configuration

| Alpha | Delta | Method | Looks | K | n per arm | Request rate |
|---:|---:|---|---|---:|---:|---:|
| 0.05 | 0.10 | `clopper_pearson` | fixed, one look at 200 | 1 | 200 | 200 paced trial starts per minute, at most 3 decisions per trial |

## Verdict and bounds

**BLOCK (exit 1)** — the upper bound on the difference is below the -0.10 margin; B fails on every trial where A succeeds.

| Condition | Baseline | Candidate | Difference bounds | Verdict |
|---|---:|---:|---|---|
| `low_confidence` | 200/200 | 0/200 | [-1.0000, -0.9567] | BLOCK |

Per-arm Clopper-Pearson at 97.5%: baseline [0.9783, 1.0000], candidate [0.0000, 0.0217]. Candidate hard violations: 0. Reason: regression bound crossed. Mean wall time per trial: baseline 1.16 s, candidate 1.15 s.

## Decisions, tokens and estimated cost

| Recorded decisions | Input tokens | Output tokens | Estimated USD at list price |
|---:|---:|---:|---:|
| 400 | 189888 | 35600 | 0.0079753 |

The estimate uses the list price of USD 0.042 per million input tokens read on 2026-09-22 and is not billed spend. Upstream: 400 with status 200; 400 with `attempts` = 1; no 429 or 529 and no bounded wait (`first_status` null throughout).

## Candidate failure clusters

| Failure fingerprint | Count | Example failure detail |
|---|---:|---|
| `b376c565db2dd4854767ef178cc9faa292faa0562e88e33b51d3bf2c14c57875` | 200 | oracle rejected final state; first_failed_tool=none |

## Divergence, minimisation and replay

`arci diff` of the first B failure against its passing A pair, then `arci minimize` of that trial and `arci replay` of the bundle (`min-bundle.json`, 10292 bytes, embeds no code):

```text
mode: boundary
common_prefix: 2
left: tool_finish tool="decision:systemone" ok=true status=200 value#0e7d6286 error_kind=null injected_by="decision_low_confidence"
right: tool_finish tool="decision:systemone" ok=true status=200 value#2efc29db error_kind=null injected_by="decision_low_confidence"
after_injection: decision_low_confidence
```

```text
kept: decision_low_confidence
removed: none
minimality: reduced
trials_run: 1
```

```text
REPRODUCED: failure reproduced
```

The condition has one fault, so there is nothing to remove; minimality is reported as `reduced`, never `1-minimal`, because the answers are sampled. The replay serves the recorded answer from the bundle and makes no upstream call.

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
.venv/bin/python -m examples.jev_triage_agent.experiment --candidate b --n-per-arm 200 \
    --condition low_confidence --runtime python --base-url https://api.typesafe.ai --model jev-1.13.0 --rpm 200 \
    --prior-run jev-live-b-clean-1 \
    --prior-run jev-live-b-low_confidence-50 \
    --prior-run jev-live-a-low_confidence-50 \
    --prior-run jev-live-c-low_confidence-50 \
    --prior-run jev-live-b-low_confidence-50-node \
    --out manifest.json
.venv/bin/arci preflight --allow-unlisted-model manifest.json
.venv/bin/arci run manifest.json --out runs/jev-2026-10-03 --workers 4
.venv/bin/arci gate runs/jev-2026-10-03/jev-live-b-low_confidence-200 --markdown report.md --junit junit.xml
# Re-derive the committed verdict from the committed records (byte-identical decision.json):
.venv/bin/arci gate docs/results/jev/2026-10-03/jev-live-b-low_confidence-200
```

