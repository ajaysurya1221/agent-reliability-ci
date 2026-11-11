"""Graded process-runner integration, provider attribution, and replay limits."""

from __future__ import annotations

import importlib.util
import os
import statistics
import time
from pathlib import Path
from typing import Any

import pytest

if importlib.util.find_spec("langchain") is None:
    if os.environ.get("ARCI_REQUIRE_ADAPTERS") == "1":
        raise ImportError("ARCI_REQUIRE_ADAPTERS=1 requires LangChain")
    pytest.skip("optional LangChain extra is absent", allow_module_level=True)

from pydantic import JsonValue

from arci.replay import make_bundle, replay
from arci.runner import run_trial
from arci.schedule import build_schedule
from arci.schema import (
    ArmSpec,
    Bucket,
    Budgets,
    Condition,
    ContractSpec,
    FaultSpec,
    Manifest,
    Outcome,
    ReplayStatus,
    Termination,
    ToolMode,
)

FIXTURE = "tests.unit.adapters.fixtures"


def manifest(
    *,
    task: dict[str, JsonValue] | None = None,
    fault: str | None = None,
    budgets: Budgets | None = None,
) -> Manifest:
    return Manifest.create(
        experiment_id="adapter-test",
        task_id="single-task",
        task={"input": "find answer", **(task or {})},
        toolset=f"{FIXTURE}:toolset",
        contract=ContractSpec(oracle="tests.unit.adapters.checks:oracle"),
        baseline=ArmSpec(label="baseline", agent=f"{FIXTURE}:baseline"),
        candidate=ArmSpec(label="candidate", agent=f"{FIXTURE}:candidate"),
        conditions=(
            Condition(
                condition_id="clean" if fault is None else fault,
                faults=() if fault is None else (FaultSpec(name=fault, bucket=Bucket.FALSIFY),),
            ),
        ),
        n_per_arm=1,
        budgets=budgets or Budgets(max_seconds=20, grader_seconds=10),
    )


@pytest.mark.parametrize("fault", [None, "tool_timeout", "tool_error_once", "empty_result"])
def test_runner_records_faults_and_snapshot_reaches_independent_grader(fault: str | None) -> None:
    """Requirements 1, 4, 7: real runner records faults and grades the exact adapter snapshot."""
    plan = manifest(task={"retry_tools": True}, fault=fault)
    spec = build_schedule(plan)[0]
    trial = run_trial(spec, lambda _event: None, plan.contract)
    assert trial.outcome is Outcome.PASS, trial.failure_detail
    assert trial.contract is not None and trial.contract.success
    assert trial.final_state is not None
    assert set(trial.final_state) == {"final_output", "structured_response", "state"}
    assert trial.final_state["final_output"] == "done"
    assert trial.usage.model_steps == 2
    assert len(trial.recording) == (2 if fault in {"tool_timeout", "tool_error_once"} else 1)
    if fault is not None:
        assert trial.recording[0].result.injected_by == fault
    if fault == "empty_result":
        assert trial.recording[0].result.value is None


def test_runner_failed_trial_bundles_and_replays_without_tool_bodies() -> None:
    """Requirements 4, 7: recorded failing trial reproduces with the source snapshot."""
    plan = manifest(task={"reject_oracle": True, "retry_tools": True}, fault="tool_timeout")
    spec = build_schedule(plan)[0]
    trial = run_trial(spec, lambda _event: None, plan.contract)
    assert trial.outcome is Outcome.FAIL
    root = Path(__file__).resolve().parents[3]
    bundle = make_bundle(plan, trial, spec, root=root, include=("tests/unit/adapters/fixtures.py",))
    result = replay(bundle)
    assert result.status is ReplayStatus.REPRODUCED, result


