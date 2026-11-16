"""Blind tests for ``order-desk-empty-message/agent.py``.

Written only from the "Interface (fixed; ...)" section of
``plan/exec/v2/tasks/R5-run3-build.md``. This file never reads the folder under test; it
only imports the module ``agent`` from it at run time, through the ``FOLDER`` constant
below. Every test's docstring quotes the sentence of the interface section it checks.

Works both under pytest and as a plain script: ``python test_blind_empty_message.py``
calls every ``test_*`` function itself and prints a pass/fail summary, exiting 1 on any
failure.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage

# Locate the code under test. BLIND_FOLDER lets this file be pointed at a stand-in
# implementation while checking the tests themselves; it is otherwise unused.
FOLDER = (
    Path(os.environ["BLIND_FOLDER"]).resolve()
    if os.environ.get("BLIND_FOLDER")
    else Path(__file__).resolve().parents[1] / "order-desk-empty-message"
)

_ENV_VARS_TO_CLEAR = (
    "ARCI_QUICKSTART_BASELINE",
    "ARCI_QUICKSTART_CANDIDATE",
    "ARCI_QUICKSTART_TEMPERATURE",
)


def _load_agent() -> Any:
    """Import ``agent`` from FOLDER with the quickstart env vars removed first.

    Removing them makes ``configuration.resolve_settings()`` fall back to
    ``offline:scripted`` for both arms, so building ``settings()`` constructs an
    ``OfflineModel`` and calls no real model.
    """
    for name in _ENV_VARS_TO_CLEAR:
        os.environ.pop(name, None)
    folder_str = str(FOLDER)
    if folder_str in sys.path:
        sys.path.remove(folder_str)
    sys.path.insert(0, folder_str)
    if "agent" in sys.modules:
        del sys.modules["agent"]
    import agent  # noqa: PLC0415

    return agent


class _FakeRequest:
    """A stand-in for a ``ToolCallRequest``: only ``tool_call`` is used by the middleware."""

    def __init__(self, name: str, call_id: str = "call-1", args: dict | None = None) -> None:
        self.tool_call = {"name": name, "id": call_id, "args": args or {}}


class _RecordingHandler:
    """A stand-in handler: records how many times it is called and what it returns/raises."""

    def __init__(self, result: Any = None, exc: BaseException | None = None) -> None:
        self.result = result
        self.exc = exc
        self.calls = 0

    def __call__(self, request: Any) -> Any:
        self.calls += 1
        if self.exc is not None:
            raise self.exc
        return self.result


class _FakeCommand:
    """A stand-in for langgraph's ``Command``: some object that is not a ``ToolMessage``."""

    def __init__(self) -> None:
        self.update = {"messages": []}


class _env_var:
    """Context manager that sets/unsets a single environment variable and restores it."""

    def __init__(self, name: str, value: str | None) -> None:
        self.name = name
        self.value = value
        self._had = False
        self._old: str | None = None

    def __enter__(self) -> "_env_var":
        self._had = self.name in os.environ
        self._old = os.environ.get(self.name)
        if self.value is None:
            os.environ.pop(self.name, None)
        else:
            os.environ[self.name] = self.value
        return self

    def __exit__(self, *exc_info: object) -> None:
        if self._had:
            os.environ[self.name] = self._old  # type: ignore[assignment]
        else:
            os.environ.pop(self.name, None)


