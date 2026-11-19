"""Hand-computed cases for the numbers of the log-signals description."""

from __future__ import annotations

import math
from datetime import UTC, datetime
from fractions import Fraction
from pathlib import Path
from typing import Any, cast

from bench.logsignals import analyze
from tests.unit.logsignals import pipeline, tables


def _row(
    *,
    path: str,
    repo: str = "0000000000000001",
    model: str = "gpt-6-astra-01",
    d: int = 20,
    zero: int = 1,
    first: datetime | None = None,
    month: str = "2026-04",
    half: str = "confirmation",
    user: str = "",
) -> analyze.SignalRow:
    return analyze.SignalRow(
        path=path,
        repo_key=repo,
        half=half,
        month=month,
        user_key=user,
        model=model,
        d=d,
        first_time=first,
        zero=zero,
        tokens=Fraction(11),
    )


def _fractions(values: list[float]) -> list[Fraction]:
    return [Fraction(value).limit_denominator(1000) for value in values]


# --- midranks and the number of one block ------------------------------------


def test_midranks_share_the_ranks_they_span() -> None:
    assert analyze.midranks(_fractions([1, 2, 2, 3])) == [
        Fraction(1),
        Fraction(5, 2),
        Fraction(5, 2),
        Fraction(4),
    ]
    assert analyze.midranks(_fractions([7, 7, 7, 7])) == [Fraction(5, 2)] * 4
    assert analyze.midranks(_fractions([3, 1, 2])) == [Fraction(3), Fraction(1), Fraction(2)]


def test_rho_of_a_block_on_hand_cases() -> None:
    assert analyze.rho_of_block(_fractions([1, 2, 3]), _fractions([1, 2, 3])) == 1.0
    assert analyze.rho_of_block(_fractions([1, 2, 3]), _fractions([3, 2, 1])) == -1.0
    # xs = [1.5, 1.5, 3], ys = [1, 2, 3]: numerator 4.5, spreads 4.5 and 6, rho = sqrt(0.75).
    found = analyze.rho_of_block(_fractions([1, 1, 2]), _fractions([1, 2, 3]))
    assert found is not None
    assert math.isclose(found, math.sqrt(0.75), rel_tol=0, abs_tol=1e-15)


def test_a_constant_or_one_session_block_carries_no_weight() -> None:
    assert analyze.rho_of_block(_fractions([1, 1, 1]), _fractions([1, 2, 3])) is None
    assert analyze.rho_of_block(_fractions([1, 2, 3]), _fractions([5, 5, 5])) is None
    assert analyze.rho_of_block(_fractions([1]), _fractions([2])) is None
    assert analyze.rho_of_block([], []) is None


def test_the_short_tied_form_is_not_used() -> None:
    # 1 - 6 * sum(d^2) / (n^3 - n) is wrong under ties: for these vectors it gives 0.75 while
    # the midrank correlation is sqrt(0.75).
    signal, outcome = _fractions([1, 1, 2]), _fractions([1, 2, 3])
    found = analyze.rho_of_block(signal, outcome)
    assert found is not None
    short = 1 - 6 * sum(
        (x - y) ** 2
        for x, y in zip(analyze.midranks(signal), analyze.midranks(outcome), strict=True)
    ) / (3**3 - 3)
    assert not math.isclose(found, float(short), rel_tol=0, abs_tol=1e-9)


# --- the thirds ---------------------------------------------------------------


def _third_labels(count: int) -> list[str]:
    rows = [
        _row(path=f"transcripts0/third-{index:03d}.jsonl", d=20 + index) for index in range(count)
    ]
    keys = analyze.block_keys(rows, "repository_model_length")
    return [keys[row.path][2] for row in rows]


