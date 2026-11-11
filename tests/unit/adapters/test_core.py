"""Native-observation parity and adapter boundary contracts, without network."""

from __future__ import annotations

import importlib.util
import os
import random
from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Any

import pytest

if importlib.util.find_spec("langchain") is None:
    if os.environ.get("ARCI_REQUIRE_ADAPTERS") == "1":
        raise ImportError("ARCI_REQUIRE_ADAPTERS=1 requires LangChain")
    pytest.skip("optional LangChain extra is absent", allow_module_level=True)

from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware, ToolRetryMiddleware
from langchain.agents.structured_output import ToolStrategy
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, JsonValue, field_validator

from arci.adapters.langchain import Adapter, ToolEnv, make_adapter
from arci.hashing import canonical_json, hash_record
from arci.interfaces import BudgetExceeded, ToolFault, ToolSet
from arci.perturb import build
from arci.schema import Bucket, Budgets, FaultSpec, RecordedCall, ToolMode
from arci.toolbox import ToolBox
from tests.unit.adapters.fixtures import Input, ScriptedModel, call_message, model


def boundary(
    adapter: Adapter,
    *,
    task: dict[str, JsonValue] | None = None,
    budgets: Budgets | None = None,
    fault: str | None = None,
    recording: tuple[RecordedCall, ...] | None = None,
) -> tuple[ToolSet, ToolBox, list[tuple[str, dict[str, JsonValue]]]]:
    task = task or {"input": "find answer"}
    world = adapter.toolset(task, 7)
    events: list[tuple[str, dict[str, JsonValue]]] = []
    box = ToolBox(
        world.tools,
        budgets or Budgets(),
        lambda kind, payload: events.append((kind, payload)),
        mode=ToolMode.RECORD if recording is None else ToolMode.REPLAY,
        recording=recording or (),
        perturbations=()
        if fault is None
        else (build(FaultSpec(name=fault, bucket=Bucket.FALSIFY, tool="lookup")),),
    )
    return world, box, events


def observations(scripted: ScriptedModel) -> bytes:
    return canonical_json(
        [
            {"content": message.content, "status": message.status, "name": message.name}
            for message in scripted.seen[-1]
            if isinstance(message, ToolMessage)
        ]
    )


def adapted(
    tools: Sequence[BaseTool],
    scripted: ScriptedModel,
    *,
    middleware: Sequence[AgentMiddleware[Any, Any, Any]] = (),
    **kwargs: Any,
) -> tuple[ToolSet, ToolBox]:
    def spec() -> dict[str, Any]:
        return {"model": scripted, "middleware": middleware}

    adapter = make_adapter(lambda _task, _seed: tools, spec, spec, **kwargs)
    world, box, _ = boundary(adapter)
    adapter.baseline({"input": "find answer"}, box, random.Random(7))
    return world, box


@pytest.mark.parametrize("value", ["a\nβ", {"z": 1, "a": "β"}, ["alpha", "beta"], [1, 2]])
def test_native_result_bytes(value: JsonValue) -> None:
    """Requirements 4, 5, 9: native formatting of strings, dicts and lists survives proxies."""
    calls: list[str] = []

    def lookup(key: str) -> JsonValue:
        calls.append(key)
        return value

    tool = StructuredTool.from_function(lookup, description="Lookup a value.")
    native = model(call_message({"key": "answer"}), AIMessage(content="done"))
    create_agent(native, tools=[tool]).invoke({"messages": [HumanMessage(content="find answer")]})
    wrapped = model(call_message({"key": "answer"}), AIMessage(content="done"))
    world, box = adapted([tool], wrapped)
    assert observations(wrapped) == observations(native)
    assert calls == ["answer", "answer"]
    assert len(box.recording) == 1
    assert world.snapshot() == {"final_output": "done", "structured_response": None, "state": None}


class ObserveValidation(AgentMiddleware[Any, Any, Any]):
    def __init__(self) -> None:
        self.seen: list[bytes] = []

    def wrap_tool_call(self, request: Any, handler: Callable[[Any], Any]) -> Any:
        response = handler(request)
        self.seen.append(canonical_json({"content": response.content, "status": response.status}))
        return response


