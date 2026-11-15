"""Reduce private reader identities to a deterministic, exact daily table."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from fractions import Fraction
from typing import Literal

from . import kept
from .records import ReadResult, Response, Tool, version_order
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
    unconfigured_responses: tuple[Response, ...] = field(default=(), kw_only=True)


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
    first_response_day: str | None = None
    response_days_before: int = 0
    response_days_after: int = 0
    kept_days_before: int = 0
    kept_days_after: int = 0
    kept_rows_other_offset: int = 0
    settings_not_kept: int = 0
    days_not_kept: int = 0
    newest: date | None = None
    write_rows: tuple[kept.KeptRow, ...] = ()


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


def _context(
    before: list[Response], after: list[Response], versions: tuple[str | None, ...]
) -> ContextCounts:
    vb, va = {r.version for r in before}, {r.version for r in after}
    names = [versions[i] for i in va if 0 <= i < len(versions) and versions[i] is not None]
    shown = tuple(version_order(name for name in names if name is not None)[:3])
    return ContextCounts(
        client_versions_after_shown=shown,
        client_versions_after_more=len(va) - len(shown),
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
    kept_rows: tuple[kept.KeptRow, ...] = (),
    keep: bool = False,
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
    try:
        logs = kept.from_logs(result, utc_offset=utc_offset, now=now)
        minutes = utc_offset // timedelta(minutes=1)
        rows = kept.use(
            logs,
            kept_rows,
            result=result,
            offset=minutes,
            first=first,
            newest=newest,
            window_end=max(last, newest),
        )
        written, settings_not_kept, days_not_kept = (
            kept.for_write(logs, result, offset=minutes, newest=newest) if keep else ((), 0, 0)
        )
    except (OverflowError, ValueError):
        raise UsageError("calendar_range") from None
    other_offset = sum(
        row.tool == result.tool and row.utc_offset_minutes != minutes for row in kept_rows
    )
    counts: Counter[tuple[int, int]] = Counter()
    after_counts: Counter[tuple[int, int]] = Counter()
    for (m, e, day), row in rows.items():
        if row.responses:
            counts[m, e] += row.responses
            if day >= split:
                after_counts[m, e] += row.responses
    models = _names(result.models, result.model_order, "model")
    efforts = _names(result.efforts, result.effort_order, "effort")
    eligible = [
        setting
        for setting in counts
        if (model is None or models[setting[0]] == model)
        and (effort is None or efforts[setting[1]] == effort)
    ]
    if not eligible:
        return ToolTable(
            result.tool,
            None,
            None,
            len(counts),
            split.isoformat(),
            None,
            None,
            (),
            None,
            newest=newest,
            write_rows=written,
            kept_rows_other_offset=other_offset,
            settings_not_kept=settings_not_kept,
            days_not_kept=days_not_kept,
        )
    model_ranks = {value: i for i, value in enumerate(result.model_order)}
    effort_ranks = {value: i for i, value in enumerate(result.effort_order)}
    scores = after_counts if any(after_counts[setting] for setting in eligible) else counts
    chosen = min(
        eligible,
        key=lambda setting: (-scores[setting], model_ranks[setting[0]], effort_ranks[setting[1]]),
    )
    selected = {day: row for (m, e, day), row in rows.items() if (m, e) == chosen}
    positive: Counter[int] = Counter()
    for row in selected.values():
        positive.update(
            {value: frequency for value, frequency in row.reasoning.items() if value > 0}
        )
    reference = min(positive, key=lambda count: (-positive[count], count)) if positive else None
    values: dict[MeasureId, list[DayValue]] = {
        "reasoning_tokens": [],
        "no_reasoning_share": [],
        "edit_failure_share" if result.tool == "claude-code" else "repeated_value_share": [],
    }
    for day, row in sorted(selected.items()):
        known = sum(row.reasoning.values())
        n = known - row.reasoning[0]

        def add(
            key: MeasureId,
            count: int,
            value: Fraction,
            *,
            day: date = day,
            row: kept.DailyRow = row,
        ) -> None:
            values[key].append(
                DayValue(
                    day=day.isoformat(), count=count, value=fraction_str(value), source=row.source
                )
            )

        if known >= 20:
            add("no_reasoning_share", known, Fraction(row.reasoning[0], known))
            if n >= 10:
                middle: list[int] = []
                cumulative = 0
                for number, frequency in sorted(row.reasoning.items()):
                    if number <= 0:
                        continue
                    for index in ((n - 1) // 2, n // 2):
                        if cumulative <= index < cumulative + frequency:
                            middle.append(number)
                    cumulative += frequency
                add("reasoning_tokens", n, Fraction(sum(middle), 2))
                if result.tool == "codex":
                    add(
                        "repeated_value_share",
                        n,
                        Fraction(row.reasoning[reference] if reference is not None else 0, n),
                    )
        if result.tool == "claude-code" and row.edits >= 10:
            add("edit_failure_share", row.edits, Fraction(row.edits_failed, row.edits))
    split_text = split.isoformat()
    context_responses = list(responses)
    if isinstance(result, WindowReadResult):
        context_responses.extend(
            (r.when.astimezone(zone).date(), r)
            for r in result.unconfigured_responses
            if r.in_project and r.when.tzinfo is not None and r.when <= now
        )
    window = [(d, r) for d, r in context_responses if first <= d <= max(last, newest)]
    response_days = [day for day, row in selected.items() if row.responses]
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
        _context(
            [r for d, r in window if d < split],
            [r for d, r in window if d >= split],
            result.versions,
        ),
        reference,
        first_response_day=min(response_days).isoformat(),
        response_days_before=sum(day < split for day in response_days),
        response_days_after=sum(day >= split for day in response_days),
        kept_days_before=sum(day < split and row.source == "kept" for day, row in selected.items()),
        kept_days_after=sum(day >= split and row.source == "kept" for day, row in selected.items()),
        newest=newest,
        write_rows=written,
        kept_rows_other_offset=other_offset,
        settings_not_kept=settings_not_kept,
        days_not_kept=days_not_kept,
    )
