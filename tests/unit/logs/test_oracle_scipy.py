"""An outside check of the exact rank test against SciPy.

`src/arci/logs/rank_test.py` computes `p_real` (the real-drop test) by integer dynamic
programming over doubled midranks, as described in `docs/STATISTICS_LOGS.md`: the share,
among all `C(n+m, m)` ways to split the pooled `before`/`after` values, whose "after" midrank
sum is at most the observed one. This module checks that exact count against two independent
SciPy oracles that compute the same quantity by brute-force enumeration:

- `scipy.stats.permutation_test`, with a midrank-sum statistic, `permutation_type="independent"`,
  full enumeration (forced by an `n_resamples` above the total number of splits) and
  `alternative="less"` (a left tail on the "after" group's rank sum, matching `p_real`'s "at
  most the observed sum"). Used for every case, with and without ties.
- `scipy.stats.mannwhitneyu(method="exact")`, used only for the tie-free cases, where the
  rank-sum and U statistics are exactly equivalent.

This whole module is skipped, as a unit, when SciPy cannot be imported
(`pytest.importorskip("scipy")` below runs at collection time). It is not run in this
worktree; the "oracle / SciPy" CI job installs SciPy from `constraints/oracle.txt` and runs
it, and fails if the module reports as skipped there.

This file is new; it does not import or modify any other test file.
"""

from __future__ import annotations

import random
from fractions import Fraction
from math import comb

import pytest

scipy = pytest.importorskip("scipy")

# SciPy is never installed in this worktree's .venv (only the "oracle / SciPy" CI job
# installs it, from constraints/oracle.txt); the import is unresolvable for basedpyright here.
from scipy.stats import (  # noqa: E402  # pyright: ignore[reportMissingImports]
    mannwhitneyu,
    permutation_test,
    rankdata,
)

from arci.logs.rank_test import p_real  # noqa: E402

# Group sizes range from 2 to 6 for each side, so the largest pooled split count is
# comb(12, 6) = 924: small enough that forcing full enumeration is cheap for every case.
_MIN_GROUP = 2
_MAX_GROUP = 6
_TIE_VALUES = (1, 2, 3)
_FORCE_EXACT_RESAMPLES = 10_000_000


def _midrank_statistic(x: object, y: object) -> float:
    """Sum of the pooled midranks that fall in `y` (the "after" sample)."""
    pooled = [*x, *y]  # type: ignore[misc]
    ranks = rankdata(pooled, method="average")
    return float(sum(ranks[len(x) :]))  # type: ignore[arg-type]


def _random_case(rng: random.Random, *, with_ties: bool) -> tuple[list[int], list[int]]:
    n = rng.randint(_MIN_GROUP, _MAX_GROUP)
    m = rng.randint(_MIN_GROUP, _MAX_GROUP)
    if with_ties:
        values = [rng.choice(_TIE_VALUES) for _ in range(n + m)]
    else:
        values = rng.sample(range(1, 50 * (n + m)), n + m)
    rng.shuffle(values)
    return values[:n], values[n:]


def _assert_matches_permutation_test(before: list[int], after: list[int]) -> None:
    n, m = len(before), len(after)
    total = comb(n + m, m)
    expected = p_real(before, after)

    result = permutation_test(
        (before, after),
        _midrank_statistic,
        permutation_type="independent",
        n_resamples=_FORCE_EXACT_RESAMPLES,
        alternative="less",
    )

    scaled = result.pvalue * total
    rounded = round(scaled)
    assert abs(scaled - rounded) < 1e-9, (before, after, result.pvalue, total)
    assert Fraction(rounded, total) == expected, (before, after, result.pvalue, total, expected)


def _assert_matches_mannwhitneyu(before: list[int], after: list[int]) -> None:
    n, m = len(before), len(after)
    total = comb(n + m, m)
    expected = p_real(before, after)

    # `after` is sample 1: a small U1 means `after` tends to rank below `before`, the same
    # left tail p_real tests on the "after" group's midrank sum.
    result = mannwhitneyu(after, before, alternative="less", method="exact")

    scaled = result.pvalue * total
    rounded = round(scaled)
    assert abs(scaled - rounded) < 1e-9, (before, after, result.pvalue, total)
    assert Fraction(rounded, total) == expected, (before, after, result.pvalue, total, expected)


@pytest.mark.parametrize("seed", range(200))
def test_p_real_matches_scipy_permutation_test_with_ties(seed: int) -> None:
    rng = random.Random(f"with_ties:{seed}")
    before, after = _random_case(rng, with_ties=True)
    _assert_matches_permutation_test(before, after)


@pytest.mark.parametrize("seed", range(100))
def test_p_real_matches_scipy_without_ties(seed: int) -> None:
    rng = random.Random(f"no_ties:{seed}")
    before, after = _random_case(rng, with_ties=False)
    _assert_matches_permutation_test(before, after)
    _assert_matches_mannwhitneyu(before, after)
