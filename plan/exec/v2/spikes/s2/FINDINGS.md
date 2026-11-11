# S2: LangChain adapter spike

## Result and acceptance limit

The nine technical questions are demonstrated using the installed LangChain 1.4.9,
LangGraph 1.2.20 and langchain-core 1.7.7, with scripted fake chat models, no network,
and the unchanged ARCI Python worker, runner, ToolBox, grader and CLI.

**Full pass conditions are not met.** The outside-owned-file hash check fails because
four paths changed concurrently after the initial read-only inventory:

- `plan/exec/v2/adr-0012-draft.md`
- `plan/exec/v2/spikes/s1/suite_stats.py`
- `plan/exec/v2/spikes/s1/suite_stats_sim.py`
- `plan/exec/v2/spikes/s1/test_suite_stats.py`

This task wrote only inside `plan/exec/v2/spikes/s2/`; it did not restore, edit or remove
those external changes. `scope_before.json`, `status_before.txt`, and each run's
`scope-differences.json` and `status.txt` preserve the evidence. The repository also
already contained untracked `dist-v0.8.0/`, `plan/exec/v2/` and research files before
the task. Consequently, literal whole-repository status cleanliness cannot be claimed.
The scope check is retained as a failure, and `run_spike.py` exits 1 for it.

Run 0001 preserves the initial missing synchronous `before_agent` counterpart failure.
Run 0002 preserves the incorrect diff-offset expectation and insufficiently descriptive
invalid-result diagnostics. Runs 0003 and 0004 use the final source version. Source
hashes are stored per run; all attempts are retained, with no experiment padding or
statistical pooling. The repeatability check compares the previous invocation only
when the adapter, verifier and descriptor hashes match.

Runs 0003 and 0004 both exit **1**, with every technical check OK and only scope FAIL.
Run 0004 confirms identical check verdicts and all 12 identical sealed trial hashes.
The fourth outside-owned path appeared by run 0004. The latest measured median is
**0.7476 s** for launch/import/exit and **0.6826 s** for imports (10 fresh children).

## Evidence for the nine questions

| Question | Observation and evidence |
|---|---|
| 1. Exactly once | Middleware never calls `handler`; ToolBox alone invokes `World.lookup`. The schema-only LangChain callable raises if executed. Clean call: one body execution. Each timeout/error trial's first call: zero bodies; a retry executes one body. Empty-result calls execute one body each, including the injected call. Snapshot counts and `usage.tool_calls` are asserted across every experiment trial, plus a clean control. |
| 2. Fault visibility | Timeout/error become `ToolMessage(status="error")`; empty result remains a successful message containing JSON `null`. The script inspects that feedback: baseline retries once, candidate stops. Across three conditions and two pairs each, baseline is 6/6 PASS, candidate 0/6 PASS. A real tool exception has the same message behavior. Budget stays FAIL/budget; an empty replay recording stays ERROR/replay_miss and CLI replay INVALID. |
| 3. Faults fire | Each of `tool_timeout`, `tool_error_once`, `empty_result` appears in four recorded `tool_finish.injected_by` fields. See `fault-accounting.json` and the store's `events.jsonl`. No inference from declared faults alone. |
| 4. Budget | With `max_tool_calls=1`, the injected first attempt consumes the budget. The retry ends FAIL/budget, with one tool call and no second `tool_start`. See `budget.trial.json`. |
| 5. Final state | `after_agent` captures the final text in the factory-created capture object; `World.snapshot()` exposes it to the independent oracle. Successful baseline intentionally returns `success=False`; failing candidate returns `success=True`. Erasing only the captured final answer causes a clean control to FAIL despite the correct environment answer. See `erased-capture.trial.json`. |
| 6. Replay/diff | CLI `bundle` embeds `adapter_spike.py`; CLI `replay` returns REPRODUCED. Same-pair passing baseline/failing candidate diff identifies retry `tool_start` versus candidate `agent_result` after `tool_timeout`. CLI reports `common_prefix: 5`, the left event offset used by the current implementation, not one matched tool exchange. See `bundle.json`, `replay.stdout.txt`, `diff.stdout.txt`. |
| 7. Parallel calls | A native create_agent probe issues two calls in one AIMessage. Both tool bodies rendezvous at a barrier, proving overlap (`peak_active=2`). The adapter rejects a multi-call response in `after_model`, before either ToolBox call: FAIL/crash, zero tool events/body executions. See `native-parallel.json` and `parallel.trial.json`. |
| 8. Unsupported shapes | A tool returning `Command` or a set is rejected by the existing ToolBox result validation: ERROR/harness_error. Since the runner normalizes Pydantic's multiline diagnostic, middleware additionally records `S2: unsupported tool result Command/set; only JSON values supported` in a model-step event and snapshot. Non-finite arguments are rejected before ToolBox. `ainvoke` is rejected in `abefore_agent`, before any model/tool call. Both end FAIL/crash. See `unsupported-*.trial.json`. |
| 9. Start cost | Ten fresh interpreter processes import `arci.worker`, the adapter and LangChain. Run 0003 median import time: **0.6761 s**; median process launch + imports + exit: **0.7406 s**. Every sample is in `startup.json`; this is a warm-filesystem-cache measurement on this machine, not a cold-cache or provider latency estimate. |

The v1 gate returns **INCONCLUSIVE**, exit 2, as expected for `n_per_arm=2`; the
verifier treats that as a successful smoke check, not evidence of a statistical regression.

## Recommended product API

