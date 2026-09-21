"""Trace divergence and fault minimisation. FROZEN."""

from __future__ import annotations

import pytest

from arci.schema import Event, Outcome, ReplayStatus, TrialEnvelope
from tests.acceptance.helpers import COND_NOISY, COND_TIMEOUT, contract, manifest, spec

pytestmark = pytest.mark.acceptance


def _run(agent: str, **kw: object) -> TrialEnvelope:
    from arci.runner import run_trial

    sink: list[Event] = []
    return run_trial(spec(agent, **kw), sink.append, contract())  # pyright: ignore[reportArgumentType]


def test_first_divergence_is_located_after_the_injected_fault() -> None:
    from arci.diff import first_divergence

    passing = _run("good_agent", condition=COND_TIMEOUT, arm="baseline")
    failing = _run("fragile_agent", condition=COND_TIMEOUT, arm="candidate")
    d = first_divergence(passing, failing)
    assert d.after_injection == "tool_timeout"
    assert d.common_prefix >= 4  # trial_start, log start/finish, model_step, fetch start ...
    assert d.left is not None and d.right is not None and d.left != d.right
    assert "fetch" in d.left or "model_step" in d.left  # the good agent retries here


def test_identical_trials_do_not_diverge() -> None:
    from arci.diff import first_divergence

    a = _run("fragile_agent")
    b = _run("fragile_agent")
    d = first_divergence(a, b)
    assert d.left is None and d.right is None and d.common_prefix == len(a.events)


def test_signatures_ignore_ids_and_timing() -> None:
    from arci.diff import step_signature

    e1 = Event(
        trial_id="x",
        seq=3,
        kind="tool_start",
        at_ms=1.0,
        payload={"tool": "fetch", "call_id": "c-1", "arguments": {"key": "answer"}},
    )
    e2 = Event(
        trial_id="y",
        seq=9,
        kind="tool_start",
        at_ms=99.0,
        payload={"tool": "fetch", "call_id": "c-7", "arguments": {"key": "answer"}},
    )
    assert step_signature(e1) == step_signature(e2)


def test_minimiser_keeps_only_the_triggering_fault() -> None:
    from arci.minimize import minimize_faults
    from arci.replay import replay

    m = manifest(conditions=(COND_NOISY,))
    failing = _run("fragile_agent", condition=COND_NOISY)
    assert failing.outcome is Outcome.FAIL
    result = minimize_faults(m, failing, spec("fragile_agent", condition=COND_NOISY))
    assert result.kept == ("tool_timeout",)
    assert set(result.removed) == {"empty_result", "tool_error_once"}
    assert result.minimality == "1-minimal"
    assert result.bundle.expected_fingerprint == failing.failure_fingerprint
    assert len(result.bundle.spec.condition.faults) == 1
    assert replay(result.bundle).status is ReplayStatus.REPRODUCED


def test_minimiser_refuses_a_passing_trial() -> None:
    from arci.minimize import minimize_faults

    m = manifest(conditions=(COND_NOISY,))
    passing = _run("good_agent", condition=COND_NOISY)
    with pytest.raises(ValueError):
        minimize_faults(m, passing, spec("good_agent", condition=COND_NOISY))
