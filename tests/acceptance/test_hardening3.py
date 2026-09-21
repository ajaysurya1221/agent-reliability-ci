"""Third and last hardening round: the release re-check. FROZEN."""

from __future__ import annotations

import pytest

from arci.schema import (
    Bucket,
    Condition,
    Event,
    FaultSpec,
    Outcome,
    Termination,
    TrialEnvelope,
    Verdict,
)
from tests.acceptance.helpers import COND_CLEAN, MOD, contract, manifest, spec

pytestmark = pytest.mark.acceptance


def _cond(factory: str, **params: str) -> Condition:
    fault = FaultSpec(
        name=f"{MOD}:{factory}", bucket=Bucket.FALSIFY, tool="fetch", params=dict(params)
    )
    return Condition(condition_id=factory, faults=(fault,))


def _run(agent: str, condition: Condition) -> TrialEnvelope:
    from arci.runner import run_trial

    sink: list[Event] = []
    return run_trial(spec(agent, condition=condition), sink.append, contract())


@pytest.mark.parametrize("raises", ["tool_fault", "budget", "replay_miss"])
@pytest.mark.parametrize("agent", ["swallow_everything_agent", "good_agent", "uncaught_agent"])
def test_an_injector_raising_boundary_exceptions_is_a_harness_fault(
    raises: str, agent: str
) -> None:
    """Whether the agent retries, swallows or dies, a buggy injector is never the agent's fault."""
    env = _run(agent, _cond("control_raising_perturbation", raises=raises))
    assert env.validate_seal()
    assert env.outcome is Outcome.ERROR and env.termination is Termination.HARNESS_ERROR


@pytest.mark.parametrize("factory", ["unprintable_perturbation", "surrogate_factory"])
@pytest.mark.parametrize("agent", ["swallow_everything_agent", "swallow_then_exit_agent"])
def test_unprintable_diagnostics_cannot_erase_a_harness_fault(factory: str, agent: str) -> None:
    env = _run(agent, _cond(factory))
    assert env.validate_seal()
    assert env.outcome is Outcome.ERROR and env.termination is Termination.HARNESS_ERROR


def test_a_large_grader_response_is_read_not_deadlocked() -> None:
    from arci.runner import run_trial

    many = tuple(f"missing_tool_{i:04d}" for i in range(2000))
    sink: list[Event] = []
    env = run_trial(
        spec("good_agent", condition=COND_CLEAN), sink.append, contract(required_tools=many)
    )
    assert env.contract is not None and len(env.contract.violations) == 2000
    assert env.outcome is Outcome.FAIL and env.termination is Termination.COMPLETED


def test_the_gate_survives_absurd_numbers() -> None:
    from arci.gate import decide

    for update in (
        {"alpha": 10**400},
        {"delta": 10**400},
        {"n_per_arm": 10**400},
        {"alpha": float("inf")},
        {"delta": float("nan")},
    ):
        d = decide(manifest().model_copy(update=update), ())
        assert d.verdict is Verdict.ERROR and d.validate_seal()
