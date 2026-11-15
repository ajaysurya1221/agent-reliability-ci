"""Synthetic day tables: selection, calendar boundaries and exact measures."""

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from fractions import Fraction

import pytest

from arci.logs.measures import ToolTable, UsageError, build, fraction_str, parse_fraction
from arci.logs.records import EditResult, ReaderCounters, ReadResult, Response, Tool

NOW = datetime(2026, 6, 1, tzinfo=UTC)
SPLIT = date(2026, 5, 1)


def sample(
    tool: Tool = "claude-code", *, before: int = 100, after: int = 100, edits: bool = True
) -> ReadResult:
    responses: list[Response] = []
    results: list[EditResult] = []
    for day in range(-10, 5):
        when = datetime(2026, 5, 1, 12, tzinfo=UTC) + timedelta(days=day)
        for i in range(20):
            responses.append(
                Response(tool, when, 0, 0, True, before if day < 0 else after, i % 2, i % 3, True)
            )
        if edits:
            results.extend(EditResult(tool, when, 0, 0, True, False, True) for _ in range(10))
    return ReadResult(
        tool,
        tuple(responses),
        tuple(results),
        ("gpt-5.3",),
        ("high",),
        (0,),
        (0,),
        ReaderCounters(),
    )


def table(result: ReadResult, *, model: str | None = None, effort: str | None = None) -> ToolTable:
    return build(result, utc_offset=timedelta(), now=NOW, since=SPLIT, model=model, effort=effort)


def test_exact_rationals_and_medians() -> None:
    assert fraction_str(Fraction(15, 4)) == "15/4"
    assert parse_fraction("15/4") == Fraction(15, 4)
    for value in ("0", "2/4", "-0/1", "1/-2", "01/2", "1/0", "1.5/2"):
        with pytest.raises(ValueError):
            parse_fraction(value)
    result = sample()
    result = replace(
        result,
        responses=tuple(replace(r, reasoning=5 + i % 2) for i, r in enumerate(result.responses)),
    )
    actual = table(result)
    assert actual.measures[0].before_days[0].value == "11/2"
    assert actual.measures[0].before_days[0].count == 20


def test_zero_and_unknown_counts() -> None:
    actual = table(sample(after=0))
    assert actual.measures[0].after_days == ()
    assert actual.measures[1].after_days[0].value == "1/1"
    result = sample()
    result = replace(result, responses=tuple(replace(r, reasoning=None) for r in result.responses))
    assert all(not m.before_days and not m.after_days for m in table(result).measures[:2])


def test_since_limits_and_empty_after() -> None:
    result = sample()
    actual = build(result, utc_offset=timedelta(), now=NOW, since=date(2026, 5, 6))
    assert actual.after is None
    assert all(not m.after_days for m in actual.measures)
    with pytest.raises(UsageError) as error:
        build(result, utc_offset=timedelta(), now=NOW, since=date(2026, 1, 1))
    assert error.value.code == "since_too_early"


def test_selection_order_unknowns_and_overrides() -> None:
    result = sample()
    result = replace(
        result,
        responses=result.responses + tuple(replace(r, model=1, effort=1) for r in result.responses),
        models=(None, None),
        efforts=(None, None),
        model_order=(1, 0),
        effort_order=(1, 0),
    )
    actual = table(result)
    assert (actual.model, actual.effort, actual.other_settings) == ("model-1", "effort-1", 1)
    assert table(result, model="model-2").model == "model-2"
    assert table(result, model="gpt-99").model is None


def test_repeated_value_tie_and_edit_setting() -> None:
    result = sample("codex")
    result = replace(
        result,
        responses=tuple(replace(r, reasoning=5 + i % 2) for i, r in enumerate(result.responses)),
    )
    actual = table(result)
    assert actual.reference_value == 5
    assert actual.measures[2].before_days[0].value == "1/2"
    result = sample()
    result = replace(
        result,
        edits=tuple(replace(e, model=1, failed=True) for e in result.edits),
        models=("gpt-5.3", "gpt-5.4"),
        model_order=(0, 1),
    )
    assert not table(result).measures[2].before_days