def test_the_thirds_for_one_to_seven_sessions() -> None:
    assert _third_labels(1) == ["high"]
    assert _third_labels(2) == ["middle", "high"]
    assert _third_labels(3) == ["low", "middle", "high"]
    assert _third_labels(4) == ["low", "middle", "high", "high"]
    assert _third_labels(5) == ["low", "middle", "middle", "high", "high"]
    assert _third_labels(6) == ["low", "low", "middle", "middle", "high", "high"]
    assert _third_labels(7) == ["low", "low", "middle", "middle", "high", "high", "high"]


def test_a_missing_first_response_time_sorts_after_the_others() -> None:
    early = _row(path="transcripts0/a.jsonl", d=20, first=datetime(2026, 4, 1, tzinfo=UTC))
    late = _row(path="transcripts0/b.jsonl", d=20, first=datetime(2026, 4, 2, tzinfo=UTC))
    absent = _row(path="transcripts0/c.jsonl", d=20, first=None)
    keys = analyze.block_keys([absent, late, early], "repository_model_length")
    assert keys[early.path][2] == "low"
    assert keys[late.path][2] == "middle"
    assert keys[absent.path][2] == "high"


def test_the_month_and_model_labels_of_a_session_without_one() -> None:
    rows = [
        _row(path="transcripts0/a.jsonl", month="", model="unknown"),
        _row(path="transcripts0/b.jsonl", month="2026-04", model="unknown"),
    ]
    by_month = analyze.block_keys(rows, "repository_month")
    assert by_month["transcripts0/a.jsonl"][1] == "unknown"
    assert by_month["transcripts0/b.jsonl"][1] == "2026-04"
    by_thirds = analyze.block_keys(rows, "repository_model_length")
    assert by_thirds["transcripts0/a.jsonl"][1] == "unknown"


def test_unknown_labels_are_counted_as_labels(tmp_path: Path) -> None:
    sessions = [
        tables.with_model(tables.with_month(session, ""), "unknown")
        for session in tables.make_sessions(repositories=3, per_repository=4)
    ]
    signal, outcome = tables.write_tables(tmp_path, sessions)
    checks = analyze.describe(signal, outcome, "confirmation")["checks"]
    assert isinstance(checks, dict)
    assert checks["month_unknown"] == 12
    assert checks["model_unknown"] == 12
    assert checks["months"] == {}


# --- both measures enter every block definition -------------------------------


def _measure(description: dict[str, object], measure: str) -> dict[str, Any]:
    measures = description["measures"]
    assert isinstance(measures, dict)
    found = measures[measure]
    assert isinstance(found, dict)
    return cast(dict[str, Any], found)


def test_every_session_enters_both_measures(tmp_path: Path) -> None:
    # Point 1 of this round, replacing decision 1 of SPEC_G: every row carries a second measure,
    # so the two measures count the same sessions in every block definition.
    sessions = tables.make_sessions(repositories=10, per_repository=16)
    signal, outcome = tables.write_tables(tmp_path / "whole", sessions)
    description = analyze.describe(signal, outcome, "confirmation")
    assert description["sessions"] == 160
    first = _measure(description, "no_reasoning_share")
    second = _measure(description, "reasoning_tokens")
    for definition in analyze.DEFINITIONS:
        assert second[definition]["sessions"] == first[definition]["sessions"]
        assert second[definition]["W"] == first[definition]["W"]


# --- the floors ---------------------------------------------------------------


def _description(
    tmp_path: Path, *, repositories: int, per_repository: int, user_keys: int = 0
) -> dict[str, object]:
    sessions = tables.make_sessions(
        repositories=repositories, per_repository=per_repository, user_keys=user_keys
    )
    signal, outcome = tables.write_tables(tmp_path, sessions)
    return analyze.describe(signal, outcome, "confirmation")


def _repository_block(description: dict[str, object]) -> dict[str, object]:
    measures = description["measures"]
    assert isinstance(measures, dict)
    first = measures["no_reasoning_share"]
    assert isinstance(first, dict)
    block = first["repository"]
    assert isinstance(block, dict)
    return block


