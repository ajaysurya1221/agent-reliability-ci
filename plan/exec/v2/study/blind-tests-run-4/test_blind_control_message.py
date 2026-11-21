"""Blind contract tests for the run 4 control-message arms."""

import json
import sys
from collections.abc import Callable, Iterator
from importlib import import_module
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Literal, Protocol

import pytest
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage

FOLDER = Path(__file__).resolve().parents[1] / "order-desk-control-message"
AUDIT = "ORDER_DESK_EMPTY_TEXT_AUDIT"
PREFIX = "lookup_order returned an empty result."
EXPLICIT = PREFIX + " Call lookup_order again with the same order_id."
NEUTRAL = PREFIX + " This lookup_order result is for the supplied order_id."
ARMS = ((False, "baseline", EXPLICIT), (True, "candidate", NEUTRAL))


@pytest.fixture
def agent(monkeypatch: pytest.MonkeyPatch) -> Iterator[ModuleType]:
    for variable in ("ARCI_QUICKSTART_BASELINE", "ARCI_QUICKSTART_CANDIDATE", AUDIT):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.syspath_prepend(str(FOLDER))
    monkeypatch.delitem(sys.modules, "agent", raising=False)
    try:
        yield import_module("agent")
    finally:
        sys.modules.pop("agent", None)


