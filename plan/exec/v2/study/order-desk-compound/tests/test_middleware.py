"""Exercise each arm's configured middleware without a model provider."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock, patch

import pytest
from langchain.agents.middleware import ToolRetryMiddleware
from langchain_core.messages import AIMessage, ToolMessage

STUDY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STUDY))

from agent import (  # noqa: E402
    GENERIC_TEXT,
    ReplaceEmptyLookup,
    ReturnToolErrors,
    ScriptedOpening,
    settings,
)
from offline_model import OfflineModel  # noqa: E402

AUDIT_VARIABLE = "ORDER_DESK_EMPTY_TEXT_AUDIT"


@pytest.fixture
def replacement(monkeypatch: pytest.MonkeyPatch) -> ReplaceEmptyLookup:
    for var in ("BASELINE", "CANDIDATE", "TEMPERATURE"):
        monkeypatch.delenv(f"ARCI_QUICKSTART_{var}", raising=False)
    monkeypatch.delenv(AUDIT_VARIABLE, raising=False)
    middleware = settings(candidate=False)["middleware"][-1]
    assert isinstance(middleware, ReplaceEmptyLookup)
    assert middleware.arm == "baseline"
    return middleware


def _invoke(middleware: ReplaceEmptyLookup, result: Any, tool: str = "lookup_order") -> Any:
    request = SimpleNamespace(
        tool_call={"name": tool, "id": "request-id", "args": {"order_id": "O-101"}}
    )
    requests: list[object] = []

    def handler(received: object) -> Any:
        requests.append(received)
        return result

    returned = middleware.wrap_tool_call(request, handler)
    assert requests == [request]
    return returned


def _null_message(content: str = "null", name: str | None = "lookup_order") -> ToolMessage:
    return ToolMessage(content=content, tool_call_id="result-id", name=name, status="success")


def _assert_replacement(middleware: ReplaceEmptyLookup, original: ToolMessage) -> None:
    returned = _invoke(middleware, original)
    assert isinstance(returned, ToolMessage)
    assert returned is not original
    assert returned.content == GENERIC_TEXT
    assert returned.tool_call_id == original.tool_call_id
    assert returned.name == original.name
    assert returned.status == original.status
    assert original.content in ("null", " \nnull\t ")


def test_null_lookup_replaced_once_with_metadata_preserved(replacement: ReplaceEmptyLookup) -> None:
    for content in ("null", " \nnull\t "):
        for name in ("lookup_order", None):
            _assert_replacement(replacement, _null_message(content, name))


def test_other_results_pass_through_without_audit(
    replacement: ReplaceEmptyLookup, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    audit = tmp_path / "audit.jsonl"
    monkeypatch.setenv(AUDIT_VARIABLE, str(audit))
    for content in ('{"order_id": "O-101"}', "", "NULL", "None", '"null"', "[]", "{}"):
        result = _null_message(content)
        assert _invoke(replacement, result) is result
    other = _null_message(name="lookup_stock")
    assert _invoke(replacement, other, "lookup_stock") is other
    error = ToolMessage(content="null", tool_call_id="e", name="lookup_order", status="error")
    assert _invoke(replacement, error) is error
    blocks = ToolMessage(content=[{"type": "text", "text": "null"}], tool_call_id="b")
    assert _invoke(replacement, blocks) is blocks
    for unknown in (None, object(), "null", {"content": "null"}, ["null"]):
        assert _invoke(replacement, unknown) is unknown
    assert not audit.exists()


def test_audit_appends_replacements(
    replacement: ReplaceEmptyLookup, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    audit = tmp_path / "audit.jsonl"
    audit.write_text('{"existing": true}\n', encoding="utf-8")
    monkeypatch.setenv(AUDIT_VARIABLE, str(audit))
    for identifier in ("first", "second"):
        _assert_replacement(replacement, ToolMessage(content="null", tool_call_id=identifier))
    assert [json.loads(line) for line in audit.read_text().splitlines()] == [
        {"existing": True},
        {"tool": "lookup_order", "tool_call_id": "first", "arm": replacement.arm},
        {"tool": "lookup_order", "tool_call_id": "second", "arm": replacement.arm},
    ]


def test_unset_audit_does_not_open_a_file(replacement: ReplaceEmptyLookup) -> None:
    with patch("builtins.open") as builtin_open, patch("io.open") as io_open:
        _assert_replacement(replacement, _null_message())
        builtin_open.assert_not_called()
        io_open.assert_not_called()


def test_unwritable_audit_preserves_message(
    replacement: ReplaceEmptyLookup, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for target in (tmp_path / "missing-parent" / "audit.jsonl", tmp_path):
        monkeypatch.setenv(AUDIT_VARIABLE, str(target))
        _assert_replacement(replacement, _null_message())
    assert list(tmp_path.iterdir()) == []


def test_same_middleware_order_and_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    for variable in ("BASELINE", "CANDIDATE", "TEMPERATURE"):
        monkeypatch.delenv(f"ARCI_QUICKSTART_{variable}", raising=False)
    baseline, candidate = settings(False), settings(True)
    assert GENERIC_TEXT == (
        "The previous tool call returned an empty result. Repeat that call with the same input."
    )
    shared = [ScriptedOpening, ToolRetryMiddleware, ReturnToolErrors]
    assert [type(m) for m in baseline["middleware"]] == [*shared, ReplaceEmptyLookup]
    assert [type(m) for m in candidate["middleware"]] == shared
    replacement = baseline["middleware"][-1]
    assert (replacement.arm, replacement.text) == ("baseline", GENERIC_TEXT)
    assert all(isinstance(config["model"], OfflineModel) for config in (baseline, candidate))
    assert baseline["system_prompt"] == candidate["system_prompt"]
    assert baseline["system_prompt"].endswith("Retry an empty lookup once.")


def test_scripted_turns_emit_calls_then_delegate_with_original_history() -> None:
    opening = ScriptedOpening()
    request = Mock()
    request.state = {"order_id": "ORD-456"}
    handler = Mock()
    for length, tool, args in (
        (1, "check_stock", {"sku": "ORD-456"}),
        (3, "lookup_order", {"order_id": "ORD-456"}),
    ):
        request.messages = [object() for _ in range(length)]
        result = opening.wrap_model_call(request, handler)
        assert isinstance(result, AIMessage)
        (call,) = result.tool_calls
        assert call["name"] == tool and call["args"] == args and call["id"]
        handler.assert_not_called()
    for length in (5, 7, 9):
        request.messages = [object() for _ in range(length)]
        assert opening.wrap_model_call(request, handler) is handler.return_value
        handler.assert_called_once_with(request)
        handler.reset_mock()
