"""Harness-owned MCP recorder, replay server and fault-injection boundary."""

from __future__ import annotations

import base64
import contextlib
import copy
import http.client
import importlib
import json
import math
import os
import queue
import random
import selectors
import signal
import socket
import subprocess
import sys
import threading
import time
from collections import Counter
from dataclasses import dataclass
from typing import cast
from urllib.parse import urlsplit

from pydantic import JsonValue

from arci.hashing import canonical_json, hash_record
from arci.interfaces import Perturbation
from arci.perturb import build
from arci.schema import (
    DECISION_MODELS_TOOL,
    DECISION_TOOL,
    DECISION_TOOL_PREFIX,
    RPC_TOOL_PREFIX,
    DecisionSpec,
    RecordedCall,
    Termination,
    ToolCall,
    ToolMode,
    ToolResult,
    TrialSpec,
)
from arci.toolbox import format_diagnostic

_MAX_LINE = 1024 * 1024
_RECORD_CHUNK = 512 * 1024
_MAX_QUEUED_BYTES = 16 * 1024 * 1024
_MAX_HTTP_HEAD = 64 * 1024
_DECISION_CONCURRENCY = "concurrent decision requests are unsupported"
_HTTP_REASONS = {
    200: "OK",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    411: "Length Required",
    413: "Content Too Large",
    422: "Unprocessable Entity",
    500: "Internal Server Error",
    529: "Site is overloaded",
}
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


@dataclass
class _DecisionConnection:
    sock: socket.socket
    received: bytearray
    output: bytearray
    request_complete: bool = False


@dataclass(frozen=True)
class _UpstreamResult:
    status: int
    headers: dict[str, str]
    body: JsonValue
    error: str | None = None


@dataclass
class _DecisionWork:
    call: ToolCall
    request: dict[str, JsonValue]
    results: queue.Queue[_UpstreamResult]
    started: float
    timed_out: bool = False


def _detail(loc: list[str], msg: str, kind: str = "value_error") -> dict[str, JsonValue]:
    return cast(dict[str, JsonValue], {"detail": [{"loc": loc, "msg": msg, "type": kind}]})


def _decision_request_error(value: object) -> dict[str, JsonValue] | None:
    """Return a deterministic TypeSafe-style 422 body, or ``None`` when valid."""
    if not isinstance(value, dict):
        return _detail(["body"], "Input should be an object", "object_type")
    state = value.get("state")
    if not isinstance(state, str | dict | list):
        return _detail(["body", "state"], "Input should be a string, object or array")
    if not isinstance(value.get("model"), str):
        return _detail(["body", "model"], "Input should be a valid string", "string_type")
    questions = value.get("questions")
    if not isinstance(questions, dict) or not questions:
        return _detail(["body", "questions"], "Input should be a non-empty object", "object_type")
    for name, raw_question in questions.items():
        loc = ["body", "questions", str(name)]
        if not isinstance(name, str) or not isinstance(raw_question, dict):
            return _detail(loc, "Question should be an object", "object_type")
        question = cast(dict[str, object], raw_question)
        kind = question.get("type")
        if kind not in {"noul", "choice", "score"}:
            return _detail([*loc, "type"], "Input should be 'noul', 'choice' or 'score'")
        criteria = question.get("criteria")
        if kind == "noul":
            if criteria is not None and (
                not isinstance(criteria, dict)
                or set(criteria) != {"true", "false"}
                or not all(isinstance(item, str) for item in criteria.values())
            ):
                return _detail([*loc, "criteria"], "Noul criteria should define true and false")
        elif kind == "choice":
            if (
                not isinstance(criteria, dict)
                or not 1 <= len(criteria) <= 255
                or not all(
                    isinstance(key, str) and isinstance(item, str) for key, item in criteria.items()
                )
            ):
                return _detail(
                    [*loc, "criteria"], "Choice criteria should contain 1 to 255 options"
                )
        elif (
            not isinstance(criteria, list)
            or not 2 <= len(criteria) <= 10
            or not all(isinstance(item, str) for item in criteria)
        ):
            return _detail([*loc, "criteria"], "Score criteria should contain 2 to 10 levels")
    return None