@pytest.fixture
def audit_path(agent: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    path = tmp_path / "audit.jsonl"
    monkeypatch.setenv(AUDIT, str(path))
    return path


class Wrapper(Protocol):
    def wrap_tool_call(
        self, request: SimpleNamespace, handler: Callable[[object], object]
    ) -> object: ...


def message(
    content: str = "null",
    *,
    name: str | None = "lookup_order",
    call_id: str = "lookup-37",
    status: Literal["success", "error"] = "success",
) -> ToolMessage:
    return ToolMessage(content=content, name=name, tool_call_id=call_id, status=status)


def invoke(middleware: Wrapper, original: object, *, tool: str = "lookup_order") -> object:
    call_id = getattr(original, "tool_call_id", "lookup-37")
    request = SimpleNamespace(tool_call={"name": tool, "id": call_id, "args": {"order_id": "o-9"}})
    calls: list[object] = []

    def handler(received: object) -> object:
        calls.append(received)
        return original

    result = middleware.wrap_tool_call(request, handler)
    assert len(calls) == 1
    assert calls[0] is request
    return result


def check_replacement(middleware: Wrapper, original: ToolMessage, text: str) -> None:
    fields = (original.tool_call_id, original.name, original.status)
    result = invoke(middleware, original)
    assert isinstance(result, ToolMessage)
    assert result is not original
    assert result.content == text
    assert (result.tool_call_id, result.name, result.status) == fields


def check_passthrough(
    agent: ModuleType, audit_path: Path, original: object, *, tool: str = "lookup_order"
) -> None:
    for _, arm, text in ARMS:
        before = original.model_copy(deep=True) if isinstance(original, ToolMessage) else original
        assert invoke(agent.ReplaceEmptyLookup(text, arm), original, tool=tool) is original
        assert original == before
        assert not audit_path.exists() or audit_path.read_bytes() == b""


def test_explicit_text(agent: ModuleType) -> None:
    assert agent.EXPLICIT_TEXT == EXPLICIT


def test_neutral_text(agent: ModuleType) -> None:
    assert agent.NEUTRAL_TEXT == NEUTRAL


def test_text_properties(agent: ModuleType) -> None:
    explicit, neutral = agent.EXPLICIT_TEXT, agent.NEUTRAL_TEXT
    assert explicit != neutral
    for text in (explicit, neutral):
        assert text.startswith(PREFIX)
        assert "null" not in text
    assert "Call lookup_order again" in explicit
    assert "Call lookup_order again" not in neutral


def test_middleware_attributes(agent: ModuleType) -> None:
    for _, arm, text in ARMS:
        middleware = agent.ReplaceEmptyLookup(text, arm)
        assert (middleware.text, middleware.arm) == (text, arm)
        assert isinstance(middleware, AgentMiddleware)


def test_both_texts_through_each_arm(agent: ModuleType) -> None:
    for _, arm, _ in ARMS:
        for text in (EXPLICIT, NEUTRAL):
            check_replacement(agent.ReplaceEmptyLookup(text, arm), message(), text)


def test_whitespace_null(agent: ModuleType) -> None:
    check_replacement(agent.ReplaceEmptyLookup(NEUTRAL, "candidate"), message(" null\n"), NEUTRAL)


def test_preserves_result_fields(agent: ModuleType) -> None:
    for name in (None, "result-name"):
        original = message(name=name, call_id="id-from-result")
        check_replacement(agent.ReplaceEmptyLookup(EXPLICIT, "baseline"), original, EXPLICIT)


def test_wrong_request_tool(agent: ModuleType, audit_path: Path) -> None:
    check_passthrough(agent, audit_path, message(), tool="refund_order")


def test_non_tool_message(agent: ModuleType, audit_path: Path) -> None:
    lookalike = SimpleNamespace(
        content="null", status="success", name="lookup_order", tool_call_id="fake-id"
    )
    for original in (lookalike, None):
        check_passthrough(agent, audit_path, original)


def test_error_status(agent: ModuleType, audit_path: Path) -> None:
    check_passthrough(agent, audit_path, message(status="error"))


def test_non_null_content(agent: ModuleType, audit_path: Path) -> None:
    for content in ("", "NULL", '"null"', "null order", '{"order_id":"o-9"}'):
        check_passthrough(agent, audit_path, message(content))


def test_audit_appends_each_replacement(agent: ModuleType, audit_path: Path) -> None:
    for _, arm, text in ARMS:
        original = message(call_id=f"call-{arm}")
        check_replacement(agent.ReplaceEmptyLookup(text, arm), original, text)

    rows = [json.loads(line) for line in audit_path.read_text().splitlines()]
    assert [(row["tool"], row["tool_call_id"], row["arm"]) for row in rows] == [
        ("lookup_order", "call-baseline", "baseline"),
        ("lookup_order", "call-candidate", "candidate"),
    ]


def test_audit_write_failure(
    agent: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(AUDIT, str(tmp_path))  # A directory cannot be opened as a JSONL file.
    check_replacement(agent.ReplaceEmptyLookup(NEUTRAL, "candidate"), message(), NEUTRAL)


def test_settings_for_each_arm(agent: ModuleType) -> None:
    for candidate, arm, text in ARMS:
        settings = agent.settings(candidate)
        assert isinstance(settings, dict)
        assert {"model", "middleware", "system_prompt"} <= settings.keys()
        assert settings["model"] is not None
        chain = settings["middleware"]
        assert isinstance(chain, list)
        assert sum(isinstance(item, agent.ReplaceEmptyLookup) for item in chain) == 1
        assert isinstance(chain[-1], agent.ReplaceEmptyLookup)
        assert (chain[-1].arm, chain[-1].text) == (arm, text)
        check_replacement(chain[-1], message(), text)


def test_middleware_class_order(agent: ModuleType) -> None:
    baseline = agent.settings(False)["middleware"]
    candidate = agent.settings(True)["middleware"]
    assert [type(item).__name__ for item in baseline] == [type(item).__name__ for item in candidate]


def test_shared_retry_prompt(agent: ModuleType) -> None:
    prompt = agent.settings(False)["system_prompt"]
    assert prompt == agent.settings(True)["system_prompt"]
    assert prompt.endswith("Retry an empty lookup once.")


def test_settings_helpers(agent: ModuleType) -> None:
    for candidate, helper in ((False, agent.baseline_settings), (True, agent.candidate_settings)):
        expected = agent.settings(candidate)
        actual = helper()
        assert actual["system_prompt"] == expected["system_prompt"]
        assert [m.text for m in actual["middleware"] if hasattr(m, "text")] == [
            m.text for m in expected["middleware"] if hasattr(m, "text")
        ]
