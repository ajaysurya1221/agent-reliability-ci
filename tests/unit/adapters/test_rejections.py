"""Explicit unsupported shapes must never become catchable ordinary tool failures."""

from __future__ import annotations

import ast
import importlib.util
import inspect
import os
import random
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Annotated, Any

import pytest

if importlib.util.find_spec("langchain") is None:
    if os.environ.get("ARCI_REQUIRE_ADAPTERS") == "1":
        raise ImportError("ARCI_REQUIRE_ADAPTERS=1 requires LangChain")
    pytest.skip("optional LangChain extra is absent", allow_module_level=True)

from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware
from langchain.agents.structured_output import ProviderStrategy, ToolStrategy
from langchain.tools import ToolRuntime
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import BaseTool, InjectedToolArg, InjectedToolCallId, StructuredTool
from langgraph.prebuilt import InjectedState, InjectedStore
from langgraph.types import Command

from arci.adapters import langchain as implementation
from arci.adapters.langchain import make_adapter
from arci.schema import Budgets, ToolMode
from arci.toolbox import HarnessError, ToolBox
from tests.unit.adapters.fixtures import Input, call_message, model
from tests.unit.adapters.test_core import Answer, boundary


class CustomInjected(InjectedToolArg):
    pass


def state_tool(value: Annotated[dict[str, Any], InjectedState]) -> str:
    return str(value)


def store_tool(value: Annotated[Any, InjectedStore()]) -> str:
    return str(value)


def call_id_tool(value: Annotated[str, InjectedToolCallId]) -> str:
    return value


def custom_tool(value: Annotated[str, CustomInjected]) -> str:
    return value


def runtime_tool(runtime: ToolRuntime[Any, Any]) -> str:
    return str(runtime)


def named_runtime_tool(runtime: str) -> str:
    return runtime


def typed_runtime_tool(value: ToolRuntime[Any, Any]) -> str:
    return str(value)


async def coroutine_tool(key: str) -> str:
    return key


async def injected_coroutine(value: Annotated[str, CustomInjected]) -> str:
    return value


def plain_tool(key: str = "answer") -> str:
    return key


def invalid_tools(kind: str) -> Sequence[BaseTool]:
    tool = StructuredTool.from_function(plain_tool, name="lookup", description="Lookup.")
    if kind == "duplicate tool names":
        return [tool, tool]
    if kind == "tool artifacts":
        tool.response_format = "content_and_artifact"
    elif kind == "return_direct":
        tool.return_direct = True
    elif kind == "handle_tool_error":
        tool.handle_tool_error = True
    elif kind == "handle_validation_error":
        tool.handle_validation_error = True
    elif kind == "async invocation":
        tool = StructuredTool.from_function(
            coroutine=coroutine_tool, name="lookup", description="Lookup."
        )
    elif kind.startswith("injected:"):
        functions: dict[str, Callable[..., Any]] = {
            "state": state_tool,
            "store": store_tool,
            "call_id": call_id_tool,
            "custom": custom_tool,
            "runtime": runtime_tool,
            "named_runtime": named_runtime_tool,
            "typed_runtime": typed_runtime_tool,
        }
        tool = StructuredTool.from_function(
            functions[kind.partition(":")[2]], name="lookup", description="Injected."
        )
    elif kind == "injected coroutine":
        tool = StructuredTool.from_function(
            plain_tool,
            coroutine=injected_coroutine,
            args_schema=Input,
            name="lookup",
            description="Injected coroutine.",
        )
    return [tool]


REGISTRATION_REJECTIONS = [
    "duplicate tool names",
    "tool artifacts",
    "return_direct",
    "handle_tool_error",
    "handle_validation_error",
    "async invocation",
    "injected:state",
    "injected:store",
    "injected:call_id",
    "injected:custom",
    "injected:runtime",
    "injected:named_runtime",
    "injected:typed_runtime",
    "injected coroutine",
]


