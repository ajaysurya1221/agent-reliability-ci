# P1a verification ledger

Task: `/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/tasks/P1a-suite-schema-schedule-stats.md`.
Authority: `P1-CONTRACT.md`, sections 1–4. Sections 5–6 were read for compatibility only.

## Scope

- Created only `src/arci/suite_schema.py`, `src/arci/suite_schedule.py`,
  `src/arci/suite_stats.py`, and files in `tests/unit/suite/`.
- No pre-existing tracked file changed. No git mutations, dependency changes, or network.
- Schema, schedule, and statistics tests each first failed because the corresponding
  module was absent, then passed after implementation.
- One test assumption was corrected: the specified pair-id regex permits a newline
  within a non-colon component. Implementation follows that regex.
- No contract ambiguity was resolved by inventing a behavior; no contract change proposed.
- `table_c.json` contains the two unmodified `balanced` records for independent arms,
  N=20, a=95, b=95/75, from the supplied `spikes/s1c/results.json` Table C.
  Tests carry their own copy and do not depend on the spike checkout at runtime.

## Checks

| Command | Result / last output |
|---|---|
| `.venv/bin/pytest tests/unit/suite -q` | Exit 0, 159 tests, `............... [100%]` |
| `.venv/bin/pytest -q` | Exit 1; 1,496 passed, 65 failed, 2 skipped. Last line: `FAILED tests/unit/recipes/test_mcp_agent.py::test_diff_minimize_bundle_and_replay` |
| `.venv/bin/ruff format --check .` | Exit 0, `463 files already formatted` |
| `.venv/bin/ruff check .` | Exit 0, `All checks passed!` |
| `.venv/bin/basedpyright` | Exit 0, `0 errors, 0 warnings, 0 notes` |
| `shasum -a 256 -c FROZEN.sha256` | Exit 0, all 54 entries OK; last `uv.lock: OK` |

No type-checker suppression was added. Python 3.11 syntax is checked by the repository's
Ruff/BasedPyright settings; execution uses the existing Python 3.13.12 environment.
These local checks are not the orchestrator's acceptance evidence.

## Review and timing

Fresh read-only review: ACCEPT, no findings. The reviewer independently checked
6,876 count states against direct Fraction wealth and matched both Table C fixtures
to the original records. No source file was changed by the reviewer.

Cold-process `operating_characteristics` timing: **1.124 seconds**, 20 cells and 400
registered pairs, heterogeneous three-outcome laws (10 cells with `(2/5, 1/2, 1/10)`
and 10 with `(1/5, 1/2, 3/10)`). Exact probability mass was 1; each directional
probability was at most alpha/2 on this margin case. Time is environment-specific.
The statistical calculation uses integers/Fractions; only the timing display uses a float.


## Full-suite limits and failures

The progress stream contains 1,496 passes, 65 failures and 2 skips (1,563 collected).
All 159 new suite tests passed. Every failure is in a pre-existing test. No existing
test was edited, skipped, or marked by this task.

Direct sandbox evidence includes `socket.bind(self.server_address)` raising
`PermissionError: [Errno 1] Operation not permitted` in
`tests/acceptance/test_decisions.py::test_http_upstream_gets_the_real_key_and_the_pinned_model`,
and `PermissionError: [Errno 1] Operation not permitted: 'ps'` in
`tests/acceptance/test_hardening.py::test_descendants_are_cleaned_up_after_a_successful_trial`
and `tests/acceptance/test_runner_replay.py::test_timeout_mid_call_keeps_the_trace_and_kills_the_whole_process_tree`.
A diagnostic execution of the first failing decision fixture returned
`outcome=ERROR`, `termination=harness_error`,
`failure_detail=PermissionError: [Errno <n>] Operation not permitted`.
The output also contains downstream outcome, recording, gate, replay and CLI assertions.
An unrestricted rerun is required to establish full-suite acceptance; this run does
not independently prove that every failing test passes outside the sandbox.

Exact enumeration was measured at 20 cells/400 pairs only. Larger horizons or very
large rational denominators can require substantially more memory and time.

The following table lists all 65 failed node ids and their reported error line
(preferring the permission error where the failure displays one).

