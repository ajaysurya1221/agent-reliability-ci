"""Restricted replay reconstruction and stressed serial ordering."""

from __future__ import annotations

import importlib.util
import os
import random
from collections.abc import Callable
from typing import Any

import pytest

if importlib.util.find_spec("langchain") is None:
    if os.environ.get("ARCI_REQUIRE_ADAPTERS") == "1":
        raise ImportError("ARCI_REQUIRE_ADAPTERS=1 requires LangChain")
    pytest.skip("optional LangChain extra is absent", allow_module_level=True)

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import StructuredTool
from pydantic import JsonValue

from arci.adapters.langchain import make_adapter
from arci.hashing import canonical_json
from arci.schema import Budgets
from arci.toolbox import HarnessError, format_diagnostic
from tests.unit.adapters.fixtures import call_message, model
from tests.unit.adapters.test_core import boundary


class CustomError(Exception):
    pass


class NeedsTwoArguments(Exception):
    def __init__(self, first: str, second: str) -> None:
        super().__init__(first, second)


def test_replay_restores_declared_exception_type_without_running_body() -> None:
    """Requirement 4: user-declared type reconstruction preserves typed retry behavior."""
    calls: list[str] = []
    observed: list[Exception] = []

    def lookup(key: str) -> str:
        calls.append(key)
        if len(calls) == 1:
            raise CustomError("failure at 123 /tmp/path")
        return key

    class Retry(AgentMiddleware[Any, Any, Any]):
        def wrap_tool_call(self, request: Any, handler: Callable[[Any], Any]) -> Any:
            try:
                return handler(request)
            except CustomError as exc:
                observed.append(exc)
                return handler(request)

    def spec() -> dict[str, Any]:
        return {
            "model": model(call_message({"key": "x"}), AIMessage(content="done")),
            "middleware": [Retry()],
        }

    tool = StructuredTool.from_function(lookup, description="Lookup.")
    adapter = make_adapter(lambda _task, _seed: [tool], spec, spec, error_types=[CustomError])
    _, live, _ = boundary(adapter)
    adapter.baseline({"input": "x"}, live, random.Random(0))
    assert calls == ["x", "x"]
    _, replayed, _ = boundary(adapter, recording=live.recording)
    adapter.baseline({"input": "x"}, replayed, random.Random(0))
    replayed.assert_replay_consumed()
    assert calls == ["x", "x"]
    assert len(observed) == 2 and all(type(exc) is CustomError for exc in observed)
    assert str(observed[0]) != str(observed[1])  # recorded diagnostics are scrubbed


@pytest.mark.parametrize("case", ["unknown", "ambiguous", "constructor"])
def test_replay_unrecoverable_error_types_latch_harness(case: str) -> None:
    """Requirements 4, 6: unknown, ambiguous, or unconstructable error types are ERROR."""
    if case == "constructor":
        error: Exception = NeedsTwoArguments("first", "second")
        declared: list[type[Exception]] = [NeedsTwoArguments]
    elif case == "ambiguous":
        shadow = type("ValueError", (Exception,), {})
        error = ValueError("failure")
        declared = [shadow, type("ValueError", (Exception,), {})]
    else:
        error = CustomError("failure")
        declared = []

    def lookup(key: str) -> str:
        del key
        raise error

    def spec() -> dict[str, Any]:
        return {"model": model(call_message({"key": "x"}))}

    adapter = make_adapter(
        lambda _task, _seed: [StructuredTool.from_function(lookup, description="Lookup.")],
        spec,
        spec,
        error_types=declared,
    )
    _, live, _ = boundary(adapter)
    with pytest.raises(type(error)) as caught:
        adapter.baseline({"input": "x"}, live, random.Random(0))
    assert caught.value is error
    assert not live.harness_fault
    _, replayed, _ = boundary(adapter, recording=live.recording)
    with pytest.raises(HarnessError, match="unreconstructable tool error"):
        adapter.baseline({"input": "x"}, replayed, random.Random(0))
    assert replayed.harness_fault


