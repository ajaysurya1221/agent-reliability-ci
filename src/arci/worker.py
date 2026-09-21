"""Isolated trial worker. Standard output is a JSON-lines protocol."""

from __future__ import annotations

import contextlib
import json
import random
import sys
import time
from typing import Any, cast

from pydantic import JsonValue, TypeAdapter

from arci.contracts import resolve
from arci.fingerprint import normalise
from arci.interfaces import AgentFn, BudgetExceeded, ReplayMiss, ToolFault, ToolSetFactory
from arci.perturb import build
from arci.schema import Event, Termination, ToolMode, TrialSpec
from arci.toolbox import ToolBox

_FINAL_STATE = TypeAdapter(dict[str, JsonValue])


class _Emitter:
    def __init__(self, trial_id: str) -> None:
        self._trial_id = trial_id
        self._seq = 0
        self._started = time.monotonic()
        self._stream = sys.stdout

    def __call__(self, kind: str, payload: dict[str, JsonValue]) -> None:
        event = Event(
            trial_id=self._trial_id,
            seq=self._seq,
            kind=cast(Any, kind),
            payload=payload,
            at_ms=(time.monotonic() - self._started) * 1000.0,
        )
        self._seq += 1
        print(event.model_dump_json(), file=self._stream, flush=True)


def _detail(exc: BaseException) -> str:
    return normalise(f"{type(exc).__name__}: {exc}")


def _final(payload: dict[str, object]) -> None:
    print(json.dumps({"worker_result": payload}, sort_keys=True, separators=(",", ":")), flush=True)


def main() -> int:
    try:
        spec = TrialSpec.model_validate_json(sys.stdin.readline())
    except Exception as exc:
        _final({"termination": Termination.HARNESS_ERROR.value, "detail": _detail(exc)})
        return 0

    emit = _Emitter(spec.trial_id)
    emit("trial_start", {"seed": spec.seed, "arm": spec.arm, "variant": spec.variant})
    termination = Termination.COMPLETED
    detail = ""
    agent_result: dict[str, JsonValue] | None = None
    final_state: dict[str, JsonValue] | None = None
    toolbox: ToolBox | None = None

    try:
        with contextlib.redirect_stdout(sys.stderr):
            toolset_factory = cast(ToolSetFactory, resolve(spec.toolset))
            agent = cast(AgentFn, resolve(spec.agent))
            toolset = toolset_factory(spec.task, spec.seed)
        toolbox = ToolBox(
            toolset.tools,
            spec.budgets,
            emit,
            mode=spec.tool_mode,
            recording=spec.recording,
            perturbations=tuple(build(fault) for fault in spec.condition.faults),
            seed=spec.seed,
        )
        try:
            with contextlib.redirect_stdout(sys.stderr):
                agent_result = agent(spec.task, toolbox, random.Random(f"{spec.seed}:agent"))
            emit("agent_result", {"result": agent_result})
            if spec.tool_mode is ToolMode.REPLAY:
                toolbox.assert_replay_consumed()
        except ReplayMiss as exc:
            termination = Termination.REPLAY_MISS
            detail = _detail(exc)
        except BudgetExceeded as exc:
            termination = Termination.BUDGET
            detail = _detail(exc)
        except ToolFault as exc:
            termination = Termination.CRASH
            detail = _detail(exc)
        except BaseException as exc:
            termination = Termination.CRASH
            detail = _detail(exc)
            agent_result = None

        if toolbox.replay_miss:
            termination = Termination.REPLAY_MISS
            detail = detail or "ReplayMiss: recording was not consumed exactly"
        if termination is not Termination.REPLAY_MISS:
            if spec.tool_mode is ToolMode.REPLAY:
                final_state = spec.replay_final_state
            else:
                with contextlib.redirect_stdout(sys.stderr):
                    final_state = _FINAL_STATE.validate_python(toolset.snapshot())
    except Exception as exc:
        termination = Termination.HARNESS_ERROR
        detail = _detail(exc)

    emit("trial_end", {"termination": termination.value})
    _final(
        {
            "termination": termination.value,
            "detail": detail,
            "agent_result": agent_result,
            "final_state": final_state,
            "recording": (
                []
                if toolbox is None
                else [record.model_dump(mode="json") for record in toolbox.recording]
            ),
            "tool_calls": 0 if toolbox is None else toolbox.tool_calls,
            "model_steps": 0 if toolbox is None else toolbox.model_steps,
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
