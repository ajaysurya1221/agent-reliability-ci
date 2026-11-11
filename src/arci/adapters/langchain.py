"""Synchronous LangChain agents behind ARCI's recorded tool boundary.

Middleware is trusted: replacing a request's tool or answering without its handler
bypasses recording for that call. Validators execute twice on the same raw input;
validators with side effects are unsupported. Replay reconstructs only exception
classes and round-trippable scrubbed diagnostics, never attributes or exact messages.
A policy can take a different path and still reproduce when sequence, outcome and fingerprint agree.
Provider retries belong in the model client's settings. The inner handler includes
LangChain binding/output processing; infrastructure-shaped errors there are also
classified as infrastructure. Serial execution includes retry backoff. Live tool
failures re-raise the original exception. Replay reconstructs error-kind failures
unless their detail is the injector text "injected error", regardless of fault tag.
Custom perturbations must preserve real-error kind/detail and use that text for
synthetic error-kind failures: altered diagnostics or synthetic class-like text
cannot be distinguished from real errors in the recording and may diverge in replay.
BaseTool run managers are supplied by BaseTool.run; parent-callback linkage can differ.
functools.partial tool functions are accepted by ARCI, although native create_agent
in the supported LangChain version rejects them.
User error_types override builtin names. Reconstructed exceptions must format to
the exact recorded diagnostic;
unrecoverable text (including scrubbed non-literal KeyError keys) is a harness error.
"""

from __future__ import annotations

import ast
import builtins
import copy
import inspect
import json
import random
import socket
import ssl
import threading
import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from contextlib import suppress
from dataclasses import asdict, dataclass, is_dataclass
from functools import partial
from typing import Any, NamedTuple, NoReturn, Protocol, cast, get_args, get_origin, get_type_hints

from pydantic import BaseModel, JsonValue, TypeAdapter

from arci.hashing import canonical_json
from arci.interfaces import (
    AgentFn,
    BudgetExceeded,
    ReplayMiss,
    ToolBoxProtocol,
    ToolFault,
    ToolSetFactory,
)
from arci.toolbox import HarnessError, format_diagnostic

try:
    from httpx import TransportError
    from langchain.agents import create_agent
    from langchain.agents.middleware import (
        AgentMiddleware,
        AgentState,
        ModelRequest,
        ModelResponse,
        ToolCallRequest,
    )
    from langchain.agents.structured_output import AutoStrategy, ProviderStrategy, ToolStrategy
    from langchain_core.callbacks import BaseCallbackHandler
    from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
    from langchain_core.outputs import ChatGeneration, LLMResult
    from langchain_core.runnables import RunnableConfig
    from langchain_core.tools import BaseTool, InjectedToolArg, StructuredTool, Tool
    from langgraph.errors import GraphInterrupt
    from langgraph.prebuilt import ToolRuntime
    from langgraph.runtime import Runtime
    from langgraph.types import Command
except ImportError as exc:
    raise ImportError(
        "LangChain adapter requires public framework APIs; "
        f"{str(exc).splitlines()[0]}; pip install 'agent-reliability-ci[langchain]'"
    ) from None


for _owner, _method in (
    (ToolCallRequest, "override"),
    (BaseTool, "run"),
    (BaseTool, "get_input_schema"),
):
    if not callable(getattr(_owner, _method, None)):
        raise ImportError(f"LangChain adapter requires public {_owner.__name__}.{_method}")


@dataclass(frozen=True)
class ToolEnv:
    tools: Sequence[BaseTool]
    snapshot: Callable[[], dict[str, JsonValue]] | None = None


MakeTools = Callable[[dict[str, JsonValue], int], Sequence[BaseTool] | ToolEnv]
AgentSpec = Callable[[], Mapping[str, Any]]
Middleware = AgentMiddleware[AgentState[Any], None, Any]
ToolHandler = Callable[[ToolCallRequest], ToolMessage | Command[Any]]
ModelHandler = Callable[[ModelRequest[None]], ModelResponse[Any]]
WAIT_SECONDS = 30.0
_JSON = TypeAdapter(JsonValue)


class Adapter(NamedTuple):
    toolset: ToolSetFactory
    baseline: AgentFn
    candidate: AgentFn


