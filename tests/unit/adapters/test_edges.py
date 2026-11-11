"""Adversarial control-flow probes for the synchronous public adapter."""

from __future__ import annotations

import asyncio
import importlib.util
import os
import random
import threading
from typing import Any, cast

import pytest

if importlib.util.find_spec("langchain") is None:
    if os.environ.get("ARCI_REQUIRE_ADAPTERS") == "1":
        raise ImportError("ARCI_REQUIRE_ADAPTERS=1 requires LangChain")
    pytest.skip("optional LangChain extra is absent", allow_module_level=True)

from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware, ToolCallRequest
from langchain.agents.structured_output import ToolStrategy
from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage, ToolMessage
from langchain_core.tools import StructuredTool
from pydantic import JsonValue

from arci.adapters import langchain as implementation
from arci.adapters.langchain import make_adapter
from arci.schema import Budgets, ToolMode
from arci.toolbox import HarnessError, ToolBox
from tests.unit.adapters.fixtures import call_message, model
from tests.unit.adapters.test_core import Answer, boundary


@pytest.mark.parametrize("replay_mode", [False, True])
def test_missing_model_is_explicit_harness_rejection(replay_mode: bool) -> None:
    adapter = make_adapter(lambda _task, _seed: [], lambda: {}, lambda: {})
    _, box, _ = boundary(adapter, recording=() if replay_mode else None)
    with pytest.raises(HarnessError, match="LangChain adapter unsupported: missing model"):
        adapter.baseline({"input": "x"}, box, random.Random(0))
    assert box.harness_fault


def test_boundary_requires_fail_harness_capability() -> None:
    class OldBoundary:
        def call(self, tool: str, **arguments: JsonValue) -> JsonValue:
            del tool, arguments
            raise AssertionError("must not execute")

        def note_model_step(self, summary: str, **payload: JsonValue) -> None:
            del summary, payload
            raise AssertionError("must not execute")

    adapter = make_adapter(lambda _task, _seed: [], lambda: {}, lambda: {})
    with pytest.raises(
        HarnessError, match="LangChain adapter unsupported: boundary lacks fail_harness"
    ):
        adapter.baseline({"input": "x"}, OldBoundary(), random.Random(0))


@pytest.mark.parametrize("replay_mode", [False, True])
def test_non_json_structured_response_is_harness_error(replay_mode: bool) -> None:
    class InjectResult(AgentMiddleware[Any, Any, Any]):
        def after_agent(self, state: Any, runtime: Any) -> dict[str, Any]:
            del state, runtime
            return {"structured_response": object()}

    def spec() -> dict[str, Any]:
        return {"model": model(AIMessage(content="done")), "middleware": [InjectResult()]}

    adapter = make_adapter(lambda _task, _seed: [], spec, spec)
    _, box, _ = boundary(adapter, recording=() if replay_mode else None)
    with pytest.raises(HarnessError, match="non-JSON structured response"):
        adapter.baseline({"input": "x"}, box, random.Random(0))
    assert box.harness_fault


@pytest.mark.parametrize("reason", ["missing call id", "duplicate call ids"])
@pytest.mark.parametrize("replay_mode", [False, True])
def test_invalid_call_ids_are_rejected_before_tool_execution(
    reason: str, replay_mode: bool
) -> None:
    first = call_message({"key": "a"}, {"key": "b"})
    first.tool_calls[0]["id"] = None if reason == "missing call id" else "duplicate"
    if reason == "duplicate call ids":
        first.tool_calls[1]["id"] = "duplicate"

    def lookup(key: str) -> str:
        raise AssertionError(key)

    def spec() -> dict[str, Any]:
        return {"model": model(first)}

    adapter = make_adapter(
        lambda _task, _seed: [StructuredTool.from_function(lookup, description="Lookup.")],
        spec,
        spec,
    )
    _, box, _ = boundary(adapter, recording=() if replay_mode else None)
    with pytest.raises(HarnessError, match=reason):
        adapter.baseline({"input": "x"}, box, random.Random(0))
    assert box.harness_fault and box.tool_calls == 0


@pytest.mark.parametrize("replay_mode", [False, True])
def test_async_graph_invocation_is_fatal(
    monkeypatch: pytest.MonkeyPatch, replay_mode: bool
) -> None:
    """Requirements 3, 6: async middleware hooks reject through the same sticky boundary."""
    real_create = create_agent

    class AsyncGraph:
        def __init__(self, graph: Any) -> None:
            self.graph = graph

        def invoke(self, value: Any, **kwargs: Any) -> Any:
            return asyncio.run(self.graph.ainvoke(value, **kwargs))

    def create(*args: Any, **kwargs: Any) -> Any:
        return AsyncGraph(real_create(*args, **kwargs))

    monkeypatch.setattr(implementation, "create_agent", create)

    def spec() -> dict[str, Any]:
        return {"model": model(AIMessage(content="done"))}

    adapter = make_adapter(lambda _task, _seed: [], spec, spec)
    _, box, _ = boundary(adapter, recording=() if replay_mode else None)
    with pytest.raises(HarnessError, match="async invocation"):
        adapter.baseline({"input": "x"}, box, random.Random(0))
    assert box.harness_fault


