"""Harness-owned MCP recorder, replay server and fault-injection boundary."""

from __future__ import annotations

import base64
import contextlib
import copy
import email.utils
import http.client
import importlib
import importlib.metadata
import json
import math
import os
import queue
import random
import selectors
import signal
import socket
import ssl
import subprocess
import sys
import threading
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC
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
_MAX_JSON_DEPTH = 64
_DECISION_CONCURRENCY = "concurrent decision requests are unsupported"
_HTTP_REASONS = {
    200: "OK",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    411: "Length Required",
    413: "Content Too Large",
    417: "Expectation Failed",
    422: "Unprocessable Entity",
    500: "Internal Server Error",
    529: "Site is overloaded",
}
_PROTOCOL = sys.stdout.buffer


class _DecisionTransportError(RuntimeError):
    """An already-normalised, deterministic upstream transport diagnostic."""


def _scrub_diagnostic(detail: str | BaseException) -> str:
    """Format a boundary diagnostic and remove the real upstream credential."""
    clean = format_diagnostic(
        str(detail) if isinstance(detail, _DecisionTransportError) else detail
    )
    api_key = os.environ.get("TYPESAFE_API_KEY")
    if api_key:
        clean = clean.replace(api_key, "<redacted>")
    return clean


def upstream_diagnostic(detail: str | BaseException) -> str:
    """Return a key-free upstream diagnostic within the v0.6 wire limit."""
    return _scrub_diagnostic(detail)[:299]


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

    def _set(self, attribute: str, wire_name: str, detail: str | BaseException) -> None:
        if getattr(self, attribute) is None:
            clean = _scrub_diagnostic(detail)
            setattr(self, attribute, clean)
            _frame(self.nonce, "latch", latch=wire_name, detail=clean)

    def set_replay(self, detail: str) -> None:
        self._set("replay", "replay_miss", detail)

    def set_harness(self, detail: str | BaseException) -> None:
        self._set("harness", "harness_error", detail)

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
    request_parsed: bool = False
    request_complete: bool = False


@dataclass(frozen=True)
class UpstreamResult:
    status: int
    headers: dict[str, str]
    body: JsonValue
    error: str | None = None
    attempts: int = 1
    first_status: int | None = None


_UpstreamResult = UpstreamResult


@dataclass(frozen=True)
class _DecisionCompletion:
    finished_at: float
    result: _UpstreamResult


@dataclass
class _DecisionWork:
    call: ToolCall
    request: dict[str, JsonValue]
    results: queue.Queue[_DecisionCompletion]
    started: float
    timed_out: bool = False


@dataclass(frozen=True)
class _HttpRequest:
    method: str
    path: str
    headers: dict[str, str]
    body: bytes


class _HttpRequestError(Exception):
    def __init__(self, status: int, body: JsonValue) -> None:
        super().__init__(status)
        self.status = status
        self.body = body


def _detail(loc: list[str], msg: str, kind: str = "value_error") -> dict[str, JsonValue]:
    return cast(dict[str, JsonValue], {"detail": [{"loc": loc, "msg": msg, "type": kind}]})


def _json_depth_exceeded(value: object, limit: int = _MAX_JSON_DEPTH) -> bool:
    """Check JSON container depth iteratively; repeated containers are non-JSON cycles."""
    stack: list[tuple[object, int]] = [(value, 1)]
    seen: set[int] = set()
    while stack:
        current, depth = stack.pop()
        if not isinstance(current, dict | list):
            continue
        if depth > limit or id(current) in seen:
            return True
        seen.add(id(current))
        if isinstance(current, dict):
            children = cast(dict[object, object], current).values()
        else:
            children = cast(list[object], current)
        stack.extend((child, depth + 1) for child in children)
    return False


def _structured_description(value: object, *, null: bool) -> bool:
    return isinstance(value, str | dict | list) or (null and value is None)


def _validate_decision_request(value: object) -> dict[str, JsonValue] | None:
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
        if not isinstance(kind, str) or kind not in {"noul", "choice", "score"}:
            return _detail([*loc, "type"], "Input should be 'noul', 'choice' or 'score'")
        if not _structured_description(question.get("instructions"), null=True):
            return _detail(
                [*loc, "instructions"], "Instructions should be a string, object, array or null"
            )
        criteria = question.get("criteria")
        if kind == "noul":
            if criteria is not None and (
                not isinstance(criteria, dict)
                or not set(criteria).issubset({"true", "false"})
                or not all(_structured_description(item, null=True) for item in criteria.values())
            ):
                return _detail([*loc, "criteria"], "Noul criteria has an invalid shape")
        elif kind == "choice":
            if (
                not isinstance(criteria, dict)
                or not 1 <= len(criteria) <= 255
                or not all(
                    isinstance(key, str) and _structured_description(item, null=True)
                    for key, item in criteria.items()
                )
            ):
                return _detail(
                    [*loc, "criteria"], "Choice criteria should contain 1 to 255 options"
                )
        elif (
            not isinstance(criteria, list)
            or not 2 <= len(criteria) <= 10
            or not all(_structured_description(item, null=False) for item in criteria)
        ):
            return _detail([*loc, "criteria"], "Score criteria should contain 2 to 10 levels")
    return None


