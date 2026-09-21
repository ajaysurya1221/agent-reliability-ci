from __future__ import annotations

import math
from itertools import pairwise

import pytest

from arci.stats import clopper_pearson, clopper_pearson_tail

CP_EDGE = (
    (10000, 10000, 0.998480974397, 1.0),
    (9990, 10000, 0.996371411368, 0.999890624362),
    (0, 10000, 0.0, 0.001519025603),
    (190, 200, 0.829920472982, 0.994422498826),
    (5, 10, 0.016037872750, 0.983962127250),
)


@pytest.mark.parametrize(("x", "n", "low", "high"), CP_EDGE)
def test_clopper_pearson_tail_matches_edge_references(
    x: int, n: int, low: float, high: float
) -> None:
    assert clopper_pearson_tail(x, n, 2.5e-7) == pytest.approx((low, high), rel=0, abs=1e-9)


def test_clopper_pearson_tail_tightens_monotonically_as_tail_grows() -> None:
    intervals = [
        clopper_pearson_tail(190, 200, tail) for tail in (2.5e-7, 1e-5, 1e-3, 0.0125, 0.1, 0.49)
    ]
    assert all(left[0] <= right[0] for left, right in pairwise(intervals))
    assert all(left[1] >= right[1] for left, right in pairwise(intervals))


@pytest.mark.parametrize("tail", [0.0, 1e-8, 0.5, 1.0, math.nan])
def test_clopper_pearson_tail_rejects_unsupported_tail(tail: float) -> None:
    with pytest.raises(ValueError):
        clopper_pearson_tail(5, 10, tail)


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
