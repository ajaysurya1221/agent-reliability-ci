"""Pinned, synchronous LangChain prototype; no kernel or schema changes.

Builders receive [SerialOrder, Boundary]; put user middleware between these two.
The outer gate orders entire tool operations (including retries), while Boundary
is the innermost wrapper and makes exactly one ToolBox.call for each attempt.
Replay recreates schemas with seed zero: seed-dependent tool schemas are outside
this prototype's supported subset. Argument-rewriting user middleware is not
supported: original arguments are prevalidated, and BaseTool validates the actual
arguments again at execution. Replay does not verify captured final answers.
"""

from __future__ import annotations

import copy
import json
import random
import threading
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, NoReturn, Protocol, cast

from langchain.agents.middleware import AgentMiddleware, AgentState, ToolCallRequest
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import BaseTool
from langchain_core.tools import base as tool_base
from langgraph.prebuilt.tool_node import ToolInvocationError
from langgraph.runtime import Runtime
from langgraph.types import Command
from pydantic import BaseModel, JsonValue, ValidationError

from arci.hashing import canonical_json
from arci.interfaces import AgentFn, ToolBoxProtocol, ToolSetFactory

Middleware = AgentMiddleware[AgentState[Any], None, Any]
Handler = Callable[[ToolCallRequest], ToolMessage | Command[Any]]
# Version-pinned use of LangChain's own formatting rule, including content blocks.
_format_native = cast(Callable[..., Any], vars(tool_base)["_format_output"])


class Graph(Protocol):
    def invoke(self, input: Any, **kwargs: Any) -> Any: ...

    def ainvoke(self, input: Any, **kwargs: Any) -> Awaitable[Any]: ...


MakeTools = Callable[[dict[str, JsonValue], int], list[BaseTool]]
BuildAgent = Callable[[list[BaseTool], list[Middleware]], Graph]


class UnsupportedAdapterError(RuntimeError):
    """An unsupported adapter mode, with a fixed diagnostic."""


@dataclass
class Capture:
    final_output: str | None = None
    observations: list[JsonValue] = field(default_factory=list)
    adapter_error: str | None = None

    def reject(self, reason: str) -> NoReturn:
        self.adapter_error = f"LangChain adapter unsupported: {reason}"
        raise UnsupportedAdapterError(self.adapter_error)


class DerivedToolSet:
    def __init__(self, objects: list[BaseTool], capture: Capture) -> None:
        self.objects = objects
        self.capture = capture
        registered: dict[str, Callable[..., JsonValue]] = {}
        self.tools: Mapping[str, Callable[..., JsonValue]] = registered
        for tool in objects:
            if tool.name in self.tools:
                capture.reject("duplicate tool names")
            if tool.response_format != "content":
                capture.reject("tool artifacts")
            if tool.return_direct:
                capture.reject("return_direct")
            if tool.handle_validation_error or tool.handle_tool_error:
                capture.reject("BaseTool error handlers")
            registered[tool.name] = self._bind(tool)

    def _bind(self, tool: BaseTool) -> Callable[..., JsonValue]:
        def execute(**arguments: JsonValue) -> JsonValue:
            # Dictionary invocation retains the raw JSON result. Passing a ToolCall
            # here would stringify dicts before ARCI records them.
            value: Any = tool.invoke(arguments)
            if isinstance(value, Command):
                self.capture.reject("Command result")
            try:
                canonical_json(value)
            except (TypeError, ValueError):
                self.capture.reject("non-JSON tool result")
            return cast(JsonValue, value)

        return execute

    def snapshot(self) -> dict[str, JsonValue]:
        # Worker calls snapshot outside its agent-exception guard. This is a real
        # environment failure, not a fabricated tool call or private latch access.
        # Replay skips snapshot, so this route does not classify replay-time limits.
        if self.capture.adapter_error is not None:
            raise UnsupportedAdapterError(self.capture.adapter_error)
        metadata: dict[str, JsonValue] = {}
        for tool in self.objects:
            value = copy.deepcopy(tool.metadata or {})
            canonical_json(value)
            metadata[tool.name] = cast(JsonValue, value)
        return {
            "final_output": self.capture.final_output,
            "observations": self.capture.observations,
            "tool_metadata": metadata,
            "adapter_error": self.capture.adapter_error,
        }


