"""Pure, privacy-bounded renderers for sealed session-log decisions."""

from __future__ import annotations

import textwrap
from collections.abc import Collection
from fractions import Fraction

from arci.outcome_report import escape_terminal

from .records import Tool
from .schema import LogsDecision, MeasureDecision, ToolDecision

__all__ = [
    "context_text",
    "format_number",
    "format_scope",
    "measure_row",
    "notices",
    "reason_text",
    "render_markdown",
    "render_text",
    "wrap_text",
]

F1 = (
    "realornoise {version} · reads local session logs · sends nothing · writes nothing unless asked"
)
F2 = "{Tool} · {model} · effort {effort} · main thread · days at UTC{offset}"
F3_BEFORE = "before  {first} to {last}"
F3_AFTER = "after   {first} to {last}   split {s}"
F3_EMPTY = "after   no days   split {s}"
F4 = {
    "REAL_DROP": "RESULT: REAL DROP",
    "NO_DROP": "RESULT: NO DROP",
    "CANNOT_TELL": "RESULT: CANNOT TELL",
    "ERROR": "RESULT: ERROR",
}
EXIT = "exit {code}"
F5 = {
    "real_drop": (
        "In at least one recorded measure, the days after the split moved toward "
        "worse by more than a chance ordering of your days explains."
    ),
    "no_drop": (
        "No recorded measure moved toward worse by its margin or more. This does "
        "not say anything improved."
    ),
    "not_enough_evidence": "The days are too few or too variable to tell a shift from noise.",
    "too_few_days": "Too few usable days for every measure (5 needed after the split, 10 before).",
    "streaky_days": (
        "Your earlier days come in streaks in a recorded measure, so this "
        "comparison cannot tell a streak from a drop."
    ),
    "no_usable_setting": "No model and effort setting has a response in the window.",
    "no_logs": (
        "No session logs found for {Tool}. Looked under {default}. Use {flag} DIR, "
        "or try: realornoise --example"
    ),
    "read_error": "Session log files could not be read.",
    "format_not_recognised": (
        "Log files were found, but this version could not recover a response from them."
    ),
}
F5_DIRECTORY = (
    "No session logs found for {Tool} under the directory given with {flag}. "
    "Or try: realornoise --example"
)
DUPLICATE_OUTPUT = "Two output options name the same file."
SINCE_DATE = "--since needs a date as YYYY-MM-DD."
SINCE_EARLY = "--since can be at most 83 days before the newest day in the logs."
WRITE_ERROR = "Requested output could not be written."
CALENDAR_RANGE = "Comparison dates are outside the supported calendar range."
USAGE_ERROR = "Usage error. Run: realornoise --help"
INTERNAL_ERROR = "Internal error."
F6_HEADERS = ("measure, median day", "before (days)", "after (days)", "change", "finding")
F6_NAMES = {
    "reasoning_tokens": "reasoning tokens per response",
    "no_reasoning_share": "responses with no reasoning",
    "edit_failure_share": "file edits that failed",
    "repeated_value_share": "reasoning at one repeated value",
}
F6_FINDINGS = {
    "real_drop": "real drop",
    "no_drop": "no drop (margin {margin})",
    "cannot_tell": "cannot tell",
    "too_few_days": "too few days",
    "streaky": "days come in streaks",
}
F7_HEADER = "Context counts; differences between the periods are not tested:"
F7 = (
    "client versions {a} before, {b} after, {c} in both · working directories "
    "{d} before, {e} after · sub-agent share {f}% -> {g}%"
)
F8 = "Streak check: {k} of {K} tested measures were not flagged."
F9 = "Compressed Codex files not read (Python 3.14 is needed): {k}. The result uses the rest."
F9_ERROR = "Compressed Codex files not read (Python 3.14 is needed): {k}."
F9_NEXT = "To read them: uvx --python 3.14 realornoise"
F10 = (
    "This shows what your logs recorded. It does not establish answer quality, "
    "a cause, or a change\n"
    "to the model: your tasks, prompts, projects or client version may have changed.\n"
    "For each tool above and one comparison: if nothing shifted, REAL DROP "
    "appears at most 2.5% of the\n"
    "time; if a measure moved toward worse by its margin or more, NO DROP "
    "appears at most 2.5% of the\n"
    "time. Both hold only if: (1) the days in this window are interchangeable "
    "when nothing changes;\n"
    "(2) any date, model, effort or project you gave was not chosen from these logs; (3) a change\n"
    "moves every day alike, by an amount the measure can take; (4) a change leaves the same days,\n"
    "setting, reference value and earlier-day values in use. None of these is "
    "checked, and the streak\n"
    "check does not prove them. Running this again and again until a result "
    "appears is not covered.\n"
    "Exact statement: docs/STATISTICS_LOGS.md in the repository."
)
F11 = "method arci-logs/1 · exact rank tests · no random numbers · day-table digest {digest}"
F12 = (
    "Share: --markdown FILE · --html FILE · --json FILE      Stronger evidence: "
    "arci verdict, arci run"
)
F13 = "Example data, generated. Not anyone's logs."
F14 = "Other model or effort settings, not compared: {k}."
F15 = "Lines that lacked a needed field, left out: {k}."
F16 = "Records stamped later than now, left out: {k}."
F17 = "Files that could not be read: {k}. The result uses the rest."
F17_ERROR = "Files that could not be read: {k}."
MD_CLOSING = {
    "REAL_DROP": (
        "One person's logs. Evidence of movement toward worse in a recorded "
        "measure; this establishes no cause and says nothing about answer quality."
    ),
    "NO_DROP": (
        "One person's logs. No recorded measure moved toward worse by its margin; "
        "this does not say anything improved."
    ),
    "CANNOT_TELL": "One person's logs. Not enough to tell a shift from noise.",
}
MD_LIMITS = (
    "Wrong REAL DROP and wrong NO DROP are each at most 2.5% for "
    "this tool and one comparison, only under unchecked assumptions (days in the window "
    "interchangeable; no date, model, effort or project chosen from these logs; "
    "a uniform shift the "
    "measure can take; the same days, setting, reference value and earlier-day values in use). "
    "Repeated checking until a result appears is not covered. arci-logs/1, digest {digest}. "
    "Yours: uvx realornoise"
)
TOOL_NAMES = {"claude-code": "Claude Code", "codex": "Codex"}
DEFAULTS = {
    "claude-code": "~/.claude/projects (or CLAUDE_CONFIG_DIR)",
    "codex": "~/.codex (or CODEX_HOME)",
}
FLAGS = {"claude-code": "--claude-dir", "codex": "--codex-dir"}
MARGINS = {"1/4": "25%", "1/10": "10 pts", "3/100": "3 pts"}


