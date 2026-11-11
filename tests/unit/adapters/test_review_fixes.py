"""P3a2 regressions, numbered against the independent review's findings."""

from __future__ import annotations

import copy
import importlib.util
import os
import random
import socket
import ssl
import time
from collections.abc import Callable
from typing import Any

import pytest

if importlib.util.find_spec("langchain") is None:
    if os.environ.get("ARCI_REQUIRE_ADAPTERS") == "1":
        raise ImportError("ARCI_REQUIRE_ADAPTERS=1 requires LangChain")
    pytest.skip("optional LangChain extra is absent", allow_module_level=True)

from langchain.agents.middleware import (
    AgentMiddleware,
    HumanInTheLoopMiddleware,
    ModelResponse,
    ModelRetryMiddleware,
)
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import StructuredTool

from arci.adapters import langchain as implementation
from arci.adapters.langchain import make_adapter
from arci.interfaces import BudgetExceeded
from arci.schema import Budgets, ToolMode
from arci.toolbox import HarnessError, ToolBox, format_diagnostic
from tests.unit.adapters.fixtures import HTTPFailure, ResponseFailure, call_message, model
from tests.unit.adapters.test_core import boundary


def lookup(key: str) -> str:
    return key


def tool() -> StructuredTool:
    return StructuredTool.from_function(lookup, description="Lookup.")


