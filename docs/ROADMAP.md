# Roadmap

v0.1 proved one thing: a measured regression becomes an executable, reduced failure case, for
Python agents. v0.2 extends that to any program that speaks MCP over stdio. v0.5 adds System One
decisions made by command agents, and v0.6 makes the documented Jev workflow ready for day one.

## Done in v0.2

The out-of-process boundary: command agents (any subprocess) behind a harness-owned stdio MCP
boundary, with record, replay, budgets and fault injection; a bridge that serves any python toolset
as an MCP server; a real local-LLM example. See docs/REAL_AGENTS.md and
docs/design/0002-out-of-process-boundary.md.

## Done in v0.5

The command-agent boundary also serves `POST /v1/systemone`, keeps the real TypeSafe key out of the
agent, and records, perturbs, minimises and replays decisions. It supports seeded fixtures for CI
and a real Jev upstream. See docs/DECISIONS.md and docs/design/0003-decision-boundary.md.

## Done in v0.6

Day-one readiness: gateway path prefixes, tolerant vendor-shaped responses, preflight receipts,
parent-paced live runs, token/cost reporting, raw upstream snapshots, a pinned JavaScript SDK agent,
and release/write-up guidance. These behaviors are fixture-tested and derived from documentation;
they have not been run against Jev without a key.

## Next, most valuable first

1. (Shipped in v0.3 and v0.4: `interval_method: newcombe`, and pre-registered `looks` with equal
   Bonferroni spending. Alpha-spending functions or confidence sequences are not planned unless
   the Bonferroni cost proves too high in practice.)
2. **Per-request pacing through parent IPC**, replacing the documented divide-by-k trial-start
   approximation for agents that make several decisions per trial.
3. **Counterfactual replay of recorded decisions**, if agent-path dependence can be represented
   without overstating what a re-perturbed recording proves.
4. **Independent calibration audit of decision models on exact intervals**, which needs labelled
   real outputs and a key.
5. **System One emulator over a local model via `system-one-adapter`**.
6. **Streamable HTTP transport** and several MCP servers per trial.
7. **Importers**, split into analysis-only and replay-capable, built only from authentic versioned
   fixtures: OTLP GenAI spans, Claude Code `stream-json`, Codex `--json`.
8. **Cohort localisation** (spectrum-based scoring of step signatures across all passing and
   failing trials), and minimisation of injected context and recorded history.
9. **Task-clustered aggregation** across many tasks (average within task, then within family).
10. SQLite index and resumable runs, HTML report, a growing perturbation library
   (reordered results, misleading tool output, latency, crash-after-checkpoint).

## Known limits of v0.1

- The tool boundary only sees what goes through it. An agent that touches the filesystem or the
  network directly is outside the contract; a fresh working directory is not a sandbox.
- Deterministic replay is guaranteed for seeded, fixture-backed agents. A live model is not
  replayable token for token; what replays is the tool boundary.
- Hashes are integrity checks, not signatures.
- Trace divergence shows where two runs part ways. It is evidence for a cause, not proof of one.
