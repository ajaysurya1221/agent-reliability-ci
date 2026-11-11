"""Public API capabilities and edge cases of the optional adapter boundary."""

from __future__ import annotations

import importlib.util
import os
import random
import subprocess
import sys
from collections.abc import Sequence
from typing import Any

import pytest

if importlib.util.find_spec("langchain") is None:
    if os.environ.get("ARCI_REQUIRE_ADAPTERS") == "1":
        raise ImportError("ARCI_REQUIRE_ADAPTERS=1 requires LangChain")
    pytest.skip("optional LangChain extra is absent", allow_module_level=True)

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool, StructuredTool
from pydantic import JsonValue

from arci.adapters.langchain import make_adapter
from arci.hashing import hash_record
from arci.interfaces import ToolFault
from arci.schema import Bucket, Budgets, RecordedCall, ToolCall, ToolMode, ToolResult
from arci.toolbox import HarnessError, ToolBox
from tests.unit.adapters.fixtures import Input, call_message, model


@pytest.mark.parametrize(
    ("module", "name", "method"),
    [
        ("langchain.agents.middleware", "ToolCallRequest", "override"),
        ("langchain_core.tools", "BaseTool", "run"),
        ("langchain_core.tools", "BaseTool", "get_input_schema"),
    ],
)
def test_missing_public_capability_is_named(module: str, name: str, method: str) -> None:
    """Requirement 5: absent required public methods fail at import with one named line."""
    code = f"""
import importlib
owner = getattr(importlib.import_module({module!r}), {name!r})
setattr(owner, {method!r}, None)
try:
    import arci.adapters.langchain
except ImportError as exc:
    print(str(exc))
else:
    raise AssertionError('adapter imported with missing public capability')
"""
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == f"LangChain adapter requires public {name}.{method}"


def config_tool(key: str, config: RunnableConfig) -> str:
    del config
    return key


def callback_tool(key: str, callbacks: Any = None) -> str:
    del callbacks
    return key


async def async_function(key: str) -> str:
    return key


@pytest.mark.parametrize("kind", ["config", "callbacks", "async"])
@pytest.mark.parametrize("replay", [False, True])
def test_additional_injected_and_async_shapes(kind: str, replay: bool) -> None:
    """Requirements 3, 6, 9: framework-injected configuration and async func are rejected."""
    tool = StructuredTool(
        name="lookup",
        description="Lookup.",
        args_schema=Input,
        func={"config": config_tool, "callbacks": callback_tool, "async": async_function}[kind],
    )
    adapter = make_adapter(lambda _task, _seed: [tool], lambda: {}, lambda: {})
    reason = "async invocation" if kind == "async" else "injected tool arguments"
    if replay:
        box = ToolBox({}, Budgets(), lambda _kind, _payload: None, mode=ToolMode.REPLAY)
        with pytest.raises(HarnessError, match=reason):
            adapter.baseline({"input": "x"}, box, random.Random())
        assert box.harness_fault
    else:
        with pytest.raises(HarnessError, match=reason):
            adapter.toolset({"input": "x"}, 0)


def test_factory_errors_are_harness_failures_live_and_replay() -> None:
    """Requirement 6: replay factory errors stay harness failures."""

    def broken(_task: dict[str, JsonValue], _seed: int) -> Sequence[BaseTool]:
        raise ValueError("factory failed")

    adapter = make_adapter(broken, lambda: {}, lambda: {})
    with pytest.raises(HarnessError, match="tool factory failed"):
        adapter.toolset({"input": "x"}, 0)
    box = ToolBox({}, Budgets(), lambda _kind, _payload: None, mode=ToolMode.REPLAY)
    with pytest.raises(HarnessError, match="tool factory failed"):
        adapter.baseline({"input": "x"}, box, random.Random())
    assert box.harness_fault


@pytest.mark.parametrize("value", [(1, 2), {1: "not a JSON key"}])
def test_non_json_result_shapes_rejected_before_recording(value: Any) -> None:
    """Requirements 3, 6: JSON encodability alone must not allow invalid JsonValue results."""

    def body(key: str) -> Any:
        del key
        return value

    tool = StructuredTool.from_function(body, name="lookup", description="Lookup.")

    def spec() -> dict[str, Any]:
        return {"model": model(call_message({"key": "x"}))}

    adapter = make_adapter(lambda _task, _seed: [tool], spec, spec)
    world = adapter.toolset({"input": "x"}, 0)
    box = ToolBox(world.tools, Budgets(), lambda _kind, _payload: None)
    with pytest.raises(HarnessError, match="non-JSON tool result"):
        adapter.baseline({"input": "x"}, box, random.Random())
    assert box.harness_fault
    assert not box.recording


class UnmarkedFault:
    name = "unmarked"
    bucket = Bucket.FALSIFY

    def __init__(self, kind: str) -> None:
        self.kind = kind

    def before(self, call: ToolCall, rng: random.Random) -> ToolResult:
        del rng
        return ToolResult(
            call_id=call.call_id,
            tool=call.tool,
            ok=False,
            error_kind=self.kind,
            error_detail="injected",
        )

    def after(self, call: ToolCall, result: ToolResult, rng: random.Random) -> ToolResult:
        del call, rng
        return result


