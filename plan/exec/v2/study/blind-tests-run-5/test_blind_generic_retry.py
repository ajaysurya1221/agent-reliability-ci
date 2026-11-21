"""Blind contract tests for the explicit and generic retry instructions."""

import json
import sys
from collections.abc import Callable, Iterator
from importlib import import_module
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Literal, Protocol
from unittest.mock import Mock

import pytest
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage

TARGET = Path(__file__).resolve().parents[1] / "order-desk-generic-retry"
EXPLICIT = "lookup_order returned an empty result. Call lookup_order again with the same order_id."
GENERIC = "The previous tool call returned an empty result. Repeat that call with the same input."
ARMS = [(False, "baseline", EXPLICIT), (True, "candidate", GENERIC)]


@pytest.fixture
def audit_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> Path:
    path = tmp_path / "audit.jsonl"
    if getattr(request, "param", None) == "directory":
        path.mkdir()  # A directory cannot be appended to as a file.
    monkeypatch.setenv("ORDER_DESK_EMPTY_TEXT_AUDIT", str(path))
    return path


@pytest.fixture
def agent(audit_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[ModuleType]:
    monkeypatch.delenv("ARCI_QUICKSTART_BASELINE", raising=False)
    monkeypatch.delenv("ARCI_QUICKSTART_CANDIDATE", raising=False)
    monkeypatch.syspath_prepend(str(TARGET))
    monkeypatch.delitem(sys.modules, "agent", raising=False)
    try:
        yield import_module("agent")
    finally:
        sys.modules.pop("agent", None)


class Middleware(Protocol):
    def wrap_tool_call(
        self, request: SimpleNamespace, handler: Callable[[object], object]
    ) -> object: ...


def message(
    content: str = "null",
    *,
    name: str | None = "lookup_order",
    call_id: str = "call-42",
    status: Literal["success", "error"] = "success",
) -> ToolMessage:
    return ToolMessage(content=content, tool_call_id=call_id, name=name, status=status)


def invoke(
    middleware: Middleware,
    original: object,
    tool: str = "lookup_order",
    *,
    request_id: str | None = None,
) -> object:
    request = SimpleNamespace(
        tool_call={
            "name": tool,
            "id": request_id
            if request_id is not None
            else getattr(original, "tool_call_id", "call-42"),
            "args": {"order_id": "order-7"},
        }
    )
    handler = Mock(return_value=original)
    result = middleware.wrap_tool_call(request, handler)
    handler.assert_called_once_with(request)
    assert handler.call_args.args[0] is request
    return result


def assert_replacement(
    middleware: Middleware, original: ToolMessage, text: str, *, request_id: str | None = None
) -> None:
    fields = (original.tool_call_id, original.name, original.status)
    result = invoke(middleware, original, request_id=request_id)
    assert isinstance(result, ToolMessage)
    assert result is not original
    assert result.content == text
    assert (result.tool_call_id, result.name, result.status) == fields


def assert_passthrough(
    agent: ModuleType, audit_path: Path, original: object, tool: str = "lookup_order"
) -> None:
    for _, arm, text in ARMS:
        before = original.model_copy(deep=True) if isinstance(original, ToolMessage) else original
        assert invoke(agent.ReplaceEmptyLookup(text, arm), original, tool) is original
        assert original == before
        assert not audit_path.exists() or audit_path.read_bytes() == b""


def test_explicit_text(agent: ModuleType) -> None:
    assert agent.EXPLICIT_TEXT == EXPLICIT


def test_generic_text(agent: ModuleType) -> None:
    assert agent.GENERIC_TEXT == GENERIC


def test_text_lengths(agent: ModuleType) -> None:
    assert len(agent.EXPLICIT_TEXT) == len(agent.GENERIC_TEXT) == 86


def test_text_vocabulary(agent: ModuleType) -> None:
    for name in ("lookup_order", "order_id"):
        assert name in agent.EXPLICIT_TEXT
        assert name not in agent.GENERIC_TEXT
    for text in (agent.EXPLICIT_TEXT, agent.GENERIC_TEXT):
        assert "null" not in text


@pytest.mark.parametrize("arm", ["baseline", "candidate"])
@pytest.mark.parametrize("text", [EXPLICIT, GENERIC], ids=["explicit", "generic"])
def test_middleware_uses_supplied_text(agent: ModuleType, arm: str, text: str) -> None:
    middleware = agent.ReplaceEmptyLookup(text, arm)
    assert (middleware.text, middleware.arm) == (text, arm)
    assert_replacement(middleware, message(), text)
    assert isinstance(middleware, AgentMiddleware)


def test_whitespace_around_null(agent: ModuleType) -> None:
    middleware = agent.ReplaceEmptyLookup(GENERIC, "candidate")
    assert_replacement(middleware, message(" null\n"), GENERIC)


@pytest.mark.parametrize("name", [None, "result-alias"])
def test_preserves_result_metadata(agent: ModuleType, name: str | None) -> None:
    middleware = agent.ReplaceEmptyLookup(EXPLICIT, "baseline")
    assert_replacement(
        middleware, message(name=name, call_id="metadata-28"), EXPLICIT, request_id="request-19"
    )


def test_other_request_tool(agent: ModuleType, audit_path: Path) -> None:
    assert_passthrough(agent, audit_path, message(), tool="other_tool")


def test_non_tool_message(agent: ModuleType, audit_path: Path) -> None:
    lookalike = SimpleNamespace(
        content="null", status="success", name="lookup_order", tool_call_id="lookalike"
    )
    assert_passthrough(agent, audit_path, lookalike)


def test_error_with_null_content(agent: ModuleType, audit_path: Path) -> None:
    assert_passthrough(agent, audit_path, message(status="error"))


@pytest.mark.parametrize("content", ["", "NULL", '"null"', "null order", '{"order_id": "7"}'])
def test_other_content(agent: ModuleType, audit_path: Path, content: str) -> None:
    assert_passthrough(agent, audit_path, message(content))


def test_audit_appends_one_row_per_replacement(agent: ModuleType, audit_path: Path) -> None:
    for _, arm, text in ARMS:
        middleware = agent.ReplaceEmptyLookup(text, arm)
        assert_replacement(middleware, message(call_id=f"id-{arm}"), text)
        original = message("found")
        assert invoke(middleware, original) is original

    rows = [json.loads(line) for line in audit_path.read_text().splitlines()]
    assert [(row["tool"], row["tool_call_id"], row["arm"]) for row in rows] == [
        ("lookup_order", "id-baseline", "baseline"),
        ("lookup_order", "id-candidate", "candidate"),
    ]


@pytest.mark.parametrize("audit_path", ["directory"], indirect=True)
def test_unwritable_audit_path(agent: ModuleType, audit_path: Path) -> None:
    for _, arm, text in ARMS:
        assert_replacement(agent.ReplaceEmptyLookup(text, arm), message(), text)


@pytest.mark.parametrize(("candidate", "arm", "text"), ARMS)
def test_arm_settings(agent: ModuleType, candidate: bool, arm: str, text: str) -> None:
    settings = agent.settings(candidate)
    assert isinstance(settings, dict)
    assert {"middleware", "system_prompt", "model"} <= settings.keys()
    assert settings["model"] is not None
    chain = settings["middleware"]
    assert isinstance(chain, list)
    assert sum(isinstance(item, agent.ReplaceEmptyLookup) for item in chain) == 1
    assert isinstance(chain[-1], agent.ReplaceEmptyLookup)
    assert (chain[-1].text, chain[-1].arm) == (text, arm)
    assert_replacement(chain[-1], message(), text)


def test_middleware_class_order(agent: ModuleType) -> None:
    baseline = agent.settings(False)["middleware"]
    candidate = agent.settings(True)["middleware"]
    assert [type(item).__name__ for item in baseline] == [type(item).__name__ for item in candidate]


def test_shared_retry_prompt(agent: ModuleType) -> None:
    prompt = agent.settings(False)["system_prompt"]
    assert prompt == agent.settings(True)["system_prompt"]
    assert prompt.endswith("Retry an empty lookup once.")


@pytest.mark.parametrize(
    ("candidate", "helper"), [(False, "baseline_settings"), (True, "candidate_settings")]
)
def test_settings_helpers(agent: ModuleType, candidate: bool, helper: str) -> None:
    expected = agent.settings(candidate)
    actual = getattr(agent, helper)()
    assert actual["system_prompt"] == expected["system_prompt"]
    assert [m.text for m in actual["middleware"] if isinstance(m, agent.ReplaceEmptyLookup)] == [
        m.text for m in expected["middleware"] if isinstance(m, agent.ReplaceEmptyLookup)
    ]
