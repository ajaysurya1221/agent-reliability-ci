"""Replay fidelity regressions from P3a2."""

from __future__ import annotations

import importlib.util
import os
import random
from collections.abc import Callable
from typing import Any

import pytest

if importlib.util.find_spec("langchain") is None:
    if os.environ.get("ARCI_REQUIRE_ADAPTERS") == "1":
        raise ImportError("ARCI_REQUIRE_ADAPTERS=1 requires LangChain")
    pytest.skip("optional LangChain extra is absent", allow_module_level=True)
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import StructuredTool

from arci.adapters.langchain import make_adapter
from arci.perturb import REGISTRY, build
from arci.schema import DECISION_TOOL, Bucket, Budgets, FaultSpec, ToolMode
from arci.toolbox import HarnessError, ToolBox, format_diagnostic
from tests.unit.adapters.fixtures import call_message, model
from tests.unit.adapters.test_core import boundary


class PrefixError(Exception):
    def __str__(self) -> str:
        return "prefixed: " + super().__str__()


@pytest.mark.parametrize(
    "error", [KeyError("zzz"), KeyError(17), KeyError(("a", "b")), KeyError(), PrefixError("x")]
)
def test_rebuilt_diagnostic_is_exact_or_rejected(error: Exception) -> None:
    """Findings 8, 9, 15, 27: a reconstructed crash must keep the recorded fingerprint."""

    def body(key: str) -> str:
        raise error

    def spec() -> dict[str, Any]:
        return {"model": model(call_message({"key": "x"}))}

    adapter = make_adapter(
        lambda _t, _s: [StructuredTool.from_function(body, name="lookup", description="Lookup.")],
        spec,
        spec,
        error_types=[PrefixError],
    )
    _, live, _ = boundary(adapter)
    with pytest.raises(type(error)):
        adapter.baseline({"input": "x"}, live, random.Random())
    _, replayed, _ = boundary(adapter, recording=live.recording)
    if isinstance(error, PrefixError) or error.args in ((), (17,)):
        with pytest.raises(HarnessError, match="unreconstructable tool error"):
            adapter.baseline({"input": "x"}, replayed, random.Random())
        assert replayed.harness_fault
    else:
        with pytest.raises(type(error)) as caught:
            adapter.baseline({"input": "x"}, replayed, random.Random())
        assert format_diagnostic(caught.value) == live.recording[0].result.error_detail
        replayed.assert_replay_consumed()


def test_declared_error_type_overrides_builtin_name() -> None:
    """Finding 30: user error_types takes precedence over same-named builtins."""
    shadow = type("ValueError", (Exception,), {})
    original = shadow("user failure")

    def body(key: str) -> str:
        raise original

    def spec() -> dict[str, Any]:
        return {"model": model(call_message({"key": "x"}))}

    adapter = make_adapter(
        lambda _t, _s: [StructuredTool.from_function(body, name="lookup", description="Lookup.")],
        spec,
        spec,
        error_types=[shadow],
    )
    _, live, _ = boundary(adapter)
    with pytest.raises(shadow):
        adapter.baseline({"input": "x"}, live, random.Random())
    _, replayed, _ = boundary(adapter, recording=live.recording)
    with pytest.raises(shadow) as caught:
        adapter.baseline({"input": "x"}, replayed, random.Random())
    assert format_diagnostic(caught.value) == live.recording[0].result.error_detail


@pytest.mark.parametrize("fault", list(REGISTRY))
@pytest.mark.parametrize("raising", [False, True])
@pytest.mark.parametrize("mode", [ToolMode.RECORD, ToolMode.LIVE])
def test_every_builtin_fault_has_same_live_and_replay_branch(
    fault: str, raising: bool, mode: ToolMode
) -> None:
    """Findings 22, 26: empty_result preserves real errors; all builtins have branch parity."""
    name = DECISION_TOOL if fault.startswith("decision_") else "lookup"
    bodies: list[str] = []
    observations: list[tuple[str, str]] = []

    def body(key: str) -> Any:
        bodies.append(key)
        if raising:
            raise KeyError("zzz")
        if name == DECISION_TOOL:
            return {
                "body": {
                    "answers": {"pick": {"type": "choice", "probabilities": {"a": 0.9, "b": 0.1}}}
                }
            }
        return key

    class Catch(AgentMiddleware[Any, Any, Any]):
        def wrap_tool_call(self, request: Any, handler: Callable[[Any], Any]) -> Any:
            try:
                result = handler(request)
                observations.append(("success", result.content))
                return result
            except Exception as exc:
                observations.append((type(exc).__name__, format_diagnostic(exc)))
                return ToolMessage(content="caught", tool_call_id=request.tool_call["id"])

    def spec() -> dict[str, Any]:
        return {
            "model": model(call_message({"key": "x"}, name=name), AIMessage(content="done")),
            "middleware": [Catch()],
        }

    adapter = make_adapter(
        lambda _t, _s: [StructuredTool.from_function(body, name=name, description="Lookup.")],
        spec,
        spec,
    )
    world = adapter.toolset({}, 1)
    fault_spec = FaultSpec(name=fault, bucket=Bucket.FALSIFY, tool=name)
    recorded = ToolBox(
        world.tools, Budgets(), lambda _kind, _payload: None, perturbations=[build(fault_spec)]
    )
    adapter.baseline({"input": "x"}, recorded, random.Random())
    assert recorded.recording[0].result.injected_by == fault
    expected = observations[-1]
    if mode is ToolMode.LIVE:
        live = ToolBox(
            world.tools,
            Budgets(),
            lambda _kind, _payload: None,
            mode=mode,
            perturbations=[build(fault_spec)],
        )
        adapter.baseline({"input": "x"}, live, random.Random())
        assert observations[-1] == expected
    before = len(bodies)
    replayed = ToolBox(
        {},
        Budgets(),
        lambda _kind, _payload: None,
        mode=ToolMode.REPLAY,
        recording=recorded.recording,
    )
    adapter.baseline({"input": "x"}, replayed, random.Random())
    assert observations[-1] == expected
    assert len(bodies) == before
    replayed.assert_replay_consumed()
    if raising and fault == "empty_result":
        assert expected == ("KeyError", "KeyError: 'zzz'")


@pytest.mark.parametrize("injected_index", [0, 1])
def test_mixed_real_and_injected_replay_advances_attempt_index(injected_index: int) -> None:
    """Finding 31b: reconstruction must use this attempt, not recording[0]."""
    observed: list[str] = []
    bodies: list[str] = []

    def body(key: str) -> str:
        bodies.append(key)
        raise ValueError("real")

    class Catch(AgentMiddleware[Any, Any, Any]):
        def wrap_tool_call(self, request: Any, handler: Callable[[Any], Any]) -> Any:
            try:
                return handler(request)
            except Exception as exc:
                observed.append(type(exc).__name__)
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
    world = adapter.toolset({}, 1)
    box = ToolBox(
        world.tools,
        Budgets(),
        lambda _kind, _payload: None,
        perturbations=[
            build(
                FaultSpec(
                    name="tool_error_once", bucket=Bucket.FALSIFY, at_occurrence=injected_index
                )
            )
        ],
    )
    adapter.baseline({"input": "x"}, box, random.Random())
    replayed = ToolBox(
        {}, Budgets(), lambda _kind, _payload: None, mode=ToolMode.REPLAY, recording=box.recording
    )
    adapter.baseline({"input": "x"}, replayed, random.Random())
    expected = ["ToolFault", "ValueError"] if injected_index == 0 else ["ValueError", "ToolFault"]
    assert observed == expected * 2 and len(bodies) == 1
    replayed.assert_replay_consumed()
