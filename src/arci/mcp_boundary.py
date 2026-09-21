"""Harness-owned MCP recorder, replay server and fault-injection boundary."""

from __future__ import annotations

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
_PROTOCOL = sys.stdout.buffer


def _frame(nonce: str, kind: str, **payload: object) -> None:
    _PROTOCOL.write(canonical_json({"nonce": nonce, "kind": kind, **payload}) + b"\n")
    _PROTOCOL.flush()


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
    occurrence: int
    arguments: dict[str, JsonValue]
    call: ToolCall | None = None


def _id_key(value: JsonValue) -> bytes:
    return canonical_json(value)


def _task_file(workdir: str) -> str:
    """The task JSON the parent wrote into the trial directory before starting us."""
    return os.path.join(workdir, "task.json")


def _expand(values: tuple[str, ...], workdir: str, seed: int) -> list[str]:
    return [
        item.replace("{workdir}", workdir)
        .replace("{seed}", str(seed))
        .replace("{task_file}", _task_file(workdir))
        for item in values
    ]


def _error_result(kind: str, text: str) -> dict[str, JsonValue]:
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
        self.pending: dict[bytes, _Pending] = {}
        self.occurrences: Counter[str] = Counter()
        self.rpc_occurrences: Counter[str] = Counter()
        self.tool_calls = 0
        self.replay_index = 0
        self.recording: list[RecordedCall] = []
        self.perturbations: tuple[Perturbation, ...] = ()
        self.tools_inflight = False

    def request_stop(self, _signum: int, _frame_value: object) -> None:
        self.stop = True

    def _write_client(self, message: dict[str, JsonValue]) -> None:
        assert self.connection is not None
        self.connection.sendall(canonical_json(message) + b"\n")

    def _write_server(self, message: dict[str, JsonValue]) -> None:
        if self.server is None or self.server.stdin is None:
            raise BrokenPipeError("MCP server is unavailable")
        self.server.stdin.write(canonical_json(message) + b"\n")
        self.server.stdin.flush()

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

    def _tool_request(self, message: dict[str, JsonValue], rpc_id: JsonValue) -> None:
        raw_params = message.get("params", {})
        if not isinstance(raw_params, dict):
            self.latches.set_harness("tools/call params must be an object")
            return
        name = raw_params.get("name")
        raw_arguments = raw_params.get("arguments", {})
        if not isinstance(name, str) or not isinstance(raw_arguments, dict):
            self.latches.set_harness("tools/call is malformed")
            return
        arguments = cast(dict[str, JsonValue], copy.deepcopy(raw_arguments))
        canonical_json(arguments)
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
        self.pending[_id_key(rpc_id)] = _Pending(
            method="tools/call",
            rpc_id=rpc_id,
            occurrence=occurrence,
            arguments=arguments,
            call=call,
        )
        self._write_server(message)

    def _rpc_request(self, message: dict[str, JsonValue], method: str, rpc_id: JsonValue) -> None:
        raw_params = message.get("params", {})
        if not isinstance(raw_params, dict):
            self.latches.set_harness(f"{method} params must be an object")
            return
        params = cast(dict[str, JsonValue], copy.deepcopy(raw_params))
        occurrence = self.rpc_occurrences[method]
        self.rpc_occurrences[method] += 1
        key = f"rpc:{method}"
        if self.spec.tool_mode is ToolMode.REPLAY:
            replayed = self._replay(key, params, occurrence)
            if replayed is None:
                self._write_client(
                    {
                        "jsonrpc": "2.0",
                        "id": rpc_id,
                        "error": {"code": -32000, "message": "arci: replay mismatch"},
                    }
                )
                return
            self._write_client(
                {"jsonrpc": "2.0", "id": rpc_id, "result": copy.deepcopy(replayed.value)}
            )
            return
        self.pending[_id_key(rpc_id)] = _Pending(
            method=method,
            rpc_id=rpc_id,
            occurrence=occurrence,
            arguments=params,
        )
        self._write_server(message)

    def _client_message(self, raw: bytes) -> None:
        value = json.loads(raw.decode("utf-8", errors="replace"))
        canonical_json(value)
        if not isinstance(value, dict):
            raise TypeError("MCP client message is not an object")
        message = cast(dict[str, JsonValue], value)
        method = message.get("method")
        if not isinstance(method, str):
            raise TypeError("MCP client message has no method")
        if "id" not in message:
            if method != "notifications/initialized":
                self.latches.set_harness("unsupported MCP notification")
            elif self.spec.tool_mode is not ToolMode.REPLAY:
                self._write_server(message)
            return
        rpc_id = message["id"]
        if method == "tools/call":
            self._tool_request(message, rpc_id)
        elif method in {"initialize", "ping", "tools/list"}:
            self._rpc_request(message, method, rpc_id)
        else:
            self.latches.set_harness("unsupported MCP method")

    def _server_message(self, raw: bytes) -> None:
        value = json.loads(raw.decode("utf-8", errors="replace"))
        canonical_json(value)
        if not isinstance(value, dict):
            raise TypeError("MCP server message is not an object")
        message = cast(dict[str, JsonValue], value)
        if isinstance(message.get("method"), str):
            if "id" in message:
                self.latches.set_harness("server-initiated requests are unsupported")
                self._write_server(
                    {
                        "jsonrpc": "2.0",
                        "id": message["id"],
                        "error": {"code": -32601, "message": "unsupported"},
                    }
                )
            else:
                self.latches.set_harness("server notifications are unsupported")
            return
        if "id" not in message:
            raise TypeError("MCP server response has no id")
        pending = self.pending.pop(_id_key(message["id"]), None)
        if pending is None:
            raise ValueError("unexpected MCP server response")
        reply = copy.deepcopy(message)
        reply["id"] = pending.rpc_id
        if pending.call is None:
            if "error" in reply:
                self.latches.set_harness("supported MCP exchange returned an error")
                self._write_client(reply)
                return
            result_value = reply.get("result")
            canonical_json(result_value)
            result = ToolResult(
                call_id=f"r-{len(self.recording):04d}",
                tool=f"rpc:{pending.method}",
                ok=True,
                value=copy.deepcopy(result_value),
            )
            self._write_client(reply)
            self._record(f"rpc:{pending.method}", pending.arguments, pending.occurrence, result)
            return

        self.tools_inflight = False
        call = pending.call
        if "error" in reply:
            mcp_value: dict[str, JsonValue] = {"error": copy.deepcopy(reply["error"])}
            result = ToolResult(
                call_id=call.call_id,
                tool=call.tool,
                ok=False,
                value=mcp_value,
                error_kind="mcp_error",
            )
        else:
            raw_result = reply.get("result")
            if not isinstance(raw_result, dict):
                raise TypeError("tools/call result is not an object")
            mcp_value = cast(dict[str, JsonValue], copy.deepcopy(raw_result))
            result_type = mcp_value.get("resultType")
            if result_type not in {None, "complete"}:
                self.latches.set_harness("MCP task results are unsupported")
            result = ToolResult(
                call_id=call.call_id,
                tool=call.tool,
                ok=mcp_value.get("isError") is not True,
                value=mcp_value,
                error_kind="mcp_error" if mcp_value.get("isError") is True else None,
            )
            rewritten = self._apply_after(call, result)
            if rewritten.value is None and rewritten.injected_by is not None:
                empty = copy.deepcopy(mcp_value)
                empty["content"] = []
                rewritten = rewritten.model_copy(update={"value": empty}, deep=True)
            result = rewritten
        self._reply_tool(pending.rpc_id, call, result)

    def _read_lines(self, source: str, fd: int) -> bool:
        chunk = os.read(fd, 65536)
        if not chunk:
            return False
        buffer = self.buffers[source]
        buffer.extend(chunk)
        while True:
            newline = buffer.find(b"\n")
            if newline < 0:
                if len(buffer) > _MAX_LINE:
                    raise ValueError("MCP line too long")
                return True
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
        self.selector.register(self.server.stdout, selectors.EVENT_READ, "server")

    def run(self) -> None:
        self.emitter.emit(
            "trial_start",
            {"seed": self.spec.seed, "arm": self.spec.arm, "variant": self.spec.variant},
        )
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
                    self.latches.set_harness("MCP server exited before the agent finished")
                    break
                for key, _mask in self.selector.select(timeout=0.05):
                    source = cast(str, key.data)
                    if source == "listener":
                        assert self.listener is not None
                        if self.connection is not None:
                            self.latches.set_harness("more than one MCP connection")
                            extra, _ = self.listener.accept()
                            extra.close()
                            continue
                        self.connection, _ = self.listener.accept()
                        self.connection.setblocking(True)
                        self.selector.register(self.connection, selectors.EVENT_READ, "client")
                    else:
                        try:
                            alive = self._read_lines(source, key.fd)
                        except BaseException as exc:
                            self.latches.set_harness(exc)
                            self.stop = True
                            break
                        if not alive:
                            if source == "client":
                                self.stop = True
                            elif not self.stop:
                                self.latches.set_harness(
                                    "MCP server exited before the agent finished"
                                )
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
                "recording": [item.model_dump(mode="json") for item in self.recording]
                if self.spec.tool_mode is not ToolMode.REPLAY
                else [item.model_dump(mode="json") for item in self.spec.recording],
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
