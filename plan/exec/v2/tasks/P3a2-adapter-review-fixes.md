# TASK P3a2: fixes after the independent review of the LangChain adapter

Lane B. Worktree `/Users/ajay/Developer/.arci-worktrees/wt-v2-adapter` (branch `v2/adapter`,
your P3a work is committed there). Work only there. No git command that changes state.

Read: `AGENTS.md`; your brief `plan/exec/v2/tasks/P3a-langchain-adapter-core.md`;
`plan/exec/v2/DECISIONS.md` D-08 (binding); the review record
`plan/exec/v2/reviews/P3a-review-workflow.json` (35 findings, each with a skeptic's verdict
and reproduction notes; none was refuted). All paths under
`/Users/ajay/Developer/agent-reliability-ci/`.

You own the files you created in P3a, and `src/arci/toolbox.py` only if a fix needs it
(say why). Nothing else. No private LangChain names. Every fix gets a test that fails
without it; name the finding number in the test's docstring.

## Fix

1. **Set-up failures are harness ERROR** (D-08 item 1; findings 1, 11, 28). Everything the
   agent function does before the first model invocation attempt: the settings callable
   raising or returning the wrong thing, `create_agent` raising, `task_to_input` raising,
   the graph rejecting its input, a user middleware that implements only async hooks. Keep
   the user's own exception text in the detail (finding 7, 14): `tool factory failed` and
   the like must carry `format_diagnostic` of the cause. Include an experiment-level test:
   a misconfigured adapter must not produce a PASS verdict from v1's gate.
2. **Interrupted runs are rejected** (findings 2, 25): a result with a pending interrupt
   is `LangChain adapter unsupported: interrupted run`.
3. **Order gate deadline** (findings 3, 12, 21, 24; D-08 item 4): no fixed deadline while a
   predecessor is running. A waiter fails with the harness ERROR only after 30 seconds in
   which no call was in progress. Test a healthy message whose first call takes longer than
   the old limit (patch the constant to keep the test fast), and a true deadlock.
4. **Infrastructure rule** (finding 4; D-08 item 2): add statuses 401, 403, 407, 408,
   `socket.gaierror` and `ssl.SSLError`. Still the exception object only, no cause chain.
5. **Replay must reproduce what it recorded** (findings 8, 22, 26, 9, 27, 15, 30):
   - a rebuilt exception must format back (`format_diagnostic`) to exactly the recorded
     text; try the recorded message and its Python literal value as constructor
     arguments; if nothing reproduces the text, it is the unreconstructable ERROR. An
     uncaught `KeyError` from a tool must replay REPRODUCED.
   - live and replay must take the same branch for every built-in fault, including
     `empty_result` applied to a call whose real tool raised. Choose one rule, state it in
     the module docstring, and test live against replay for each built-in fault on both a
     succeeding and a raising tool. If no rule can do it without a frozen change, stop and
     report.
   - a user class in `error_types` wins over a builtin of the same name.
6. **Proxies keep `extras`, `metadata` and `tags`** (findings 10, 34), so provider tool
   options and user policies keyed on them behave natively. Parity test on the bound tool
   definitions.
7. **Tool acceptance** (findings 13, 34, 5): stock synchronous tools built with `Tool`,
   `create_retriever_tool`, `Runnable.as_tool` and `functools.partial` are accepted when
   they have no injected argument; a `BaseTool` subclass whose `_run` takes an injected
   `RunnableConfig` or run manager is handled like natively or rejected with the right
   reason; a user tool with a parameter named `tool` or `self` is rejected at registration.
8. **Abort flag on any `BaseException` from a tool body** (finding 6).
9. **Mismatched adapters** (finding 19): an arm run with a toolset from another
   `make_adapter` call is a harness ERROR with a fixed message.
10. **Tests the review showed missing** (findings 29, 31, 32): the model-step budget
    carrier; each mutation survivor listed in finding 31 that guards a requirement; a
    copied proxy tool.
11. **Overhead** (findings 23, 35): find why LangChain is imported in the grader process
    and avoid it if the adapter can (the snapshot and the check must not need LangChain).
    Report the median of 12 graded trials before and after. If the 1.5 s budget is not
    reachable, say what dominates.

Not to change: D-08 item 5 limits; the `fault_exceptions` key rule (finding 18 goes to the
recipe).

## Acceptance (from the worktree root)

```sh
LANGSMITH_TRACING=false ARCI_REQUIRE_ADAPTERS=1 .venv/bin/pytest tests/unit/adapters tests/unit/toolbox -q
LANGSMITH_TRACING=false .venv/bin/pytest -q
.venv/bin/ruff format --check . && .venv/bin/ruff check . && .venv/bin/basedpyright
.venv/bin/basedpyright --project pyrightconfig.adapters.json
shasum -a 256 -c FROZEN.sha256
```

Sandbox: name any test outside your files that fails only on sockets or `ps`.

Report (under 60 lines): per item what changed and its test; command tails; overhead
before and after; anything you could not do; the limits a recipe must state.
