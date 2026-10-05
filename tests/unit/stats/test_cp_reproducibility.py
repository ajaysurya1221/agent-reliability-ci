"""Clopper-Pearson bounds are exact functions of their binary64 inputs, on every platform.

The binomial tails behind each bisection step are compared with exact integer arithmetic, so a
bound depends only on the counts, the tail and IEEE-754 midpoints, never on libm. Every reference
below is built independently with ``fractions.Fraction`` (via ``Fraction.from_float``, never a
decimal string) or from a closed form evaluated with ``decimal``.
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable, Iterator
from decimal import Decimal, localcontext
from fractions import Fraction
from itertools import accumulate

import pytest

from arci.stats import (
    _tail_is_greater,  # pyright: ignore[reportPrivateUsage]  the unit under test
    clopper_pearson_tail,
)

GATE_TAIL = 0.0125  # alpha 0.05, K=1: the tail every committed store uses
MIN_TAIL = 2.5e-7
BISECTION_STEPS = 60

# Canonical bounds of clopper_pearson_tail(x, n, 0.0125), as float.hex().
CANONICAL = (
    (38, 50, "0x1.3260888cc2d7cp-1", "0x1.c333f6b1990a0p-1"),
    (130, 200, "0x1.23a6984ce7bd4p-1", "0x1.730611ce6cb6cp-1"),
    (138, 200, "0x1.38e507468bd6ep-1", "0x1.85f47f46da8e4p-1"),
    (187, 200, "0x1.c4f9e23162ecap-1", "0x1.efadb37e2f212p-1"),
)

GRID_N = (1, 2, 3, 5, 7, 8, 13, 21, 50)
GRID_P = (
    0.0,
    5e-324,
    2.0**-60,
    1e-9,
    0.0125,
    0.25,
    1.0 / 3.0,
    0.5,
    2.0 / 3.0,
    0.75,
    0.9875,
    1.0 - 2.0**-53,
    1.0,
)
GRID_TARGETS = (MIN_TAIL, GATE_TAIL, 0.25, 0.4999999999999999, 0.5, 0.75, 1.0 - MIN_TAIL)


def _pmf(n: int, p: float) -> list[Fraction]:
    prob = Fraction.from_float(p)
    complement = 1 - prob
    return [math.comb(n, k) * prob**k * complement ** (n - k) for k in range(n + 1)]


def _oracle_tail(x: int, n: int, p: float, *, upper: bool) -> Fraction:
    """Directly summed P(X >= x) or P(X <= x): no complement, no reflection."""
    terms = _pmf(n, p)
    return sum(terms[x:] if upper else terms[: x + 1], Fraction(0))


def _oracle_tails(n: int, p: float) -> Iterator[tuple[int, bool, Fraction]]:
    """Every tail at (n, p): running sums of the mass function, from each end separately."""
    terms = _pmf(n, p)
    lower = list(accumulate(terms))
    upper = list(accumulate(reversed(terms)))[::-1]
    for x in range(n + 1):
        yield x, True, upper[x]
        yield x, False, lower[x]


def _oracle_root(x: int, n: int, tail: float, *, upper: bool) -> float:
    """The gate's 60-step bisection on [0, 1], driven by the Fraction oracle."""
    low, high = 0.0, 1.0
    target = Fraction.from_float(tail)
    for _ in range(BISECTION_STEPS):
        midpoint = (low + high) / 2.0
        greater = _oracle_tail(x, n, midpoint, upper=upper) > target
        if upper == greater:
            high = midpoint
        else:
            low = midpoint
    return (low + high) / 2.0


def _oracle_interval(x: int, n: int, tail: float) -> tuple[float, float]:
    low = 0.0 if x == 0 else _oracle_root(x, n, tail, upper=True)
    high = 1.0 if x == n else _oracle_root(x, n, tail, upper=False)
    return low, high


def _reflection_points(n: int) -> list[float]:
    """Probabilities on and beside the reflection boundary cutoff = (n + 1) p."""
    points: list[float] = []
    for cutoff in range(n + 1):
        p = cutoff / (n + 1)
        if 0.0 < p < 1.0:
            points += [math.nextafter(p, 0.0), p, math.nextafter(p, 1.0)]
    return points


