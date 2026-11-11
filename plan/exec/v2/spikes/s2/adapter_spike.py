"""Offline, synchronous LangChain boundary experiment; not a product adapter."""

from __future__ import annotations

import asyncio
import math
import random
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, cast

from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware, AgentState, ToolCallRequest
from langchain.agents.middleware.types import InputAgentState
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import BaseTool, StructuredTool
from langgraph.runtime import Runtime
from langgraph.types import Command
from pydantic import JsonValue, ValidationError

from arci.hashing import canonical_json
from arci.interfaces import ToolBoxProtocol, ToolFault


def require_json(value: object) -> JsonValue:
    """Reject coercible Python shapes as well as non-finite or non-UTF-8 JSON."""
    if (
        value is None
        or type(value) in (str, bool, int)
        or (type(value) is float and math.isfinite(value))
    ):
        pass
    elif type(value) is list:
        for item in cast(list[object], value):
            require_json(item)
    elif type(value) is dict:
        for key, item in cast(dict[object, object], value).items():
            if type(key) is not str:
                raise ValueError("S2: non-JSON object key")
            require_json(item)
    else:
        raise ValueError(f"S2: non-JSON value ({type(value).__name__})")
    canonical_json(value)
    return cast(JsonValue, value)


@dataclass
class Capture:
    final_output: str | None = None
    observations: list[JsonValue] = field(default_factory=list)
    adapter_error: str | None = None


# One factory invocation per worker. Replay constructs no toolset; it uses a fresh
# capture here and the runner grades the sealed source snapshot after exact replay.
_capture = Capture()


class World:
    def __init__(self, task: dict[str, JsonValue], capture: Capture) -> None:
        self.task = task
        self.capture = capture
        self.body_calls = 0
        self.tools: dict[str, Callable[..., JsonValue]] = {"lookup": self.lookup}

    def lookup(self, key: str) -> JsonValue:
        self.body_calls += 1
        shape = self.task.get("shape")
        if shape == "command":
            # Deliberately invalid environment output; the existing ToolBox must
            # reject this as a harness fault, not turn it into an agent success.
            return cast(JsonValue, Command(update={"answer": "bypassed"}))
        if shape == "result":
            return cast(JsonValue, {"not-json"})
        if self.task.get("real_error") and self.body_calls == 1:
            raise RuntimeError("fixture service unavailable")
        return self.task.get("answer") if key == "answer" else None

    def snapshot(self) -> dict[str, JsonValue]:
        return {
            "environment": {"answer": self.task.get("answer"), "body_calls": self.body_calls},
            "final_output": self.capture.final_output,
            "observations": self.capture.observations,
            "adapter_error": self.capture.adapter_error,
        }


def make_world(task: dict[str, JsonValue], seed: int) -> World:
    del seed
    global _capture
    _capture = Capture()
    return World(task, _capture)


def oracle(task: dict[str, JsonValue], final_state: dict[str, JsonValue]) -> bool:
    return final_state.get("final_output") == task.get("answer")


def schema_only(key: str) -> str:
    """Look up the answer by key."""
    del key
    raise AssertionError("S2: LangChain handler executed the schema-only tool")


def tool_schemas() -> list[BaseTool]:
    return [StructuredTool.from_function(schema_only, name="lookup")]


