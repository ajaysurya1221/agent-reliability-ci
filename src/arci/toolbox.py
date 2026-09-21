"""Agent-facing tool boundary with recording, replay and fault injection."""

from __future__ import annotations

import copy
import random
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from typing import TypeVar

from pydantic import JsonValue

from arci.fingerprint import normalise
from arci.hashing import canonical_json, hash_record
from arci.interfaces import BudgetExceeded, Perturbation, ReplayMiss, ToolFault
from arci.schema import Budgets, RecordedCall, ToolCall, ToolMode, ToolResult

Emit = Callable[[str, dict[str, JsonValue]], None]
Latch = Callable[[str], None]
JsonT = TypeVar("JsonT", bound=JsonValue)


def format_diagnostic(value: BaseException | str) -> str:
    """Return a deterministic, one-line, UTF-8-safe diagnostic without raising."""
    fallback = "<unprintable diagnostic>"
    try:
        if isinstance(value, BaseException):
            name = type(value).__name__
            fallback = f"<unprintable {name}>"
            try:
                message = str(value)
            except BaseException:
                text = fallback
            else:
                text = f"{name}: {message}" if message else name
        else:
            text = value
        text = text.encode("utf-8", errors="replace").decode("utf-8")
        return normalise(text)
    except BaseException:
        return fallback


def _arguments_sha256(arguments: dict[str, JsonValue]) -> str:
    return hash_record(arguments)


def _copy_json(value: JsonT) -> JsonT:
    """Return an independent boundary value without changing its JSON shape."""
    return copy.deepcopy(value)


def _agent_json(value: JsonT) -> JsonT:
    """Copy and validate agent input before any boundary side effect."""
    try:
        copied = _copy_json(value)
        canonical_json(copied)
    except BaseException as exc:
        raise ValueError("value is not canonical JSON") from exc
    return copied


def _validate_harness_json(value: object) -> None:
    """Reject a harness value that could not cross or be sealed safely."""
    canonical_json(value)


def _require_result(value: object, hook: str) -> ToolResult:
    if not isinstance(value, ToolResult):
        raise TypeError(f"perturbation {hook} returned an invalid result")
    return value


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
        event_payload = _agent_json({"summary": summary, **payload})
        if self.__model_steps >= self.__budgets.max_model_steps:
            detail = "model step budget exhausted"
            self.__mark_budget(detail)
            raise BudgetExceeded(detail)
        try:
            self.__model_steps += 1
            self.__emit("model_step", event_payload)
        except BaseException as exc:
            detail = format_diagnostic(exc)
            self.__mark_harness(detail)
            raise

    def call(self, tool: str, **arguments: JsonValue) -> JsonValue:
        call_tool = _agent_json(tool)
        call_arguments = _agent_json(arguments)
        if self.__tool_calls >= self.__budgets.max_tool_calls:
            detail = "tool call budget exhausted"
            self.__mark_budget(detail)
            raise BudgetExceeded(detail)

        try:
            occurrence = self.__occurrences[call_tool]
            call = ToolCall(
                call_id=f"c-{self.__tool_calls:04d}",
                tool=call_tool,
                arguments=call_arguments,
                occurrence=occurrence,
            )
            self.__tool_calls += 1
            self.__occurrences[call_tool] += 1
            self.__emit(
                "tool_start",
                _copy_json(
                    {
                        "tool": call_tool,
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
                    recorded = RecordedCall(
                        tool=call_tool,
                        arguments_sha256=_arguments_sha256(call_arguments),
                        occurrence=occurrence,
                        result=result.model_copy(deep=True),
                    )
                    _validate_harness_json(recorded.model_dump(mode="python"))
                    self.__recorded.append(recorded)

            finish_payload: dict[str, JsonValue] = {
                "tool": result.tool,
                "call_id": result.call_id,
                "ok": result.ok,
                "value": _copy_json(result.value),
                "error_kind": result.error_kind,
                "injected_by": result.injected_by,
            }
            _validate_harness_json(finish_payload)
            self.__emit("tool_finish", finish_payload)
            returned = _copy_json(result.value)
        except (BudgetExceeded, ReplayMiss, ToolFault):
            raise
        except BaseException as exc:
            detail = format_diagnostic(exc)
            self.__mark_harness(detail)
            raise

        if not result.ok:
            raise ToolFault(result.error_kind or "error", result.error_detail or "")
        return returned

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
            except BaseException as exc:
                self.__mark_harness(format_diagnostic(exc))
                raise
            if injected is not None:
                result = _require_result(injected, "before()").model_copy(deep=True)
                self.__validate_result(call, result)
                return result

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
                    error_detail=format_diagnostic(exc),
                )
            else:
                result = ToolResult(
                    call_id=call.call_id,
                    tool=call.tool,
                    ok=True,
                    value=_copy_json(value),
                )
        self.__validate_result(call, result)

        for perturbation in self.__perturbations:
            try:
                rewritten_value = perturbation.after(
                    call.model_copy(deep=True),
                    result.model_copy(deep=True),
                    random.Random(f"{self.__seed}:fault:{perturbation.name}"),
                )
            except BaseException as exc:
                self.__mark_harness(format_diagnostic(exc))
                raise
            rewritten = _require_result(rewritten_value, "after()")
            result = rewritten
            self.__validate_result(call, result)
        copied = result.model_copy(deep=True)
        self.__validate_result(call, copied)
        return copied

    @staticmethod
    def __validate_result(call: ToolCall, result: ToolResult) -> None:
        if result.call_id != call.call_id or result.tool != call.tool:
            raise ValueError("tool result does not match its call")
        _validate_harness_json(result.model_dump(mode="python"))
