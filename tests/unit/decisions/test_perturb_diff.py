from __future__ import annotations

import random
from dataclasses import dataclass
from typing import cast

import pytest
from pydantic import JsonValue

from arci.diff import step_signature
from arci.interfaces import Perturbation
from arci.perturb import build
from arci.schema import DECISION_TOOL, Bucket, Event, FaultSpec, ToolCall, ToolResult


def _call(tool: str = DECISION_TOOL, occurrence: int = 0) -> ToolCall:
    return ToolCall(call_id=f"c-{occurrence:04d}", tool=tool, occurrence=occurrence)


def _result(probabilities: dict[str, float]) -> ToolResult:
    winner = max(probabilities, key=probabilities.__getitem__)
    return ToolResult(
        call_id="c-0000",
        tool=DECISION_TOOL,
        ok=True,
        value=cast(
            JsonValue,
            {
                "status": 200,
                "headers": {},
                "body": {
                    "model": "jev-1.13.0",
                    "answers": {
                        "route": {
                            "type": "choice",
                            "choice": winner,
                            "probabilities": probabilities,
                            "confidence": 0.9,
                        },
                        "singleton": {
                            "type": "choice",
                            "choice": "only",
                            "probabilities": {"only": 1.0},
                            "confidence": 1.0,
                        },
                        "noul": {"type": "noul", "noul": 0.9},
                        "score": {
                            "type": "score",
                            "score": 0.8,
                            "legend": {"0": "low", "1": "high"},
                            "probabilities": {"0": 0.2, "1": 0.8},
                            "confidence": 0.6,
                        },
                    },
                    "usage": {"input_tokens": 1, "output_tokens": 0},
                },
            },
        ),
    )


def _answers(result: ToolResult) -> dict[str, dict[str, object]]:
    value = cast(dict[str, object], result.value)
    body = cast(dict[str, object], value["body"])
    return cast(dict[str, dict[str, object]], body["answers"])


def test_low_confidence_mixes_choices_to_the_cap_without_mutating_input() -> None:
    original = _result({"a": 0.9, "b": 0.08, "c": 0.02})
    fault = build(
        FaultSpec(
            name="decision_low_confidence",
            bucket=Bucket.FALSIFY,
            tool=DECISION_TOOL,
            params={"confidence_max": 0.4},
        )
    )

    rewritten = fault.after(_call(), original, random.Random(0))
    before = _answers(original)
    after = _answers(rewritten)
    probabilities = cast(dict[str, float], after["route"]["probabilities"])

    assert rewritten.injected_by == "decision_low_confidence"
    assert before["route"]["probabilities"] == {"a": 0.9, "b": 0.08, "c": 0.02}
    assert after["route"]["choice"] == "a"
    assert after["route"]["confidence"] == 0.4
    assert sum(probabilities.values()) == pytest.approx(1.0, abs=1e-12)
    assert (3 * max(probabilities.values()) - 1) / 2 == pytest.approx(0.4, abs=1e-12)
    assert sorted(probabilities, key=probabilities.__getitem__) == ["c", "b", "a"]
    assert after["singleton"] == before["singleton"]
    assert after["noul"] == before["noul"]
    assert after["score"] == before["score"]


@pytest.mark.parametrize(
    "probabilities,cap",
    [
        ({"a": 0.7, "b": 0.3}, 0.4),
        ({"a": 0.5, "b": 0.5}, 0.0),
    ],
)
def test_low_confidence_leaves_at_cap_and_ties_unchanged(
    probabilities: dict[str, float], cap: float
) -> None:
    original = _result(probabilities)
    fault = build(
        FaultSpec(
            name="decision_low_confidence",
            bucket=Bucket.FALSIFY,
            tool=DECISION_TOOL,
            params={"confidence_max": cap},
        )
    )

    rewritten = fault.after(_call(), original, random.Random(0))

    assert _answers(rewritten)["route"] == _answers(original)["route"]
    assert rewritten.injected_by == "decision_low_confidence"


def test_low_confidence_preserves_a_tied_maximum_when_flattening() -> None:
    original = _result({"a": 0.45, "b": 0.45, "c": 0.1})
    fault = build(
        FaultSpec(
            name="decision_low_confidence",
            bucket=Bucket.FALSIFY,
            tool=DECISION_TOOL,
            params={"confidence_max": 0.1},
        )
    )

    rewritten = fault.after(_call(), original, random.Random(0))
    route = _answers(rewritten)["route"]
    probabilities = cast(dict[str, float], route["probabilities"])

    assert route["choice"] == "a"
    assert probabilities["a"] == pytest.approx(probabilities["b"], abs=1e-12)
    assert probabilities["a"] > probabilities["c"]
    assert (3 * max(probabilities.values()) - 1) / 2 == pytest.approx(0.1, abs=1e-12)


