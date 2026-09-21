"""Parent-process trial and experiment orchestration."""

from __future__ import annotations

import contextlib
import json
import os
import queue
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

from arci.contracts import evaluate_contract, validate_contract
from arci.fingerprint import fingerprint, normalise
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
    TrialEnvelope,
    TrialSpec,
    Usage,
)
from arci.storage import ExperimentStore


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


def _safe_emit(emit_event: EmitEvent, event: Event) -> None:
    with contextlib.suppress(Exception):
        emit_event(event)


def _terminal_event(spec: TrialSpec, seq: int, termination: Termination) -> Event:
    return Event(
        trial_id=spec.trial_id,
        seq=seq,
        kind="trial_end",
        payload={"termination": termination.value},
    )


def _incomplete_calls(events: Sequence[Event]) -> tuple[ToolCall, ...]:
    starts: dict[str, ToolCall] = {}
    finished: set[str] = set()
    for event in events:
        if event.kind == "tool_start":
            call_id = str(event.payload.get("call_id", ""))
            arguments = event.payload.get("arguments")
            occurrence_value = event.payload.get("occurrence", 0)
            occurrence = occurrence_value if isinstance(occurrence_value, int) else 0
            starts[call_id] = ToolCall(
                call_id=call_id,
                tool=str(event.payload.get("tool", "")),
                arguments=cast(
                    dict[str, JsonValue], arguments if isinstance(arguments, dict) else {}
                ),
                occurrence=occurrence,
            )
        elif event.kind == "tool_finish":
            finished.add(str(event.payload.get("call_id", "")))
    return tuple(call for call_id, call in starts.items() if call_id not in finished)


def _first_failed_tool(events: Sequence[Event]) -> str:
    for event in events:
        if event.kind == "tool_finish" and event.payload.get("ok") is False:
            return f"{event.payload.get('tool')}:{event.payload.get('error_kind')}"
    return "none"


def _failure(
    termination: Termination, contract: ContractResult | None, events: Sequence[Event], detail: str
) -> tuple[Outcome, str | None, str | None]:
    clean_detail = normalise(detail) if detail else ""
    if termination is Termination.HARNESS_ERROR:
        message = clean_detail or "worker harness failed"
        return Outcome.ERROR, fingerprint("harness", message), message
    if termination is Termination.REPLAY_MISS:
        message = clean_detail or "recording was not consumed exactly"
        return Outcome.ERROR, fingerprint("replay_miss", message), message
    if termination is Termination.TIMEOUT:
        message = "trial exceeded max_seconds"
        return Outcome.FAIL, fingerprint("timeout", message), message
    if termination is Termination.BUDGET:
        message = clean_detail or "trial budget exhausted"
        return Outcome.FAIL, fingerprint("budget", message), message
    if termination is Termination.CRASH:
        message = clean_detail or "worker exited before returning"
        return Outcome.FAIL, fingerprint("crash", message), message
    if contract is not None and contract.grader_error is not None:
        message = normalise(contract.grader_error)
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


