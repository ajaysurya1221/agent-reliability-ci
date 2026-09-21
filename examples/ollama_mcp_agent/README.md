# Local Ollama MCP agent experiment

This example puts a real local language-model agent behind ARCI's MCP boundary. It compares a
retry-aware prompt (`a`) with a one-shot regression (`b`) while ARCI injects the first `reserve`
timeout. The inventory environment is the same deterministic Python `ToolSet` used by
`examples/retry_agent`; `arci.mcp_toolset_server` exposes it as a stdio MCP server.

## Run

Install and start Ollama separately, then make sure the model is present:

```console
ollama pull qwen3.5:4b-mlx
```

From the repository root:

```console
.venv/bin/python -m examples.ollama_mcp_agent.experiment \
  --n 30 --workers 3 --out .arci-runs
```

The command checks the literal loopback Ollama service and model before starting, stores the run
under `.arci-runs/ollama-retry-b-30`, prints the Markdown gate report, and exits with the verdict's
code.

## Scope and cost

The results are exploratory: they cover one machine, one small local model, and N=30 trials per
arm. They are not a general benchmark of Ollama or Qwen. The example makes no network calls beyond
literal loopback (`127.0.0.1`) and uses no paid API, so running it costs nothing beyond local
compute and electricity.
