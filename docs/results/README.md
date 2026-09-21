# Results: a prompt regression in a local LLM agent

Exploratory evidence from one machine (Apple M5 Pro, 24 GB), one small local model
(`qwen3.5:4b-mlx` through Ollama, temperature 0.7, loopback only, zero API cost), one task. Read it
as a worked example of the method, not as a benchmark.

**The experiment.** `examples/ollama_mcp_agent`: a real tool-calling agent behind the MCP boundary,
on the inventory task from `examples/retry_agent`, with `tool_timeout` injected on the first
`reserve` call. The two arms differ by ONE sentence of the system prompt: A says "Retry a failed
tool call up to three times before giving up"; B says "Never call a tool twice; if a tool fails,
carry on with the next step."

## The four runs, including the two that were invalid

| Run | N per arm | A | B | Verdict | What happened |
|---|---:|---:|---:|---|---|
| 1 | 30 | 17/30 | 15/30 | INCONCLUSIVE, and meaningless | All 28 failures shared ONE fingerprint that was not the injected fault. The recorded trace showed the model calling every tool with `{}`: the toolset bridge advertised tools with no parameters. A harness bug, found by the failure clusters and the trace in minutes. Fixed. |
| 2 | 30 | 29/30 | 23/30 | INCONCLUSIVE | A 20-point gap, visible by eye, with 6 of B's 7 failures on the `reserve:timeout` fingerprint, and still not decidable: bounds on the difference [-0.45, +0.11]. This is the README's warning about small N, on a real agent. |
| 3 | 400 | 172/182* | 143/183* | ERROR (invalid) | The local model server died at pair 182 of 400, so 435 trials "crashed" on connection refused; separately, one trial hit a shutdown race in the harness and was an ERROR, which is what invalidated the run. Both led to fixes: agents can now report an infrastructure failure (exit 75 => ERROR, never FAIL), and the race is gone. *Counts among trials where the agent actually ran. |
| 4 | 400 | 376/400 (94.0%) | 308/400 (77.0%) | **INCONCLUSIVE** | Clean: no ERROR trials, model server up throughout, nothing else on the machine. 68 of B's 92 failures are on the `reserve:timeout` fingerprint; B calls `reserve` 0.56 times per trial against A's 0.82, so it really does not retry. Bounds on the difference: [-0.2445, -0.0921]. BLOCK needs the upper bound below -0.10. It missed by 0.008. |

Run 4 lists runs 1 to 3 in its sealed manifest's `prior_runs`, as the discipline in
`docs/STATISTICS.md` requires. Reports: `ollama-run1-n30-bridge-bug.md`, `ollama-run2-n30.md`,
`ollama-run3-n400-invalid.md`, `ollama-run4-n400.md`.

## What this shows

- A one-sentence prompt edit that passes a manual try can cost about twenty points of reliability
  under a single transient tool fault.
- N=30 could not confirm it, and under the pre-registered rule neither could N=400: a 17-point
  observed drop is INCONCLUSIVE by a hair. We report that, and we do not re-run until it blocks.
  For scale only (NOT the gate, not pre-registered): an ordinary Wald 95% interval for the same data
  is [-0.217, -0.123], which lies entirely below -0.10. The gap between those two
  answers is the cost of the v0.1 gate's conservatism (per-arm Clopper-Pearson plus Bonferroni), and
  it is why a tighter exact test for the margin is now first on the roadmap: with real agents,
  every trial costs model time.
- Twice the experiment was wrong rather than the agent (a bridge bug, a dead model server). Both
  times the clusters and traces said so quickly, and both times the tool now says so by itself.
