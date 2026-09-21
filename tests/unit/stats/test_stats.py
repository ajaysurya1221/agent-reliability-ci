from __future__ import annotations

import math
from itertools import pairwise

import pytest

from arci.stats import clopper_pearson


def test_clopper_pearson_bounds_are_monotone_in_successes() -> None:
    intervals = [clopper_pearson(x, 20, 0.95) for x in range(21)]
    assert all(left[0] <= right[0] for left, right in pairwise(intervals))
    assert all(left[1] <= right[1] for left, right in pairwise(intervals))


def test_clopper_pearson_is_symmetric() -> None:
    n = 17
    for x in range(n + 1):
        low, high = clopper_pearson(x, n, 0.95)
        reflected_low, reflected_high = clopper_pearson(n - x, n, 0.95)
        assert low == pytest.approx(1.0 - reflected_high, abs=1e-13)
        assert high == pytest.approx(1.0 - reflected_low, abs=1e-13)


def test_clopper_pearson_has_exact_coverage_on_small_grid() -> None:
    n = 8
    confidence = 0.95
    intervals = [clopper_pearson(x, n, confidence) for x in range(n + 1)]
    for step in range(101):
        p = step / 100
        coverage = math.fsum(
            math.comb(n, x) * p**x * (1.0 - p) ** (n - x)
            for x, (low, high) in enumerate(intervals)
            if low <= p <= high
        )
        assert coverage >= confidence - 1e-12