def test_native_validation_feedback_and_middleware_position() -> None:
    """Requirements 1, 5, 9: native validation occurs inside the user wrapper."""
    calls: list[object] = []

    def lookup(key: str) -> str:
        calls.append(key)
        return key

    tool = StructuredTool.from_function(lookup, args_schema=Input, description="Lookup.")
    native_spy, adapted_spy = ObserveValidation(), ObserveValidation()
    native = model(call_message({"key": [1]}), AIMessage(content="done"))
    create_agent(native, tools=[tool], middleware=[native_spy]).invoke(
        {"messages": [HumanMessage(content="find answer")]}
    )
    wrapped = model(call_message({"key": [1]}), AIMessage(content="done"))
    _, box = adapted([tool], wrapped, middleware=[adapted_spy])
    assert observations(wrapped) == observations(native)
    assert adapted_spy.seen == native_spy.seen
    assert calls == []
    assert box.recording == ()


class TransformInput(BaseModel):
    key: str

    @field_validator("key")
    @classmethod
    def prefix(cls, value: str) -> str:
        return "parsed:" + value


class DateInput(BaseModel):
    key: datetime


@pytest.mark.parametrize(
    "schema, raw", [(TransformInput, "abc"), (DateInput, "2026-01-01T00:00:00")]
)
def test_raw_arguments_validated_without_double_transformation(
    schema: type[BaseModel], raw: str
) -> None:
    """Requirements 4, 9: raw JSON records survive transforming and non-JSON parsers."""
    bodies: list[object] = []

    def lookup(key: Any) -> str:
        bodies.append(key)
        return str(key)

    tool = StructuredTool.from_function(lookup, args_schema=schema, description="Lookup.")
    native = model(call_message({"key": raw}), AIMessage(content="done"))
    create_agent(native, tools=[tool]).invoke({"messages": [HumanMessage(content="find answer")]})
    wrapped = model(call_message({"key": raw}), AIMessage(content="done"))
    _, box = adapted([tool], wrapped)
    assert bodies[0] == bodies[1]
    assert observations(wrapped) == observations(native)
    assert box.recording[0].arguments_sha256 == hash_record({"key": raw})


def test_argument_dictionary_looking_like_envelope_is_plain_arguments() -> None:
    """Requirement 9: public BaseTool.run must not interpret a raw type=tool_call envelope."""
    values: list[str] = []

    def lookup(type: str) -> str:
        values.append(type)
        return type

    tool = StructuredTool.from_function(lookup, description="Return type argument.")
    wrapped = model(call_message({"type": "tool_call"}), AIMessage(content="done"))
    _, box = adapted([tool], wrapped)
    assert values == ["tool_call"]
    assert box.recording[0].arguments_sha256 == hash_record({"type": "tool_call"})


def test_live_error_identity_text_and_type_filtered_retry() -> None:
    """Requirement 4: original exception identity and unmodified text reach user middleware."""
    original = ValueError("secret /tmp/path 123\nsecond line")
    seen: list[Exception] = []
    calls: list[str] = []

    def lookup(key: str) -> str:
        calls.append(key)
        if len(calls) == 1:
            raise original
        return "ok"

    class Spy(AgentMiddleware[Any, Any, Any]):
        def wrap_tool_call(self, request: Any, handler: Callable[[Any], Any]) -> Any:
            try:
                return handler(request)
            except Exception as exc:
                seen.append(exc)
                raise

    retry = ToolRetryMiddleware(
        retry_on=(ValueError,), max_retries=1, initial_delay=0, jitter=False, on_failure="error"
    )
    tool = StructuredTool.from_function(lookup, description="Lookup.")
    _, box = adapted(
        [tool],
        model(call_message({"key": "answer"}), AIMessage(content="done")),
        middleware=[retry, Spy()],
    )
    assert seen == [original]
    assert seen[0] is original
    assert str(seen[0]) == "secret /tmp/path 123\nsecond line"
    assert calls == ["answer", "answer"]
    assert len(box.recording) == 2