@pytest.mark.parametrize("replay_mode", [False, True])
@pytest.mark.parametrize("case", ["timeout", "reentry", "outside"])
def test_serial_gate_timeout_and_reentry_abort_all_waiters(
    monkeypatch: pytest.MonkeyPatch, replay_mode: bool, case: str
) -> None:
    """Requirement 2: malformed dispatch cannot wait forever or silently re-enter the gate."""
    box = ToolBox(
        {},
        Budgets(),
        lambda _kind, _payload: None,
        mode=ToolMode.REPLAY if replay_mode else ToolMode.RECORD,
    )
    # Access our own gate via its module dictionary; no private LangChain APIs are used.
    session = vars(implementation)["_Session"](box)
    outer = vars(implementation)["_Outer"](session)
    session.indices = {"first": 0, "second": 1}
    monkeypatch.setattr(implementation, "WAIT_SECONDS", 0.01)
    target = "second" if case == "timeout" else "missing" if case == "outside" else "first"
    request = ToolCallRequest(
        tool_call={"name": "lookup", "args": {}, "id": target, "type": "tool_call"},
        tool=None,
        state={},
        runtime=cast(Any, None),
    )

    def handler(req: ToolCallRequest) -> ToolMessage:
        if case == "reentry":
            return outer.wrap_tool_call(req, handler)
        raise AssertionError("malformed dispatch reached handler")

    reason = {
        "timeout": "tool order wait timeout",
        "reentry": "tool call re-entry",
        "outside": "tool call outside current message",
    }[case]
    # Finding 31g: a removed deadline must fail this test, never hang pytest.
    errors: list[BaseException] = []

    def dispatch() -> None:
        try:
            outer.wrap_tool_call(request, handler)
        except BaseException as exc:
            errors.append(exc)

    waiter = threading.Thread(target=dispatch, daemon=True)
    waiter.start()
    waiter.join(timeout=1)
    stalled = waiter.is_alive()
    if stalled:
        session.abort(HarnessError("test cleanup"))
        waiter.join(timeout=1)
    assert not stalled, "order gate failed to detect an idle deadlock"
    assert len(errors) == 1 and isinstance(errors[0], HarnessError)
    assert reason in str(errors[0])
    with pytest.raises(HarnessError) as second:
        outer.wrap_tool_call(request, handler)
    assert errors[0] is second.value
    assert box.harness_fault


def test_pending_gate_excludes_answered_and_structured_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Requirements 2, 7: structured calls remain excluded even if their replies are removed."""
    bodies: list[str] = []

    def lookup(key: str) -> str:
        bodies.append(key)
        return key

    class RemoveStructuredReply(AgentMiddleware[Any, Any, Any]):
        def after_model(self, state: Any, runtime: Any) -> dict[str, Any]:
            del runtime
            return {
                "messages": [
                    RemoveMessage(id=message.id)
                    for message in state["messages"]
                    if isinstance(message, ToolMessage)
                    and message.name == "Answer"
                    and message.id is not None
                ]
            }

    message = AIMessage(
        content="answer",
        tool_calls=[
            {"name": "Answer", "args": {"answer": "ok"}, "id": "answer", "type": "tool_call"},
            {"name": "lookup", "args": {"key": "x"}, "id": "lookup", "type": "tool_call"},
        ],
    )
    tool = StructuredTool.from_function(lookup, description="Lookup.")
    native = create_agent(
        model(message, AIMessage(content="done")),
        tools=[tool],
        response_format=ToolStrategy(Answer),
        middleware=[RemoveStructuredReply()],
    )
    native.invoke({"messages": [HumanMessage(content="x")]})
    assert bodies == ["x"]
    bodies.clear()

    def spec() -> dict[str, Any]:
        return {
            "model": model(message, AIMessage(content="done")),
            "response_format": ToolStrategy(Answer),
            "middleware": [RemoveStructuredReply()],
        }

    adapter = make_adapter(lambda _task, _seed: [tool], spec, spec)
    _, box, _ = boundary(adapter)
    monkeypatch.setattr(implementation, "WAIT_SECONDS", 0.1)
    adapter.baseline({"input": "x"}, box, random.Random(0))
    assert bodies == ["x"]
    assert box.tool_calls == 1
