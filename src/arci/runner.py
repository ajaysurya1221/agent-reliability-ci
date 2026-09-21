"""Parent-process trial and experiment orchestration."""

from __future__ import annotations

import contextlib
import json
import os
import queue
import secrets
import select
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, cast

from pydantic import JsonValue

from arci.contracts import validate_contract
from arci.fingerprint import fingerprint
from arci.hashing import canonical_json, hash_record
from arci.interfaces import EmitEvent
from arci.schedule import build_schedule, spec_sha256
from arci.schema import (
    ContractResult,
    ContractSpec,
    Event,
    Manifest,
    Outcome,
    RecordedCall,
    Termination,
    ToolCall,
    ToolMode,
    TrialEnvelope,
    TrialSpec,
    Usage,
)
from arci.storage import ExperimentStore
from arci.toolbox import format_diagnostic

_MAX_PROTOCOL_LINE = 1024 * 1024
_PROTOCOL_QUEUE_SIZE = 256
_GRADER_TIMEOUT = "grader timed out"
_GRADER_EXIT = "grader exited non-zero"
_GRADER_OUTPUT = "grader returned invalid output"


def _pythonpath(extra: Sequence[str]) -> str:
    paths = [*extra]
    for entry in sys.path:
        resolved = os.getcwd() if entry == "" else entry
        if resolved and resolved not in paths:
            paths.append(resolved)
    existing = os.environ.get("PYTHONPATH")
    if existing:
        paths.extend(part for part in existing.split(os.pathsep) if part not in paths)
    return os.pathsep.join(paths)


def _kill_group(process: subprocess.Popen[bytes]) -> None:
    with contextlib.suppress(OSError):
        os.killpg(process.pid, signal.SIGKILL)


def _terminal_event(spec: TrialSpec, seq: int) -> Event:
    return Event(
        trial_id=spec.trial_id,
        seq=seq,
        kind="trial_end",
        payload={},
    )


def _incomplete_calls(events: Sequence[Event]) -> tuple[ToolCall, ...]:
    starts: dict[str, ToolCall] = {}
    finished: set[str] = set()
    for event in events:
        if event.kind == "tool_start":
            starts[str(event.payload["call_id"])] = ToolCall(
                call_id=str(event.payload["call_id"]),
                tool=str(event.payload["tool"]),
                arguments=cast(dict[str, JsonValue], event.payload["arguments"]),
                occurrence=cast(int, event.payload["occurrence"]),
            )
        elif event.kind == "tool_finish":
            finished.add(str(event.payload["call_id"]))
    return tuple(call for call_id, call in starts.items() if call_id not in finished)


def _first_failed_tool(events: Sequence[Event]) -> str:
    for event in events:
        if event.kind == "tool_finish" and event.payload.get("ok") is False:
            return f"{event.payload.get('tool')}:{event.payload.get('error_kind')}"
    return "none"


def _failure(
    termination: Termination, contract: ContractResult | None, events: Sequence[Event], detail: str
) -> tuple[Outcome, str | None, str | None]:
    clean_detail = format_diagnostic(detail) if detail else ""
    if termination is Termination.REPLAY_MISS:
        message = clean_detail or "recording was not consumed exactly"
        return Outcome.ERROR, fingerprint("replay_miss", message), message
    if termination is Termination.HARNESS_ERROR:
        message = clean_detail or "worker harness failed"
        return Outcome.ERROR, fingerprint("harness", message), message
    if termination is Termination.GRADER_ERROR:
        message = clean_detail or "grader failed"
        return Outcome.ERROR, fingerprint("grader", message), message
    if termination is Termination.BUDGET:
        message = clean_detail or "trial budget exhausted"
        return Outcome.FAIL, fingerprint("budget", message), message
    if termination is Termination.TIMEOUT:
        message = "trial exceeded max_seconds"
        return Outcome.FAIL, fingerprint("timeout", message), message
    if termination is Termination.CRASH:
        message = clean_detail or "worker exited before returning"
        return Outcome.FAIL, fingerprint("crash", message), message
    if contract is not None and contract.grader_error is not None:
        message = format_diagnostic(contract.grader_error)
        return Outcome.ERROR, fingerprint("grader", message), message
    if contract is not None:
        hard = next((v for v in contract.violations if v.severity == "hard"), None)
        if hard is not None:
            return (
                Outcome.FAIL,
                fingerprint(f"invariant:{hard.invariant}", hard.detail),
                hard.detail,
            )
        if contract.success:
            return Outcome.PASS, None, None
    message = f"oracle rejected final state; first_failed_tool={_first_failed_tool(events)}"
    return Outcome.FAIL, fingerprint("oracle", message), message


