# Results: the triage agent against the live System One endpoint

Day one against Jev, run on 2026-10-03 from `examples/jev_triage_agent/day_one.sh` as
pre-registered in `docs/design/0004-day-one.md`. Endpoint `https://api.typesafe.ai/v1/systemone`
(TypeSafe direct, no gateway), pinned model `jev-1.13.0`, 200 paced trial starts per minute,
4 workers, one account, one afternoon. Each run has a write-up from `docs/results/TEMPLATE-jev.md`
and its sealed store (`manifest.json`, `trials.jsonl`, `decision.json`, `report.md`, `junit.xml`)
under `2026-10-03/<experiment_id>/`, so `arci gate 2026-10-03/<experiment_id>` re-derives every
verdict from the committed records (checked before committing: byte-identical `decision.json` for
all seven). Invalid and inconclusive runs stay in the table.

## Preflight

The account's `GET /v1/models` lists only the aliases `jev-latest` and `jev-preview`. The
pre-registered preflight therefore exits 2 on the pinned versioned id; with the new
`--allow-unlisted-model` the smoke request verified the pin (`2026-10-03/preflight.txt`,
`2026-10-03/preflight.receipt.json`):

```json
{"preflight":{"endpoint":"https://api.typesafe.ai/v1/systemone","latency_ms":473.5,"manifest_sha256":"2a1dd8fef3e3d5a102a20fc94fa330cf0128300aeee30f6c409c3387fc31a56f","model":"jev-1.13.0","request_id":"req_01a101c6fa607802a72263fb22ff0916","usage":{"input_tokens":353,"output_tokens":60}}}
```

## The runs

| Run | Arms | Condition | N per arm | A | B or C | Bounds on the difference | Verdict | What happened |
|---|---|---|---:|---:|---:|---|---|---|
| attempt 1 (all six) | | | | 0/n | 0/n | | INCONCLUSIVE, PASS, PASS, PASS, ERROR | **Invalid, zero decisions.** The script ran `arci` without the repository root on `PYTHONPATH`, so neither the agent nor the toolset server could import `examples.jev_triage_agent`; every trial crashed in about 0.6 s before its first decision. Both arms failed identically, so the gate said PASS for A vs B, A vs A and A vs C; the Node run was ERROR (its MCP server exited). Stores: `2026-10-03/attempt-1-invalid/`. |
| `jev-live-b-clean-1` | A vs B | none | 1 | 1/1 | 1/1 | [-0.9875, 0.9875] | INCONCLUSIVE (exit 2) | The clean pair. Both arms completed and passed, which is all N=1 can show. |
| `jev-live-b-low_confidence-50` | A vs B | `decision_low_confidence` | 50 | 50/50 | 0/50 | [-1.0000, -0.8322] | **BLOCK** (exit 1) | The regression under capped confidence. Same counts and bounds as the seeded-fixture run of 2026-09-22. |
| `jev-live-a-low_confidence-50` | A vs A | `decision_low_confidence` | 50 | 50/50 | 50/50 | [-0.0839, 0.0839] | PASS (exit 0) | The same agent in both arms. |
| `jev-live-c-low_confidence-50` | A vs C | `decision_low_confidence` | 50 | 50/50 | 50/50 | [-0.0839, 0.0839] | PASS (exit 0) | The repair restores escalation. |
| `jev-live-b-low_confidence-50-node` | A vs B | `decision_low_confidence` | 50 | 50/50 | 0/50 | [-1.0000, -0.8322] | **BLOCK** (exit 1) | The Node agent through the official `@typesafe-ai/sdk` 0.6.0, unchanged. |
| `jev-live-b-low_confidence-200` | A vs B | `decision_low_confidence` | 200 | 200/200 | 0/200 | [-1.0000, -0.9567] | **BLOCK** (exit 1) | The pre-registered design, listing the five runs above as prior runs. The first B failure was diffed against its A pair, minimised (`reduced`, one fault kept) and replayed from the bundle: REPRODUCED. |
| `jev-live-b-clean-50` | A vs B | none | 50 | 50/50 | 50/50 | [-0.0839, 0.0839] | PASS (exit 0) | **Exploratory, not pre-registered**, added after the sequence and listing all six runs above as prior runs. All 100 decisions came back at `department.confidence` 1.0 with the department matching the ticket, so both agents acted correctly; B's regression is specific to low confidence. |

