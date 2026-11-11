# LangChain order desk: first offline verdict

Expected result: **BLOCK (exit 1), after one complete round**. This is an intentionally
broken candidate, not a failing installation. The baseline retries transient tool exceptions;
the candidate abandons the task. Both handle an empty lookup result by reading again.

## Five steps from an empty environment

Run these in an empty working directory with Python 3.11 or newer. These commands target a
build containing this quickstart; an older published version may not have `init --langchain`.

1. Create and activate an environment:
   ```sh
   python -m venv .venv
   . .venv/bin/activate
   ```
2. Install the LangChain extra:
   ```sh
   pip install 'agent-reliability-ci[langchain]'
   ```
3. Scaffold the runnable files:
   ```sh
   arci init --langchain
   ```
   It prints exactly `arci run arci.yaml`. Existing files are never overwritten; use a
   fresh directory if any scaffold filename already exists. To use this repository example
   instead, copy its six runtime files into the directory and skip this step.
4. Run once, offline:
   ```sh
   LANGSMITH_TRACING=false LANGSMITH_TRACING_V2=false arci run arci.yaml --workers 4
   ```
   Leave `ARCI_QUICKSTART_BASELINE` and `ARCI_QUICKSTART_CANDIDATE` unset. Expect exit 1.
   Allow about **50 seconds for the first offline run** with four workers, for either the
   copied example or generated scaffold. Installation time is additional; runtime varies
   with your machine. The test keeps the full 24-task, four-condition design.
5. Recompute the saved gate (the glob selects the one newly created run):
   ```sh
   arci gate runs/langchain-order-desk@*
   ```
   Expect the same **BLOCK**, exit 1. With multiple runs, use the exact store path printed
   by `arci run` instead of the glob.

The suite has 24 tasks × four conditions = 96 pairs per round. The default exact suite rule
uses alpha 1/20, margin 1/10, stakes 1/4 and 1/2, fixed scenario seeds, a five-round cap and
five tolerated errored pairs. It inspects only complete rounds. The offline example stops at
round one: baseline 96/96, candidate 48/96. Its result is seed-deterministic by construction:
seed changes affect the order price, SKU and stock, but both scripts read those facts from tools;
only the candidate fails under `tool_timeout` and `tool_error_once`. The test also computes
P(BLOCK)=1 using those degenerate cell laws. This establishes a planted fixture's behaviour,
not a real model's reliability or provider independence. Infrastructure errors can invalidate
this expectation. Never enlarge the registered cap or retry an unchanged candidate to seek PASS.

## The files you edit

| File | Purpose |
|---|---|
| `tools.py` | Four tools over a fresh seeded order store; `ToolEnv.snapshot` returns its state. |
| `tasks.jsonl` | 24 requests, order ids and independent grading actions; clean tasks need two or three calls. |
| `agent.py` | Baseline/candidate settings and the three entrypoints from `make_adapter`. |
| `offline_model.py` | Scripted public fake chat model for an installation without a provider. |
| `check.py` | Checks the refund and exact notes from `final_state['state']`, never the agent's answer. |
| `arci.yaml` | Registers the tasks, agents, conditions, budgets and suite rule before execution. |

There are six runtime files: the separate offline model is needed in addition to the five
application/configuration files. Replace the order desk, task facts and checker together to
build your own experiment. The scaffold uses editable example names, never credentials.

## Switch to real models

For an already-running local Ollama service with two installed tool-capable models, install
its LangChain integration and set both arm variables. Example identifiers (availability is
local to your machine):

```sh
pip install langchain-ollama
export ARCI_QUICKSTART_BASELINE='ollama:qwen3.5:4b-mlx-ctx32k'
export ARCI_QUICKSTART_CANDIDATE='ollama:qwen3.5:4b-mlx-ctx32k'
LANGSMITH_TRACING=false LANGSMITH_TRACING_V2=false arci run arci.yaml --workers 1
```

