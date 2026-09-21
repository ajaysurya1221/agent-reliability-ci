"""Agent-facing tool boundary with recording, replay and fault injection."""

from __future__ import annotations

import random
from collections import Counter
from collections.abc import Callable, Mapping, Sequence

from pydantic import JsonValue

from arci.fingerprint import normalise
from arci.hashing import hash_record
from arci.interfaces import BudgetExceeded, Perturbation, ReplayMiss, ToolFault
from arci.schema import Budgets, RecordedCall, ToolCall, ToolMode, ToolResult

Emit = Callable[[str, dict[str, JsonValue]], None]


def _arguments_sha256(arguments: dict[str, JsonValue]) -> str:
    return hash_record(arguments)


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
    ) -> None:
        self._tools = tools
        self._budgets = budgets
        self._emit = emit
        self._mode = mode
        self._source_recording = tuple(recording)
        self._perturbations = tuple(perturbations)
        self._seed = seed
        self._occurrences: Counter[str] = Counter()
        self._tool_calls = 0
        self._model_steps = 0
        self._replay_index = 0
        self._replay_miss = False
        self._recorded: list[RecordedCall] = []

    @property
    def recording(self) -> tuple[RecordedCall, ...]:
        if self._mode is ToolMode.REPLAY:
            return self._source_recording
        return tuple(self._recorded)

    @property
    def tool_calls(self) -> int:
        return self._tool_calls

    @property
    def model_steps(self) -> int:
        return self._model_steps

    @property
    def replay_miss(self) -> bool:
        return self._replay_miss

    @property
    def has_unconsumed_recording(self) -> bool:
        return self._mode is ToolMode.REPLAY and self._replay_index != len(self._source_recording)

    def assert_replay_consumed(self) -> None:
        if self._replay_miss or self.has_unconsumed_recording:
            self._replay_miss = True
            raise ReplayMiss("recording was not consumed exactly")

    def note_model_step(self, summary: str, **payload: JsonValue) -> None:
        if self._model_steps >= self._budgets.max_model_steps:
            raise BudgetExceeded("model step budget exhausted")
        self._model_steps += 1
        self._emit("model_step", {"summary": summary, **payload})

    def call(self, tool: str, **arguments: JsonValue) -> JsonValue:
        if self._tool_calls >= self._budgets.max_tool_calls:
            raise BudgetExceeded("tool call budget exhausted")

        occurrence = self._occurrences[tool]
        call = ToolCall(
            call_id=f"c-{self._tool_calls:04d}",
            tool=tool,
            arguments=arguments,
            occurrence=occurrence,
        )
        self._tool_calls += 1
        self._occurrences[tool] += 1
        self._emit(
            "tool_start",
            {
                "tool": tool,
                "call_id": call.call_id,
                "occurrence": occurrence,
                "arguments": arguments,
            },
        )

        if self._mode is ToolMode.REPLAY:
            try:
                result = self._replay(call)
            except ReplayMiss:
                self._emit(
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
            result = self._execute(call)
            if self._mode is ToolMode.RECORD:
                self._recorded.append(
                    RecordedCall(
                        tool=tool,
                        arguments_sha256=_arguments_sha256(arguments),
                        occurrence=occurrence,
                        result=result,
                    )
                )

        self._emit(
            "tool_finish",
            {
                "tool": result.tool,
                "call_id": result.call_id,
                "ok": result.ok,
                "value": result.value,
                "error_kind": result.error_kind,
                "injected_by": result.injected_by,
            },
        )
        if not result.ok:
            raise ToolFault(result.error_kind or "error", result.error_detail or "")
        return result.value

    def _replay(self, call: ToolCall) -> ToolResult:
        key = (call.tool, _arguments_sha256(call.arguments), call.occurrence)
        if self._replay_index >= len(self._source_recording):
            self._replay_miss = True
            raise ReplayMiss(f"no recorded result for {call.tool}")
        recorded = self._source_recording[self._replay_index]
        expected = (recorded.tool, recorded.arguments_sha256, recorded.occurrence)
        if key != expected:
            self._replay_miss = True
            raise ReplayMiss(f"recording mismatch for {call.tool}")
        self._replay_index += 1
        return recorded.result

    def _execute(self, call: ToolCall) -> ToolResult:
        for perturbation in self._perturbations:
            injected = perturbation.before(
                call, random.Random(f"{self._seed}:fault:{perturbation.name}")
            )
            if injected is not None:
                return injected

        function = self._tools.get(call.tool)
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
                value = function(**call.arguments)
                result = ToolResult(call_id=call.call_id, tool=call.tool, ok=True, value=value)
            except Exception as exc:
                result = ToolResult(
                    call_id=call.call_id,
                    tool=call.tool,
                    ok=False,
                    error_kind="error",
                    error_detail=normalise(f"{type(exc).__name__}: {exc}"),
                )

        for perturbation in self._perturbations:
            result = perturbation.after(
                call, result, random.Random(f"{self._seed}:fault:{perturbation.name}")
            )
        return result
