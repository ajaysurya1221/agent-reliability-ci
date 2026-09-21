# Testing a real agent (v0.2)

A **command agent** is a subprocess configured to use one harness-owned stdio MCP server. `arci`
runs it once per trial and gives it an MCP config file. The boundary records the supported
request/response exchanges; only `tools/call` is budgeted and fault-injected. Everything the agent
does outside MCP is invisible (see the trust model).

```text
your agent (any argv) --stdio--> arci.mcp_shim --unix socket--> arci.mcp_boundary --stdio--> MCP server
                                  byte relay only               recorder, faults, budgets     the environment
```

## The three things you provide

1. **The environment: one stdio MCP server.** Either your own server, or any v0.1 python toolset
   served through the bridge:

   ```python
   McpServerSpec(
       argv=(sys.executable, "-P", "-m", "arci.mcp_toolset_server",
             "--toolset", "my_pkg.env:make_world", "--workdir", "{workdir}", "--seed", "{seed}",
             "--task-file", "{task_file}"),
       snapshot="arci.mcp_toolset_server:snapshot",
   )
   ```

   `snapshot(task, workdir) -> dict` is trusted code that reads the environment's final state after
   the agent has exited. The oracle grades that, never the agent's own claim.

2. **The agent: an argv with placeholders.** `{mcp_config}`, `{task_file}`, `{workdir}`, `{seed}` are
   expanded at launch. Exit status 0 means "I claim success".

   ```python
   CommandSpec(argv=(sys.executable, "-P", "-m", "my_pkg.agent", "--mcp-config", "{mcp_config}",
                     "--task-file", "{task_file}"))
   ```

   Commands run in the temporary trial directory: use an importable module or an absolute script
   path, never a relative one.

3. **A manifest** with `mcp_server`, two `ArmSpec(command=...)` arms, fault conditions that name MCP
   tool names, and the usual contract, alpha, delta and `n_per_arm`.

Then `arci run`, `gate`, `diff`, `minimize`, `bundle` and `replay` work exactly as for python agents.

## Worked example: a prompt regression in a local LLM agent

[examples/ollama_mcp_agent](../examples/ollama_mcp_agent) is a real tool-calling agent on a local
Ollama model (loopback only, no API cost). Its two arms differ by ONE sentence of the system prompt:
"Retry a failed tool call up to three times" versus "Never call a tool twice; if a tool fails, carry
on". Prompt edits are the commonest agent regression, and one manual try will not show this one.

```bash
python -m examples.ollama_mcp_agent.experiment --n 30 --workers 3 --out runs
```

Measured results are in [docs/results](results/). They are exploratory: one machine, one small
model, N=30.

## Other agent CLIs

Any CLI that accepts a standard `{"mcpServers": {...}}` config file can be a command agent. One
untested Claude Code sketch follows. It was NOT run for this release (no paid-agent trials were
made), so check its flags against your CLI's current documentation before relying on it:

```python
# Claude Code, non-interactive, using only the harness's MCP server
CommandSpec(argv=("claude", "-p", "Read {task_file} and complete the task using the MCP tools.",
                  "--mcp-config", "{mcp_config}", "--strict-mcp-config"))
```

An agent that cannot take the path as an argument can read it from the environment instead:
`ARCI_MCP_CONFIG`, `ARCI_TASK_FILE`, `ARCI_WORKDIR` and `ARCI_SEED` are always set for the agent.
Placeholders are expanded in `argv` only, not in `env` values.

Budget real-model experiments deliberately: N per arm times two arms times K conditions model
sessions. The gate needs N in the low hundreds to reach PASS; a large regression can BLOCK at N=30.

## Limits specific to command agents

- One MCP server per trial, stdio only, serial `tools/call`, `resultType: "complete"`. Task results,
  sampling, elicitation and concurrent calls are a harness ERROR, not a silent pass-through.
- **Tool replay is not agent replay.** A live model rarely repeats its calls exactly; replaying its
  bundle is then INVALID, never REPRODUCED. Deterministic replay is a property of scripted clients.
  For a live model, the bundle's value is the recorded trace and the reduced fault condition, which
  you re-run live.
- The agent can bypass MCP (files, network, other servers configured elsewhere). Use your CLI's
  strict-config mode where it has one.
