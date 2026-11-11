"""Regressions numbered against the P3a3 second-fix brief."""

from __future__ import annotations

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
from langchain.agents.middleware import ToolCallRequest
from langchain_core.callbacks import CallbackManagerForToolRun
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import BaseTool, StructuredTool, Tool

from arci.adapters import langchain as implementation
from arci.adapters.langchain import make_adapter
from arci.interfaces import ToolFault
from arci.runner import run_trial
from arci.schedule import build_schedule
from arci.schema import (
    Bucket,
    Budgets,
    Manifest,
    Outcome,
    Termination,
    ToolCall,
    ToolMode,
    ToolResult,
)
from arci.toolbox import HarnessError, ToolBox, format_diagnostic
from tests.unit.adapters.fixtures import Input, ScriptedModel, call_message, model
from tests.unit.adapters.test_core import boundary, observations
from tests.unit.adapters.test_runner import manifest


@pytest.mark.parametrize(
    "kind", ["pii", "before_agent", "before_model", "wrap_model_call", "cached", "bound"]
)
def test_graph_entry_attribution_and_bound_model(kind: str) -> None:
    """P3a3 items 1/2: runtime policy failures are FAIL, bound models still PASS."""
    data = manifest(task={"case": kind, "input": "email alice@example.com"}).model_dump(
        exclude={"record_sha256"}
    )
    prefix = "tests.unit.adapters.second_fixtures"
    data.update(toolset=f"{prefix}:toolset")
    data["baseline"]["agent"] = f"{prefix}:baseline"
    data["candidate"]["agent"] = f"{prefix}:candidate"
    plan = Manifest.create(**data)
    spec = build_schedule(plan)[0]
    live = run_trial(spec, lambda _event: None, plan.contract)
    expected = Outcome.PASS if kind == "bound" else Outcome.FAIL
    assert live.outcome is expected, live.failure_detail
    assert live.termination is (Termination.COMPLETED if kind == "bound" else Termination.CRASH)
    assert live.usage.model_steps == (2 if kind == "bound" else 0)
    assert live.usage.tool_calls == (1 if kind in {"bound", "cached"} else 0)
    replayed = run_trial(
        spec.model_copy(
            update={
                "tool_mode": ToolMode.REPLAY,
                "recording": live.recording,
                "replay_final_state": live.final_state,
            }
        ),
        lambda _event: None,
        plan.contract,
    )
    assert replayed.outcome is expected, replayed.failure_detail
    assert replayed.failure_fingerprint == live.failure_fingerprint


