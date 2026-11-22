"""Black-box controls from INTERFACE.md. The stand-in always claims success."""

from __future__ import annotations

import json
import random
from collections.abc import Sequence
from importlib import import_module
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import JsonValue

from arci.descriptor import loads_suite_descriptor
from arci.perturb import build
from arci.suite_schedule import build_suite_round
from arci.toolbox import ToolBox

ROOT = Path(__file__).resolve().parents[1] / "order-desk-compound"
GENERIC = "The previous tool call returned an empty result. Repeat that call with the same input."


class ClaimSuccess(FakeMessagesListChatModel):
    inputs: list[list[BaseMessage]]

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> ClaimSuccess:
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        self.inputs.append(messages)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="Done"))])


@pytest.mark.parametrize("inject", [True, False])
def test_public_entrypoints(inject: bool, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.syspath_prepend(str(ROOT))
    descriptor = ROOT / "arci.yaml"
    suite = loads_suite_descriptor(descriptor.read_text(), str(descriptor))
    agent = import_module("agent")
    assert Path(str(agent.__file__)).resolve() == ROOT / "agent.py"
    for spec in build_suite_round(suite, 1):
        audit = tmp_path / spec.trial_id
        registered = spec.task["quickstart_settings"]
        assert isinstance(registered, dict)
        for key in ("baseline", "candidate", "temperature"):
            monkeypatch.setenv("ARCI_QUICKSTART_" + key.upper(), str(registered[key]))
        monkeypatch.setenv("ORDER_DESK_EMPTY_TEXT_AUDIT", str(audit))
        model = ClaimSuccess(responses=[], inputs=[])
        monkeypatch.setattr(agent, "init_chat_model", Mock(return_value=model))
        world = agent.toolset(spec.task, spec.seed)
        events: list[tuple[str, dict[str, JsonValue]]] = []
        boundary = ToolBox(
            world.tools,
            spec.budgets,
            lambda k, p: events.append((k, p)),  # noqa: B023
            seed=spec.seed,
            perturbations=[build(f) for f in spec.condition.faults] if inject else [],
        )
        getattr(agent, spec.arm)(spec.task, boundary, random.Random(spec.seed))
        assert not import_module("check").check(spec.task, world.snapshot())
        assert [k for k, _ in events] == [
            "tool_start",
            "tool_finish",
            "tool_start",
            "tool_finish",
            "model_step",
        ]
        order_id = spec.task["order_id"]
        assert events[0][1]["arguments"] == {"sku": order_id}
        assert events[2][1]["arguments"] == {"order_id": order_id}
        wrong, lookup = boundary.recording
        assert wrong.tool == "check_stock" and not wrong.result.ok
        assert wrong.result.error_detail == "ValueError: unknown SKU"
        assert lookup.tool == "lookup_order" and lookup.occurrence == 0 and lookup.result.ok
        (messages,) = model.inputs
        assert [m.type for m in messages] == ["system", "human", "ai", "tool", "ai", "tool"]
        assert messages[1].text == spec.task["input"]
        for i, tool, args in (
            (2, "check_stock", {"sku": order_id}),
            (4, "lookup_order", {"order_id": order_id}),
        ):
            decision, reply = messages[i : i + 2]
            assert isinstance(decision, AIMessage) and isinstance(reply, ToolMessage)
            (call,) = decision.tool_calls
            assert (call["name"], call["args"], call["id"]) == (tool, args, reply.tool_call_id)
            assert reply.name == tool
        error, answer = messages[3], messages[5]
        assert isinstance(error, ToolMessage) and (error.status, error.text) == (
            "error",
            "Error: unknown SKU",
        )
        assert isinstance(answer, ToolMessage) and answer.status == "success"
        if inject:
            assert lookup.result.injected_by == "empty_result" and lookup.result.value is None
            assert answer.text == (GENERIC if spec.arm == "baseline" else "null")
        else:
            assert lookup.result.injected_by is None
            assert isinstance(lookup.result.value, dict)
            assert json.loads(answer.text) == lookup.result.value
        if inject and spec.arm == "baseline":
            assert [json.loads(line) for line in audit.read_text().splitlines()] == [
                {"arm": "baseline", "tool": "lookup_order", "tool_call_id": answer.tool_call_id}
            ]
        else:
            assert not audit.exists()