class _Boundary(ToolBoxProtocol, Protocol):
    def fail_harness(self, detail: str) -> NoReturn: ...

    @property
    def is_replay(self) -> bool: ...

    def uses_tools(self, tools: Mapping[str, Callable[..., JsonValue]] | None) -> bool: ...


class _Stop(BaseException):
    def __init__(self, cause: BaseException) -> None:
        self.cause = cause
        super().__init__(str(cause))


class _Session:
    def __init__(self, boundary: _Boundary, *, replay: bool = False) -> None:
        self.boundary = boundary
        self.replay = replay
        self.terminal: BaseException | None = None
        self.condition = threading.Condition()
        self.indices: dict[str, int] = {}
        self.entered: set[str] = set()
        self.next_index = 0
        self.owner: int | None = None
        self.idle_since = time.monotonic()
        self.attempt = 0
        self.run_started = False
        self.model_started = False
        self.model_region = threading.local()

    def abort(self, exc: BaseException) -> BaseException:
        with self.condition:
            if self.terminal is None:
                self.terminal = exc
            self.condition.notify_all()
            return self.terminal

    def check(self) -> None:
        if self.terminal is not None:
            raise self.terminal

    def fail(self, reason: str, *, unsupported: bool = True) -> NoReturn:
        detail = f"LangChain adapter unsupported: {reason}" if unsupported else reason
        try:
            self.boundary.fail_harness(detail)
        except BaseException as exc:
            raise self.abort(exc) from None

    def budgeted(self, operation: Callable[[], Any]) -> Any:
        self.check()
        try:
            return operation()
        except (BudgetExceeded, ReplayMiss) as exc:
            raise self.abort(_Stop(exc)) from None
        except HarnessError as exc:
            raise self.abort(exc) from None
        except Exception:
            raise
        except BaseException as exc:
            raise self.abort(exc) from None


class _World:
    def __init__(self, value: Sequence[BaseTool] | ToolEnv) -> None:
        self.env = value if isinstance(value, ToolEnv) else ToolEnv(value)
        self.session: _Session | None = None
        self.original: Exception | None = None
        self.output: dict[str, JsonValue] = {"final_output": None, "structured_response": None}
        self.objects = list(self.env.tools)
        registered: dict[str, Callable[..., JsonValue]] = {}
        self.tools: Mapping[str, Callable[..., JsonValue]] = registered
        for tool in self.objects:
            if tool.name in self.tools:
                self.reject("duplicate tool names")
            self.validate_tool(tool)
            registered[tool.name] = self.bind(tool)

    def reject(self, reason: str) -> NoReturn:
        if self.session is not None:
            self.session.fail(reason)
        raise HarnessError(f"LangChain adapter unsupported: {reason}")

    def validate_tool(self, tool: BaseTool) -> None:
        if tool.response_format != "content":
            self.reject("tool artifacts")
        if tool.return_direct:
            self.reject("return_direct")
        if tool.handle_tool_error:
            self.reject("handle_tool_error")
        if tool.handle_validation_error:
            self.reject("handle_validation_error")
        if getattr(tool, "coroutine", None) is not None and getattr(tool, "func", None) is None:
            self.reject("async invocation")
        if inspect.iscoroutinefunction(getattr(tool, "func", None)):
            self.reject("async invocation")
        if {"tool", "self"}.intersection(tool.args):
            self.reject("reserved boundary argument name")
        # Tool's public single-input args differ from its inferred implementation schema.
        sources: list[tuple[Any, bool]] = (
            []
            if isinstance(tool, Tool) and tool.args_schema is None
            else [(tool.get_input_schema(), False)]
        )
        sources.extend((getattr(tool, key, None), False) for key in ("func", "coroutine"))
        # Inspect the user implementation of the ABC's extension points through
        # standard Python reflection, without importing any framework helper.
        for method in BaseTool.__abstractmethods__:
            implementation = getattr(tool, method)
            if not implementation.__module__.startswith("langchain_core."):
                sources.append((implementation, True))
        for source, supplies_run_manager in sources:
            if source is None:
                continue
            signature_source = source
            while isinstance(source, partial):
                source = source.func
            try:
                annotations = get_type_hints(source, include_extras=True)
            except (NameError, TypeError):
                self.reject("unresolved tool annotations")
            if "runtime" in annotations:
                self.reject("injected tool arguments")
            if callable(signature_source) and not isinstance(signature_source, type):
                parameters = inspect.signature(signature_source).parameters
                if not isinstance(tool, Tool) and {"tool", "self"}.intersection(parameters):
                    self.reject("reserved boundary argument name")
                injected_names = {"runtime"}
                if not supplies_run_manager:
                    injected_names.add("run_manager")
                # Stock Runnable/retriever wrappers accept callbacks internally;
                # user-declared callback injection remains unsupported.
                if not getattr(source, "__module__", "").startswith("langchain_core."):
                    injected_names.add("callbacks")
                if injected_names.intersection(parameters):
                    self.reject("injected tool arguments")
            if any(_injected(annotation) for annotation in annotations.values()):
                self.reject("injected tool arguments")

    def bind(self, tool: BaseTool) -> Callable[..., JsonValue]:
        def execute(**arguments: JsonValue) -> JsonValue:
            try:
                # Public run treats a dictionary as arguments, even type='tool_call'.
                value: Any = tool.run(arguments)
            except GraphInterrupt:
                self.reject("interrupted run")
            except Exception as exc:
                self.original = exc
                raise
            if isinstance(value, Command):
                self.reject("Command result")
            try:
                _JSON.validate_python(value)
                canonical_json(value)
            except (TypeError, ValueError, UnicodeError):
                self.reject("non-JSON tool result")
            return cast(JsonValue, value)

        return execute

    def snapshot(self) -> dict[str, JsonValue]:
        state = self.env.snapshot() if self.env.snapshot is not None else None
        return {**self.output, "state": state}


