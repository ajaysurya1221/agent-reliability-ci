"""v0.5 hardening: findings of the adversarial release review, as regression tests. FROZEN.

Each test reproduces one way a buggy agent, a careless fixture, the SDK's own behaviour or the
boundary's shutdown could have changed a verdict, corrupted a recording or leaked the real key.
"""

from __future__ import annotations

from typing import Any, cast

import pytest

from arci.schema import DECISION_TOOL, Outcome, Termination, TrialEnvelope
from tests.acceptance.decision_fixtures import decision_contract, decision_spec, decisions

pytestmark = pytest.mark.acceptance


def _run(variant: str, **kw: object) -> TrialEnvelope:
    from arci.runner import run_trial

    return run_trial(decision_spec(variant, **kw), lambda _e: None, decision_contract())  # pyright: ignore[reportArgumentType]


def _starts(env: TrialEnvelope) -> list[str]:
    return [cast(str, e.payload["tool"]) for e in env.events if e.kind == "tool_start"]


def test_an_overdue_fixture_is_a_harness_fault_even_if_it_answers_later() -> None:
    env = _run("gated", spec=decisions(fixture_name="slow_fixture", request_seconds=0.05))
    assert env.outcome is Outcome.ERROR and env.termination is Termination.HARNESS_ERROR


def test_a_fixture_fault_still_queued_at_shutdown_is_not_lost() -> None:
    env = _run("fireandforget", spec=decisions(fixture_name="broken_fixture"))
    assert env.outcome is Outcome.ERROR and env.termination is Termination.HARNESS_ERROR


def test_request_validation_is_total() -> None:
    for variant in ("weird", "deep"):
        env = _run(variant)
        assert env.outcome is Outcome.PASS, (variant, env.failure_detail)
        assert env.termination is Termination.COMPLETED
        assert _starts(env).count(DECISION_TOOL) == 1, variant  # the bad request was never admitted


def test_the_shapes_the_official_sdk_may_send_are_accepted() -> None:
    env = _run("sdkshapes")
    assert env.outcome is Outcome.PASS, env.failure_detail
    assert env.final_state == {"stored": "refund", "log": ["start"]}
    start = next(
        e for e in env.events if e.kind == "tool_start" and e.payload["tool"] == DECISION_TOOL
    )
    questions = cast(dict[str, Any], cast(dict[str, Any], start.payload["arguments"])["questions"])
    assert questions["department"]["criteria"]["billing"] is None
    assert isinstance(questions["department"]["instructions"], dict)


def test_a_decision_during_any_pending_mcp_exchange_is_a_harness_fault() -> None:
    env = _run("pingrace", server_args=("--slow-ping", "1"))
    assert env.outcome is Outcome.ERROR and env.termination is Termination.HARNESS_ERROR


def test_one_request_per_connection_so_replay_sees_what_the_agent_saw() -> None:
    env = _run("pipeline")
    assert env.outcome is Outcome.PASS, env.failure_detail
    assert _starts(env).count(DECISION_TOOL) == 2  # the pipelined first request, then the real one
    assert env.usage.tool_calls == 4  # log, decision, decision, store: the trailing bytes never ran
    assert [r.occurrence for r in env.recording if r.tool == DECISION_TOOL] == [0, 1]


def test_expect_continue_is_answered_at_once_and_never_admitted() -> None:
    env = _run("expect")
    assert env.outcome is Outcome.FAIL and env.termination is Termination.COMPLETED
    assert env.final_state == {"stored": "expect-rejected", "log": ["start"]}
    assert DECISION_TOOL not in _starts(env)


def test_the_mcp_server_never_inherits_the_real_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TYPESAFE_API_KEY", "real-secret")
    env = _run("gated", server_args=("--env-probe",))
    assert env.outcome is Outcome.PASS
    assert cast(dict[str, Any], env.final_state)["env_has_key"] is False


def test_diagnostics_never_carry_the_real_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TYPESAFE_API_KEY", "real-secret")
    env = _run("gated", spec=decisions(fixture_name="leaky_fixture"))
    assert env.outcome is Outcome.ERROR and env.termination is Termination.HARNESS_ERROR
    assert "real-secret" not in env.model_dump_json()