def test_replay_same_builtin_error_has_same_failure_diagnostic() -> None:
    def lookup(key: str) -> str:
        del key
        raise ValueError("failure at 123 /tmp/path")

    def spec() -> dict[str, Any]:
        return {"model": model(call_message({"key": "x"}))}

    adapter = make_adapter(
        lambda _task, _seed: [StructuredTool.from_function(lookup, description="Lookup.")],
        spec,
        spec,
    )
    _, live, _ = boundary(adapter)
    with pytest.raises(ValueError) as first:
        adapter.baseline({"input": "x"}, live, random.Random(0))
    _, replayed, _ = boundary(adapter, recording=live.recording)
    with pytest.raises(ValueError) as second:
        adapter.baseline({"input": "x"}, replayed, random.Random(0))
    assert format_diagnostic(first.value) == format_diagnostic(second.value)


def test_replay_lost_errno_changes_policy_branch_without_changing_calls() -> None:
    """Requirement 4 stated limit: errno-dependent policy takes another branch in replay."""
    seen: list[str] = []
    bodies: list[int] = []

    def lookup(key: str) -> str:
        del key
        bodies.append(1)
        raise OSError(5, "disk unavailable")

    class Catch(AgentMiddleware[Any, Any, Any]):
        def wrap_tool_call(self, request: Any, handler: Callable[[Any], Any]) -> Any:
            try:
                return handler(request)
            except OSError as exc:
                branch = "live errno" if exc.errno == 5 else "replay lost errno"
                seen.append(branch)
                return ToolMessage(content=branch, tool_call_id=request.tool_call["id"])

    def spec() -> dict[str, Any]:
        return {
            "model": model(call_message({"key": "x"}), AIMessage(content="done")),
            "middleware": [Catch()],
        }

    adapter = make_adapter(
        lambda _task, _seed: [StructuredTool.from_function(lookup, description="Lookup.")],
        spec,
        spec,
    )
    _, live, _ = boundary(adapter)
    adapter.baseline({"input": "x"}, live, random.Random(0))
    _, replayed, _ = boundary(adapter, recording=live.recording)
    adapter.baseline({"input": "x"}, replayed, random.Random(0))
    replayed.assert_replay_consumed()
    assert seen == ["live errno", "replay lost errno"]
    assert bodies == [1]
    assert live.tool_calls == replayed.tool_calls == 1


def _fatal_multicall_once(failure_index: int) -> tuple[bytes, str]:
    bodies: list[str] = []

    def lookup(key: str) -> str:
        bodies.append(key)
        if key == str(failure_index):
            raise ValueError(f"failure at index {failure_index}")
        return key

    def spec() -> dict[str, Any]:
        return {"model": model(call_message(*({"key": str(i)} for i in range(40))))}

    adapter = make_adapter(
        lambda _task, _seed: [StructuredTool.from_function(lookup, description="Lookup.")],
        spec,
        spec,
    )
    _, box, events = boundary(adapter, budgets=Budgets(max_tool_calls=100))
    with pytest.raises(ValueError) as caught:
        adapter.baseline({"input": "x"}, box, random.Random(0))
    assert bodies == [str(index) for index in range(failure_index + 1)]
    assert box.tool_calls == failure_index + 1
    payload: list[JsonValue] = [{"kind": kind, "payload": data} for kind, data in events]
    return canonical_json(payload), format_diagnostic(caught.value)


@pytest.mark.parametrize("failure_index", [0, 20])
def test_thousand_fatal_multicall_repetitions(failure_index: int) -> None:
    """Requirements 2, 9: 1,000 runs per position, 40 calls exceed the default 32-worker cap."""
    # CPython's default thread-pool size is min(32, cpu_count + 4). This exercises
    # queued siblings as well as running ones, without altering LangChain internals.
    first = _fatal_multicall_once(failure_index)
    for _ in range(999):
        assert _fatal_multicall_once(failure_index) == first
