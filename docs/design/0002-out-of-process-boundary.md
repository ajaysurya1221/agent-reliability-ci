# 0002: the out-of-process boundary (v0.2)

Decision by the project owner's delegate, checked with an independent reviewer (2026-09-21).

## Problem

v0.1 tests Python functions written for it. A real user has an agent that is a program: `claude -p`,
`codex exec`, a LangGraph script. v0.1 also keeps the recorder, the environment and the fault latches
in the agent's own process, which is the largest gap in the trust model.

## Decision

A trial may be a **command agent**: any subprocess, whose tools are ONE stdio MCP server.

```text
parent (run_trial)
  |-- boundary process   python -P -m arci.mcp_boundary      harness-owned
  |      owns the real MCP server (child), the recorder, fault injection, budgets, latches
  |      streams the v0.1 frame protocol to the parent on its stdout
  |      listens on a unix socket in a short-lived trial directory
  |
  `-- agent process      the user's argv                      untrusted-but-not-hostile
         spawns only a thin shim:  python -P -m arci.mcp_shim --socket PATH
         the shim relays bytes between the agent's stdio and the socket. Nothing else.
```

The agent gets a standard MCP config file (`{"mcpServers": {name: {command, args, env}}}`) whose one
server entry is the shim. After the agent exits, a trusted `snapshot(task, workdir)` function runs in
the grader process and its result is the final state handed to the oracle.

Everything above the boundary is unchanged: schedule, gate, storage, reports, diff, minimiser,
bundles, replay semantics, exit codes.

## Supported MCP subset

Revision 2026-07-28, stdio transport (newline-delimited JSON-RPC, one message per line).
`initialize`, `notifications/initialized`, `ping`, `tools/list`, and SERIAL `tools/call` whose result
has `resultType: "complete"` (or no `resultType`, for older servers). Everything else that the boundary
cannot faithfully record and replay is a harness fault: task results, sampling, elicitation, a second
in-flight `tools/call`. One server per trial.

## Fault mapping

| perturbation | what the agent sees |
|---|---|
| `tool_timeout`, `tool_error_once` | an immediate result with `isError: true` and a text content naming the error kind; the real server is not called |
| `empty_result` | the real result with `content: []` |
| budget exhausted | `isError: true`, "tool budget exceeded"; the `budget` latch trips |

## Replay

Tool replay, not agent replay. The boundary serves the recording (including `initialize` and
`tools/list` responses) and never starts the server. JSON-RPC ids are normalised out of the recording.
The trial is graded on the recorded snapshot and only if the recording was consumed exactly. A live
model will often diverge; that is INVALID, never REPRODUCED. Determinism is claimed only for scripted
clients.

## Not in v0.2

HTTP transport, several servers, concurrent calls, automatic configuration of any particular agent
CLI, model-response replay, containment of a hostile agent, importers, new perturbations, statistics.
An agent can still bypass MCP entirely (files, network); the boundary sees only what goes through it.
