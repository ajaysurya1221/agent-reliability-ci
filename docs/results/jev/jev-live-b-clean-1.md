# Jev experiment: `jev-live-b-clean-1`

Run on 2026-10-03 against the live System One endpoint. The pre-registered clean pair: one trial per arm, no fault injected, Agent A against Agent B. At N=1 the gate is INCONCLUSIVE by construction (bounds on the difference span almost the whole range), so its verdict carries no information. What it checks is that both arms complete a trial on the live endpoint, which they did: two decisions, both status 200, both reporting the pinned model.

## Provider and preflight

| Item | Value |
|---|---|
| Endpoint | `https://api.typesafe.ai/v1/systemone` (TypeSafe direct, no gateway) |
| Pinned model | `jev-1.13.0`. Not in the account's `GET /v1/models` list, which carries only the aliases `jev-latest` and `jev-preview`; the smoke request and every recorded response reported it: `jev-1.13.0` x2 |
| Python SDK | not used: the Python agent speaks HTTP with the standard library (`typesafe-sdk` 0.7.1 was installed into the virtualenv only to run `tests/acceptance/test_decisions_sdk.py`, 2 passed, fixture upstream through the boundary) |
| JavaScript SDK | not used in this run (see the `-node` run) |
| Preflight receipt | `{"preflight":{"endpoint":"https://api.typesafe.ai/v1/systemone","latency_ms":473.5,"manifest_sha256":"2a1dd8fef3e3d5a102a20fc94fa330cf0128300aeee30f6c409c3387fc31a56f","model":"jev-1.13.0","request_id":"req_01a101c6fa607802a72263fb22ff0916","usage":{"input_tokens":353,"output_tokens":60}}}` |
| Manifest SHA-256 | `10c2b08b63370a7c37ef5f2b32dae2803b1f2b3e550628d3ddd8595d9d4c7809` |
| Trials SHA-256 | `ad3234ef79f8109ac4f2fc65829cd3f22da8b8a1a2d01981a33958df89c303e7` |
| Decision record SHA-256 | `d2bda9bd0dfbd43ff772d8a02e77f69f85be41a1593af2fb754a8882ec025059` |

Answers are sampled. Preflight ran once for the whole sequence with `--allow-unlisted-model`, which is new in this release: without it the pre-registered preflight exits 2 on this account because the pin is not listed. Prior runs sealed in the manifest: none. Note: attempt 1 of this run was invalid (see the index); this is attempt 2, the first in which a decision reached the endpoint.

## Gate configuration

| Alpha | Delta | Method | Looks | K | n per arm | Request rate |
|---:|---:|---|---|---:|---:|---:|
| 0.05 | 0.10 | `clopper_pearson` | fixed, one look at 1 | 1 | 1 | 200 paced trial starts per minute, at most 3 decisions per trial |

## Verdict and bounds

**INCONCLUSIVE (exit 2)** — both arms completed and passed; at N=1 no non-inferiority or regression bound can clear the margin.

| Condition | Baseline | Candidate | Difference bounds | Verdict |
|---|---:|---:|---|---|
| `clean` | 1/1 | 1/1 | [-0.9875, 0.9875] | INCONCLUSIVE |

Per-arm Clopper-Pearson at 97.5%: baseline [0.0125, 1.0000], candidate [0.0125, 1.0000]. Candidate hard violations: 0. Reason: bounds cross the margin. Mean wall time per trial: baseline 1.07 s, candidate 1.15 s.

## Decisions, tokens and estimated cost

| Recorded decisions | Input tokens | Output tokens | Estimated USD at list price |
|---:|---:|---:|---:|
| 2 | 944 | 178 | 0.0000396 |

The estimate uses the list price of USD 0.042 per million input tokens read on 2026-09-22 and is not billed spend. Upstream: 2 with status 200; 2 with `attempts` = 1; no 429 or 529 and no bounded wait (`first_status` null throughout).

## Candidate failure clusters

No candidate failures were recorded.

## Limitations

- N=1 cannot decide anything; this run is a sanity check, kept because the discipline keeps every run.
- Under the `clean` condition every one of the recorded decisions reported `department.confidence` 1.0: the three seeded tickets are unambiguous, so this run shows the live model at ceiling and says nothing about calibration or about ambiguous tickets.
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
.venv/bin/python -m examples.jev_triage_agent.experiment --candidate b --n-per-arm 1 \
    --condition clean --runtime python --base-url https://api.typesafe.ai --model jev-1.13.0 --rpm 200 \
    --out manifest.json
.venv/bin/arci preflight --allow-unlisted-model manifest.json
.venv/bin/arci run manifest.json --out runs/jev-2026-10-03 --workers 4
.venv/bin/arci gate runs/jev-2026-10-03/jev-live-b-clean-1 --markdown report.md --junit junit.xml
# Re-derive the committed verdict from the committed records (byte-identical decision.json):
.venv/bin/arci gate docs/results/jev/2026-10-03/jev-live-b-clean-1
```