@pytest.mark.parametrize("budget", ["tools", "models"])
def test_runner_budget_has_fail_budget_outcome(budget: str) -> None:
    """Requirement 3: retries cannot convert exhausted budgets to ordinary agent outcomes."""
    plan = manifest(
        task={"retry_tools": True, "retry_models": True},
        budgets=Budgets(max_tool_calls=0 if budget == "tools" else 10, max_model_steps=1),
    )
    trial = run_trial(build_schedule(plan)[0], lambda _event: None, plan.contract)
    assert trial.outcome is Outcome.FAIL, trial.failure_detail
    assert trial.termination is Termination.BUDGET
    assert trial.usage.model_steps == 1
    assert trial.usage.tool_calls == (0 if budget == "tools" else 1)


@pytest.mark.parametrize(
    "kind",
    [
        "http429",
        "http503",
        "response599",
        "connection",
        "timeout",
        "transport",
        "api_connection",
        "api_timeout",
    ],
)
@pytest.mark.parametrize("policy", ["retry_models", "catch_models"])
def test_infrastructure_errors_end_as_error_before_user_model_retry(kind: str, policy: str) -> None:
    """Requirement 6 / ADR 0011.10: provider infrastructure latches before user retries."""
    plan = manifest(task={"provider_error": kind, policy: True})
    trial = run_trial(build_schedule(plan)[0], lambda _event: None, plan.contract)
    assert trial.outcome is Outcome.ERROR, trial.failure_detail
    assert trial.termination is Termination.HARNESS_ERROR
    assert trial.usage.model_steps == 1


@pytest.mark.parametrize("kind", ["http400", "parse", "cause"])
def test_agent_exceptions_are_not_infrastructure(kind: str) -> None:
    """Requirement 6: HTTP 400, parsing failures, and nested timeout causes stay agent failures."""
    plan = manifest(task={"provider_error": kind})
    trial = run_trial(build_schedule(plan)[0], lambda _event: None, plan.contract)
    assert trial.outcome is Outcome.FAIL, trial.failure_detail
    assert trial.termination is Termination.CRASH
    assert trial.usage.model_steps == 1


def test_model_retry_counts_each_invocation_attempt() -> None:
    """Requirement 6: an ordinary agent error retried by user middleware counts twice."""
    plan = manifest(task={"provider_error": "parse", "retry_models": True})
    trial = run_trial(build_schedule(plan)[0], lambda _event: None, plan.contract)
    assert trial.termination is Termination.COMPLETED, trial.failure_detail
    assert trial.usage.model_steps == 2
    assert trial.outcome is Outcome.FAIL  # oracle wants "done", model says "recovered"


def test_replay_can_reproduce_despite_lost_errno_and_different_policy_path() -> None:
    """Requirement 4 limit: changed error attributes need not change replay's verdict."""
    plan = manifest(task={"real_error": True, "reject_oracle": True})
    spec = build_schedule(plan)[0]
    live = run_trial(spec, lambda _event: None, plan.contract)
    assert live.outcome is Outcome.FAIL and live.termination is Termination.COMPLETED
    replayed = run_trial(
        spec.model_copy(
            update={
                "tool_mode": ToolMode.REPLAY,
                "recording": live.recording,
                "replay_final_state": live.final_state,
            }
        ),
        lambda _event: None,
        plan.contract,
    )
    assert replayed.outcome is Outcome.FAIL and replayed.termination is Termination.COMPLETED
    assert replayed.failure_fingerprint == live.failure_fingerprint
    assert replay(make_bundle(plan, live, spec)).status is ReplayStatus.REPRODUCED
    # The direct middleware test asserts the differing branch observations. Here the
    # real runner verifies the verdict is legitimately REPRODUCED under that policy.


