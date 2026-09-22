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
DecisionCompletion = vars(boundary_module)["_DecisionCompletion"]
DecisionWork = vars(boundary_module)["_DecisionWork"]
HttpRequestError = vars(boundary_module)["_HttpRequestError"]
UpstreamResult = vars(boundary_module)["_UpstreamResult"]
deadline_expired = vars(boundary_module)["_decision_deadline_expired"]
parse_http_request = vars(boundary_module)["_parse_http_request"]
scrub_diagnostic = vars(boundary_module)["_scrub_diagnostic"]
server_environment = vars(boundary_module)["_server_environment"]
transports_conflict = vars(boundary_module)["_transports_conflict"]


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


def test_deadline_uses_worker_completion_time_and_rejects_an_overdue_result(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    instance, _protocol, replies = _instance(monkeypatch, tmp_path, condition=COND_LOW_CONFIDENCE)
    request = _request()
    call = ToolCall(call_id="c-0000", tool=DECISION_TOOL, arguments=request, occurrence=0)
    started = 10.0
    results: queue.Queue[Any] = queue.Queue(maxsize=1)
    results.put_nowait(
        DecisionCompletion(
            started + instance.spec.decisions.request_seconds + 0.001,
            UpstreamResult(200, {}, {}),
        )
    )
    instance.decision_work = DecisionWork(call, request, results, started)

    instance._poll_decision_work()

    assert deadline_expired(started, 0.05, started + 0.05)
    assert instance.latches.harness == "decision upstream timed out"
    assert instance.decision_work.timed_out is True
    assert replies == [(500, {"detail": "arci: decision upstream failed"}, {})]


def test_a_queued_worker_fault_is_latched_by_the_final_poll(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    instance, _protocol, replies = _instance(monkeypatch, tmp_path, condition=COND_LOW_CONFIDENCE)
    request = _request()
    call = ToolCall(call_id="c-0000", tool=DECISION_TOOL, arguments=request, occurrence=0)
    started = time.monotonic()
    results: queue.Queue[Any] = queue.Queue(maxsize=1)
    results.put_nowait(
        DecisionCompletion(started + 0.001, UpstreamResult(500, {}, None, "fixture failed"))
    )
    instance.decision_work = DecisionWork(call, request, results, started)

    instance._poll_decision_work()

    assert instance.latches.harness == "fixture failed"
    assert instance.decision_work is None
    assert replies == [(500, {"detail": "arci: decision upstream failed"}, {})]


def test_deep_raw_json_is_a_local_422_even_when_the_decoder_recurses(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    instance, _protocol, replies = _instance(monkeypatch, tmp_path, condition=COND_LOW_CONFIDENCE)
    # Built as text: json.dumps cannot encode 5000 levels on Python 3.11.
    nested = "[" * 5000 + '"leaf"' + "]" * 5000
    raw = (
        '{"state": '
        + nested
        + ', "model": "jev-latest", "questions": '
        + json.dumps(QUESTIONS)
        + "}"
    ).encode()

    instance._handle_http_request(
        "POST",
        "/v1/systemone",
        {"authorization": "Bearer proxy-token"},
        raw,
    )

    assert replies[0][0] == 422
    assert instance.tool_calls == 0
    assert instance.latches.harness is None


def test_http_parser_uses_only_the_first_request_and_rejects_expect() -> None:
    body = b'{"request":1}'
    head = (
        b"POST /v1/systemone HTTP/1.1\r\n"
        b"Host: localhost\r\n" + f"Content-Length: {len(body)}\r\n\r\n".encode()
    )

    parsed = parse_http_request(head + body + head + body, 1024)

    assert parsed is not None
    assert parsed.body == body
    with pytest.raises(HttpRequestError) as error:
        parse_http_request(head.replace(b"\r\n\r\n", b"\r\nExpect: 100-continue\r\n\r\n"), 1024)
    assert error.value.status == 417


def test_serial_rule_covers_every_cross_transport_overlap() -> None:
    assert transports_conflict(pending_mcp=True, active_decision=True)
    assert not transports_conflict(pending_mcp=False, active_decision=True)
    assert not transports_conflict(pending_mcp=True, active_decision=False)


def test_real_key_is_removed_from_server_environment_and_diagnostics() -> None:
    inherited = {
        "KEEP": "yes",
        "TYPESAFE_API_KEY": "real-secret",
        "TYPESAFE_BASE_URL": "https://real.invalid",
    }
    configured = {
        "TYPESAFE_API_KEY": "configured-secret",
        "TYPESAFE_BASE_URL": "https://configured.invalid",
    }

    env = server_environment(inherited, configured, "/tmp/trial", 7)

    assert "TYPESAFE_API_KEY" not in env and "TYPESAFE_BASE_URL" not in env
    assert env["KEEP"] == "yes"
    assert env["ARCI_SEED"] == "7"


def test_real_key_is_scrubbed_after_safe_diagnostic_formatting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TYPESAFE_API_KEY", "real-secret")

    detail = scrub_diagnostic(RuntimeError("upstream refused real-secret"))

    assert "real-secret" not in detail
    assert "<redacted>" in detail
