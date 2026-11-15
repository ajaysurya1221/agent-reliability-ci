"""Conditional exact rank test, integer DP on doubled midrank sums."""

from __future__ import annotations

from bisect import bisect_right
from collections import Counter
from collections.abc import Sequence
from fractions import Fraction
from functools import lru_cache
from itertools import combinations
from math import comb

Exact = int | Fraction


def _ranks(before: Sequence[Exact], after: Sequence[Exact]) -> tuple[list[int], tuple[int, ...]]:
    if not before or not after or any(type(v) not in (int, Fraction) for v in (*before, *after)):
        raise ValueError("invalid_values")
    values = [*before, *after]
    counts = Counter(values)
    sizes: list[int] = []
    ranks: dict[Exact, int] = {}
    position = 0
    for value in sorted(counts):
        size = counts[value]
        ranks[value] = 2 * position + size + 1
        sizes.append(size)
        position += size
    return [ranks[value] for value in values], tuple(sizes)


@lru_cache(maxsize=256)
def null_distribution(
    n: int, m: int, ties: tuple[int, ...]
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """Return attainable sums and cumulative counts; each tied selection has C(t,j) weight."""
    if n < 1 or m < 1 or sum(ties) != n + m or min(ties) < 1:
        raise ValueError("invalid_values")
    selected = min(n, m)
    dp: list[dict[int, int]] = [{} for _ in range(selected + 1)]
    dp[0][0] = 1
    position = 0
    for size in ties:
        rank = 2 * position + size + 1
        weights = [comb(size, j) for j in range(min(size, selected) + 1)]
        # Descending updates preserve the previous group at each smaller cardinality.
        for k in range(min(selected, position + size), 0, -1):
            dest = dp[k]
            for j in range(1, min(size, k) + 1):
                offset, weight = j * rank, weights[j]
                for total, count in dp[k - j].items():
                    key = total + offset
                    dest[key] = dest.get(key, 0) + count * weight
        position += size
    distribution = dp[selected]
    if m > n:
        total_rank = (n + m) * (n + m + 1)
        distribution = {total_rank - rank: count for rank, count in distribution.items()}
    sums = tuple(sorted(distribution))
    cumulative: list[int] = []
    count = 0
    for total in sums:
        count += distribution[total]
        cumulative.append(count)
    assert count == comb(n + m, m)
    return sums, tuple(cumulative)


def p_lower(before: Sequence[Exact], after: Sequence[Exact]) -> Fraction:
    ranks, ties = _ranks(before, after)
    n, m = len(before), len(after)
    sums, cumulative = null_distribution(n, m, ties)
    index = bisect_right(sums, sum(ranks[n:])) - 1
    return Fraction(cumulative[index], comb(n + m, m))


def brute_p_lower(before: Sequence[Exact], after: Sequence[Exact]) -> Fraction:
    if not before or not after or any(type(v) not in (int, Fraction) for v in (*before, *after)):
        raise ValueError("invalid_values")
    pooled = [*before, *after]
    # Deliberately independent of the production rank assignment and DP.
    ranks = [
        sum(x < value for x in pooled) + sum(x <= value for x in pooled) + 1 for value in pooled
    ]
    n, m = len(before), len(after)
    observed = sum(ranks[n:])
    count = sum(sum(chosen) <= observed for chosen in combinations(ranks, m))
    return Fraction(count, comb(n + m, m))
