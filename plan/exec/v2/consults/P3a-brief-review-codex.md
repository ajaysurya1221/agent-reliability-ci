P3a BRIEF: REVISE

References below use `P3a` for the brief and `LC` for the specified installed `site-packages` directory.

**Blocking findings**

1. **CODE — Infrastructure detection cannot satisfy its catch guarantee.**  
   Where: P3a:105–114,153. The outer wrapper sees only exceptions escaping user middleware. An inner handler can recover, return a fallback, or swallow an exhausted failure. Conversely, the wrapped handler includes output parsing, so following its exception causes can misclassify parsing failures.  
   Evidence: `LC/langchain/agents/factory.py:357,1506–1517`; `LC/langchain/agents/middleware/model_retry.py:210–219`. Probe: swallowed `TimeoutError` produced `"recovered"`; the outer wrapper observed no exception.  
   **Fix:** put classification around the actual provider invocation through a public model proxy, after SDK retries but inside user middleware; exclude output parsing. Revise the promise about letting user model retries finish first—it conflicts with irrevocably latching failures before that middleware catches them.

2. **CODE — Replay cannot reconstruct the promised real-error behaviour from the recording.**  
   Where: P3a:94–99. `ToolBox` preserves neither the original object nor constructor arguments/attributes; it records an unqualified class name inside scrubbed text. Classes can share names, and constructing an exception from one string can silently lose state.  
   Evidence: [`toolbox.py:298`](/Users/ajay/Developer/agent-reliability-ci/src/arci/toolbox.py:298), `toolbox.py:254–255`; `src/arci/fingerprint.py:17–25`. Probe: `FileNotFoundError(errno=2, filename=...)` became `"FileNotFoundError: [Errno <n>] missing: '<path>'"`. Reconstructing its class cannot restore `errno` or filename-dependent retry behaviour.  
   **Fix:** specify per-attempt capture/re-raising of the original object live, clearing capture before every attempt. Define replay as a restricted reconstruction contract with unique type names, supported constructors and explicit rejection of unavailable required state; remove blanket behavioural-parity wording. Full fidelity needs a separately approved recording design.

3. **CODE — Supplying proxy tools does not cover every native tool-registration path.**  
   Where: P3a:71–84,123–127. `create_agent` adds `middleware.tools` independently; user middleware can also replace `request.tool`. Those bodies need not cross `ToolBox`.  
   Evidence: `LC/langchain/agents/factory.py:1089,1136–1144`; `LC/langgraph/prebuilt/tool_node.py:132–137,949–966`. Probe: middleware-added tools executed with an empty supplied tool list.  
   **Fix:** reject middleware-owned tools in this task, explicitly exclude dynamic tool replacement/custom execution, and test the registration rejection. State that arbitrary user middleware is trusted code; one outer wrapper does not enforce complete mediation against it.

4. **CODE — Copying only name, description and schema does not preserve BaseTool semantics.**  
   Where: P3a:78–82,155. Proxy validation followed by the prototype’s `real_tool.invoke(arguments)` validates twice. Passing already-parsed arguments can transform them twice or introduce non-JSON objects. Omitting `handle_validation_error` changes native feedback.  
   Evidence: `LC/langchain_core/tools/base.py:834–835,869–874,1091–1098,1115–1125`; `plan/exec/v2/spikes/s2b/arci_langchain.py:86`. Probes: a validator incremented native input to **2**, proxy-plus-original input to **3**; native handled invalid input while the minimal proxy raised `ValidationError`.  
   **Fix:** define the raw-argument versus parsed-argument boundary explicitly, preserve supported error-handler settings, and reject unsupported validation/custom-invocation semantics. Add transforming-validator, non-JSON parsed-argument and handled-validation parity tests.

