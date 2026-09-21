"""Harness-owned MCP recorder, replay server and fault-injection boundary."""

from __future__ import annotations

import base64
import contextlib
import copy
import json
import os
import random
import selectors
import signal
import socket
import subprocess
import sys
import time
from collections import Counter
from dataclasses import dataclass
from typing import cast

from pydantic import JsonValue

from arci.hashing import canonical_json, hash_record
from arci.interfaces import Perturbation
from arci.perturb import build
from arci.schema import RecordedCall, Termination, ToolCall, ToolMode, ToolResult, TrialSpec
from arci.toolbox import format_diagnostic

_MAX_LINE = 1024 * 1024
_RECORD_CHUNK = 512 * 1024
_MAX_QUEUED_BYTES = 16 * 1024 * 1024
_PROTOCOL = sys.stdout.buffer


def _frame(nonce: str, kind: str, **payload: object) -> None:
    _PROTOCOL.write(canonical_json({"nonce": nonce, "kind": kind, **payload}) + b"\n")
    _PROTOCOL.flush()


def _valid_rpc_id(value: object) -> bool:
    return (
        value is None
        or isinstance(value, str)
        or (isinstance(value, int) and not isinstance(value, bool))
    )


def _rpc_error(request_id: JsonValue, code: int, message: str) -> dict[str, JsonValue]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }


class _Latches:
    def __init__(self, nonce: str) -> None:
        self.nonce = nonce
        self.replay: str | None = None
        self.harness: str | None = None
        self.budget: str | None = None

    def _set(self, attribute: str, wire_name: str, detail: str) -> None:
        if getattr(self, attribute) is None:
            clean = format_diagnostic(detail)
            setattr(self, attribute, clean)
            _frame(self.nonce, "latch", latch=wire_name, detail=clean)

    def set_replay(self, detail: str) -> None:
        self._set("replay", "replay_miss", detail)

    def set_harness(self, detail: str | BaseException) -> None:
        self._set("harness", "harness_error", format_diagnostic(detail))

    def set_budget(self, detail: str) -> None:
        self._set("budget", "budget", detail)


class _Emitter:
    def __init__(self, spec: TrialSpec, nonce: str) -> None:
        self.spec = spec
        self.nonce = nonce
        self.seq = 0
        self.started = time.monotonic()

    def emit(self, kind: str, payload: dict[str, JsonValue]) -> None:
        copied = copy.deepcopy(payload)
        canonical_json(copied)
        event = {
            "trial_id": self.spec.trial_id,
            "seq": self.seq,
            "kind": kind,
            "payload": copied,
            "at_ms": (time.monotonic() - self.started) * 1000.0,
        }
        self.seq += 1
        _frame(self.nonce, "event", event=event)


@dataclass
class _Pending:
    method: str
    rpc_id: JsonValue
    client_key: bytes
    occurrence: int
    arguments: dict[str, JsonValue]
    call: ToolCall | None = None


def _id_key(value: JsonValue) -> bytes:
    return canonical_json(value)


def _task_file(workdir: str) -> str:
    """Return the task JSON path written by the parent."""
    return os.path.join(workdir, "task.json")


def _expand(values: tuple[str, ...], workdir: str, seed: int) -> list[str]:
    return [
        item.replace("{workdir}", workdir)
        .replace("{seed}", str(seed))
        .replace("{task_file}", _task_file(workdir))
        for item in values
    ]


def _error_result(kind: str, text: str) -> dict[str, JsonValue]:
    del kind
    return {
        "resultType": "complete",
        "content": [{"type": "text", "text": text}],
        "isError": True,
    }