def _finite_number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value)


def _probabilities(value: object, expected: set[str]) -> dict[str, float] | None:
    if not isinstance(value, dict) or set(value) != expected:
        return None
    probabilities: dict[str, float] = {}
    for key, raw in value.items():
        if not isinstance(key, str) or not _finite_number(raw) or cast(float, raw) < 0.0:
            return None
        probabilities[key] = float(cast(int | float, raw))
    if not math.isclose(sum(probabilities.values()), 1.0, abs_tol=1e-6):
        return None
    return probabilities


def _validate_decision_response(
    value: object, request: dict[str, JsonValue], model: str
) -> dict[str, JsonValue]:
    """Validate and deep-copy a successful System One response."""
    canonical_json(value)
    if not isinstance(value, dict) or value.get("model") != model:
        raise ValueError("decision response has an invalid model")
    raw_usage = value.get("usage")
    if not isinstance(raw_usage, dict) or any(
        not isinstance(raw_usage.get(name), int) or isinstance(raw_usage.get(name), bool)
        for name in ("input_tokens", "output_tokens")
    ):
        raise ValueError("decision response has invalid usage")
    questions = cast(dict[str, JsonValue], request["questions"])
    raw_answers = value.get("answers")
    if not isinstance(raw_answers, dict) or set(raw_answers) != set(questions):
        raise ValueError("decision response answers do not match the questions")
    for name, raw_question in questions.items():
        question = cast(dict[str, JsonValue], raw_question)
        answer = raw_answers.get(name)
        if not isinstance(answer, dict) or answer.get("type") != question.get("type"):
            raise ValueError("decision response has an invalid answer type")
        kind = question["type"]
        if kind == "noul":
            noul = answer.get("noul")
            if not _finite_number(noul) or not 0.0 <= float(cast(int | float, noul)) <= 1.0:
                raise ValueError("decision response has an invalid noul")
            continue
        criteria = question.get("criteria")
        expected = (
            set(cast(dict[str, JsonValue], criteria))
            if kind == "choice"
            else {str(index) for index in range(len(cast(list[JsonValue], criteria)))}
        )
        probabilities = _probabilities(answer.get("probabilities"), expected)
        confidence = answer.get("confidence")
        if (
            probabilities is None
            or not _finite_number(confidence)
            or not (0.0 <= float(cast(int | float, confidence)) <= 1.0)
        ):
            raise ValueError("decision response has invalid probabilities or confidence")
        if kind == "choice":
            choice = answer.get("choice")
            if (
                not isinstance(choice, str)
                or choice not in expected
                or probabilities[choice] != max(probabilities.values())
            ):
                raise ValueError("decision response has an invalid choice")
        else:
            legend = answer.get("legend")
            score = answer.get("score")
            if (
                not isinstance(legend, dict)
                or set(legend) != expected
                or not all(isinstance(item, str) for item in legend.values())
                or not _finite_number(score)
            ):
                raise ValueError("decision response has an invalid score")
    copied = cast(dict[str, JsonValue], copy.deepcopy(value))
    canonical_json(copied)
    return copied


def _validate_models_response(value: object) -> dict[str, JsonValue]:
    canonical_json(value)
    if not isinstance(value, dict) or not isinstance(value.get("models"), list):
        raise ValueError("decision models response has an invalid shape")
    for model in value["models"]:
        if not isinstance(model, dict) or any(
            not isinstance(model.get(name), str) for name in ("name", "description", "release_date")
        ):
            raise ValueError("decision models response has an invalid shape")
    return cast(dict[str, JsonValue], copy.deepcopy(value))


def _allowed_headers(headers: dict[str, str]) -> dict[str, str]:
    allowed: dict[str, str] = {}
    for name, value in headers.items():
        if name.lower() != "retry-after":
            continue
        if "\r" in value or "\n" in value:
            raise ValueError("decision upstream returned an invalid header")
        allowed["retry-after"] = value
    return allowed


