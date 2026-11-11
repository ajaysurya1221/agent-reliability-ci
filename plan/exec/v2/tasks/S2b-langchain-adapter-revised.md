# TASK S2b: LangChain adapter spike, revised design (phase 0, no product code)

You are the implementer. The orchestrator re-runs everything you report; your report is not
acceptance evidence. Read `AGENTS.md` first and obey its hard rules.

## Why this task exists

S2 proved the mechanics (read `plan/exec/v2/spikes/s2/FINDINGS.md` and `adapter_spike.py`).
Its review (`plan/exec/v2/reviews/S2-review.md`) rejected the adapter design on five points.
The original brief was wrong on one of them: it assumed a tool failure reaches a LangChain
agent as an error `ToolMessage`. In LangChain 1.4.9 it does not by default. A tool exception
leaves `invoke` unless the user added `ToolRetryMiddleware` or `ToolErrorMiddleware`
(`langgraph/prebuilt/tool_node.py` `_default_handle_tool_errors`; `langchain/agents/factory.py`
where `create_agent` builds the `ToolNode`). S2b proves the revised design end to end.

## Owned files

Only `plan/exec/v2/spikes/s2b/`. Create nothing and edit nothing anywhere else. You may read
and copy from `plan/exec/v2/spikes/s2/`. No changes under `src/`, `tests/`, `docs/` or
`examples/`. No git commands that change state. No network. If the goal seems to need a
change under `src/`, stop and say exactly which line and why.

Other jobs write under `plan/exec/v2/` at the same time. Your scope check must only assert
that nothing outside `plan/exec/v2/` changed and that the frozen hashes still pass.

## Environment

Same as S2: `/Users/ajay/Developer/.arci-worktrees/v2-spike-venv/bin/python`, with
`PYTHONPATH=src:<spike dir>`, `PYTHONDONTWRITEBYTECODE=1`, `LANGSMITH_TRACING=false`.
The installed LangChain source is the authority. Do not install anything.

## The revised design to prove

1. **Derived toolset.** The user supplies `make_tools(task, seed) -> list[BaseTool]` (their
   real LangChain tools, fresh per trial). The adapter builds the ARCI toolset from those
   objects, so `ToolBox` invokes the user's own tool and LangChain's argument validation still
   applies. The user does not write tool bodies twice and writes no schema stubs.
2. **Faults are exceptions, raised from the tool-execution position.** The ARCI middleware is
   the innermost `wrap_tool_call` (last in the middleware list). An injected `ToolFault`, and
   a real tool exception, leave it as an exception. The user's own `ToolRetryMiddleware`,
   `ToolErrorMiddleware`, or the absence of both, decides what happens next. Each retry is a
   second recorded, budgeted `ToolBox.call`. The adapter builds no error `ToolMessage`.
3. **Several tool calls in one message run in a deterministic serial order**, keyed on the
   call's index in the `AIMessage`, with waiters released in a `finally` block so a
   `BudgetExceeded` cannot deadlock. If you find this cannot be made deterministic, say why
   with evidence, and route the case to a harness ERROR outcome, never an agent FAIL.
4. **Anything the adapter does not support is ERROR, never FAIL.** Async invocation, tool
   artifacts, `return_direct`, `Command` returns. Find the cleanest way to make the trial end
   as outcome ERROR with a fixed, readable detail using only unfrozen code paths that exist
   today. If none exists, report exactly what small unfrozen change in `toolbox.py` or
   `worker.py` would be needed; do not make it.
5. **Native message shapes.** `ToolMessage` content is built by LangChain's own rule (a string
   unchanged, other values via `json.dumps`), while ARCI records canonical JSON. The final
   answer is captured with `message.text`, so list-block content works.
6. **The adapter owns the glue.** A helper builds the three module-level names the frozen
   schema needs (`toolset`, `baseline`, `candidate`) from: the user's `make_tools`, the user's
   `build_agent(tools, middleware)` for each arm, and nothing else. The user's check function
   lives in a module that does not import LangChain.
7. **Replay checks the answer.** Decide and demonstrate how the captured final answer is
   verified in replay, or demonstrate with a negative test that it is not and say so plainly.

## Deliverables (all inside the owned directory)

1. `arci_langchain.py`: the prototype adapter (middleware, derived toolset, glue helper).
2. `user_app.py`: what a user would write, and only that: `make_tools`, `build_baseline`,
   `build_candidate` (each one `create_agent(...)` call with the ARCI middleware passed in),
   and the three glue names. Keep it as short as it honestly can be.
3. `user_check.py`: the check function, importing no LangChain.
4. `arci.yaml`, `run_spike.py` (prints `OK`/`FAIL` per check, exits non-zero on any FAIL, keeps
   every attempt under `out/`), and `FINDINGS.md`.

## Checks `run_spike.py` must make

1. **Parity with native LangChain, three configurations.** For the same scripted model and
   a tool that raises once: (a) no error middleware, (b) `ToolRetryMiddleware`,
   (c) `ToolErrorMiddleware`. Run each natively (no ARCI) and under the adapter with the
   matching injected fault. The final answer or the raised exception type, and the number of
   tool body executions, must match in every configuration. Under the adapter the trial
   outcomes must be: (a) FAIL with termination `crash`, (b) PASS with two recorded calls,
   (c) whatever native does, shown side by side.
2. **Exactly once**, counted in the user's own tool body, including under retry.
3. **Argument validation is live**: a wrong-typed argument is rejected as it is natively.
4. **Each of the three built-in faults fires**, read from recorded events.
5. **Budget**: a tiny budget ends FAIL with termination `budget`.
6. **Multi-call message**: two calls in one message execute in index order on every one of
   20 repetitions, with identical recorded event sequences; the trial replays REPRODUCED.
7. **Unsupported shapes end as ERROR**, or the report states exactly what blocks that.
8. **Message shapes**: for a tool returning a multi-line string and one returning a dict, the
   text the model receives under the adapter equals the native text, byte for byte. A final
   message with list-block content is captured, not crashed.
9. **Replay**: a failing trial replays REPRODUCED; a trial whose final answer is altered does
   not report REPRODUCED (or the limit is demonstrated and stated).
10. **Cost**: median `wall_seconds` from at least 12 real graded trial envelopes, with the
    check function in the LangChain-free module, beside the S2 figure.
11. **User burden**: print the line counts of `user_app.py` and `user_check.py`, and list
    every name the user had to write.
12. **Scope and frozen hashes**, as limited above. **Repeatability**: two runs, identical
    verdicts and sealed trial hashes.

## Pass conditions

1. `run_spike.py` exits 0 with every check `OK`, twice in a row.
2. `.venv/bin/ruff format --check` and `.venv/bin/ruff check` clean on the owned directory.
3. `shasum -a 256 -c FROZEN.sha256` passes.

A failed check is a valid result. Report it plainly with the evidence; do not weaken a check
to make it pass.

## Final message

Files created, exact commands with their last lines, one or two lines per check, the exact
list of what a user must write, anything you could not do, and risks. No long logs.
