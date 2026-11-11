# TASK P3a: the LangChain adapter (core)

Lane B. Worktree: `/Users/ajay/Developer/.arci-worktrees/wt-v2-adapter` (branch
`v2/adapter`, cut from `main` at v1.0.0). Work only there. Its `.venv` already holds
`langchain==1.4.9`, `langchain-core==1.7.7`, `langgraph==1.2.20`,
`langgraph-prebuilt==1.1.1`, installed by the orchestrator under the accepted ADR 0012.
`pyproject.toml` and `uv.lock` stay frozen and unchanged in this task.

## Read first

1. `AGENTS.md` in the worktree. One sentence of rule 4 is amended for this task by the
   accepted ADR 0012: a module under `src/arci/adapters/` may import the one optional extra
   it is named for, and that extra's own packages, lazily. Everything else stands.
2. Under `/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/`:
   `adr-0012-draft.md` (accepted), `adr-0011-draft.md` item 10 (the infrastructure-error
   rule), `reviews/S2b-review.md` (the nine binding requirements),
   `reviews/S2b-review-workflow.json` (the findings behind them), and your own phase 0
   prototype in `spikes/s2b/` with its `FINDINGS.md`.
3. `src/arci/interfaces.py`, `src/arci/toolbox.py`, `src/arci/worker.py`,
   `src/arci/replay.py`, `docs/AGENT_SEMANTICS.md` (trial outcomes and latches).

## You own

- `src/arci/adapters/__init__.py`, `src/arci/adapters/langchain.py` (new)
- `src/arci/toolbox.py`: add the one public method described below and nothing else
- `tests/unit/adapters/` (new) and `tests/unit/toolbox/test_fail_harness.py` (new)
- `pyrightconfig.adapters.json` (new, repository root)

## The shape to build

The prototype's two-middleware splice does not ship. Build this instead. It was revised
after your read-only review of the first draft
(`consults/P3a-brief-review-codex.md`); each of that review's findings is answered here.

**User-facing API** (`arci.adapters.langchain`):

```python
@dataclass(frozen=True)
class ToolEnv:
    tools: Sequence[BaseTool]
    snapshot: Callable[[], dict[str, JsonValue]] | None = None   # the user's environment state

MakeTools  = Callable[[dict[str, JsonValue], int], Sequence[BaseTool] | ToolEnv]   # (task, seed)
AgentSpec  = Callable[[], Mapping[str, Any]]      # keyword arguments for create_agent

class Adapter(NamedTuple):
    toolset: ToolSetFactory
    baseline: AgentFn
    candidate: AgentFn

def make_adapter(
    make_tools: MakeTools,
    baseline: AgentSpec,
    candidate: AgentSpec,
    *,
    task_to_input: Callable[[dict[str, JsonValue]], Any] | None = None,
    fault_exceptions: Mapping[str, type[Exception]] | None = None,
    error_types: Sequence[type[Exception]] = (),
) -> Adapter
```

A user's whole adapter file is then:

```python
def make_tools(task, seed): ...                      # their real tools
def baseline_agent():
    return {"model": MODEL_A, "system_prompt": PROMPT, "middleware": [ToolRetryMiddleware(...)]}
def candidate_agent():
    return {"model": MODEL_B, "system_prompt": PROMPT}
toolset, baseline, candidate = make_adapter(make_tools, baseline_agent, candidate_agent)
```

- **ARCI builds the graph (requirement 1).** The user returns keyword arguments; the
  adapter calls `langchain.agents.create_agent` itself with
  `tools=<proxies>` and `middleware=[<ARCI outer>, *<user middleware>, <ARCI inner>]`.
  There is no user-built graph, so there is nothing to misplace and nothing to detect.
  Allowed keys: `model`, `system_prompt`, `middleware`, `response_format`, `name`. `model`
  is required. Any other key, `tools` included, is rejected with a fixed message that names
  the key. A user middleware that carries its own tools (a non-empty `tools` attribute) is
  rejected the same way: those tool bodies would not cross the boundary.
- **Trust statement, to be repeated in the recipe.** User middleware is trusted code. One
  that replaces the tool on a request, or answers a tool call without calling its handler,
  bypasses the boundary for that call; ARCI records nothing for it and does not claim to
  detect it.
- **Proxy tools and the raw-argument boundary.** Each proxy carries the user tool's name,
  description and argument schema, so LangChain's own tool node validates arguments and
  produces native feedback for invalid ones (no body runs, nothing is recorded: that is
  agent behaviour). Tools that set `handle_validation_error` or `handle_tool_error` are
  rejected in v2.0: a handled error natively carries `status="error"`, and that status
  would be lost through the boundary. For a valid call the proxy passes the **raw
  arguments exactly as the model sent them** (taken from the tool call, not the parsed
  values) to `ToolBox.call`, and the callable registered with `ToolBox` runs the real tool
  on those raw arguments through a public path that cannot mistake an argument dictionary
  for a tool-call envelope. `real_tool.invoke(raw)` is not such a path: an argument
  `{"type": "tool_call"}` makes it raise `KeyError`. `BaseTool.run(raw)` takes its input as
  arguments directly; confirm that in the installed source, and if no public path is
  unambiguous, reject the ambiguous argument shape with a fixed message instead. Either
  way, test an argument dictionary that looks like an envelope. So ARCI always records JSON, a transforming validator
  transforms once as it does natively, and the user tool body runs exactly once per
  attempt (never in replay). Validation itself runs twice on the same raw input; a
  validator with side effects is a stated limit. No private LangChain import anywhere
  (requirement 5, ADR 0012 item 3). If a public name the adapter needs is missing,
  importing the adapter fails with one line naming it.
