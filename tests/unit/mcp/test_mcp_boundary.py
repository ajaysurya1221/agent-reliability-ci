from __future__ import annotations

import io
import json
import socket
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import pytest

import arci.mcp_boundary as boundary_module
import arci.runner as runner_module
from arci.schema import Budgets, RecordedCall, ToolMode, ToolResult
from tests.acceptance.helpers import COND_CLEAN
from tests.acceptance.mcp_fixtures import mcp_spec, server

Boundary = vars(boundary_module)["_Boundary"]
decode_recording_chunks = vars(runner_module)["_decode_recording_chunks"]
replay_consumption_error = vars(runner_module)["_replay_consumption_error"]


@pytest.fixture
def boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[Any, socket.socket]]:
    protocol = io.BytesIO()
    monkeypatch.setattr(boundary_module, "_PROTOCOL", protocol)
    instance = Boundary("nonce", mcp_spec("good", condition=COND_CLEAN), "unused", str(tmp_path))
    instance.connection, peer = socket.socketpair()
    instance._start_server()
    try:
        yield instance, peer
    finally:
        instance._cleanup()
        peer.close()


def _message(method: str, request_id: str, params: dict[str, Any] | None = None) -> bytes:
    return json.dumps(
        {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}}
    ).encode()


def _round_trip(instance: Any, peer: socket.socket, request: bytes) -> dict[str, Any]:
    instance._client_message(request)
    assert instance.server is not None and instance.server.stdout is not None
    instance._server_message(instance.server.stdout.readline().rstrip(b"\n"))
    return cast(dict[str, Any], json.loads(peer.recv(65536)))


@pytest.mark.parametrize("method", ["initialize", "tools/list"])
def test_boundary_passes_through_discovery(
    boundary: tuple[Any, socket.socket], method: str
) -> None:
    instance, peer = boundary
    reply = _round_trip(instance, peer, _message(method, "client-id"))
    assert reply["id"] == "client-id" and "result" in reply
    assert instance.recording[-1].tool == f"rpc:{method}"


def test_tools_call_is_intercepted_and_recorded(
    boundary: tuple[Any, socket.socket], monkeypatch: pytest.MonkeyPatch
) -> None:
    instance, peer = boundary
    protocol = io.BytesIO()
    monkeypatch.setattr(boundary_module, "_PROTOCOL", protocol)
    reply = _round_trip(
        instance,
        peer,
        _message("tools/call", "call-id", {"name": "log", "arguments": {"msg": "hello"}}),
    )
    assert reply["result"]["isError"] is False
    assert instance.recording[-1].tool == "log"
    frames = [json.loads(line) for line in protocol.getvalue().splitlines()]
    events = [frame["event"]["kind"] for frame in frames if frame["kind"] == "event"]
    assert events == ["tool_start", "tool_finish"]
    assert [frame["kind"] for frame in frames].count("recording") >= 1


def test_budget_call_is_not_forwarded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(boundary_module, "_PROTOCOL", io.BytesIO())
    spec = mcp_spec("chatty", condition=COND_CLEAN).model_copy(
        update={"budgets": Budgets(max_tool_calls=0)}
    )
    instance = Boundary("nonce", spec, "unused", str(tmp_path))
    instance.connection, peer = socket.socketpair()
    try:
        instance._tool_request(
            cast(
                dict[str, Any],
                json.loads(_message("tools/call", "over", {"name": "log", "arguments": {}})),
            ),
            "over",
        )
        reply = json.loads(peer.recv(65536))
        assert reply["result"]["isError"] is True
        assert instance.latches.budget == "tool call budget exhausted"
        assert instance.tool_calls == 0
    finally:
        instance.connection.close()
        peer.close()


def test_task_result_latches_a_harness_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(boundary_module, "_PROTOCOL", io.BytesIO())
    spec = mcp_spec("direct", condition=COND_CLEAN).model_copy(
        update={"mcp_server": server("--task-results")}
    )
    instance = Boundary("nonce", spec, "unused", str(tmp_path))
    instance.connection, peer = socket.socketpair()
    instance._start_server()
    try:
        _round_trip(
            instance,
            peer,
            _message("tools/call", "task", {"name": "log", "arguments": {}}),
        )
        assert instance.latches.harness == "MCP task results are unsupported"
    finally:
        instance._cleanup()
        peer.close()


def test_server_request_and_concurrent_call_are_rejected(
    boundary: tuple[Any, socket.socket],
) -> None:
    instance, peer = boundary
    instance._server_message(_message("sampling/createMessage", "server-id", {"messages": []}))
    assert instance.latches.harness == "server-initiated requests are unsupported"
    instance.tools_inflight = True
    instance._tool_request(
        cast(
            dict[str, Any],
            json.loads(_message("tools/call", "second", {"name": "log", "arguments": {}})),
        ),
        "second",
    )
    assert json.loads(peer.recv(65536))["result"]["isError"] is True


