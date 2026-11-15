"""Independent labeled-subset and mark-arrangement enumeration through size 12."""

from __future__ import annotations

import subprocess
import sys
from collections import Counter
from collections.abc import Iterator, Sequence
from fractions import Fraction
from itertools import combinations, product

import pytest

from arci.logs.rank_test import g_tail, p_none, p_real, p_streak, strict_count


def _splits(total: int) -> Iterator[tuple[int, ...]]:
    for selected in range(total + 1):
        yield total, selected


def _labelings(total: int, selected: int) -> list[tuple[int, ...]]:
    return list(combinations(range(total), selected))


def _split(
    values: Sequence[Fraction], indices: tuple[int, ...]
) -> tuple[list[Fraction], list[Fraction]]:
    return (
        [value for i, value in enumerate(values) if i not in indices],
        [values[i] for i in indices],
    )


def _lower_tails(counts: Counter[Fraction | int]) -> dict[Fraction | int, Fraction]:
    running = 0
    total = sum(counts.values())
    tails: dict[Fraction | int, Fraction] = {}
    for statistic, count in sorted(counts.items()):
        running += count
        tails[statistic] = Fraction(running, total)
    return tails


@pytest.mark.parametrize("total,selected", [case for n in range(13) for case in _splits(n)])
@pytest.mark.parametrize("pattern", ["distinct", "three-level", "equal"])
def test_rank_and_no_drop_all_labelings(total: int, selected: int, pattern: str) -> None:
    # Rational, negative and unevenly spaced values keep the oracle independent
    # of the production DP's doubled-rank representation.
    levels = (Fraction(-7, 3), Fraction(2, 5), Fraction(19, 7))
    values = [
        Fraction(i * i - 11, 7)
        if pattern == "distinct"
        else levels[i % 3]
        if pattern == "three-level"
        else Fraction(2, 5)
        for i in range(total)
    ]
    labels = _labelings(total, selected)
    # Compute each midrank directly from pair comparisons, with no grouping.
    ranks = [
        1 + sum(other < value for other in values) + Fraction(values.count(value) - 1, 2)
        for value in values
    ]
    statistics = [sum((ranks[i] for i in indices), Fraction()) for indices in labels]
    reference = _lower_tails(Counter(statistics))
    alphas = (Fraction(1, 40), Fraction(1, 120))
    real_rejections = [0, 0]
    none_rejections = [0, 0]
    for indices, statistic in zip(labels, statistics, strict=True):
        before, after = _split(values, indices)
        real = p_real(before, after)
        assert real == reference[statistic]
        u = sum(1 for x in before for y in after if x < y)
        assert strict_count(before, after) == u
        none = p_none(before, after)
        assert none == g_tail(len(before), len(after), u)
        assert isinstance(real, Fraction)
        assert isinstance(none, Fraction)
        for i, alpha in enumerate(alphas):
            real_rejections[i] += real <= alpha
            none_rejections[i] += none <= alpha
    for i, alpha in enumerate(alphas):
        assert Fraction(real_rejections[i], len(labels)) <= alpha
        assert Fraction(none_rejections[i], len(labels)) <= alpha


@pytest.mark.parametrize("total,selected", [case for n in range(13) for case in _splits(n)])
def test_g_tail_all_thresholds(total: int, selected: int) -> None:
    # Each binary labeling represents the same number n!*m! of permutations
    # of distinct values. Count x<y directly on the positions.
    counts = Counter(
        sum(x < y for x in range(total) if x not in indices for y in indices)
        for indices in _labelings(total, selected)
    )
    n, m = total - selected, selected
    for u in range(-1, n * m + 2):
        expected = Fraction(
            sum(count for score, count in counts.items() if score >= u), sum(counts.values())
        )
        actual = g_tail(n, m, u)
        assert actual == expected
        assert isinstance(actual, Fraction)


def _runs(marks: Sequence[bool]) -> int:
    return sum(i == 0 or mark != marks[i - 1] for i, mark in enumerate(marks))


@pytest.mark.parametrize("total,a", [case for n in range(13) for case in _splits(n)])
def test_streak_every_mark_arrangement(total: int, a: int) -> None:
    arrangements = [[i in above for i in range(total)] for above in _labelings(total, a)]
    reference = _lower_tails(Counter(_runs(marks) for marks in arrangements))
    b = total - a
    for marks in arrangements:
        values = [Fraction(1 if mark else -1) for mark in marks]
        # Force median zero even for unequal a,b, so the retained marks
        # exercise EVERY runs distribution, not only balanced binary data.
        ties = [Fraction()] * (abs(a - b) + 1)
        middle = total // 2
        actual = p_streak(values[:middle] + ties + values[middle:])
        assert actual == reference[_runs(marks)]
        assert isinstance(actual, Fraction)