- **Serial order (requirement 2).** The outer ARCI middleware orders the *pending* tool
  calls of the latest AI message (not calls already answered, not structured-output calls)
  so that they reach `ToolBox` in message order, each including all its retries, whatever
  thread pool LangChain uses. The gate has an abort flag, a wait timeout that becomes a
  harness ERROR, and re-entry detection. After a fatal exception in one call, no later
  call of that message reaches `ToolBox`, and every aborted sibling reports the same
  terminal cause, so thread scheduling cannot change the failure fingerprint.
- **What user middleware sees (requirements 3, 4, 6).**
  - Budget exhaustion and every adapter rejection travel as a `BaseException` carrier, so
    ordinary handlers (`except Exception`, retry middleware) do not catch or retry them.
    User code can still catch `BaseException`; the sticky latches and the abort flag make
    the outcome the same if it does. The adapter converts the carrier back outside graph
    execution, so the worker sees `BudgetExceeded` or the harness latch as usual.
  - Live, a real tool failure reaches user middleware as the original exception object:
    capture it per attempt where the tool body runs, clear the capture before every
    attempt, and re-raise that object when `ToolBox.call` reports the failure.
  - An injected fault raises `ToolFault` by default; `fault_exceptions` maps a fault kind
    (`ToolFault.kind`) to an exception class to raise instead.
  - **Replay is a restricted reconstruction, not parity.** The recording holds only a
    scrubbed one-line text beginning with the class name. In replay a recorded real
    failure is rebuilt as that class, looked up by name among builtins and `error_types`
    (the name must be unique there), constructed from the recorded text alone. An unknown
    or ambiguous name, or a class that cannot be constructed from one string, is a harness
    ERROR. Attributes and exact messages are not restored, so a user policy that depends
    on them may act differently in replay. What replay then reports follows ARCI's
    existing rule and nothing stronger: a different tool-call sequence is INVALID; a
    different outcome or fingerprint is NOT_REPRODUCED; and if the sequence, outcome and
    fingerprint are unchanged, replay says REPRODUCED even though the policy took another
    path (your probe with a lost `errno` showed this). State it as a limit and keep one
    test that demonstrates it; do not claim a guarantee.
- **`ToolBox.fail_harness(detail: str) -> NoReturn`** (the one change to `toolbox.py`):
  sets the harness latch through the existing private marker and raises a new
  `BaseException` subclass defined in `toolbox.py`. Works in live and replay mode. The
  adapter requires a boundary that has it and fails with a fixed message otherwise. This is
  requirement 6's `reject_unsupported`; one method serves rejections and the rule below.
- **Infrastructure errors (ADR 0011 item 10).** The **inner** ARCI middleware is the last
  in the list, so its `wrap_model_call` sits directly round the provider invocation, inside
  every user middleware and after the provider client's own retries. It calls
  `note_model_step` once per invocation attempt, before invoking. When the invocation
  raises, the exception object itself (do not follow `__cause__` or `__context__`) is an
  infrastructure error if: its `status_code`, or its `response.status_code`, is an `int`
  equal to 429 or in 500 to 599; or it is a builtin `ConnectionError` or `TimeoutError`; or
  it is an `httpx.TransportError`; or a class in its MRO is named `APIConnectionError` or
  `APITimeoutError`. The handler of the innermost middleware also covers tool binding and
  output processing, not only the provider call. To keep user code out of that region,
  a `response_format` strategy whose `handle_errors` is a callable is rejected in v2.0
  (the booleans, strings and exception types it also accepts are fine). What remains is a
  stated limit: an exception of one of the shapes above raised by LangChain's own binding
  or output processing would be classified as infrastructure. Then the adapter calls `fail_harness` at once: the latch is set and
  the carrier ends the run, so a user model-retry or fallback middleware does not get to
  retry it and cannot turn it into an agent outcome. That is the accepted rule; the recipe
  will say that provider retries belong in the model client's own settings. Anything else
  propagates untouched and is the agent's outcome. Injected faults, tool failures, output
  parsing failures and budget exhaustion are never infrastructure errors.
- **Input and output (requirements 7, 8).** `task_to_input(task)` builds the graph input;
  the default is `{"messages": [{"role": "user", "content": task["input"]}]}` and a task
  without a string `input` is a harness ERROR that names the hook. The toolset snapshot,
  which is all the grader sees, is exactly
  `{"final_output": <text>, "structured_response": <JSON or None>, "state": <ToolEnv.snapshot() or None>}`.
  `final_output` is the text of the last `AIMessage` in the returned messages, found by
  scanning backwards (a structured-output run can end on a `ToolMessage`), or `None`.
  `structured_response` is the returned state's structured response dumped to JSON
  (Pydantic models and dataclasses dumped; anything not JSON-serialisable is a rejection).
  Other graph state is not exposed. A tool call to an unknown name is answered natively and
  is agent behaviour, not an error. In replay the grader sees the source trial's snapshot,
  as for every ARCI replay.