def test_context_uses_all_window_responses_but_project_filter() -> None:
    data = sample()
    sub = tuple(
        replace(r, main_thread=False, model=1, version=2, workdir=3) for r in data.responses
    )
    outside = tuple(replace(r, in_project=False, version=4, workdir=4) for r in data.responses)
    actual = table(
        replace(
            data,
            responses=(*data.responses, *sub, *outside),
            models=("gpt-5.3", "gpt-5.4"),
            model_order=(0, 1),
        )
    )
    assert actual.context is not None
    assert actual.context.client_versions_before == actual.context.client_versions_after == 3
    assert actual.context.client_versions_both == 3
    assert actual.context.workdirs_before == actual.context.workdirs_after == 4
    assert actual.context.subagent_share_before == actual.context.subagent_share_after == "1/2"
    assert actual.other_settings == 0
    assert actual.measures[0].before_days[0].count == 20


def test_fixed_offset_newest_day_and_default_periods() -> None:
    data = sample()
    stamp = datetime(2026, 5, 5, 23, 45, tzinfo=UTC)
    response = replace(data.responses[0], when=stamp)
    rows = tuple(response for _ in range(20))
    data = replace(data, responses=rows, edits=())
    actual = build(data, utc_offset=timedelta(minutes=330), now=NOW)
    assert actual.split_date == "2026-04-23"
    assert actual.before is not None and actual.before.first_day == "2026-01-29"
    assert actual.after is not None and actual.after.last_day == "2026-05-06"
    assert actual.measures[0].after_days[0].day == "2026-05-06"
    # A future, out-of-project or subagent response must not advance N.
    ignored = (
        replace(response, when=NOW + timedelta(days=1)),
        replace(response, when=NOW, in_project=False),
        replace(response, when=NOW, main_thread=False),
    )
    assert (
        build(
            replace(data, responses=(*rows, *ignored)), utc_offset=timedelta(minutes=330), now=NOW
        ).after
        == actual.after
    )


def test_calendar_overflow_and_since_boundary() -> None:
    data = sample()
    for stamp, offset in (
        (datetime.min.replace(tzinfo=UTC), timedelta()),
        (datetime.max.replace(tzinfo=UTC), timedelta(hours=1)),
    ):
        early = replace(data, responses=(replace(data.responses[0], when=stamp),), edits=())
        with pytest.raises(UsageError) as error:
            build(early, utc_offset=offset, now=datetime.max.replace(tzinfo=UTC))
        assert error.value.code == "calendar_range"
    newest = date(2026, 5, 5)
    assert (
        build(data, utc_offset=timedelta(), now=NOW, since=newest - timedelta(days=83)).split_date
        == "2026-02-11"
    )
    with pytest.raises(UsageError):
        build(data, utc_offset=timedelta(), now=NOW, since=newest - timedelta(days=84))


def test_pooled_setting_selection_and_effort_tie() -> None:
    data = sample()
    other = tuple(replace(r, effort=1) for r in data.responses if r.when.date() >= SPLIT)
    # The minority setting owns more after responses, but the original wins pooled.
    data = replace(
        data,
        responses=(*data.responses, *other, *other),
        efforts=("high", "low"),
        effort_order=(1, 0),
    )
    assert table(data).effort == "high"
    assert table(data, effort="low").effort == "low"
    assert table(data, effort="effort-1").model is None
    tied = replace(
        data,
        responses=tuple(replace(r, effort=1) for r in data.responses[:300]) + data.responses[:300],
    )
    assert table(tied).effort == "low"


def test_each_usable_day_boundary() -> None:
    data = sample("codex")
    for known, positive, token_days, zero_days in [(19, 19, 0, 0), (20, 9, 0, 1), (20, 10, 1, 1)]:
        rows = tuple(
            replace(data.responses[i], reasoning=5 if i < positive else 0) for i in range(known)
        )
        actual = table(replace(data, responses=rows, edits=()))
        assert len(actual.measures[0].before_days) == token_days
        assert len(actual.measures[1].before_days) == zero_days
        assert len(actual.measures[2].before_days) == token_days
    data = sample()
    for n in (9, 10):
        actual = table(replace(data, edits=data.edits[:n]))
        assert len(actual.measures[2].before_days) == (n == 10)


def test_no_main_response_and_empty_context() -> None:
    data = sample()
    actual = table(
        replace(data, responses=tuple(replace(r, main_thread=False) for r in data.responses))
    )
    assert actual.model is None and actual.split_date == SPLIT.isoformat()
    actual = table(replace(data, responses=data.responses[:20], edits=()))
    assert actual.after is None
    assert actual.context is not None and actual.context.subagent_share_after is None
