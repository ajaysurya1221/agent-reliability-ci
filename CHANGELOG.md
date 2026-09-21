# Changelog

## v0.2.0 (2026-09-21)

Command agents: test any program that speaks MCP over stdio, not only Python functions.

### Added

- **The out-of-process boundary.** A trial can be any subprocess (`CommandSpec`). Its tools are ONE
  stdio MCP server owned by the harness (`McpServerSpec`). The agent's process tree holds only a
  byte-relay shim (`arci.mcp_shim`); the recorder, fault injection, budgets and fault latches live in
  a harness-owned boundary process (`arci.mcp_boundary`). Same frame protocol, latch precedence,
  deadlines, process-group cleanup and sealed envelopes as v0.1.
- Supported MCP subset (revision 2026-07-28): `initialize`, `notifications/initialized`, `ping`,
  `tools/list`, serial `tools/call` with `resultType: "complete"`. Task results, sampling,
  elicitation and concurrent calls are a harness ERROR, never a silent pass-through.
- Replay for command agents: the recording includes `initialize` and `tools/list`, the server is
  never started, JSON-RPC ids are normalised, consumption must be exact.
- `arci.mcp_toolset_server`: serve any v0.1 python toolset as an MCP server, with a trusted
  `snapshot` for grading.
- `examples/ollama_mcp_agent`: a real tool-calling agent on a local model, with a one-sentence
  prompt regression between its arms. `docs/REAL_AGENTS.md`, `docs/design/0002-...md`.
- Schema `arci/0.2`: `ArmSpec.command`, `Manifest.mcp_server`, `McpServerSpec.snapshot`. An
  experiment is all python agents or all command agents. v0.1 run stores must be re-run.

### Trust model

For command agents the record can no longer be corrupted by accident from inside the agent's
process. This is isolation from accident, not a sandbox: the agent still holds the socket it was
given, and whatever it does outside MCP is invisible.

### Known limits

- One MCP server per trial, stdio only. No HTTP transport yet.
- Tool replay is not agent replay: a live model rarely repeats its calls, so replaying its bundle is
  usually INVALID. Deterministic replay is demonstrated only with scripted clients.
- The Claude Code recipe in `docs/REAL_AGENTS.md` is an untested sketch; no paid-agent trials were
  run for this release. The local-model results are exploratory (one machine, one small model).
- POSIX only (unix sockets, process groups).

## v0.1.0 (2026-09-21)

First release. One claim: a measured regression becomes an executable, reduced failure case.

### What is in it

- Frozen, sealed experiments (`Manifest`), a deterministic paired schedule, one fresh process per
  trial with a separate grader process, a single parent writer for `events.jsonl` and `trials.jsonl`.
- The tool boundary (`ToolBox`): budgets, seeded fault injection (`tool_timeout`, `tool_error_once`,
  `empty_result`, or your own `"module:function"`), record and replay.
- The gate: exact Clopper-Pearson at tail `alpha / (4K)`, Bonferroni bounds on the difference,
  verdicts PASS / BLOCK / INCONCLUSIVE / ERROR with exit codes 0 / 1 / 2 / 3. It never raises.
- `bench/selfcheck.py`: the gate's own operating characteristics by exact enumeration.
- Boundary-aligned trace divergence, ddmin fault minimisation with an honest 1-minimal claim,
  portable replay bundles with hash-verified embedded code.
- CLI (`arci run | gate | report | bundle | replay | diff | minimize`), Markdown and JUnit reports,
  a composite GitHub Action.
- `examples/retry_agent`: agents A, B (A minus one retry) and C (the repair), with a six-step demo.

### How it was checked

229 tests, basedpyright strict, CI on Python 3.11 and 3.14. The acceptance suite was written before
the implementation and is hash-pinned (`FROZEN.sha256`). An adversarial reviewer attacked the design and
the code in four rounds, with reproductions: about 45 findings. They were fixed, or, where out of
scope (a hostile in-process agent, detached descendants), documented as non-goals. The behavioural
fixes have frozen regression tests (`tests/acceptance/test_hardening*.py` and the gate, replay and
schema suites); documentation corrections and the protocol queue bound do not. Every published
calibration number was recomputed independently by the reviewer and matched.

### Known limits and residual risks

- Trust model: the agent is assumed buggy, not hostile. It shares a process with the tool boundary,
  so a deliberately hostile agent can forge its result. See `docs/TRUST_MODEL.md`.
- Only the tool boundary is observed. Direct file, network or subprocess use by the agent is
  invisible. Descendants that start their own session survive cleanup.
- The gate is conservative by design: mid-range success rates need large N to reach PASS, and
  N=20 decides almost nothing. `prior_runs` is author-supplied; no cross-run error budget is enforced.
- Supported statistics range: `alpha` in [1e-6, 0.5] with `alpha >= K x 1e-6`, `n_per_arm <= 10000`.
- Bundles embed only the files you include; the minimiser's output embeds none.
- The final reviewer re-check ran on Python 3.13 in a read-only sandbox, so writing bundle payloads
  to disk was exercised by the test suite and CI (3.11, 3.14) but not by that review.
- POSIX only (process groups, `ps` in tests). Windows is untested.