| Failed test | Error line |
|---|---|
| `tests/acceptance/test_decisions.py::test_a_gated_agent_decides_then_acts_and_everything_is_recorded` | `E       AssertionError: assert (<Outcome.ERROR: 'ERROR'> is <Outcome.PASS: 'PASS'>)` |
| `tests/acceptance/test_decisions.py::test_the_real_key_never_enters_the_agent_process` | `E       AssertionError: assert <Outcome.ERROR: 'ERROR'> is <Outcome.PASS: 'PASS'>` |
| `tests/acceptance/test_decisions.py::test_local_rejections_are_the_agents_problem_not_the_harness` | `E       AssertionError: assert (<Outcome.ERROR: 'ERROR'> is <Outcome.FAIL: 'FAIL'>)` |
| `tests/acceptance/test_decisions.py::test_models_discovery_is_recorded_but_is_not_a_tool_event` | `E       AssertionError: assert <Outcome.ERROR: 'ERROR'> is <Outcome.PASS: 'PASS'>` |
| `tests/acceptance/test_decisions.py::test_decisions_after_the_mcp_session_closed_are_still_served_and_recorded` | `E       AssertionError: PermissionError: [Errno <n>] Operation not permitted` |
| `tests/acceptance/test_decisions.py::test_budgets_cover_decision_attempts` | `E       AssertionError: assert (<Outcome.ERROR: 'ERROR'> is <Outcome.FAIL: 'FAIL'>)` |
| `tests/acceptance/test_decisions.py::test_low_confidence_flattens_choices_but_keeps_the_winner` | `E       AssertionError: assert <Outcome.ERROR: 'ERROR'> is <Outcome.PASS: 'PASS'>` |
| `tests/acceptance/test_decisions.py::test_low_confidence_leaves_an_already_uncertain_answer_alone` | `E       ValueError: not enough values to unpack (expected 1, got 0)` |
| `tests/acceptance/test_decisions.py::test_provider_unavailable_is_529_for_the_rest_of_the_trial` | `E       AssertionError: assert (<Outcome.ERROR: 'ERROR'> is <Outcome.PASS: 'PASS'>)` |
| `tests/acceptance/test_decisions.py::test_replay_serves_recorded_decisions_and_never_runs_the_fixture` | `E       assert False` |
| `tests/acceptance/test_decisions.py::test_the_gate_blocks_the_abandoning_agent` | `E       assert (0, 0) == (20, 0)` |
| `tests/acceptance/test_decisions.py::test_diff_hides_the_state_and_still_locates_the_divergence` | `E       AssertionError: assert None == 'decision_low_confidence'` |
| `tests/acceptance/test_decisions.py::test_minimisation_keeps_only_the_decision_fault` | `E       AssertionError: assert <Outcome.ERROR: 'ERROR'> is <Outcome.FAIL: 'FAIL'>` |
| `tests/acceptance/test_decisions.py::test_http_upstream_gets_the_real_key_and_the_pinned_model` | `E       PermissionError: [Errno 1] Operation not permitted` |
| `tests/acceptance/test_decisions.py::test_a_real_provider_failure_is_a_harness_fault_and_a_422_is_passed_through` | `E       PermissionError: [Errno 1] Operation not permitted` |
| `tests/acceptance/test_decisions_hardening.py::test_request_validation_is_total` | `E           AssertionError: ('weird', 'PermissionError: [Errno <n>] Operation not permitted')` |
| `tests/acceptance/test_decisions_hardening.py::test_the_shapes_the_official_sdk_may_send_are_accepted` | `E       AssertionError: PermissionError: [Errno <n>] Operation not permitted` |
| `tests/acceptance/test_decisions_hardening.py::test_one_request_per_connection_so_replay_sees_what_the_agent_saw` | `E       AssertionError: PermissionError: [Errno <n>] Operation not permitted` |
| `tests/acceptance/test_decisions_hardening.py::test_expect_continue_is_answered_at_once_and_never_admitted` | `E       AssertionError: assert (<Outcome.ERROR: 'ERROR'> is <Outcome.FAIL: 'FAIL'>)` |
| `tests/acceptance/test_decisions_hardening.py::test_the_mcp_server_never_inherits_the_real_key` | `E       AssertionError: assert <Outcome.ERROR: 'ERROR'> is <Outcome.PASS: 'PASS'>` |
| `tests/acceptance/test_decisions_sdk.py::test_the_official_sdk_needs_no_change` | `E       AssertionError: PermissionError: [Errno <n>] Operation not permitted` |
| `tests/acceptance/test_decisions_sdk.py::test_the_sdk_retries_twice_then_the_agent_degrades` | `E       AssertionError: assert (<Outcome.ERROR: 'ERROR'> is <Outcome.PASS: 'PASS'>)` |
| `tests/acceptance/test_decisions_v06.py::test_a_gateway_shaped_upstream_is_accepted_recorded_and_served` | `E       PermissionError: [Errno 1] Operation not permitted` |
| `tests/acceptance/test_decisions_v06.py::test_models_discovery_through_the_prefix` | `E       PermissionError: [Errno 1] Operation not permitted` |
| `tests/acceptance/test_decisions_v06.py::test_one_bounded_wait_on_429_or_529_then_one_recorded_attempt` | `E       PermissionError: [Errno 1] Operation not permitted` |
| `tests/acceptance/test_decisions_v06.py::test_encoding_and_non_json_and_tls_are_one_clear_harness_message` | `E       PermissionError: [Errno 1] Operation not permitted` |
| `tests/acceptance/test_decisions_v06.py::test_the_parent_paces_trial_starts_for_http_upstreams` | `E       PermissionError: [Errno 1] Operation not permitted` |
| `tests/acceptance/test_decisions_v06.py::test_a_failed_resend_is_a_harness_fault_not_an_agent_failure` | `E       PermissionError: [Errno 1] Operation not permitted` |
| `tests/acceptance/test_decisions_v06.py::test_every_probability_must_lie_in_the_unit_interval` | `E       PermissionError: [Errno 1] Operation not permitted` |
| `tests/acceptance/test_decisions_v06.py::test_a_dripping_upstream_is_bounded_by_request_seconds` | `E       PermissionError: [Errno 1] Operation not permitted` |
| `tests/acceptance/test_decisions_v06.py::test_preflight_is_bounded_by_the_same_deadline` | `E       PermissionError: [Errno 1] Operation not permitted` |
| `tests/acceptance/test_decisions_v06.py::test_the_report_lists_decision_tokens_and_cost` | `E       PermissionError: [Errno 1] Operation not permitted` |
| `tests/acceptance/test_decisions_v06.py::test_the_raw_upstream_answer_is_recorded_but_never_served` | `E       AssertionError: assert <Outcome.ERROR: 'ERROR'> is <Outcome.PASS: 'PASS'>` |
| `tests/acceptance/test_decisions_v06.py::test_no_upstream_means_a_null_snapshot` | `E       AssertionError: assert <Outcome.ERROR: 'ERROR'> is <Outcome.PASS: 'PASS'>` |
| `tests/acceptance/test_decisions_v06.py::test_an_error_on_removal_never_establishes_minimality` | `E       AssertionError: assert <Outcome.ERROR: 'ERROR'> is <Outcome.FAIL: 'FAIL'>` |
| `tests/acceptance/test_decisions_v06.py::test_minimality_is_never_claimed_for_a_live_upstream` | `E       PermissionError: [Errno 1] Operation not permitted` |
| `tests/acceptance/test_decisions_v06.py::test_preflight_reports_ready_missing_pin_and_unreachable` | `E       PermissionError: [Errno 1] Operation not permitted` |
| `tests/acceptance/test_decisions_v06.py::test_preflight_never_prints_provider_controlled_secrets` | `E       PermissionError: [Errno 1] Operation not permitted` |
| `tests/acceptance/test_decisions_v06.py::test_the_gate_and_the_hero_story_hold_through_the_gateway` | `E       PermissionError: [Errno 1] Operation not permitted` |
| `tests/acceptance/test_hardening.py::test_descendants_are_cleaned_up_after_a_successful_trial` | `E                   PermissionError: [Errno 1] Operation not permitted: 'ps'` |
| `tests/acceptance/test_hero_decisions.py::test_frozen_experiment_blocks_the_regression_and_passes_the_repair[b-BLOCK]` | `E       AssertionError: ('trial outcome ERROR',)` |
| `tests/acceptance/test_hero_decisions.py::test_frozen_experiment_blocks_the_regression_and_passes_the_repair[a-PASS]` | `E       AssertionError: ('trial outcome ERROR',)` |
| `tests/acceptance/test_hero_decisions.py::test_frozen_experiment_blocks_the_regression_and_passes_the_repair[c-PASS]` | `E       AssertionError: ('trial outcome ERROR',)` |
| `tests/acceptance/test_hero_decisions.py::test_one_clean_run_hides_the_regression` | `E           AssertionError: ('a', 'PermissionError: [Errno <n>] Operation not permitted')` |
| `tests/acceptance/test_hero_decisions.py::test_the_failure_replays_offline_minimises_and_the_repair_passes` | `E       AssertionError: assert <Outcome.ERROR: 'ERROR'> is <Outcome.FAIL: 'FAIL'>` |
| `tests/acceptance/test_mcp.py::test_both_clients_pass_without_injection` | `E           AssertionError: good` |
| `tests/acceptance/test_mcp.py::test_injected_timeout_separates_the_retrying_client_from_the_broken_one` | `E       AssertionError: assert (<Outcome.ERROR: 'ERROR'> is <Outcome.PASS: 'PASS'>)` |
| `tests/acceptance/test_mcp.py::test_a_client_that_never_touches_its_tools_is_failed_by_the_snapshot_oracle` | `E       AssertionError: assert (<Outcome.ERROR: 'ERROR'> is <Outcome.FAIL: 'FAIL'>)` |
| `tests/acceptance/test_mcp.py::test_timeout_budget_and_cleanup` | `E       AssertionError: assert (<Outcome.ERROR: 'ERROR'> is <Outcome.FAIL: 'FAIL'>)` |
| `tests/acceptance/test_mcp.py::test_replay_mismatch_is_invalid` | `E       AssertionError: tools/call exchanges must be in the recording` |
| `tests/acceptance/test_mcp.py::test_the_repaired_client_passes_the_same_fault_live` | `E       AssertionError: assert <ReplayStatus.REPRODUCED: 'REPRODUCED'> is <ReplayStatus.NOT_REPRODUCED: 'NOT_REPRODUCED'>` |
| `tests/acceptance/test_mcp.py::test_experiment_gate_and_cli_for_command_agents` | `E       assert (0, 0) == (12, 0)` |
| `tests/acceptance/test_mcp.py::test_diff_and_minimise_work_on_command_trials` | `E       AssertionError: assert (None == 'tool_timeout')` |
| `tests/acceptance/test_mcp_hardening.py::test_leftover_recording_is_invalid_even_when_the_agent_hangs_to_the_deadline` | `E       AssertionError: assert (<Outcome.ERROR: 'ERROR'> is <Outcome.FAIL: 'FAIL'>)` |
| `tests/acceptance/test_mcp_hardening.py::test_a_client_protocol_mistake_is_the_agents_problem_not_a_harness_error` | `E       AssertionError: PermissionError: [Errno <n>] Operation not permitted` |
| `tests/acceptance/test_mcp_hardening.py::test_tool_error_text_from_the_bridge_does_not_leak_run_specific_paths` | `E       AssertionError: assert (<Outcome.ERROR: 'ERROR'> is <Outcome.FAIL: 'FAIL'>)` |
| `tests/acceptance/test_mcp_hardening.py::test_large_recordings_are_streamed_not_squeezed_into_one_frame` | `E       AssertionError: PermissionError: [Errno <n>] Operation not permitted` |
| `tests/acceptance/test_mcp_hardening.py::test_pipelined_large_messages_do_not_deadlock_the_boundary` | `E       AssertionError: PermissionError: [Errno <n>] Operation not permitted` |
| `tests/acceptance/test_mcp_hardening.py::test_an_infrastructure_exit_code_invalidates_the_trial_instead_of_blaming_the_agent` | `E       AssertionError: assert ('PermissionError: [Errno <n>] Operation not permitted' is not None and 'infrastructure' in 'PermissionError: [Errno <n>] Operation not permitted')` |
| `tests/acceptance/test_mcp_toolset.py::test_a_python_toolset_becomes_an_mcp_environment` | `E       AssertionError: assert <Outcome.ERROR: 'ERROR'> is <Outcome.PASS: 'PASS'>` |
| `tests/acceptance/test_mcp_toolset.py::test_fault_injection_and_the_oracle_work_through_the_bridge` | `E       AssertionError: assert <Outcome.ERROR: 'ERROR'> is <Outcome.PASS: 'PASS'>` |
| `tests/acceptance/test_runner_replay.py::test_timeout_mid_call_keeps_the_trace_and_kills_the_whole_process_tree` | `E                   PermissionError: [Errno 1] Operation not permitted: 'ps'` |
| `tests/unit/examples/test_guardrail_agent.py::test_offline_run_fails_b_only_on_dangerous_asks_when_the_provider_is_down` | `E       AssertionError: ['PermissionError: [Errno <n>] Operation not permitted', 'PermissionError: [Errno <n>] Operation not permitted', 'Perm...', 'PermissionError: [Errno <n>] Operation not permitted', 'PermissionError: [Errno <n>] Operation not permitted', ...]` |
| `tests/unit/recipes/test_mcp_agent.py::test_the_faulted_run_blocks_with_a_sealed_store` | `E       AssertionError: SMOKE DESIGN: n_per_arm=8 (alpha 0.05, delta 0.1, K=1): under this design's fixed-sample Clopper–Pearson rule two perfect arms cannot PASS below N=42 and a total collapse cannot BLOCK below N=8; expect INCONCLUSIVE. Plan a confirmatory N: arci plan --baseline-rate P --candidate-rate P --target-verdict BLOCK` |
| `tests/unit/recipes/test_mcp_agent.py::test_diff_minimize_bundle_and_replay` | `E       assert 3 == 1` |