class SerialOrder(Middleware):
    """Gate full logical calls, so retries cannot interleave with the next index."""

    def __init__(self, boundary: ToolBoxProtocol, capture: Capture) -> None:
        self.boundary = boundary
        self.capture = capture
        self.condition = threading.Condition()
        self.indices: dict[str, int] = {}
        self.next_index = 0

    def before_agent(self, state: AgentState[Any], runtime: Runtime[None]) -> None:
        del state, runtime

    async def abefore_agent(self, state: AgentState[Any], runtime: Runtime[None]) -> None:
        del state, runtime
        self.capture.reject("async invocation")

    def before_model(self, state: AgentState[Any], runtime: Runtime[None]) -> None:
        del runtime
        self.capture.observations = [
            {"content": cast(JsonValue, message.content), "status": message.status}
            for message in state["messages"]
            if isinstance(message, ToolMessage)
        ]
        self.boundary.note_model_step("model", messages=len(state["messages"]))

    def after_model(self, state: AgentState[Any], runtime: Runtime[None]) -> None:
        del runtime
        message = state["messages"][-1]
        if not isinstance(message, AIMessage):
            self.capture.reject("non-AI model response")
            return
        ids: list[str] = []
        for call in message.tool_calls:
            call_id = call["id"]
            if call_id is None:
                self.capture.reject("missing call id")
            ids.append(call_id)
        if len(ids) != len(set(ids)):
            self.capture.reject("duplicate call ids")
        with self.condition:
            self.indices = {call_id: index for index, call_id in enumerate(ids)}
            self.next_index = 0

    def after_agent(self, state: AgentState[Any], runtime: Runtime[None]) -> None:
        del runtime
        message = state["messages"][-1]
        if not isinstance(message, AIMessage):
            self.capture.reject("non-AI final response")
            return
        self.capture.final_output = message.text
        self.boundary.note_model_step("final answer", answer=message.text)

    def wrap_tool_call(
        self, request: ToolCallRequest, handler: Handler
    ) -> ToolMessage | Command[Any]:
        call_id = request.tool_call["id"]
        if call_id is None or call_id not in self.indices:
            self.capture.reject("tool call outside current message")
        index = self.indices[call_id]
        with self.condition:
            self.condition.wait_for(lambda: index == self.next_index)
        try:
            # Validate outside user retry/error middleware, as native ToolNode does.
            # Its default handler will build the error ToolMessage after this
            # finally releases the next index; the adapter builds no error message.
            tool = request.tool
            if tool is None:
                self.capture.reject("unknown tool")
            try:
                schema = tool.get_input_schema()
                if not issubclass(schema, BaseModel):
                    self.capture.reject("legacy argument schema")
                schema.model_validate(request.tool_call["args"])
            except ValidationError as exc:
                call = request.tool_call
                raise ToolInvocationError(call["name"], exc, call["args"], exc.errors()) from exc
            return handler(request)
        finally:
            with self.condition:
                self.next_index += 1
                self.condition.notify_all()


class Boundary(Middleware):
    """Last middleware: execute through ToolBox and let user error policy decide."""

    def __init__(self, boundary: ToolBoxProtocol, capture: Capture) -> None:
        self.boundary = boundary
        self.capture = capture

    def wrap_tool_call(self, request: ToolCallRequest, handler: Handler) -> ToolMessage:
        del handler
        call = request.tool_call
        if request.tool is None:
            self.capture.reject("unknown tool")
            raise AssertionError("unreachable")
        value = self.boundary.call(call["name"], **call["args"])
        message: Any = _format_native(value, None, call["id"], call["name"], "success")
        if not isinstance(message, ToolMessage):
            self.capture.reject("non-message formatted result")
            raise AssertionError("unreachable")
        return message

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[Any]]],
    ) -> ToolMessage:
        del request, handler
        self.capture.reject("async invocation")
        raise AssertionError("unreachable")


def make_adapter(
    make_tools: MakeTools, build_baseline: BuildAgent, build_candidate: BuildAgent
) -> tuple[ToolSetFactory, AgentFn, AgentFn]:
    """Build frozen-schema entrypoints without user-written wrappers or tool stubs."""
    active: DerivedToolSet | None = None

    def toolset(task: dict[str, JsonValue], seed: int) -> DerivedToolSet:
        nonlocal active
        active = DerivedToolSet(make_tools(task, seed), Capture())
        return active

    def arm(builder: BuildAgent) -> AgentFn:
        def run(
            task: dict[str, JsonValue], boundary: ToolBoxProtocol, rng: random.Random
        ) -> dict[str, JsonValue]:
            del rng
            # Fresh worker per trial. Live uses the factory's exact objects; replay
            # creates only schemas, since ToolBox never invokes live bodies there.
            world = active if active is not None else DerivedToolSet(make_tools(task, 0), Capture())
            serial = SerialOrder(boundary, world.capture)
            inner = Boundary(boundary, world.capture)
            graph = builder(world.objects, [serial, inner])
            graph.invoke({"messages": [{"role": "user", "content": json.dumps(task)}]})
            return {"final_output": world.capture.final_output}

        return run

    return toolset, arm(build_baseline), arm(build_candidate)