@pytest.mark.parametrize("kind", ["error", "custom"])
def test_unmarked_live_injected_fault_remains_tool_fault(kind: str) -> None:
    """Requirement 4: live uncaptured failures stay injected without an attribution marker."""

    def body(key: str) -> str:
        return key

    tool = StructuredTool.from_function(body, name="lookup", description="Lookup.")

    def spec() -> dict[str, Any]:
        return {"model": model(call_message({"key": "x"}), AIMessage(content="done"))}

    adapter = make_adapter(lambda _task, _seed: [tool], spec, spec)
    world = adapter.toolset({"input": "x"}, 0)
    box = ToolBox(
        world.tools, Budgets(), lambda _kind, _payload: None, perturbations=[UnmarkedFault(kind)]
    )
    with pytest.raises(ToolFault) as caught:
        adapter.baseline({"input": "x"}, box, random.Random())
    assert caught.value.kind == kind
    assert not box.harness_fault
    if kind == "custom":
        replay = ToolBox(
            {},
            Budgets(),
            lambda _kind, _payload: None,
            mode=ToolMode.REPLAY,
            recording=box.recording,
        )
        with pytest.raises(ToolFault) as caught:
            adapter.baseline({"input": "x"}, replay, random.Random())
        assert caught.value.kind == kind
        assert not replay.harness_fault


@pytest.mark.parametrize("wrong_exception", [False, True])
@pytest.mark.parametrize("replay", [False, True])
def test_constructor_must_return_requested_exception(wrong_exception: bool, replay: bool) -> None:
    """Requirements 4, 6: malformed exception constructors must produce harness ERROR."""

    class BadConstructor(Exception):
        def __init__(self, message: str) -> None:
            super().__init__(message)

        def __new__(cls, message: str) -> Any:
            del cls, message
            return ValueError("wrong class") if wrong_exception else object()

    def body(key: str) -> str:
        return key

    tool = StructuredTool.from_function(body, name="lookup", description="Lookup.")

    def spec() -> dict[str, Any]:
        return {"model": model(call_message({"key": "x"}))}

    adapter = make_adapter(
        lambda _task, _seed: [tool],
        spec,
        spec,
        fault_exceptions={"custom": BadConstructor},
        error_types=[BadConstructor],
    )
    if replay:
        recorded = RecordedCall(
            tool="lookup",
            arguments_sha256=hash_record({"key": "x"}),
            occurrence=0,
            result=ToolResult(
                call_id="c-0000",
                tool="lookup",
                ok=False,
                error_kind="error",
                error_detail="BadConstructor: problem",
            ),
        )
        box = ToolBox(
            {}, Budgets(), lambda _kind, _payload: None, mode=ToolMode.REPLAY, recording=[recorded]
        )
        reason = "unreconstructable tool error"
    else:
        world = adapter.toolset({"input": "x"}, 0)
        box = ToolBox(
            world.tools,
            Budgets(),
            lambda _kind, _payload: None,
            perturbations=[UnmarkedFault("custom")],
        )
        reason = "unconstructable fault exception"
    with pytest.raises(HarnessError, match=reason):
        adapter.baseline({"input": "x"}, box, random.Random())
    assert box.harness_fault


@pytest.mark.parametrize("replay", [False, True])
def test_unresolved_tool_annotations_live_and_replay(replay: bool) -> None:
    """Requirements 6, 9: unresolved annotations produce the same fixed rejection."""

    def body(key: str) -> str:
        raise AssertionError("rejected tool body must not execute")

    tool = StructuredTool(name="lookup", description="Lookup.", args_schema=Input, func=body)
    body.__annotations__["key"] = "MissingAdapterAnnotation"
    adapter = make_adapter(lambda _task, _seed: [tool], lambda: {}, lambda: {})
    detail = "LangChain adapter unsupported: unresolved tool annotations"
    if replay:
        box = ToolBox({}, Budgets(), lambda _kind, _payload: None, mode=ToolMode.REPLAY)
        with pytest.raises(HarnessError, match=detail):
            adapter.baseline({"input": "x"}, box, random.Random())
        assert box.harness_fault
        assert box.tool_calls == box.model_steps == 0
    else:
        with pytest.raises(HarnessError, match=detail):
            adapter.toolset({"input": "x"}, 0)


@pytest.mark.parametrize("task", [{}, {"input": 123}])
@pytest.mark.parametrize("replay", [False, True])
def test_default_input_requires_string_live_and_replay(
    task: dict[str, JsonValue], replay: bool
) -> None:
    """Requirements 6, 8, 9: missing or nonstring input names the hook before model execution."""
    scripted = model(AIMessage(content="unused"))

    def spec() -> dict[str, Any]:
        return {"model": scripted}

    adapter = make_adapter(lambda _task, _seed: [], spec, spec)
    if replay:
        box = ToolBox({}, Budgets(), lambda _kind, _payload: None, mode=ToolMode.REPLAY)
    else:
        world = adapter.toolset(task, 0)
        box = ToolBox(world.tools, Budgets(), lambda _kind, _payload: None)
    detail = "LangChain adapter unsupported: task_to_input requires a string input"
    with pytest.raises(HarnessError, match=detail):
        adapter.baseline(task, box, random.Random())
    assert box.harness_fault
    assert box.tool_calls == box.model_steps == scripted.attempts == 0
