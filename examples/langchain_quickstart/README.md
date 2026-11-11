# LangChain order desk: first offline verdict

Expected result: **BLOCK (exit 1), after one complete round**. This is an intentionally
broken candidate, not a failing installation. The baseline retries transient tool exceptions;
the candidate has no middleware retry. The same scripted model in both arms abandons an unrecovered tool error. Both handle an empty lookup result by reading again.

## Five steps from an empty environment

Use Python 3.11 or newer. Version 2.0.0 is the first release with this extra and scaffold.

1. Create and activate an environment:
   ```sh
   python -m venv .venv
   . .venv/bin/activate
   ```
2. Install the LangChain extra:
   ```sh
   pip install 'agent-reliability-ci[langchain]>=2.0.0'
   ```
3. Create an empty project directory beside the virtual environment and scaffold:
   ```sh
   mkdir order-desk
   cd order-desk
   arci init --langchain
   ```
   It prints `LANGSMITH_TRACING=false LANGSMITH_TRACING_V2=false arci run arci.yaml`.
   The directory must be empty, including no existing `tools/` or `agent/` packages.
   Existing entries are never overwritten; `--force` is not supported. To use this repository
   example instead, copy its eight runtime files into the directory and skip this step.
4. Run once, offline:
   ```sh
   LANGSMITH_TRACING=false LANGSMITH_TRACING_V2=false arci run arci.yaml --workers 4
   ```
   Leave both model variables and `ARCI_QUICKSTART_TEMPERATURE` unset. Expect exit 1.
   Allow **1–2 minutes for the first offline run** (about 50 seconds measured with four workers), for either the
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
seed changes affect the order price, SKU and stock, but the shared script reads those facts from tools;
only the candidate fails under `tool_timeout` and `tool_error_once`. The test also computes
P(BLOCK)=1 using those degenerate cell laws. This establishes a planted fixture's behaviour,
not a real model's reliability or provider independence. With fixed seeds and a deterministic
model every round is identical: this BLOCK is by construction, not a measurement. Infrastructure errors can invalidate
this expectation. Never enlarge the registered cap or retry an unchanged candidate to seek PASS.

## The files you edit

| File | Purpose |
|---|---|
| `tools.py` | Four tools over a fresh seeded order store; `ToolEnv.snapshot` returns its state. |
| `tasks.jsonl` | 24 requests, order ids and independent grading actions; clean tasks need two or three calls. |
| `agent.py` | Baseline/candidate settings and the three entrypoints from `make_adapter`. |
| `offline_model.py` | Scripted public fake chat model for an installation without a provider. |
| `configuration.py` | Resolves public model settings and rejects disagreement with sealed task metadata. |
| `register.py` | Writes those settings into the tasks and selects fixed/offline or per-round/live seeds. |
| `check.py` | Checks the refund and requested notes from `final_state['state']`, never the agent's answer. |
| `arci.yaml` | Registers tasks, agent import references, conditions, budgets and the suite rule before execution. |

There are eight runtime files. Replace the order desk, task facts and checker together to
build your own experiment. **The offline model only solves the shipped task wording and must
be replaced with the tasks**; unsupported wording is a setup ERROR, not a tied FAIL.
Run `python register.py` after changing tasks or inference settings and before a new experiment.
The scaffold uses editable example names, never credentials.

## Switch to real models

For an already-running local Ollama service with two installed tool-capable models, install
its LangChain integration and set both arm variables. Example identifiers (availability is
local to your machine):

```sh
pip install langchain-ollama
export ARCI_QUICKSTART_BASELINE='ollama:qwen3.5:4b-mlx-ctx32k'
export ARCI_QUICKSTART_CANDIDATE='ollama:qwen3.5:4b-mlx-ctx32k'
# Optional shared override; default for real models is 0.7.
export ARCI_QUICKSTART_TEMPERATURE=0.7
python register.py
LANGSMITH_TRACING=false LANGSMITH_TRACING_V2=false arci run arci.yaml --workers 1
```

Using the same model isolates the retry change. Each variable accepts `provider:model`, as
`init_chat_model` does; other providers need their integration and credentials. Exactly one
model variable set is a setup ERROR. Both arms use the same positive temperature (default 0.7,
overridable by `ARCI_QUICKSTART_TEMPERATURE`) and disable Ollama reasoning; other providers
retain their default reasoning policy, recorded as `provider_default`.

Real models use positive temperature so repeated rounds can sample different model behavior.
Registration also selects `scenario_seeds: per_round` so scenario data varies between rounds;
this does not establish independence or the per-round null premise of the statistical guarantee.
The offline path stays deterministic at temperature 0 with fixed scenario seeds.
Provider retries belong in the **model client's settings**, not tool middleware.

`python register.py` copies the resolved model id of each arm, temperature and each reasoning
policy into `quickstart_settings` on every task. These values enter the sealed manifest and
experiment id through task content; they are checked against the environment before tools or
models run, including when running an old sealed manifest. A mismatch is a setup ERROR: restore
the registered environment or register a new experiment. Registration rewrites `tasks.jsonl`
and the descriptor's seed mode; choose your budgets before running.

Changing these registered settings, task content, conditions, budgets, rule, agent references
or prior-run list changes the experiment id. Changing environment variables alone does not
change it and is refused if settings differ. Editing Python source, changing provider defaults,
model aliases/weights behind an id, credentials or tracing flags does not change the id: code
and provider artifacts are not automatically hashed. Pin model versions and keep source under
version control; this is an integrity seal, not proof of provider behavior.

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
  there are classified as infrastructure too. Pre-provider setup failures on any model turn are ERROR. See the recipe's complete failure table.
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

## Inspect the outcome

Both `run` and `gate` print per-arm success counts. When baseline succeeds in fewer than half
of its trials they warn that a non-inferiority PASS says little about absolute reliability.
On ERROR they show the first harness-error detail and the number of trials sharing it.
Suite `report`, `triage`, `diff` and `plan` are available. `minimize`, `bundle`, `replay` and
`trace-check` are not built for suites. To list failing/errored trials, replace `RUN_DIR`:

```sh
python -c 'import json,sys; [print(t["trial_id"],t["arm"],t["outcome"],t.get("failure_detail")) for line in open(sys.argv[1]+"/trials.jsonl") if (t:=json.loads(line))["outcome"] != "PASS"]' RUN_DIR
```

An added fault on a tool some tasks never call is diluted into ties; fault accounting in the
report shows how often it fired. A real tool raising `ValueError` on a wrong argument crashes
the trial (FAIL) unless the agent handles it; this retry middleware handles only timeout and
runtime errors. A plain refund does not require empty notes; exact notes are graded only when
requested. An unknown grading action is a grader ERROR.