def test_measure_twelve_graded_trials(record_property: Any) -> None:
    """Measure process, adapter and independent grading elapsed cost without speed claims."""
    plan = manifest()
    spec = build_schedule(plan)[0]
    elapsed: list[float] = []
    for _ in range(12):
        start = time.monotonic()
        trial = run_trial(spec, lambda _event: None, plan.contract)
        elapsed.append(time.monotonic() - start)
        assert trial.outcome is Outcome.PASS, trial.failure_detail
    measured = statistics.median(elapsed)
    record_property("graded_trial_median_seconds", measured)
    record_property("graded_trial_samples_seconds", elapsed)
    print(f"\nADAPTER_GRADED_TRIAL_MEDIAN_SECONDS={measured:.6f}; n=12; samples={elapsed!r}")


@pytest.mark.parametrize("kind", ["command", "nonjson"])
def test_unsupported_live_result_bundle_is_invalid_without_reexecuting_body(kind: str) -> None:
    """Requirement 6: replay cannot recreate an unrecordable live result; it fails closed.

    Live rejects the result with a harness latch. Replay runs no bodies and has no
    recorded exchange to serve, so the frozen replay rule returns ERROR/replay_miss
    and bundle INVALID rather than reconstructing the unsupported live object.
    """
    plan = manifest(task={"runtime_reject": kind})
    spec = build_schedule(plan)[0]
    # Seed zero is reserved by this fixture as a replay-body execution tripwire.
    spec = spec.model_copy(update={"seed": 7})
    live = run_trial(spec, lambda _event: None, plan.contract)
    assert live.outcome is Outcome.ERROR
    assert live.termination is Termination.HARNESS_ERROR
    assert live.recording == ()
    expected = "Command result" if kind == "command" else "non-JSON tool result"
    assert expected in (live.failure_detail or "")
    bundle = make_bundle(plan, live, spec)
    result = replay(bundle)
    assert result.status is ReplayStatus.INVALID
    assert result.observed_outcome is Outcome.ERROR
    assert result.detail == "recording mismatch"


def test_real_tool_timeout_is_an_agent_failure_not_infrastructure() -> None:
    plan = manifest(task={"tool_timeout_error": True, "retry_models": True})
    trial = run_trial(build_schedule(plan)[0], lambda _event: None, plan.contract)
    assert trial.outcome is Outcome.FAIL
    assert trial.termination is Termination.CRASH
    assert trial.recording[0].result.error_kind == "error"


def test_misconfigured_experiment_cannot_pass_v1_gate() -> None:
    """Findings 1, 11, 28: real setup-error trials invalidate even a permissive gate."""
    from arci.gate import decide
    from arci.schema import Verdict

    # At this prespecified coarse margin, two all-crash arms would pass the old adapter.
    data = manifest(task={"setup_error": True}).model_dump(exclude={"record_sha256"})
    data.update(n_per_arm=2, delta=0.99)
    plan = Manifest.create(**data)
    trials = [run_trial(spec, lambda _event: None, plan.contract) for spec in build_schedule(plan)]
    assert all(
        t.outcome is Outcome.ERROR and t.termination is Termination.HARNESS_ERROR for t in trials
    )
    assert all("ValueError: settings unavailable" in (t.failure_detail or "") for t in trials)
    assert decide(plan, trials).verdict is Verdict.ERROR
    from arci.schema import TrialEnvelope

    crashed = []
    for trial in trials:
        data = trial.model_dump(exclude={"record_sha256"})
        data.update(outcome=Outcome.FAIL, termination=Termination.CRASH)
        crashed.append(TrialEnvelope.create(**data))
    assert decide(plan, crashed).verdict is Verdict.PASS


def test_uncaught_keyerror_bundle_reproduces() -> None:
    """Findings 8, 22, 26: a real tool KeyError must replay with the same crash fingerprint."""
    plan = manifest(task={"key_error": True})
    spec = build_schedule(plan)[0]
    trial = run_trial(spec, lambda _event: None, plan.contract)
    assert trial.outcome is Outcome.FAIL and trial.termination is Termination.CRASH
    assert trial.failure_detail == "KeyError: 'zzz'"
    assert replay(make_bundle(plan, trial, spec)).status is ReplayStatus.REPRODUCED
