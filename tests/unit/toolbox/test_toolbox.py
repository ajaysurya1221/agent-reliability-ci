from __future__ import annotations

from collections.abc import Callable

import pytest
from pydantic import JsonValue

from arci.hashing import hash_record
from arci.interfaces import BudgetExceeded, ReplayMiss, ToolFault
from arci.perturb import build
from arci.schema import (
    Bucket,
    Budgets,
    FaultSpec,
    RecordedCall,
    ToolMode,
    ToolResult,
)
from arci.toolbox import ToolBox, format_diagnostic


class _RaisingPerturbation:
    name = "broken"
    bucket = Bucket.FALSIFY

    def __init__(self, hook: str, error: BaseException) -> None:
        self.hook = hook
        self.error = error

    def before(self, call: object, rng: object) -> None:
        del call, rng
        if self.hook == "before":
            raise self.error

    def after(self, call: object, result: ToolResult, rng: object) -> ToolResult:
        del call, rng
        if self.hook == "after":
            raise self.error
        return result


class _UnprintableError(Exception):
    def __str__(self) -> str:
        raise RuntimeError("broken string")


def test_injected_fault_is_recorded_and_counts_toward_budget() -> None:
    events: list[tuple[str, dict[str, JsonValue]]] = []
    tools: dict[str, Callable[..., JsonValue]] = {"fetch": lambda: 42}
    fault = build(FaultSpec(name="tool_timeout", bucket=Bucket.FALSIFY, tool="fetch"))
    box = ToolBox(
        tools,
        Budgets(max_tool_calls=1),
        lambda kind, payload: events.append((kind, payload)),
        perturbations=(fault,),
    )

    with pytest.raises(ToolFault, match="timeout"):
        box.call("fetch")
    with pytest.raises(BudgetExceeded):
        box.call("fetch")

    assert [kind for kind, _ in events] == ["tool_start", "tool_finish"]
    assert box.recording[0].result.injected_by == "tool_timeout"


def test_replay_miss_latches_even_if_the_agent_catches_it() -> None:
    recorded = RecordedCall(
        tool="fetch",
        arguments_sha256=hash_record({"key": "answer"}),
        occurrence=0,
        result=ToolResult(call_id="c-0000", tool="fetch", ok=True, value=42),
    )
    box = ToolBox(
        {},
        Budgets(),
        lambda _kind, _payload: None,
        mode=ToolMode.REPLAY,
        recording=(recorded,),
    )

    with pytest.raises(ReplayMiss):
        box.call("fetch", key="different")
    assert box.replay_miss
    with pytest.raises(ReplayMiss):
        box.assert_replay_consumed()


def test_unconsumed_recording_is_rejected() -> None:
    recorded = RecordedCall(
        tool="fetch",
        arguments_sha256=hash_record({}),
        occurrence=0,
        result=ToolResult(call_id="c-0000", tool="fetch", ok=True, value=42),
    )
    box = ToolBox(
        {},
        Budgets(),
        lambda _kind, _payload: None,
        mode=ToolMode.REPLAY,
        recording=(recorded,),
    )
    with pytest.raises(ReplayMiss):
        box.assert_replay_consumed()


def test_empty_result_rewrites_only_the_selected_occurrence() -> None:
    fault = build(FaultSpec(name="empty_result", bucket=Bucket.BENIGN, tool="fetch"))
    box = ToolBox(
        {"fetch": lambda: 42},
        Budgets(),
        lambda _kind, _payload: None,
        perturbations=(fault,),
    )
    assert box.call("fetch") is None
    assert box.call("fetch") == 42


def test_budget_and_returned_values_are_latched_and_isolated() -> None:
    budget: list[str] = []
    emitted: list[dict[str, JsonValue]] = []
    original: dict[str, JsonValue] = {"nested": {"value": 42}}
    box = ToolBox(
        {"fetch": lambda: original},
        Budgets(max_tool_calls=1),
        lambda kind, payload: emitted.append(payload) if kind == "tool_finish" else None,
        latch_budget=budget.append,
    )

    returned = box.call("fetch")
    assert isinstance(returned, dict)
    returned["nested"] = None
    assert box.recording[0].result.value == {"nested": {"value": 42}}
    assert emitted[0]["value"] == {"nested": {"value": 42}}

    with pytest.raises(BudgetExceeded):
        box.call("fetch")
    assert budget == ["tool call budget exhausted"]


@pytest.mark.parametrize("hook", ["before", "after"])
@pytest.mark.parametrize("error", [ToolFault("error"), BudgetExceeded(), ReplayMiss()])
def test_injector_boundary_exceptions_latch_as_harness_fault(
    hook: str, error: BaseException
) -> None:
    harness: list[str] = []
    box = ToolBox(
        {"fetch": lambda: 42},
        Budgets(),
        lambda _kind, _payload: None,
        perturbations=(_RaisingPerturbation(hook, error),),
        latch_harness=harness.append,
    )

    with pytest.raises(type(error)):
        box.call("fetch")
    assert box.harness_fault
    assert len(harness) == 1


def test_diagnostic_formatter_handles_unprintable_and_non_utf8_text() -> None:
    assert format_diagnostic(_UnprintableError()) == "<unprintable _UnprintableError>"
    assert format_diagnostic("first\nsecond " + chr(0xD800)) == "first"
