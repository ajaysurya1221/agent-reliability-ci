"""Closed, immutable session-log decisions and their integrity seals."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import date
from fractions import Fraction
from itertools import pairwise
from typing import TYPE_CHECKING, Annotated, Literal, Self

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

from .records import EFFORTS, VERSION_PATTERN, Tool, render_model, version_order

if TYPE_CHECKING:
    from .measures import ToolTable

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


def _model_v1(value: str) -> str:
    if "sol" in re.split(r"[-._]", value):
        raise ValueError("invalid_model")
    return _model(value)


def _effort_v1(value: str) -> str:
    if value in {"none", "ultra", "persistent"}:
        raise ValueError("invalid_effort")
    return _effort(value)


ModelNameV1 = Annotated[StrictStr, AfterValidator(_model_v1)]
EffortNameV1 = Annotated[StrictStr, AfterValidator(_effort_v1)]
KeptState = Literal["not_read", "absent", "read", "unreadable"]


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


class DayValueV1(Model):
    day: Day
    count: Annotated[StrictInt, Field(gt=0)]
    value: Rational


class ContextCountsV1(Model):
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


def median_v1(values: tuple[DayValueV1, ...]) -> str | None:
    if not values:
        return None
    ordered = sorted(Fraction(day.value) for day in values)
    n = len(ordered)
    value = (ordered[(n - 1) // 2] + ordered[n // 2]) / 2
    return f"{value.numerator}/{value.denominator}"


class MeasureDecisionV1(Model):
    id: MeasureId
    worse: Literal["lower", "higher"]
    margin: Rational
    before_days: tuple[DayValueV1, ...]
    after_days: tuple[DayValueV1, ...]
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
        if self.median_before != median_v1(self.before_days) or self.median_after != median_v1(
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
        from . import rank_test
        from .decide import move_before

        direction = 1 if self.worse == "lower" else -1
        before = [direction * Fraction(day.value) for day in self.before_days]
        after = [direction * Fraction(day.value) for day in self.after_days]
        if self.p_streak is not None and Fraction(self.p_streak) != rank_test.p_streak(before):
            raise ValueError("inconsistent_p_streak")
        if self.p_real is not None and Fraction(self.p_real) != rank_test.p_real(before, after):
            raise ValueError("inconsistent_p_real")
        if self.u_none is not None:
            moved = [move_before(self.id, value) for value in before]
            if self.u_none != rank_test.strict_count(moved, after):
                raise ValueError("inconsistent_u_none")
            if self.p_none is None or Fraction(self.p_none) != rank_test.p_none(moved, after):
                raise ValueError("inconsistent_p_none")
        if self.u_none is not None and self.u_none > len(self.before_days) * len(self.after_days):
            raise ValueError("invalid_pair_count")
        return self


class ToolDecisionV1(Model):
    tool: Tool
    result: Result
    reason: ReasonCode
    model: ModelNameV1 | None = None
    effort: EffortNameV1 | None = None
    other_settings: NonNegative = 0
    split_date: Day | None = None
    before: Period | None = None
    after: Period | None = None
    measures: tuple[MeasureDecisionV1, ...] = ()
    context: ContextCountsV1 | None = None
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
        if self.day_table_sha256 != day_table_digest(self):
            raise ValueError("inconsistent_day_table_sha256")
        return self


class LogsDecisionV1(Model):
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
    tools: tuple[ToolDecisionV1, ...] = Field(min_length=1, max_length=2)
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


class DayValue(Model):
    source: Literal["logs", "kept"] = "logs"
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

    client_versions_after_shown: tuple[StrictStr, ...] = Field(default=(), max_length=3)
    client_versions_after_more: NonNegative = 0

    @model_validator(mode="after")
    def _versions(self) -> Self:
        names = self.client_versions_after_shown
        if any(VERSION_PATTERN.fullmatch(name) is None for name in names):
            raise ValueError("invalid_version")
        if len(set(names)) != len(names) or tuple(version_order(names)) != names:
            raise ValueError("invalid_version_order")
        if len(names) + self.client_versions_after_more != self.client_versions_after:
            raise ValueError("invalid_version_count")
        return self

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
        from . import rank_test
        from .decide import move_before

        direction = 1 if self.worse == "lower" else -1
        before = [direction * Fraction(day.value) for day in self.before_days]
        after = [direction * Fraction(day.value) for day in self.after_days]
        if self.p_streak is not None and Fraction(self.p_streak) != rank_test.p_streak(before):
            raise ValueError("inconsistent_p_streak")
        if self.p_real is not None and Fraction(self.p_real) != rank_test.p_real(before, after):
            raise ValueError("inconsistent_p_real")
        if self.u_none is not None:
            moved = [move_before(self.id, value) for value in before]
            if self.u_none != rank_test.strict_count(moved, after):
                raise ValueError("inconsistent_u_none")
            if self.p_none is None or Fraction(self.p_none) != rank_test.p_none(moved, after):
                raise ValueError("inconsistent_p_none")
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

    first_response_day: Day | None = None
    response_days_before: NonNegative = 0
    response_days_after: NonNegative = 0
    earliest_test_date: Day | None = None
    kept_days_before: NonNegative = 0
    kept_days_after: NonNegative = 0
    kept_rows_other_offset: NonNegative = 0
    settings_not_kept: NonNegative = 0
    days_not_kept: NonNegative = 0

    @model_validator(mode="after")
    def _days(self) -> Self:
        if self.model is None:
            if any(
                (
                    self.first_response_day,
                    self.earliest_test_date,
                    self.response_days_before,
                    self.response_days_after,
                    self.kept_days_before,
                    self.kept_days_after,
                )
            ):
                raise ValueError("invalid_empty_tool")
            if self.result == "ERROR" and any(
                (self.kept_rows_other_offset, self.settings_not_kept, self.days_not_kept)
            ):
                raise ValueError("invalid_empty_tool")
            return self
        assert self.before is not None
        first = self.first_response_day
        end = self.after.last_day if self.after else self.before.last_day
        if first is None or not self.before.first_day <= first <= end:
            raise ValueError("invalid_first_response_day")
        if not self.response_days_before + self.response_days_after:
            raise ValueError("invalid_response_days")
        sources: dict[str, str] = {}
        for measure in self.measures:
            for day in (*measure.before_days, *measure.after_days):
                if sources.setdefault(day.day, day.source) != day.source:
                    raise ValueError("inconsistent_day_source")
                if measure.id != "edit_failure_share" and day.day < first:
                    raise ValueError("invalid_first_response_day")
        for before, period, responses, kept in (
            (True, self.before, self.response_days_before, self.kept_days_before),
            (False, self.after, self.response_days_after, self.kept_days_after),
        ):
            capacity = (
                (date.fromisoformat(period.last_day) - date.fromisoformat(period.first_day)).days
                + 1
                if period
                else 0
            )
            kept_dates: set[str] = set()
            for measure in self.measures:
                days = measure.before_days if before else measure.after_days
                kept_dates.update(day.day for day in days if day.source == "kept")
                if measure.id != "edit_failure_share" and responses < len(days):
                    raise ValueError("invalid_response_days")
            if not len(kept_dates) <= kept <= capacity:
                raise ValueError("invalid_kept_days")
            if responses > capacity:
                raise ValueError("invalid_response_days")
        if self.earliest_test_date is not None and (
            self.reason != "too_few_days"
            or self.earliest_test_date != earliest_date(self.measures, self.after)
        ):
            raise ValueError("invalid_earliest_test_date")
        return self

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
        if self.day_table_sha256 != day_table_digest(self):
            raise ValueError("inconsistent_day_table_sha256")
        return self


def day_table_digest(table: ToolTable | ToolDecision | ToolDecisionV1) -> str:
    from .decide import ALPHA_NONE, ALPHA_REAL, MARGINS
    from .measures import fraction_str

    return hash_record(
        {
            "method": "arci-logs/1" if isinstance(table, ToolDecisionV1) else "arci-logs/2",
            "tool": table.tool,
            "model": table.model,
            "effort": table.effort,
            "split_date": table.split_date,
            "before": table.before.model_dump(mode="json") if table.before else None,
            "after": table.after.model_dump(mode="json") if table.after else None,
            "alpha_real": fraction_str(ALPHA_REAL),
            "alpha_none": fraction_str(ALPHA_NONE),
            "measures": [
                {
                    "id": m.id,
                    "margin": fraction_str(MARGINS[m.id]),
                    "before_days": [d.model_dump(mode="json") for d in m.before_days],
                    "after_days": [d.model_dump(mode="json") for d in m.after_days],
                }
                for m in table.measures
            ],
        }
    )


class LogsDecision(Model):
    schema_version: Literal["arci-logs/2"] = "arci-logs/2"
    arci_version: Annotated[
        StrictStr,
        Field(
            pattern=r"^[0-9]+\.[0-9]+\.[0-9]+(?:a[0-9]+|b[0-9]+|rc[0-9]+|\.post[0-9]+|\.dev[0-9]+)?$"
        ),
    ]
    example: StrictBool
    utc_offset_minutes: Annotated[StrictInt, Field(gt=-1440, lt=1440)]
    since_given: StrictBool = False
    kept_table: KeptState = "not_read"
    keep: StrictBool = False
    project_filtered: StrictBool
    tools: tuple[ToolDecision, ...] = Field(min_length=1, max_length=2)
    exit_code: Annotated[StrictInt, Field(ge=0, le=3)]
    seal: StrictStr = ""

    @model_validator(mode="after")
    def _kept(self) -> Self:
        if self.kept_table == "not_read" and self.keep:
            raise ValueError("invalid_kept_state")
        if (self.example or self.project_filtered) and self.kept_table != "not_read":
            raise ValueError("invalid_kept_state")
        if self.example and self.keep:
            raise ValueError("invalid_kept_state")
        for tool in self.tools:
            if not self.keep and (tool.settings_not_kept or tool.days_not_kept):
                raise ValueError("invalid_keep_counts")
            if self.kept_table != "read" and (
                tool.kept_days_before
                or tool.kept_days_after
                or tool.kept_rows_other_offset
                or any(
                    day.source == "kept"
                    for m in tool.measures
                    for day in (*m.before_days, *m.after_days)
                )
            ):
                raise ValueError("invalid_kept_source")
            if tool.reason == "too_few_days" and not self.since_given and tool.after is None:
                raise ValueError("invalid_earliest_test_date")
            expected = (
                earliest_date(tool.measures, tool.after)
                if tool.reason == "too_few_days" and not self.since_given
                else None
            )
            if tool.earliest_test_date != expected:
                raise ValueError("invalid_earliest_test_date")
        return self

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


def verify_seal(decision: LogsDecision | LogsDecisionV1) -> bool:
    return decision.seal == hash_record(decision.model_dump(mode="json", exclude={"seal"}))


def earliest_date(measures: tuple[MeasureDecision, ...], after: Period | None) -> str | None:
    """First future default window with 5 after-days and 10 before-days, best case."""
    if after is None:
        return None
    newest = date.fromisoformat(after.last_day).toordinal()
    usable = [
        {date.fromisoformat(day.day).toordinal() for day in (*m.before_days, *m.after_days)}
        for m in measures
    ]
    for candidate in range(newest + 1, newest + 25):
        for days in usable:
            days.add(candidate)
            if (
                sum(candidate - 13 <= day <= candidate for day in days) >= 5
                and sum(candidate - 97 <= day <= candidate - 14 for day in days) >= 10
            ):
                return date.fromordinal(candidate).isoformat()
    raise ValueError("missing_gating_measures")