def _http_response(status: int, body: JsonValue, headers: dict[str, str] | None = None) -> bytes:
    raw = canonical_json(body)
    lines = [
        f"HTTP/1.1 {status} {_HTTP_REASONS.get(status, 'Error')}",
        "Content-Type: application/json",
        f"Content-Length: {len(raw)}",
        "Connection: close",
    ]
    for name, value in (headers or {}).items():
        lines.append(f"{name}: {value}")
    return ("\r\n".join(lines) + "\r\n\r\n").encode("ascii") + raw


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
    def __init__(
        self,
        nonce: str,
        spec: TrialSpec,
        socket_path: str,
        workdir: str,
        decision_token: str | None = None,
    ) -> None:
        self.nonce = nonce
        self.spec = spec
        self.socket_path = socket_path
        self.workdir = workdir
        self.latches = _Latches(nonce)
        self.emitter = _Emitter(spec, nonce)
        self.stop = False
        self.listener: socket.socket | None = None
        self.connection: socket.socket | None = None
        self.decision_token = decision_token
        self.decision_listener: socket.socket | None = None
        self.decision_connection: _DecisionConnection | None = None
        self.rejected_decisions: dict[socket.socket, bytearray] = {}
        self.decision_work: _DecisionWork | None = None
        self.decision_count = 0
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
        self.mcp_closed = False
        self.mcp_server_done = False

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

    def _refresh_decision_events(self) -> None:
        connection = self.decision_connection
        if connection is None:
            return
        events = selectors.EVENT_READ
        if connection.output:
            events |= selectors.EVENT_WRITE
        self.selector.modify(connection.sock, events, "decision")

    def _close_decision_connection(self) -> None:
        connection = self.decision_connection
        if connection is None:
            return
        with contextlib.suppress(Exception):
            self.selector.unregister(connection.sock)
        with contextlib.suppress(OSError):
            connection.sock.close()
        self.decision_connection = None

    def _queue_http(
        self, status: int, body: JsonValue, headers: dict[str, str] | None = None
    ) -> None:
        connection = self.decision_connection
        if connection is None:
            return
        data = _http_response(status, body, headers)
        if len(connection.output) + len(data) > _MAX_QUEUED_BYTES:
            raise BufferError("decision output queue exceeded its limit")
        connection.output.extend(data)
        connection.request_complete = True
        self._refresh_decision_events()

    def _flush_decision(self) -> None:
        connection = self.decision_connection
        if connection is None or not connection.output:
            return
        try:
            sent = connection.sock.send(connection.output)
        except BlockingIOError:
            return
        except (ConnectionError, OSError):
            self._close_decision_connection()
            return
        if sent:
            del connection.output[:sent]
        if not connection.output and connection.request_complete:
            self._close_decision_connection()
        else:
            self._refresh_decision_events()

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

    def _start_decision_worker(self, call: ToolCall, request: dict[str, JsonValue]) -> None:
        spec = self.spec.decisions
        if spec is None:
            raise ValueError("decision request without decision configuration")
        results: queue.Queue[_UpstreamResult] = queue.Queue(maxsize=1)
        pinned = copy.deepcopy(request)
        pinned["model"] = spec.model

        def invoke() -> None:
            try:
                if spec.upstream == "fixture":
                    assert spec.fixture is not None
                    module_name, _, attribute = spec.fixture.partition(":")
                    fixture = getattr(importlib.import_module(module_name), attribute)
                    if not callable(fixture):
                        raise TypeError("decision fixture is not callable")
                    body = fixture(copy.deepcopy(pinned), self.spec.seed, call.occurrence)
                    result = _UpstreamResult(200, {}, cast(JsonValue, copy.deepcopy(body)))
                else:
                    result = self._http_upstream("POST", "/v1/systemone", pinned, spec)
            except BaseException as exc:
                result = _UpstreamResult(500, {}, None, format_diagnostic(exc))
            with contextlib.suppress(queue.Full):
                results.put_nowait(result)

        self.decision_work = _DecisionWork(call, copy.deepcopy(request), results, time.monotonic())
        threading.Thread(target=invoke, daemon=True).start()

    def _start_models_worker(self, occurrence: int) -> None:
        spec = self.spec.decisions
        if spec is None:
            raise ValueError("models request without decision configuration")
        call = ToolCall(
            call_id=f"r-{len(self.recording):04d}",
            tool=DECISION_MODELS_TOOL,
            arguments={},
            occurrence=occurrence,
        )
        results: queue.Queue[_UpstreamResult] = queue.Queue(maxsize=1)

        def invoke() -> None:
            try:
                if spec.upstream == "fixture":
                    result = _UpstreamResult(
                        200,
                        {},
                        {
                            "models": [
                                {
                                    "name": spec.model,
                                    "description": "arci fixture",
                                    "release_date": "2026-09-15",
                                }
                            ]
                        },
                    )
                else:
                    result = self._http_upstream("GET", "/v1/models", None, spec)
            except BaseException as exc:
                result = _UpstreamResult(500, {}, None, format_diagnostic(exc))
            with contextlib.suppress(queue.Full):
                results.put_nowait(result)

        self.decision_work = _DecisionWork(call, {}, results, time.monotonic())
        threading.Thread(target=invoke, daemon=True).start()

    def _http_upstream(
        self,
        method: str,
        path: str,
        body: dict[str, JsonValue] | None,
        spec: DecisionSpec,
    ) -> _UpstreamResult:
        api_key = os.environ.get("TYPESAFE_API_KEY")
        if not api_key:
            raise RuntimeError("TYPESAFE_API_KEY is not set for the decision upstream")
        parts = urlsplit(spec.base_url)
        if parts.hostname is None:
            raise ValueError("decision upstream has no host")
        port = parts.port
        connection_type = (
            http.client.HTTPSConnection if parts.scheme == "https" else http.client.HTTPConnection
        )
        connection = connection_type(parts.hostname, port, timeout=spec.request_seconds)
        raw = None if body is None else canonical_json(body)
        headers = {"Authorization": f"Bearer {api_key}"}
        if raw is not None:
            headers["Content-Type"] = "application/json"
        try:
            connection.request(method, path, body=raw, headers=headers)
            response = connection.getresponse()
            payload = response.read()
            try:
                value = json.loads(payload.decode("utf-8"))
                canonical_json(value)
            except (json.JSONDecodeError, UnicodeError, TypeError, ValueError) as exc:
                raise ValueError("decision upstream returned non-JSON") from exc
            return _UpstreamResult(
                response.status,
                _allowed_headers(dict(response.getheaders())),
                cast(JsonValue, value),
            )
        finally:
            connection.close()

    def _decision_result(self, result: ToolResult) -> None:
        value = cast(dict[str, JsonValue], copy.deepcopy(result.value))
        status = cast(int, value["status"])
        headers = cast(dict[str, str], value["headers"])
        self._emit_finish(result)
        if self.spec.tool_mode is ToolMode.RECORD:
            work = self.decision_work
            if work is None:
                raise RuntimeError("decision work vanished before recording")
            self._record(result.tool, work.request, work.call.occurrence, result)
        self.decision_work = None
        self._queue_http(status, value["body"], headers)

    def _finish_decision_work(self, upstream: _UpstreamResult) -> None:
        work = self.decision_work
        spec = self.spec.decisions
        if work is None or spec is None:
            return
        call = work.call
        if upstream.error is not None:
            self.latches.set_harness(upstream.error)
            self.decision_work = None
            self._queue_http(500, {"detail": "arci: decision upstream failed"})
            return
        if call.tool == DECISION_MODELS_TOOL:
            if upstream.status != 200:
                self.latches.set_harness("decision models upstream failed")
                self.decision_work = None
                self._queue_http(500, {"detail": "arci: decision upstream failed"})
                return
            models_body = _validate_models_response(upstream.body)
            value = cast(
                dict[str, JsonValue],
                {
                    "status": 200,
                    "headers": _allowed_headers(upstream.headers),
                    "body": models_body,
                },
            )
            result = ToolResult(
                call_id=call.call_id,
                tool=call.tool,
                ok=True,
                value=value,
            )
            self._record(call.tool, {}, call.occurrence, result)
            self.decision_work = None
            self._queue_http(200, value["body"], cast(dict[str, str], value["headers"]))
            return
        if upstream.status == 422:
            value = cast(
                dict[str, JsonValue],
                {
                    "status": 422,
                    "headers": _allowed_headers(upstream.headers),
                    "body": copy.deepcopy(upstream.body),
                },
            )
            canonical_json(value)
            result = ToolResult(
                call_id=call.call_id,
                tool=call.tool,
                ok=False,
                value=value,
                error_kind="http_422",
            )
            result = self._apply_after(call, result)
            canonical_json(result.model_dump(mode="python"))
        elif upstream.status == 200:
            body = _validate_decision_response(upstream.body, work.request, spec.model)
            value = cast(
                dict[str, JsonValue],
                {
                    "status": 200,
                    "headers": _allowed_headers(upstream.headers),
                    "body": body,
                },
            )
            result = ToolResult(call_id=call.call_id, tool=call.tool, ok=True, value=value)
            result = self._apply_after(call, result)
            rewritten = cast(dict[str, JsonValue], result.value)
            rewritten_body = _validate_decision_response(
                rewritten.get("body"), work.request, spec.model
            )
            result = result.model_copy(
                update={
                    "value": {
                        "status": rewritten.get("status"),
                        "headers": _allowed_headers(cast(dict[str, str], rewritten.get("headers"))),
                        "body": rewritten_body,
                    }
                },
                deep=True,
            )
        else:
            self.latches.set_harness(f"decision upstream returned HTTP {upstream.status}")
            self.decision_work = None
            self._queue_http(500, {"detail": "arci: decision upstream failed"})
            return
        self._decision_result(result)

    def _poll_decision_work(self) -> None:
        work = self.decision_work
        spec = self.spec.decisions
        if work is None or spec is None:
            return
        if work.timed_out:
            return
        try:
            result = work.results.get_nowait()
        except queue.Empty:
            result = None
        if result is not None:
            try:
                self._finish_decision_work(result)
            except BaseException as exc:
                self.latches.set_harness(exc)
                self.decision_work = None
                self._queue_http(500, {"detail": "arci: decision upstream failed"})
            return
        if time.monotonic() - work.started >= spec.request_seconds:
            self.latches.set_harness("decision upstream timed out")
            # Keep the timed-out work installed until shutdown.  The daemon
            # call cannot be cancelled safely, and retaining it prevents an
            # SDK retry from starting a second upstream worker concurrently.
            work.timed_out = True
            self._queue_http(500, {"detail": "arci: decision upstream failed"})

    def _close_rejected_decision(self, connection: socket.socket) -> None:
        self.rejected_decisions.pop(connection, None)
        with contextlib.suppress(Exception):
            self.selector.unregister(connection)
        with contextlib.suppress(OSError):
            connection.close()

    def _flush_rejected_decision(self, connection: socket.socket) -> None:
        output = self.rejected_decisions.get(connection)
        if output is None:
            return
        try:
            sent = connection.send(output)
        except BlockingIOError:
            return
        except (ConnectionError, OSError):
            self._close_rejected_decision(connection)
            return
        if sent:
            del output[:sent]
        if not output:
            self._close_rejected_decision(connection)

    def _reject_concurrent_decision(self, connection: socket.socket) -> None:
        self.latches.set_harness(_DECISION_CONCURRENCY)
        connection.setblocking(False)
        response = _http_response(500, {"detail": f"arci: {_DECISION_CONCURRENCY}"})
        self.rejected_decisions[connection] = bytearray(response)
        self.selector.register(connection, selectors.EVENT_WRITE, "decision_reject")

    def _accept_decision(self) -> None:
        assert self.decision_listener is not None
        connection, _ = self.decision_listener.accept()
        if (
            self.decision_connection is not None
            or self.decision_work is not None
            or self.tools_inflight
        ):
            self._reject_concurrent_decision(connection)
            return
        connection.setblocking(False)
        self.decision_connection = _DecisionConnection(connection, bytearray(), bytearray())
        self.selector.register(connection, selectors.EVENT_READ, "decision")

    def _local_http_error(self, status: int, body: JsonValue) -> None:
        self._queue_http(status, body)

    def _admit_decision(self, request: dict[str, JsonValue]) -> None:
        spec = self.spec.decisions
        if spec is None:
            self._local_http_error(404, {"detail": "not found"})
            return
        if (
            self.tool_calls >= self.spec.budgets.max_tool_calls
            or self.decision_count >= spec.max_decisions
        ):
            self.latches.set_budget("decision budget exhausted")
            self._local_http_error(403, {"detail": "arci: decision budget exceeded"})
            return
        occurrence = self.occurrences[DECISION_TOOL]
        call = ToolCall(
            call_id=f"c-{self.tool_calls:04d}",
            tool=DECISION_TOOL,
            arguments=copy.deepcopy(request),
            occurrence=occurrence,
        )
        self.tool_calls += 1
        self.decision_count += 1
        self.occurrences[DECISION_TOOL] += 1
        self._emit_start(call)
        if self.spec.tool_mode is ToolMode.REPLAY:
            replayed = self._replay(DECISION_TOOL, request, occurrence)
            if replayed is None:
                self._local_http_error(500, {"detail": "arci: replay mismatch"})
                return
            result = replayed.model_copy(
                update={"call_id": call.call_id, "tool": DECISION_TOOL}, deep=True
            )
            value = cast(dict[str, JsonValue], copy.deepcopy(result.value))
            self._emit_finish(result)
            self._queue_http(
                cast(int, value["status"]),
                value["body"],
                cast(dict[str, str], value["headers"]),
            )
            return
        injected = self._apply_before(call)
        if injected is not None:
            self.decision_work = _DecisionWork(
                call, copy.deepcopy(request), queue.Queue(maxsize=1), time.monotonic()
            )
            self._decision_result(injected)
            return
        self._start_decision_worker(call, request)

    def _serve_models(self) -> None:
        occurrence = self.rpc_occurrences[DECISION_MODELS_TOOL]
        self.rpc_occurrences[DECISION_MODELS_TOOL] += 1
        if self.spec.tool_mode is ToolMode.REPLAY:
            replayed = self._replay(DECISION_MODELS_TOOL, {}, occurrence)
            if replayed is None:
                self._local_http_error(500, {"detail": "arci: replay mismatch"})
                return
            value = cast(dict[str, JsonValue], copy.deepcopy(replayed.value))
            self._queue_http(
                cast(int, value["status"]),
                value["body"],
                cast(dict[str, str], value["headers"]),
            )
            return
        self._start_models_worker(occurrence)

    def _handle_http_request(
        self, method: str, path: str, headers: dict[str, str], raw_body: bytes
    ) -> None:
        if headers.get("authorization") != f"Bearer {self.decision_token}":
            self._local_http_error(401, {"detail": "invalid api key"})
            return
        if method == "GET" and path == "/v1/models":
            self._serve_models()
            return
        if method != "POST" or path != "/v1/systemone":
            self._local_http_error(404, {"detail": "not found"})
            return
        try:
            value = json.loads(raw_body.decode("utf-8"))
            canonical_json(value)
        except (json.JSONDecodeError, UnicodeError, TypeError, ValueError):
            self._local_http_error(422, _detail(["body"], "Input should be valid JSON"))
            return
        error = _decision_request_error(value)
        if error is not None:
            self._local_http_error(422, error)
            return
        self._admit_decision(cast(dict[str, JsonValue], copy.deepcopy(value)))

    def _consume_http(self, chunk: bytes) -> None:
        connection = self.decision_connection
        spec = self.spec.decisions
        if connection is None or spec is None:
            return
        connection.received.extend(chunk)
        head_end = connection.received.find(b"\r\n\r\n")
        if head_end < 0:
            if len(connection.received) > _MAX_HTTP_HEAD:
                self._local_http_error(413, {"detail": "request too large"})
            return
        if head_end > _MAX_HTTP_HEAD:
            self._local_http_error(413, {"detail": "request too large"})
            return
        try:
            lines = bytes(connection.received[:head_end]).decode("iso-8859-1").split("\r\n")
            request_line = lines[0].split(" ")
            if len(request_line) != 3 or request_line[2] != "HTTP/1.1":
                raise ValueError("invalid request line")
            method, path, _version = request_line
            headers: dict[str, str] = {}
            for line in lines[1:]:
                name, separator, value = line.partition(":")
                if not separator or not name:
                    raise ValueError("invalid header")
                headers[name.strip().lower()] = value.strip()
        except (UnicodeError, ValueError):
            self._local_http_error(422, _detail(["request"], "Invalid HTTP request"))
            return
        if "chunked" in headers.get("transfer-encoding", "").lower():
            self._local_http_error(411, {"detail": "content-length required"})
            return
        raw_length = headers.get("content-length")
        if method == "POST" and raw_length is None:
            self._local_http_error(411, {"detail": "content-length required"})
            return
        try:
            content_length = 0 if raw_length is None else int(raw_length)
        except ValueError:
            self._local_http_error(411, {"detail": "content-length required"})
            return
        if content_length < 0:
            self._local_http_error(411, {"detail": "content-length required"})
            return
        if content_length > spec.max_body_bytes:
            self._local_http_error(413, {"detail": "request too large"})
            return
        body_start = head_end + 4
        if len(connection.received) - body_start < content_length:
            return
        body = bytes(connection.received[body_start : body_start + content_length])
        if len(connection.received) != body_start + content_length:
            self._local_http_error(422, _detail(["request"], "Only one request is allowed"))
            return
        self._handle_http_request(method, path, headers, body)

    def _read_decision(self) -> None:
        connection = self.decision_connection
        if connection is None:
            return
        try:
            chunk = connection.sock.recv(65536)
        except (ConnectionError, OSError):
            self._close_decision_connection()
            return
        if not chunk:
            self._close_decision_connection()
            return
        self._consume_http(chunk)

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
        if name.startswith((DECISION_TOOL_PREFIX, RPC_TOOL_PREFIX)):
            self._client_error(rpc_id, -32601, f"unknown tool {name}")
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
        if self.decision_connection is not None or self.decision_work is not None:
            self.latches.set_harness(_DECISION_CONCURRENCY)
            self._write_client(
                {
                    "jsonrpc": "2.0",
                    "id": rpc_id,
                    "result": _error_result("error", f"arci: {_DECISION_CONCURRENCY}"),
                }
            )
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
            name = cast(str, item["name"])
            if name.startswith((DECISION_TOOL_PREFIX, RPC_TOOL_PREFIX)):
                self.latches.set_harness("MCP server advertised a reserved tool name")
            names.add(name)
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

    def _close_mcp_session(self) -> None:
        self.mcp_closed = True
        if self.connection is not None:
            with contextlib.suppress(Exception):
                self.selector.unregister(self.connection)
            with contextlib.suppress(OSError):
                self.connection.close()
            self.connection = None
        if self.listener is not None:
            with contextlib.suppress(Exception):
                self.selector.unregister(self.listener)
            with contextlib.suppress(OSError):
                self.listener.close()
            self.listener = None

    def _drain_client_after_server_exit(self) -> None:
        """Observe an already-written client EOF before classifying server exit."""
        connection = self.connection
        if connection is None:
            return
        drained = 0
        while drained <= _MAX_QUEUED_BYTES:
            try:
                chunk = os.read(connection.fileno(), 65536)
            except BlockingIOError:
                return
            if not chunk:
                self._close_mcp_session()
                return
            drained += len(chunk)
            self._consume_chunk("client", chunk)

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
            ready: dict[str, object] = {}
            if self.spec.decisions is not None:
                if not self.decision_token:
                    raise ValueError("boundary config has no decision token")
                self.decision_listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.decision_listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.decision_listener.bind(("127.0.0.1", 0))
                self.decision_listener.listen(8)
                self.decision_listener.setblocking(False)
                self.selector.register(
                    self.decision_listener, selectors.EVENT_READ, "decision_listener"
                )
                ready["decision_port"] = self.decision_listener.getsockname()[1]
            _frame(self.nonce, "ready", **ready)

            while not self.stop:
                self._poll_decision_work()
                selected = list(self.selector.select(timeout=0.05))
                # If the agent closed MCP at the same instant the server exited,
                # observe the client EOF first.  Late decision requests are valid
                # after MCP EOF, so classification must not depend on selector or
                # process-scheduling order.
                selected.sort(key=lambda item: 0 if item[0].data == "client" else 1)
                for key, mask in selected:
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
                        elif source == "decision_listener":
                            self._accept_decision()
                        elif source == "decision":
                            if mask & selectors.EVENT_WRITE:
                                self._flush_decision()
                            if mask & selectors.EVENT_READ:
                                self._read_decision()
                        elif source == "decision_reject":
                            self._flush_rejected_decision(cast(socket.socket, key.fileobj))
                        elif source == "server_write":
                            self._flush("server")
                        else:
                            if mask & selectors.EVENT_WRITE:
                                self._flush("client")
                            if mask & selectors.EVENT_READ:
                                alive = self._read_lines(source, key.fd)
                                if not alive:
                                    if source == "client":
                                        if self.spec.decisions is None:
                                            self.stop = True
                                        else:
                                            self._close_mcp_session()
                                    else:
                                        if (
                                            self.spec.decisions is not None
                                            and self.mcp_closed
                                            and not self.pending
                                        ):
                                            self.mcp_server_done = True
                                            with contextlib.suppress(Exception):
                                                assert self.server is not None
                                                assert self.server.stdout is not None
                                                self.selector.unregister(self.server.stdout)
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
                if (
                    not self.stop
                    and self.server is not None
                    and not self.mcp_server_done
                    and self.server.poll() is not None
                ):
                    with contextlib.suppress(BaseException):
                        self._drain_server_after_exit()
                    if self.spec.decisions is not None and not self.mcp_closed:
                        self._drain_client_after_server_exit()
                    if self.spec.decisions is not None and self.mcp_closed and not self.pending:
                        self.mcp_server_done = True
                        if self.server.stdout is not None:
                            with contextlib.suppress(Exception):
                                self.selector.unregister(self.server.stdout)
                    else:
                        self.latches.set_harness("MCP server exited before the agent finished")
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
        self._close_decision_connection()
        for connection in tuple(self.rejected_decisions):
            self._close_rejected_decision(connection)
        for value in (self.connection, self.listener, self.decision_listener):
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