@pytest.mark.parametrize("fault", ["tool_timeout", "tool_error_once"])
@pytest.mark.parametrize("mapped", [False, True])
def test_injected_failure_default_and_explicit_mapping(fault: str, mapped: bool) -> None:
    """Requirement 4: injected errors remain ToolFault unless a kind is explicitly mapped."""
    bodies: list[str] = []
    caught: list[Exception] = []

    def lookup(key: str) -> str:
        bodies.append(key)
        return key

    class Catch(AgentMiddleware[Any, Any, Any]):
        def wrap_tool_call(self, request: Any, handler: Callable[[Any], Any]) -> Any:
            try:
                return handler(request)
            except Exception as exc:
                caught.append(exc)
                return ToolMessage(content="handled", tool_call_id=request.tool_call["id"])

    tool = StructuredTool.from_function(lookup, description="Lookup.")
    scripted = model(call_message({"key": "answer"}), AIMessage(content="done"))

    def spec() -> dict[str, Any]:
        return {"model": scripted, "middleware": [Catch()]}

    adapter = make_adapter(
        lambda _task, _seed: [tool],
        spec,
        spec,
        fault_exceptions={"timeout": TimeoutError, "error": ValueError} if mapped else None,
    )
    _, box, _ = boundary(adapter, fault=fault)
    adapter.baseline({"input": "find answer"}, box, random.Random(7))
    assert bodies == []
    assert len(caught) == 1
    expected = (TimeoutError if fault == "tool_timeout" else ValueError) if mapped else ToolFault
    assert type(caught[0]) is expected


def test_serial_retries_with_backoff_do_not_interleave() -> None:
    """Requirements 1, 2, 9: a whole logical call owns the gate across non-zero backoff."""
    attempts: list[str] = []

    def lookup(key: str) -> str:
        attempts.append(key)
        if attempts.count(key) == 1:
            raise ValueError("retry")
        return key

    tool = StructuredTool.from_function(lookup, description="Lookup.")
    retry = ToolRetryMiddleware(
        max_retries=1, initial_delay=0.001, jitter=False, on_failure="error"
    )
    _, box = adapted(
        [tool],
        model(call_message(*({"key": str(i)} for i in range(4))), AIMessage(content="done")),
        middleware=[retry],
    )
    assert attempts == ["0", "0", "1", "1", "2", "2", "3", "3"]
    assert len(box.recording) == 8


@pytest.mark.parametrize("catch_base", [False, True])
def test_budget_aborts_siblings_even_when_user_catches(catch_base: bool) -> None:
    """Requirements 2, 3: budgets bypass Exception handlers and stay terminal if swallowed."""
    caught: list[BaseException] = []
    bodies: list[str] = []

    class Catch(AgentMiddleware[Any, Any, Any]):
        def wrap_tool_call(self, request: Any, handler: Callable[[Any], Any]) -> Any:
            try:
                return handler(request)
            except BaseException as exc:
                if isinstance(exc, Exception) or catch_base:
                    caught.append(exc)
                    return ToolMessage(content="caught", tool_call_id=request.tool_call["id"])
                raise

    def lookup(key: str) -> str:
        bodies.append(key)
        return key

    tool = StructuredTool.from_function(lookup, description="Lookup.")
    scripted = model(call_message(*({"key": str(i)} for i in range(4))), AIMessage(content="done"))

    def spec() -> dict[str, Any]:
        return {"model": scripted, "middleware": [Catch()]}

    adapter = make_adapter(lambda _task, _seed: [tool], spec, spec)
    _, box, _ = boundary(adapter, budgets=Budgets(max_tool_calls=1))
    with pytest.raises(BudgetExceeded):
        adapter.baseline({"input": "find answer"}, box, random.Random(7))
    assert box.budget_exceeded
    assert box.tool_calls == 1
    assert bodies == ["0"]
    assert bool(caught) is catch_base


def test_unknown_name_is_native_agent_feedback() -> None:
    """Requirement 7: unknown names are native feedback, never a harness rejection."""

    def lookup(key: str) -> str:
        return key

    tool = StructuredTool.from_function(lookup, name="lookup", description="Lookup.")
    native = model(call_message({"key": "x"}, name="missing"), AIMessage(content="done"))
    create_agent(native, tools=[tool]).invoke({"messages": [HumanMessage(content="find answer")]})
    wrapped = model(call_message({"key": "x"}, name="missing"), AIMessage(content="done"))
    _, box = adapted([tool], wrapped)
    assert observations(wrapped) == observations(native)
    assert box.recording == ()
    assert not box.harness_fault


class Answer(BaseModel):
    answer: str


def test_structured_response_and_last_ai_text_snapshot() -> None:
    """Requirement 7: structured-output tool messages do not hide the last AI text."""
    scripted = model(call_message({"answer": "forty-two"}, name="Answer", content="explanation"))

    def spec() -> dict[str, Any]:
        return {"model": scripted, "response_format": ToolStrategy(Answer)}

    adapter = make_adapter(lambda _task, _seed: ToolEnv([], lambda: {"count": 4}), spec, spec)
    world, box, _ = boundary(adapter)
    adapter.baseline({"input": "find answer"}, box, random.Random(7))
    assert world.snapshot() == {
        "final_output": "explanation",
        "structured_response": {"answer": "forty-two"},
        "state": {"count": 4},
    }
    assert box.recording == ()


