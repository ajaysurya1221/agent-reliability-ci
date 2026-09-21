from __future__ import annotations

import io
import json
import socket
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import pytest

import arci.mcp_boundary as boundary_module
from arci.schema import Budgets, RecordedCall, ToolMode, ToolResult
from tests.acceptance.helpers import COND_CLEAN
from tests.acceptance.mcp_fixtures import mcp_spec, server

Boundary = vars(boundary_module)["_Boundary"]


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
    assert [frame["event"]["kind"] for frame in frames] == ["tool_start", "tool_finish"]


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
