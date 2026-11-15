"""Exact conditional rank, strict-count and runs tests for daily log measures."""

from __future__ import annotations

from collections.abc import Sequence
from fractions import Fraction
from functools import lru_cache as _lru_cache
from itertools import groupby as _groupby
from itertools import pairwise as _pairwise
from math import comb as _comb


@_lru_cache(maxsize=16)
def _rank_counts(groups: tuple[int, ...], selected: int) -> tuple[int, int, int]:
    """Pack the tied-rank DP's integer coefficients into carry-free bit fields.

    Row k represents sum(rank2) - k*(k+1), removing the smallest possible
    doubled rank sum. Each coefficient counts labeled subsets, not unique
    multisets. Base B exceeds twice C(N, selected), so neither coefficients
    nor their eventual sum can carry. Intermediate rows also fit: selected
    is at most N/2 and C(seen, k) <= C(N, selected) for k <= selected.
    """
    total = sum(groups)
    bits = _comb(total, selected).bit_length() + 1
    # All odd-sized groups have even doubled midranks; halve their exponents.
    unit = 2 if all(size % 2 for size in groups) else 1
    rows = [1] + [0] * selected
    seen = 0
    for size in groups:
        updated = [0] * (selected + 1)
        weights = [_comb(size, j) for j in range(min(size, selected) + 1)]
        for k in range(max(0, selected - (total - seen)), min(seen, selected) + 1):
            if not rows[k]:
                continue
            for j in range(
                max(0, selected - k - (total - seen - size)), min(size, selected - k) + 1
            ):
                # New rank2 is 2*seen + size + 1. Subtract the change in
                # k*(k+1) as well. The resulting shift is always nonnegative.
                shift = j * (2 * (seen - k) + size - j) // unit
                updated[k + j] += (rows[k] * weights[j]) << (bits * shift)
        rows = updated
        seen += size
    return rows[selected], bits, unit


def p_real(before: Sequence[Fraction | int], after: Sequence[Fraction | int]) -> Fraction:
    """Conditional probability of an after midrank sum at most the observed sum."""
    n, m = len(before), len(after)
    if not n or not m:
        return Fraction(1)
    pooled = sorted([(value, False) for value in before] + [(value, True) for value in after])
    groups: list[int] = []
    observed = 0
    seen = 0
    for _, members in _groupby(pooled, key=lambda item: item[0]):
        labels = [is_after for _, is_after in members]
        size = len(labels)
        observed += sum(labels) * (2 * seen + size + 1)
        groups.append(size)
        seen += size

    # Choose the smaller group. The complement converts <= into >= when
    # before is smaller, since the total doubled rank sum is N*(N+1).
    selected = min(n, m)
    complement = m > n
    if complement:
        observed = seen * (seen + 1) - observed - 1
    packed, bits, unit = _rank_counts(tuple(groups), selected)
    cutoff = (observed - selected * (selected + 1)) // unit
    prefix = packed & ((1 << (bits * (cutoff + 1))) - 1) if cutoff >= 0 else 0
    # Evaluating a base-B polynomial at 1 is reduction modulo B-1. The
    # coefficient sum is strictly below B-1, so this is the exact tail count.
    count = prefix % ((1 << bits) - 1)
    total = _comb(n + m, m)
    return Fraction(total - count if complement else count, total)


def strict_count(moved_before: Sequence[Fraction | int], after: Sequence[Fraction | int]) -> int:
    """Count pairs x' < y, excluding equal values."""
    return sum(x < y for x in moved_before for y in after)


@_lru_cache(maxsize=64)
def _u_tails(n: int, m: int) -> tuple[int, ...]:
    """All integer upper tails of the Gaussian binomial [n+m choose n]_q."""
    # Multiply (1-q**(m+i))/(1-q**i) for i=1..n. Descending subtraction
    # multiplies the numerator; ascending addition divides the denominator.
    # Every intermediate quotient is a polynomial of degree i*m.
    counts = [1] + [0] * (n * m)
    for i in range(1, n + 1):
        for u in range(i * m, m + i - 1, -1):
            counts[u] -= counts[u - m - i]
        for u in range(i, i * m + 1):
            counts[u] += counts[u - i]
    for u in range(n * m - 1, -1, -1):
        counts[u] += counts[u + 1]
    return tuple(counts)


def g_tail(n: int, m: int, u: int) -> Fraction:
    """P(U >= u) for n and m distinct, uniformly labeled pooled values."""
    if n < 0 or m < 0:
        raise ValueError("group sizes must be non-negative")
    if u <= 0:
        return Fraction(1)
    if u > n * m:
        return Fraction(0)
    tails = _u_tails(min(n, m), max(n, m))
    return Fraction(tails[u], tails[0])


def p_none(moved_before: Sequence[Fraction | int], after: Sequence[Fraction | int]) -> Fraction:
    """Exact fixed-reference upper tail of the strict pair count."""
    return g_tail(len(moved_before), len(after), strict_count(moved_before, after))


def _choose(n: int, k: int) -> int:
    return _comb(n, k) if 0 <= k <= n else 0


def p_streak(before_in_date_order: Sequence[Fraction | int]) -> Fraction:
    """Lower tail of runs above/below the median, dropping median ties."""
    size = len(before_in_date_order)
    if not size:
        return Fraction(1)
    ordered = sorted(before_in_date_order)
    median = (Fraction(ordered[(size - 1) // 2]) + Fraction(ordered[size // 2])) / 2
    marks = [value > median for value in before_in_date_order if value != median]
    a = sum(marks)
    b = len(marks) - a
    if not a or not b:
        return Fraction(1)
    runs = 1 + sum(left != right for left, right in _pairwise(marks))
    count = 0
    for r in range(2, runs + 1):
        k = r // 2
        if r % 2:
            count += _choose(a - 1, k) * _choose(b - 1, k - 1)
            count += _choose(a - 1, k - 1) * _choose(b - 1, k)
        else:
            count += 2 * _choose(a - 1, k - 1) * _choose(b - 1, k - 1)
    return Fraction(count, _comb(a + b, a))