def _valid_event_payload(event: Event, tool_starts: int) -> bool:
    payload = event.payload
    try:
        canonical_json(event.model_dump(mode="python"))
    except (TypeError, ValueError, UnicodeError):
        return False
    if event.kind == "trial_start":
        return (
            isinstance(payload.get("seed"), int)
            and not isinstance(payload.get("seed"), bool)
            and isinstance(payload.get("arm"), str)
            and isinstance(payload.get("variant"), str)
        )
    if event.kind == "model_step":
        return isinstance(payload.get("summary"), str)
    if event.kind == "tool_start":
        call_id = payload.get("call_id")
        tool = payload.get("tool")
        arguments = payload.get("arguments")
        occurrence = payload.get("occurrence")
        if not (
            isinstance(call_id, str)
            and isinstance(tool, str)
            and isinstance(arguments, dict)
            and isinstance(occurrence, int)
            and not isinstance(occurrence, bool)
        ):
            return False
        try:
            call = ToolCall(
                call_id=call_id,
                tool=tool,
                arguments=arguments,
                occurrence=occurrence,
            )
        except Exception:
            return False
        return call.call_id == f"c-{tool_starts:04d}"
    if event.kind == "tool_finish":
        return (
            isinstance(payload.get("tool"), str)
            and isinstance(payload.get("call_id"), str)
            and type(payload.get("ok")) is bool
            and (payload.get("error_kind") is None or isinstance(payload.get("error_kind"), str))
            and (payload.get("injected_by") is None or isinstance(payload.get("injected_by"), str))
            and "value" in payload
        )
    if event.kind == "agent_result":
        return isinstance(payload.get("result"), dict)
    return False


