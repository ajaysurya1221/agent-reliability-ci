# Recipe: an MCP command agent, Inspector preflight, then ARCI

A scripted MCP client (`agent.py`) in two variants: `retry` retries a failed `fetch` up to three
times, `fragile` gives up on the first error. ARCI runs both as command agents against the same
seeded environment, with the first `fetch` of every trial failing at its boundary. The walkthrough,
including what the Inspector and ARCI each check, is
[docs/recipes/mcp-inspector.md](../../../docs/recipes/mcp-inspector.md).

| File | What it is |
|---|---|
| `world.py` | `make_world(task, seed)`: tools `fetch(key)` (30% of seeds fail the first real call transiently) and `store(key, value)`; `snapshot()`; `passed(task, final_state)`: the stored value equals the upstream's |
| `agent.py` | stdlib newline-delimited JSON-RPC stdio client: one session, `initialize` (protocol `2026-07-28`), `notifications/initialized`, `tools/list`, `fetch`, `store`; exit 0 done, 1 gave up, 75 infrastructure |
| `arci.yaml` | written by hand (`arci init` scaffolds Python arms only): two command arms, `mcp_server` = the bridge `arci.mcp_toolset_server --toolset world:make_world`, one condition `tool_error_once` on `fetch` at occurrence 0, 8 trials per arm |
| `mcp.inspector.json` | an Inspector `--config` file that starts the same bridge directly (seed 0, `task.json`, `PYTHONPATH=.`) |
| `task.json` | the task, `{"key": "answer"}` |

Run from a copy of this directory, with an environment active whose `python` and `arci` come from
an install of agent-reliability-ci (`arci.yaml` and `mcp.inspector.json` say `python`; write an
absolute interpreter path if yours differs):

```bash
cp -R examples/recipes/mcp_agent mcp-recipe && cd mcp-recipe
npx @modelcontextprotocol/inspector --cli --config mcp.inspector.json --server env --method tools/list
arci run arci.yaml
arci diff runs/mcp-fetch-retry fetch-error:00000:baseline fetch-error:00000:candidate
```

Expect `VERDICT: BLOCK (exit 1)`: `fragile` fails all 8 trials, `retry` passes all 8, and a total
collapse is the one result 8 trials per arm can decide. The Inspector step was blocked on
2026-10-13 by the Inspector SDK's protocol-version check; the doc has a stdlib manual preflight
that drives the same server over a pipe.

The agent runs as `python -P -m agent` because command agents start in a temporary trial
directory: `agent` and `world` import from this directory only because `arci run` appends the
current directory to every child's import path (ADR 0006). Not a sandbox: ARCI sees only what
crosses its MCP boundary.
