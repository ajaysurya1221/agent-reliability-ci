"""Readable snapshots and independent checks against the design's fixed texts."""

import re
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest

from arci import __version__
from arci.logs import report
from arci.logs.claude_code import read as read_claude
from arci.logs.codex import read as read_codex
from arci.logs.decide import decide_tool, error_tool, exit_code
from arci.logs.discover import claude_files, codex_files
from arci.logs.example import load
from arci.logs.html import render_html
from arci.logs.measures import build
from arci.logs.records import ReaderCounters
from arci.logs.schema import LogsDecision, ToolDecision, seal
from tests.unit.logs.test_measures import sample, table

SNAPSHOTS = Path(__file__).parent / "snapshots"
RECORD = Path(__file__).resolve().parents[3] / "docs/design/0016-logs.md"


def normalize_version(text: str) -> str:
    return re.sub(r"(realornoise )[^ <]+( ·)", r"\1<version>\2", text, count=1)


def record(
    tools: tuple[ToolDecision, ...], *, example: bool = False, offset: int = 330
) -> LogsDecision:
    return seal(
        LogsDecision(
            arci_version=__version__,
            example=example,
            utc_offset_minutes=offset,
            project_filtered=False,
            tools=tools,
            exit_code=exit_code(tools),
        )
    )


def example_record() -> LogsDecision:
    claude, codex, now = load()
    tools = []
    for reader, paths in ((read_claude, claude_files(claude)), (read_codex, codex_files(codex))):
        result = reader(paths, project=None, now=now)
        tools.append(decide_tool(build(result, utc_offset=timedelta(), now=now), result.counters))
    return record(tuple(tools), example=True, offset=0)


def cases() -> dict[str, LogsDecision]:
    data = sample()
    good = decide_tool(table(data), data.counters)
    few = replace(data, responses=data.responses[:20], edits=())
    incomplete = sample(edits=False)
    streak = replace(
        data,
        responses=tuple(
            replace(r, reasoning=10 if r.when.month == 4 and r.when.day < 26 else 20)
            for r in data.responses
        ),
    )
    notices = ReaderCounters(
        files_unread_compressed=2, lines_lacking_field=3, records_in_future=4, files_unreadable=1
    )
    empty = decide_tool(table(data, model="model-99"), notices)
    return {
        "example": example_record(),
        "no_drop": record((good,)),
        "not_enough_evidence": record((decide_tool(table(incomplete), incomplete.counters),)),
        "too_few_days": record((decide_tool(table(few), few.counters),)),
        "streaky_days": record((decide_tool(table(streak), streak.counters),)),
        "no_usable_setting": record((empty,)),
        "error_beside_result": record((good, error_tool("codex", "read_error", ReaderCounters()))),
        "error_notices": record((error_tool("codex", "read_error", notices),)),
        "both_no_logs": record(
            tuple(error_tool(t, "no_logs", ReaderCounters()) for t in ("claude-code", "codex"))
        ),
        "format_not_recognised": record(
            (error_tool("codex", "format_not_recognised", ReaderCounters()),)
        ),
        "utc": record((good,), offset=0),
    }


@pytest.mark.parametrize("name", list(cases()))
@pytest.mark.parametrize("extension", ["txt", "md"])
def test_snapshot(name: str, extension: str) -> None:
    render = report.render_text if extension == "txt" else report.render_markdown
    actual = render(cases()[name])
    assert normalize_version(actual) == normalize_version(
        (SNAPSHOTS / f"{name}.{extension}").read_text(encoding="utf-8")
    )
    if extension == "txt":
        assert max(map(len, actual.splitlines())) <= 100
    assert all(char == "·" or char == "\n" or 32 <= ord(char) <= 126 for char in actual)