def wrap_text(value: str) -> str:
    return "\n".join(
        textwrap.fill(line, width=100, break_long_words=True, break_on_hyphens=False)
        if len(line) > 100
        else line
        for line in value.splitlines()
    )


def format_number(value: Fraction, decimals: int = 0, *, signed: bool = False) -> str:
    scale = 10**decimals
    number = (abs(value).numerator * scale * 2 + abs(value).denominator) // (
        2 * abs(value).denominator
    )
    sign = "-" if value < 0 and number else "+" if signed and number else ""
    digits = str(number) if not decimals else f"{number // scale}.{number % scale:0{decimals}d}"
    return sign + digits


def _percent(value: str | None) -> str:
    return "-" if value is None else format_number(Fraction(value) * 100, 1)


def format_scope(tool: ToolDecision, decision: LogsDecision) -> str:
    minutes = decision.utc_offset_minutes
    offset = f"{'+' if minutes >= 0 else '-'}{abs(minutes) // 60:02}:{abs(minutes) % 60:02}"
    return F2.format(
        Tool=TOOL_NAMES[tool.tool],
        model=escape_terminal(tool.model or "-"),
        effort=escape_terminal(tool.effort or "-"),
        offset=offset,
    )


def reason_text(tool: ToolDecision, *, directory_given: bool = False) -> str:
    template = F5_DIRECTORY if tool.reason == "no_logs" and directory_given else F5[tool.reason]
    return template.format(
        Tool=TOOL_NAMES[tool.tool], default=DEFAULTS[tool.tool], flag=FLAGS[tool.tool]
    )


F6_NOT_USED = "not used"


def measure_row(measure: MeasureDecision, *, streaky_days: bool = False) -> tuple[str, ...]:
    tokens = measure.id == "reasoning_tokens"
    cells: list[str] = [F6_NAMES[measure.id]]
    for value, days in (
        (measure.median_before, measure.before_days),
        (measure.median_after, measure.after_days),
    ):
        rendered = (
            "-"
            if value is None
            else (format_number(Fraction(value)) if tokens else _percent(value) + "%")
        )
        cells.append(f"{rendered} ({len(days)})")
    change = "-"
    if measure.median_before is not None and measure.median_after is not None:
        before, after = Fraction(measure.median_before), Fraction(measure.median_after)
        if tokens and before:
            change = format_number((after - before) * 100 / before, signed=True) + "%"
        elif not tokens:
            change = format_number((after - before) * 100, 1, signed=True) + " pts"
    finding = (
        F6_NOT_USED
        if streaky_days and measure.finding not in {"streaky", "too_few_days"}
        else F6_FINDINGS[measure.finding].format(margin=MARGINS[measure.margin])
    )
    cells.extend((change, finding))
    return tuple(cells)