# --- 1. Independent tail oracle ------------------------------------------------------------


@pytest.mark.parametrize("n", GRID_N)
def test_tail_comparison_matches_the_fraction_oracle_on_a_grid(n: int) -> None:
    checked = 0
    for p in (*GRID_P, *_reflection_points(n)):
        for x, upper, exact in _oracle_tails(n, p):
            for target in GRID_TARGETS:
                expected = exact > Fraction.from_float(target)
                assert _tail_is_greater(x, n, p, target, upper=upper) is expected, (x, n, p, target)
                checked += 1
    assert checked >= len(GRID_P) * (n + 1) * 2 * len(GRID_TARGETS)


@pytest.mark.parametrize("n", (1, 2, 3, 4, 7, 8))
def test_tail_comparison_is_exact_at_and_beside_equality(n: int) -> None:
    """Dyadic p gives tails that are binary64 values: equal is not greater; one ulp decides."""
    exercised = 0
    for p in (0.125, 0.25, 0.5, 0.625, 0.75, 0.875):
        for x, upper, exact in _oracle_tails(n, p):
            target = float(exact)
            if not 0.0 < exact < 1.0 or Fraction.from_float(target) != exact:
                continue
            below, above = math.nextafter(target, 0.0), math.nextafter(target, 1.0)
            assert _tail_is_greater(x, n, p, target, upper=upper) is False
            assert _tail_is_greater(x, n, p, below, upper=upper) is True
            assert _tail_is_greater(x, n, p, above, upper=upper) is False
            exercised += 1
    assert exercised >= n


@pytest.mark.parametrize("n", (1, 5, 50))
def test_tail_comparison_handles_endpoints(n: int) -> None:
    for target in (MIN_TAIL, GATE_TAIL, 0.4999999999999999):
        for p in (0.0, 1.0):
            # P(X >= 0) = P(X <= n) = 1 at every p, including the clamped endpoints.
            assert _tail_is_greater(0, n, p, target, upper=True) is True
            assert _tail_is_greater(n, n, p, target, upper=False) is True
        # At p = 0 all mass is at 0; at p = 1 all mass is at n.
        assert _tail_is_greater(1, n, 0.0, target, upper=True) is False
        assert _tail_is_greater(0, n, 0.0, target, upper=False) is True
        assert _tail_is_greater(n, n, 1.0, target, upper=True) is True
        assert _tail_is_greater(n - 1, n, 1.0, target, upper=False) is False


# --- 2. Seeded random binary64 inputs ------------------------------------------------------


def _random_probability(rng: random.Random) -> float:
    draw = rng.random()
    shape = rng.randrange(4)
    if shape == 0:
        return draw
    if shape == 1:
        return math.ldexp(draw, -rng.randrange(1, 64))
    if shape == 2:
        return 1.0 - math.ldexp(draw, -rng.randrange(1, 53))
    return rng.randrange(1, 1 << 12) / (1 << 12)


def test_tail_comparison_matches_the_oracle_on_random_binary64_inputs() -> None:
    rng = random.Random(20261005)
    for _ in range(2000):
        n = rng.randint(1, 64)
        x = rng.randint(0, n)
        p = _random_probability(rng)
        target = rng.uniform(MIN_TAIL, 0.5) if rng.random() < 0.75 else rng.random()
        upper = rng.random() < 0.5
        expected = _oracle_tail(x, n, p, upper=upper) > Fraction.from_float(target)
        assert _tail_is_greater(x, n, p, target, upper=upper) is expected, (x, n, p, target, upper)


def test_bounds_match_the_fraction_bisection_on_random_counts() -> None:
    rng = random.Random(5)
    cases = [(0, 1), (1, 1), (0, 9), (9, 9), (1, 13), (12, 13)]
    cases += [(rng.randint(0, n), n) for n in (rng.randint(2, 30) for _ in range(14))]
    for x, n in cases:
        tail = rng.choice((MIN_TAIL, GATE_TAIL, rng.uniform(MIN_TAIL, 0.5)))
        assert clopper_pearson_tail(x, n, tail) == _oracle_interval(x, n, tail), (x, n, tail)


# --- 3. Canonical bounds -------------------------------------------------------------------