def _read_config() -> tuple[str, TrialSpec, str, str, str | None]:
    value = json.load(sys.stdin.buffer)
    if not isinstance(value, dict):
        raise TypeError("boundary config is not an object")
    nonce = value.get("nonce")
    socket_path = value.get("socket_path")
    workdir = value.get("workdir")
    decision_token = value.get("decision_token")
    if not isinstance(nonce, str) or not nonce:
        raise ValueError("boundary config has no nonce")
    if not isinstance(socket_path, str) or not isinstance(workdir, str):
        raise ValueError("boundary config has invalid paths")
    spec = TrialSpec.model_validate(value.get("spec"))
    if spec.decisions is not None and (not isinstance(decision_token, str) or not decision_token):
        raise ValueError("boundary config has no decision token")
    if spec.decisions is None and decision_token is not None:
        raise ValueError("boundary config has an unexpected decision token")
    return nonce, spec, socket_path, workdir, cast(str | None, decision_token)


def main() -> int:
    try:
        nonce, spec, socket_path, workdir, decision_token = _read_config()
    except BaseException:
        return 2
    boundary = _Boundary(nonce, spec, socket_path, workdir, decision_token)
    signal.signal(signal.SIGTERM, boundary.request_stop)
    boundary.run()
    boundary.write_result()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
