"""Closed, immutable session-log decisions and their integrity seals."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import date
from fractions import Fraction
from itertools import pairwise
from typing import Annotated, Literal, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    model_validator,
)

from arci.hashing import hash_record

from .records import EFFORTS, Tool, render_model

MeasureId = Literal[
    "reasoning_tokens", "no_reasoning_share", "edit_failure_share", "repeated_value_share"
]
Finding = Literal["streaky", "real_drop", "no_drop", "cannot_tell", "too_few_days"]
ReasonCode = Literal[
    "real_drop",
    "no_drop",
    "not_enough_evidence",
    "too_few_days",
    "streaky_days",
    "no_usable_setting",
    "no_logs",
    "read_error",
    "format_not_recognised",
]
Result = Literal["REAL_DROP", "NO_DROP", "CANNOT_TELL", "ERROR"]
NonNegative = Annotated[StrictInt, Field(ge=0)]
Digest = Annotated[StrictStr, Field(pattern=r"^[0-9a-f]{64}$")]


def validate_rational(value: str) -> str:
    if re.fullmatch(r"-?(?:0|[1-9][0-9]*)/[1-9][0-9]*", value) is None:
        raise ValueError("invalid_rational")
    number = Fraction(value)
    if value != f"{number.numerator}/{number.denominator}":
        raise ValueError("noncanonical_rational")
    return value


def _day(value: str) -> str:
    if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value) is None:
        raise ValueError("invalid_date")
    try:
        date.fromisoformat(value)
    except ValueError:
        raise ValueError("invalid_date") from None
    return value


def _model(value: str) -> str:
    if render_model(value) is None and re.fullmatch(r"model-[1-9][0-9]*", value) is None:
        raise ValueError("invalid_model")
    return value


def _effort(value: str) -> str:
    if value not in EFFORTS and re.fullmatch(r"effort-[1-9][0-9]*", value) is None:
        raise ValueError("invalid_effort")
    return value


Rational = Annotated[StrictStr, AfterValidator(validate_rational)]
Day = Annotated[StrictStr, AfterValidator(_day)]
ModelName = Annotated[StrictStr, AfterValidator(_model)]
EffortName = Annotated[StrictStr, AfterValidator(_effort)]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ReaderCounters(Model):
    files_read: NonNegative = 0
    files_unread_compressed: NonNegative = 0
    files_unreadable: NonNegative = 0
    files_outside_project: NonNegative = 0
    lines: NonNegative = 0
    lines_not_json: NonNegative = 0
    lines_unknown_type: NonNegative = 0
    lines_lacking_field: NonNegative = 0
    records_in_future: NonNegative = 0
    records_without_timezone: NonNegative = 0
    responses: NonNegative = 0
    responses_duplicate: NonNegative = 0
    responses_without_reasoning: NonNegative = 0
    responses_without_setting: NonNegative = 0
    edits_denied: NonNegative = 0
    edits_unmatched: NonNegative = 0


class Period(Model):
    first_day: Day
    last_day: Day

    @model_validator(mode="after")
    def _order(self) -> Self:
        if self.first_day > self.last_day:
            raise ValueError("invalid_period")
        return self


class DayValue(Model):
    day: Day
    count: Annotated[StrictInt, Field(gt=0)]
    value: Rational


class ContextCounts(Model):
    client_versions_before: NonNegative
    client_versions_after: NonNegative
    client_versions_both: NonNegative
    workdirs_before: NonNegative
    workdirs_after: NonNegative
    subagent_share_before: Rational | None
    subagent_share_after: Rational | None

    @model_validator(mode="after")
    def _counts(self) -> Self:
        if self.client_versions_both > min(self.client_versions_before, self.client_versions_after):
            raise ValueError("invalid_context")
        for share in (self.subagent_share_before, self.subagent_share_after):
            if share is not None and not 0 <= Fraction(share) <= 1:
                raise ValueError("invalid_share")
        return self


def median(values: tuple[DayValue, ...]) -> str | None:
    if not values:
        return None
    ordered = sorted(Fraction(day.value) for day in values)
    n = len(ordered)
    value = (ordered[(n - 1) // 2] + ordered[n // 2]) / 2
    return f"{value.numerator}/{value.denominator}"


class MeasureDecision(Model):
    id: MeasureId
    worse: Literal["lower", "higher"]
    margin: Rational
    before_days: tuple[DayValue, ...]
    after_days: tuple[DayValue, ...]
    median_before: Rational | None
    median_after: Rational | None
    p_streak: Rational | None = None
    p_real: Rational | None = None
    u_none: NonNegative | None = None
    p_none: Rational | None = None
    finding: Finding

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        # Local import keeps all method constants in decide.py without a module cycle.
        from .decide import ALPHA_NONE, ALPHA_REAL, ALPHA_STREAK, MARGINS, MIN_AFTER, MIN_BEFORE

        if Fraction(self.margin) != MARGINS[self.id] or self.worse != (
            "lower" if self.id == "reasoning_tokens" else "higher"
        ):
            raise ValueError("invalid_measure_rule")
        for days in (self.before_days, self.after_days):
            if any(a.day >= b.day for a, b in pairwise(days)):
                raise ValueError("invalid_day_order")
            for day in days:
                value = Fraction(day.value)
                minimum = 20 if self.id == "no_reasoning_share" else 10
                if day.count < minimum or (
                    value <= 0 if self.worse == "lower" else not 0 <= value <= 1
                ):
                    raise ValueError("invalid_day_value")
        if self.median_before != median(self.before_days) or self.median_after != median(
            self.after_days
        ):
            raise ValueError("invalid_median")
        enough = len(self.before_days) >= MIN_BEFORE and len(self.after_days) >= MIN_AFTER
        if (self.finding == "too_few_days") == enough:
            raise ValueError("invalid_day_count")
        fields = (self.p_streak, self.p_real, self.u_none, self.p_none)
        filled = {"too_few_days": 0, "streaky": 1, "real_drop": 2, "no_drop": 4, "cannot_tell": 4}[
            self.finding
        ]
        if any((value is not None) != (i < filled) for i, value in enumerate(fields)):
            raise ValueError("invalid_test_fields")
        for probability in (self.p_streak, self.p_real, self.p_none):
            if probability is not None and not 0 <= Fraction(probability) <= 1:
                raise ValueError("invalid_probability")
        if self.p_streak is not None and (Fraction(self.p_streak) <= ALPHA_STREAK) != (
            self.finding == "streaky"
        ):
            raise ValueError("invalid_streak_finding")
        if self.p_real is not None and (Fraction(self.p_real) <= ALPHA_REAL) != (
            self.finding == "real_drop"
        ):
            raise ValueError("invalid_real_finding")
        if self.p_none is not None and (Fraction(self.p_none) <= ALPHA_NONE) != (
            self.finding == "no_drop"
        ):
            raise ValueError("invalid_none_finding")
        if self.u_none is not None and self.u_none > len(self.before_days) * len(self.after_days):
            raise ValueError("invalid_pair_count")
        return self


class ToolDecision(Model):
    tool: Tool
    result: Result
    reason: ReasonCode
    model: ModelName | None = None
    effort: EffortName | None = None
    other_settings: NonNegative = 0
    split_date: Day | None = None
    before: Period | None = None
    after: Period | None = None
    measures: tuple[MeasureDecision, ...] = ()
    context: ContextCounts | None = None
    counters: ReaderCounters
    day_table_sha256: Digest | None = None

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        from .decide import BEFORE_DAYS, ladder

        error = self.reason in {"no_logs", "read_error", "format_not_recognised"}
        empty = error or self.reason == "no_usable_setting"
        if empty:
            if (
                self.result != ("ERROR" if error else "CANNOT_TELL")
                or any(
                    value is not None
                    for value in (
                        self.model,
                        self.effort,
                        self.before,
                        self.after,
                        self.context,
                        self.day_table_sha256,
                    )
                )
                or self.measures
            ):
                raise ValueError("invalid_empty_tool")
            return self
        if any(
            value is None
            for value in (
                self.model,
                self.effort,
                self.split_date,
                self.before,
                self.context,
                self.day_table_sha256,
            )
        ):
            raise ValueError("missing_tool_fields")
        expected = (
            "reasoning_tokens",
            "no_reasoning_share",
            "edit_failure_share" if self.tool == "claude-code" else "repeated_value_share",
        )
        if tuple(m.id for m in self.measures) != expected:
            raise ValueError("invalid_measure_order")
        if (self.result, self.reason) != ladder(tuple(m.finding for m in self.measures)):
            raise ValueError("invalid_result")
        assert self.before is not None and self.split_date is not None
        split = date.fromisoformat(self.split_date)
        if (split - date.fromisoformat(self.before.first_day)).days != BEFORE_DAYS or (
            split - date.fromisoformat(self.before.last_day)
        ).days != 1:
            raise ValueError("invalid_before_period")
        if self.after is not None and self.after.first_day != self.split_date:
            raise ValueError("invalid_after_period")
        for measure in self.measures:
            for days, period in (
                (measure.before_days, self.before),
                (measure.after_days, self.after),
            ):
                if days and period is None:
                    raise ValueError("days_without_period")
                if period is not None and any(
                    not period.first_day <= d.day <= period.last_day for d in days
                ):
                    raise ValueError("day_outside_period")
        return self


class LogsDecision(Model):
    schema_version: Literal["arci-logs/1"] = "arci-logs/1"
    arci_version: Annotated[
        StrictStr,
        Field(
            pattern=r"^[0-9]+\.[0-9]+\.[0-9]+(?:a[0-9]+|b[0-9]+|rc[0-9]+|\.post[0-9]+|\.dev[0-9]+)?$"
        ),
    ]
    example: StrictBool
    utc_offset_minutes: Annotated[StrictInt, Field(gt=-1440, lt=1440)]
    project_filtered: StrictBool
    tools: tuple[ToolDecision, ...] = Field(min_length=1, max_length=2)
    exit_code: Annotated[StrictInt, Field(ge=0, le=3)]
    seal: StrictStr = ""

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        from .decide import exit_code

        names = tuple(tool.tool for tool in self.tools)
        if names not in (("claude-code",), ("codex",), ("claude-code", "codex")):
            raise ValueError("invalid_tool_order")
        if self.exit_code != exit_code(self.tools):
            raise ValueError("invalid_exit_code")
        if self.seal and re.fullmatch(r"[0-9a-f]{64}", self.seal) is None:
            raise ValueError("invalid_seal")
        return self


def seal(decision_without_seal: LogsDecision | Mapping[str, object]) -> LogsDecision:
    decision = LogsDecision.model_validate(decision_without_seal)
    return decision.model_copy(
        update={"seal": hash_record(decision.model_dump(mode="json", exclude={"seal"}))}
    )


def verify_seal(decision: LogsDecision) -> bool:
    return decision.seal == hash_record(decision.model_dump(mode="json", exclude={"seal"}))
