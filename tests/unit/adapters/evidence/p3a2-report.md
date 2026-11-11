# P3a2 adapter review fixes

All 11 task items implemented. Local diff review: ACCEPT after fixing pre-invocation BaseException recovery. Full-suite acceptance remains unverified outside the sandbox.

Files changed:
- Runtime: `src/arci/adapters/langchain.py`, `src/arci/toolbox.py`. ToolBox gains read-only replay-mode and registration-identity queries so mismatched adapters reject without inspecting private boundary state.
- Fixtures: `tests/unit/adapters/{fixtures,checks}.py`; the independent check consumes JSON and imports no optional framework.
- Existing tests: `tests/unit/adapters/{test_edges,test_lazy_import,test_rejections,test_replay_and_order,test_runner}.py`.
- New tests: `tests/unit/adapters/{test_review_fixes,test_review_replay,test_review_tools}.py`.
- Receipts: `tests/unit/adapters/evidence/p3a2-{report.md,verification.json,full-suite-failures.json}`.

| Item | Change | Regression test (under tests/unit/adapters) |
|---|---|---|
| 1 | Setup, graph input, async-only hooks and pre-provider binding failures latch ERROR; causes retained. | `test_setup_failure_latches_with_cause`, `test_tool_binding_before_first_model_attempt_is_setup_error`, `test_misconfigured_experiment_cannot_pass_v1_gate` |
| 2 | Pending middleware/tool interrupts reject as `interrupted run`. | `test_interrupted_run_rejected` |
| 3 | Gate deadline counts only continuous idle time; active calls and retries have no gate deadline. | `test_slow_healthy_predecessor_has_no_gate_deadline`, bounded `test_serial_gate_timeout_and_reentry_abort_all_waiters` |
| 4 | Added 401/403/407/408, DNS and TLS; exact object-only classification retained. | `test_added_infrastructure_errors_bypass_user_handler`, `test_infrastructure_rule_exact_boundaries` |
| 5 | Replay diagnostics must match exactly; try text/literal reconstruction; declared classes override builtins; value-only builtin faults preserve real errors. | `test_rebuilt_diagnostic_is_exact_or_rejected`, `test_uncaught_keyerror_bundle_reproduces`, `test_every_builtin_fault_has_same_live_and_replay_branch`, `test_declared_error_type_overrides_builtin_name` |
| 6 | Both proxy layers retain extras, metadata, tags, and the native single-input Tool definition. | `test_proxy_definitions_and_tool_policy_metadata_match_native` |
| 7 | Accept stock Tool, retriever, Runnable and partial forms; reject user subclass injection and reserved fields at registration. | `test_stock_sync_tools_have_native_observations`, `test_subclass_injection_rejected`, `test_reserved_names_rejected_at_registration` |
| 8 | Tool-body BaseException sets the abort flag even if user middleware swallows it. | `test_base_exception_stops_siblings_even_if_swallowed` |
| 9 | A live arm with another adapter's toolset rejects before model/tool execution. | `test_mismatched_adapter_rejected_before_model` |
| 10 | Model-budget carrier, mixed replay indices, schema-only injection, infrastructure edges, private aliases, copied proxies and bounded deadlock checks added. | `test_model_budget_carrier_bypasses_recovery_and_backoff`, `test_mixed_real_and_injected_replay_advances_attempt_index`, `test_schema_only_injection_is_rejected`, `test_copied_proxy_rejected`; all 11 final-source mutants killed |
| 11 | Independent oracle moved out of the framework-importing fixture module. | `test_grader_check_import_is_framework_free`, `test_measure_twelve_graded_trials` |

Command results (pytest invocations also wrote JUnit receipts; counts below are from those receipts):
| Command | Exit / result / tail |
|---|---|
| `LANGSMITH_TRACING=false ARCI_REQUIRE_ADAPTERS=1 .venv/bin/pytest tests/unit/adapters tests/unit/toolbox -q` | 0; **308 passed**, 0 skipped; final progress `[100%]` |
| `LANGSMITH_TRACING=false .venv/bin/pytest -q` | 1; **1633 passed, 65 failed, 2 skipped**; final failure `tests/unit/recipes/test_mcp_agent.py::test_diff_minimize_bundle_and_replay` |
| `.venv/bin/ruff format --check . && .venv/bin/ruff check . && .venv/bin/basedpyright` | 0; `472 files already formatted`; `All checks passed!`; `0 errors, 0 warnings, 0 notes` |
| `.venv/bin/basedpyright --project pyrightconfig.adapters.json` | 0; `0 errors, 0 warnings, 0 notes` |
| `shasum -a 256 -c FROZEN.sha256` | 0; **54 OK**; last line `uv.lock: OK` |

Overhead: median of 12 graded trials **2.372219 s before → 0.879899 s after**, below 1.5 s. Samples are in `p3a2-verification.json`. These are local elapsed measurements with variable machine load, not a controlled speedup estimate. Removing the grader's LangChain import accounts for the avoidable work; a fresh-interpreter test verifies the new grader stays framework-free.

Limits / work not completed:
- All 65 failing test names and diagnostics are in `p3a2-full-suite-failures.json`. They are outside owned paths and identical across both full runs: 29 directly print PermissionError; 36 are dependent assertions in socket-dependent tests. IPv4/Unix bind and `ps` denials, plus representative MCP/decision harness errors, were reproduced. An unrestricted rerun is still required. Two Node SDK tests skip because `@typesafe-ai/sdk` is absent.
- Validation used the installed LangChain 1.4.9 / core 1.7.7 / LangGraph 1.2.20 / prebuilt 1.1.1 and fake models. No other dependency endpoints or real providers were tested. Runnable.as_tool emits its upstream beta warning; JUnit adds a record_property compatibility warning. No new type ignores.

Recipe must state:
- Synchronous execution only; interrupts, injected arguments, return_direct, artifacts, tool error/validation handlers, callable structured-output error handlers, Command and non-JSON results reject. Tuples and integer-keyed dictionaries remain rejected. Empty/duplicate call IDs and raw `tool`/`self` keys reject; non-finite arguments remain agent failures (D-08 unchanged).
- Middleware is trusted and may replace/skip calls outside recording; copied ARCI proxies reject. Proxies do not preserve arbitrary user subclass identity. Validators run twice on raw arguments; side effects are unsupported. Serial calls include retries/backoff, so wall-clock budgets need headroom; only 30 seconds with no active call is a gate deadlock.
- Replay calls the model again, rebuilds tools with seed zero, executes no tool bodies and grades the source snapshot; factories must be safe and schemas seed-independent. It checks call sequence/outcome/fingerprint, not the final answer. Declare non-builtin error classes (especially builtin-name collisions); unknown, ambiguous or non-round-trippable errors become harness ERROR. Attributes and original messages are not restored, so policy branches can differ even with REPRODUCED. Custom injectors are outside the tested builtin parity claim.
- Provider retries belong in model-client settings. Infrastructure classification uses only the exception object and the specified status/transport shapes, including binding/output processing; unsupported SDK status shapes can remain agent failures. `fault_exceptions` uses kinds such as `timeout`/`error`, not manifest fault names. The key rule is unchanged.
- Default tasks need string `input` or a `task_to_input` hook. Grader state is `{final_output, structured_response, state}`; keep the oracle independent of LangChain imports. Stores may contain task data, and ARCI does not enable LangSmith tracing. Bare partial works through the adapter and public Tool.run; this installed native ToolNode cannot inspect a bare partial directly.

This report is local verification, not orchestrator acceptance evidence. No frozen files, dependencies, index, commits or branches were changed.