def test_strict_count_monotone_in_every_after_value() -> None:
    levels = (Fraction(-1, 3), Fraction(), Fraction(1, 3))
    for values in product(levels, repeat=6):
        before, after = values[:3], list(values[3:])
        original = strict_count(before, after)
        for i in range(len(after)):
            for decrease in (Fraction(1, 6), Fraction(1, 3), Fraction(2)):
                lowered = after.copy()
                lowered[i] -= decrease
                assert strict_count(before, lowered) <= original


def test_reviewers_tie_example() -> None:
    assert p_real([200] * 8 + [100] * 2, [100] * 5) == Fraction(1, 143)


def test_empty_singleton_and_equal_values() -> None:
    for before, after in (([], []), ([], [1]), ([1], [])):
        assert p_real(before, after) == Fraction(1)
        assert p_none(before, after) == Fraction(1)
        assert strict_count(before, after) == 0
    assert p_real([2], [1]) == Fraction(1, 2)
    assert p_real([1], [2]) == Fraction(1)
    assert p_none([1], [2]) == Fraction(1, 2)
    assert p_none([2], [1]) == Fraction(1)
    for value in (1, Fraction(7, 11)):
        assert p_real([value] * 10, [value] * 5) == Fraction(1)
        assert p_none([value] * 10, [value] * 5) == Fraction(1)
        assert strict_count([value] * 10, [value] * 5) == 0
        assert p_streak([value] * 12) == Fraction(1)
        assert p_streak([value]) == Fraction(1)
    assert p_streak([]) == Fraction(1)
    assert p_streak([0, 0, 1, 1]) == Fraction(1, 3)  # even median is 1/2
    assert p_streak([-1, -1, 0, 1, 1]) == Fraction(1, 3)  # drop odd median
    assert p_streak([0, 1, 0, 1]) == Fraction(1)
    assert g_tail(3, 4, -100) == Fraction(1)
    assert g_tail(3, 4, 13) == Fraction(0)
    with pytest.raises(ValueError, match="group sizes must be non-negative"):
        g_tail(-1, 2, 0)


def test_inputs_unchanged_and_exact_rationals() -> None:
    # The tiny difference disappears in floating arithmetic at this magnitude.
    before = [Fraction(10**30), Fraction(10**30) + Fraction(1, 10**30)]
    after = [Fraction(10**30) - Fraction(1, 10**30)]
    originals = before.copy(), after.copy()
    assert p_real(before, after) == Fraction(1, 3)
    assert strict_count(before, after) == 0
    assert p_none(before, after) == Fraction(1)
    assert p_streak(before) == Fraction(1)
    assert (before, after) == originals
    assert p_real(tuple(before), tuple(after)) == Fraction(1, 3)


@pytest.mark.parametrize(
    "expression",
    [
        "p_real(list(range(0, 168, 2)), list(range(1, 168, 2)))",
        "p_real([i // 2 for i in range(84)], [i // 2 for i in range(84, 168)])",
        "p_real([i % 3 for i in range(84)], [i % 3 for i in range(84)])",
        "p_real([min(i, 80) for i in range(84)], list(range(84, 168)))",
        "p_real(list(range(83)), list(range(83, 167)))",
        "p_real([1] * 84, [1] * 84)",
        "g_tail(84, 84, 3528)",
        "p_none(list(range(84)), list(range(84)))",
        "p_streak(list(range(84)))",
        "p_streak(list(range(168)))",
    ],
)
def test_maximum_sizes_cold(expression: str) -> None:
    # Fresh processes establish genuinely cold caches without coupling tests
    # to private cache helpers. Time only the public call, not interpreter start.
    script = (
        "from fractions import Fraction\n"
        "from time import perf_counter\n"
        "from arci.logs.rank_test import p_real, g_tail, p_none, p_streak\n"
        "start = perf_counter()\n"
        f"result = {expression}\n"
        "elapsed = perf_counter() - start\n"
        "assert isinstance(result, Fraction)\n"
        "assert 0 <= result <= 1\n"
        "assert elapsed < 2, elapsed\n"
        "print(f'{elapsed:.6f}s')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=10, check=True
    )
    print(f"{expression}: {result.stdout.strip()}")
