# 0003: the decision boundary (v0.5)

Decision by the project owner's delegate as lead architect, reviewed adversarially by an
independent senior consultant (gpt-6-astra, xhigh) on 2026-09-22. Research notes:
`jev-research-2026-09-22.md`.

## Problem

TypeSafe's Jev (2026-09-15) is a "System One" model: state plus typed questions in, calibrated
probabilities out in 70 to 500 ms, no text. Agents are starting to use it for routing, guardrails
and confidence-gated actions ("the answer tells you what; confidence tells you whether to act").
That gating logic is exactly the kind of code that regresses quietly: a dropped threshold, a
removed fallback, a retry that vanished in a refactor. arci could not see those calls: they are
HTTP, not MCP.

## Options considered

1. A decision boundary: record, replay, budget and perturb the agent's System One calls (chosen).
2. An independent calibration audit of decision models on arci's exact intervals. Second: it
   needs independently labelled real outputs, which fixtures cannot supply and the owner has no
   key. Noted on the roadmap.
3. Jev as a post-BLOCK trace-triage classifier. Later: deterministic step signatures come first.
4. Jev as a pre-execution tool guardrail in the owner's other repos. Belongs there; probabilistic
   advice cannot replace capability enforcement.
5. Jev as arci's oracle or inside the gate. Rejected: the oracle is a trusted bool and the gate is
   exact statistics; a model's confidence is not certified accuracy.

## Decision

`Manifest.decisions: DecisionSpec` (command agents only). The existing boundary process also
serves `POST /v1/systemone` and `GET /v1/models` on loopback. The agent finds it through the
official SDKs' own environment variables, so an agent using `typesafe-sdk` or `@typesafe-ai/sdk`
needs no change and never holds the real key.

```text
parent (run_trial)
  |-- boundary process       MCP unix socket + HTTP loopback listener
  |      records every admitted decision as a tool call named decision:systemone
  |      upstream: a trusted seeded fixture (offline, CI) or the real API with the harness's key
  |      lifetime now follows the agent's exit, not the MCP session's end
  `-- agent process          TYPESAFE_BASE_URL=http://127.0.0.1:<port>  TYPESAFE_API_KEY=<token>
```

Reusing `ToolCall`/`ToolResult`/`RecordedCall` under a reserved name means budgets, latches,
fingerprints, replay, diff, the minimiser and bundles work without new record types. The
schema version moved to `arci/0.5` because a new field with a default enters every seal.

Two perturbations, both targeting `decision:systemone`:

| perturbation | what the agent sees | bucket |
|---|---|---|
| `decision_low_confidence` | choice distributions mixed toward uniform until confidence equals `confidence_max`; ranking and winner unchanged; nouls and scores untouched | falsify when escalation is an oracle-approved fallback, else ceiling |
| `decision_unavailable` | HTTP 529 for every attempt from the chosen occurrence to the end of the trial (so SDK retries are exhausted) | falsify |

Mixing toward uniform cannot reverse a ranking, so the demo regression is not "acts on a wrong
answer" but "returns without acting when unsure": A escalates, B abandons, C is the repair.

## Fault classification

Real upstream trouble (network, auth, 429, 5xx, malformed answers, a raising fixture) is a harness
fault (ERROR): the experiment is invalid, the agent is not blamed. Injected 529s are ordinary
results. Local rejections (401 wrong token, 413, 422) are the agent's problem, served
deterministically, never recorded, never budgeted. Concurrent decision requests, or a decision
during an in-flight tool call, are unsupported and therefore harness faults.

## Not in v0.5

Python in-process agents (run them as command agents through the toolset bridge); an
Ollama-backed System One emulator (`system-one-adapter` exists); a descriptive calibration
table in reports (repeated decisions inside trials are not independent binomial draws);
disconnect injection; noul or score mutation; streamable HTTP MCP transport.