def test_every_fixed_text_matches_record() -> None:
    source = RECORD.read_text(encoding="utf-8")
    section = source.split("## Fixed texts\n", 1)[1].split("## Command line", 1)[0]
    fixed = re.findall(r"`([^`]+)`", section)
    constants = [
        report.F1,
        report.F2.replace("{offset}", "{+hh:mm}"),
        report.F3_BEFORE,
        report.F3_AFTER,
        report.F3_EMPTY,
        *report.F4.values(),
        report.EXIT,
        *report.F5.values(),
        report.F5_DIRECTORY,
        report.DUPLICATE_OUTPUT,
        report.INTERNAL_ERROR,
        *report.DEFAULTS.values(),
        *report.FLAGS.values(),
        report.SINCE_DATE,
        report.SINCE_EARLY,
        report.WRITE_ERROR,
        report.CALENDAR_RANGE,
        *report.F6_HEADERS,
        *report.F6_NAMES.values(),
        *report.F6_FINDINGS.values(),
        report.F6_NOT_USED,
        report.F7_HEADER,
        report.F7,
        report.F8,
        report.F9,
        report.F9_NEXT,
        *report.F10.splitlines(),
        report.F11.replace("{digest}", "{12 hex}"),
        report.F12,
        report.F13,
        report.F14,
        report.F15,
        report.F16,
        report.F17,
        *report.MD_CLOSING.values(),
        report.MD_LIMITS.replace("{digest}", "{12 hex}"),
    ]

    def normal(value: str) -> str:
        return " ".join(value.split())

    for value in constants:
        assert normal(value) in [normal(text) for text in fixed], value
    # All prose literals are accounted for, not just a chosen subset.
    ignored = {
        "{}",
        "ERROR",
        "K",
        "k",
        "p_streak > 1/10",
        "real_drop",
        "no_drop",
        "not_enough_evidence",
        "too_few_days",
        "streaky_days",
        "no_usable_setting",
        "no_logs",
        "read_error",
        "format_not_recognised",
        "{default}",
        "{flag}",
        "{k}",
        "files_read",
        "files_outside_project",
        "responses",
        "--since",
    }
    for value in fixed:
        assert value in ignored or normal(value) in [normal(text) for text in constants], value
    assert len(constants) == len(set(constants))


def test_rounding_is_exact_and_signed() -> None:
    data = sample()
    data = replace(
        data,
        responses=tuple(
            replace(r, reasoning=(2 if r.when.month == 4 else 1) + i % 2)
            for i, r in enumerate(data.responses)
        ),
    )
    decision = record((decide_tool(table(data), data.counters),))
    text = report.render_text(decision)
    row = next(line for line in text.splitlines() if line.startswith("reasoning tokens"))
    assert "3 (10)" in row and "2 (5)" in row and "-40%" in row
    assert "0.0 pts" in text


def test_renderers_use_record_only() -> None:
    decision = example_record()
    restored = LogsDecision.model_validate_json(decision.model_dump_json())
    assert report.render_text(restored) == report.render_text(decision)
    assert report.render_markdown(restored) == report.render_markdown(decision)


def test_streak_notice_requires_tested_measure() -> None:
    assert "Streak check:" not in report.render_text(cases()["too_few_days"])


def test_fixed_sentence_wraps_at_last_space() -> None:
    sentence = report.F5["real_drop"]
    text = report.render_text(example_record())
    lines = text.splitlines()
    start = lines.index("RESULT: REAL DROP") + 1
    first, rest = lines[start : start + 2]
    assert first == sentence[: sentence.rfind(" ", 0, 101)]
    assert first + " " + rest == sentence


@pytest.mark.parametrize("finding", ["real_drop", "no_drop", "cannot_tell", "too_few_days"])
def test_streak_veto_rows_keep_stored_findings(finding: str) -> None:
    data = sample()
    rows = tuple(
        replace(r, reasoning=10 if r.when.month == 4 and r.when.day < 26 else 20)
        for r in data.responses
    )
    source = table(replace(data, responses=rows))
    share = source.measures[1]
    before_days = tuple(
        d.model_copy(update={"value": f"{i % 2 if finding == 'cannot_tell' else 0}/1"})
        for i, d in enumerate(share.before_days)
    )
    after_days = tuple(
        d.model_copy(
            update={
                "value": f"{i % 2 if finding == 'cannot_tell' else int(finding == 'real_drop')}/1"
            }
        )
        for i, d in enumerate(share.after_days)
    )
    share = replace(
        share,
        before_days=before_days,
        after_days=after_days[:4] if finding == "too_few_days" else after_days,
    )
    source = replace(source, measures=(source.measures[0], share, source.measures[2]))
    tool = decide_tool(source, data.counters)
    assert tool.measures[1].finding == finding
    decision = record((tool,))
    before = decision.model_dump_json()
    for render in (report.render_text, report.render_markdown, render_html):
        output = render(decision)
        assert output.count("not used") == (1 if finding == "too_few_days" else 2)
        assert "days come in streaks" in output
        if finding == "too_few_days":
            assert "too few days" in output
    assert decision.model_dump_json() == before