def _read_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    text = path.read_text()
    return [line for line in text.splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# EMPTY_LOOKUP_TEXT
# ---------------------------------------------------------------------------


def test_empty_lookup_text_exact() -> None:
    """`EMPTY_LOOKUP_TEXT: str`, exactly: `lookup_order returned an empty result. Call lookup_order again with the same order_id.`"""
    agent = _load_agent()
    assert agent.EMPTY_LOOKUP_TEXT == (
        "lookup_order returned an empty result. Call lookup_order again with the same order_id."
    )


# ---------------------------------------------------------------------------
# The replacement case
# ---------------------------------------------------------------------------


def test_null_lookup_is_replaced() -> None:
    """It returns a new ToolMessage with content=EMPTY_LOOKUP_TEXT and the same tool_call_id, name and status as the result."""
    agent = _load_agent()
    original = ToolMessage(content="null", tool_call_id="call-77", name="lookup_order", status="success")
    handler = _RecordingHandler(result=original)
    request = _FakeRequest("lookup_order", call_id="call-77")
    mw = agent.ExplainEmptyLookup()

    result = mw.wrap_tool_call(request, handler)

    assert isinstance(result, ToolMessage)
    assert result is not original
    assert result.content == agent.EMPTY_LOOKUP_TEXT
    assert result.tool_call_id == original.tool_call_id == "call-77"
    assert result.name == original.name == "lookup_order"
    assert result.status == original.status == "success"


def test_whitespace_around_null_still_counts() -> None:
    """Compare `str(content).strip() == "null"`: content with surrounding whitespace such as " null\\n" still counts."""
    agent = _load_agent()
    original = ToolMessage(content=" null\n", tool_call_id="call-2", name="lookup_order", status="success")
    handler = _RecordingHandler(result=original)
    request = _FakeRequest("lookup_order", call_id="call-2")
    mw = agent.ExplainEmptyLookup()

    result = mw.wrap_tool_call(request, handler)

    assert isinstance(result, ToolMessage)
    assert result.content == agent.EMPTY_LOOKUP_TEXT
    assert result.tool_call_id == "call-2"
    assert result.name == "lookup_order"
    assert result.status == "success"


def test_non_null_variants_pass_through() -> None:
    """Content `None`, `""`, `"nullx"`, `"{}"` and a JSON order do not count as the text `null`."""
    agent = _load_agent()
    non_matching_contents = [
        "None",
        "",
        "nullx",
        "{}",
        json.dumps({"order_id": "o-1", "total_cents": 1234}),
    ]
    for content in non_matching_contents:
        original = ToolMessage(
            content=content, tool_call_id="call-3", name="lookup_order", status="success"
        )
        handler = _RecordingHandler(result=original)
        request = _FakeRequest("lookup_order", call_id="call-3")
        mw = agent.ExplainEmptyLookup()

        result = mw.wrap_tool_call(request, handler)

        assert result is original, f"content {content!r} should pass through unchanged"


# ---------------------------------------------------------------------------
# "does nothing for other tools, for error results, or for a lookup that returned an order"
# ---------------------------------------------------------------------------


def test_other_tool_null_result_passes_through_unchanged() -> None:
    """It does nothing for other tools: a different tool whose result is the text null is returned unchanged."""
    agent = _load_agent()
    original = ToolMessage(content="null", tool_call_id="call-4", name="refund_order", status="success")
    handler = _RecordingHandler(result=original)
    request = _FakeRequest("refund_order", call_id="call-4")
    mw = agent.ExplainEmptyLookup()

    result = mw.wrap_tool_call(request, handler)

    assert result is original


def test_error_status_null_result_passes_through_unchanged() -> None:
    """It does nothing for error results: a lookup result with status "error" is returned unchanged even if its content is null."""
    agent = _load_agent()
    original = ToolMessage(content="null", tool_call_id="call-5", name="lookup_order", status="error")
    handler = _RecordingHandler(result=original)
    request = _FakeRequest("lookup_order", call_id="call-5")
    mw = agent.ExplainEmptyLookup()

    result = mw.wrap_tool_call(request, handler)

    assert result is original


def test_non_toolmessage_results_pass_through_without_raising() -> None:
    """It never raises for a result it does not recognise: a result that is not a ToolMessage is returned unchanged."""
    agent = _load_agent()
    for odd_result in ("null", {"content": "null"}, None, _FakeCommand()):
        handler = _RecordingHandler(result=odd_result)
        request = _FakeRequest("lookup_order", call_id="call-6")
        mw = agent.ExplainEmptyLookup()

        result = mw.wrap_tool_call(request, handler)

        assert result is odd_result


# ---------------------------------------------------------------------------
# Handler-call discipline
# ---------------------------------------------------------------------------


def test_handler_called_exactly_once_in_every_case() -> None:
    """It calls handler(request) exactly once ... It never calls the handler a second time (including the replacement case)."""
    agent = _load_agent()
    scenarios = [
        ("lookup_order", ToolMessage(content="null", tool_call_id="c", name="lookup_order", status="success")),
        ("lookup_order", ToolMessage(content='{"order_id": "o"}', tool_call_id="c", name="lookup_order", status="success")),
        ("refund_order", ToolMessage(content="null", tool_call_id="c", name="refund_order", status="success")),
        ("lookup_order", ToolMessage(content="null", tool_call_id="c", name="lookup_order", status="error")),
        ("lookup_order", "null"),
        ("lookup_order", None),
    ]
    for name, result in scenarios:
        handler = _RecordingHandler(result=result)
        request = _FakeRequest(name, call_id="c")
        mw = agent.ExplainEmptyLookup()
        mw.wrap_tool_call(request, handler)
        assert handler.calls == 1, f"scenario {(name, result)!r} called handler {handler.calls} times"


def test_handler_exception_propagates_unchanged() -> None:
    """The middleware does not swallow an exception raised by the handler; it propagates unchanged."""
    agent = _load_agent()

    class _Boom(RuntimeError):
        pass

    handler = _RecordingHandler(exc=_Boom("boom"))
    request = _FakeRequest("lookup_order", call_id="call-7")
    mw = agent.ExplainEmptyLookup()

    raised = None
    try:
        mw.wrap_tool_call(request, handler)
    except _Boom as exc:  # noqa: BLE001
        raised = exc

    assert raised is not None
    assert handler.calls == 1


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------


def test_audit_writes_one_line_per_replacement_and_none_for_pass_through() -> None:
    """Each replacement appends one JSON line {"tool": "lookup_order", "tool_call_id": "<id>"}; no line for pass-through."""
    agent = _load_agent()
    with tempfile.TemporaryDirectory() as tmp:
        audit_path = Path(tmp) / "audit.jsonl"
        with _env_var("ORDER_DESK_EMPTY_TEXT_AUDIT", str(audit_path)):
            # Replacement case.
            original = ToolMessage(content="null", tool_call_id="call-r1", name="lookup_order", status="success")
            mw = agent.ExplainEmptyLookup()
            mw.wrap_tool_call(_FakeRequest("lookup_order", call_id="call-r1"), _RecordingHandler(result=original))

            # Pass-through cases: must not add lines.
            mw.wrap_tool_call(
                _FakeRequest("refund_order", call_id="call-p1"),
                _RecordingHandler(result=ToolMessage(content="null", tool_call_id="call-p1", name="refund_order", status="success")),
            )
            mw.wrap_tool_call(
                _FakeRequest("lookup_order", call_id="call-p2"),
                _RecordingHandler(result=ToolMessage(content="null", tool_call_id="call-p2", name="lookup_order", status="error")),
            )

            # A second replacement case.
            mw.wrap_tool_call(
                _FakeRequest("lookup_order", call_id="call-r2"),
                _RecordingHandler(result=ToolMessage(content="null", tool_call_id="call-r2", name="lookup_order", status="success")),
            )

        lines = _read_lines(audit_path)
        assert len(lines) == 2, f"expected 2 audit lines, got {lines!r}"
        recorded_ids = [json.loads(line)["tool_call_id"] for line in lines]
        assert recorded_ids == ["call-r1", "call-r2"]
        for line in lines:
            parsed = json.loads(line)
            assert parsed == {"tool": "lookup_order", "tool_call_id": parsed["tool_call_id"]}


def test_audit_unset_writes_nothing() -> None:
    """If the variable is unset ... the middleware behaves the same and writes nothing."""
    agent = _load_agent()
    with tempfile.TemporaryDirectory() as tmp:
        # Nothing should be created anywhere inside this fresh, otherwise-empty directory.
        with _env_var("ORDER_DESK_EMPTY_TEXT_AUDIT", None):
            original = ToolMessage(content="null", tool_call_id="call-8", name="lookup_order", status="success")
            mw = agent.ExplainEmptyLookup()
            result = mw.wrap_tool_call(_FakeRequest("lookup_order", call_id="call-8"), _RecordingHandler(result=original))

        assert result.content == agent.EMPTY_LOOKUP_TEXT
        assert list(Path(tmp).iterdir()) == []


def test_audit_write_failure_still_returns_replacement_without_raising() -> None:
    """If ... the write fails, the middleware behaves the same and writes nothing; it must not change what the model receives."""
    agent = _load_agent()
    with tempfile.TemporaryDirectory() as tmp:
        unwritable = Path(tmp)  # a directory: opening it for append writing fails
        with _env_var("ORDER_DESK_EMPTY_TEXT_AUDIT", str(unwritable)):
            original = ToolMessage(content="null", tool_call_id="call-9", name="lookup_order", status="success")
            mw = agent.ExplainEmptyLookup()
            result = mw.wrap_tool_call(_FakeRequest("lookup_order", call_id="call-9"), _RecordingHandler(result=original))

        assert isinstance(result, ToolMessage)
        assert result.content == agent.EMPTY_LOOKUP_TEXT
        assert result.tool_call_id == "call-9"
        assert result.name == "lookup_order"
        assert result.status == "success"


# ---------------------------------------------------------------------------
# settings() and the two arms
# ---------------------------------------------------------------------------


def test_baseline_middleware_ends_with_exactly_one_explain_empty_lookup() -> None:
    """The middleware list is [retry, ReturnToolErrors(), ExplainEmptyLookup()] for the baseline arm."""
    agent = _load_agent()
    middleware = agent.settings(False)["middleware"]
    is_explain = [isinstance(m, agent.ExplainEmptyLookup) for m in middleware]
    assert is_explain[-1] is True, "ExplainEmptyLookup must be the last middleware"
    assert sum(is_explain) == 1, "exactly one ExplainEmptyLookup instance"


def test_candidate_middleware_has_no_explain_empty_lookup() -> None:
    """The middleware list is [retry, ReturnToolErrors()] for the candidate arm, exactly as in run 2."""
    agent = _load_agent()
    middleware = agent.settings(True)["middleware"]
    assert not any(isinstance(m, agent.ExplainEmptyLookup) for m in middleware)


def test_middleware_lists_same_length_wise_baseline_has_one_more() -> None:
    """Nothing else differs between the arms: the two middleware lists are the same length-wise, baseline has one more."""
    agent = _load_agent()
    baseline_middleware = agent.settings(False)["middleware"]
    candidate_middleware = agent.settings(True)["middleware"]
    assert len(baseline_middleware) == len(candidate_middleware) + 1


def test_system_prompts_identical_and_end_with_retry_sentence() -> None:
    """The system prompt ... stay as in order-desk-recoverable/agent.py, character for character."""
    agent = _load_agent()
    baseline_prompt = agent.settings(False)["system_prompt"]
    candidate_prompt = agent.settings(True)["system_prompt"]
    assert baseline_prompt == candidate_prompt
    assert baseline_prompt.endswith("Retry an empty lookup once.")


def test_explain_empty_lookup_is_agent_middleware_subclass() -> None:
    """`class ExplainEmptyLookup(AgentMiddleware)`."""
    agent = _load_agent()
    assert issubclass(agent.ExplainEmptyLookup, AgentMiddleware)


# ---------------------------------------------------------------------------
# Runner for use without pytest.
# ---------------------------------------------------------------------------


def main() -> int:
    tests = [
        (name, obj)
        for name, obj in sorted(globals().items())
        if name.startswith("test_") and callable(obj)
    ]
    failures = []
    for name, test in tests:
        try:
            test()
        except Exception as exc:  # noqa: BLE001
            failures.append((name, exc))
            print(f"FAIL {name}: {exc!r}")
        else:
            print(f"PASS {name}")
    print(f"\n{len(tests) - len(failures)}/{len(tests)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