def test_the_floor_needs_ten_repositories(tmp_path: Path) -> None:
    block = _repository_block(_description(tmp_path, repositories=9, per_repository=20))
    assert block["m"] == 9
    assert block["W"] == 171
    assert block["formed"] is False
    assert block["rho_bar"] is None


def test_the_floor_needs_one_hundred_and_fifty_units(tmp_path: Path) -> None:
    block = _repository_block(_description(tmp_path, repositories=10, per_repository=15))
    assert block["m"] == 10
    assert block["W"] == 140
    assert block["formed"] is False


def test_the_floor_is_met_at_exactly_ten_and_one_hundred_and_fifty(tmp_path: Path) -> None:
    block = _repository_block(_description(tmp_path, repositories=10, per_repository=16))
    assert block["m"] == 10
    assert block["W"] == 150
    assert block["formed"] is True
    assert isinstance(block["rho_bar"], float)


def test_an_unformed_first_measure_nulls_every_extra_number(tmp_path: Path) -> None:
    description = _description(tmp_path, repositories=9, per_repository=20)
    extra = description["first_measure_repository"]
    assert extra == {
        "above": None,
        "below": None,
        "zero": None,
        "positive_weight_share": None,
        "loo_formed": False,
        "loo_min": None,
        "loo_max": None,
        "without_shared_formed": False,
        "without_shared": None,
    }


# --- the sign count, the range and the number without shared users ------------


def _extra(description: dict[str, object]) -> dict[str, object]:
    extra = description["first_measure_repository"]
    assert isinstance(extra, dict)
    return extra


def _aggregate(signal: Path, outcome: Path, half: str) -> analyze.Aggregate:
    rows = [row for row in analyze.read_signal(signal) if row.half == half]
    values = analyze.read_outcome(outcome, {row.path for row in rows})
    return analyze.aggregate(rows, values, "no_reasoning_share", "repository")


def test_the_sign_counts_and_their_denominator(tmp_path: Path) -> None:
    sessions = tables.make_sessions(repositories=12, per_repository=20)
    signal, outcome = tables.write_tables(tmp_path, sessions)
    found = _aggregate(signal, outcome, "confirmation")
    extra = _extra(analyze.describe(signal, outcome, "confirmation"))

    above = [rho for _repo, _weight, rho in found.per_repository if rho > 0]
    below = [rho for _repo, _weight, rho in found.per_repository if rho < 0]
    zero = [rho for _repo, _weight, rho in found.per_repository if rho == 0]
    assert extra["above"] == len(above)
    assert extra["below"] == len(below)
    assert extra["zero"] == len(zero)
    assert len(above) + len(below) + len(zero) == found.m

    positive_weight = sum(weight for _repo, weight, rho in found.per_repository if rho > 0)
    # The denominator is the whole weight, not the weight of the repositories above 0.
    assert extra["positive_weight_share"] == float(Fraction(positive_weight, found.weight))
    assert positive_weight < found.weight


def test_the_range_is_not_formed_at_ten_repositories(tmp_path: Path) -> None:
    extra = _extra(_description(tmp_path, repositories=10, per_repository=20))
    assert extra["loo_formed"] is False
    assert extra["loo_min"] is None
    assert extra["loo_max"] is None


def test_the_range_is_formed_at_eleven_repositories(tmp_path: Path) -> None:
    sessions = tables.make_sessions(repositories=11, per_repository=20)
    signal, outcome = tables.write_tables(tmp_path, sessions)
    found = _aggregate(signal, outcome, "confirmation")
    extra = _extra(analyze.describe(signal, outcome, "confirmation"))
    assert found.m == 11
    assert extra["loo_formed"] is True
    left_out = [
        (found.total - weight * rho) / (found.weight - weight)
        for _repo, weight, rho in found.per_repository
    ]
    assert extra["loo_min"] == min(left_out)
    assert extra["loo_max"] == max(left_out)