class BoundaryMiddleware(AgentMiddleware[AgentState[Any], None, Any]):
    def __init__(self, tools: ToolBoxProtocol, capture: Capture) -> None:
        self.boundary = tools
        self.capture = capture

    def before_agent(self, state: AgentState[Any], runtime: Runtime[None]) -> None:
        # create_agent needs the synchronous counterpart when abefore_agent exists.
        del state, runtime

    def before_model(self, state: AgentState[Any], runtime: Runtime[None]) -> None:
        del runtime
        self.boundary.note_model_step("scripted model", messages=len(state["messages"]))

    def after_model(self, state: AgentState[Any], runtime: Runtime[None]) -> None:
        del runtime
        message = state["messages"][-1]
        if isinstance(message, AIMessage) and len(message.tool_calls) > 1:
            raise ValueError("S2: parallel tool calls unsupported; request one call per message")

    def after_agent(self, state: AgentState[Any], runtime: Runtime[None]) -> None:
        del runtime
        message = state["messages"][-1]
        if not isinstance(message, AIMessage) or not isinstance(message.content, str):
            raise ValueError("S2: final output must be a text AIMessage")
        self.capture.final_output = message.content

    async def abefore_agent(self, state: AgentState[Any], runtime: Runtime[None]) -> None:
        del state, runtime
        raise ValueError("S2: async invocation unsupported; use invoke")

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command[Any]],
    ) -> ToolMessage:
        del handler  # ToolBox owns execution; calling this would execute the tool twice.
        call = request.tool_call
        require_json(call["args"])
        if request.tool is not None and (
            request.tool.response_format != "content" or request.tool.return_direct
        ):
            raise ValueError("S2: tool artifacts and return_direct unsupported")
        try:
            value = self.boundary.call(call["name"], **call["args"])
        except ValidationError as exc:
            # The boundary already latched harness_error. Its one-line diagnostic
            # drops Pydantic's input detail; retain the type in snapshot and trace.
            rejected_type = type(exc.errors(include_url=False)[0]["input"]).__name__
            detail = f"S2: unsupported tool result {rejected_type}; only JSON values supported"
            self.capture.adapter_error = detail
            self.boundary.note_model_step("adapter rejected tool result", detail=detail)
            raise
        except ToolFault as exc:
            message = ToolMessage(
                content=f"{exc.kind}: {exc.detail}",
                tool_call_id=call["id"],
                name=call["name"],
                status="error",
            )
        else:
            require_json(value)
            message = ToolMessage(
                content=canonical_json(value).decode(),
                tool_call_id=call["id"],
                name=call["name"],
                status="success",
            )
        self.capture.observations.append(
            require_json({"status": message.status, "content": message.content})
        )
        return message

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[Any]]],
    ) -> ToolMessage:
        del request, handler
        raise ValueError("S2: async invocation unsupported; use invoke")


class ScriptedModel(FakeMessagesListChatModel):
    """Fixed offline policy that chooses its next scripted message from tool feedback."""

    retry: bool = False
    parallel: bool = False
    bad_arguments: bool = False

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | Callable[..., Any] | BaseTool],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> ScriptedModel:
        del tools, tool_choice, kwargs
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        import json

        del stop, run_manager, kwargs
        observed = [message for message in messages if isinstance(message, ToolMessage)]
        failed = bool(observed) and (
            observed[-1].status == "error" or observed[-1].content == "null"
        )
        if not observed or (self.retry and len(observed) == 1 and failed):
            arguments: dict[str, Any] = {"key": "answer"}
            if self.bad_arguments:
                arguments["key"] = float("nan")
            response = AIMessage(
                content="",
                tool_calls=[
                    {"name": "lookup", "args": arguments, "id": f"script-{len(observed)}-{i}"}
                    for i in range(2 if self.parallel else 1)
                ],
            )
        else:
            answer = "unavailable" if failed else json.loads(str(observed[-1].content))
            response = AIMessage(content=str(answer))
        return ChatResult(generations=[ChatGeneration(message=response)])


def _run(task: dict[str, JsonValue], tools: ToolBoxProtocol, retry: bool) -> dict[str, JsonValue]:
    graph = create_agent(
        ScriptedModel(
            responses=[],
            retry=retry,
            parallel=task.get("shape") == "parallel",
            bad_arguments=task.get("shape") == "arguments",
        ),
        tools=tool_schemas(),
        middleware=[BoundaryMiddleware(tools, _capture)],
    )
    inputs: InputAgentState = {"messages": [{"role": "user", "content": "Look up the answer."}]}
    if task.get("shape") == "async":
        asyncio.run(graph.ainvoke(inputs))
    else:
        graph.invoke(inputs)
    if task.get("erase_capture"):
        _capture.final_output = None
    # Intentionally contradict the oracle to demonstrate the snapshot boundary.
    return {"success": not retry, "answer": "return value is not oracle input"}


def baseline(
    task: dict[str, JsonValue], tools: ToolBoxProtocol, rng: random.Random
) -> dict[str, JsonValue]:
    del rng
    return _run(task, tools, retry=True)


def candidate(
    task: dict[str, JsonValue], tools: ToolBoxProtocol, rng: random.Random
) -> dict[str, JsonValue]:
    del rng
    return _run(task, tools, retry=False)