Proposed API, not shipped by this spike: `arci.adapters.langchain.ArciMiddleware`.
The one changed construction line should be:

```python
agent = create_agent(model, tools=tool_schemas, middleware=[ArciMiddleware(tools, capture)])
```

Here `tools` is the **ARCI ToolBox argument** passed to the Python agent function;
`tool_schemas` describes the same named synchronous tools registered by the toolset.
The middleware directly calls ToolBox and constructs ToolMessages. It must never
invoke the downstream handler, which would bypass or duplicate boundary execution.

The user must additionally supply:

1. An importable `(task, tools, rng) -> dict` Python entrypoint that builds and invokes
   the graph synchronously, plus the adapter import. A hosted model also needs its own
   dependencies/credentials; this spike uses none.
2. A fresh `(task, seed) -> toolset` factory with deterministic/resettable tool bodies
   in `.tools`, and a trial-local capture shared with the middleware. Its `.snapshot()`
   includes environment state and the captured final output.
3. An independent `(task, final_state) -> bool` oracle and a v1 descriptor naming the
   two agent references, toolset, oracle, task, faults and budgets.

The one-line change is therefore an **agent interception hook**, not a claim that an
arbitrary existing LangChain application needs only one line of total integration.
Use the same tools and schemas, and validate their names/signatures before a product run.
In this spike, sharing uses a factory-reset module-local `Capture`; each real trial has
its own process. A product must provide explicit session binding, including a replay
binding that does not depend on constructing a live toolset. Never put capture behind
a tool call merely to get it into the snapshot.

## Supported subset and mandatory rejections

| Shape/mode | Policy and coverage |
|---|---|
| Synchronous `invoke`, one call per AIMessage, ordinary named Python functions | Demonstrated. The JSON return is serialized into ToolMessage content; failures use error status. Final output is text. |
| Multiple tool calls in one AIMessage | Reject the entire response before execution. Demonstrated; safe serial reordering was not implemented. ToolBox counters/recording have no locks and replay consumes ordered calls. A mutex around each body would not establish deterministic acquisition order. |
| `ainvoke` / asynchronous tool hooks | Explicit rejection demonstrated before execution. Async functions/toolsets, concurrent graph invocations, `batch` and `abatch` must also be rejected by the product entrypoint; these extra entrypoints are not claimed tested here. |
| `langgraph.types.Command`, sets and non-JSON values | Demonstrated runtime rejection. Arguments use strict recursive JSON validation; finite floats and UTF-8 are required. Product tool registration must reject Command/artifact result annotations and validate raw results before any coercion. |
| Tool artifacts, `return_direct`, injected state/runtime/store, provider-side tools, graph/state mutations, structured responses, checkpoint/resume and partial streaming | First two have a defensive tool-request guard in the spike; no artifact integration test is claimed. The remaining modes must be rejected/documented unsupported by the initial product because this spike does not record their semantics. Middleware composition that skips/rewrites execution must be rejected or separately proven. |

## Commands and verification

From the repository root, the complete check invocation is:

```sh
PYTHONDONTWRITEBYTECODE=1 LANGSMITH_TRACING=false LANGCHAIN_TRACING_V2=false PYTHONPATH=src:plan/exec/v2/spikes/s2 /Users/ajay/Developer/.arci-worktrees/v2-spike-venv/bin/python -B plan/exec/v2/spikes/s2/run_spike.py
```

Every CLI invocation's exact argv and exit code are in `*.command.json`, with stdout
and stderr beside them. Other trial specs/envelopes and version/timing data are also
retained. `out/latest.txt` points to the latest attempt. Temporary replay payloads
are created beneath that run's `tmp/` and removed by the existing replay implementation.
Bytecode writes and LangSmith tracing are disabled.

Quality commands:

```sh
.venv/bin/ruff format --no-cache plan/exec/v2/spikes/s2
.venv/bin/ruff format --no-cache --check plan/exec/v2/spikes/s2
.venv/bin/ruff check --no-cache plan/exec/v2/spikes/s2
.venv/bin/basedpyright --pythonpath /Users/ajay/Developer/.arci-worktrees/v2-spike-venv/bin/python plan/exec/v2/spikes/s2
shasum -a 256 -c FROZEN.sha256
git status --short
```

Type checking uses the repository's strict configuration with the provided interpreter
for LangChain imports. No pyright ignores or new dependencies are used. The dedicated
spike verifier supplies the behavioral checks; the full product suite is not run because
no product code changed. All 54 frozen hashes passed during the technical runs.

## Open risks and recommendation

- **Scope acceptance remains failed:** preserve the concurrent external changes and let
  the orchestrator assess/re-run the candidate in its own isolated checkout. Do not
  reset other lanes or claim the failing global scope check passed.
- **Replay is bounded:** it reproduces scripted model behavior against recorded tool
  results and grades the sealed source snapshot after exact consumption. It does not
  record/replay hosted model responses or prove a live model's determinism.
- **Integration is narrow:** bypassing handler also bypasses LangChain's normal tool
  schema validation, injected arguments and handler middleware. Product registration
  needs explicit validation; the fixed string-key schema here is not a generic converter.
- **Process overhead matters:** both the worker and independent grader import this
  module and therefore LangChain. Moving the user's oracle/world into a lightweight
  module could reduce grader startup; that optimization is not measured here.
- **No adoption or production claim:** these are small offline fixture runs. The
  technical evidence supports continuing a synchronous, single-call-per-message adapter
  design, subject to the unresolved scope acceptance and orchestrator review.
