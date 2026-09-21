from __future__ import annotations

from arci.diff import first_divergence, step_signature
from arci.schedule import spec_sha256
from arci.schema import Event, Outcome, Termination, TrialEnvelope, TrialSpec
from tests.acceptance.helpers import spec


def _envelope(trial_spec: TrialSpec, events: tuple[Event, ...]) -> TrialEnvelope:
    return TrialEnvelope.create(
        spec_sha256=spec_sha256(trial_spec),
        experiment_id=trial_spec.experiment_id,
        trial_id=trial_spec.trial_id,
        pair_id=trial_spec.pair_id,
        arm=trial_spec.arm,
        variant=trial_spec.variant,
        task_id=trial_spec.task_id,
        condition_id=trial_spec.condition.condition_id,
        seed=trial_spec.seed,
        outcome=Outcome.PASS,
        termination=Termination.COMPLETED,
    ).model_copy(update={"events": events})


def test_step_signature_ignores_positional_fields_and_canonicalizes_arguments() -> None:
    first = Event(
        trial_id="left",
        seq=2,
        at_ms=1.5,
        kind="tool_start",
        payload={
            "tool": "fetch",
            "call_id": "c-0001",
            "occurrence": 0,
            "arguments": {"z": 1, "a": {"two": 2, "one": 1}},
        },
    )
    second = Event(
        trial_id="right",
        seq=99,
        at_ms=900.0,
        kind="tool_start",
        payload={
            "arguments": {"a": {"one": 1, "two": 2}, "z": 1},
            "occurrence": 8,
            "call_id": "c-9000",
            "tool": "fetch",
        },
    )

    assert step_signature(first) == step_signature(second)
    assert step_signature(first) == (
        'tool_start tool="fetch" arguments={"a":{"one":1,"two":2},"z":1}'
    )


def test_first_divergence_when_left_trial_is_a_strict_prefix() -> None:
    trial_spec = spec("fragile_agent")
    start = Event(trial_id="left", seq=0, kind="trial_start", payload={"arm": "candidate"})
    next_step = Event(
        trial_id="right",
        seq=1,
        kind="model_step",
        payload={"summary": "retry", "attempt": 1},
    )
    left = _envelope(trial_spec, (start,))
    right = _envelope(trial_spec, (start, next_step))

    divergence = first_divergence(left, right)

    assert divergence.common_prefix == 1
    assert divergence.left is None
    assert divergence.right == 'model_step summary="retry" payload={"attempt":1}'
    assert divergence.after_injection is None


def test_tool_finish_value_only_change_is_a_visible_divergence() -> None:
    trial_spec = spec("fragile_agent")
    common = {
        "tool": "fetch",
        "call_id": "c-0001",
        "ok": True,
        "error_kind": None,
        "injected_by": None,
    }
    left_event = Event(
        trial_id="left",
        seq=2,
        kind="tool_finish",
        payload={**common, "value": {"answer": 42}},
    )
    right_event = Event(
        trial_id="right",
        seq=9,
        kind="tool_finish",
        payload={**common, "call_id": "c-9999", "value": None},
    )

    divergence = first_divergence(
        _envelope(trial_spec, (left_event,)),
        _envelope(trial_spec, (right_event,)),
    )

    assert divergence.common_prefix == 0
    assert divergence.left is not None and "value#" in divergence.left
    assert divergence.right is not None and "value#" in divergence.right
    assert divergence.left != divergence.right