def test_custom_task_input_hook_and_default_validation() -> None:
    """Requirement 8: the supplied hook controls graph input; missing default input latches."""
    scripted = model(AIMessage(content="done"))

    def spec() -> dict[str, Any]:
        return {"model": scripted}

    adapter = make_adapter(
        lambda _task, _seed: [],
        spec,
        spec,
        task_to_input=lambda task: {"messages": [("user", task["question"])]},
    )
    _, box, _ = boundary(adapter, task={"question": "custom"})
    adapter.baseline({"question": "custom"}, box, random.Random(7))
    assert scripted.seen[0][0].content == "custom"
    plain = make_adapter(lambda _task, _seed: [], spec, spec)
    _, plain_box, _ = boundary(plain)
    with pytest.raises(BaseException, match="task_to_input"):
        plain.baseline({}, plain_box, random.Random(7))
    assert plain_box.harness_fault


def test_original_exception_capture_is_cleared_before_an_injected_retry() -> None:
    """Requirement 4: an injected second attempt must not reuse the first real exception."""
    attempts: list[str] = []
    seen: list[Exception] = []
    original = ValueError("first real failure")

    def lookup(key: str) -> str:
        attempts.append(key)
        if len(attempts) == 1:
            raise original
        return key

    class Retry(AgentMiddleware[Any, Any, Any]):
        def wrap_tool_call(self, request: Any, handler: Callable[[Any], Any]) -> Any:
            for _ in range(3):
                try:
                    return handler(request)
                except Exception as exc:
                    seen.append(exc)
            raise AssertionError("retry did not recover")

    def spec() -> dict[str, Any]:
        return {
            "model": model(call_message({"key": "x"}), AIMessage(content="done")),
            "middleware": [Retry()],
        }

    adapter = make_adapter(
        lambda _task, _seed: [StructuredTool.from_function(lookup, description="Lookup.")],
        spec,
        spec,
    )
    world = adapter.toolset({"input": "x"}, 7)
    box = ToolBox(
        world.tools,
        Budgets(),
        lambda _kind, _payload: None,
        perturbations=(
            build(FaultSpec(name="tool_timeout", bucket=Bucket.FALSIFY, at_occurrence=1)),
        ),
    )
    adapter.baseline({"input": "x"}, box, random.Random(7))
    assert seen[0] is original
    assert type(seen[1]) is ToolFault and seen[1].kind == "timeout"
    assert len(attempts) == 2 and box.tool_calls == 3
    assert not box.harness_fault


def test_pending_gate_skips_user_answered_calls() -> None:
    """Requirement 2: a call answered by trusted middleware never blocks later pending calls."""
    bodies: list[str] = []

    def lookup(key: str) -> str:
        bodies.append(key)
        return key

    class AnswerFirst(AgentMiddleware[Any, Any, Any]):
        def after_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
            del runtime
            latest = state["messages"][-1]
            if isinstance(latest, AIMessage) and latest.tool_calls:
                return {
                    "messages": [ToolMessage(content="already answered", tool_call_id="call-0")]
                }
            return None

    tool = StructuredTool.from_function(lookup, description="Lookup.")
    _, box = adapted(
        [tool],
        model(call_message({"key": "first"}, {"key": "second"}), AIMessage(content="done")),
        middleware=[AnswerFirst()],
    )
    assert bodies == ["second"]
    assert box.tool_calls == 1


def test_dataclass_structured_response_is_json() -> None:
    from dataclasses import dataclass

    @dataclass
    class DataclassAnswer:
        answer: str

    def spec() -> dict[str, Any]:
        return {
            "model": model(call_message({"answer": "ok"}, name="DataclassAnswer")),
            "response_format": ToolStrategy(DataclassAnswer),
        }

    adapter = make_adapter(lambda _task, _seed: [], spec, spec)
    world, box, _ = boundary(adapter)
    adapter.baseline({"input": "x"}, box, random.Random(7))
    assert world.snapshot()["structured_response"] == {"answer": "ok"}
    assert not box.harness_fault