def _decision_request_error(value: object) -> dict[str, JsonValue] | None:
    """Return a deterministic TypeSafe-style 422 body; validation is total."""
    try:
        if _json_depth_exceeded(value):
            return _detail(["body"], f"JSON nesting may not exceed {_MAX_JSON_DEPTH} levels")
        canonical_json(value)
        return _validate_decision_request(value)
    except BaseException:
        return _detail(["body"], "Input should be valid JSON")


def _decision_deadline_expired(started: float, request_seconds: float, at: float) -> bool:
    return at - started >= request_seconds


def _transports_conflict(*, pending_mcp: bool, active_decision: bool) -> bool:
    return pending_mcp and active_decision


def _parse_http_request(received: bytes, max_body_bytes: int) -> _HttpRequest | None:
    """Parse the first HTTP request only; trailing pipelined bytes are ignored."""
    head_end = received.find(b"\r\n\r\n")
    if head_end < 0:
        if len(received) > _MAX_HTTP_HEAD:
            raise _HttpRequestError(413, {"detail": "request too large"})
        return None
    if head_end > _MAX_HTTP_HEAD:
        raise _HttpRequestError(413, {"detail": "request too large"})
    try:
        lines = received[:head_end].decode("iso-8859-1").split("\r\n")
        request_line = lines[0].split(" ")
        if len(request_line) != 3 or request_line[2] != "HTTP/1.1":
            raise ValueError("invalid request line")
        method, path, _version = request_line
        headers: dict[str, str] = {}
        for line in lines[1:]:
            name, separator, header_value = line.partition(":")
            if not separator or not name:
                raise ValueError("invalid header")
            headers[name.strip().lower()] = header_value.strip()
    except (UnicodeError, ValueError) as exc:
        raise _HttpRequestError(422, _detail(["request"], "Invalid HTTP request")) from exc
    if "expect" in headers:
        raise _HttpRequestError(417, {"detail": "expectation failed"})
    if "chunked" in headers.get("transfer-encoding", "").lower():
        raise _HttpRequestError(411, {"detail": "content-length required"})
    raw_length = headers.get("content-length")
    if method == "POST" and raw_length is None:
        raise _HttpRequestError(411, {"detail": "content-length required"})
    try:
        content_length = 0 if raw_length is None else int(raw_length)
    except ValueError as exc:
        raise _HttpRequestError(411, {"detail": "content-length required"}) from exc
    if content_length < 0:
        raise _HttpRequestError(411, {"detail": "content-length required"})
    if content_length > max_body_bytes:
        raise _HttpRequestError(413, {"detail": "request too large"})
    body_start = head_end + 4
    if len(received) - body_start < content_length:
        return None
    return _HttpRequest(
        method=method,
        path=path,
        headers=headers,
        body=received[body_start : body_start + content_length],
    )


def _finite_number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value)


def _probabilities(value: object, expected: set[str]) -> dict[str, float] | None:
    if not isinstance(value, dict) or set(value) != expected:
        return None
    probabilities: dict[str, float] = {}
    for key, raw in value.items():
        if (
            not isinstance(key, str)
            or not _finite_number(raw)
            or not 0.0 <= float(cast(int | float, raw)) <= 1.0
        ):
            return None
        probabilities[key] = float(cast(int | float, raw))
    if not math.isclose(sum(probabilities.values()), 1.0, abs_tol=1e-3):
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
            if not isinstance(legend, dict) or set(legend) != expected or not _finite_number(score):
                raise ValueError("decision response has an invalid score")
            # Legend values are level descriptions: text or structure, never null, numbers or bools.
            if any(not isinstance(v, str | dict | list) for v in legend.values()):
                raise ValueError("decision response has an invalid score legend")
    copied = cast(dict[str, JsonValue], copy.deepcopy(value))
    canonical_json(copied)
    return copied


def validate_decision_response(
    value: object, request: dict[str, JsonValue], model: str
) -> dict[str, JsonValue]:
    return _validate_decision_response(value, request, model)


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


