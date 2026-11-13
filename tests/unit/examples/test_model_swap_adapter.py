"""Model swap and optional error feedback, using only in-process fake models."""

from __future__ import annotations

import importlib
import importlib.util
import os
import random
from collections.abc import Callable
from typing import Any

import pytest

from tests.unit.examples.test_langchain_quickstart import EXAMPLE

if importlib.util.find_spec("langchain") is None:
    if os.environ.get("ARCI_REQUIRE_ADAPTERS") == "1":
        raise ImportError("ARCI_REQUIRE_ADAPTERS=1 requires LangChain")
    pytest.skip("optional LangChain extra is absent", allow_module_level=True)

from arci.adapters.langchain import make_adapter
from tests.unit.adapters.fixtures import call_message, model
from tests.unit.adapters.test_core import boundary

# Optional imports stay dynamic so the base environment can type-check this file.
# Runtime coverage is also required in the separate adapter environment.
middleware_module = importlib.import_module("langchain.agents.middleware")
AgentMiddleware = middleware_module.AgentMiddleware
ToolRetryMiddleware = middleware_module.ToolRetryMiddleware
messages_module = importlib.import_module("langchain_core.messages")
AIMessage = messages_module.AIMessage
ToolMessage = messages_module.ToolMessage
StructuredTool = importlib.import_module("langchain_core.tools").StructuredTool


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.syspath_prepend(str(EXAMPLE))
    for name in ("BASELINE", "CANDIDATE", "TEMPERATURE"):
        monkeypatch.delenv(f"ARCI_QUICKSTART_{name}", raising=False)
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGSMITH_TRACING_V2", "false")


@pytest.mark.parametrize(
    "ids,retries",
    [
        ((None, None), (1, 0)),
        (("fake:same", "fake:same"), (1, 0)),
        (("fake:first", "fake:second"), (1, 1)),
        (("ollama:first", "ollama:second"), (1, 1)),
        (("ollama:first", "fake:second"), (1, 1)),
    ],
)
def test_arm_settings_only_change_model_or_retry(
    monkeypatch: pytest.MonkeyPatch,
    ids: tuple[str | None, str | None],
    retries: tuple[int, int],
) -> None:
    agent = importlib.import_module("agent")
    calls: list[tuple[str, dict[str, Any]]] = []

    def fake_model(identifier: str, **kwargs: Any) -> object:
        calls.append((identifier, kwargs))
        return object()

    monkeypatch.setattr(agent, "init_chat_model", fake_model)
    for arm, identifier in zip(("BASELINE", "CANDIDATE"), ids, strict=True):
        if identifier is not None:
            monkeypatch.setenv(f"ARCI_QUICKSTART_{arm}", identifier)
    baseline = agent.baseline_settings()
    candidate = agent.candidate_settings()
    baseline_model = baseline.pop("model")
    candidate_model = candidate.pop("model")
    if ids[0] is None:
        assert baseline_model.model_dump() == candidate_model.model_dump()
        assert calls == []
    else:
        assert [identifier for identifier, _ in calls] == list(ids)
        for identifier, inference in calls:
            expected: dict[str, Any] = {"temperature": 0.7}
            if identifier.startswith("ollama:"):
                expected["reasoning"] = False
            assert inference == expected
    left, right = baseline.pop("middleware"), candidate.pop("middleware")
    assert len(left) == len(right) == 1
    assert type(left[0]) is type(right[0]) is ToolRetryMiddleware
    left_args, right_args = vars(left[0]).copy(), vars(right[0]).copy()
    assert (left_args.pop("max_retries"), right_args.pop("max_retries")) == retries
    assert left_args == right_args
    assert baseline == candidate


class ReturnToolErrors(AgentMiddleware):
    def wrap_tool_call(self, request: Any, handler: Callable[[Any], Any]) -> Any:
        try:
            return handler(request)
        except ValueError as exc:
            call = request.tool_call
            return ToolMessage(
                content=f"Error: {exc}",
                tool_call_id=call["id"],
                name=call["name"],
                status="error",
            )


@pytest.mark.parametrize("arm", ["baseline", "candidate"])
def test_returned_tool_error_reaches_next_turn_and_retains_failed_event(arm: str) -> None:
    def lookup(key: str) -> str:
        raise ValueError(f"unknown key: {key}")

    scripted = model(call_message({"key": "wrong"}), AIMessage(content="received error"))

    def settings() -> dict[str, Any]:
        return {
            "model": scripted,
            "middleware": [
                ToolRetryMiddleware(
                    max_retries=1,
                    initial_delay=0,
                    jitter=False,
                    retry_on=(TimeoutError, RuntimeError),
                    on_failure="continue",
                ),
                ReturnToolErrors(),
            ],
        }

    adapter = make_adapter(
        lambda _task, _seed: [StructuredTool.from_function(lookup, description="Lookup a key.")],
        settings,
        settings,
    )
    _, box, events = boundary(adapter)
    getattr(adapter, arm)({"input": "find answer"}, box, random.Random(7))
    feedback: list[Any] = [
        message for message in scripted.seen[-1] if isinstance(message, ToolMessage)
    ]
    assert len(feedback) == 1
    assert feedback[0].content == "Error: unknown key: wrong"
    assert feedback[0].status == "error"
    assert feedback[0].tool_call_id == "call-0"
    assert feedback[0].name == "lookup"
    assert len(box.recording) == 1
    assert not box.recording[0].result.ok
    assert box.recording[0].result.error_kind == "error"
    assert box.recording[0].result.error_detail == "ValueError: unknown key: wrong"
    finished = [payload for kind, payload in events if kind == "tool_finish"]
    assert len(finished) == 1
    assert finished[0]["ok"] is False
    assert finished[0]["error_kind"] == "error"