def _validate_worker_result(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError("worker result is not an object")
    canonical_json(value)
    Termination(value.get("termination"))
    if not isinstance(value.get("detail"), str):
        raise TypeError("worker detail is not a string")
    if value.get("agent_result") is not None and not isinstance(value.get("agent_result"), dict):
        raise TypeError("worker agent result is invalid")
    if value.get("final_state") is not None and not isinstance(value.get("final_state"), dict):
        raise TypeError("worker final state is invalid")
    recording = value.get("recording")
    if not isinstance(recording, list):
        raise TypeError("worker recording is invalid")
    tuple(RecordedCall.model_validate(item) for item in recording)
    latches = value.get("latches")
    if not isinstance(latches, dict):
        raise TypeError("worker latches are invalid")
    for name in ("replay", "harness", "budget"):
        if latches.get(name) is not None and not isinstance(latches.get(name), str):
            raise TypeError("worker latch is invalid")
    return cast(dict[str, Any], value)


def _replay_mismatch(
    spec: TrialSpec, events: Sequence[Event], worker_result: dict[str, Any] | None
) -> str | None:
    if spec.tool_mode is not ToolMode.REPLAY:
        return None
    if worker_result is not None:
        latches = cast(dict[str, object], worker_result["latches"])
        if isinstance(latches.get("replay"), str):
            return "recording was not consumed exactly"

    starts: list[Event] = [event for event in events if event.kind == "tool_start"]
    finishes = {
        str(event.payload["call_id"]): event for event in events if event.kind == "tool_finish"
    }
    consumed = 0
    for event in starts:
        if consumed >= len(spec.recording):
            return "recording was not consumed exactly"
        recorded = spec.recording[consumed]
        arguments = cast(dict[str, JsonValue], event.payload["arguments"])
        observed = (
            str(event.payload["tool"]),
            hash_record(arguments),
            cast(int, event.payload["occurrence"]),
        )
        expected = (recorded.tool, recorded.arguments_sha256, recorded.occurrence)
        finish = finishes.get(str(event.payload["call_id"]))
        if (
            observed != expected
            or finish is None
            or finish.payload.get("error_kind") == "replay_miss"
        ):
            return "recording was not consumed exactly"
        consumed += 1
    if consumed != len(spec.recording):
        return "recording was not consumed exactly"
    return None


def _grade(
    spec: TrialSpec,
    contract: ContractSpec,
    events: Sequence[Event],
    final_state: dict[str, JsonValue] | None,
    *,
    run_oracle: bool,
    extra_pythonpath: Sequence[str],
) -> ContractResult:
    deadline = time.monotonic() + spec.budgets.grader_seconds
    try:
        request = canonical_json(
            {
                "contract": contract.model_dump(mode="json"),
                "events": [event.model_dump(mode="json") for event in events],
                "task": spec.task,
                "final_state": final_state,
                "run_oracle": run_oracle,
            }
        )
    except (TypeError, ValueError, UnicodeError):
        return ContractResult(success=False, grader_error=_GRADER_OUTPUT)
    env = os.environ.copy()
    env["PYTHONPATH"] = _pythonpath(extra_pythonpath)
    process: subprocess.Popen[bytes] | None = None
    try:
        process = subprocess.Popen(
            [sys.executable, "-P", "-m", "arci.grade"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=env,
            start_new_session=True,
        )
        assert process.stdin is not None and process.stdout is not None
        chunks: list[bytes] = []
        reader_stop = threading.Event()
        reader_done = threading.Event()
        reader_failed = threading.Event()

        def read_response() -> None:
            try:
                assert process is not None and process.stdout is not None
                while True:
                    timeout = 0.0 if reader_stop.is_set() else 0.05
                    ready, _, _ = select.select([process.stdout.fileno()], [], [], timeout)
                    if not ready:
                        if reader_stop.is_set():
                            return
                        continue
                    chunk = os.read(process.stdout.fileno(), 65536)
                    if not chunk:
                        return
                    chunks.append(chunk)
            except BaseException:
                reader_failed.set()
            finally:
                reader_done.set()

        def write_request() -> None:
            try:
                assert process is not None and process.stdin is not None
                process.stdin.write(request + b"\n")
                process.stdin.flush()
            except (BrokenPipeError, OSError):
                pass
            finally:
                with contextlib.suppress(Exception):
                    assert process is not None and process.stdin is not None
                    process.stdin.close()

        reader = threading.Thread(target=read_response, daemon=True)
        reader.start()
        threading.Thread(target=write_request, daemon=True).start()
        try:
            exit_code = process.wait(timeout=max(0.0, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            _kill_group(process)
            with contextlib.suppress(Exception):
                process.wait()
            reader_stop.set()
            return ContractResult(success=False, grader_error=_GRADER_TIMEOUT)
        _kill_group(process)
        reader_stop.set()
        reader_done.wait(timeout=max(0.0, deadline - time.monotonic()))
        if exit_code != 0:
            return ContractResult(success=False, grader_error=_GRADER_EXIT)
        if not reader_done.is_set() or reader_failed.is_set():
            return ContractResult(success=False, grader_error=_GRADER_OUTPUT)
        try:
            return ContractResult.model_validate_json(b"".join(chunks))
        except Exception:
            return ContractResult(success=False, grader_error=_GRADER_OUTPUT)
    except BaseException:
        return ContractResult(success=False, grader_error=_GRADER_EXIT)
    finally:
        if process is not None:
            _kill_group(process)
            with contextlib.suppress(Exception):
                if process.stdin is not None:
                    process.stdin.close()
                if process.stdout is not None:
                    process.stdout.close()
            with contextlib.suppress(Exception):
                process.wait()


def _run_trial(
    spec: TrialSpec,
    emit_event: EmitEvent,
    contract: ContractSpec,
    *,
    extra_pythonpath: Sequence[str] = (),
) -> TrialEnvelope:
    """Run a trial in a process group and always return a sealed envelope."""
    started = time.monotonic()
    deadline = started + spec.budgets.max_seconds
    validate_contract(contract)
    events: list[Event] = []
    worker_result: dict[str, Any] | None = None
    protocol_error: str | None = None
    sink_error: str | None = None
    timed_out = False
    exit_code: int | None = None
    process: subprocess.Popen[bytes] | None = None
    nonce = secrets.token_hex(16)
    messages: queue.Queue[tuple[str, object]] = queue.Queue(maxsize=_PROTOCOL_QUEUE_SIZE)
    reader_stop = threading.Event()
    result_seen = False
    expected_seq = 0
    tool_starts = 0
    parent_latches: dict[str, str] = {}

    def stop_worker() -> None:
        if process is not None:
            _kill_group(process)

    def deliver(event: Event) -> None:
        nonlocal sink_error
        events.append(event)
        if sink_error is None:
            try:
                emit_event(event)
            except BaseException:
                sink_error = "event sink failed"
                stop_worker()

    try:
        env = os.environ.copy()
        env["PYTHONPATH"] = _pythonpath(extra_pythonpath)
        process = subprocess.Popen(
            [sys.executable, "-P", "-m", "arci.worker"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=env,
            start_new_session=True,
        )
        assert process.stdin is not None and process.stdout is not None

        request = (
            json.dumps(
                {"nonce": nonce, "spec": spec.model_dump(mode="json")},
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            + b"\n"
        )

        def write_stdin() -> None:
            try:
                assert process is not None and process.stdin is not None
                process.stdin.write(request)
                process.stdin.flush()
            except Exception:
                pass
            finally:
                with contextlib.suppress(Exception):
                    assert process is not None and process.stdin is not None
                    process.stdin.close()

        def read_stdout() -> None:
            buffer = bytearray()

            def send(message: str, value: object) -> bool:
                while True:
                    try:
                        messages.put((message, value), timeout=0.05)
                        return True
                    except queue.Full:
                        if reader_stop.is_set():
                            return False

            try:
                assert process is not None and process.stdout is not None
                while True:
                    if reader_stop.is_set():
                        ready, _, _ = select.select([process.stdout.fileno()], [], [], 0.0)
                        if not ready:
                            if buffer:
                                send("protocol_error", "partial worker protocol line")
                            return
                    else:
                        ready, _, _ = select.select([process.stdout.fileno()], [], [], 0.05)
                        if not ready:
                            continue
                    chunk = os.read(process.stdout.fileno(), 65536)
                    if not chunk:
                        if buffer:
                            send("protocol_error", "partial worker protocol line")
                        return
                    buffer.extend(chunk)
                    while True:
                        newline = buffer.find(b"\n")
                        if newline < 0:
                            if len(buffer) > _MAX_PROTOCOL_LINE:
                                send("protocol_error", "worker protocol line too long")
                                return
                            break
                        line = bytes(buffer[:newline])
                        del buffer[: newline + 1]
                        if len(line) > _MAX_PROTOCOL_LINE:
                            send("protocol_error", "worker protocol line too long")
                            return
                        if not send("line", line):
                            return
            except Exception:
                send("protocol_error", "worker protocol reader failed")
            finally:
                send("reader_done", None)

        threading.Thread(target=write_stdin, daemon=True).start()
        reader = threading.Thread(target=read_stdout, daemon=True)
        reader.start()

        while exit_code is None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = process.poll() is None
                stop_worker()
                break
            polled = process.poll()
            if polled is not None:
                exit_code = polled
                reader_stop.set()
                stop_worker()
                break
            try:
                message, value = messages.get(timeout=min(remaining, 0.05))
            except queue.Empty:
                continue
            if message == "reader_done":
                continue
            if protocol_error is not None or sink_error is not None:
                continue
            if message == "protocol_error":
                protocol_error = cast(str, value)
                stop_worker()
                continue
            try:
                decoded = json.loads(cast(bytes, value).decode("utf-8", errors="replace"))
                if not isinstance(decoded, dict):
                    raise TypeError("protocol frame is not an object")
                canonical_json(decoded)
                if decoded.get("nonce") != nonce:
                    raise ValueError("protocol nonce mismatch")
                kind = decoded.get("kind")
                if kind == "event":
                    if result_seen:
                        raise ValueError("event after worker result")
                    event = Event.model_validate(decoded.get("event"))
                    if event.kind == "trial_end":
                        raise ValueError("worker emitted trial_end")
                    if event.trial_id != spec.trial_id or event.seq != expected_seq:
                        raise ValueError("invalid event identity or sequence")
                    if not _valid_event_payload(event, tool_starts):
                        raise ValueError("invalid event payload")
                    deliver(event)
                    expected_seq += 1
                    if event.kind == "tool_start":
                        tool_starts += 1
                elif kind == "result":
                    if result_seen:
                        raise ValueError("duplicate worker result")
                    worker_result = _validate_worker_result(decoded.get("result"))
                    result_seen = True
                elif kind == "latch":
                    latch = decoded.get("latch")
                    latch_detail = decoded.get("detail")
                    if result_seen:
                        raise ValueError("latch after worker result")
                    if latch not in {"replay_miss", "harness_error", "budget"}:
                        raise ValueError("invalid worker latch")
                    if not isinstance(latch_detail, str):
                        raise TypeError("worker latch detail is not a string")
                    parent_latches.setdefault(latch, latch_detail)
                else:
                    raise ValueError("invalid protocol frame kind")
            except Exception:
                protocol_error = "invalid worker protocol"
                stop_worker()

        reader_stop.set()
        while (reader.is_alive() or not messages.empty()) and time.monotonic() < deadline:
            try:
                message, value = messages.get(timeout=min(0.05, deadline - time.monotonic()))
            except queue.Empty:
                continue
            if message == "reader_done":
                continue
            if protocol_error is not None or sink_error is not None:
                continue
            if message == "protocol_error":
                protocol_error = cast(str, value)
                continue
            try:
                decoded = json.loads(cast(bytes, value).decode("utf-8", errors="replace"))
                if not isinstance(decoded, dict):
                    raise TypeError("protocol frame is not an object")
                canonical_json(decoded)
                if decoded.get("nonce") != nonce:
                    raise ValueError("protocol nonce mismatch")
                kind = decoded.get("kind")
                if kind == "event":
                    if result_seen:
                        raise ValueError("event after worker result")
                    event = Event.model_validate(decoded.get("event"))
                    if event.kind == "trial_end":
                        raise ValueError("worker emitted trial_end")
                    if event.trial_id != spec.trial_id or event.seq != expected_seq:
                        raise ValueError("invalid event identity or sequence")
                    if not _valid_event_payload(event, tool_starts):
                        raise ValueError("invalid event payload")
                    deliver(event)
                    expected_seq += 1
                    if event.kind == "tool_start":
                        tool_starts += 1
                elif kind == "result":
                    if result_seen:
                        raise ValueError("duplicate worker result")
                    worker_result = _validate_worker_result(decoded.get("result"))
                    result_seen = True
                elif kind == "latch":
                    latch = decoded.get("latch")
                    latch_detail = decoded.get("detail")
                    if result_seen or latch not in {"replay_miss", "harness_error", "budget"}:
                        raise ValueError("invalid worker latch")
                    if not isinstance(latch_detail, str):
                        raise TypeError("worker latch detail is not a string")
                    parent_latches.setdefault(cast(str, latch), latch_detail)
                else:
                    raise ValueError("invalid protocol frame kind")
            except Exception:
                protocol_error = "invalid worker protocol"
    except Exception as exc:
        protocol_error = format_diagnostic(exc)
    finally:
        reader_stop.set()
        if process is not None:
            _kill_group(process)
            with contextlib.suppress(Exception):
                if process.stdin is not None:
                    process.stdin.close()
                if process.stdout is not None:
                    process.stdout.close()
            with contextlib.suppress(Exception):
                exit_code = process.wait()

    if not events:
        deliver(
            Event(
                trial_id=spec.trial_id,
                seq=0,
                kind="trial_start",
                payload={"seed": spec.seed, "arm": spec.arm, "variant": spec.variant},
            )
        )

    replay_error = parent_latches.get("replay_miss") or _replay_mismatch(
        spec, events, worker_result
    )
    worker_latches: dict[str, object] = (
        {} if worker_result is None else cast(dict[str, object], worker_result["latches"])
    )
    worker_harness = parent_latches.get("harness_error") or worker_latches.get("harness")
    worker_budget = parent_latches.get("budget") or worker_latches.get("budget")

    if timed_out:
        base_termination = Termination.TIMEOUT
        detail = "trial exceeded max_seconds"
    elif exit_code is None or exit_code != 0:
        base_termination = Termination.CRASH
        detail = "worker exited non-zero" if exit_code is not None else "worker did not exit"
    elif worker_result is None:
        base_termination = Termination.CRASH
        detail = "worker exited before returning"
    else:
        base_termination = Termination(str(worker_result["termination"]))
        detail = str(worker_result["detail"])

    if replay_error is not None:
        termination = Termination.REPLAY_MISS
        detail = replay_error
    elif sink_error is not None or protocol_error is not None or isinstance(worker_harness, str):
        termination = Termination.HARNESS_ERROR
        detail = sink_error or protocol_error or cast(str, worker_harness)
    elif isinstance(worker_budget, str):
        termination = Termination.BUDGET
        detail = worker_budget
    else:
        termination = base_termination

    agent_result = None if worker_result is None else worker_result.get("agent_result")
    claimed = agent_result.get("success") if isinstance(agent_result, dict) else None
    agent_claimed_success = claimed if isinstance(claimed, bool) else None
    final_state = cast(
        dict[str, JsonValue] | None,
        None if worker_result is None else worker_result.get("final_state"),
    )
    recording = tuple(
        RecordedCall.model_validate(item)
        for item in (() if worker_result is None else worker_result["recording"])
    )

    run_oracle = (
        termination is Termination.COMPLETED
        and exit_code == 0
        and worker_result is not None
        and final_state is not None
    )
    contract_result = _grade(
        spec,
        contract,
        events,
        final_state,
        run_oracle=run_oracle,
        extra_pythonpath=extra_pythonpath,
    )
    if contract_result.grader_error is not None and termination not in {
        Termination.REPLAY_MISS,
        Termination.HARNESS_ERROR,
    }:
        termination = Termination.GRADER_ERROR
        detail = contract_result.grader_error

    outcome, failure_fingerprint, failure_detail = _failure(
        termination, contract_result, events, detail
    )
    terminal = _terminal_event(spec, len(events))
    deliver(terminal)
    if sink_error is not None and termination is not Termination.REPLAY_MISS:
        termination = Termination.HARNESS_ERROR
        detail = sink_error
        outcome, failure_fingerprint, failure_detail = _failure(
            termination, contract_result, events, detail
        )

    usage = Usage(
        tool_calls=sum(event.kind == "tool_start" for event in events),
        model_steps=sum(event.kind == "model_step" for event in events),
        wall_seconds=time.monotonic() - started,
    )
    return TrialEnvelope.create(
        spec_sha256=spec_sha256(spec),
        experiment_id=spec.experiment_id,
        trial_id=spec.trial_id,
        pair_id=spec.pair_id,
        arm=spec.arm,
        variant=spec.variant,
        task_id=spec.task_id,
        condition_id=spec.condition.condition_id,
        seed=spec.seed,
        outcome=outcome,
        termination=termination,
        agent_claimed_success=agent_claimed_success,
        contract=contract_result,
        failure_fingerprint=failure_fingerprint,
        failure_detail=failure_detail,
        events=tuple(events),
        incomplete_calls=_incomplete_calls(events),
        recording=recording,
        final_state=final_state,
        usage=usage,
    )


def run_trial(
    spec: TrialSpec,
    emit_event: EmitEvent,
    contract: ContractSpec,
    *,
    extra_pythonpath: Sequence[str] = (),
) -> TrialEnvelope:
    """Run one trial; any internal failure becomes a sealed harness-error envelope."""
    started = time.monotonic()
    delivered: list[Event] = []

    def tracked_emit(event: Event) -> None:
        delivered.append(event)
        emit_event(event)

    try:
        return _run_trial(
            spec,
            tracked_emit,
            contract,
            extra_pythonpath=extra_pythonpath,
        )
    except BaseException as exc:
        detail = format_diagnostic(exc) or "trial harness failed"
        try:
            canonical_json(detail)
        except (TypeError, ValueError, UnicodeError):
            detail = f"{type(exc).__name__}: invalid error detail"
        new_events: list[Event] = []
        if not delivered:
            new_events.append(
                Event(
                    trial_id=spec.trial_id,
                    seq=0,
                    kind="trial_start",
                    payload={"seed": spec.seed, "arm": spec.arm, "variant": spec.variant},
                )
            )
            delivered.extend(new_events)
        if delivered[-1].kind != "trial_end":
            terminal = _terminal_event(spec, len(delivered))
            delivered.append(terminal)
            new_events.append(terminal)
        for event in new_events:
            with contextlib.suppress(BaseException):
                emit_event(event)
        try:
            digest = spec_sha256(spec)
        except BaseException:
            digest = "0" * 64
        return TrialEnvelope.create(
            spec_sha256=digest,
            experiment_id=spec.experiment_id,
            trial_id=spec.trial_id,
            pair_id=spec.pair_id,
            arm=spec.arm,
            variant=spec.variant,
            task_id=spec.task_id,
            condition_id=spec.condition.condition_id,
            seed=spec.seed,
            outcome=Outcome.ERROR,
            termination=Termination.HARNESS_ERROR,
            contract=None,
            failure_fingerprint=fingerprint("harness", detail),
            failure_detail=detail,
            events=tuple(delivered),
            usage=Usage(wall_seconds=time.monotonic() - started),
        )


def _store_failure(trial: TrialEnvelope) -> TrialEnvelope:
    detail = "experiment store failed"
    return TrialEnvelope.create(
        **{
            **trial.model_dump(exclude={"record_sha256"}),
            "outcome": Outcome.ERROR,
            "termination": Termination.HARNESS_ERROR,
            "failure_fingerprint": fingerprint("harness", detail),
            "failure_detail": detail,
            "events": trial.events,
        }
    )


def run_experiment(
    manifest: Manifest, out_dir: Path | str, *, max_workers: int = 4
) -> tuple[TrialEnvelope, ...]:
    validate_contract(manifest.contract)
    schedule = build_schedule(manifest)
    store = ExperimentStore(out_dir, manifest)
    lock = threading.Lock()
    results: list[TrialEnvelope | None] = [None] * len(schedule)

    def run(index: int, spec: TrialSpec) -> tuple[int, TrialEnvelope]:
        def emit(event: Event) -> None:
            with lock:
                store.append_event(event)

        return index, run_trial(spec, emit, manifest.contract)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(run, index, spec) for index, spec in enumerate(schedule)]
        for future in as_completed(futures):
            index, trial = future.result()
            try:
                with lock:
                    store.append_trial(trial)
            except Exception:
                trial = _store_failure(trial)
            results[index] = trial
    return tuple(cast(TrialEnvelope, trial) for trial in results)