Gate on every run: alpha 0.05, delta 0.10, `clopper_pearson`, one look, K=1. Reports:
`jev-live-b-clean-1.md`, `jev-live-b-low_confidence-50.md`, `jev-live-a-low_confidence-50.md`,
`jev-live-c-low_confidence-50.md`, `jev-live-b-low_confidence-50-node.md`,
`jev-live-b-low_confidence-200.md`, `jev-live-b-clean-50.md`.

| Totals over the seven valid runs | |
|---|---:|
| Recorded decisions | 902 |
| Upstream status 200 on the first attempt | 902 of 902 (no 429 or 529, no bounded wait) |
| Reported model | `jev-1.13.0` on every decision |
| Input tokens | 428,272 |
| Output tokens | 80,278 |
| Estimated cost at the list price read on 2026-09-22 (USD 0.042 per million input tokens) | USD 0.018 |
| Mean wall time per trial | 1.14 to 1.16 s (Python agent), 1.23 to 1.24 s (Node agent) |

## What this shows

- The whole v0.5 and v0.6 path works against the real service: key held by the harness, a per-trial
  token for the agent, the pinned model reported on every answer, paced trial starts, recorded and
  sealed decisions, both official SDKs unchanged, the gate, the diff, the minimiser and the replay.
- The planted regression is caught with the real endpoint supplying the answers, at N=50 and at the
  pre-registered N=200, in Python and in Node, and the two controls (A vs A, A vs C) pass.
- The example's agents act correctly on the live model's answers when nothing is injected.

## What this does not show

- Anything about the model's calibration or accuracy beyond three unambiguous seeded tickets, on
  which it answered every clean decision at confidence 1.0. `decision_low_confidence` is injected by
  the harness (the served `confidence` is capped at 0.4 on the first decision of each trial), so
  the low-confidence verdicts measure the agents' handling of low confidence, not the model's
  uncertainty. Under the cap A escalates and B routes on every trial, so those counts are
  deterministic given the agents; the live model supplied the answers, not the variance.
- Billed spend (the cost above is list price applied to recorded tokens), provider behaviour under
  load (no 429 or 529 was seen at 200 paced trial starts per minute), or the gateway route.
- Minimality: live answers are sampled, so the minimised bundle is `reduced`, never `1-minimal`.

## What the key taught us

Four things in the pre-registered plan did not survive contact with the real service and are
fixed in this release (details in `docs/DECISIONS.md`, "What day one found"): the alias-only
model list (`arci preflight --allow-unlisted-model`); a smoke question needs `instructions`; a
CONNECT-proxy-only network needs `ARCI_HTTPS_PROXY`; and the example manifests need the repository
root on `PYTHONPATH` when `arci` is the console script. The invalid first attempt in the table is
the fourth one. Its gate verdicts are a reminder that the gate compares arms: a harness fault that
breaks both arms equally yields PASS, so the clean pair's trial outcomes, not its verdict, are the
sanity check, and `day_one.sh` now stops with exit 4 unless both clean-pair arms PASS.

## Re-check

```bash
export PYTHONPATH="$PWD"
for run in docs/results/jev/2026-10-03/jev-live-*; do .venv/bin/arci gate "$run" > /dev/null; git diff --stat -- "$run/decision.json"; done
.venv/bin/arci replay docs/results/jev/2026-10-03/jev-live-b-low_confidence-200/min-bundle.json
```

`arci gate` rewrites `decision.json` from `manifest.json` and `trials.jsonl`; an empty diff means
the committed verdict re-derives. The replay serves the recorded answer and makes no upstream
call, so neither command needs a key.
