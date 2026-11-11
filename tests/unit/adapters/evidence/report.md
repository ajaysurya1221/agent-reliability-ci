# P3a adapter verification

The authoritative acceptance command receipts are in `verification.json`; their full output is in the corresponding `.log` files. Candidate SHA-256 entries bind the checked Python files and adapter configuration. `attempt1-*` retains the failed reserved-self probe and deliberately interrupted pre-fix full suite. No acceptance claim rests on the interrupted run.

## Requirement coverage

| Requirement | Discriminating test |
|---|---|
| 1: adapter owns composition | `test_every_disallowed_create_agent_key_is_named`; `test_native_validation_feedback_and_middleware_position` |
| 2: serial order and abort | `test_thousand_fatal_multicall_repetitions` (1000 each, indices 0 and 20, 40 calls); `test_serial_gate_timeout_and_reentry_abort_all_waiters` |
| 3: fatal budget/rejection carrier | `test_budget_aborts_siblings_even_when_user_catches`; `test_runtime_result_rejection_is_not_retryable` |
| 4: original errors and restricted replay | `test_live_error_identity_text_and_type_filtered_retry`; `test_replay_restores_declared_exception_type_without_running_body`; `test_replay_can_reproduce_despite_lost_errno_and_different_policy_path` |
| 5: public API only | `test_only_public_framework_imports_are_used`; `test_missing_public_capability_is_named` |
| 6: sticky harness outcome | `test_tool_registration_rejection_live_and_replay`; `test_infrastructure_errors_end_as_error_before_user_model_retry`; toolbox `test_fail_harness_latches_before_raising_outside_exception_handlers` |
| 7: native unknown calls and grading snapshot | `test_unknown_name_is_native_agent_feedback`; `test_structured_response_and_last_ai_text_snapshot`; `test_runner_records_faults_and_snapshot_reaches_independent_grader` |
| 8: task input hook | `test_custom_task_input_hook_and_default_validation` |
| 9: expanded regression and stress coverage | `test_native_result_bytes`; `test_serial_retries_with_backoff_do_not_interleave`; registration/result rejection matrices and 2000 stress repetitions |

## Rejections beyond the explicit list

Fixed unsupported reasons additionally cover unresolved tool annotations; reserved boundary arguments (`self` before native handling, `tool` after native validation); missing/duplicate call IDs; a call outside the current message; re-entry; order wait timeout; unreconstructable recorded error classes; unconstructable fault mappings; non-JSON structured output; missing model; boundary missing `fail_harness`; tool factory failure; and default input without a string `input` (names `task_to_input`). The brief already separately requires the last three capability/input/config checks. `RunnableConfig` and explicit `callbacks` arguments are included in injected-argument rejection. Async functions assigned as a synchronous `func` are included in async rejection.

## Limits

- Middleware is trusted. Replacing the requested tool or returning without the handler bypasses the recorded boundary for that call; the adapter does not detect or measure it.
- Validators execute twice on the same raw input. Side-effectful validators are outside the parity claim. Raw `self` is explicitly unsupported even if native validation would otherwise discard or reject it.
- Replay restores only the named exception class and scrubbed recorded message. Attributes and exact messages are not reconstructed. A changed policy path can still be REPRODUCED when sequence, outcome and fingerprint agree.
- Rejected Command/non-JSON live results have no completed recorded exchange. Replaying such a source is INVALID from the missing exchange, without running its tool body or rediscovering its return value.
- Custom injectors should set `injected_by`: unmarked `error_kind="error"` results cannot be distinguished from real tool failures in replay and follow recorded-class reconstruction.
- Replay rebuilds the factory with seed zero; it must be safe to call and provide seed-independent schemas.
- Serial order includes retry backoff. Provider retries belong in the model client. Infrastructure-shaped errors from LangChain binding/output processing share the provider classification region.
- Only the supplied installed versions are tested: langchain 1.4.9, langchain-core 1.7.7, langgraph 1.2.20, langgraph-prebuilt 1.1.1. Endpoint-version matrices require separate environments. No network, installs, frozen edits or state-changing git commands were used.

