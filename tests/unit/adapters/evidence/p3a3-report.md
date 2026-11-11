# P3a3 local report

All nine requested items are implemented. This report is local verification, not orchestrator acceptance.

Files changed: `src/arci/adapters/langchain.py`; `tests/unit/adapters/{second_fixtures.py,test_second_fixes.py,test_review_fixes.py,test_review_tools.py}`; this report and `p3a3-verification.json`.

| Item | Change and regression proof |
|---|---|
| 1 | Graph entry marks runtime; each inner invocation separately detects pre-provider setup failure. `test_graph_entry_attribution_and_bound_model` covers PII, before_agent, before_model, wrap_model_call and cached responses through the real runner and replay. `test_binding_failure_on_later_attempt_stays_setup_error` protects later binding. |
| 2 | Removed model type pre-check. Bound-model runner case passes; existing invalid-model cases still latch ERROR. |
| 3 | All literal-parser exceptions discard only that candidate. `test_literal_parse_failure_only_discards_candidate` covers malformed text, TypeError, MemoryError, RecursionError and KeyboardInterrupt. |
| 4 | Replay uses error kind/detail, independently of injected_by. `test_failure_content_controls_reconstruction` covers custom, built-in and absent tags; live preserves exception identity. |
| 5 | Accept documented BaseTool run_manager; retain config rejection. `test_run_manager_subclass_native_parity` matches native output and verifies a real manager reaches the body. |
| 6 | Both proxies retain extras/metadata/tags by reference. `test_proxy_options_are_references_even_when_not_copyable` checks identity and lock-bearing metadata. |
| 7 | Single-input Tool skips signature reserved-name checks. `test_single_input_function_reserved_names_have_native_parity` covers tool/self; raw-key rejection has separate controls. |
| 8 | `test_gate_idle_clock_resets_after_call` uses a controlled clock and missing successor. Removing the reset deterministically fails: no idle wait instead of 30 seconds. |
| 9 | Partial tools remain accepted; module docstring states native create_agent rejection. Existing partial test now explicitly verifies native rejection and adapter success. |

| Acceptance command | Exit and last output/result |
|---|---|
| `LANGSMITH_TRACING=false ARCI_REQUIRE_ADAPTERS=1 .venv/bin/pytest tests/unit/adapters tests/unit/toolbox -q` | 0; `[100%]`; 332 passed; existing Runnable.as_tool beta warning. |
| `LANGSMITH_TRACING=false .venv/bin/pytest -q` | 1; 1657 passed, 65 failed, 2 skipped; last failure: `tests/unit/recipes/test_mcp_agent.py::test_diff_minimize_bundle_and_replay`. |
| `.venv/bin/ruff format --check . && .venv/bin/ruff check . && .venv/bin/basedpyright` | 0; `475 files already formatted`; `All checks passed!`; `0 errors, 0 warnings, 0 notes`. |
| `.venv/bin/basedpyright --project pyrightconfig.adapters.json` | 0; `0 errors, 0 warnings, 0 notes`. |
| `shasum -a 256 -c FROZEN.sha256` | 0; all 54 OK; last line `uv.lock: OK`. |

Before fixes, the new regression tests had 19 failures and 4 passing controls. Removing either the idle reset or the per-invocation provider marker reset also fails its regression test. No new type ignores were added.

Full-suite failures exactly match the 65 names in the stored P3a2 run. Current traces show socket-bind `PermissionError: [Errno 1] Operation not permitted` and `PermissionError: [Errno 1] Operation not permitted: 'ps'`. All names and current diagnostic excerpts are in [p3a3-verification.json](p3a3-verification.json); dependent assertions do not all print the underlying permission cause. No adapter/toolbox failures occurred.

Limits: custom perturbations must preserve real-error kind/detail and distinguish synthetic error text; rewritten diagnostics cannot ensure replay parity. Partial-tool acceptance differs from native create_agent. Run-manager parent-callback linkage may differ. These limits are documented in the module.

Remaining action: orchestrator reruns full acceptance outside the sandbox. No state-changing git, network, dependency, frozen-file or out-of-scope source changes were made.
