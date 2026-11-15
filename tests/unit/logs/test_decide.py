"""Result precedence and exact statistical moves."""

from dataclasses import replace
from fractions import Fraction

import pytest

from arci.logs.decide import decide_tool, error_tool, exit_code, move_before
from arci.logs.records import ReaderCounters
from tests.unit.logs.test_measures import sample, table


@pytest.mark.parametrize(
    "after,edits,result,reason",
    [
        (100, True, "NO_DROP", "no_drop"),
        (1, False, "REAL_DROP", "real_drop"),
        (0, False, "REAL_DROP", "real_drop"),
        (100, False, "CANNOT_TELL", "not_enough_evidence"),
    ],
)
def test_ladder(after: int, edits: bool, result: str, reason: str) -> None:
    data = sample(after=after, edits=edits)
    decision = decide_tool(table(data), data.counters)
    assert (decision.result, decision.reason) == (result, reason)
    for measure in decision.measures:
        if measure.finding == "real_drop":
            assert measure.p_none is measure.u_none is None


def test_too_few_and_no_setting() -> None:
    data = sample()
    data = replace(data, responses=data.responses[:20], edits=())
    assert decide_tool(table(data), data.counters).reason == "too_few_days"
    assert decide_tool(table(data, model="gpt-99"), data.counters).reason == "no_usable_setting"


def test_margins_are_exact() -> None:
    assert move_before("reasoning_tokens", Fraction(5)) == Fraction(15, 4)
    assert move_before("no_reasoning_share", Fraction(-1, 2)) == Fraction(-3, 5)
    assert move_before("edit_failure_share", Fraction(-1)) == Fraction(-103, 100)
    assert move_before("repeated_value_share", Fraction(0)) == Fraction(-1, 10)


@pytest.mark.parametrize("reason", ["no_logs", "read_error", "format_not_recognised"])
def test_errors_and_exit_mapping(reason: str) -> None:
    err = error_tool("codex", reason, ReaderCounters())
    assert err.result == "ERROR" and err.reason == reason
    assert exit_code([err]) == 3
    for after, edits, expected in [(1, True, 1), (100, False, 2), (100, True, 0)]:
        data = sample(after=after, edits=edits)
        assert exit_code([decide_tool(table(data), data.counters), err]) == expected


def test_streak_vetoes_another_real_drop() -> None:
    data = sample()
    # Tokens have two long runs before the split. Zeros have constant before-days.
    rows = tuple(
        replace(r, reasoning=(10 if r.when.day < 26 else 20) if r.when.month == 4 else 0)
        for r in data.responses
    )
    decision = decide_tool(table(replace(data, responses=rows)), data.counters)
    # Tokens have no after-days here, so also test a streak with usable after-days.
    assert decision.result == "REAL_DROP"
    rows = tuple(
        replace(
            r,
            reasoning=(10 if r.when.day < 26 else 20)
            if r.when.month == 4
            else (0 if i % 2 else 10),
        )
        for i, r in enumerate(data.responses)
    )
    decision = decide_tool(table(replace(data, responses=rows)), data.counters)
    assert decision.measures[0].finding == "streaky"
    assert decision.measures[1].finding == "real_drop"
    assert (decision.result, decision.reason) == ("CANNOT_TELL", "streaky_days")
    assert exit_code([decision]) == 2
    # Same streak, zero share unchanged: prevents NO DROP.
    rows = tuple(
        replace(r, reasoning=10 if r.when.month == 4 and r.when.day < 26 else 20)
        for r in data.responses
    )
    decision = decide_tool(table(replace(data, responses=rows)), data.counters)
    assert decision.reason == "streaky_days"
    assert [m.finding for m in decision.measures] == ["streaky", "no_drop", "no_drop"]


def test_cannot_tell_measure_and_determinism() -> None:
    from arci.logs.decide import day_table_digest
    from arci.logs.schema import seal

    data = sample(after=75)
    # At the margin the strict no-drop count is zero; rank test finds a real drop.
    # Alternate wide-spread values instead for an unresolved measure.
    rows = tuple(replace(r, reasoning=10 if r.when.day % 2 else 1000) for r in data.responses)
    data = replace(data, responses=rows, edits=())
    original = table(data)
    decision = decide_tool(original, data.counters)
    assert decision.measures[0].finding == "cannot_tell"
    reversed_data = replace(
        data, responses=tuple(reversed(data.responses)), edits=tuple(reversed(data.edits))
    )
    shuffled = table(reversed_data)
    assert day_table_digest(original) == day_table_digest(shuffled)
    assert decision == decide_tool(shuffled, data.counters)
    payload: dict[str, object] = {
        "arci_version": "2.3.0",
        "example": True,
        "utc_offset_minutes": 0,
        "project_filtered": False,
        "tools": [decision],
        "exit_code": 2,
    }
    first = seal(payload)
    payload["tools"] = [decide_tool(shuffled, data.counters)]
    assert first == seal(payload)


def test_real_drop_skips_no_drop_computation(monkeypatch: pytest.MonkeyPatch) -> None:
    from arci.logs import rank_test

    data = sample(after=1, edits=False)
    # Only the unchanged zero-share measure may run the no-drop test.
    original = rank_test.p_none
    seen: list[tuple[Fraction | int, ...]] = []

    def track(before: object, after: object) -> Fraction:
        from collections.abc import Sequence
        from typing import cast

        b = cast(Sequence[Fraction | int], before)
        a = cast(Sequence[Fraction | int], after)
        seen.append(tuple(b))
        return original(b, a)

    monkeypatch.setattr(rank_test, "p_none", track)
    decision = decide_tool(table(data), data.counters)
    assert decision.measures[0].finding == "real_drop"
    assert seen and all(v == Fraction(-1, 10) for values in seen for v in values)


def test_digest_payload_is_exact_and_medians_use_day_values() -> None:
    from arci.hashing import hash_record
    from arci.logs.decide import day_table_digest

    data = sample()
    data = replace(
        data,
        responses=tuple(replace(r, reasoning=5 if r.when.day % 2 else 6) for r in data.responses),
    )
    actual = table(data)
    decision = decide_tool(actual, data.counters)
    assert decision.measures[0].median_before == "11/2"
    assert actual.before is not None and actual.after is not None
    expected = {
        "method": "arci-logs/2",
        "tool": "claude-code",
        "model": "gpt-5.3",
        "effort": "high",
        "split_date": "2026-05-01",
        "before": {"first_day": "2026-02-06", "last_day": "2026-04-30"},
        "after": {"first_day": "2026-05-01", "last_day": "2026-05-05"},
        "alpha_real": "1/120",
        "alpha_none": "1/40",
        "measures": [
            {
                "id": measure.id,
                "margin": margin,
                "before_days": [d.model_dump() for d in measure.before_days],
                "after_days": [d.model_dump() for d in measure.after_days],
            }
            for measure, margin in zip(actual.measures, ("1/4", "1/10", "3/100"), strict=True)
        ],
    }
    assert day_table_digest(actual) == hash_record(expected)
    changed = replace(actual, model="gpt-5.4")
    assert day_table_digest(actual) != day_table_digest(changed)