@pytest.mark.parametrize("reason", REGISTRATION_REJECTIONS)
@pytest.mark.parametrize("replay_mode", [False, True])
def test_tool_registration_rejection_live_and_replay(reason: str, replay_mode: bool) -> None:
    """Requirements 3, 6, 9: unsupported tools are fatal in live factory and replay setup."""

    def spec() -> dict[str, Any]:
        return {"model": model(AIMessage(content="done"))}

    adapter = make_adapter(lambda _task, _seed: invalid_tools(reason), spec, spec)
    expected = "injected tool arguments" if reason.startswith("injected") else reason
    detail = f"LangChain adapter unsupported: {expected}"
    if not replay_mode:
        with pytest.raises(HarnessError, match=detail) as captured:
            adapter.toolset({"input": "x"}, 7)
        assert not isinstance(captured.value, Exception)
    else:
        box = ToolBox({}, Budgets(), lambda _kind, _payload: None, mode=ToolMode.REPLAY)
        with pytest.raises(HarnessError, match=detail):
            adapter.baseline({"input": "x"}, box, random.Random(7))
        assert box.harness_fault


DISALLOWED_KEYS = sorted(
    set(inspect.signature(create_agent).parameters)
    - {"model", "system_prompt", "middleware", "response_format", "name"}
)


@pytest.mark.parametrize("key", [*DISALLOWED_KEYS, "unknown_option"])
@pytest.mark.parametrize("replay_mode", [False, True])
def test_every_disallowed_create_agent_key_is_named(key: str, replay_mode: bool) -> None:
    """Requirement 1: users cannot provide tools, graph state, persistence, or unknown keys."""

    def spec() -> dict[str, Any]:
        return {"model": model(AIMessage(content="done")), key: None}

    adapter = make_adapter(lambda _task, _seed: [], spec, spec)
    _, box, _ = boundary(adapter, recording=() if replay_mode else None)
    with pytest.raises(
        HarnessError, match=f"LangChain adapter unsupported: create_agent key {key}"
    ):
        adapter.baseline({"input": "x"}, box, random.Random(7))
    assert box.harness_fault


@pytest.mark.parametrize("replay_mode", [False, True])
def test_middleware_owned_tools_are_rejected(replay_mode: bool) -> None:
    """Requirements 1, 6: middleware cannot add tools that evade the boundary."""

    class OwnTools(AgentMiddleware[Any, Any, Any]):
        def __init__(self) -> None:
            self.tools = [StructuredTool.from_function(plain_tool, description="Own tool.")]

    def spec() -> dict[str, Any]:
        return {"model": model(AIMessage(content="done")), "middleware": [OwnTools()]}

    adapter = make_adapter(lambda _task, _seed: [], spec, spec)
    _, box, _ = boundary(adapter, recording=() if replay_mode else None)
    with pytest.raises(HarnessError, match="LangChain adapter unsupported: middleware-owned tools"):
        adapter.baseline({"input": "x"}, box, random.Random(7))
    assert box.harness_fault


@pytest.mark.parametrize("replay_mode", [False, True])
def test_callable_response_format_handler_rejected(replay_mode: bool) -> None:
    """Requirement 6: arbitrary response recovery stays outside infrastructure classification."""

    def spec() -> dict[str, Any]:
        return {
            "model": model(AIMessage(content="done")),
            "response_format": ToolStrategy(Answer, handle_errors=lambda _error: "retry"),
        }

    adapter = make_adapter(lambda _task, _seed: [], spec, spec)
    _, box, _ = boundary(adapter, recording=() if replay_mode else None)
    with pytest.raises(HarnessError, match="callable response_format handle_errors"):
        adapter.baseline({"input": "x"}, box, random.Random(7))
    assert box.harness_fault


@pytest.mark.parametrize("handler", [True, False, "retry", ValueError, (ValueError, TypeError)])
def test_non_callable_response_error_strategies_are_supported(handler: Any) -> None:
    def spec() -> dict[str, Any]:
        return {
            "model": model(call_message({"answer": "ok"}, name="Answer")),
            "response_format": ToolStrategy(Answer, handle_errors=handler),
        }

    adapter = make_adapter(lambda _task, _seed: [], spec, spec)
    world, box, _ = boundary(adapter)
    adapter.baseline({"input": "x"}, box, random.Random(7))
    assert world.snapshot()["structured_response"] == {"answer": "ok"}


@pytest.mark.parametrize("provider_strategy", [False, True])
@pytest.mark.parametrize("replay_mode", [False, True])
def test_non_ai_model_message_is_rejected_before_output_processing(
    provider_strategy: bool, replay_mode: bool
) -> None:
    """Requirements 3, 6: non-AI results cannot masquerade as output parsing failures."""

    def spec() -> dict[str, Any]:
        result: dict[str, Any] = {"model": model(HumanMessage(content="wrong role"))}
        if provider_strategy:
            result["response_format"] = ProviderStrategy(Answer)
        return result

    adapter = make_adapter(lambda _task, _seed: [], spec, spec)
    _, box, _ = boundary(adapter, recording=() if replay_mode else None)
    with pytest.raises(HarnessError, match="LangChain adapter unsupported: non-AI model response"):
        adapter.baseline({"input": "x"}, box, random.Random(7))
    assert box.harness_fault


