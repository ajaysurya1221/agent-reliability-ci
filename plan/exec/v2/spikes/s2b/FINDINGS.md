# S2b revised LangChain adapter spike

## Decision

**Not accepted as an all-green spike.** Required native/injected-fault parity fails:
a native failing tool executes its body, while `tool_error_once` short-circuits it.
The no-middleware native exception is `ValueError`; the injected exception is
`ToolFault`. The verifier retains this as FAIL and exits nonzero. Calling a body
on a short-circuited fault merely to equalize the count would violate ARCI's
frozen semantics, so this spike does not do that.

This is an offline prototype against installed LangChain 1.4.9, langchain-core
1.7.7, and LangGraph 1.2.20. No product code, dependencies, frozen files, or git
state were changed. All created files are under `plan/exec/v2/spikes/s2b/`.

## Final verification

Runs **0003 and 0004** both exit **1**, with **17 OK and 1 FAIL**. Their complete
check verdicts and all **53 sealed trial hashes** are identical. Both use the same
source digests as revised run 0002. The sole failing assertion is native_parity;
OK limit-demonstration checks do not mean those missing capabilities work.

Final measured graded-trial median: **0.9998 s** (12 samples, run 0004).
Revised runs 0002/0003 measured 5.6308/0.9188 s. These are machine-local elapsed
measurements with substantial between-run variation; they do not establish a
controlled speedup over S2's approximately 1.5 s graded figure.

Ruff formatting/lint and strict basedpyright pass. All 54 frozen hashes pass.
The 735 inventoried tracked/non-ignored files outside plan/exec/v2 are unchanged.
No pyright ignores were added. Quality receipts are in `quality/results.json`;
`quality/final-verification.json` verifies the adjacent final runs independently.

## Design actually implemented

`make_adapter(make_tools, build_baseline, build_candidate)` creates the three
module-level entrypoints `toolset`, `baseline`, and `candidate`. The live toolset
uses the exact `BaseTool` instances returned by the user's factory. The builder
gets those instances and `[SerialOrder, Boundary]`; user retry/error middleware
belongs between the two. The user writes no second body or schema stub.

`SerialOrder` is outermost. It assigns indexes from each AIMessage and waits on a
condition variable before entering the entire user middleware chain. Its `finally`
releases the next index even when validation, a tool, or a budget raises. Keeping
retry inside this region prevents the next logical call from interleaving between
attempts. `Boundary` is last and makes one `ToolBox.call` per attempted execution;
it does not build error ToolMessages or catch ToolFault. The user's policy decides
whether to retry, handle, or propagate it.

Validation happens in the outer wrapper, before the user's retry/error policy.
It raises LangChain's `ToolInvocationError`, allowing ToolNode's own handler to
create native validation feedback. Successful calls also undergo the user's
BaseTool.invoke validation. Success messages use the installed private
`langchain_core.tools.base._format_output` rule; ARCI separately seals JSON.
Final output uses `.text`, is captured in the snapshot, and is emitted as a
`model_step` event. Emitting that event does **not** make replay compare it.

## Evidence by required check