5. **CODE — Ignored-factory detection happens too late.**  
   Where: P3a:74–77. An unrelated graph may raise or hang before either proposed detector fires; it can also execute real tools before being rejected. The worker treats an ordinary agent exception as a crash.  
   Evidence: [`worker.py:147`](/Users/ajay/Developer/agent-reliability-ci/src/arci/worker.py:147), particularly :168–171; `LC/langchain/agents/factory.py:909–910` returns the graph directly.  
   **Fix:** retain the graph objects issued by the supplied factory and require the builder’s return value to match one **before invocation**. Reject wrappers/custom graphs explicitly. Retain middleware-entry checks as secondary checks.

**Non-blocking findings**

1. **CODE — BaseException propagation works; “uncatchable” is too strong.**  
   Evidence: `LC/langchain_core/tools/base.py:1127–1132`; `LC/langgraph/prebuilt/tool_node.py:997,1076`; `LC/langgraph/pregel/_executor.py:85–125`, `_runner.py:680–694`. Probes preserved the same signal object through tool-body and middleware failures to `graph.invoke`. Ordinary retry middleware catches `Exception`, but user code can catch `BaseException`.  
   **Fix:** promise bypass of ordinary exception handlers, backed by sticky latches and abort checks. Keep carriers until outside graph execution. `fail_harness` before raising is sound: `worker.py:191–199` gives the harness latch precedence over crashes/budgets; replay mismatch still wins.

2. **CODE — The serial gate must track pending calls, not every AI tool call.**  
   Evidence: `LC/langchain/agents/factory.py:1857–1867,2021–2032` runs ARCI’s first-listed `after_model` last, then dispatches only unanswered, non-structured-output calls. `_runner.py:677–694` selects failed futures from a set.  
   **Fix:** derive the gate from the latest AI message’s pending calls, excluding already-answered calls; never reject merely because the final message is a `ToolMessage`. Preserve one terminal cause across aborted siblings so scheduling cannot select different failure fingerprints. Specify model-step accounting, including retries, rather than testing only tool budgets.

3. **CODE — Injection detection needs both schemas and function annotations.**  
   Evidence: `LC/langgraph/prebuilt/tool_node.py:2013–2056` examines both, and treats a parameter named `runtime` specially. Its combined detector is private.  
   **Fix:** use public `InjectedState`, `InjectedStore`, `ToolRuntime` and stdlib annotation inspection, including inherited/schema annotations, `func`, `coroutine`, and the reserved parameter name. Explicitly support or reject `InjectedToolCallId` and custom injected arguments; checking only the model-visible JSON schema misses them.

4. **CODE — Offline tests are feasible after the contradictory contracts are repaired; stock fake models need a fixture subclass.**  
   Public `create_agent`, middleware hooks and `ToolCallRequest.override(tool=...)` exist: `LC/langchain/agents/factory.py:892–908`, middleware `__init__.py`, and `LC/langgraph/prebuilt/tool_node.py:132–137,178–207`.  
   However, `FakeMessagesListChatModel` inherits unimplemented `bind_tools`: `LC/langchain_core/language_models/fake_chat_models.py:21–47`; `chat_models.py:2409–2426`. Probe confirmed `NotImplementedError`.  
   **Fix:** explicitly authorize a local fake subclass implementing `bind_tools`, plus scripted provider exceptions and structured responses. The stress, runner, replay and import-guard tests need no network. Low/latest dependency testing remains a later environment task.

5. **OPINION — The snapshot is sufficient for answer/environment checks, not arbitrary graph-state checks.**  
   Structured output is available directly in returned state; ToolStrategy can end on a `ToolMessage` (`LC/langchain/agents/factory.py:1318–1327`, confirmed by probe). Replay grades the source snapshot, not newly generated output (`worker.py:180–181`; `src/arci/replay.py:115–118`).  
   **Fix:** state those limits and scan backwards for the last AI message. Keep `ToolEnv` for environment state. A simpler builder API is `build_baseline() -> create_agent kwargs`, with ARCI creating the graph itself; this removes ignored-factory detection entirely.

Read-only validation: two in-memory `.venv/bin/python -B -c …` probe runs exited **0**. No files or git state changed; no network used. Full acceptance/stress suites were not run.