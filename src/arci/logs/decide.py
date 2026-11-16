"""Exact method constants, per-measure tests, result ladder and day-table digest."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict
from fractions import Fraction
from typing import TYPE_CHECKING

from . import rank_test
from .records import ReaderCounters as InputCounters
from .records import Tool
from .schema import (
    Finding,
    MeasureDecision,
    MeasureId,
    ReaderCounters,
    ReasonCode,
    Result,
    ToolDecision,
    ToolDecisionV1,
    earliest_date,
    median,
)
from .schema import (
    day_table_digest as day_table_digest,
)

if TYPE_CHECKING:
    from .measures import MeasureTable, ToolTable

ALPHA_REAL = Fraction(1, 120)
ALPHA_NONE = Fraction(1, 40)
ALPHA_STREAK = Fraction(1, 10)
MARGINS: dict[MeasureId, Fraction] = {
    "reasoning_tokens": Fraction(1, 4),
    "no_reasoning_share": Fraction(1, 10),
    "edit_failure_share": Fraction(3, 100),
    "repeated_value_share": Fraction(1, 10),
}
MIN_AFTER = 5
MIN_BEFORE = 10
BEFORE_DAYS = 84
DEFAULT_AFTER_DAYS = 14


def ladder(findings: Sequence[Finding]) -> tuple[Result, ReasonCode]:
    if all(f == "too_few_days" for f in findings):
        return "CANNOT_TELL", "too_few_days"
    if "streaky" in findings:
        return "CANNOT_TELL", "streaky_days"
    if "real_drop" in findings:
        return "REAL_DROP", "real_drop"
    if all(f == "no_drop" for f in findings):
        return "NO_DROP", "no_drop"
    return "CANNOT_TELL", "not_enough_evidence"


def move_before(measure: MeasureId, value: Fraction) -> Fraction:
    return (
        value * (1 - MARGINS[measure])
        if measure == "reasoning_tokens"
        else value - MARGINS[measure]
    )


def _measure(table: MeasureTable) -> MeasureDecision:
    from .measures import fraction_str

    direction = 1 if table.id == "reasoning_tokens" else -1
    before = [direction * Fraction(d.value) for d in table.before_days]
    after = [direction * Fraction(d.value) for d in table.after_days]
    streak = real = none = None
    count = None
    finding: Finding = "too_few_days"
    if len(before) >= MIN_BEFORE and len(after) >= MIN_AFTER:
        streak = rank_test.p_streak(before)
        finding = "streaky"
        if streak > ALPHA_STREAK:
            real = rank_test.p_real(before, after)
            finding = "real_drop"
            if real > ALPHA_REAL:
                moved = [move_before(table.id, value) for value in before]
                count = rank_test.strict_count(moved, after)
                none = rank_test.p_none(moved, after)
                finding = "no_drop" if none <= ALPHA_NONE else "cannot_tell"
    return MeasureDecision(
        id=table.id,
        worse="lower" if direction == 1 else "higher",
        margin=fraction_str(MARGINS[table.id]),
        before_days=table.before_days,
        after_days=table.after_days,
        median_before=median(table.before_days),
        median_after=median(table.after_days),
        p_streak=fraction_str(streak) if streak is not None else None,
        p_real=fraction_str(real) if real is not None else None,
        u_none=count,
        p_none=fraction_str(none) if none is not None else None,
        finding=finding,
    )


def decide_tool(
    table: ToolTable, counters: InputCounters, *, since_given: bool = False
) -> ToolDecision:
    counts = ReaderCounters(**asdict(counters))
    if table.model is None:
        return ToolDecision(
            tool=table.tool,
            result="CANNOT_TELL",
            reason="no_usable_setting",
            split_date=table.split_date,
            counters=counts,
            other_settings=table.other_settings,
            kept_rows_other_offset=table.kept_rows_other_offset,
            settings_not_kept=table.settings_not_kept,
            days_not_kept=table.days_not_kept,
        )
    measures = tuple(_measure(m) for m in table.measures)
    result, reason = ladder(tuple(m.finding for m in measures))
    return ToolDecision(
        tool=table.tool,
        result=result,
        reason=reason,
        model=table.model,
        effort=table.effort,
        other_settings=table.other_settings,
        split_date=table.split_date,
        before=table.before,
        after=table.after,
        measures=measures,
        context=table.context,
        counters=counts,
        day_table_sha256=day_table_digest(table),
        first_response_day=table.first_response_day,
        response_days_before=table.response_days_before,
        response_days_after=table.response_days_after,
        earliest_test_date=earliest_date(measures, table.after)
        if reason == "too_few_days" and not since_given
        else None,
        kept_days_before=table.kept_days_before,
        kept_days_after=table.kept_days_after,
        kept_rows_other_offset=table.kept_rows_other_offset,
        settings_not_kept=table.settings_not_kept,
        days_not_kept=table.days_not_kept,
    )


def error_tool(tool: Tool, reason: str, counters: InputCounters) -> ToolDecision:
    if reason not in {"no_logs", "read_error", "format_not_recognised"}:
        raise ValueError("invalid_error_reason")
    return ToolDecision.model_validate(
        {"tool": tool, "result": "ERROR", "reason": reason, "counters": asdict(counters)}
    )


def exit_code(tools: Sequence[ToolDecision | ToolDecisionV1]) -> int:
    results = {tool.result for tool in tools} - {"ERROR"}
    if "REAL_DROP" in results:
        return 1
    if "CANNOT_TELL" in results:
        return 2
    return 0 if results else 3