| # | Result | Evidence and interpretation |
|---|---|---|
| 1 | FAIL | `parity.json`: none native/adapted bodies 1/0 and ValueError/ToolFault; retry bodies 2/1 with the same successful answer; error middleware bodies 1/0 with the same unavailable answer. `exception_positions` separately verifies none=FAIL/crash, retry=PASS with two recorded calls, error=FAIL/completed for the independent oracle. |
| 2 | OK | Own-body counters in tool metadata: clean one body; pre-injected failure zero bodies; injected retry one body across two boundary calls; real-error retry two bodies across two calls; empty_result one body. The tool is not duplicated. |
| 3 | OK | `argument-parity.json` compares all three middleware configurations: wrong-typed input reaches zero bodies, and native/adapted observations are identical. Validation errors are not incorrectly exposed to the user's error middleware. |
| 4 | OK | `faults.json` counts four tool_finish injections for each of tool_timeout, tool_error_once, empty_result. Counts come from events, not declared conditions. |
| 5 | OK | Three real budget envelopes end FAIL/budget: retry exhaustion, second multi-call exhaustion, first multi-call exhaustion. Non-null final snapshots prove the worker got past graph execution; the assertion does not rely only on a budget latch that could mask a timeout. |
| 6 | OK | Twenty multi-call repetitions with a retry record `key-0, key-0, key-1`, identical full event payload sequences and sealed hashes. `multi-replay.json` is REPRODUCED. The deliberately false oracle expectation supplies a failing trial that the existing bundle API permits. |
| 7 | BOUNDED | Live async, artifacts, return_direct, Command return are ERROR/harness_error with exact fixed diagnostics in `unsupported.json`. A swallowed Command rejection still yields ERROR. `unsupported-async-replay.trial.json` demonstrates the remaining replay gap: FAIL/crash because replay does not call snapshot. The brief permits reporting the missing unfrozen support; details below. |
| 8 | OK | `message-parity.json` compares model-visible multiline-string and literal-dict observations byte for byte. The dict has deliberately non-sorted key insertion order and Unicode. Final list-block messages are captured via `.text`. |
| 9 | LIMIT PROVEN | `failure.bundle.json` replays REPRODUCED. A separately resealed diagnostic bundle changes only the task's requested final answer; `altered-answer.trial.json` emits `answer=ALTERED` while grading the original final_state. `replay-limit.json` still says REPRODUCED. Replay does not verify the new answer. This is a negative test, not a corrupted-seal test. |
| 10 | MEASURED | `cost.json` contains 12 real graded envelope wall_seconds and their median. `check-imports.stdout.txt` is False: importing user_check loads neither LangChain nor LangGraph. Compare the measured median to S2 review's approximately 1.5 s graded cost; S2's 0.7476 s was launch/import/exit only. |
| 11 | OK | `user-burden.json`: user_app.py 44 physical lines, user_check.py 7. API/body names and configuration are listed below. The model fixture is not hidden adapter behavior. |
| 12 | VERIFIED SEPARATELY | Per-run `scope-differences.json`, frozen output, and `verdicts.json` retain scope/hash evidence and cross-run comparison. Only paths outside plan/exec/v2 are included in scope assertions, as instructed. Initial untracked files are preserved. |

The scheduled smoke experiment has twelve trials: baseline 4 PASS / 2 FAIL,
candidate 6 FAIL; its gate is INCONCLUSIVE (CLI exit 2). Empty-result recovery is
not provided by ToolRetryMiddleware: the empty result is successful, not an
exception. These are fixed scripted fixtures, not evidence of production
reliability, adoption, or a statistically established regression.

## Remaining kernel boundary and exact proposed extension

Live registration failures occur in the factory, already a harness-error path.
Runtime rejection stores a fixed reason in the adapter's capture. The live
`DerivedToolSet.snapshot()` then raises that reason outside the worker's
agent-exception guard: see `src/arci/worker.py:183-189`.

That route is insufficient for replay and for an agent that catches an unsupported
exception then hangs. Replay omits the factory (`worker.py:125-127`) and copies
`replay_final_state` instead of calling snapshot (`worker.py:180-181`). An
unsupported exception from agent code falls into the crash branch at
`worker.py:168-171`. A deliberate async replay confirms FAIL/crash.

The smallest proposed unfrozen addition is a public
`ToolBox.reject_unsupported(detail: str) -> NoReturn` adjacent to
`src/arci/toolbox.py:154-156`. It would call the existing private
`__mark_harness(detail)` and then raise a fixed exception. This immediately uses
the worker's existing harness latch even when an outer user middleware catches
it, and works in live and replay mode. The adapter would require this concrete
capability, without changing frozen ToolBoxProtocol or schemas. **It is not
implemented here.** A snapshot-only workaround is not represented as a complete
solution to unsupported-mode classification.

Real tool exceptions are caught and normalized at `toolbox.py:298-307` and exposed
as ToolFault by ToolBox.call. The wrapper does not reconstruct original exception
classes from error strings. Type-specific retry/error policies therefore can
behave differently from native tools. Injected errors are ToolFault by frozen
contract; no exact ValueError parity claim is made. Tool error details are also
scrubbed to a deterministic single line, with numbers/paths normalized.

