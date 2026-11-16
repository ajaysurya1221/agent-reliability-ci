"""Blind interface tests for R5; runnable with pytest or as a plain Python script."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from tempfile import mkdtemp
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from langchain.agents.middleware import ToolRetryMiddleware
from langchain_core.messages import ToolMessage

STUDY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STUDY))

from agent import (  # noqa: E402 -- support direct execution from any working directory.
    EMPTY_LOOKUP_TEXT,
    ExplainEmptyLookup,
    ReturnToolErrors,
    settings,
)
from offline_model import OfflineModel  # noqa: E402

EXPECTED_TEXT = (
    "lookup_order returned an empty result. Call lookup_order again with the same order_id."
)
AUDIT_VARIABLE = "ORDER_DESK_EMPTY_TEXT_AUDIT"


def _invoke(result: Any, tool: str = "lookup_order") -> Any:
    request = SimpleNamespace(
        tool_call={"name": tool, "id": "request-id", "args": {"order_id": "O-101"}}
    )
    requests: list[object] = []

    def handler(received: object) -> Any:
        requests.append(received)
        return result

    returned = ExplainEmptyLookup().wrap_tool_call(request, handler)
    assert requests == [request], "every result must invoke the handler exactly once"
    return returned


def _null_message(content: str = "null", name: str | None = "lookup_order") -> ToolMessage:
    return ToolMessage(content=content, tool_call_id="result-id", name=name, status="success")


def _assert_replacement(returned: Any, original: ToolMessage) -> None:
    assert isinstance(returned, ToolMessage)
    assert returned is not original
    assert returned.content == EXPECTED_TEXT
    assert returned.tool_call_id == original.tool_call_id
    assert returned.name == original.name
    assert returned.status == original.status
    assert original.content in ("null", " \nnull\t ")


def _audit_directory() -> Path:
    root = STUDY / "_offline"
    root.mkdir(exist_ok=True)
    # Keep supporting audit artifacts; a subsequent run uses a new directory.
    return Path(mkdtemp(prefix="middleware-audit-", dir=root))


def test_null_lookup_replaced_once_with_metadata_preserved() -> None:
    assert EMPTY_LOOKUP_TEXT == EXPECTED_TEXT
    with patch.dict(os.environ, {}, clear=True):
        for content in ("null", " \nnull\t "):
            for name in ("lookup_order", None):
                original = _null_message(content, name)
                _assert_replacement(_invoke(original), original)


def test_order_lookup_passes_through_same_object() -> None:
    result = ToolMessage(
        content='{"order_id": "O-101", "total_cents": 1200}',
        tool_call_id="order-result",
        name="lookup_order",
    )
    with patch.dict(os.environ, {}, clear=True):
        assert _invoke(result) is result


def test_other_tool_null_passes_through_same_object() -> None:
    result = _null_message(name="lookup_stock")
    with patch.dict(os.environ, {}, clear=True):
        assert _invoke(result, tool="lookup_stock") is result


def test_error_result_passes_through_same_object() -> None:
    result = ToolMessage(
        content="null", tool_call_id="error-result", name="lookup_order", status="error"
    )
    with patch.dict(os.environ, {}, clear=True):
        assert _invoke(result) is result


def test_unrecognised_result_passes_through_same_object() -> None:
    results: tuple[object, ...] = (None, object(), "null", {"content": "null"}, ["null"])
    with patch.dict(os.environ, {}, clear=True):
        for result in results:
            assert _invoke(result) is result
        for content in ("", "NULL", "None", '"null"', "[]", "{}"):
            message = _null_message(content)
            assert _invoke(message) is message
        blocks = ToolMessage(content=[{"type": "text", "text": "null"}], tool_call_id="b")
        assert _invoke(blocks) is blocks


def test_audit_appends_only_for_replacements() -> None:
    audit = _audit_directory() / "audit.jsonl"
    previous = {"existing": True}
    audit.write_text(json.dumps(previous) + "\n", encoding="utf-8")
    with patch.dict(os.environ, {AUDIT_VARIABLE: str(audit)}, clear=True):
        for identifier in ("first", "second"):
            result = ToolMessage(content="null", tool_call_id=identifier, name="lookup_order")
            _assert_replacement(_invoke(result), result)
        other = _null_message(name="lookup_stock")
        assert _invoke(other, tool="lookup_stock") is other
        order = ToolMessage(content='{"order_id": "O-101"}', tool_call_id="order")
        assert _invoke(order) is order
        error = ToolMessage(content="null", tool_call_id="error", status="error")
        assert _invoke(error) is error
        unknown = object()
        assert _invoke(unknown) is unknown
    assert [json.loads(line) for line in audit.read_text(encoding="utf-8").splitlines()] == [
        previous,
        {"tool": "lookup_order", "tool_call_id": "first"},
        {"tool": "lookup_order", "tool_call_id": "second"},
    ]


def test_unset_audit_does_not_open_a_file() -> None:
    result = _null_message()
    with (
        patch.dict(os.environ, {}, clear=True),
        patch("builtins.open") as builtin_open,
        patch("pathlib.Path.open") as path_open,
        patch("io.open") as io_open,
    ):
        _assert_replacement(_invoke(result), result)
        builtin_open.assert_not_called()
        path_open.assert_not_called()
        io_open.assert_not_called()


def test_audit_write_failure_does_not_change_message() -> None:
    directory = _audit_directory()
    # Both a missing parent and a directory are deterministic write failures,
    # including when tests run with elevated filesystem permissions.
    for target in (directory / "missing-parent" / "audit.jsonl", directory):
        with patch.dict(os.environ, {AUDIT_VARIABLE: str(target)}, clear=True):
            result = _null_message()
            _assert_replacement(_invoke(result), result)
    assert list(directory.iterdir()) == []


def test_only_baseline_has_explanation_middleware_offline() -> None:
    with patch.dict(os.environ, {}, clear=True):
        baseline = settings(candidate=False)
        candidate = settings(candidate=True)
    baseline_middleware = baseline["middleware"]
    candidate_middleware = candidate["middleware"]
    assert [type(item) for item in baseline_middleware] == [
        ToolRetryMiddleware,
        ReturnToolErrors,
        ExplainEmptyLookup,
    ]
    assert [type(item) for item in candidate_middleware] == [ToolRetryMiddleware, ReturnToolErrors]
    assert isinstance(baseline["model"], OfflineModel)
    assert isinstance(candidate["model"], OfflineModel)
    assert baseline["system_prompt"] == candidate["system_prompt"]
    assert baseline["system_prompt"].endswith("Retry an empty lookup once.")


def main() -> None:
    tests = (
        test_null_lookup_replaced_once_with_metadata_preserved,
        test_order_lookup_passes_through_same_object,
        test_other_tool_null_passes_through_same_object,
        test_error_result_passes_through_same_object,
        test_unrecognised_result_passes_through_same_object,
        test_audit_appends_only_for_replacements,
        test_unset_audit_does_not_open_a_file,
        test_audit_write_failure_does_not_change_message,
        test_only_baseline_has_explanation_middleware_offline,
    )
    for test in tests:
        test()
    print(f"{len(tests)} middleware tests passed")


if __name__ == "__main__":
    main()
