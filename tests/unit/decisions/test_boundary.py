from __future__ import annotations

import io
import json
import queue
import socket
import time
from typing import Any, cast

import pytest
from pydantic import JsonValue

import arci.mcp_boundary as boundary_module
from arci.perturb import build
from arci.schema import DECISION_TOOL, ToolCall, ToolMode
from tests.acceptance.decision_fixture_client import QUESTIONS
from tests.acceptance.decision_fixtures import (
    COND_LOW_CONFIDENCE,
    COND_UNAVAILABLE,
    PINNED_MODEL,
    TASK,
    decision_spec,
)

Boundary = vars(boundary_module)["_Boundary"]
DecisionWork = vars(boundary_module)["_DecisionWork"]
UpstreamResult = vars(boundary_module)["_UpstreamResult"]


def _request() -> dict[str, JsonValue]:
    return cast(
        dict[str, JsonValue],
        {"state": {"ticket": TASK}, "model": "jev-latest", "questions": QUESTIONS},
    )


def _instance(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any, *, condition: Any
) -> tuple[Any, io.BytesIO, list[tuple[int, JsonValue, dict[str, str]]]]:
    protocol = io.BytesIO()
    monkeypatch.setattr(boundary_module, "_PROTOCOL", protocol)
    spec = decision_spec("gated", condition=condition)
    instance = Boundary("nonce", spec, "unused", str(tmp_path), "proxy-token")
    instance.perturbations = tuple(build(fault) for fault in condition.faults)
    replies: list[tuple[int, JsonValue, dict[str, str]]] = []

    def reply(status: int, body: JsonValue, headers: dict[str, str] | None = None) -> None:
        replies.append((status, body, headers or {}))

    monkeypatch.setattr(instance, "_queue_http", reply)
    return instance, protocol, replies


def _finish_worker(instance: Any) -> None:
    deadline = time.monotonic() + 2.0
    while instance.decision_work is not None and time.monotonic() < deadline:
        instance._poll_decision_work()
        time.sleep(0.005)
    assert instance.decision_work is None


def test_fixture_decision_is_validated_perturbed_recorded_and_replayed(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    instance, protocol, replies = _instance(monkeypatch, tmp_path, condition=COND_LOW_CONFIDENCE)
    request = _request()

    instance._admit_decision(request)
    _finish_worker(instance)

    assert replies[0][0] == 200
    body = cast(dict[str, Any], replies[0][1])
    assert body["model"] == PINNED_MODEL
    assert body["answers"]["department"]["confidence"] == pytest.approx(0.4)
    assert len(instance.recording) == 1
    recorded = instance.recording[0]
    assert recorded.tool == DECISION_TOOL and recorded.occurrence == 0
    frames = [json.loads(line) for line in protocol.getvalue().splitlines()]
    event_kinds = [frame["event"]["kind"] for frame in frames if frame["kind"] == "event"]
    assert event_kinds == ["tool_start", "tool_finish"]

    replay_spec = instance.spec.model_copy(
        update={"tool_mode": ToolMode.REPLAY, "recording": (recorded,)}
    )
    replay = Boundary("nonce", replay_spec, "unused", str(tmp_path), "proxy-token")
    replay_replies: list[tuple[int, JsonValue, dict[str, str]]] = []

    def replay_reply(
        status: int, response_body: JsonValue, headers: dict[str, str] | None = None
    ) -> None:
        replay_replies.append((status, response_body, headers or {}))

    monkeypatch.setattr(
        replay,
        "_queue_http",
        replay_reply,
    )
    replay._admit_decision(request)
    assert replay.replay_index == 1 and replay_replies == replies


def test_unavailable_short_circuits_without_starting_a_worker(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    instance, _protocol, replies = _instance(monkeypatch, tmp_path, condition=COND_UNAVAILABLE)

    instance._admit_decision(_request())

    assert instance.decision_work is None
    assert replies == [(529, {"detail": "arci injected unavailable"}, {})]
    assert instance.recording[0].result.error_kind == "http_529"


def test_concurrent_rejection_flushes_the_complete_500_before_closing(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    instance, _protocol, _replies = _instance(monkeypatch, tmp_path, condition=COND_LOW_CONFIDENCE)
    connection, peer = socket.socketpair()
    peer.settimeout(1.0)
    try:
        instance._reject_concurrent_decision(connection)
        while instance.rejected_decisions:
            instance._flush_rejected_decision(connection)
        response = peer.recv(65536)
        assert response.startswith(b"HTTP/1.1 500")
        assert b"concurrent decision requests are unsupported" in response
        assert instance.latches.harness == "concurrent decision requests are unsupported"
    finally:
        peer.close()
        instance._cleanup()


def test_matched_low_confidence_fault_marks_an_upstream_422(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    instance, _protocol, replies = _instance(monkeypatch, tmp_path, condition=COND_LOW_CONFIDENCE)
    request = _request()
    call = ToolCall(call_id="c-0000", tool=DECISION_TOOL, arguments=request, occurrence=0)
    instance.decision_work = DecisionWork(call, request, queue.Queue(maxsize=1), time.monotonic())

    instance._finish_decision_work(
        UpstreamResult(
            422,
            {},
            {"detail": [{"loc": ["body"], "msg": "no", "type": "value_error"}]},
        )
    )

    assert replies[0][0] == 422
    assert instance.recording[0].result.error_kind == "http_422"
    assert instance.recording[0].result.injected_by == "decision_low_confidence"
