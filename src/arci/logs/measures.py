"""Reduce private reader identities to a deterministic, exact daily table."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from fractions import Fraction
from typing import Literal

from .records import ReadResult, Response, Tool
from .schema import ContextCounts, DayValue, MeasureId, Period, validate_rational


def fraction_str(x: Fraction) -> str:
    return f"{x.numerator}/{x.denominator}"


def parse_fraction(s: str) -> Fraction:
    return Fraction(validate_rational(s))


class UsageError(ValueError):
    def __init__(self, code: Literal["since_too_early", "calendar_range"]) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class WindowReadResult(ReadResult):
    """Retain the window anchor even when a response has no usable setting.

    Readers keep only an in-project, non-future main-thread timestamp here;
    unconfigured responses stay out of the response count and selected day values.
    """

    latest_main_response: datetime | None = None


@dataclass(frozen=True, slots=True)
class MeasureTable:
    id: MeasureId
    before_days: tuple[DayValue, ...]
    after_days: tuple[DayValue, ...]


@dataclass(frozen=True, slots=True)
class ToolTable:
    tool: Tool
    model: str | None
    effort: str | None
    other_settings: int
    split_date: str | None
    before: Period | None
    after: Period | None
    measures: tuple[MeasureTable, ...]
    context: ContextCounts | None
    reference_value: int | None = None


def _names(values: tuple[str | None, ...], order: tuple[int, ...], prefix: str) -> dict[int, str]:
    names: dict[int, str] = {}
    unknown = 0
    for i in order:
        name = values[i]
        if name is None:
            unknown += 1
            name = f"{prefix}-{unknown}"
        names[i] = name
    return names


def _context(before: list[Response], after: list[Response]) -> ContextCounts:
    vb, va = {r.version for r in before}, {r.version for r in after}
    return ContextCounts(
        client_versions_before=len(vb),
        client_versions_after=len(va),
        client_versions_both=len(vb & va),
        workdirs_before=len({r.workdir for r in before}),
        workdirs_after=len({r.workdir for r in after}),
        subagent_share_before=fraction_str(
            Fraction(sum(not r.main_thread for r in before), len(before))
        )
        if before
        else None,
        subagent_share_after=fraction_str(
            Fraction(sum(not r.main_thread for r in after), len(after))
        )
        if after
        else None,
    )


def build(
    result: ReadResult,
    *,
    utc_offset: timedelta,
    now: datetime,
    since: date | None = None,
    model: str | None = None,
    effort: str | None = None,
) -> ToolTable:
    from .decide import BEFORE_DAYS, DEFAULT_AFTER_DAYS

    try:
        zone = timezone(utc_offset)
        responses = [
            (r.when.astimezone(zone).date(), r)
            for r in result.responses
            if r.in_project and r.when.tzinfo is not None and r.when <= now
        ]
        main_days = [day for day, r in responses if r.main_thread]
        if isinstance(result, WindowReadResult) and result.latest_main_response is not None:
            main_days.append(result.latest_main_response.astimezone(zone).date())
        newest = max(main_days, default=None)
        split = (
            since
            if since is not None
            else (newest - timedelta(days=DEFAULT_AFTER_DAYS - 1) if newest else None)
        )
        if newest is not None and split is not None and (newest - split).days > BEFORE_DAYS - 1:
            raise UsageError("since_too_early")
        first = split - timedelta(days=BEFORE_DAYS) if split else None
        last = split - timedelta(days=1) if split else None
    except (OverflowError, ValueError) as error:
        if isinstance(error, UsageError):
            raise
        raise UsageError("calendar_range") from None
    empty = ToolTable(
        result.tool, None, None, 0, split.isoformat() if split else None, None, None, (), None
    )
    if newest is None or split is None or first is None or last is None:
        return empty
    # If the split is in the future, before still ends at split - 1; no after period exists.
    window_end = max(last, newest)
    window = [(d, r) for d, r in responses if first <= d <= window_end]
    counts = Counter((r.model, r.effort) for _, r in window if r.main_thread)
    models = _names(result.models, result.model_order, "model")
    efforts = _names(result.efforts, result.effort_order, "effort")
    eligible = [
        setting
        for setting in counts
        if (model is None or models[setting[0]] == model)
        and (effort is None or efforts[setting[1]] == effort)
    ]
    if not eligible:
        return empty
    model_ranks = {value: i for i, value in enumerate(result.model_order)}
    effort_ranks = {value: i for i, value in enumerate(result.effort_order)}
    chosen = min(
        eligible,
        key=lambda setting: (-counts[setting], model_ranks[setting[0]], effort_ranks[setting[1]]),
    )
    selected = [(d, r) for d, r in window if r.main_thread and (r.model, r.effort) == chosen]
    positive = Counter(
        r.reasoning for _, r in selected if r.reasoning is not None and r.reasoning > 0
    )
    reference = min(positive, key=lambda count: (-positive[count], count)) if positive else None
    known: dict[date, list[int]] = defaultdict(list)
    for day, response in selected:
        if response.reasoning is not None:
            known[day].append(response.reasoning)
    edit_counts: dict[date, list[bool]] = defaultdict(list)
    try:
        for edit in result.edits:
            if (
                edit.in_project
                and edit.main_thread
                and (edit.model, edit.effort) == chosen
                and edit.when.tzinfo is not None
                and edit.when <= now
            ):
                day = edit.when.astimezone(zone).date()
                if first <= day <= window_end:
                    edit_counts[day].append(edit.failed)
    except (OverflowError, ValueError):
        raise UsageError("calendar_range") from None
    values: dict[MeasureId, list[DayValue]] = {
        "reasoning_tokens": [],
        "no_reasoning_share": [],
        "edit_failure_share" if result.tool == "claude-code" else "repeated_value_share": [],
    }
    for day, numbers in sorted(known.items()):
        positives = sorted(number for number in numbers if number > 0)
        n = len(positives)
        if len(numbers) >= 20:
            values["no_reasoning_share"].append(
                DayValue(
                    day=day.isoformat(),
                    count=len(numbers),
                    value=fraction_str(Fraction(numbers.count(0), len(numbers))),
                )
            )
            if n >= 10:
                value = Fraction(positives[(n - 1) // 2] + positives[n // 2], 2)
                values["reasoning_tokens"].append(
                    DayValue(day=day.isoformat(), count=n, value=fraction_str(value))
                )
                if result.tool == "codex":
                    values["repeated_value_share"].append(
                        DayValue(
                            day=day.isoformat(),
                            count=n,
                            value=fraction_str(Fraction(sum(v == reference for v in positives), n)),
                        )
                    )
    if result.tool == "claude-code":
        for day, failures in sorted(edit_counts.items()):
            if len(failures) >= 10:
                values["edit_failure_share"].append(
                    DayValue(
                        day=day.isoformat(),
                        count=len(failures),
                        value=fraction_str(Fraction(sum(failures), len(failures))),
                    )
                )
    split_text = split.isoformat()
    return ToolTable(
        result.tool,
        models[chosen[0]],
        efforts[chosen[1]],
        len(counts) - 1,
        split_text,
        Period(first_day=first.isoformat(), last_day=last.isoformat()),
        Period(first_day=split_text, last_day=newest.isoformat()) if split <= newest else None,
        tuple(
            MeasureTable(
                key,
                tuple(d for d in days if d.day < split_text),
                tuple(d for d in days if d.day >= split_text),
            )
            for key, days in values.items()
        ),
        _context([r for d, r in window if d < split], [r for d, r in window if d >= split]),
        reference,
    )
