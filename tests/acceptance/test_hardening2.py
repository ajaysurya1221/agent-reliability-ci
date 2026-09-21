"""Second hardening round: findings from the final pre-release review. FROZEN."""

from __future__ import annotations

import time

import pytest

from arci.schema import (
    Bucket,
    Condition,
    Event,
    FaultSpec,
    Outcome,
    Termination,
    ToolMode,
    TrialEnvelope,
    Verdict,
)
from tests.acceptance.helpers import COND_CLEAN, MOD, contract, manifest, spec

pytestmark = pytest.mark.acceptance


def _cond(factory: str) -> Condition:
    return Condition(
        condition_id=factory,
        faults=(FaultSpec(name=f"{MOD}:{factory}", bucket=Bucket.FALSIFY, tool="fetch"),),
    )


def _run(agent: str, **kw: object) -> tuple[TrialEnvelope, list[Event]]:
    from arci.runner import run_trial

    seen: list[Event] = []
    oracle = str(kw.pop("oracle", "oracle"))
    env = run_trial(spec(agent, **kw), seen.append, contract(oracle))  # pyright: ignore[reportArgumentType]
    return env, seen


@pytest.mark.parametrize("oracle", ["dict_oracle", "async_oracle"])
def test_an_oracle_must_return_a_real_bool(oracle: str) -> None:
    env, _ = _run("good_agent", condition=COND_CLEAN, oracle=oracle)
    assert env.outcome is Outcome.ERROR and env.termination is Termination.GRADER_ERROR


@pytest.mark.parametrize("agent", ["nan_agent", "surrogate_agent"])
def test_values_that_are_not_json_never_break_sealing(agent: str) -> None:
    """The boundary raises ValueError to the agent; uncaught, that is the agent's crash."""
    env, _ = _run(agent, condition=COND_CLEAN)
    assert env.validate_seal()
    assert env.outcome is Outcome.FAIL and env.termination is Termination.CRASH


@pytest.mark.parametrize(
    "factory", ["bad_before_perturbation", "bad_after_perturbation", "exiting_perturbation"]
)
def test_a_misbehaving_injector_is_always_a_harness_error(factory: str) -> None:
    env, _ = _run("swallow_everything_agent", condition=_cond(factory))
    assert env.final_state is not None and env.final_state.get("stored") == 42
    assert env.outcome is Outcome.ERROR and env.termination is Termination.HARNESS_ERROR


def test_latches_survive_a_hang_or_a_hard_exit() -> None:
    hung, _ = _run(
        "swallow_then_hang_agent", condition=_cond("broken_perturbation"), max_seconds=3.0
    )
    assert hung.outcome is Outcome.ERROR and hung.termination is Termination.HARNESS_ERROR
    gone, _ = _run("swallow_then_exit_agent", condition=_cond("broken_perturbation"))
    assert gone.outcome is Outcome.ERROR and gone.termination is Termination.HARNESS_ERROR
    spent, _ = _run("budget_then_exit_agent", condition=COND_CLEAN, max_tool_calls=5)
    assert spent.outcome is Outcome.FAIL and spent.termination is Termination.BUDGET


def test_a_grader_result_is_not_held_hostage_by_a_detached_child() -> None:
    started = time.monotonic()
    env, _ = _run(
        "good_agent", condition=COND_CLEAN, oracle="detaching_oracle", grader_seconds=20.0
    )
    assert time.monotonic() - started < 8  # the detached child holds stdout for 12 seconds
    assert env.outcome is Outcome.PASS


def test_run_trial_rejects_unobservable_contracts_itself() -> None:
    from arci.runner import run_trial

    sink: list[Event] = []
    env = run_trial(
        spec("good_agent", condition=COND_CLEAN),
        sink.append,
        contract(unobservable=("network egress",)),
    )
    assert env.validate_seal()
    assert env.outcome is Outcome.ERROR and env.termination is Termination.HARNESS_ERROR


def test_a_sink_failing_on_the_last_event_does_not_rewrite_history() -> None:
    from arci.runner import run_trial

    delivered: list[Event] = []

    def sink(event: Event) -> None:
        delivered.append(event)
        if event.kind == "trial_end":
            raise OSError("disk full at the very end")

    env = run_trial(spec("good_agent", condition=COND_CLEAN), sink, contract())
    assert env.outcome is Outcome.ERROR and env.termination is Termination.HARNESS_ERROR
    assert [(e.seq, e.kind, e.payload) for e in env.events] == [
        (e.seq, e.kind, e.payload) for e in delivered
    ]
    assert env.events[-1].payload == {}  # trial_end carries no verdict; the envelope does


def test_replay_never_builds_injectors() -> None:
    from arci.runner import run_trial

    live, _ = _run("good_agent")
    sink: list[Event] = []
    replayed = run_trial(
        spec("good_agent", condition=_cond("exploding_factory")).model_copy(
            update={
                "tool_mode": ToolMode.REPLAY,
                "recording": live.recording,
                "replay_final_state": live.final_state,
            }
        ),
        sink.append,
        contract(),
    )
    assert replayed.outcome is Outcome.PASS


def test_the_gate_never_raises_on_a_malformed_typed_manifest() -> None:
    from arci.gate import decide

    for update in ({"alpha": 0.0}, {"alpha": 5.0}, {"delta": -1.0}, {"n_per_arm": 0}):
        d = decide(manifest().model_copy(update=update), ())
        assert d.verdict is Verdict.ERROR and d.validate_seal()


def test_alpha_too_small_for_k_conditions_is_an_error_not_a_crash() -> None:
    from arci.gate import decide
    from tests.acceptance.helpers import COND_TIMEOUT, synthetic_trials

    m = manifest(alpha=1e-6, conditions=(COND_CLEAN, COND_TIMEOUT))  # tail 1.25e-7: unsupported
    trials = [
        *synthetic_trials(m, condition_id="clean", baseline_successes=190, candidate_successes=190),
        *synthetic_trials(
            m, condition_id="fetch_timeout", baseline_successes=190, candidate_successes=190
        ),
    ]
    assert decide(m, trials).verdict is Verdict.ERROR