def validate_models_response(value: object) -> dict[str, JsonValue]:
    return _validate_models_response(value)


def _allowed_headers(headers: dict[str, str]) -> dict[str, str]:
    allowed: dict[str, str] = {}
    for name, value in headers.items():
        lowered = name.lower()
        if lowered not in {"retry-after", "retry-after-ms", "x-typesafe-request-id"}:
            continue
        if "\r" in value or "\n" in value:
            raise ValueError("decision upstream returned an invalid header")
        allowed[lowered] = value
    return allowed


def _join_upstream_path(base_url: str, endpoint: str) -> str:
    """Join a validated base URL path prefix to an absolute API endpoint."""
    prefix = urlsplit(base_url).path.rstrip("/")
    return f"{prefix}/{endpoint.lstrip('/')}"


def _retry_delay(headers: dict[str, str], *, now: float | None = None) -> float:
    """Return the provider-requested retry delay, or the deterministic 500 ms default."""
    lowered = {name.lower(): value for name, value in headers.items()}
    raw_milliseconds = lowered.get("retry-after-ms")
    if raw_milliseconds is not None:
        try:
            milliseconds = float(raw_milliseconds)
            if math.isfinite(milliseconds) and milliseconds >= 0.0:
                return milliseconds / 1000.0
        except ValueError:
            pass
    raw_retry_after = lowered.get("retry-after")
    if raw_retry_after is not None:
        try:
            seconds = float(raw_retry_after)
            if math.isfinite(seconds) and seconds >= 0.0:
                return seconds
        except ValueError:
            try:
                parsed = email.utils.parsedate_to_datetime(raw_retry_after)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=UTC)
                return max(0.0, parsed.timestamp() - (time.time() if now is None else now))
            except (TypeError, ValueError, OverflowError):
                pass
    return 0.5


def _retry_wait_fits(wait_seconds: float, elapsed: float, request_seconds: float) -> bool:
    """Reserve one second for the resend after the requested wait."""
    return wait_seconds + 1.0 <= request_seconds - elapsed


def _deadline_remaining(deadline: float, *, clock: Callable[[], float] = time.monotonic) -> float:
    """Return time left on one upstream deadline, or the fixed timeout diagnostic."""
    remaining = deadline - clock()
    if remaining <= 0.0:
        raise _DecisionTransportError("decision upstream timed out")
    return remaining


def _package_version() -> str:
    try:
        return importlib.metadata.version("agent-reliability-ci")
    except importlib.metadata.PackageNotFoundError:
        return "0.5.0"


def _tls_diagnostic(exc: ssl.SSLError) -> str:
    reason = getattr(exc, "reason", None)
    if isinstance(reason, str) and reason:
        clean = reason.replace("_", " ").lower()
    else:
        clean = format_diagnostic(exc).lower()
        if clean.startswith("sslerror: "):
            clean = clean.removeprefix("sslerror: ")
    return f"TLS failed: {clean}"[:299]


def _request_upstream_once(
    method: str,
    endpoint: str,
    body: dict[str, JsonValue] | None,
    spec: DecisionSpec,
    api_key: str,
    deadline: float,
    *,
    clock: Callable[[], float] = time.monotonic,
) -> _UpstreamResult:
    parts = urlsplit(spec.base_url)
    if parts.hostname is None:
        raise ValueError("decision upstream has no host")
    connection_type = (
        http.client.HTTPSConnection if parts.scheme == "https" else http.client.HTTPConnection
    )
    connection = connection_type(
        parts.hostname,
        parts.port,
        timeout=max(_deadline_remaining(deadline, clock=clock), 0.001),
    )
    raw = None if body is None else canonical_json(body)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Accept-Encoding": "identity",
        "User-Agent": f"arci/{_package_version()}",
    }
    if raw is not None:
        headers["Content-Type"] = "application/json"
    expired = threading.Event()
    # `getresponse()` detaches the socket from the connection on `Connection: close` replies;
    # keep our own reference so the deadline can still interrupt a trickling body.
    sockets: list[socket.socket] = []

    def expire_connection() -> None:
        expired.set()
        sock = connection.sock or (sockets[0] if sockets else None)
        if sock is not None:
            with contextlib.suppress(OSError):
                sock.shutdown(socket.SHUT_RDWR)
            with contextlib.suppress(OSError):
                sock.close()

    timer = threading.Timer(_deadline_remaining(deadline, clock=clock), expire_connection)
    timer.daemon = True
    timer.start()
    try:
        try:
            connection.timeout = max(_deadline_remaining(deadline, clock=clock), 0.001)
            connection.request(
                method,
                _join_upstream_path(spec.base_url, endpoint),
                body=raw,
                headers=headers,
            )
            if connection.sock is not None:
                sockets.append(connection.sock)
                connection.sock.settimeout(max(_deadline_remaining(deadline, clock=clock), 0.001))
            response = connection.getresponse()
            response_headers = dict(response.getheaders())
            lowered_response_headers = {
                name.lower(): value for name, value in response_headers.items()
            }
            encoding = lowered_response_headers.get("content-encoding", "identity")
            if encoding.lower() != "identity":
                raise _DecisionTransportError(f"decision upstream sent Content-Encoding {encoding}")
            payload = bytearray()
            while True:
                remaining = _deadline_remaining(deadline, clock=clock)
                for sock in sockets:
                    with contextlib.suppress(OSError):
                        sock.settimeout(max(remaining, 0.001))
                chunk = response.read1(64 * 1024)
                if not chunk:
                    break
                payload.extend(chunk)
            _deadline_remaining(deadline, clock=clock)
        except ssl.SSLError as exc:
            raise _DecisionTransportError(_tls_diagnostic(exc)) from None
        except TimeoutError:
            raise _DecisionTransportError("decision upstream timed out") from None
        except OSError:
            if expired.is_set():
                raise _DecisionTransportError("decision upstream timed out") from None
            raise
        try:
            value = json.loads(bytes(payload).decode("utf-8"))
            canonical_json(value)
        except (json.JSONDecodeError, UnicodeError, TypeError, ValueError):
            raise _DecisionTransportError("decision upstream returned non-JSON") from None
        return _UpstreamResult(
            response.status,
            _allowed_headers(response_headers),
            cast(JsonValue, value),
        )
    finally:
        timer.cancel()
        connection.close()