def run_trial(
    spec: TrialSpec,
    emit_event: EmitEvent,
    contract: ContractSpec,
    *,
    extra_pythonpath: Sequence[str] = (),
) -> TrialEnvelope:
    """Run a trial in a process group and always return a sealed envelope."""
    started = time.monotonic()
    events: list[Event] = []
    worker_result: dict[str, Any] | None = None
    parse_error = ""
    timed_out = False

    env = os.environ.copy()
    env["PYTHONPATH"] = _pythonpath(extra_pythonpath)
    try:
        process = subprocess.Popen(
            [sys.executable, "-m", "arci.worker"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            env=env,
            start_new_session=True,
        )
        assert process.stdin is not None and process.stdout is not None
        stdout = process.stdout
        process.stdin.write(spec.model_dump_json() + "\n")
        process.stdin.close()

        lines: queue.Queue[str | None] = queue.Queue()

        def read_stdout() -> None:
            for line in stdout:
                lines.put(line)
            lines.put(None)

        reader = threading.Thread(target=read_stdout, daemon=True)
        reader.start()
        deadline = started + spec.budgets.max_seconds
        stream_ended = False
        while not stream_ended:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                break
            try:
                line = lines.get(timeout=min(remaining, 0.1))
            except queue.Empty:
                if process.poll() is not None and not reader.is_alive():
                    break
                continue
            if line is None:
                stream_ended = True
                continue
            try:
                decoded = json.loads(line)
                if "worker_result" in decoded:
                    worker_result = cast(dict[str, Any], decoded["worker_result"])
                else:
                    event = Event.model_validate(decoded)
                    events.append(event)
                    _safe_emit(emit_event, event)
            except Exception as exc:
                parse_error = f"invalid worker output: {type(exc).__name__}"

        if timed_out:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
            process.wait()
        reader.join(timeout=1)
        while True:
            try:
                line = lines.get_nowait()
            except queue.Empty:
                break
            if line is None:
                continue
            try:
                decoded = json.loads(line)
                if "worker_result" in decoded:
                    worker_result = cast(dict[str, Any], decoded["worker_result"])
                else:
                    event = Event.model_validate(decoded)
                    events.append(event)
                    _safe_emit(emit_event, event)
            except Exception as exc:
                parse_error = f"invalid worker output: {type(exc).__name__}"
    except Exception as exc:
        process = None
        parse_error = f"{type(exc).__name__}: {exc}".splitlines()[0]

    if not events:
        start = Event(
            trial_id=spec.trial_id,
            seq=0,
            kind="trial_start",
            payload={"seed": spec.seed, "arm": spec.arm, "variant": spec.variant},
        )
        events.append(start)
        _safe_emit(emit_event, start)

    if timed_out:
        termination = Termination.TIMEOUT
        detail = "trial exceeded max_seconds"
        worker_result = None
    elif parse_error:
        termination = Termination.HARNESS_ERROR
        detail = parse_error
    elif worker_result is None:
        termination = Termination.CRASH
        detail = "worker exited before returning"
    else:
        try:
            termination = Termination(str(worker_result.get("termination")))
            detail = str(worker_result.get("detail", ""))
        except Exception:
            termination = Termination.HARNESS_ERROR
            detail = "invalid worker result"

    end_positions = [index for index, event in enumerate(events) if event.kind == "trial_end"]
    if (
        timed_out
        or not end_positions
        or len(end_positions) != 1
        or end_positions[0] != len(events) - 1
    ):
        events = [event for event in events if event.kind != "trial_end"]
        end = _terminal_event(spec, len(events), termination)
        events.append(end)
        _safe_emit(emit_event, end)

    # The worker owns normal sequencing; synthesised terminal events continue it.
    if [event.seq for event in events] != list(range(len(events))):
        events = [event.model_copy(update={"seq": index}) for index, event in enumerate(events)]

    agent_result = None if worker_result is None else worker_result.get("agent_result")
    claimed = agent_result.get("success") if isinstance(agent_result, dict) else None
    agent_claimed_success = claimed if isinstance(claimed, bool) else None
    final_state_raw = None if worker_result is None else worker_result.get("final_state")
    if final_state_raw is not None and not isinstance(final_state_raw, dict):
        final_state: dict[str, JsonValue] | None = None
        termination = Termination.HARNESS_ERROR
        detail = "worker returned an invalid final state"
    else:
        final_state = cast(dict[str, JsonValue] | None, final_state_raw)
    recording_raw = () if worker_result is None else worker_result.get("recording", ())
    try:
        recording = tuple(RecordedCall.model_validate(item) for item in recording_raw)
    except Exception:
        recording = ()
        termination = Termination.HARNESS_ERROR
        detail = "invalid worker recording"

    contract_result: ContractResult | None = None
    if termination not in {Termination.HARNESS_ERROR, Termination.REPLAY_MISS}:
        contract_result = evaluate_contract(contract, events, spec.task, final_state)
        if contract_result.grader_error is not None:
            termination = Termination.GRADER_ERROR
    outcome, failure_fingerprint, failure_detail = _failure(
        termination, contract_result, events, detail
    )

    observed_calls = sum(event.kind == "tool_start" for event in events)
    observed_steps = sum(event.kind == "model_step" for event in events)
    usage = Usage(
        tool_calls=observed_calls,
        model_steps=observed_steps,
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
            results[index] = trial
            with lock:
                store.append_trial(trial)
    return tuple(cast(TrialEnvelope, trial) for trial in results)
