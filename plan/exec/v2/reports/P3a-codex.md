Review the [implementation report](/Users/ajay/Developer/.arci-worktrees/wt-v2-adapter/tests/unit/adapters/evidence/report.md): **adapter implemented; 200 focused tests pass**, including 2,000 fatal-call repetitions.

Changed files:

- `src/arci/adapters/{__init__,langchain}.py`
- `src/arci/toolbox.py`: added `HarnessError` and `fail_harness`
- `tests/unit/adapters/`: fixtures, tests and verification evidence
- `tests/unit/toolbox/test_fail_harness.py`
- `pyrightconfig.adapters.json`

| Acceptance command | Result / last output |
|---|---|
| `LANGSMITH_TRACING=false ARCI_REQUIRE_ADAPTERS=1 .venv/bin/pytest tests/unit/adapters tests/unit/toolbox -q` | 200 passed; `[100%]` |
| `LANGSMITH_TRACING=false .venv/bin/pytest -q` | 1,519 passed, 65 failed, 2 skipped |
| `.venv/bin/ruff format --check .` | `468 files already formatted` |
| `.venv/bin/ruff check .` | `All checks passed!` |
| `.venv/bin/basedpyright` | `0 errors, 0 warnings, 0 notes` |
| `.venv/bin/basedpyright --project pyrightconfig.adapters.json` | `0 errors, 0 warnings, 0 notes` |
| `shasum -a 256 -c FROZEN.sha256` | All 54 match; final line `uv.lock: OK` |

Exact command tails are in the [verification receipt](/Users/ajay/Developer/.arci-worktrees/wt-v2-adapter/tests/unit/adapters/evidence/verification.json).

**Full-suite verification remains limited.** All 65 failures are outside the adapter paths. Confirmed sandbox blockers include:

- `test_http_upstream_gets_the_real_key_and_the_pinned_model`: `PermissionError: [Errno 1] Operation not permitted` during socket binding.
- `test_descendants_are_cleaned_up_after_a_successful_trial` and `test_timeout_mid_call_keeps_the_trace_and_kills_the_whole_process_tree`: the same error executing `ps`.

[Every failed test and error line](/Users/ajay/Developer/.arci-worktrees/wt-v2-adapter/tests/unit/adapters/evidence/full-suite-failures.json) is retained. The full suite preceded six test-only additions; runtime code is unchanged, and all six passed in final focused verification.

**Timing:** median **1.758 seconds per graded trial**, across 12 isolated trials. No other verification jobs ran concurrently. Whole-machine idleness could not be confirmed because the sandbox denied `top`; this is end-to-end elapsed time, not incremental adapter cost.

| Requirement | Proving test |
|---|---|
| 1 | `test_every_disallowed_create_agent_key_is_named` |
| 2 | `test_thousand_fatal_multicall_repetitions` |
| 3 | `test_budget_aborts_siblings_even_when_user_catches` |
| 4 | `test_live_error_identity_text_and_type_filtered_retry` |
| 5 | `test_only_public_framework_imports_are_used` |
| 6 | `test_tool_registration_rejection_live_and_replay` |
| 7 | `test_structured_response_and_last_ai_text_snapshot` |
| 8 | `test_custom_task_input_hook_and_default_validation` |
| 9 | `test_native_result_bytes`, rejection matrices and retry/stress tests |

Additional rejections cover unresolved annotations; reserved `self`/`tool` arguments; invalid call IDs, ordering, re-entry and timeout; unreconstructable errors or fault mappings; non-JSON structured responses; missing model/boundary capability; and factory failures. `RunnableConfig` and explicit `callbacks` parameters are treated as injected arguments.

Remaining limits: trusted middleware can bypass recording; validators run twice; replay restores scrubbed error text without attributes; unmarked injected `"error"` results are ambiguous during replay. Only the supplied pinned dependency environment was tested. No frozen files or existing tests were changed.

Next: have the orchestrator start `LANGSMITH_TRACING=false .venv/bin/pytest -q` outside the sandbox.

