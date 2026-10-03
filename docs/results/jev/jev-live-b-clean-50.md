# Jev experiment: `jev-live-b-clean-50`

Run on 2026-10-03 against the live System One endpoint. **Exploratory, not pre-registered.** Added after the six planned runs, A versus B under the `clean` condition at N=50, to show what the live model does on the seeded tickets when nothing is injected. Its manifest lists all six pre-registered runs as prior runs. Every one of the 100 decisions came back with `department.confidence` 1.0 and the department that matches the ticket's ground truth (billing for the duplicate charge, technical for the crash, sales for the plan question), so both agents acted correctly on every trial. B is fine here: its regression is specific to low confidence, which is the point of the `decision_low_confidence` runs.

## Provider and preflight

| Item | Value |
|---|---|
| Endpoint | `https://api.typesafe.ai/v1/systemone` (TypeSafe direct, no gateway) |
| Pinned model | `jev-1.13.0`. Not in the account's `GET /v1/models` list, which carries only the aliases `jev-latest` and `jev-preview`; the smoke request and every recorded response reported it: `jev-1.13.0` x100 |
| Python SDK | not used: the Python agent speaks HTTP with the standard library (`typesafe-sdk` 0.7.1 was installed into the virtualenv only to run `tests/acceptance/test_decisions_sdk.py`, 2 passed, fixture upstream through the boundary) |
| JavaScript SDK | not used in this run (see the `-node` run) |
| Preflight receipt | `{"preflight":{"endpoint":"https://api.typesafe.ai/v1/systemone","latency_ms":473.5,"manifest_sha256":"2a1dd8fef3e3d5a102a20fc94fa330cf0128300aeee30f6c409c3387fc31a56f","model":"jev-1.13.0","request_id":"req_01a101c6fa607802a72263fb22ff0916","usage":{"input_tokens":353,"output_tokens":60}}}` |
| Manifest SHA-256 | `72cee49e1e1157610d722d3a45eebea0cd1f338af941e8078ba0c3739f21142a` |
| Trials SHA-256 | `3253af2e5aa17d3c8adc49eaa6ee59c536dc598395748bbee6d1deececbb4287` |
| Decision record SHA-256 | `ce6209ba6ca4c2e26eaac76eaca2efeb9e6eb69d65615b31416a56ee4819b52d` |

Answers are sampled. Preflight ran once for the whole sequence with `--allow-unlisted-model`, which is new in this release: without it the pre-registered preflight exits 2 on this account because the pin is not listed. Prior runs sealed in the manifest: `jev-live-b-clean-1`, `jev-live-b-low_confidence-50`, `jev-live-a-low_confidence-50`, `jev-live-c-low_confidence-50`, `jev-live-b-low_confidence-50-node`, `jev-live-b-low_confidence-200`. Note: attempt 1 of this run was invalid (see the index); this is attempt 2, the first in which a decision reached the endpoint.

## Gate configuration

| Alpha | Delta | Method | Looks | K | n per arm | Request rate |
|---:|---:|---|---|---:|---:|---:|
| 0.05 | 0.10 | `clopper_pearson` | fixed, one look at 50 | 1 | 50 | 200 paced trial starts per minute, at most 3 decisions per trial |

## Verdict and bounds

**PASS (exit 0)** — both arms succeed on every trial; the live model is at ceiling on these three tickets.

| Condition | Baseline | Candidate | Difference bounds | Verdict |
|---|---:|---:|---|---|
| `clean` | 50/50 | 50/50 | [-0.0839, 0.0839] | PASS |

Per-arm Clopper-Pearson at 97.5%: baseline [0.9161, 1.0000], candidate [0.9161, 1.0000]. Candidate hard violations: 0. Reason: non-inferiority bound passed. Mean wall time per trial: baseline 1.15 s, candidate 1.15 s.

## Decisions, tokens and estimated cost

| Recorded decisions | Input tokens | Output tokens | Estimated USD at list price |
|---:|---:|---:|---:|
| 100 | 47488 | 8900 | 0.0019945 |

The estimate uses the list price of USD 0.042 per million input tokens read on 2026-09-22 and is not billed spend. Upstream: 100 with status 200; 100 with `attempts` = 1; no 429 or 529 and no bounded wait (`first_status` null throughout).

## Candidate failure clusters

No candidate failures were recorded.

## Limitations

- Not pre-registered. It was added after the planned sequence and is reported as exploratory.
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
.venv/bin/python -m examples.jev_triage_agent.experiment --candidate b --n-per-arm 50 \
    --condition clean --runtime python --base-url https://api.typesafe.ai --model jev-1.13.0 --rpm 200 \
    --prior-run jev-live-b-clean-1 \
    --prior-run jev-live-b-low_confidence-50 \
    --prior-run jev-live-a-low_confidence-50 \
    --prior-run jev-live-c-low_confidence-50 \
    --prior-run jev-live-b-low_confidence-50-node \
    --prior-run jev-live-b-low_confidence-200 \
    --out manifest.json
.venv/bin/arci preflight --allow-unlisted-model manifest.json
.venv/bin/arci run manifest.json --out runs/jev-2026-10-03 --workers 4
.venv/bin/arci gate runs/jev-2026-10-03/jev-live-b-clean-50 --markdown report.md --junit junit.xml
# Re-derive the committed verdict from the committed records (byte-identical decision.json):
.venv/bin/arci gate docs/results/jev/2026-10-03/jev-live-b-clean-50
```