@pytest.mark.parametrize(
    "value, reason",
    [
        (Command(update={}), "Command result"),
        (object(), "non-JSON tool result"),
        ((1, 2), "non-JSON tool result"),
        ({1: "value"}, "non-JSON tool result"),
        (float("inf"), "non-JSON tool result"),
    ],
)
def test_runtime_result_rejection_is_not_retryable(value: Any, reason: str) -> None:
    """Requirements 3, 6: tool-body rejections set the latch before Exception handlers."""
    calls: list[int] = []
    caught: list[Exception] = []

    def lookup(key: str) -> Any:
        del key
        calls.append(1)
        return value

    class Catch(AgentMiddleware[Any, Any, Any]):
        def wrap_tool_call(self, request: Any, handler: Callable[[Any], Any]) -> Any:
            try:
                return handler(request)
            except Exception as exc:
                caught.append(exc)
                raise

    def spec() -> dict[str, Any]:
        return {"model": model(call_message({"key": "x"})), "middleware": [Catch()]}

    adapter = make_adapter(
        lambda _task, _seed: [StructuredTool.from_function(lookup, description="Lookup.")],
        spec,
        spec,
    )
    _, box, _ = boundary(adapter)
    with pytest.raises(HarnessError, match=f"LangChain adapter unsupported: {reason}"):
        adapter.baseline({"input": "x"}, box, random.Random(7))
    assert box.harness_fault
    assert calls == [1] and caught == []
    assert box.recording == ()


@pytest.mark.parametrize("key", ["tool", "self"])
@pytest.mark.parametrize("replay_mode", [False, True])
def test_reserved_boundary_argument_names_are_explicit_rejections(
    key: str, replay_mode: bool
) -> None:
    def body(**kwargs: Any) -> str:
        return str(kwargs)

    def spec() -> dict[str, Any]:
        return {"model": model(call_message({key: "x"}))}

    tool = StructuredTool(
        name="lookup",
        description="Lookup.",
        args_schema={"type": "object", "properties": {key: {"type": "string"}}},
        func=body,
    )
    adapter = make_adapter(lambda _task, _seed: [tool], spec, spec)
    _, box, _ = boundary(adapter, recording=() if replay_mode else None)
    with pytest.raises(HarnessError, match="reserved boundary argument name"):
        adapter.baseline({"input": "x"}, box, random.Random(7))
    assert box.harness_fault and box.tool_calls == 0


def test_only_public_framework_imports_are_used() -> None:
    """Requirement 5: the runtime never imports private or unexported framework helpers."""
    tree = ast.parse(Path(implementation.__file__).read_text())
    framework = ("langchain", "langgraph", "langsmith", "httpx")
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(framework):
            assert node.module is not None
            assert not any(part.startswith("_") for part in node.module.split("."))
            module = importlib.import_module(node.module)
            exported = getattr(module, "__all__", None)
            for name in node.names:
                assert not name.name.startswith("_")
                assert hasattr(module, name.name)
                if exported is not None:
                    assert name.name in exported


@pytest.mark.parametrize("replay_mode", [False, True])
def test_unconstructable_fault_mapping_latches_harness(replay_mode: bool) -> None:
    class NeedsBoth(Exception):
        def __init__(self, first: str, second: str) -> None:
            super().__init__(first, second)

    tool = StructuredTool.from_function(plain_tool, name="lookup", description="Lookup.")

    def spec() -> dict[str, Any]:
        return {"model": model(call_message({"key": "x"}))}

    adapter = make_adapter(
        lambda _task, _seed: [tool],
        spec,
        spec,
        fault_exceptions={"timeout": NeedsBoth},
    )
    _, live, _ = boundary(adapter, fault="tool_timeout")
    with pytest.raises(HarnessError, match="unconstructable fault exception"):
        adapter.baseline({"input": "x"}, live, random.Random(7))
    assert live.harness_fault
    if replay_mode:
        _, replayed, _ = boundary(adapter, recording=live.recording)
        with pytest.raises(HarnessError, match="unconstructable fault exception"):
            adapter.baseline({"input": "x"}, replayed, random.Random(7))
        assert replayed.harness_fault
