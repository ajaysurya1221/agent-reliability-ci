"""Exact and display-only intervals used by the reliability gate."""

from __future__ import annotations

import math
from statistics import NormalDist

_MAX_N = 10_000
_BISECTION_STEPS = 60
_MIN_TAIL = 2.5e-7


def _validate_counts(successes: int, n: int) -> None:
    if n < 1 or n > _MAX_N:
        raise ValueError("n must be between 1 and 10000")
    if successes < 0 or successes > n:
        raise ValueError("successes must be between 0 and n")


def _validate(successes: int, n: int, confidence: float) -> None:
    _validate_counts(successes, n)
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must be strictly between 0 and 1")


def _log_binomial_sum(start: int, stop: int, n: int, p: float) -> float:
    """Log-sum binomial probabilities for ``start <= X < stop``."""
    log_p = math.log(p)
    log_q = math.log1p(-p)
    log_n_factorial = math.lgamma(n + 1)
    logs = [
        log_n_factorial - math.lgamma(k + 1) - math.lgamma(n - k + 1) + k * log_p + (n - k) * log_q
        for k in range(start, stop)
    ]
    largest = max(logs)
    return largest + math.log(math.fsum(math.exp(value - largest) for value in logs))


def _tail_is_greater(x: int, n: int, p: float, target: float, *, upper: bool) -> bool:
    """Compare one binomial tail with ``target`` without subtracting a CDF.

    The smaller-probability side is log-summed. When that is the complement of
    the requested tail, the comparison is reversed against ``1 - target`` in
    log space, so no rounded probability is subtracted from one.
    """
    if p <= 0.0:
        return not upper
    if p >= 1.0:
        return upper

    # floor(np + p) is a binomial median. It identifies which side has at most
    # half the mass, including the only ambiguous point around the mean.
    median = math.floor(n * p + p)
    log_target = math.log(target)
    log_complement_target = math.log1p(-target)
    if upper:
        if x > median:
            return _log_binomial_sum(x, n + 1, n, p) > log_target
        return _log_binomial_sum(0, x, n, p) < log_complement_target
    if x < median:
        return _log_binomial_sum(0, x + 1, n, p) > log_target
    return _log_binomial_sum(x + 1, n + 1, n, p) < log_complement_target


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

    if successes == 0:
        low = 0.0
        high = 1.0 - tail ** (1.0 / n)
    elif successes == n:
        low = tail ** (1.0 / n)
        high = 1.0
    else:
        low = _tail_root(successes, n, tail, upper=True)
        high = _tail_root(successes, n, tail, upper=False)
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
    z = NormalDist().inv_cdf((1.0 + confidence) / 2.0)
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