def test_low_confidence_matches_only_its_selected_decision_occurrence() -> None:
    fault = build(
        FaultSpec(
            name="decision_low_confidence",
            bucket=Bucket.FALSIFY,
            tool=DECISION_TOOL,
            at_occurrence=1,
        )
    )
    result = _result({"a": 0.9, "b": 0.1})

    assert fault.after(_call(occurrence=0), result, random.Random(0)) is result
    assert fault.after(_call("fetch", 1), result, random.Random(0)) is result
    assert fault.after(_call(occurrence=1), result, random.Random(0)).injected_by == fault.name


def test_unavailable_applies_from_selected_occurrence_onward() -> None:
    fault = build(
        FaultSpec(
            name="decision_unavailable",
            bucket=Bucket.FALSIFY,
            tool=DECISION_TOOL,
            at_occurrence=1,
        )
    )

    assert fault.before(_call(occurrence=0), random.Random(0)) is None
    assert fault.before(_call("fetch", 1), random.Random(0)) is None
    for occurrence in (1, 2):
        injected = fault.before(_call(occurrence=occurrence), random.Random(0))
        assert injected is not None
        assert injected.ok is False and injected.error_kind == "http_529"
        assert injected.injected_by == "decision_unavailable"
        assert injected.value == {
            "status": 529,
            "headers": {},
            "body": {"detail": "arci injected unavailable"},
        }


@dataclass
class _Passthrough:
    name: str = "custom"
    bucket: Bucket = Bucket.BENIGN

    def before(self, call: ToolCall, rng: random.Random) -> ToolResult | None:
        del rng
        return ToolResult(call_id=call.call_id, tool=call.tool, ok=False)

    def after(self, call: ToolCall, result: ToolResult, rng: random.Random) -> ToolResult:
        del call, rng
        return result.model_copy(update={"injected_by": self.name})


def custom_factory(fault: FaultSpec) -> Perturbation:
    del fault
    return _Passthrough()


@pytest.mark.parametrize("name", ["tool_timeout", "tool_error_once", "empty_result"])
def test_registered_generic_perturbations_never_see_decisions(name: str) -> None:
    fault = build(FaultSpec(name=name, bucket=Bucket.BENIGN))
    call = _call()
    result = _result({"a": 0.9, "b": 0.1})

    assert fault.before(call, random.Random(0)) is None
    assert fault.after(call, result, random.Random(0)) is result


def test_referenced_generic_perturbation_never_sees_decisions() -> None:
    fault = build(FaultSpec(name=f"{__name__}:custom_factory", bucket=Bucket.BENIGN))
    result = _result({"a": 0.9, "b": 0.1})

    assert fault.before(_call(), random.Random(0)) is None
    assert fault.after(_call(), result, random.Random(0)) is result
    assert fault.before(_call("fetch"), random.Random(0)) is not None


def test_decision_signatures_digest_arguments_and_show_status() -> None:
    start = Event(
        trial_id="trial",
        seq=0,
        kind="tool_start",
        payload={
            "tool": DECISION_TOOL,
            "call_id": "c-0002",
            "occurrence": 2,
            "arguments": {"state": {"secret": "STATE-MARKER"}, "questions": {}},
        },
    )
    changed = start.model_copy(
        update={
            "payload": {
                **start.payload,
                "arguments": {"state": {"secret": "OTHER"}, "questions": {}},
            }
        }
    )
    finish = Event(
        trial_id="trial",
        seq=1,
        kind="tool_finish",
        payload={
            "tool": DECISION_TOOL,
            "call_id": "c-0002",
            "ok": True,
            "value": {"status": 200, "headers": {}, "body": {}},
            "error_kind": None,
            "injected_by": None,
        },
    )

    signature = step_signature(start)
    assert signature.startswith('tool_start tool="decision:systemone" occurrence=2 arguments#')
    assert "STATE-MARKER" not in signature and "state" not in signature
    assert signature != step_signature(changed)
    assert "status=200" in step_signature(finish)


def test_non_decision_signature_keeps_readable_arguments() -> None:
    event = Event(
        trial_id="trial",
        seq=0,
        kind="tool_start",
        payload={"tool": "fetch", "occurrence": 3, "arguments": {"key": "value"}},
    )

    assert step_signature(event) == 'tool_start tool="fetch" arguments={"key":"value"}'
