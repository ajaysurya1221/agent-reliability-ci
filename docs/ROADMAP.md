# Roadmap

v0.1 proved one thing: a measured regression becomes an executable, reduced failure case, for
Python agents. v0.2 extends that to any program that speaks MCP over stdio.

## Done in v0.2

The out-of-process boundary: command agents (any subprocess) behind a harness-owned stdio MCP
boundary, with record, replay, budgets and fault injection; a bridge that serves any python toolset
as an MCP server; a real local-LLM example. See docs/REAL_AGENTS.md and
docs/design/0002-out-of-process-boundary.md.

## Next, most valuable first

1. **Sequential testing** with confidence sequences, so an experiment can stop early without losing
   error control. (The tighter interval shipped in v0.3 as `interval_method: newcombe`; an exact
   unconditional test is not planned unless enumeration finds Newcombe miscalibrated somewhere.)
3. **Streamable HTTP transport** and several MCP servers per trial.
4. **Importers**, split into analysis-only and replay-capable, built only from authentic versioned
   fixtures: OTLP GenAI spans, Claude Code `stream-json`, Codex `--json`.
5. **Cohort localisation** (spectrum-based scoring of step signatures across all passing and
   failing trials), and minimisation of injected context and recorded history.
6. **Task-clustered aggregation** across many tasks (average within task, then within family).
7. SQLite index and resumable runs, HTML report, a growing perturbation library
   (reordered results, misleading tool output, latency, crash-after-checkpoint).

## Known limits of v0.1

- The tool boundary only sees what goes through it. An agent that touches the filesystem or the
  network directly is outside the contract; a fresh working directory is not a sandbox.
- Deterministic replay is guaranteed for seeded, fixture-backed agents. A live model is not
  replayable token for token; what replays is the tool boundary.
- Hashes are integrity checks, not signatures.
- Trace divergence shows where two runs part ways. It is evidence for a cause, not proof of one.