@pytest.mark.parametrize(
    "parse_error", [None, TypeError, MemoryError, RecursionError, KeyboardInterrupt]
)
def test_literal_parse_failure_only_discards_candidate(
    parse_error: type[BaseException] | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """P3a3 item 3: even an exceptional literal parser must retain the string candidate."""
    original = ValueError("{['a']: 'b'}")

    def body(key: str) -> str:
        raise original

    def spec() -> dict[str, Any]:
        return {"model": model(call_message({"key": "x"}))}

    adapter = make_adapter(
        lambda _t, _s: [StructuredTool.from_function(body, name="lookup", description="Lookup.")],
        spec,
        spec,
    )
    _, live, _ = boundary(adapter)
    with pytest.raises(ValueError) as caught:
        adapter.baseline({"input": "x"}, live, random.Random())
    assert caught.value is original
    if parse_error is not None:

        def broken(value: Any) -> Any:
            raise parse_error("parse failed")

        monkeypatch.setattr(implementation.ast, "literal_eval", broken)
    _, replayed, _ = boundary(adapter, recording=live.recording)
    with pytest.raises(BaseException) as caught:
        adapter.baseline({"input": "x"}, replayed, random.Random())
    assert type(caught.value) is ValueError
    assert format_diagnostic(caught.value) == format_diagnostic(original)
    assert not replayed.harness_fault
    replayed.assert_replay_consumed()


@pytest.mark.parametrize("tag", ["custom_tagger", "tool_error_once", None])
@pytest.mark.parametrize("injected", [False, True])
def test_failure_content_controls_reconstruction(tag: str | None, injected: bool) -> None:
    """P3a3 item 4: tags do not turn a real error into an injected fault or vice versa."""
    original = ValueError("real error")
    bodies: list[str] = []

    class Tagger:
        name = "custom_tagger"
        bucket = Bucket.FALSIFY

        def before(self, call: ToolCall, rng: random.Random) -> ToolResult | None:
            if injected:
                return ToolResult(
                    call_id=call.call_id,
                    tool=call.tool,
                    ok=False,
                    error_kind="error",
                    error_detail="injected error",
                    injected_by=tag,
                )
            return None

        def after(self, call: ToolCall, result: ToolResult, rng: random.Random) -> ToolResult:
            return result.model_copy(update={"injected_by": tag})

    def body(key: str) -> str:
        bodies.append(key)
        raise original

    def spec() -> dict[str, Any]:
        return {"model": model(call_message({"key": "x"}))}

    adapter = make_adapter(
        lambda _t, _s: [StructuredTool.from_function(body, name="lookup", description="Lookup.")],
        spec,
        spec,
    )
    world = adapter.toolset({}, 7)
    live = ToolBox(world.tools, Budgets(), lambda _k, _p: None, perturbations=[Tagger()])
    expected = ToolFault if injected else ValueError
    with pytest.raises(expected) as caught:
        adapter.baseline({"input": "x"}, live, random.Random())
    if not injected:
        assert caught.value is original
    replayed = ToolBox(
        {}, Budgets(), lambda _k, _p: None, mode=ToolMode.REPLAY, recording=live.recording
    )
    with pytest.raises(expected) as rebuilt:
        adapter.baseline({"input": "x"}, replayed, random.Random())
    assert format_diagnostic(rebuilt.value) == format_diagnostic(caught.value)
    assert bodies == ([] if injected else ["x"])
    replayed.assert_replay_consumed()


class ManagerTool(BaseTool):
    name: str = "lookup"
    description: str = "Lookup."
    args_schema: Any = Input

    def _run(self, key: str, run_manager: CallbackManagerForToolRun | None = None) -> str:
        assert isinstance(run_manager, CallbackManagerForToolRun)
        return "managed:" + key


def test_run_manager_subclass_native_parity() -> None:
    """P3a3 item 5: BaseTool.run supplies the documented optional run manager."""
    target = ManagerTool()
    native = model(call_message({"key": "x"}), AIMessage(content="done"))
    create_agent(native, tools=[target]).invoke({"messages": [HumanMessage(content="x")]})
    wrapped = model(call_message({"key": "x"}), AIMessage(content="done"))
    adapter = make_adapter(lambda _t, _s: [target], lambda: {"model": wrapped}, lambda: {})
    _, box, _ = boundary(adapter)
    adapter.baseline({"input": "x"}, box, random.Random())
    assert observations(wrapped) == observations(native)
    assert box.recording[0].result.value == "managed:x"


@pytest.mark.parametrize("simple", [False, True])
def test_proxy_options_are_references_even_when_not_copyable(simple: bool) -> None:
    """P3a3 item 6: both proxy layers share extras, metadata and tags by identity."""

    def body(key: str) -> str:
        return key

    target = (
        Tool(name="lookup", description="Lookup.", func=body)
        if simple
        else StructuredTool.from_function(body, name="lookup", description="Lookup.")
    )
    target.metadata = {"lock": threading.Lock()}
    target.extras = {"cache_control": {"type": "ephemeral"}}
    target.tags = ["shared"]
    proxy = vars(implementation)["_proxy"](target, body)
    second = vars(implementation)["_proxy"](proxy, body)
    for result in (proxy, second):
        assert result.metadata is target.metadata
        assert result.extras is target.extras
        assert result.tags is target.tags
    scripted = model(call_message({"key": "x"}), AIMessage(content="done"))
    adapter = make_adapter(lambda _t, _s: [target], lambda: {"model": scripted}, lambda: {})
    _, box, _ = boundary(adapter)
    assert adapter.baseline({"input": "x"}, box, random.Random())["final_output"] == "done"


@pytest.mark.parametrize("name", ["tool", "self"])
def test_single_input_function_reserved_names_have_native_parity(name: str) -> None:
    """P3a3 item 7: positional Tool inputs do not collide with boundary keyword names."""

    def tool_arg(tool: str) -> str:
        return tool

    def self_arg(self: str) -> str:
        return self

    target = Tool(
        name="lookup", description="Lookup.", func=tool_arg if name == "tool" else self_arg
    )
    native = model(call_message({"__arg1": "x"}), AIMessage(content="done"))
    create_agent(native, tools=[target]).invoke({"messages": [HumanMessage(content="x")]})
    wrapped = model(call_message({"__arg1": "x"}), AIMessage(content="done"))
    adapter = make_adapter(lambda _t, _s: [target], lambda: {"model": wrapped}, lambda: {})
    _, box, _ = boundary(adapter)
    adapter.baseline({"input": "x"}, box, random.Random())
    assert observations(wrapped) == observations(native)


@pytest.mark.parametrize("name", ["tool", "self"])
def test_single_input_raw_reserved_keys_still_rejected(name: str) -> None:
    """P3a3 item 7: a positional implementation does not license raw reserved keys."""
    bodies: list[str] = []

    def body(value: str) -> str:
        bodies.append(value)
        return value

    target = Tool(name="lookup", description="Lookup.", func=body)

    def spec() -> dict[str, Any]:
        return {"model": model(call_message({name: "x"}))}

    adapter = make_adapter(lambda _t, _s: [target], spec, spec)
    _, box, _ = boundary(adapter)
    with pytest.raises(HarnessError, match="reserved boundary argument name"):
        adapter.baseline({"input": "x"}, box, random.Random())
    assert bodies == [] and box.recording == ()


def test_binding_failure_on_later_attempt_stays_setup_error() -> None:
    """P3a3 item 1: pre-provider inner failures are setup even after a prior model call."""

    class BindingFailure(ScriptedModel):
        def bind_tools(self, tools: Any, **kwargs: Any) -> Any:
            if self.attempts:
                raise ValueError("later binding failed")
            return self

    scripted = BindingFailure(responses=[], script=[call_message({"key": "x"})])

    def body(key: str) -> str:
        return key

    target = StructuredTool.from_function(
        body, name="lookup", description="Lookup.", args_schema=Input
    )
    adapter = make_adapter(lambda _t, _s: [target], lambda: {"model": scripted}, lambda: {})
    _, box, _ = boundary(adapter)
    with pytest.raises(HarnessError, match="agent setup failed: ValueError: later binding failed"):
        adapter.baseline({"input": "x"}, box, random.Random())
    assert box.harness_fault and scripted.attempts == 1 and box.tool_calls == 1


def test_gate_idle_clock_resets_after_call(monkeypatch: pytest.MonkeyPatch) -> None:
    """P3a3 item 8: an idle waiter gets the full interval after a long predecessor."""
    clock = [0.0]
    monkeypatch.setattr(implementation.time, "monotonic", lambda: clock[0])
    box = ToolBox({}, Budgets(), lambda _k, _p: None)
    session = vars(implementation)["_Session"](box)
    outer = vars(implementation)["_Outer"](session)
    session.indices = {"first": 0, "missing": 1, "third": 2}

    def request(call_id: str) -> ToolCallRequest:
        return ToolCallRequest(
            tool_call={"name": "lookup", "args": {}, "id": call_id, "type": "tool_call"},
            tool=None,
            state={},
            runtime=cast(Any, None),
        )

    def long_call(req: ToolCallRequest) -> ToolMessage:
        clock[0] = 100.0
        return ToolMessage(content="ok", tool_call_id="first")

    outer.wrap_tool_call(request("first"), long_call)
    waits: list[float] = []

    def wait(timeout: float | None = None) -> None:
        assert timeout is not None
        waits.append(timeout)
        clock[0] += timeout

    monkeypatch.setattr(session.condition, "wait", wait)
    with pytest.raises(HarnessError, match="tool order wait timeout"):
        outer.wrap_tool_call(request("third"), long_call)
    assert waits == [implementation.WAIT_SECONDS]
    assert clock[0] == 100.0 + implementation.WAIT_SECONDS