@pytest.mark.parametrize("case", ["builder", "nonmapping", "create", "input", "graph_input"])
@pytest.mark.parametrize("replaying", [False, True])
def test_setup_failure_latches_with_cause(
    case: str, replaying: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Findings 1, 11, 28, 7, 14: setup errors cannot count as agent failures."""

    def spec() -> Any:
        if case == "builder":
            raise ValueError("settings failed")
        if case == "nonmapping":
            return None
        return {"model": model(AIMessage(content="done"))}

    def inputs(task: Any) -> Any:
        if case == "input":
            raise KeyError("question")
        return 42 if case == "graph_input" else {"messages": [("user", "x")]}

    if case == "create":

        def broken(**kwargs: Any) -> Any:
            raise RuntimeError("graph factory broke")

        monkeypatch.setattr(implementation, "create_agent", broken)
    adapter = make_adapter(lambda _t, _s: [], spec, spec, task_to_input=inputs)
    _, box, _ = boundary(adapter, recording=() if replaying else None)
    with pytest.raises(HarnessError) as caught:
        adapter.baseline({"input": "x"}, box, random.Random())
    assert box.harness_fault
    assert box.model_steps == 0
    expected = {
        "builder": "ValueError: settings failed",
        "nonmapping": "TypeError",
        "create": "RuntimeError: graph factory broke",
        "input": "KeyError: 'question'",
        "graph_input": "InvalidUpdateError",
    }
    assert expected[case] in str(caught.value)


@pytest.mark.parametrize("replaying", [False, True])
def test_factory_diagnostic_preserved(replaying: bool) -> None:
    """Findings 7, 14: fixed context must retain the user's scrubbed diagnostic."""

    def broken(task: Any, seed: int) -> Any:
        raise ValueError("fixture database unavailable")

    adapter = make_adapter(broken, lambda: {}, lambda: {})
    with pytest.raises(
        HarnessError, match="tool factory failed: ValueError: fixture database unavailable"
    ):
        if replaying:
            adapter.baseline(
                {},
                ToolBox({}, Budgets(), lambda _kind, _payload: None, mode=ToolMode.REPLAY),
                random.Random(),
            )
        else:
            adapter.toolset({}, 1)


@pytest.mark.parametrize(
    "hook",
    [
        "before_agent",
        "before_model",
        "after_model",
        "after_agent",
        "wrap_model_call",
        "wrap_tool_call",
    ],
)
def test_async_only_user_middleware_rejected(hook: str) -> None:
    """Findings 1, 28: async-only hooks are unsupported before any invocation."""

    async def async_hook(self: Any, *args: Any, **kwargs: Any) -> Any:
        return None

    middleware = type("AsyncOnly", (AgentMiddleware,), {"a" + hook: async_hook})()

    def spec() -> dict[str, Any]:
        return {
            "model": model(call_message({"key": "x"}), AIMessage(content="done")),
            "middleware": [middleware],
        }

    adapter = make_adapter(lambda _t, _s: [tool()], spec, spec)
    _, box, _ = boundary(adapter)
    with pytest.raises(HarnessError, match="LangChain adapter unsupported: async invocation"):
        adapter.baseline({"input": "x"}, box, random.Random())
    assert box.model_steps == 0 and box.harness_fault


@pytest.mark.parametrize("source", ["middleware", "tool"])
def test_interrupted_run_rejected(source: str) -> None:
    """Findings 2, 25: pending interrupts never yield a completed snapshot."""

    def body(key: str) -> str:
        from langgraph.types import interrupt

        return str(interrupt(key))

    def spec() -> dict[str, Any]:
        return {
            "model": model(call_message({"key": "x"}, content="done")),
            "middleware": [HumanInTheLoopMiddleware(interrupt_on={"lookup": True})]
            if source == "middleware"
            else [],
        }

    adapter = make_adapter(
        lambda _t, _s: [StructuredTool.from_function(body, name="lookup", description="Lookup.")],
        spec,
        spec,
    )
    _, box, _ = boundary(adapter)
    with pytest.raises(HarnessError, match="LangChain adapter unsupported: interrupted run"):
        adapter.baseline({"input": "x"}, box, random.Random())
    assert box.harness_fault


def test_slow_healthy_predecessor_has_no_gate_deadline(monkeypatch: pytest.MonkeyPatch) -> None:
    """Findings 3, 12, 21, 24: active predecessors suspend the idle deadline."""
    monkeypatch.setattr(implementation, "WAIT_SECONDS", 0.03)
    bodies: list[str] = []

    def slow(key: str) -> str:
        bodies.append(key)
        time.sleep(0.08)
        return key

    def spec() -> dict[str, Any]:
        return {
            "model": model(
                call_message({"key": "a"}, {"key": "b"}, {"key": "c"}), AIMessage(content="done")
            )
        }

    adapter = make_adapter(
        lambda _t, _s: [StructuredTool.from_function(slow, name="lookup", description="Lookup.")],
        spec,
        spec,
    )
    _, box, _ = boundary(adapter)
    adapter.baseline({"input": "x"}, box, random.Random())
    assert bodies == ["a", "b", "c"] and not box.harness_fault


@pytest.mark.parametrize(
    "error",
    [HTTPFailure(c) for c in (401, 403, 407, 408)]
    + [ResponseFailure(c) for c in (401, 403, 407, 408)]
    + [socket.gaierror("dns"), ssl.SSLError("tls")],
)
def test_added_infrastructure_errors_bypass_user_handler(error: Exception) -> None:
    """Finding 4: the widened D-08 infrastructure rule latches before user recovery."""
    seen: list[Exception] = []

    class Catch(AgentMiddleware[Any, Any, Any]):
        def wrap_model_call(self, request: Any, handler: Callable[[Any], Any]) -> Any:
            try:
                return handler(request)
            except Exception as exc:
                seen.append(exc)
                return ModelResponse(result=[AIMessage(content="caught")])

    def spec() -> dict[str, Any]:
        return {"model": model(error), "middleware": [Catch()]}

    adapter = make_adapter(lambda _t, _s: [], spec, spec)
    _, box, _ = boundary(adapter)
    with pytest.raises(HarnessError, match="infrastructure error"):
        adapter.baseline({"input": "x"}, box, random.Random())
    assert seen == [] and box.harness_fault and box.model_steps == 1


@pytest.mark.parametrize("error_class", [KeyboardInterrupt, SystemExit])
def test_base_exception_stops_siblings_even_if_swallowed(error_class: type[BaseException]) -> None:
    """Finding 6: a tool-body BaseException must abort before any sibling executes."""
    bodies: list[str] = []
    original = error_class("stop")

    def body(key: str) -> str:
        bodies.append(key)
        raise original

    class Catch(AgentMiddleware[Any, Any, Any]):
        def wrap_tool_call(self, request: Any, handler: Callable[[Any], Any]) -> Any:
            try:
                return handler(request)
            except BaseException:
                return ToolMessage(content="caught", tool_call_id=request.tool_call["id"])

    def spec() -> dict[str, Any]:
        return {
            "model": model(call_message({"key": "a"}, {"key": "b"}), AIMessage(content="done")),
            "middleware": [Catch()],
        }

    adapter = make_adapter(
        lambda _t, _s: [StructuredTool.from_function(body, name="lookup", description="Lookup.")],
        spec,
        spec,
    )
    _, box, _ = boundary(adapter)
    with pytest.raises(error_class) as caught:
        adapter.baseline({"input": "x"}, box, random.Random())
    assert caught.value is original
    assert bodies == ["a"] and box.tool_calls == box.model_steps == 1 and box.harness_fault


@pytest.mark.parametrize("initialized", [False, True])
def test_mismatched_adapter_rejected_before_model(initialized: bool) -> None:
    """Finding 19: another adapter's toolset cannot silently produce a graded snapshot."""

    def spec() -> dict[str, Any]:
        return {"model": model(call_message({"key": "x"}), AIMessage(content="done"))}

    first = make_adapter(lambda _t, _s: [tool()], spec, spec)
    second = make_adapter(lambda _t, _s: [tool()], spec, spec)
    _, box, _ = boundary(first)
    if initialized:
        second.toolset({}, 7)
    with pytest.raises(
        HarnessError, match="LangChain adapter unsupported: mismatched adapter toolset"
    ):
        second.baseline({"input": "x"}, box, random.Random())
    assert box.harness_fault and box.model_steps == box.tool_calls == 0


def copy_proxy(tool: Any) -> Any:
    return tool.model_copy(update={"description": "copied"})


@pytest.mark.parametrize("copier", [copy.copy, copy_proxy])
def test_copied_proxy_rejected(copier: Callable[[Any], Any]) -> None:
    """Finding 32: copied proxies must not fabricate a successful null observation."""

    class CopyTool(AgentMiddleware[Any, Any, Any]):
        def wrap_tool_call(self, request: Any, handler: Callable[[Any], Any]) -> Any:
            return handler(request.override(tool=copier(request.tool)))

    def spec() -> dict[str, Any]:
        return {
            "model": model(call_message({"key": "x"}), AIMessage(content="done")),
            "middleware": [CopyTool()],
        }

    adapter = make_adapter(lambda _t, _s: [tool()], spec, spec)
    _, box, _ = boundary(adapter)
    with pytest.raises(HarnessError, match="proxy tool executed outside the boundary"):
        adapter.baseline({"input": "x"}, box, random.Random())
    assert box.harness_fault and box.tool_calls == 0


@pytest.mark.parametrize("policy", ["exception", "base", "retry"])
def test_model_budget_carrier_bypasses_recovery_and_backoff(
    policy: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Finding 29: model-step exhaustion bypasses Exception recovery and retry sleep."""
    caught: list[BaseException] = []
    sleeps: list[float] = []

    class Catch(AgentMiddleware[Any, Any, Any]):
        def wrap_model_call(self, request: Any, handler: Callable[[Any], Any]) -> Any:
            try:
                return handler(request)
            except BaseException as exc:
                if policy == "base" or isinstance(exc, Exception):
                    caught.append(exc)
                    return ModelResponse(result=[AIMessage(content="caught")])
                raise

    middleware: Any = (
        ModelRetryMiddleware(max_retries=2, initial_delay=1, jitter=False)
        if policy == "retry"
        else Catch()
    )
    monkeypatch.setattr(time, "sleep", sleeps.append)
    scripted = model(call_message({"key": "x"}), AIMessage(content="done"))

    def spec() -> dict[str, Any]:
        return {"model": scripted, "middleware": [middleware]}

    adapter = make_adapter(lambda _t, _s: [tool()], spec, spec)
    _, box, _ = boundary(adapter, budgets=Budgets(max_model_steps=1))
    with pytest.raises(BudgetExceeded):
        adapter.baseline({"input": "x"}, box, random.Random())
    assert bool(caught) is (policy == "base")
    assert sleeps == [] and box.budget_exceeded and scripted.attempts == 1


@pytest.mark.parametrize(
    "kind, infra",
    [
        ("context", False),
        ("oserror", False),
        ("file", False),
        ("499", False),
        ("500", True),
        ("599", True),
        ("600", False),
        ("float", False),
    ],
)
def test_infrastructure_rule_exact_boundaries(kind: str, infra: bool) -> None:
    """Finding 31c-e: no cause/context traversal, broad OSError or non-int status matching."""
    error: Exception
    if kind == "context":
        error = ValueError("outer")
        error.__context__ = TimeoutError("inner")
    elif kind == "oserror":
        error = OSError("ordinary")
    elif kind == "file":
        error = FileNotFoundError("file")
    elif kind == "float":
        error = HTTPFailure(500)
        vars(error)["status_code"] = 500.0
    else:
        error = HTTPFailure(int(kind))

    def spec() -> dict[str, Any]:
        return {"model": model(error)}

    adapter = make_adapter(lambda _t, _s: [], spec, spec)
    _, box, _ = boundary(adapter)
    with pytest.raises(HarnessError if infra else type(error)):
        adapter.baseline({"input": "x"}, box, random.Random())
    assert box.harness_fault is infra and box.model_steps == 1


@pytest.mark.parametrize("invalid_model", [None, 123, object()])
def test_invalid_model_is_setup_error(invalid_model: Any) -> None:
    """Findings 1, 11: invalid model settings must reject before attempting invocation."""
    adapter = make_adapter(lambda _t, _s: [], lambda: {"model": invalid_model}, lambda: {})
    _, box, _ = boundary(adapter)
    with pytest.raises(HarnessError, match="invalid model"):
        adapter.baseline({"input": "x"}, box, random.Random())
    assert box.harness_fault and box.model_steps == 0


@pytest.mark.parametrize("where", ["settings", "factory_live", "factory_replay"])
def test_baseexception_during_setup_is_harness_error(where: str) -> None:
    """Findings 1, 7, 28: every pre-model setup failure retains its cause and attribution."""

    def factory(task: Any, seed: int) -> Any:
        if where.startswith("factory"):
            raise KeyboardInterrupt("setup stopped")
        return []

    def spec() -> Any:
        raise KeyboardInterrupt("setup stopped")

    adapter = make_adapter(factory, spec, spec)
    with pytest.raises(BaseException) as caught:
        if where == "factory_live":
            adapter.toolset({}, 7)
        elif where == "factory_replay":
            box = ToolBox({}, Budgets(), lambda _kind, _payload: None, mode=ToolMode.REPLAY)
            adapter.baseline({}, box, random.Random())
        else:
            _, box, _ = boundary(adapter)
            adapter.baseline({}, box, random.Random())

    assert isinstance(caught.value, HarnessError)
    assert "KeyboardInterrupt: setup stopped" in str(caught.value)


@pytest.mark.parametrize("catch_errors", [False, True])
@pytest.mark.parametrize(
    "failure", [ValueError("binding setup failed"), KeyboardInterrupt("binding setup failed")]
)
def test_tool_binding_before_first_model_attempt_is_setup_error(
    catch_errors: bool, failure: BaseException
) -> None:
    """Findings 1, 11: binding failures latch before even BaseException recovery can hide them."""
    from tests.unit.adapters.fixtures import ScriptedModel

    class BindingFailure(ScriptedModel):
        def bind_tools(self, tools: Any, **kwargs: Any) -> Any:
            raise failure

    class CatchBase(AgentMiddleware[Any, Any, Any]):
        def wrap_model_call(self, request: Any, handler: Callable[[Any], Any]) -> Any:
            try:
                return handler(request)
            except BaseException:
                return ModelResponse(result=[AIMessage(content="caught")])

    scripted = BindingFailure(responses=[], script=[])

    def spec() -> dict[str, Any]:
        return {"model": scripted, "middleware": [CatchBase()] if catch_errors else []}

    adapter = make_adapter(lambda _t, _s: [tool()], spec, spec)
    _, box, _ = boundary(adapter)
    with pytest.raises(BaseException) as caught:
        adapter.baseline({"input": "x"}, box, random.Random())
    assert isinstance(caught.value, HarnessError)
    assert "agent setup failed: " + format_diagnostic(failure) in str(caught.value)
    assert box.harness_fault and scripted.attempts == 0
