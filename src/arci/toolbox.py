"""Agent-facing tool boundary with recording, replay and fault injection."""

from __future__ import annotations

import copy
import random
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from typing import TypeVar

from pydantic import JsonValue

from arci.fingerprint import normalise
from arci.hashing import hash_record
from arci.interfaces import BudgetExceeded, Perturbation, ReplayMiss, ToolFault
from arci.schema import Budgets, RecordedCall, ToolCall, ToolMode, ToolResult

Emit = Callable[[str, dict[str, JsonValue]], None]
Latch = Callable[[str], None]
JsonT = TypeVar("JsonT", bound=JsonValue)


def _arguments_sha256(arguments: dict[str, JsonValue]) -> str:
    return hash_record(arguments)


def _copy_json(value: JsonT) -> JsonT:
    """Return an independent boundary value without changing its JSON shape."""
    return copy.deepcopy(value)


def _noop_latch(_detail: str) -> None:
    return None


class ToolBox:
    """One deterministic tool boundary for one worker process."""

    def __init__(
        self,
        tools: Mapping[str, Callable[..., JsonValue]],
        budgets: Budgets,
        emit: Emit,
        *,
        mode: ToolMode = ToolMode.RECORD,
        recording: Sequence[RecordedCall] = (),
        perturbations: Sequence[Perturbation] = (),
        seed: int = 0,
        latch_budget: Latch | None = None,
        latch_harness: Latch | None = None,
        latch_replay: Latch | None = None,
    ) -> None:
        self.__tools = tools
        self.__budgets = budgets
        self.__emit = emit
        self.__mode = mode
        self.__source_recording = tuple(recording)
        self.__perturbations = tuple(perturbations)
        self.__seed = seed
        self.__occurrences: Counter[str] = Counter()
        self.__tool_calls = 0
        self.__model_steps = 0
        self.__replay_index = 0
        self.__replay_miss = False
        self.__budget_exceeded = False
        self.__harness_fault = False
        self.__recorded: list[RecordedCall] = []
        self.__latch_budget = latch_budget or _noop_latch
        self.__latch_harness = latch_harness or _noop_latch
        self.__latch_replay = latch_replay or _noop_latch

    @property
    def recording(self) -> tuple[RecordedCall, ...]:
        if self.__mode is ToolMode.REPLAY:
            return self.__source_recording
        return tuple(self.__recorded)

    @property
    def tool_calls(self) -> int:
        return self.__tool_calls

    @property
    def model_steps(self) -> int:
        return self.__model_steps

    @property
    def replay_miss(self) -> bool:
        return self.__replay_miss

    @property
    def budget_exceeded(self) -> bool:
        return self.__budget_exceeded

    @property
    def harness_fault(self) -> bool:
        return self.__harness_fault

    @property
    def has_unconsumed_recording(self) -> bool:
        return self.__mode is ToolMode.REPLAY and self.__replay_index != len(
            self.__source_recording
        )

    def __mark_replay(self, detail: str) -> None:
        self.__replay_miss = True
        self.__latch_replay(detail)

    def __mark_budget(self, detail: str) -> None:
        self.__budget_exceeded = True
        self.__latch_budget(detail)

    def __mark_harness(self, detail: str) -> None:
        self.__harness_fault = True
        self.__latch_harness(detail)

    def assert_replay_consumed(self) -> None:
        if self.__replay_miss or self.has_unconsumed_recording:
            detail = "recording was not consumed exactly"
            self.__mark_replay(detail)
            raise ReplayMiss(detail)

    def note_model_step(self, summary: str, **payload: JsonValue) -> None:
        if self.__model_steps >= self.__budgets.max_model_steps:
            detail = "model step budget exhausted"
            self.__mark_budget(detail)
            raise BudgetExceeded(detail)
        self.__model_steps += 1
        self.__emit("model_step", _copy_json({"summary": summary, **payload}))

    def call(self, tool: str, **arguments: JsonValue) -> JsonValue:
        if self.__tool_calls >= self.__budgets.max_tool_calls:
            detail = "tool call budget exhausted"
            self.__mark_budget(detail)
            raise BudgetExceeded(detail)

        occurrence = self.__occurrences[tool]
        call_arguments = _copy_json(arguments)
        try:
            call = ToolCall(
                call_id=f"c-{self.__tool_calls:04d}",
                tool=tool,
                arguments=call_arguments,
                occurrence=occurrence,
            )
        except Exception as exc:
            detail = normalise(f"{type(exc).__name__}: {exc}")
            self.__mark_harness(detail)
            raise
        self.__tool_calls += 1
        self.__occurrences[tool] += 1
        self.__emit(
            "tool_start",
            _copy_json(
                {
                    "tool": tool,
                    "call_id": call.call_id,
                    "occurrence": occurrence,
                    "arguments": call_arguments,
                }
            ),
        )

        if self.__mode is ToolMode.REPLAY:
            try:
                result = self.__replay(call)
            except ReplayMiss:
                self.__emit(
                    "tool_finish",
                    {
                        "tool": call.tool,
                        "call_id": call.call_id,
                        "ok": False,
                        "value": None,
                        "error_kind": "replay_miss",
                        "injected_by": None,
                    },
                )
                raise
        else:
            result = self.__execute(call)
            if self.__mode is ToolMode.RECORD:
                self.__recorded.append(
                    RecordedCall(
                        tool=tool,
                        arguments_sha256=_arguments_sha256(call_arguments),
                        occurrence=occurrence,
                        result=result.model_copy(deep=True),
                    )
                )

        self.__emit(
            "tool_finish",
            _copy_json(
                {
                    "tool": result.tool,
                    "call_id": result.call_id,
                    "ok": result.ok,
                    "value": result.value,
                    "error_kind": result.error_kind,
                    "injected_by": result.injected_by,
                }
            ),
        )
        if not result.ok:
            raise ToolFault(result.error_kind or "error", result.error_detail or "")
        return _copy_json(result.value)

    def __replay(self, call: ToolCall) -> ToolResult:
        key = (call.tool, _arguments_sha256(call.arguments), call.occurrence)
        if self.__replay_index >= len(self.__source_recording):
            detail = f"no recorded result for {call.tool}"
            self.__mark_replay(detail)
            raise ReplayMiss(detail)
        recorded = self.__source_recording[self.__replay_index]
        expected = (recorded.tool, recorded.arguments_sha256, recorded.occurrence)
        if key != expected:
            detail = f"recording mismatch for {call.tool}"
            self.__mark_replay(detail)
            raise ReplayMiss(detail)
        self.__replay_index += 1
        return recorded.result.model_copy(deep=True)

    def __execute(self, call: ToolCall) -> ToolResult:
        for perturbation in self.__perturbations:
            try:
                injected = perturbation.before(
                    call.model_copy(deep=True),
                    random.Random(f"{self.__seed}:fault:{perturbation.name}"),
                )
            except Exception as exc:
                detail = normalise(f"{type(exc).__name__}: {exc}")
                self.__mark_harness(detail)
                raise
            if injected is not None:
                return injected.model_copy(deep=True)

        function = self.__tools.get(call.tool)
        if function is None:
            result = ToolResult(
                call_id=call.call_id,
                tool=call.tool,
                ok=False,
                error_kind="unknown_tool",
                error_detail=f"unknown tool: {call.tool}",
            )
        else:
            try:
                value = function(**_copy_json(call.arguments))
            except Exception as exc:
                result = ToolResult(
                    call_id=call.call_id,
                    tool=call.tool,
                    ok=False,
                    error_kind="error",
                    error_detail=normalise(f"{type(exc).__name__}: {exc}"),
                )
            else:
                try:
                    result = ToolResult(
                        call_id=call.call_id,
                        tool=call.tool,
                        ok=True,
                        value=_copy_json(value),
                    )
                except Exception as exc:
                    detail = normalise(f"{type(exc).__name__}: {exc}")
                    self.__mark_harness(detail)
                    raise

        for perturbation in self.__perturbations:
            try:
                result = perturbation.after(
                    call.model_copy(deep=True),
                    result.model_copy(deep=True),
                    random.Random(f"{self.__seed}:fault:{perturbation.name}"),
                )
            except Exception as exc:
                detail = normalise(f"{type(exc).__name__}: {exc}")
                self.__mark_harness(detail)
                raise
        return result.model_copy(deep=True)