def request_decision_upstream(
    method: str,
    endpoint: str,
    body: dict[str, JsonValue] | None,
    spec: DecisionSpec,
    *,
    api_key: str | None = None,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> _UpstreamResult:
    """Call a DecisionSpec HTTP upstream with at most one bounded 429/529 wait."""
    key = os.environ.get("TYPESAFE_API_KEY") if api_key is None else api_key
    if not key:
        raise RuntimeError("TYPESAFE_API_KEY is not set for the decision upstream")
    started = clock()
    deadline = started + spec.request_seconds
    first = _request_upstream_once(method, endpoint, body, spec, key, deadline, clock=clock)
    if first.status not in {429, 529}:
        return first
    delay = _retry_delay(first.headers)
    elapsed = clock() - started
    if not _retry_wait_fits(delay, elapsed, spec.request_seconds):
        return first
    sleep(delay)
    remaining = _deadline_remaining(deadline, clock=clock)
    if remaining < 1.0:
        return first
    second = _request_upstream_once(method, endpoint, body, spec, key, deadline, clock=clock)
    if second.status != 200:
        raise _DecisionTransportError("decision upstream failed after retry")
    return _UpstreamResult(
        second.status,
        second.headers,
        second.body,
        second.error,
        attempts=2,
        first_status=first.status,
    )


def _raw_upstream_snapshot(upstream: _UpstreamResult) -> dict[str, JsonValue]:
    value = cast(
        dict[str, JsonValue],
        {
            "status": upstream.status,
            "headers": _allowed_headers(upstream.headers),
            "body": copy.deepcopy(upstream.body),
            "attempts": upstream.attempts,
            "first_status": upstream.first_status,
        },
    )
    canonical_json(value)
    return value


def _attach_upstream(result: ToolResult, upstream: dict[str, JsonValue] | None) -> ToolResult:
    value = cast(dict[str, JsonValue], copy.deepcopy(result.value))
    value["upstream"] = copy.deepcopy(upstream)
    canonical_json(value)
    return result.model_copy(update={"value": value}, deep=True)


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


def _server_environment(
    inherited: dict[str, str], configured: dict[str, str], workdir: str, seed: int
) -> dict[str, str]:
    env = {**inherited, **configured}
    env.pop("TYPESAFE_API_KEY", None)
    env.pop("TYPESAFE_BASE_URL", None)
    env["ARCI_WORKDIR"] = workdir
    env["ARCI_SEED"] = str(seed)
    env["ARCI_TASK_FILE"] = _task_file(workdir)
    return env


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
        results: queue.Queue[_DecisionCompletion] = queue.Queue(maxsize=1)
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
                    result = request_decision_upstream("POST", "/v1/systemone", pinned, spec)
            except BaseException as exc:
                result = _UpstreamResult(500, {}, None, upstream_diagnostic(exc))
            with contextlib.suppress(queue.Full):
                results.put_nowait(_DecisionCompletion(time.monotonic(), result))

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
        results: queue.Queue[_DecisionCompletion] = queue.Queue(maxsize=1)

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
                    result = request_decision_upstream("GET", "/v1/models", None, spec)
            except BaseException as exc:
                result = _UpstreamResult(500, {}, None, upstream_diagnostic(exc))
            with contextlib.suppress(queue.Full):
                results.put_nowait(_DecisionCompletion(time.monotonic(), result))

        self.decision_work = _DecisionWork(call, {}, results, time.monotonic())
        threading.Thread(target=invoke, daemon=True).start()

    def _decision_result(self, result: ToolResult) -> None:
        value_before = cast(dict[str, JsonValue], result.value)
        if "upstream" not in value_before:
            result = _attach_upstream(result, None)
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
        raw_upstream = _raw_upstream_snapshot(upstream)
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
            rewritten = cast(dict[str, JsonValue], result.value)
            rewritten_status = rewritten.get("status")
            if not isinstance(rewritten_status, int) or isinstance(rewritten_status, bool):
                raise ValueError("decision perturbation returned an invalid status")
            rewritten_body = copy.deepcopy(rewritten.get("body"))
            canonical_json(rewritten_body)
            result = result.model_copy(
                update={
                    "value": {
                        "status": rewritten_status,
                        "headers": _allowed_headers(cast(dict[str, str], rewritten.get("headers"))),
                        "body": rewritten_body,
                    }
                },
                deep=True,
            )
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
        result = _attach_upstream(result, raw_upstream)
        self._decision_result(result)

    def _poll_decision_work(self) -> None:
        work = self.decision_work
        spec = self.spec.decisions
        if work is None or spec is None:
            return
        if work.timed_out:
            return
        try:
            completion = work.results.get_nowait()
        except queue.Empty:
            completion = None
        observed_at = time.monotonic()
        expired_at = observed_at if completion is None else completion.finished_at
        if _decision_deadline_expired(work.started, spec.request_seconds, expired_at):
            self.latches.set_harness("decision upstream timed out")
            # Retain the work so no retry can start a second uncancellable worker.
            work.timed_out = True
            self._queue_http(500, {"detail": "arci: decision upstream failed"})
            return
        if completion is not None:
            try:
                self._finish_decision_work(completion.result)
            except BaseException as exc:
                self.latches.set_harness(exc)
                self.decision_work = None
                self._queue_http(500, {"detail": "arci: decision upstream failed"})
            return

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
            or _transports_conflict(
                pending_mcp=bool(self.pending) or self.tools_inflight,
                active_decision=True,
            )
        ):
            self._reject_concurrent_decision(connection)
            return
        connection.setblocking(False)
        self.decision_connection = _DecisionConnection(connection, bytearray(), bytearray())
        self.selector.register(connection, selectors.EVENT_READ, "decision")

    def _local_http_error(self, status: int, body: JsonValue) -> None:
        if self.decision_connection is not None:
            self.decision_connection.request_parsed = True
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
            result = _attach_upstream(result, None)
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
            error = _decision_request_error(value)
            if error is not None:
                self._local_http_error(422, error)
                return
            request = cast(dict[str, JsonValue], copy.deepcopy(value))
        except BaseException:
            self._local_http_error(422, _detail(["body"], "Input should be valid JSON"))
            return
        self._admit_decision(request)

    def _consume_http(self, chunk: bytes) -> None:
        connection = self.decision_connection
        spec = self.spec.decisions
        if connection is None or spec is None:
            return
        if connection.request_parsed:
            return
        connection.received.extend(chunk)
        try:
            request = _parse_http_request(bytes(connection.received), spec.max_body_bytes)
        except _HttpRequestError as exc:
            self._local_http_error(exc.status, exc.body)
            return
        if request is None:
            return
        connection.request_parsed = True
        self._handle_http_request(request.method, request.path, request.headers, request.body)

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
        if _transports_conflict(
            pending_mcp=True,
            active_decision=(
                self.decision_connection is not None or self.decision_work is not None
            ),
        ):
            self.latches.set_harness(_DECISION_CONCURRENCY)
            if method == "tools/call":
                self._write_client(
                    {
                        "jsonrpc": "2.0",
                        "id": rpc_id,
                        "result": _error_result("error", f"arci: {_DECISION_CONCURRENCY}"),
                    }
                )
            else:
                self._client_error(rpc_id, -32600, _DECISION_CONCURRENCY)
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
        env = _server_environment(dict(os.environ), server_spec.env, self.workdir, self.spec.seed)
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
            try:
                self._poll_decision_work()
            except BaseException as exc:
                self.latches.set_harness(exc)
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