- **Rejected, each with its own fixed message `LangChain adapter unsupported: <reason>`:**
  async invocation; tools with `response_format="content_and_artifact"`; `return_direct`;
  `handle_tool_error` or `handle_validation_error` set on a tool; a callable
  `handle_errors` in the agent's `response_format`; `Command` results; non-JSON tool results; duplicate
  tool names; tools with any injected argument (`InjectedState`, `InjectedStore`,
  `ToolRuntime`, `InjectedToolCallId`, a custom injected argument, or a parameter named
  `runtime`), found through the public marker types and standard-library annotation
  inspection of the schema, `func` and `coroutine`; a model response that is not an
  `AIMessage`. List any further case you find and reject it the same way; do not pass it
  through.
- **Lazy import (ADR 0012 item 4).** `import arci` and every existing command work with
  LangChain absent. Importing `arci.adapters.langchain` without it raises one line naming
  `pip install 'agent-reliability-ci[langchain]'`.

If this shape cannot meet a requirement, stop and report exactly which and why, with a
minimal reproduction. Do not switch to another shape yourself.

## Tests (offline, fake chat models only, no network)

The stock fake chat models do not implement `bind_tools`. Write one local fixture subclass
of a `langchain_core.language_models.fake_chat_models` class that does, and that can script
tool calls, provider exceptions and structured responses. That is the only model used.

Every module under `tests/unit/adapters/` that needs LangChain starts with the guard of
ADR 0012 item 6: skip when LangChain is absent unless `ARCI_REQUIRE_ADAPTERS=1`, in which
case fail. Required coverage:

1. End to end through the real runner on a v1 single-task manifest: tool calls recorded;
   each of `tool_timeout`, `tool_error_once`, `empty_result` fires; budgets enforced; the
   snapshot reaches the grader; a failing trial bundles and replays REPRODUCED.
2. Requirement 9 in full: every rejection reason, live and in replay; list-of-strings
   results; a real error's text and type under a type-filtered retry policy; non-zero retry
   backoff with three or more calls in one message; 1,000 repetitions each of a failure at
   index 0 and mid-message with more calls than pool threads (mark these slow if needed,
   but they must run under `ARCI_REQUIRE_ADAPTERS=1`).
3. Each of requirements 1 to 8 has at least one test that fails if the requirement is
   removed. Name the requirement in the test's docstring.
4. Infrastructure-error rule: each class of the list above gives outcome ERROR even when
   a user model-retry middleware or a user middleware that catches `Exception` is present;
   an HTTP 400, a parsing failure and an exception whose `__cause__` is a `TimeoutError` do
   not. Model steps are counted once per invocation attempt and the model-step budget is
   enforced.
5. Model-visible parity with native LangChain, compared byte for byte against an agent
   built without ARCI: string, dict and list results; validation errors; a transforming
   validator (the body sees the same value as
   natively). A tool whose arguments parse to non-JSON objects still records JSON.
6a. Every rejection in the list, including middleware-owned tools and each disallowed
   `create_agent` key.
6. ADR 0012 item 9: a test, not behind the guard, that starts a fresh interpreter, imports
   `arci`, runs `arci --help`, and fails if `langchain`, `langgraph` or `langsmith` is in
   `sys.modules`.
7. `pyrightconfig.adapters.json`: strict, `include` the two adapter paths, no exclusion.

## Acceptance commands (from the worktree root)

```sh
LANGSMITH_TRACING=false ARCI_REQUIRE_ADAPTERS=1 .venv/bin/pytest tests/unit/adapters tests/unit/toolbox -q
LANGSMITH_TRACING=false .venv/bin/pytest -q          # the whole suite
.venv/bin/ruff format --check .
.venv/bin/ruff check .
.venv/bin/basedpyright
.venv/bin/basedpyright --project pyrightconfig.adapters.json
shasum -a 256 -c FROZEN.sha256
```

## Rules specific to this task

- No git command that changes state. No network. No package installation.
- `src/arci/adapters/langchain.py` is one file; split only if it passes 600 lines.
- No `# pyright: ignore` without a one-line reason. No private LangChain names.
- Out of scope here (next task): `arci init --langchain`, the example, the recipe, fault
  accounting in reports, CI changes.

## Report (your final message, under 70 lines)

Files changed; the last lines of each acceptance command; the per-trial overhead you
measured on an idle machine (median of at least 12 graded trials); a table of requirement
number against the test that proves it; every case you rejected beyond the list; anything
you could not do; risks.

## Sandbox note

You run in a sandbox without network. Some existing tests open loopback sockets. If a test
outside your files fails only because the sandbox refuses a socket, say so in the report
with the test name and the error line; the orchestrator re-runs the whole suite outside the
sandbox. Do not skip, edit or mark any existing test.
