"""Isolated trial worker. Standard output is a nonce-authenticated protocol."""

from __future__ import annotations

import contextlib
import copy
import json
import random
import sys
import time
from typing import Any, cast

from pydantic import JsonValue, TypeAdapter

from arci.contracts import resolve
from arci.fingerprint import normalise
from arci.interfaces import AgentFn, BudgetExceeded, ReplayMiss, ToolFault, ToolSet, ToolSetFactory
from arci.perturb import build
from arci.schema import Event, Termination, ToolMode, TrialSpec
from arci.toolbox import ToolBox

_AGENT_RESULT = TypeAdapter(dict[str, JsonValue])
_FINAL_STATE = TypeAdapter(dict[str, JsonValue])
_PROTOCOL = sys.stdout.buffer


class _Latches:
    def __init__(self) -> None:
        self.replay: str | None = None
        self.harness: str | None = None
        self.budget: str | None = None

    def set_replay(self, detail: str) -> None:
        if self.replay is None:
            self.replay = normalise(detail)

    def set_harness(self, detail: str) -> None:
        if self.harness is None:
            self.harness = normalise(detail)

    def set_budget(self, detail: str) -> None:
        if self.budget is None:
            self.budget = normalise(detail)


def _write_frame(nonce: str, kind: str, payload_name: str, payload: object) -> None:
    frame = {"nonce": nonce, "kind": kind, payload_name: payload}
    data = json.dumps(frame, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
    _PROTOCOL.write(data)
    _PROTOCOL.flush()


class _Emitter:
    def __init__(self, trial_id: str, nonce: str) -> None:
        self._trial_id = trial_id
        self._nonce = nonce
        self._seq = 0
        self._started = time.monotonic()

    def __call__(self, kind: str, payload: dict[str, JsonValue]) -> None:
        event = Event(
            trial_id=self._trial_id,
            seq=self._seq,
            kind=cast(Any, kind),
            payload=copy.deepcopy(payload),
            at_ms=(time.monotonic() - self._started) * 1000.0,
        )
        self._seq += 1
        _write_frame(self._nonce, "event", "event", event.model_dump(mode="json"))


def _detail(exc: BaseException) -> str:
    return normalise(f"{type(exc).__name__}: {exc}")


def _read_request() -> tuple[str, TrialSpec]:
    raw = sys.stdin.buffer.readline()
    request = json.loads(raw)
    if not isinstance(request, dict):
        raise TypeError("worker request is not an object")
    nonce = request.get("nonce")
    if not isinstance(nonce, str) or not nonce:
        raise ValueError("worker request has no nonce")
    return nonce, TrialSpec.model_validate(request.get("spec"))


def main() -> int:
    try:
        nonce, spec = _read_request()
    except BaseException:
        return 2

    emit = _Emitter(spec.trial_id, nonce)
    latches = _Latches()
    emit("trial_start", {"seed": spec.seed, "arm": spec.arm, "variant": spec.variant})
    termination = Termination.COMPLETED
    detail = ""
    agent_result: dict[str, JsonValue] | None = None
    final_state: dict[str, JsonValue] | None = None
    toolbox: ToolBox | None = None
    toolset: ToolSet | None = None

    try:
        with contextlib.redirect_stdout(sys.stderr):
            toolset_factory = cast(ToolSetFactory, resolve(spec.toolset))
            agent = cast(AgentFn, resolve(spec.agent))
            toolset = toolset_factory(copy.deepcopy(spec.task), spec.seed)
            perturbations = tuple(build(fault) for fault in spec.condition.faults)
        toolbox = ToolBox(
            toolset.tools,
            spec.budgets,
            emit,
            mode=spec.tool_mode,
            recording=spec.recording,
            perturbations=perturbations,
            seed=spec.seed,
            latch_budget=latches.set_budget,
            latch_harness=latches.set_harness,
            latch_replay=latches.set_replay,
        )
        try:
            with contextlib.redirect_stdout(sys.stderr):
                returned = agent(
                    copy.deepcopy(spec.task), toolbox, random.Random(f"{spec.seed}:agent")
                )
            agent_result = _AGENT_RESULT.validate_python(returned)
            emit("agent_result", {"result": copy.deepcopy(agent_result)})
        except ReplayMiss as exc:
            termination = Termination.REPLAY_MISS
            detail = _detail(exc)
            latches.set_replay(detail)
        except BudgetExceeded as exc:
            termination = Termination.BUDGET
            detail = _detail(exc)
            latches.set_budget(detail)
        except ToolFault as exc:
            termination = Termination.CRASH
            detail = _detail(exc)
        except BaseException as exc:
            termination = Termination.CRASH
            detail = _detail(exc)
            agent_result = None

        if spec.tool_mode is ToolMode.REPLAY:
            try:
                toolbox.assert_replay_consumed()
            except ReplayMiss as exc:
                latches.set_replay(_detail(exc))

        if latches.replay is None:
            if spec.tool_mode is ToolMode.REPLAY:
                final_state = copy.deepcopy(spec.replay_final_state)
            else:
                with contextlib.redirect_stdout(sys.stderr):
                    snapshot = toolset.snapshot()
                final_state = _FINAL_STATE.validate_python(snapshot)
    except BaseException as exc:
        latches.set_harness(_detail(exc))

    if latches.replay is not None:
        termination = Termination.REPLAY_MISS
        detail = latches.replay
    elif latches.harness is not None:
        termination = Termination.HARNESS_ERROR
        detail = latches.harness
    elif latches.budget is not None:
        termination = Termination.BUDGET
        detail = latches.budget

    result: dict[str, object] = {
        "termination": termination.value,
        "detail": detail,
        "agent_result": agent_result,
        "final_state": final_state,
        "recording": (
            []
            if toolbox is None
            else [record.model_dump(mode="json") for record in toolbox.recording]
        ),
        "latches": {
            "replay": latches.replay,
            "harness": latches.harness,
            "budget": latches.budget,
        },
    }
    _write_frame(nonce, "result", "result", result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