Replay's final-answer limitation is the existing rule, not a frozen-file defect:
`worker.py:180-181` grades the source snapshot, and `src/arci/replay.py:115-118`
compares outcome/fingerprint. Recording a final-answer model_step does not change
that predicate. No frozen edit or fabricated tool call is used to disguise this.

## User-written surface

The complete callable/binding inventory is:

- `make_tools(task, seed)`, including the real nested `lookup(key)` tool body.
- `build_baseline(tools, middleware)` and `build_candidate(tools, middleware)`, each
  containing one create_agent call.
- `toolset, baseline, candidate = make_adapter(...)`.
- Independent `check(task, final_state)` in the LangChain-free `user_check.py`.
- `arci.yaml`, including the task, references, conditions, and budgets.

The example imports `Graph`, `Middleware`, `make_adapter`, `create_agent`,
`ToolRetryMiddleware`, `BaseTool`, `StructuredTool`, and `JsonValue`.
`ScriptedModel` is an explicit test replacement for the user's existing model;
its complete implementation is `scripted_model.py`. Extra adversarial factories
and builders live in `probe_app.py`, not in the user's required integration code.
The counters and metadata in the example are visible instrumentation, included in
the physical line count. No user-authored capture class, ARCI toolset wrapper,
agent entry function, duplicate body, or schema stub is required.

## Supported scope and risks

This proves a synchronous, fresh-process fixture subset, with native tool objects,
pure Pydantic validation, serial indexed calls, and ordinary JSON returns. It is
not ready as a general framework adapter:

- Accepted arguments are validated twice. Stateful/custom validator effects and
  middleware that rewrites arguments are not covered by native-parity claims.
- The native formatter and ToolInvocationError are private/version-sensitive APIs.
- Replay reconstructs tool schemas by calling make_tools(task, 0) because the
  frozen AgentFn supplies an RNG, not the original seed, and replay skips the
  toolset factory. Seed-dependent tool schemas and side-effectful factories are
  outside this prototype's replay support. Replay does not execute tool bodies.
- There is no claim for injected runtime/store/state, provider-side tools,
  checkpoint/resume, graph mutations, streaming, concurrent graph invocations,
  or middleware that changes/skips tool execution. The two supplied ARCI
  middleware entries must remain outermost and innermost respectively.
- Canonical JSON transport discards object insertion order in task dictionaries
  and replay recordings. Live literal-dict formatting is tested; preserving
  arbitrary original dict insertion order through replay is not established.

## Attempts and exact reproduction

All attempts are retained under out/. Run 0001 exposed an input-fixture ordering
confound: the native tool read an insertion-ordered task dict, but the worker
received its canonical key order. The revised message test returns a literal dict
inside the same native/adapted tool body and retains exact byte equality; it does
not sort observed text to force a pass. Run 0001 also predates the strengthened
validation, exact-diagnostic, and budget-completion assertions. Source hashes in
each attempt distinguish versions; checks never pool statistical runs.

From the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 LANGSMITH_TRACING=false PYTHONPATH=src:plan/exec/v2/spikes/s2b /Users/ajay/Developer/.arci-worktrees/v2-spike-venv/bin/python -B plan/exec/v2/spikes/s2b/run_spike.py
.venv/bin/ruff format --no-cache --check plan/exec/v2/spikes/s2b
.venv/bin/ruff check --no-cache plan/exec/v2/spikes/s2b
.venv/bin/basedpyright --pythonpath /Users/ajay/Developer/.arci-worktrees/v2-spike-venv/bin/python plan/exec/v2/spikes/s2b
shasum -a 256 -c FROZEN.sha256
```

Run the first command twice to compare adjacent identical source versions.
`out/latest.txt` locates the latest invocation. Every command performed by the
runner has an argv/exit receipt and stdout/stderr files. Replay temporary files
stay beneath that attempt's out directory. No network or installation is used.
Quality-command receipts are under quality/. No full product suite was run because
all implementation and verification code is confined to this spike.
