from __future__ import annotations

from arci.diff import first_divergence, render_divergence, step_signature
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

    boundary = first_divergence(left, right)
    divergence = first_divergence(left, right, mode="all")

    assert boundary.common_prefix == len(left.events)
    assert boundary.left is None and boundary.right is None
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


def _annotation_mismatch_around_shared_fault() -> tuple[TrialEnvelope, TrialEnvelope]:
    trial_spec = spec("fragile_agent")
    start = Event(trial_id="trial", seq=0, kind="trial_start", payload={})
    reserve_start = Event(
        trial_id="trial",
        seq=2,
        kind="tool_start",
        payload={"tool": "reserve", "call_id": "c-0000", "arguments": {"order": "7"}},
    )
    injected_finish = Event(
        trial_id="trial",
        seq=3,
        kind="tool_finish",
        payload={
            "tool": "reserve",
            "call_id": "c-0000",
            "ok": False,
            "value": None,
            "error_kind": "timeout",
            "injected_by": "tool_timeout",
        },
    )
    left = _envelope(
        trial_spec,
        (
            start,
            Event(
                trial_id="left",
                seq=1,
                kind="model_step",
                payload={"summary": "reserve_attempt", "attempt": 1},
            ),
            reserve_start,
            injected_finish,
            Event(
                trial_id="left",
                seq=4,
                kind="model_step",
                payload={"summary": "reserve_attempt", "attempt": 2},
            ),
            Event(
                trial_id="left",
                seq=5,
                kind="tool_start",
                payload={"tool": "reserve", "call_id": "c-0001", "arguments": {"order": "7"}},
            ),
        ),
    )
    right = _envelope(
        trial_spec,
        (
            start,
            Event(
                trial_id="right",
                seq=1,
                kind="model_step",
                payload={"summary": "reserve_once"},
            ),
            reserve_start,
            injected_finish,
            Event(
                trial_id="right",
                seq=4,
                kind="model_step",
                payload={"summary": "reserve_failed_continue"},
            ),
            Event(
                trial_id="right",
                seq=5,
                kind="model_step",
                payload={"summary": "explain_next_action"},
            ),
            Event(
                trial_id="right",
                seq=6,
                kind="tool_start",
                payload={"tool": "confirm", "call_id": "c-0001", "arguments": {"order": "7"}},
            ),
        ),
    )
    return left, right


def test_boundary_mode_ignores_annotation_differences_before_shared_fault() -> None:
    left, right = _annotation_mismatch_around_shared_fault()

    boundary = first_divergence(left, right)
    all_steps = first_divergence(left, right, mode="all")

    assert boundary.common_prefix == 5
    assert boundary.left is not None and 'tool="reserve"' in boundary.left
    assert boundary.right is not None and 'tool="confirm"' in boundary.right
    assert boundary.after_injection == "tool_timeout"
    assert all_steps.common_prefix == 1
    assert all_steps.left is not None and "reserve_attempt" in all_steps.left
    assert all_steps.right is not None and "reserve_once" in all_steps.right
    assert all_steps.after_injection is None


def test_identical_trials_use_full_event_coordinates_in_both_modes() -> None:
    left, _right = _annotation_mismatch_around_shared_fault()

    for mode in ("boundary", "all"):
        divergence = first_divergence(left, left, mode=mode)
        assert divergence.common_prefix == len(left.events)
        assert divergence.left is None and divergence.right is None


def test_render_marks_annotations_and_names_the_mode() -> None:
    left, right = _annotation_mismatch_around_shared_fault()
    divergence = first_divergence(left, right)

    rendered = render_divergence(left, right, divergence)

    assert rendered.startswith("Mode: boundary.\n")
    assert 'after injection "tool_timeout"' in rendered
    assert "[annotation]: model_step" in rendered