Using the same model isolates the retry change. Each variable accepts `provider:model`, as
`init_chat_model` does; other providers need their own integration and credentials. Set both
variables for a real-model comparison; an unset arm remains scripted. Both arms use temperature
0 and disable Ollama reasoning in code. Other providers retain their own default reasoning
mode; use the same provider and explicitly match any provider-specific reasoning settings in
`settings` when changing providers. Provider retries belong in the **model client's settings**,
not tool middleware. Temperature 0 is not a guarantee of deterministic live inference.

The offline verdict is not promised for real models. Plan budgets before running: a normal
trial needs three or four model turns and two or three tool attempts; an empty lookup adds one
of each, a middleware retry adds a tool attempt without another model call. Registered limits
are six model turns, six tool attempts and 15 seconds per trial. A local model may need larger
time limits; set those before registering a new run. A complete first round is 192 trials;
the cap is 960 trials. Offline provider cost is zero. Real cost depends on model tokens, prices
or local hardware time; neither usage nor money is automatically estimated here.

## Adapter limits

- This is a synchronous `create_agent` adapter. It accepts settings for model, system prompt,
  middleware, response format and name. Async-only tools/middleware, interrupts, checkpointers,
  stores, custom state/context and other `create_agent` settings are rejected.
- Tools need stable names and schemas across seeds and JSON arguments/results. Tool artifacts,
  `return_direct`, `handle_tool_error`, `handle_validation_error`, injected runtime/config/callback
  arguments, `Command` results, tuples, integer-keyed result dictionaries and non-JSON results
  are rejected. Names `tool` and `self` are reserved argument names. Duplicate tool names and
  missing/empty/duplicate tool-call ids are rejected. Non-finite arguments are agent failures.
- Tool validation runs twice on the same raw arguments: validators must have no side effects.
  The adapter accepts `functools.partial` tool functions even though native `create_agent` in
  the supported version rejects them. `BaseTool.run` supplies run managers; the parent callback
  connection may differ from a native run.
- Calls from one model response execute serially in their declared order, including retry
  backoff. The trial time budget bounds the run. A waiting call is a deadlock only after
  30 seconds with no call running.
- Middleware is trusted. Replacing a tool or answering without invoking its handler bypasses
  recording for that call. Middleware-owned tools and callable structured-output error handlers
  are rejected. The boundary is not a sandbox for arbitrary code or direct network calls.
- Setup/configuration failures and provider infrastructure failures are ERROR, not agent FAIL.
  The inner model handler includes binding and output processing: infrastructure-shaped errors
  there are classified as infrastructure too. See the recipe's complete failure table.
- Live tool failures re-raise the original exception. `fault_exceptions` maps **fault kind**
  (`timeout`, `error`) to an exception class, not perturbation names (`tool_timeout`,
  `tool_error_once`). For v1 replay, exceptions are reconstructed from their class and scrubbed
  diagnostic; attributes and original exact messages are not preserved. User `error_types`
  override builtin class names; the reconstructed diagnostic must match exactly. Unrecoverable
  text, including scrubbed non-literal `KeyError` keys, makes replay a harness ERROR.
- Custom perturbations must retain real error kind/detail and use exactly `injected error` for
  synthetic `error` failures. Replay treats other `error` diagnostics as real, regardless of
  the fault tag; changing them or inventing class-like text can cause divergence.
- Replay rebuilds tool schemas at seed zero without executing tool bodies. Recorded tools do
  not record model inference. A different policy path can reproduce if the compared sequence,
  outcome and failure fingerprint agree. **Suite bundle/replay commands are not built yet**;
  adapter replay support currently applies to v1 trial bundles, not this suite command path.

LangChain installs `langsmith` transitively. ARCI does not enable tracing, but existing
LangSmith environment settings can send traces. Set both `LANGSMITH_TRACING=false` and
`LANGSMITH_TRACING_V2=false` for offline work; V2 overrides inherited legacy settings.
Run stores may contain sensitive task data even when tracing is disabled (ADR 0012).

Read the [full recipe](../../docs/recipes/langchain.md) for the adapter walkthrough and failure table.