def _other_half_sharing(users: int, *, start: int = 9000) -> list[tables.Session]:
    """Sessions of the other half carrying the first `users` shared user keys."""
    shared = [tables.canary_key(2000 + index) for index in range(users)]
    sessions = tables.make_sessions(
        repositories=1, per_repository=20, half="discovery", start=start
    )
    return [
        tables.with_user(session, shared[index % users]) for index, session in enumerate(sessions)
    ]


def test_the_number_without_shared_users(tmp_path: Path) -> None:
    mine = tables.make_sessions(repositories=14, per_repository=20, user_keys=2)
    signal, outcome = tables.write_tables(tmp_path, mine + _other_half_sharing(2))

    excluded = analyze.shared_user_repositories(analyze.read_signal(signal), "confirmation")
    assert excluded == {tables.canary_key(1000), tables.canary_key(1001)}

    kept = [row for row in analyze.read_signal(signal) if row.half == "confirmation"]
    kept = [row for row in kept if row.repo_key not in excluded]
    values = analyze.read_outcome(
        outcome, {row.path for row in analyze.read_signal(signal) if row.half == "confirmation"}
    )
    expected = analyze.aggregate(kept, values, "no_reasoning_share", "repository")

    extra = _extra(analyze.describe(signal, outcome, "confirmation"))
    assert extra["without_shared_formed"] is True
    assert extra["without_shared"] == expected.rho_bar
    assert expected.m == 12


def _below_floor_without_shared(tmp_path: Path) -> tuple[Path, Path]:
    """Eleven repositories carry weight; three of them hold a shared user id, so the number
    without shared users is computed inside eight and is not formed."""
    mine = tables.make_sessions(repositories=11, per_repository=20, user_keys=3)
    return tables.write_tables(tmp_path, mine + _other_half_sharing(3))


def test_the_number_without_shared_users_is_not_formed_below_the_floor(tmp_path: Path) -> None:
    signal, outcome = _below_floor_without_shared(tmp_path)
    extra = _extra(analyze.describe(signal, outcome, "confirmation"))
    assert extra["loo_formed"] is True
    assert extra["without_shared_formed"] is False
    assert extra["without_shared"] is None


# --- the printed forms --------------------------------------------------------


def test_the_printed_formats() -> None:
    assert analyze.printed_rho(0.0356781) == "+0.036"
    assert analyze.printed_rho(-0.5) == "-0.500"
    assert analyze.printed_coarse(0.0356781) == "+0.04"
    assert analyze.printed_coarse(-1.0) == "-1.00"
    assert analyze.printed_share(0.5487179) == "55%"
    assert analyze.printed_share(0.0) == "0%"
    assert analyze.not_formed_form(9, 171) == "not formed (9 repositories, 171 units)"


def test_every_not_formed_form(tmp_path: Path) -> None:
    # The result file records the start time (decision 6), so the provenance carries it.
    provenance = pipeline.provenance()

    below_floor = _description(tmp_path / "below", repositories=9, per_repository=20)
    printed = analyze.printed_result(below_floor, provenance)
    measures = printed["measures"]
    assert isinstance(measures, dict)
    first = measures["no_reasoning_share"]
    assert isinstance(first, dict)
    assert first["repository"] == {"not_formed": "not formed (9 repositories, 171 units)"}
    assert printed["first_measure_repository"] == {
        "not_formed": "not formed (9 repositories, 171 units)"
    }

    at_ten = _description(tmp_path / "ten", repositories=10, per_repository=16)
    printed = analyze.printed_result(at_ten, provenance)
    extra = printed["first_measure_repository"]
    assert isinstance(extra, dict)
    assert extra["loo_range"] == "not formed"
    assert "loo_min" not in extra

    signal, outcome = _below_floor_without_shared(tmp_path / "shared")
    printed = analyze.printed_result(analyze.describe(signal, outcome, "confirmation"), provenance)
    extra = printed["first_measure_repository"]
    assert isinstance(extra, dict)
    assert extra["without_shared"] == "not formed"
    assert extra["loo_min"] != "not formed"