def _injected(annotation: Any) -> bool:
    marker = get_origin(annotation) or annotation
    if marker is RunnableConfig:
        return True
    if isinstance(marker, InjectedToolArg):
        return True
    if isinstance(marker, type) and issubclass(marker, (InjectedToolArg, ToolRuntime)):
        return True
    return any(_injected(part) for part in get_args(annotation))


def _proxy(tool: BaseTool, function: Callable[..., Any]) -> BaseTool:
    shared: dict[str, Any] = {
        "name": tool.name,
        "description": tool.description,
    }
    if isinstance(tool, Tool):

        def invoke(*arguments: Any, **kwargs: Any) -> Any:
            del arguments  # A Tool supplies its single input positionally; raw args are captured.
            return function(**kwargs)

        proxy: BaseTool = Tool(func=invoke, args_schema=tool.args_schema, **shared)
    else:
        proxy = StructuredTool(
            args_schema=tool.args_schema or tool.get_input_schema(), func=function, **shared
        )
    # Constructor validation copies these containers; native tools share them.
    proxy.extras = tool.extras
    proxy.metadata = tool.metadata
    proxy.tags = tool.tags
    return proxy


def _infra(exc: Exception) -> bool:
    status = getattr(exc, "status_code", None)
    response_status = getattr(getattr(exc, "response", None), "status_code", None)
    return (
        any(
            isinstance(code, int) and (code in {401, 403, 407, 408, 429} or 500 <= code <= 599)
            for code in (status, response_status)
        )
        or isinstance(
            exc, (ConnectionError, TimeoutError, TransportError, socket.gaierror, ssl.SSLError)
        )
        or any(
            cls.__name__ in {"APIConnectionError", "APITimeoutError"} for cls in type(exc).__mro__
        )
    )