## Full-suite verification limit

The complete suite executed on the final runtime and failed 65 tests outside the adapter paths. The full log and `full-suite-failures.json` retain every failed test and its assertion/error lines. Socket binding is denied with `PermissionError: [Errno 1] Operation not permitted`; for example `tests/acceptance/test_decisions.py::test_http_upstream_gets_the_real_key_and_the_pinned_model`. Both `tests/acceptance/test_hardening.py::test_descendants_are_cleaned_up_after_a_successful_trial` and `tests/acceptance/test_runner_replay.py::test_timeout_mid_call_keeps_the_trace_and_kills_the_whole_process_tree` reach their process-inspection assertions but fail with `PermissionError: [Errno 1] Operation not permitted: 'ps'`.

Representative existing decision and MCP fixtures independently reproduce `ERROR/harness_error` with a scrubbed PermissionError detail (`sandbox-probes.json`). The dependent outcome/empty-recording assertions have not each been independently validated outside the sandbox. Do not treat this as a full-suite pass. No existing test was edited, skipped or marked. The full suite preceded six tests-only rejection additions; the runtime is byte-identical and the final focused suite includes those additions.

## Final results

200 focused tests pass, including all 2000 fatal-call repetitions. The full-suite progress and failed-node summary give 1519 passed, 65 failed, and 2 skipped. Both Ruff checks pass; both strict BasedPyright checks report zero errors/warnings/notes. All 54 frozen hashes match. No type-ignore comments were added.

The isolated 12-graded-trial timing median is **1.757636 seconds/trial**. These are end-to-end worker, adapter and grader elapsed samples, not an incremental native-versus-adapter delta. No other verification job ran concurrently. Whole-host idleness was not established: the sandbox refused `/usr/bin/top`; load averages before/after and all samples are in `overhead.json`. This is not claimed as a verified idle-machine measurement.

| Acceptance command | Exit | Last output line |
|---|---:|---|
| `LANGSMITH_TRACING=false .venv/bin/pytest -q` | 1 | `FAILED tests/unit/recipes/test_mcp_agent.py::test_diff_minimize_bundle_and_replay` |
| `LANGSMITH_TRACING=false ARCI_REQUIRE_ADAPTERS=1 .venv/bin/pytest tests/unit/adapters tests/unit/toolbox -q` | 0 | `........................................................                 [100%]` |
| `.venv/bin/ruff format --check .` | 0 | `468 files already formatted` |
| `.venv/bin/ruff check .` | 0 | `All checks passed!` |
| `.venv/bin/basedpyright` | 0 | `0 errors, 0 warnings, 0 notes` |
| `.venv/bin/basedpyright --project pyrightconfig.adapters.json` | 0 | `0 errors, 0 warnings, 0 notes` |
| `shasum -a 256 -c FROZEN.sha256` | 0 | `uv.lock: OK` |

## Changed implementation and test files

- `pyrightconfig.adapters.json`
- `src/arci/adapters/__init__.py`
- `src/arci/adapters/langchain.py`
- `src/arci/toolbox.py`
- `tests/unit/adapters/__init__.py`
- `tests/unit/adapters/fixtures.py`
- `tests/unit/adapters/test_capabilities.py`
- `tests/unit/adapters/test_core.py`
- `tests/unit/adapters/test_edges.py`
- `tests/unit/adapters/test_lazy_import.py`
- `tests/unit/adapters/test_rejections.py`
- `tests/unit/adapters/test_replay_and_order.py`
- `tests/unit/adapters/test_runner.py`
- `tests/unit/toolbox/test_fail_harness.py`

Verification artifacts are confined to `tests/unit/adapters/evidence/`. Existing files outside ownership were not changed. The orchestrator must rerun the full suite without the sandbox restrictions before treating repository-wide acceptance as established.
