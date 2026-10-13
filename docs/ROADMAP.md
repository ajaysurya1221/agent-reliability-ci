# Roadmap

v0.1 proved one thing: a measured regression becomes an executable, reduced failure case, for
Python agents. v0.2 extends that to any program that speaks MCP over stdio. v0.5 adds System One
decisions made by command agents, and v0.6 makes the documented Jev workflow ready for day one, and
v0.7.0 runs it against Jev and publishes an intent-routing calibration audit, and v0.8.0 ships
the onboarding path (PyPI, `arci demo`, `arci.yaml` and `arci init`) whose target, a first
experiment in ten minutes, is measured by `docs/measurement/ttfv-protocol.md` and not yet
established by cold-reader receipts.

## Done in v0.2

The out-of-process boundary: command agents (any subprocess) behind a harness-owned stdio MCP
boundary, with record, replay, budgets and fault injection; a bridge that serves any python toolset
as an MCP server; a real local-LLM example. See docs/REAL_AGENTS.md and
docs/design/0002-out-of-process-boundary.md.

## Done in v0.3 and v0.4

`interval_method: newcombe`, and pre-registered `looks` with equal Bonferroni spending.
Alpha-spending functions or confidence sequences are not planned unless the Bonferroni cost proves
too high in practice.

## Done in v0.5

The command-agent boundary also serves `POST /v1/systemone`, keeps the real TypeSafe key out of the
agent, and records, perturbs, minimises and replays decisions. It supports seeded fixtures for CI
and a real Jev upstream. See docs/DECISIONS.md and docs/design/0003-decision-boundary.md.

## Done in v0.6

Day-one readiness: gateway path prefixes, tolerant vendor-shaped responses, preflight receipts,
parent-paced live runs, token/cost reporting, raw upstream snapshots, a pinned JavaScript SDK agent,
and release/write-up guidance. These behaviours were initially fixture-tested from vendor
documentation.

## Done in v0.7.0

The pre-registered day one ran against the direct Jev endpoint on 2026-10-03; see
[the committed results](results/jev/README.md). A pre-registered intent-routing calibration audit of
the decision model is published in [results/jev-calibration](results/jev-calibration/README.md)
(protocol: `bench/jev_calibration/PROTOCOL.md`). The gateway route, provider rate limits under load
and billed spend remain unverified.

## Done in v0.8.0

The onboarding release: the PyPI package and `uvx --from agent-reliability-ci arci demo`, the
`arci.yaml` descriptor with its generated JSON Schema, `arci init`, the smoke-design notice, the
current directory on the child import path, the CI install matrix and release workflow, the
measurement protocol, and the README's first screen. Also released: `arci plan`, opt-in
`arci report --pass-k` and the platform-portability fixes that had been on `main` since v0.7.0.
See [CHANGELOG.md](../CHANGELOG.md).

## Next, most valuable first

1. **Per-request pacing through parent IPC**, replacing the documented divide-by-k trial-start
   approximation for agents that make several decisions per trial.
2. **Counterfactual replay of recorded decisions**, if agent-path dependence can be represented
   without overstating what a re-perturbed recording proves.
3. **Extend the published intent-routing calibration audit** to labelled coding-agent permission
   decisions, with a separate protocol and explicit limits.
4. **System One emulator over a local model via `system-one-adapter`**.
5. **Streamable HTTP transport** and several MCP servers per trial.
6. **Importers**, split into analysis-only and replay-capable, built only from authentic versioned
   fixtures: OTLP GenAI spans, Claude Code `stream-json`, Codex `--json`.
7. **Cohort localisation** (spectrum-based scoring of step signatures across all passing and
   failing trials), and minimisation of injected context and recorded history.
8. **Task-clustered aggregation** across many tasks (average within task, then within family).
9. SQLite index and resumable runs, HTML report, a growing perturbation library
   (reordered results, misleading tool output, latency, crash-after-checkpoint).

## Known limits of v0.1

- The tool boundary only sees what goes through it. An agent that touches the filesystem or the
  network directly is outside the contract; a fresh working directory is not a sandbox.
- Deterministic replay is guaranteed for seeded, fixture-backed agents. A live model is not
  replayable token for token; what replays is the tool boundary.
- Hashes are integrity checks, not signatures.
- Trace divergence shows where two runs part ways. It is evidence for a cause, not proof of one.