class _Boundary:
    def __init__(self, nonce: str, spec: TrialSpec, socket_path: str, workdir: str) -> None:
        self.nonce = nonce
        self.spec = spec
        self.socket_path = socket_path
        self.workdir = workdir
        self.latches = _Latches(nonce)
        self.emitter = _Emitter(spec, nonce)
        self.stop = False
        self.listener: socket.socket | None = None
        self.connection: socket.socket | None = None
        self.server: subprocess.Popen[bytes] | None = None
        self.selector = selectors.DefaultSelector()
        self.buffers: dict[str, bytearray] = {"client": bytearray(), "server": bytearray()}
        self.output: dict[str, bytearray] = {"client": bytearray(), "server": bytearray()}
        self.pending: dict[bytes, _Pending] = {}
        self.client_pending: set[bytes] = set()
        self.occurrences: Counter[str] = Counter()
        self.rpc_occurrences: Counter[str] = Counter()
        self.tool_calls = 0
        self.replay_index = 0
        self.recording: list[RecordedCall] = []
        self.perturbations: tuple[Perturbation, ...] = ()
        self.tools_inflight = False
        self.known_tools: set[str] | None = None
        self.next_upstream_id = 0
        self.async_io = False

    def request_stop(self, _signum: int, _frame_value: object) -> None:
        self.stop = True

    def _refresh_client_events(self) -> None:
        if self.connection is None or not self.async_io:
            return
        events = selectors.EVENT_READ
        if self.output["client"]:
            events |= selectors.EVENT_WRITE
        self.selector.modify(self.connection, events, "client")

    def _refresh_server_events(self) -> None:
        if self.server is None or self.server.stdin is None or not self.async_io:
            return
        try:
            key = self.selector.get_key(self.server.stdin)
        except KeyError:
            if self.output["server"]:
                self.selector.register(self.server.stdin, selectors.EVENT_WRITE, "server_write")
        else:
            if not self.output["server"]:
                self.selector.unregister(key.fileobj)

    def _queue(self, destination: str, data: bytes) -> None:
        target = self.output[destination]
        if len(target) + len(data) > _MAX_QUEUED_BYTES:
            raise BufferError(f"MCP {destination} output queue exceeded its limit")
        target.extend(data)
        if destination == "client":
            self._refresh_client_events()
        else:
            self._refresh_server_events()

    def _write_client(self, message: dict[str, JsonValue]) -> None:
        assert self.connection is not None
        data = canonical_json(message) + b"\n"
        if self.async_io:
            self._queue("client", data)
        else:
            self.connection.sendall(data)

    def _write_server(self, message: dict[str, JsonValue]) -> None:
        if self.server is None or self.server.stdin is None:
            raise BrokenPipeError("MCP server is unavailable")
        data = canonical_json(message) + b"\n"
        if self.async_io:
            self._queue("server", data)
        else:
            self.server.stdin.write(data)
            self.server.stdin.flush()

    def _flush(self, destination: str) -> None:
        data = self.output[destination]
        if not data:
            return
        if destination == "client":
            assert self.connection is not None
            sent = self.connection.send(data)
        else:
            assert self.server is not None and self.server.stdin is not None
            sent = os.write(self.server.stdin.fileno(), data)
        if sent:
            del data[:sent]
        if destination == "client":
            self._refresh_client_events()
        else:
            self._refresh_server_events()

    def _stream_record(self, recorded: RecordedCall) -> None:
        encoded = base64.b64encode(canonical_json(recorded.model_dump(mode="python")))
        chunks = [
            encoded[index : index + _RECORD_CHUNK]
            for index in range(0, len(encoded), _RECORD_CHUNK)
        ]
        for index, chunk in enumerate(chunks):
            _frame(
                self.nonce,
                "recording",
                index=len(self.recording) - 1,
                chunk=index,
                chunks=len(chunks),
                data=chunk.decode("ascii"),
            )

    def _record(
        self, key: str, arguments: dict[str, JsonValue], occurrence: int, result: ToolResult
    ) -> None:
        recorded = RecordedCall(
            tool=key,
            arguments_sha256=hash_record(arguments),
            occurrence=occurrence,
            result=result.model_copy(deep=True),
        )
        canonical_json(recorded.model_dump(mode="python"))
        self.recording.append(recorded)
        self._stream_record(recorded)

    def _replay(
        self, key: str, arguments: dict[str, JsonValue], occurrence: int
    ) -> ToolResult | None:
        observed = (key, hash_record(arguments), occurrence)
        if self.replay_index >= len(self.spec.recording):
            self.latches.set_replay("recording was not consumed exactly")
            return None
        recorded = self.spec.recording[self.replay_index]
        expected = (recorded.tool, recorded.arguments_sha256, recorded.occurrence)
        if observed != expected:
            self.latches.set_replay("recording was not consumed exactly")
            return None
        self.replay_index += 1
        _frame(self.nonce, "replay_progress", consumed=self.replay_index)
        return recorded.result.model_copy(deep=True)

    def _emit_start(self, call: ToolCall) -> None:
        self.emitter.emit(
            "tool_start",
            {
                "tool": call.tool,
                "call_id": call.call_id,
                "occurrence": call.occurrence,
                "arguments": copy.deepcopy(call.arguments),
            },
        )

    def _emit_finish(self, result: ToolResult) -> None:
        self.emitter.emit(
            "tool_finish",
            {
                "tool": result.tool,
                "call_id": result.call_id,
                "ok": result.ok,
                "value": copy.deepcopy(result.value),
                "error_kind": result.error_kind,
                "injected_by": result.injected_by,
            },
        )

    def _apply_before(self, call: ToolCall) -> ToolResult | None:
        for perturbation in self.perturbations:
            try:
                with contextlib.redirect_stdout(sys.stderr):
                    value = cast(
                        object,
                        perturbation.before(
                            call.model_copy(deep=True),
                            random.Random(f"{self.spec.seed}:fault:{perturbation.name}"),
                        ),
                    )
                if value is not None and not isinstance(value, ToolResult):
                    raise TypeError("perturbation before() returned an invalid result")
                if value is not None and (value.call_id != call.call_id or value.tool != call.tool):
                    raise ValueError("perturbation result does not match its call")
                if value is not None:
                    canonical_json(value.model_dump(mode="python"))
            except BaseException as exc:
                self.latches.set_harness(exc)
                return None
            if value is not None:
                return value.model_copy(deep=True)
        return None

    def _apply_after(self, call: ToolCall, result: ToolResult) -> ToolResult:
        current = result
        for perturbation in self.perturbations:
            try:
                with contextlib.redirect_stdout(sys.stderr):
                    value = cast(
                        object,
                        perturbation.after(
                            call.model_copy(deep=True),
                            current.model_copy(deep=True),
                            random.Random(f"{self.spec.seed}:fault:{perturbation.name}"),
                        ),
                    )
                if not isinstance(value, ToolResult):
                    raise TypeError("perturbation after() returned an invalid result")
                if value.call_id != call.call_id or value.tool != call.tool:
                    raise ValueError("perturbation result does not match its call")
                current = value.model_copy(deep=True)
                canonical_json(current.model_dump(mode="python"))
            except BaseException as exc:
                self.latches.set_harness(exc)
                return result
        return current

    def _reply_tool(self, rpc_id: JsonValue, call: ToolCall, result: ToolResult) -> None:
        value = cast(dict[str, JsonValue], copy.deepcopy(result.value))
        if "error" in value and result.error_kind == "mcp_error":
            reply: dict[str, JsonValue] = {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "error": value["error"],
            }
        else:
            reply = {"jsonrpc": "2.0", "id": rpc_id, "result": value}
        self._write_client(reply)
        self._emit_finish(result)
        if self.spec.tool_mode is ToolMode.RECORD:
            self._record(call.tool, call.arguments, call.occurrence, result)

    def _client_error(self, rpc_id: JsonValue, code: int, message: str) -> None:
        self._write_client(_rpc_error(rpc_id, code, message))

    def _forward(self, message: dict[str, JsonValue], pending: _Pending) -> None:
        upstream_id = self.next_upstream_id
        self.next_upstream_id += 1
        self.pending[_id_key(upstream_id)] = pending
        self.client_pending.add(pending.client_key)
        forwarded = copy.deepcopy(message)
        forwarded["id"] = upstream_id
        self._write_server(forwarded)

    def _tool_request(self, message: dict[str, JsonValue], rpc_id: JsonValue) -> None:
        raw_params = message.get("params", {})
        if not isinstance(raw_params, dict):
            self._client_error(rpc_id, -32602, "tools/call params must be an object")
            return
        name = raw_params.get("name")
        raw_arguments = raw_params.get("arguments", {})
        if not isinstance(name, str) or not isinstance(raw_arguments, dict):
            self._client_error(rpc_id, -32602, "tools/call is malformed")
            return
        if self.known_tools is not None and name not in self.known_tools:
            self._client_error(rpc_id, -32601, f"unknown tool {name}")
            return
        arguments = cast(dict[str, JsonValue], copy.deepcopy(raw_arguments))
        try:
            canonical_json(arguments)
        except (TypeError, ValueError, UnicodeError):
            self._client_error(rpc_id, -32602, "tool arguments are not canonical JSON")
            return
        if self.tools_inflight:
            self.latches.set_harness("concurrent tools/call is unsupported")
            self._write_client(
                {
                    "jsonrpc": "2.0",
                    "id": rpc_id,
                    "result": _error_result("error", "arci: concurrent tools/call"),
                }
            )
            return
        if self.tool_calls >= self.spec.budgets.max_tool_calls:
            self.latches.set_budget("tool call budget exhausted")
            self._write_client(
                {
                    "jsonrpc": "2.0",
                    "id": rpc_id,
                    "result": _error_result("budget", "arci: tool budget exceeded"),
                }
            )
            return

        occurrence = self.occurrences[name]
        call = ToolCall(
            call_id=f"c-{self.tool_calls:04d}",
            tool=name,
            arguments=arguments,
            occurrence=occurrence,
        )
        self.tool_calls += 1
        self.occurrences[name] += 1
        self._emit_start(call)

        if self.spec.tool_mode is ToolMode.REPLAY:
            replayed = self._replay(name, arguments, occurrence)
            if replayed is None:
                result = ToolResult(
                    call_id=call.call_id,
                    tool=name,
                    ok=False,
                    value=_error_result("replay_miss", "arci: replay mismatch"),
                    error_kind="replay_miss",
                )
            else:
                result = replayed.model_copy(
                    update={"call_id": call.call_id, "tool": name}, deep=True
                )
            self._reply_tool(rpc_id, call, result)
            return

        injected = self._apply_before(call)
        if injected is not None:
            mcp_value = _error_result(
                injected.error_kind or "error",
                f"arci injected {injected.error_kind or 'error'}",
            )
            result = injected.model_copy(
                update={"call_id": call.call_id, "tool": name, "value": mcp_value}, deep=True
            )
            self._reply_tool(rpc_id, call, result)
            return

        self.tools_inflight = True
        client_key = _id_key(rpc_id)
        self._forward(
            message,
            _Pending(
                method="tools/call",
                rpc_id=rpc_id,
                client_key=client_key,
                occurrence=occurrence,
                arguments=arguments,
                call=call,
            ),
        )

    def _rpc_request(self, message: dict[str, JsonValue], method: str, rpc_id: JsonValue) -> None:
        raw_params = message.get("params", {})
        if not isinstance(raw_params, dict):
            self._client_error(rpc_id, -32602, f"{method} params must be an object")
            return
        params = cast(dict[str, JsonValue], copy.deepcopy(raw_params))
        occurrence = self.rpc_occurrences[method]
        self.rpc_occurrences[method] += 1
        key = f"rpc:{method}"
        if self.spec.tool_mode is ToolMode.REPLAY:
            replayed = self._replay(key, params, occurrence)
            if replayed is None:
                self._client_error(rpc_id, -32000, "arci: replay mismatch")
                return
            value = copy.deepcopy(replayed.value)
            if replayed.error_kind == "mcp_error" and isinstance(value, dict) and "error" in value:
                self._write_client({"jsonrpc": "2.0", "id": rpc_id, "error": value["error"]})
            else:
                self._write_client({"jsonrpc": "2.0", "id": rpc_id, "result": value})
            return
        client_key = _id_key(rpc_id)
        self._forward(
            message,
            _Pending(
                method=method,
                rpc_id=rpc_id,
                client_key=client_key,
                occurrence=occurrence,
                arguments=params,
            ),
        )

    def _client_message(self, raw: bytes) -> None:
        try:
            value = json.loads(raw.decode("utf-8"))
            canonical_json(value)
        except (json.JSONDecodeError, UnicodeError, TypeError, ValueError):
            self._client_error(None, -32600, "invalid request")
            return
        if not isinstance(value, dict):
            self._client_error(None, -32600, "invalid request")
            return
        message = cast(dict[str, JsonValue], value)
        rpc_id = message.get("id")
        method = message.get("method")
        if message.get("jsonrpc") != "2.0" or not isinstance(method, str):
            self._client_error(rpc_id if _valid_rpc_id(rpc_id) else None, -32600, "invalid request")
            return
        if "id" not in message:
            if method == "notifications/initialized" and self.spec.tool_mode is not ToolMode.REPLAY:
                self._write_server(message)
            return
        if not _valid_rpc_id(rpc_id):
            self._client_error(None, -32600, "invalid request id")
            return
        client_key = _id_key(rpc_id)
        if client_key in self.client_pending:
            self._client_error(rpc_id, -32600, "request id is already outstanding")
            return
        if method == "tools/call":
            self._tool_request(message, rpc_id)
        elif method in {"initialize", "ping", "tools/list"}:
            self._rpc_request(message, method, rpc_id)
        else:
            self._client_error(rpc_id, -32601, "method not found")

    def _validate_server_response(
        self, message: dict[str, JsonValue]
    ) -> tuple[JsonValue, JsonValue | None, dict[str, JsonValue] | None]:
        if message.get("jsonrpc") != "2.0" or "id" not in message:
            raise ValueError("MCP server returned an invalid JSON-RPC response")
        response_id = message["id"]
        if not _valid_rpc_id(response_id):
            raise ValueError("MCP server returned an invalid response id")
        has_result = "result" in message
        has_error = "error" in message
        if has_result == has_error:
            raise ValueError("MCP server response needs exactly one of result or error")
        if not has_error:
            return response_id, message.get("result"), None
        raw_error = message.get("error")
        if not isinstance(raw_error, dict):
            raise ValueError("MCP server returned an invalid JSON-RPC error")
        error = cast(dict[str, JsonValue], raw_error)
        code = error.get("code")
        if (
            not isinstance(code, int)
            or isinstance(code, bool)
            or not isinstance(error.get("message"), str)
        ):
            raise ValueError("MCP server returned an invalid JSON-RPC error")
        if code not in {-32600, -32601, -32602}:
            self.latches.set_harness("MCP server returned an internal JSON-RPC error")
        return response_id, None, error

    def _remember_tools(self, value: JsonValue | None) -> None:
        if not isinstance(value, dict):
            return
        raw_tools = value.get("tools")
        if not isinstance(raw_tools, list):
            return
        names: set[str] = set()
        for item in raw_tools:
            if not isinstance(item, dict) or not isinstance(item.get("name"), str):
                return
            names.add(cast(str, item["name"]))
        self.known_tools = names

    def _server_message(self, raw: bytes) -> None:
        value = json.loads(raw.decode("utf-8"))
        canonical_json(value)
        if not isinstance(value, dict):
            raise TypeError("MCP server message is not an object")
        message = cast(dict[str, JsonValue], value)
        if isinstance(message.get("method"), str):
            if "id" in message:
                self.latches.set_harness("server-initiated requests are unsupported")
                self._write_server(_rpc_error(message["id"], -32601, "unsupported"))
            else:
                self.latches.set_harness("server notifications are unsupported")
            return
        response_id, result_value, error = self._validate_server_response(message)
        pending = self.pending.pop(_id_key(response_id), None)
        if pending is None:
            raise ValueError("unexpected MCP server response")
        self.client_pending.discard(pending.client_key)
        reply: dict[str, JsonValue]
        if error is None:
            reply = {
                "jsonrpc": "2.0",
                "id": pending.rpc_id,
                "result": copy.deepcopy(result_value),
            }
        else:
            reply = {
                "jsonrpc": "2.0",
                "id": pending.rpc_id,
                "error": copy.deepcopy(error),
            }

        if pending.call is None:
            if pending.method == "tools/list" and error is None:
                self._remember_tools(result_value)
            result = ToolResult(
                call_id=f"r-{len(self.recording):04d}",
                tool=f"rpc:{pending.method}",
                ok=error is None,
                value=(
                    copy.deepcopy(result_value)
                    if error is None
                    else {"error": copy.deepcopy(error)}
                ),
                error_kind=None if error is None else "mcp_error",
            )
            self._write_client(reply)
            self._record(f"rpc:{pending.method}", pending.arguments, pending.occurrence, result)
            return

        self.tools_inflight = False
        call = pending.call
        if error is not None:
            mcp_value: dict[str, JsonValue] = {"error": copy.deepcopy(error)}
            result = ToolResult(
                call_id=call.call_id,
                tool=call.tool,
                ok=False,
                value=mcp_value,
                error_kind="mcp_error",
            )
        else:
            if not isinstance(result_value, dict):
                raise TypeError("tools/call result is not an object")
            mcp_value = cast(dict[str, JsonValue], copy.deepcopy(result_value))
            result_type = mcp_value.get("resultType")
            if result_type not in {None, "complete"}:
                self.latches.set_harness("MCP task results are unsupported")
            if (
                not isinstance(mcp_value.get("content"), list)
                or type(mcp_value.get("isError")) is not bool
            ):
                self.latches.set_harness("tools/call result has an invalid shape")
            is_error = mcp_value.get("isError") is True
            result = ToolResult(
                call_id=call.call_id,
                tool=call.tool,
                ok=not is_error,
                value=mcp_value,
                error_kind="tool_error" if is_error else None,
            )
            rewritten = self._apply_after(call, result)
            if rewritten.value is None and rewritten.injected_by is not None:
                empty = copy.deepcopy(mcp_value)
                empty["content"] = []
                rewritten = rewritten.model_copy(update={"value": empty}, deep=True)
            result = rewritten
        self._reply_tool(pending.rpc_id, call, result)

    def _consume_chunk(self, source: str, chunk: bytes) -> None:
        buffer = self.buffers[source]
        buffer.extend(chunk)
        while True:
            newline = buffer.find(b"\n")
            if newline < 0:
                if len(buffer) > _MAX_LINE:
                    raise ValueError("MCP line too long")
                return
            line = bytes(buffer[:newline])
            del buffer[: newline + 1]
            if len(line) > _MAX_LINE:
                raise ValueError("MCP line too long")
            if not line.strip():
                continue
            if source == "client":
                self._client_message(line)
            else:
                self._server_message(line)

    def _read_lines(self, source: str, fd: int) -> bool:
        try:
            chunk = os.read(fd, 65536)
        except BlockingIOError:
            return True
        if not chunk:
            return False
        self._consume_chunk(source, chunk)
        return True

    def _drain_server_after_exit(self) -> None:
        assert self.server is not None and self.server.stdout is not None
        while True:
            try:
                chunk = os.read(self.server.stdout.fileno(), 65536)
            except BlockingIOError:
                return
            if not chunk:
                return
            self._consume_chunk("server", chunk)

    def _start_server(self) -> None:
        server_spec = self.spec.mcp_server
        if server_spec is None:
            raise ValueError("command trial has no MCP server")
        env = {**os.environ, **server_spec.env}
        env["ARCI_WORKDIR"] = self.workdir
        env["ARCI_SEED"] = str(self.spec.seed)
        env["ARCI_TASK_FILE"] = _task_file(self.workdir)
        self.server = subprocess.Popen(
            _expand(server_spec.argv, self.workdir, self.spec.seed),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=env,
        )
        assert self.server.stdout is not None
        if self.async_io:
            assert self.server.stdin is not None
            os.set_blocking(self.server.stdout.fileno(), False)
            os.set_blocking(self.server.stdin.fileno(), False)
        self.selector.register(self.server.stdout, selectors.EVENT_READ, "server")

    def run(self) -> None:
        self.emitter.emit(
            "trial_start",
            {"seed": self.spec.seed, "arm": self.spec.arm, "variant": self.spec.variant},
        )
        self.async_io = True
        try:
            if self.spec.tool_mode is not ToolMode.REPLAY:
                try:
                    with contextlib.redirect_stdout(sys.stderr):
                        self.perturbations = tuple(
                            build(fault) for fault in self.spec.condition.faults
                        )
                except BaseException as exc:
                    self.latches.set_harness(exc)
                    return
                self._start_server()

            self.listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.listener.bind(self.socket_path)
            self.listener.listen(1)
            self.listener.setblocking(False)
            self.selector.register(self.listener, selectors.EVENT_READ, "listener")
            _frame(self.nonce, "ready")

            while not self.stop:
                if self.server is not None and self.server.poll() is not None:
                    with contextlib.suppress(BaseException):
                        self._drain_server_after_exit()
                    self.latches.set_harness("MCP server exited before the agent finished")
                    break
                for key, mask in self.selector.select(timeout=0.05):
                    source = cast(str, key.data)
                    try:
                        if source == "listener":
                            assert self.listener is not None
                            if self.connection is not None:
                                self.latches.set_harness("more than one MCP connection")
                                extra, _ = self.listener.accept()
                                extra.close()
                                continue
                            self.connection, _ = self.listener.accept()
                            self.connection.setblocking(False)
                            self.selector.register(self.connection, selectors.EVENT_READ, "client")
                        elif source == "server_write":
                            self._flush("server")
                        else:
                            if mask & selectors.EVENT_WRITE:
                                self._flush("client")
                            if mask & selectors.EVENT_READ:
                                alive = self._read_lines(source, key.fd)
                                if not alive:
                                    if source == "client":
                                        self.stop = True
                                    else:
                                        self.latches.set_harness(
                                            "MCP server exited before the agent finished"
                                        )
                                        self.stop = True
                                    break
                    except BaseException as exc:
                        self.latches.set_harness(exc)
                        self.stop = True
                        break
            if self.spec.tool_mode is ToolMode.REPLAY and self.replay_index != len(
                self.spec.recording
            ):
                self.latches.set_replay("recording was not consumed exactly")
        except BaseException as exc:
            self.latches.set_harness(exc)
        finally:
            self._cleanup()

    def _cleanup(self) -> None:
        for value in (self.connection, self.listener):
            if value is not None:
                with contextlib.suppress(OSError):
                    value.close()
        if self.server is not None:
            with contextlib.suppress(Exception):
                if self.server.stdin is not None:
                    self.server.stdin.close()
            if self.server.poll() is None:
                with contextlib.suppress(OSError):
                    self.server.kill()
            with contextlib.suppress(Exception):
                self.server.wait()
        self.selector.close()

    def write_result(self) -> None:
        if self.latches.replay is not None:
            termination = Termination.REPLAY_MISS
            detail = self.latches.replay
        elif self.latches.harness is not None:
            termination = Termination.HARNESS_ERROR
            detail = self.latches.harness
        elif self.latches.budget is not None:
            termination = Termination.BUDGET
            detail = self.latches.budget
        else:
            termination = Termination.COMPLETED
            detail = ""
        _frame(
            self.nonce,
            "result",
            result={
                "termination": termination.value,
                "detail": detail,
                "agent_result": None,
                "final_state": None,
                "latches": {
                    "replay": self.latches.replay,
                    "harness": self.latches.harness,
                    "budget": self.latches.budget,
                },
            },
        )


def _read_config() -> tuple[str, TrialSpec, str, str]:
    value = json.load(sys.stdin.buffer)
    if not isinstance(value, dict):
        raise TypeError("boundary config is not an object")
    nonce = value.get("nonce")
    socket_path = value.get("socket_path")
    workdir = value.get("workdir")
    if not isinstance(nonce, str) or not nonce:
        raise ValueError("boundary config has no nonce")
    if not isinstance(socket_path, str) or not isinstance(workdir, str):
        raise ValueError("boundary config has invalid paths")
    return nonce, TrialSpec.model_validate(value.get("spec")), socket_path, workdir


def main() -> int:
    try:
        nonce, spec, socket_path, workdir = _read_config()
    except BaseException:
        return 2
    boundary = _Boundary(nonce, spec, socket_path, workdir)
    signal.signal(signal.SIGTERM, boundary.request_stop)
    boundary.run()
    boundary.write_result()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
