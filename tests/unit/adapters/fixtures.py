"""The single offline scripted model and process-importable adapter fixtures."""

from __future__ import annotations

import importlib.util
import os
from collections.abc import Callable, Sequence
from typing import Any, cast

import pytest

if importlib.util.find_spec("langchain") is None:
    if os.environ.get("ARCI_REQUIRE_ADAPTERS") == "1":
        raise ImportError("ARCI_REQUIRE_ADAPTERS=1 requires LangChain")
    pytest.skip("optional LangChain extra is absent", allow_module_level=True)

from langchain.agents.middleware import AgentMiddleware, ModelRetryMiddleware, ToolRetryMiddleware
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import LanguageModelInput
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field, JsonValue

from arci.adapters.langchain import ToolEnv, make_adapter


class ScriptedModel(FakeMessagesListChatModel):
    """Public fake-chat-model subclass with binding and deterministic scripted failures."""

    script: list[BaseMessage | Exception] = Field(default_factory=list)
    seen: list[list[BaseMessage]] = Field(default_factory=list)
    attempts: int = 0

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | Callable[..., Any] | BaseTool],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> Runnable[LanguageModelInput, AIMessage]:
        del tools, tool_choice, kwargs
        return cast(Runnable[LanguageModelInput, AIMessage], self)

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        del stop, run_manager, kwargs
        self.seen.append(list(messages))
        index = self.attempts
        self.attempts += 1
        if index >= len(self.script):
            raise AssertionError("fake model script exhausted")
        response = self.script[index]
        if isinstance(response, Exception):
            raise response
        return ChatResult(generations=[ChatGeneration(message=response)])


def model(*script: BaseMessage | Exception) -> ScriptedModel:
    return ScriptedModel(responses=[], script=list(script))


def call_message(*arguments: dict[str, Any], name: str = "lookup", content: str = "") -> AIMessage:
    return AIMessage(
        content=content,
        tool_calls=[
            {"name": name, "args": argument, "id": f"call-{index}", "type": "tool_call"}
            for index, argument in enumerate(arguments)
        ],
    )


class Input(BaseModel):
    key: str = "answer"


class HTTPFailure(Exception):
    def __init__(self, code: int) -> None:
        super().__init__("provider status")
        self.status_code = code


class ResponseFailure(Exception):
    def __init__(self, code: int) -> None:
        super().__init__("response status")
        self.response = HTTPFailure(code)


class APIConnectionError(Exception):
    pass


class APITimeoutError(Exception):
    pass


class ChildAPIConnectionError(APIConnectionError):
    pass


def provider_error(kind: str) -> Exception:
    if kind == "http429":
        return HTTPFailure(429)
    if kind == "http503":
        return HTTPFailure(503)
    if kind == "response599":
        return ResponseFailure(599)
    if kind == "http400":
        return HTTPFailure(400)
    if kind == "connection":
        return ConnectionError("offline")
    if kind == "timeout":
        return TimeoutError("provider timed out")
    if kind == "api_connection":
        return ChildAPIConnectionError("offline")
    if kind == "api_timeout":
        return APITimeoutError("provider timed out")
    if kind == "transport":
        import httpx

        return httpx.TransportError("transport failed")
    error = ValueError("output parsing failed")
    if kind == "cause":
        error.__cause__ = TimeoutError("not the thrown exception")
    return error


_task: dict[str, JsonValue] = {}


def runner_tools(task: dict[str, JsonValue], seed: int) -> ToolEnv:
    global _task
    _task = task
    body_calls: list[str] = []

    def lookup(key: str = "answer") -> Any:
        body_calls.append(key)
        rejected = task.get("runtime_reject")
        if rejected:
            if seed == 0:
                raise AssertionError("replay executed a live body")
            if rejected == "command":
                from langgraph.types import Command

                return Command(update={})
            return object()
        if task.get("key_error"):
            raise KeyError("zzz")
        if task.get("tool_timeout_error"):
            raise TimeoutError("real tool timeout")
        if task.get("real_error"):
            raise OSError(5, "disk unavailable")
        return task.get("value", "forty-two")

    return ToolEnv(
        [StructuredTool.from_function(lookup, name="lookup", description="Lookup a value.")],
        lambda: {"body_calls": list(body_calls), "seed": seed},
    )


def runner_spec() -> dict[str, Any]:
    if _task.get("setup_error"):
        raise ValueError("settings unavailable")
    middleware: list[AgentMiddleware[Any, Any, Any]] = []
    if _task.get("retry_tools"):
        middleware.append(
            ToolRetryMiddleware(max_retries=1, initial_delay=0, jitter=False, on_failure="error")
        )
    if _task.get("retry_models"):
        middleware.append(
            ModelRetryMiddleware(max_retries=2, initial_delay=0, jitter=False, on_failure="error")
        )
    if _task.get("catch_models"):
        middleware.append(CatchModelException())
    kind = _task.get("provider_error")
    if isinstance(kind, str):
        scripted = model(provider_error(kind), AIMessage(content="recovered"))
    elif _task.get("real_error"):
        scripted = model(call_message({"key": "answer"}), AIMessage(content="done"))
        middleware.append(ErrnoPolicy())
    else:
        scripted = model(call_message({"key": "answer"}), AIMessage(content="done"))
    return {"model": scripted, "middleware": middleware}


class CatchModelException(AgentMiddleware[Any, Any, Any]):
    def wrap_model_call(self, request: Any, handler: Callable[[Any], Any]) -> Any:
        from langchain.agents.middleware import ModelResponse

        try:
            return handler(request)
        except Exception:
            return ModelResponse(result=[AIMessage(content="caught")])


class ErrnoPolicy(AgentMiddleware[Any, Any, Any]):
    """Different recovered text leaves sequence, oracle result and fingerprint unchanged."""

    def wrap_tool_call(self, request: Any, handler: Callable[[Any], Any]) -> Any:
        from langchain_core.messages import ToolMessage

        try:
            return handler(request)
        except OSError as exc:
            text = "live errno" if exc.errno == 5 else "replay lost errno"
            return ToolMessage(content=text, tool_call_id=request.tool_call["id"])


toolset, baseline, candidate = make_adapter(runner_tools, runner_spec, runner_spec)