class _Outer(Middleware):
    def __init__(self, session: _Session, structured_names: set[str] | None = None) -> None:
        self.session = session
        self.structured_names = structured_names or set()

    def before_agent(self, state: AgentState[Any], runtime: Runtime[None]) -> None:
        self.session.check()
        self.session.run_started = True

    async def abefore_agent(self, state: AgentState[Any], runtime: Runtime[None]) -> None:
        self.session.fail("async invocation")

    def after_model(self, state: AgentState[Any], runtime: Runtime[None]) -> None:
        session = self.session
        session.check()
        messages = state["messages"]
        latest = next(
            (
                index
                for index in range(len(messages) - 1, -1, -1)
                if isinstance(messages[index], AIMessage)
            ),
            None,
        )
        if latest is None:
            session.fail("non-AI model response")
        message = cast(AIMessage, messages[latest])
        answered = {
            item.tool_call_id for item in messages[latest + 1 :] if isinstance(item, ToolMessage)
        }
        pending = [
            call
            for call in message.tool_calls
            if call["id"] not in answered and call["name"] not in self.structured_names
        ]
        ids = [call["id"] for call in pending]
        if any(not value for value in ids):
            session.fail("missing call id")
        if len(set(ids)) != len(ids):
            session.fail("duplicate call ids")
        with session.condition:
            session.indices = {cast(str, value): index for index, value in enumerate(ids)}
            session.entered.clear()
            session.next_index = 0
            session.idle_since = time.monotonic()

    def wrap_tool_call(
        self, request: ToolCallRequest, handler: ToolHandler
    ) -> ToolMessage | Command[Any]:
        session = self.session
        call_id = request.tool_call["id"]
        with session.condition:
            session.check()
            if call_id is None or call_id not in session.indices:
                session.fail("tool call outside current message")
            if call_id in session.entered or session.owner == threading.get_ident():
                session.fail("tool call re-entry")
            session.entered.add(call_id)
            index = session.indices[call_id]
            while index != session.next_index:
                session.check()
                remaining = None
                if session.owner is None:
                    remaining = WAIT_SECONDS - (time.monotonic() - session.idle_since)
                    if remaining <= 0:
                        session.fail("tool order wait timeout")
                session.condition.wait(timeout=remaining)
            session.check()
            session.owner = threading.get_ident()
            session.condition.notify_all()
        try:
            result = handler(request)
            session.check()
            return result
        except BaseException as exc:
            raise session.abort(exc) from None
        finally:
            with session.condition:
                session.owner = None
                session.idle_since = time.monotonic()
                session.next_index += 1
                session.condition.notify_all()

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[Any]]],
    ) -> ToolMessage | Command[Any]:
        self.session.fail("async invocation")


class _Inner(Middleware):
    def __init__(
        self,
        session: _Session,
        world: _World,
        proxies: Sequence[BaseTool],
        faults: Mapping[str, type[Exception]],
        errors: Sequence[type[Exception]],
    ) -> None:
        self.session = session
        self.world = world
        self.proxies = {id(tool) for tool in proxies}
        self.faults = faults
        self.errors = errors

    def wrap_model_call(
        self, request: ModelRequest[None], handler: ModelHandler
    ) -> ModelResponse[Any]:
        session = self.session
        session.budgeted(lambda: session.boundary.note_model_step("model"))
        session.model_started = False
        try:
            session.model_region.active = True
            try:
                response = handler(request)
            finally:
                session.model_region.active = False
        except BaseException as exc:
            session.check()
            if isinstance(exc, Exception) and _infra(exc):
                session.fail("LangChain adapter infrastructure error", unsupported=False)
            if not session.model_started:
                session.fail(f"agent setup failed: {format_diagnostic(exc)}")
            raise
        if not response.result or not isinstance(response.result[0], AIMessage):
            session.fail("non-AI model response")
        session.check()
        return response

    async def awrap_model_call(
        self,
        request: ModelRequest[None],
        handler: Callable[[ModelRequest[None]], Awaitable[ModelResponse[Any]]],
    ) -> ModelResponse[Any]:
        self.session.fail("async invocation")

    def rebuild(self, fault: ToolFault, index: int) -> NoReturn:
        if self.world.original is not None:
            raise self.world.original
        recording = getattr(self.session.boundary, "recording", ())
        recorded = recording[index] if index < len(recording) else None
        if (
            self.session.replay
            and fault.kind == "error"
            and recorded is not None
            and fault.detail != "injected error"
        ):
            name = fault.detail.split(":", 1)[0]
            classes = {value for value in self.errors if format_diagnostic(value.__name__) == name}
            if not classes:
                classes = {
                    value
                    for value in vars(builtins).values()
                    if isinstance(value, type)
                    and issubclass(value, Exception)
                    and value.__name__ == name
                }
            if len(classes) != 1:
                self.session.fail("unreconstructable tool error")
            message = fault.detail[len(name) :].removeprefix(": ")
            arguments: list[Any] = [message]
            with suppress(BaseException):
                arguments.append(ast.literal_eval(message))
            selected = next(iter(classes))
            for argument in arguments:
                try:
                    reconstructed = selected(argument)
                    matches = (
                        isinstance(reconstructed, selected)
                        and format_diagnostic(reconstructed) == fault.detail
                    )
                except BaseException:
                    continue
                if matches:
                    raise reconstructed
            self.session.fail("unreconstructable tool error")

        exception = self.faults.get(fault.kind)
        if exception is not None:
            try:
                mapped = exception(fault.detail)
                if not isinstance(mapped, exception):
                    self.session.fail("unconstructable fault exception")
            except BaseException:
                self.session.fail("unconstructable fault exception")
            raise mapped
        raise fault

    def wrap_tool_call(
        self, request: ToolCallRequest, handler: ToolHandler
    ) -> ToolMessage | Command[Any]:
        if request.tool is None or id(request.tool) not in self.proxies:
            return handler(request)
        raw = copy.deepcopy(request.tool_call["args"])
        name = request.tool_call["name"]
        if "self" in raw:
            self.session.fail("reserved boundary argument name")

        def execute(**parsed: Any) -> Any:
            del parsed
            if "tool" in raw:
                self.session.fail("reserved boundary argument name")
            session = self.session
            self.world.original = None
            index = session.attempt
            session.attempt += 1
            try:
                return session.budgeted(lambda: session.boundary.call(name, **raw))
            except ToolFault as fault:
                self.rebuild(fault, index)

        result = handler(request.override(tool=_proxy(request.tool, execute)))
        self.session.check()
        return result


