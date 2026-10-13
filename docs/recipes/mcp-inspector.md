# Gate an MCP agent: Inspector for discovery, ARCI for repeated faulted trials

Your agent is a program that talks to its tools over MCP. Two tools answer two different questions:

- **MCP Inspector** asks: does this server start, speak the protocol and list the tools I expect?
- **ARCI** asks: across repeated trials with injected tool faults, is the candidate agent less
  reliable than the baseline, and what did a failing trial do?

The runnable tree is [examples/recipes/mcp_agent](../../examples/recipes/mcp_agent):
`world.py` (a Python toolset with `fetch` and `store`, served over stdio by
`arci.mcp_toolset_server`, the "bridge"), `agent.py` (a scripted stdlib MCP client, variants
`retry` and `fragile`), `arci.yaml`, `mcp.inspector.json` and `task.json`. A test
(`tests/unit/recipes/test_mcp_agent.py`) runs the manual preflight and the commands below from a
copy of the tree.

## Setup

Copy the tree out of the clone and use an environment where `python` and `arci` both come from an
install of agent-reliability-ci (the bridge imports `arci`; `arci.yaml` and `mcp.inspector.json`
say `python`, resolved on `PATH`):

```bash
cp -R examples/recipes/mcp_agent mcp-recipe && cd mcp-recipe
python -m venv .venv && . .venv/bin/activate && pip install agent-reliability-ci
```

Before the PyPI release, activate the clone's `uv sync` environment instead. A `python` without
arci fails every trial as a harness ERROR.

## Step 1: Inspector preflight against the raw bridge

```bash
npx @modelcontextprotocol/inspector --cli --config mcp.inspector.json --server env --method tools/list
```

`mcp.inspector.json` starts the bridge directly (seed 0, `--task-file task.json`,
`"env": {"PYTHONPATH": "."}` so `world` imports from this directory). The Inspector connects,
initializes and lists the tools (its `tools/call` method calls one). It talks to the **raw**
server: ARCI's boundary is not in the path, so nothing it sees is recorded, budgeted or
fault-injected.

Recorded on the orchestrator's machine:

```text
$ npx -y @modelcontextprotocol/inspector@latest --cli --config mcp.inspector.json --server env --method tools/list
{"error":{"code":"error","message":"Server's protocol version is not supported: 2026-07-28"}}
exit: 1
```

Recorded by the orchestrator on 2026-10-13 with Inspector 2.10.1, whose bundled
`@modelcontextprotocol/sdk` 1.29.0 accepts protocol revisions up to 2025-11-25.

The bridge speaks MCP revision `2026-07-28` (the boundary's supported subset,
[ADR 0002](../design/0002-out-of-process-boundary.md)). Inspector 2.10.1, on TypeScript SDK 1.29.0,
rejects that version during `initialize`, so on that date **step 1 is blocked by the Inspector
SDK's version check**, not by the server. The manual preflight below checks the same three things
and works today. This recipe does not change the bridge's version handling.

### Manual preflight (no Node, standard library only)

This sends `initialize`, the `notifications/initialized` notification, `tools/list` and one
`tools/call` over a pipe to the server that `mcp.inspector.json` describes, launched with the
current interpreter:

```bash
python - <<'EOF'
import json, os, subprocess, sys

entry = json.load(open("mcp.inspector.json"))["mcpServers"]["env"]
messages = [
    {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2026-07-28",
     "capabilities": {}, "clientInfo": {"name": "preflight", "version": "1"}}},
    {"jsonrpc": "2.0", "method": "notifications/initialized"},
    {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
     "params": {"name": "fetch", "arguments": {"key": "answer"}}},
]
done = subprocess.run([sys.executable, *entry["args"]], env={**os.environ, **entry["env"]},
                      input="".join(json.dumps(m) + "\n" for m in messages),
                      capture_output=True, text=True, timeout=30, check=False)
for line in done.stdout.splitlines():
    print(line)
print("server exit", done.returncode, done.stderr.strip())
EOF
```