def _table(tool: ToolDecision, *, markdown: bool = False) -> str:
    rows = [
        F6_HEADERS,
        *(
            measure_row(measure, streaky_days=tool.reason == "streaky_days")
            for measure in tool.measures
        ),
    ]
    widths = [max(len(row[i]) for row in rows) for i in range(5)]
    if markdown:
        # Omit optional edge pipes; ordinary rows fit with aligned columns.
        def line(row: tuple[str, ...]) -> str:
            return " | ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)).rstrip()

        return "\n".join(
            [
                line(rows[0]),
                " | ".join("-" * width for width in widths),
                *(line(row) for row in rows[1:]),
            ]
        )
    # Wrap individual cells when large counts would exceed the terminal's line budget.
    while sum(widths) + 4 > 100:
        longest = max(range(5), key=lambda i: widths[i])
        widths[longest] -= 1
    lines: list[str] = []
    for row in rows:
        wrapped = [
            textwrap.wrap(cell, width=widths[i], break_on_hyphens=False) or [""]
            for i, cell in enumerate(row)
        ]
        for j in range(max(map(len, wrapped))):
            lines.append(
                " ".join(
                    (cell[j] if j < len(cell) else "").ljust(widths[i])
                    for i, cell in enumerate(wrapped)
                ).rstrip()
            )
    return "\n".join(lines)


def context_text(tool: ToolDecision) -> str:
    c = tool.context
    assert c is not None
    return F7.format(
        a=c.client_versions_before,
        b=c.client_versions_after,
        c=c.client_versions_both,
        d=c.workdirs_before,
        e=c.workdirs_after,
        f=_percent(c.subagent_share_before),
        g=_percent(c.subagent_share_after),
    ).replace("-%", "-")


def notices(tool: ToolDecision) -> list[str]:
    c = tool.counters
    if tool.result == "ERROR":
        return [
            template.format(k=count)
            for template, count in (
                (F9_ERROR, c.files_unread_compressed),
                (F9_NEXT, c.files_unread_compressed),
                (F17_ERROR, c.files_unreadable),
            )
            if count
        ]
    return [
        template.format(k=count)
        for template, count in (
            (F14, tool.other_settings),
            (F9, c.files_unread_compressed),
            (F9_NEXT, c.files_unread_compressed),
            (F15, c.lines_lacking_field),
            (F16, c.records_in_future),
            (F17, c.files_unreadable),
        )
        if count
    ]


def render_text(decision: LogsDecision, *, directory_tools: Collection[Tool] = ()) -> str:
    header = F1.format(version=escape_terminal(decision.arci_version))
    groups = [header + ("\n" + F13 if decision.example else "")]
    for tool in decision.tools:
        result = (
            F4[tool.result] + "\n" + reason_text(tool, directory_given=tool.tool in directory_tools)
        )
        if tool.model is None:
            groups.append(
                "\n".join(
                    [
                        TOOL_NAMES[tool.tool],
                        result,
                        *notices(tool),
                    ]
                )
            )
            continue
        assert tool.before is not None
        periods = [F3_BEFORE.format(first=tool.before.first_day, last=tool.before.last_day)]
        periods.append(
            F3_AFTER.format(first=tool.after.first_day, last=tool.after.last_day, s=tool.split_date)
            if tool.after
            else F3_EMPTY.format(s=tool.split_date)
        )
        groups.extend(["\n".join([format_scope(tool, decision), *periods]), result, _table(tool)])
        tested = [m for m in tool.measures if m.p_streak is not None]
        groups.append(
            "\n".join(
                [
                    F7_HEADER,
                    context_text(tool),
                    *(
                        [
                            F8.format(
                                k=sum(
                                    Fraction(m.p_streak or "0") > Fraction(1, 10) for m in tested
                                ),
                                K=len(tested),
                            )
                        ]
                        if tested
                        else []
                    ),
                    *notices(tool),
                    F11.format(digest=(tool.day_table_sha256 or "")[:12]),
                ]
            )
        )
    if any(tool.result != "ERROR" for tool in decision.tools):
        groups.append(F10)
    groups.append(F12 + "\n" + EXIT.format(code=decision.exit_code))
    return wrap_text("\n\n".join(groups)) + "\n"


def render_markdown(decision: LogsDecision, *, directory_tools: Collection[Tool] = ()) -> str:
    blocks: list[str] = [F13] if decision.example else []
    for tool in decision.tools:
        if tool.model is None:
            block = "\n".join(
                [
                    TOOL_NAMES[tool.tool],
                    tool.result.replace("_", " "),
                    reason_text(tool, directory_given=tool.tool in directory_tools),
                ]
            )
            block += "\n" + "\n".join(
                [*notices(tool), *([" ".join(F10.splitlines())] if tool.result != "ERROR" else [])]
            )
            block = block.rstrip()
        else:
            block = "\n\n".join(
                [
                    f"**{format_scope(tool, decision)} · {tool.result.replace('_', ' ')}**",
                    _table(tool, markdown=True),
                    f"split {tool.split_date} · {context_text(tool)}",
                    *(notices(tool)),
                    MD_CLOSING[tool.result],
                    MD_LIMITS.format(digest=(tool.day_table_sha256 or "")[:12]),
                ]
            )
        blocks.append(block)
    return "\n\n".join(blocks) + "\n"