@pytest.mark.parametrize(("x", "n", "low_hex", "high_hex"), CANONICAL)
def test_canonical_bounds_are_exact(x: int, n: int, low_hex: str, high_hex: str) -> None:
    low, high = clopper_pearson_tail(x, n, GATE_TAIL)
    assert (low.hex(), high.hex()) == (low_hex, high_hex)
    assert (low, high) == (float.fromhex(low_hex), float.fromhex(high_hex))


@pytest.mark.parametrize(("x", "n", "low_hex", "high_hex"), CANONICAL)
def test_canonical_bounds_follow_from_the_fraction_bisection(
    x: int, n: int, low_hex: str, high_hex: str
) -> None:
    low, high = _oracle_interval(x, n, GATE_TAIL)
    assert (low.hex(), high.hex()) == (low_hex, high_hex)


@pytest.mark.parametrize("n", (1, 50, 200))
def test_edge_counts_keep_their_closed_endpoint(n: int) -> None:
    assert clopper_pearson_tail(0, n, GATE_TAIL)[0] == 0.0
    assert clopper_pearson_tail(n, n, GATE_TAIL)[1] == 1.0
    assert clopper_pearson_tail(0, n, GATE_TAIL) == _oracle_interval(0, n, GATE_TAIL)
    assert clopper_pearson_tail(n, n, GATE_TAIL) == _oracle_interval(n, n, GATE_TAIL)


# --- 4. libm independence ------------------------------------------------------------------

LIBM_COUNTS = ((0, 1), (1, 1), (0, 50), (50, 50), (5, 10), (38, 50), (130, 200), (1, 200))


def test_bounds_do_not_call_libm(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = {counts: clopper_pearson_tail(*counts, GATE_TAIL) for counts in LIBM_COUNTS}

    def forbidden(name: str) -> Callable[..., float]:
        def call(*args: object) -> float:
            raise AssertionError(f"math.{name}{args} called")

        return call

    for name in ("log", "log1p", "exp", "lgamma"):
        monkeypatch.setattr(math, name, forbidden(name))

    assert {counts: clopper_pearson_tail(*counts, GATE_TAIL) for counts in LIBM_COUNTS} == expected
    assert clopper_pearson_tail(38, 50, GATE_TAIL) == (
        float.fromhex(CANONICAL[0][2]),
        float.fromhex(CANONICAL[0][3]),
    )
    assert clopper_pearson_tail(10_000, 10_000, MIN_TAIL)[1] == 1.0


# --- 5. Supported range --------------------------------------------------------------------


def _closed_form(x: int, n: int, tail: float) -> tuple[Decimal | None, Decimal | None]:
    """Bounds solvable in closed form (one-term tails), to 40 significant digits."""
    with localcontext() as context:
        context.prec = 40
        t, root = Decimal(tail), Decimal(1) / Decimal(n)
        if x == 0:
            return None, 1 - t**root  # (1 - p)^n = tail
        if x == 1:
            return 1 - (1 - t) ** root, None  # 1 - (1 - p)^n = tail
        if x == n - 1:
            return None, (1 - t) ** root  # 1 - p^n = tail
        if x == n:
            return t**root, None  # p^n = tail
    raise AssertionError("no closed form")


@pytest.mark.parametrize("x", (0, 1, 9_999, 10_000))
def test_largest_supported_n_at_the_minimum_tail(x: int) -> None:
    n = 10_000
    low, high = clopper_pearson_tail(x, n, MIN_TAIL)
    assert 0.0 <= low < high <= 1.0
    for got, reference in zip((low, high), _closed_form(x, n, MIN_TAIL), strict=True):
        if reference is None:
            continue
        error = abs(Fraction.from_float(got) - Fraction(reference))
        # The bisection bracket shrinks to 2**-60 or stalls at one ulp of the bound.
        assert error <= max(Fraction(2) ** -60, 2 * Fraction.from_float(math.ulp(got)))


def test_supported_range_is_enforced() -> None:
    clopper_pearson_tail(1, 10_000, MIN_TAIL)
    with pytest.raises(ValueError):
        clopper_pearson_tail(1, 10_001, MIN_TAIL)
    with pytest.raises(ValueError):
        clopper_pearson_tail(1, 10, math.nextafter(MIN_TAIL, 0.0))