class _ResponseGuard(BaseCallbackHandler):
    """Validate before LangChain's structured-output processing touches the message."""

    def __init__(self, session: _Session) -> None:
        self.session = session

    def on_chat_model_start(
        self, serialized: dict[str, Any], messages: list[list[BaseMessage]], **kwargs: Any
    ) -> None:
        # Binding and input processing can fail before the provider is ever invoked.
        if getattr(self.session.model_region, "active", False):
            self.session.model_started = True

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        if not getattr(self.session.model_region, "active", False):
            return
        for generations in response.generations:
            for generation in generations:
                if not isinstance(generation, ChatGeneration) or not isinstance(
                    generation.message, AIMessage
                ):
                    self.session.fail("non-AI model response")


def _structured(value: Any, world: _World) -> JsonValue:
    try:
        if isinstance(value, BaseModel):
            value = value.model_dump(mode="json")
        elif is_dataclass(value) and not isinstance(value, type):
            value = asdict(value)
        value = json.loads(json.dumps(value, allow_nan=False))
        canonical_json(value)
    except (TypeError, ValueError, UnicodeError):
        world.reject("non-JSON structured response")
    return cast(JsonValue, value)


def make_adapter(
    make_tools: MakeTools,
    baseline: AgentSpec,
    candidate: AgentSpec,
    *,
    task_to_input: Callable[[dict[str, JsonValue]], Any] | None = None,
    fault_exceptions: Mapping[str, type[Exception]] | None = None,
    error_types: Sequence[type[Exception]] = (),
) -> Adapter:
    """Return manifest entrypoints; each worker owns one fresh tool environment.

    Replay rebuilds tool schemas using seed zero and never executes their bodies.
    make_tools must therefore be safe to call again, with seed-independent schemas.
    """
    active: _World | None = None

    def toolset(task: dict[str, JsonValue], seed: int) -> _World:
        nonlocal active
        try:
            active = _World(make_tools(task, seed))
        except HarnessError:
            raise
        except BaseException as exc:
            raise HarnessError(
                f"LangChain adapter unsupported: tool factory failed: {format_diagnostic(exc)}"
            ) from None
        return active

    def arm(builder: AgentSpec) -> AgentFn:
        def run(
            task: dict[str, JsonValue], boundary: ToolBoxProtocol, rng: random.Random
        ) -> dict[str, JsonValue]:
            del rng
            if not callable(getattr(boundary, "fail_harness", None)):
                raise HarnessError("LangChain adapter unsupported: boundary lacks fail_harness")
            session = _Session(
                cast(_Boundary, boundary),
                replay=bool(getattr(boundary, "is_replay", False)),
            )
            try:
                return execute(task, session)
            except _Stop as exc:
                raise exc.cause from None
            except HarnessError:
                raise
            except BaseException as exc:
                session.check()
                if not session.run_started:
                    session.fail(f"agent setup failed: {format_diagnostic(exc)}")
                raise

        def execute(task: dict[str, JsonValue], session: _Session) -> dict[str, JsonValue]:
            if not session.replay and not session.boundary.uses_tools(
                active.tools if active is not None else None
            ):
                session.fail("mismatched adapter toolset")
            try:
                world = active if active is not None else _World(make_tools(task, 0))
            except HarnessError as exc:
                session.fail(str(exc).removeprefix("LangChain adapter unsupported: "))
            except BaseException as exc:
                session.fail(f"tool factory failed: {format_diagnostic(exc)}")
            world.session = session
            settings: Any = builder()
            if not isinstance(settings, Mapping):
                raise TypeError("agent settings must be a mapping")
            kwargs = dict(settings)
            for key in kwargs:
                if key not in {"model", "system_prompt", "middleware", "response_format", "name"}:
                    session.fail(f"create_agent key {key}")
            if "model" not in kwargs:
                session.fail("missing model")
            middleware: list[Middleware] = list(kwargs.pop("middleware", ()))
            if any(getattr(item, "tools", ()) for item in middleware):
                session.fail("middleware-owned tools")
            for item in middleware:
                for hook in (
                    "before_agent",
                    "before_model",
                    "after_model",
                    "after_agent",
                    "wrap_model_call",
                    "wrap_tool_call",
                ):
                    if getattr(type(item), "a" + hook) is not getattr(
                        AgentMiddleware, "a" + hook
                    ) and getattr(type(item), hook) is getattr(AgentMiddleware, hook):
                        session.fail("async invocation")
            handle_errors = getattr(kwargs.get("response_format"), "handle_errors", None)
            if callable(handle_errors) and not (
                isinstance(handle_errors, type) and issubclass(handle_errors, Exception)
            ):
                session.fail("callable response_format handle_errors")

            def placeholder(**arguments: Any) -> None:
                del arguments
                session.fail("proxy tool executed outside the boundary")

            proxies = [_proxy(tool, placeholder) for tool in world.objects]
            structured_names: set[str] = set()
            response_format = kwargs.get("response_format")
            if response_format is not None and not isinstance(response_format, ProviderStrategy):
                strategy = response_format
                if isinstance(strategy, AutoStrategy):
                    strategy = ToolStrategy(strategy.schema)
                elif not isinstance(strategy, ToolStrategy):
                    strategy = ToolStrategy(strategy)
                structured_names = {spec.name for spec in strategy.schema_specs}
            outer = _Outer(session, structured_names)
            inner = _Inner(session, world, proxies, fault_exceptions or {}, error_types)
            graph = create_agent(tools=proxies, middleware=[outer, *middleware, inner], **kwargs)
            if task_to_input is None:
                if not isinstance(task.get("input"), str):
                    session.fail("task_to_input requires a string input")
                graph_input: Any = {"messages": [{"role": "user", "content": task["input"]}]}
            else:
                graph_input = task_to_input(task)
            result: Any = graph.invoke(graph_input, config={"callbacks": [_ResponseGuard(session)]})
            session.check()
            if result.get("__interrupt__"):
                session.fail("interrupted run")
            messages = result.get("messages", ())
            final = next(
                (message.text for message in reversed(messages) if isinstance(message, AIMessage)),
                None,
            )
            world.output = {
                "final_output": final,
                "structured_response": _structured(result.get("structured_response"), world),
            }
            return copy.deepcopy(world.output)

        return run

    return Adapter(toolset, arm(baseline), arm(candidate))
