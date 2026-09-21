"""Exact and display-only intervals used by the reliability gate."""

from __future__ import annotations

import math
from statistics import NormalDist

_MAX_N = 10_000
_BISECTION_STEPS = 60


def _validate(successes: int, n: int, confidence: float) -> None:
    if n < 1 or n > _MAX_N:
        raise ValueError("n must be between 1 and 10000")
    if successes < 0 or successes > n:
        raise ValueError("successes must be between 0 and n")
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must be strictly between 0 and 1")


def _binomial_cdf(x: int, n: int, p: float) -> float:
    """Return P(X <= x) by log-summing the exact binomial terms."""
    if x < 0:
        return 0.0
    if x >= n:
        return 1.0
    if p <= 0.0:
        return 1.0
    if p >= 1.0:
        return 0.0

    log_p = math.log(p)
    log_q = math.log1p(-p)
    log_n_factorial = math.lgamma(n + 1)
    logs = [
        log_n_factorial - math.lgamma(k + 1) - math.lgamma(n - k + 1) + k * log_p + (n - k) * log_q
        for k in range(x + 1)
    ]
    largest = max(logs)
    return math.exp(largest) * math.fsum(math.exp(value - largest) for value in logs)


def _cdf_root(x: int, n: int, target: float) -> float:
    """Solve binomial_cdf(x, n, p) == target for p."""
    low = 0.0
    high = 1.0
    for _ in range(_BISECTION_STEPS):
        midpoint = (low + high) / 2.0
        if _binomial_cdf(x, n, midpoint) > target:
            low = midpoint
        else:
            high = midpoint
    return (low + high) / 2.0


def clopper_pearson(successes: int, n: int, confidence: float) -> tuple[float, float]:
    """Return the equal-tailed exact binomial confidence interval."""
    _validate(successes, n, confidence)
    tail = (1.0 - confidence) / 2.0
    low = 0.0 if successes == 0 else _cdf_root(successes - 1, n, 1.0 - tail)
    high = 1.0 if successes == n else _cdf_root(successes, n, tail)
    return low, high


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
