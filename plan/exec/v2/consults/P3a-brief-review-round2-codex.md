P3a BRIEF: REVISE

`P3a` = [revised brief](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/tasks/P3a-langchain-adapter-core.md). `LC` = the specified installed `site-packages/` directory. B/N identify the previous blocking/non-blocking findings.

**Previous findings**

1. **B1 — PARTLY RESOLVED — CODE.** Last-listed middleware is innermost, but its handler includes binding and output processing—not just provider invocation. A `ToolStrategy.handle_errors` callback raising `TimeoutError` is misclassified. Narrow the interception boundary. Evidence: P3a:128–141; LC/langchain/agents/factory.py:365–368,673,1501–1511.
2. **B2 — PARTLY RESOLVED — CODE.** Original-object capture and restricted reconstruction are specified, but “different behaviour becomes INVALID, never false REPRODUCED” remains false. The probe changed the answer after losing `errno`, consumed the recording, and retained identical FAIL/fingerprint. Remove that guarantee; recording mismatches produce INVALID, differing outcomes/fingerprints produce NOT_REPRODUCED. Evidence: P3a:110–122; src/arci/worker.py:173–181; src/arci/replay.py:108–123.
3. **B3 — RESOLVED — CODE.** Middleware-owned tools are rejected and custom execution/replacement is explicitly trusted. Evidence: P3a:79–84,199–200; LC/langchain/agents/factory.py:1089,1136–1144.
4. **B4 — PARTLY RESOLVED — CODE.** Raw arguments reach the synchronous proxy through a standard-library `ContextVar`: same thread, copied context. Transforming-validator and invalid-input feedback probes match native behavior; the new invocation defects below remain. Evidence: P3a:85–94; LC/langgraph/prebuilt/tool_node.py:966,1066–1072; LC/langchain_core/tools/base.py:1090–1120; LC/langchain_core/runnables/config.py:236–239.
5. **B5 — RESOLVED — CODE.** Returning restricted kwargs lets ARCI construct the graph before invocation, eliminating ignored-factory detection. Evidence: P3a:73–80.
6. **N1 — RESOLVED — CODE.** The brief limits the carrier guarantee to ordinary handlers and retains latches. The identical carrier raised by the inner model middleware reached `graph.invoke`’s caller. Evidence: P3a:105–109; LC/langgraph/pregel/_runner.py:679–694; src/arci/worker.py:191–199.
7. **N2 — RESOLVED — CODE.** Pending-call filtering, shared terminal cause, and per-attempt model-step accounting are explicit. Evidence: P3a:97–103,131,193–194; LC/langchain/agents/factory.py:2021–2032.
8. **N3 — RESOLVED — CODE.** Rejection now covers schema/function annotations, custom injected arguments, call IDs and reserved `runtime`. Evidence: P3a:157–160; LC/langgraph/prebuilt/tool_node.py:2013–2056.
9. **N4 — RESOLVED — CODE.** A local fake-model subclass implementing `bind_tools` is expressly authorized; the offline graph probes worked. Evidence: P3a:172–174; LC/langchain_core/language_models/fake_chat_models.py:21–47.
10. **N5 — RESOLVED — OPINION.** Snapshot scope, backward AI-message search and source-snapshot grading are explicit; kwargs construction adopts the proposed simplification. Evidence: P3a:73–80,142–153.

**New blocking defects**

1. **CODE — Raw dictionaries can be mistaken for tool-call envelopes.** A valid tool argument `{"type":"tool_call"}` succeeds natively but `real_tool.invoke(raw_arguments)` raises `KeyError: 'id'`. The prescribed path turns valid input into a recorded tool failure. Specify an unambiguous public invocation path or an explicit unsupported-case rejection and test it. Evidence: P3a:89–91; LC/langchain_core/tools/base.py:1367–1374.
2. **CODE — Handled body validation errors lose their error status.** With valid arguments, a body-raised Pydantic `ValidationError` and `handle_validation_error=True`, native execution returns `status="error"`; the proposed proxy returns the same text with `status="success"`. Raw invocation discards status before ToolBox records the result. Preserve that status through recording/replay or explicitly narrow support. Evidence: P3a:85–93,195–198; LC/langchain_core/tools/base.py:1115–1120,1133,1416–1417.

Validation: two in-memory `.venv/bin/python -B -c …` runs exited **0**, ending `PROBES COMPLETED` and `REPLAY PROBE PASSED`. No files or git state changed; no network. Acceptance/stress suites were not run.

Next: revise P3a:128–141 to separate provider invocation from binding and output processing.
---
Recorded by the orchestrator on 2026-11-11. Answers written into the brief the same day:
B1: a callable `handle_errors` is rejected, the remaining region is a stated limit.
B2: the guarantee is removed; the actual replay outcomes are stated as a limit with a test.
New 1: the real tool runs through a path that cannot read arguments as an envelope
(`BaseTool.run`, to be confirmed in source), or the shape is rejected. New 2: tools that set
`handle_validation_error` or `handle_tool_error` are rejected in v2.0. No third round: each
answer takes the narrowing option this review named, and the implementer must stop and
report if the shape cannot meet a requirement.
