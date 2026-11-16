"""Self-contained HTML and exact-coordinate daily strip charts from the record only."""

from __future__ import annotations

from collections.abc import Collection
from datetime import date
from fractions import Fraction

from arci.html_base import _CSS, _heading, _p, _table, _text

from . import report
from .records import Tool
from .report import context_text, format_number, format_scope, measure_row, notices, reason_text
from .schema import LogsDecision, MeasureDecision, ToolDecision


def _chart(measure: MeasureDecision, split_date: str) -> str:
    days = (*measure.before_days, *measure.after_days)
    if not days:
        return ""
    split = date.fromisoformat(split_date).toordinal()
    first = min(date.fromisoformat(days[0].day).toordinal(), split) - 1
    last = max(date.fromisoformat(days[-1].day).toordinal(), split) + 1
    low = min(Fraction(day.value) for day in days)
    high = max(Fraction(day.value) for day in days)

    def x(ordinal: int) -> str:
        return format_number(70 + Fraction(ordinal - first, last - first) * 620, 3)

    def y(value: str) -> str:
        position = Fraction(1, 2) if high == low else (Fraction(value) - low) / (high - low)
        return format_number(190 - position * 150, 3)

    name = report.F6_NAMES[measure.id]
    parts = [
        f'<figure><svg viewBox="0 0 760 240" role="img" aria-label="{_text(name)}">',
        f"<title>{_text(name)}</title>",
        f'<line class="split" x1="{x(split)}" x2="{x(split)}" y1="25" y2="200" '
        'stroke="currentColor" stroke-dasharray="4 4">'
        f"<title>split {_text(split_date)}</title></line>",
    ]
    for period, median, start, end in (
        ("before", measure.median_before, first, split),
        ("after", measure.median_after, split, last),
    ):
        if median is not None:
            parts.append(
                f'<line class="median" x1="{x(start)}" x2="{x(end)}" '
                f'y1="{y(median)}" y2="{y(median)}" stroke="currentColor">'
                f"<title>{period} median {_text(median)}</title></line>"
            )
    for day in days:
        fill = "none" if day.source == "kept" else "currentColor"
        parts.append(
            f'<circle cx="{x(date.fromisoformat(day.day).toordinal())}" '
            f'cy="{y(day.value)}" r="3" fill="{fill}" stroke="currentColor">'
            f"<title>{_text(day.day)} · value {_text(day.value)} · count {day.count}"
            f" · source {day.source}</title>"
            "</circle>"
        )
    parts.extend(
        [
            f'<text x="70" y="225">{_text(days[0].day)}</text>',
            f'<text x="690" y="225" text-anchor="end">{_text(days[-1].day)}</text>',
            f'<text x="5" y="40">{_text(str(high))}</text>',
            f'<text x="5" y="190">{_text(str(low))}</text>',
            "</svg><figcaption>"
            + _text(name)
            + "; one dot per usable day; dashed line: split; horizontal lines: period medians."
            "</figcaption></figure>",
        ]
    )
    return "".join(parts)


def _tool(tool: ToolDecision, decision: LogsDecision, directory_tools: Collection[Tool]) -> str:
    parts = ["<section>", _heading(report.TOOL_NAMES[tool.tool])]
    if tool.model is not None:
        assert tool.before is not None
        parts.extend(
            [
                _p(format_scope(tool, decision)),
                _p(report.F3_BEFORE.format(first=tool.before.first_day, last=tool.before.last_day)),
                _p(
                    report.F3_AFTER.format(
                        first=tool.after.first_day, last=tool.after.last_day, s=tool.split_date
                    )
                    if tool.after
                    else report.F3_EMPTY.format(s=tool.split_date)
                ),
            ]
        )
    parts.extend(
        [
            f'<p class="verdict">{_text(report.F4[tool.result])}</p>',
            _p(
                " ".join(
                    reason_text(tool, directory_given=tool.tool in directory_tools).splitlines()
                )
            ),
        ]
    )
    if tool.model is not None:
        parts.extend(
            [
                *(_p(" ".join(line.splitlines())) for line in report.short_history(tool)),
                _table(
                    "Recorded measures",
                    report.F6_HEADERS,
                    [
                        measure_row(m, streaky_days=tool.reason == "streaky_days")
                        for m in tool.measures
                    ],
                ),
                _p(report.F7_HEADER),
                _p(context_text(tool)),
                *(_p(line) for line in report.client_versions(tool)),
            ]
        )
        tested = [m for m in tool.measures if m.p_streak is not None]
        if tested:
            parts.append(
                _p(
                    report.F8.format(
                        k=sum(Fraction(m.p_streak or "0") > Fraction(1, 10) for m in tested),
                        K=len(tested),
                    )
                )
            )
    parts.extend(_p(line) for line in report.kept_days(tool, decision))
    parts.extend(_p(notice) for notice in notices(tool))
    if tool.model is not None:
        assert tool.split_date is not None and tool.day_table_sha256 is not None
        parts.extend(_chart(m, tool.split_date) for m in tool.measures)
        parts.append(_p(report.F11.format(digest=tool.day_table_sha256[:12])))
    return "".join([*parts, "</section>"])


def render_html(decision: LogsDecision, *, directory_tools: Collection[Tool] = ()) -> str:
    """Render numbers and fixed copy without reading logs or other external state."""
    parts = [
        '<!doctype html><html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>realornoise · local session logs</title><style>",
        _CSS,
        "figure { margin: 1.5em 0; }\n",
        "</style></head><body><main><h1>realornoise</h1>",
        _p(report.F1.format(version=decision.arci_version)),
    ]
    if decision.example:
        parts.append(_p(report.F13))
    if decision.kept_table == "unreadable":
        parts.append(_p(report.F24))
    parts.extend(_tool(tool, decision, directory_tools) for tool in decision.tools)
    if any(tool.result != "ERROR" for tool in decision.tools):
        parts.append(_p(" ".join(report.limits_text().splitlines())))
    parts.extend([_p(report.F12), _p(report.EXIT.format(code=decision.exit_code))])
    return "".join([*parts, "</main></body></html>\n"])
