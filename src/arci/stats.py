"""Exact and display-only intervals used by the reliability gate."""

from __future__ import annotations

import math
from statistics import NormalDist

_MAX_N = 10_000
_BISECTION_STEPS = 60
_MIN_TAIL = 2.5e-7
# Match CPython's Python fallback for reproducible 95% Wilson intervals.
_WILSON_Z_95 = 1.9599639845400536


def _validate_counts(successes: int, n: int) -> None:
    if n < 1 or n > _MAX_N:
        raise ValueError("n must be between 1 and 10000")
    if successes < 0 or successes > n:
        raise ValueError("successes must be between 0 and n")


def _validate(successes: int, n: int, confidence: float) -> None:
    _validate_counts(successes, n)
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must be strictly between 0 and 1")


def _compare_binomial_prefix(m: int, n: int, a: int, b: int, t: int, d: int) -> int:
    """Compare P(X <= m) with t/d, for p=a/b and power-of-two b."""
    if m < 0:
        return -1

    q = b - a
    term = math.comb(n, m) * a**m * q ** (n - m)
    total = term
    scale = 1 << (n * (b.bit_length() - 1))
    threshold = scale * t

    while True:
        scaled = total * d
        if scaled > threshold:
            return 1
        if m == 0:
            return (scaled > threshold) - (scaled < threshold)

        numerator = m * q
        denominator = (n - m + 1) * a

        # Remaining descending terms have decreasing ratios. Their sum
        # is bounded above by term * r / (1-r), when r < 1.
        if numerator < denominator:
            gap = denominator - numerator
            if scaled * gap + term * d * numerator < threshold * gap:
                return -1

        # Exact division: this is the next integer binomial numerator.
        term = term * numerator // denominator
        total += term
        m -= 1


def _tail_is_greater(x: int, n: int, p: float, target: float, *, upper: bool) -> bool:
    """Compare a binomial tail exactly at the supplied binary64 inputs."""
    if p <= 0.0:
        return x == 0 if upper else True
    if p >= 1.0:
        return True if upper else x == n

    a, b = p.as_integer_ratio()
    t, d = target.as_integer_ratio()
    cutoff = x - 1 if upper else x
    complement = upper

    # Reflect when needed so descending terms decrease from the start.
    # Form complements as integers, without rounded float subtraction.
    if cutoff * b > (n + 1) * a:
        cutoff = n - cutoff - 1
        a = b - a
        complement = not complement

    if complement:
        return _compare_binomial_prefix(cutoff, n, a, b, d - t, d) < 0
    return _compare_binomial_prefix(cutoff, n, a, b, t, d) > 0


def _tail_root(x: int, n: int, target: float, *, upper: bool) -> float:
    """Solve a binomial upper or lower tail equation by bisection."""
    low = 0.0
    high = 1.0
    for _ in range(_BISECTION_STEPS):
        midpoint = (low + high) / 2.0
        greater = _tail_is_greater(x, n, midpoint, target, upper=upper)
        if upper:
            if greater:
                high = midpoint
            else:
                low = midpoint
        elif greater:
            low = midpoint
        else:
            high = midpoint
    return (low + high) / 2.0


def clopper_pearson_tail(successes: int, n: int, tail: float) -> tuple[float, float]:
    """Return an exact interval by directly inverting each tail probability."""
    _validate_counts(successes, n)
    if not _MIN_TAIL <= tail < 0.5:
        raise ValueError("tail must be between 2.5e-7 (inclusive) and 0.5 (exclusive)")

    low = 0.0 if successes == 0 else _tail_root(successes, n, tail, upper=True)
    high = 1.0 if successes == n else _tail_root(successes, n, tail, upper=False)
    return low, high


def clopper_pearson(successes: int, n: int, confidence: float) -> tuple[float, float]:
    """Return the equal-tailed exact binomial confidence interval."""
    _validate(successes, n, confidence)
    tail = (1.0 - confidence) / 2.0
    return clopper_pearson_tail(successes, n, tail)


def wilson(successes: int, n: int, confidence: float = 0.95) -> tuple[float, float]:
    """Return the Wilson score interval used for display only."""
    _validate(successes, n, confidence)
    rate = successes / n
    z = _WILSON_Z_95 if confidence == 0.95 else NormalDist().inv_cdf((1.0 + confidence) / 2.0)
    z_squared = z * z
    denominator = 1.0 + z_squared / n
    centre = (rate + z_squared / (2.0 * n)) / denominator
    radius = z * math.sqrt(rate * (1.0 - rate) / n + z_squared / (4.0 * n * n)) / denominator
    return centre - radius, centre + radius


def newcombe(
    successes_a: int, n_a: int, successes_b: int, n_b: int, confidence: float
) -> tuple[float, float]:
    """Newcombe's hybrid score interval (method 10) for p_b - p_a, no continuity correction.

    Wilson intervals per arm at `confidence`, combined through their asymmetric distances from
    the observed rates. Approximate; calibration is checked by enumeration in bench/selfcheck.py.
    """
    low_a, high_a = wilson(successes_a, n_a, confidence)
    low_b, high_b = wilson(successes_b, n_b, confidence)
    rate_a, rate_b = successes_a / n_a, successes_b / n_b
    difference = rate_b - rate_a
    lower = difference - math.sqrt((rate_b - low_b) ** 2 + (high_a - rate_a) ** 2)
    upper = difference + math.sqrt((high_b - rate_b) ** 2 + (rate_a - low_a) ** 2)
    return max(-1.0, lower), min(1.0, upper)


def per_arm_confidence(alpha: float, k: int) -> float:
    """Return the Bonferroni-adjusted confidence for one arm."""
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be strictly between 0 and 1")
    if k < 1:
        raise ValueError("k must be at least 1")
    return 1.0 - alpha / (2.0 * k)


def difference_bounds(
    *, baseline: tuple[float, float], candidate: tuple[float, float]
) -> tuple[float, float]:
    """Bound candidate probability minus baseline probability."""
    baseline_low, baseline_high = baseline
    candidate_low, candidate_high = candidate
    return candidate_low - baseline_high, candidate_high - baseline_low