def test_replay_rewrites_rpc_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(boundary_module, "_PROTOCOL", io.BytesIO())
    params: dict[str, Any] = {"protocolVersion": "2026-07-28"}
    recorded = RecordedCall(
        tool="rpc:initialize",
        arguments_sha256=boundary_module.hash_record(params),
        occurrence=0,
        result=ToolResult(
            call_id="r-0000",
            tool="rpc:initialize",
            ok=True,
            value={"protocolVersion": "2026-07-28"},
        ),
    )
    spec = mcp_spec("good", condition=COND_CLEAN).model_copy(
        update={"tool_mode": ToolMode.REPLAY, "recording": (recorded,)}
    )
    instance = Boundary("nonce", spec, "unused", str(tmp_path))
    instance.connection, peer = socket.socketpair()
    try:
        instance._client_message(_message("initialize", "new-id", params))
        reply = json.loads(peer.recv(65536))
        assert reply == {
            "id": "new-id",
            "jsonrpc": "2.0",
            "result": {"protocolVersion": "2026-07-28"},
        }
    finally:
        instance.connection.close()
        peer.close()


def test_server_death_is_observable(boundary: tuple[Any, socket.socket]) -> None:
    instance, _peer = boundary
    assert instance.server is not None
    instance.server.kill()
    instance.server.wait()
    assert instance.server.poll() is not None


def test_trial_socket_path_stays_below_unix_limit() -> None:
    longest_generated = "/tmp/" + "arci-" + "x" * 16 + "/mcp.sock"
    assert len(longest_generated.encode()) < 100


def _in_process_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, spec: Any | None = None
) -> tuple[Any, list[dict[str, Any]], list[dict[str, Any]], io.BytesIO]:
    protocol = io.BytesIO()
    monkeypatch.setattr(boundary_module, "_PROTOCOL", protocol)
    instance = Boundary(
        "nonce", spec or mcp_spec("good", condition=COND_CLEAN), "unused", str(tmp_path)
    )
    client: list[dict[str, Any]] = []
    server_messages: list[dict[str, Any]] = []
    instance._write_client = client.append
    instance._write_server = server_messages.append
    return instance, client, server_messages, protocol


def test_client_errors_are_replied_to_without_a_harness_latch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    instance, client, server_messages, _protocol = _in_process_boundary(tmp_path, monkeypatch)

    instance._client_message(_message("tools/call", "bad", {"name": "fetch", "arguments": []}))

    assert client[-1]["error"]["code"] == -32602
    assert server_messages == []
    assert instance.tool_calls == 0
    assert instance.latches.harness is None

    instance.known_tools = {"fetch"}
    instance._client_message(_message("tools/call", "unknown", {"name": "store", "arguments": {}}))
    instance._client_message(b"not-json")
    assert [reply["error"]["code"] for reply in client[-2:]] == [-32601, -32600]
    assert instance.latches.harness is None


def test_client_ids_are_mapped_to_independent_upstream_ids_and_reuse_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    instance, client, server_messages, _protocol = _in_process_boundary(tmp_path, monkeypatch)
    request = _message("ping", "same")

    instance._client_message(request)
    instance._client_message(request)

    assert server_messages[0]["id"] == 0
    assert client[-1]["error"]["code"] == -32600
    instance._server_message(b'{"jsonrpc":"2.0","id":0,"result":{}}')
    assert client[-1] == {"jsonrpc": "2.0", "id": "same", "result": {}}


def test_server_response_validation_and_tool_result_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    instance, _client, _server_messages, _protocol = _in_process_boundary(tmp_path, monkeypatch)
    instance._client_message(_message("ping", "p"))
    with pytest.raises(ValueError, match="exactly one"):
        instance._server_message(b'{"jsonrpc":"2.0","id":0}')

    other, _client, _server_messages, _protocol = _in_process_boundary(tmp_path, monkeypatch)
    other._client_message(_message("tools/call", "t", {"name": "fetch", "arguments": {}}))
    other._server_message(b'{"jsonrpc":"2.0","id":0,"result":{"content":"bad","isError":"true"}}')
    assert other.latches.harness == "tools/call result has an invalid shape"


def test_recording_chunks_reassemble_and_replay_progress_is_parent_countable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    instance, _client, _server_messages, protocol = _in_process_boundary(tmp_path, monkeypatch)
    result = ToolResult(call_id="r-0000", tool="rpc:ping", ok=True, value={"pad": "x" * 900_000})
    instance._record("rpc:ping", {}, 0, result)
    frames = [json.loads(line) for line in protocol.getvalue().splitlines()]
    chunks = {frame["chunk"]: frame["data"] for frame in frames}
    rebuilt = decode_recording_chunks(chunks, frames[0]["chunks"])
    assert rebuilt == instance.recording[0]
    assert len(frames) > 1

    replay_spec = instance.spec.model_copy(
        update={"tool_mode": ToolMode.REPLAY, "recording": tuple(instance.recording)}
    )
    replay, _client, _server_messages, replay_protocol = _in_process_boundary(
        tmp_path, monkeypatch, spec=replay_spec
    )
    assert replay._replay("rpc:ping", {}, 0) is not None
    progress = [json.loads(line) for line in replay_protocol.getvalue().splitlines()]
    assert progress[-1]["consumed"] == 1
    assert replay_consumption_error(replay_spec, 1) is None
    assert replay_consumption_error(replay_spec, 0) == "recording was not consumed exactly"