Expect three reply lines and `server exit 0`: `initialize` answers protocol `2026-07-28`,
`tools/list` names `fetch` and `store` with input schemas, and the call returns
`"isError": true` with `TimeoutError: upstream transient timeout`. Seed 0 is one of the world's
flaky upstreams (30% of seeds fail the first real `fetch`), so this error comes from the
environment itself, not from ARCI; the raw bridge never injects faults.

## Step 2: repeated, faulted trials through the boundary

```bash
arci run arci.yaml
```

`arci.yaml` is written by hand: `arci init` scaffolds Python arms only. Both arms are commands:
`python -P -m agent ... --variant retry` (baseline) and `--variant fragile` (candidate), with
`mcp_server` running the same bridge per trial (`{workdir}`, `{seed}`, `{task_file}` expanded at
launch) and `arci.mcp_toolset_server:snapshot` reading its final state for the oracle
`world:passed`. One condition, `tool_error_once` on `fetch` at occurrence 0, makes the first
`fetch` of every trial return `isError: true` at the boundary. `agent` and `world` import because
`arci run` appends the current directory to every child's import path (ADR 0006).

Expect `VERDICT: BLOCK (exit 1)` even though the stderr notice calls 8 trials per arm a smoke
design: `fragile` gives up on the injected error in every trial (0/8) while `retry` recovers (8/8),
and a total collapse is the one result N=8 can decide. A smaller drop would be INCONCLUSIVE here.

## Step 3: look at a failing trial

```bash
arci diff runs/mcp-fetch-retry fetch-error:00000:baseline fetch-error:00000:candidate
arci minimize runs/mcp-fetch-retry fetch-error:00000:candidate --out min.json
arci bundle runs/mcp-fetch-retry fetch-error:00000:candidate --out bundle.json --root . --include agent.py --include world.py
arci replay bundle.json
```

`diff` shows the divergence after `tool_error_once`: `retry` calls `fetch` again, `fragile` ends.
`replay` serves the recorded MCP exchanges (initialize, tools/list and every tools/call) to a fresh
run of the scripted agent, never starting the server, and exits 0 when the failure reproduces.
That works because the client is scripted; a live model that calls differently is INVALID.

## What each one checks

| Question | Inspector or manual preflight (raw bridge) | `arci run` (through the boundary) |
|---|---|---|
| Server starts and initializes | yes (the Inspector is blocked today, above) | yes, every trial |
| Tools listed with schemas | yes | yes, recorded |
| One `tools/call` routes and returns | yes | yes, every call recorded |
| Fault injection (`tool_error_once`, `tool_timeout`, `empty_result`) | no | yes |
| Tool-call budget, deadline | no | yes |
| Repeated seeded trials, oracle on final state, verdict | no | yes |
| diff, minimize, bundle, offline replay | no | yes |

## What the raw-server preflight does not cover

A clean preflight is necessary, not sufficient. It never exercises what only the boundary does:

- **fault injection**: the raw server is never perturbed, so the agent's handling of injected
  errors, timeouts and empty results is untested;
- **budgets**: `max_tool_calls` and the trial deadline exist only in the boundary;
- **the one-connection rule**: the boundary accepts exactly one MCP connection per trial; an agent
  that opens a second one is a harness ERROR there, which a preflight's own session cannot reveal;
- **reserved tool names**: a server advertising a tool named `rpc:...` or `decision:...` is a
  harness fault under ARCI;
- **the 1 MiB line limit**: a JSON-RPC line over 1 MiB, from the agent or the server, is a harness
  fault at the boundary;
- **the -32603 mapping**: a tool that returns non-JSON makes the bridge answer JSON-RPC error
  -32603, which the boundary treats as a broken environment (harness ERROR), not as the agent's
  failure; a raw client just sees an error reply.

Neither tool makes the agent safe: ARCI observes calls that cross its boundary, it is not a
sandbox, and an agent can bypass MCP entirely ([docs/REAL_AGENTS.md](../REAL_AGENTS.md)).
