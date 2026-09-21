# Roadmap

v0.1 proves one thing: a measured regression becomes an executable, reduced failure case. It
supports Python agents that use the declared tool boundary. Everything below is deliberately out.

## v0.2 candidates, most valuable first

1. **MCP stdio proxy** (`arci mcp-proxy -- <server command>`): record, replay and inject faults for
   any MCP-speaking agent (Claude Code, Codex) with no agent changes. This is the vendor-neutral
   boundary.
2. **Command adapter** for non-Python agents, plus a loopback HTTP tool gateway.
3. **Importers**, split into analysis-only and replay-capable, built only from authentic versioned
   fixtures: OTLP GenAI spans, Claude Code `stream-json`, Codex `--json`.
4. **Sequential testing** with confidence sequences, so a gate can stop early without losing error
   control. The v0.1 rule is fixed-sample on purpose.
5. **A tighter exact test** for the non-inferiority margin. Clopper-Pearson with Bonferroni is valid
   and easy to audit, but conservative: see the calibration table.
6. **Cohort localisation** (spectrum-based scoring of step signatures across all passing and
   failing trials), and minimisation of injected context and recorded history.
7. **Task-clustered aggregation** across many tasks (average within task, then within family).
8. SQLite index and resumable runs, HTML report, a growing perturbation library
   (reordered results, misleading tool output, latency, crash-after-checkpoint).

## Known limits of v0.1

- The tool boundary only sees what goes through it. An agent that touches the filesystem or the
  network directly is outside the contract; a fresh working directory is not a sandbox.
- Deterministic replay is guaranteed for seeded, fixture-backed agents. A live model is not
  replayable token for token; what replays is the tool boundary.
- Hashes are integrity checks, not signatures.
- Trace divergence shows where two runs part ways. It is evidence for a cause, not proof of one.
