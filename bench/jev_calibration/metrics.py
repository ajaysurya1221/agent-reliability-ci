"""Estimators for the audit, on plain sequences so they can be unit tested by hand.

The exact binomial interval is implemented here (regularised incomplete beta by continued
fraction, inverted by bisection) because `arci.stats.clopper_pearson` caps n at 10,000 and the
pooled passes exceed it; the unit tests check it against `arci.stats` inside that range. Ties
are handled explicitly because the API returns probabilities to two decimals.
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class Bin:
    lower: float
    upper: float
    count: int
    mean_score: float
    accuracy: float


@dataclass(frozen=True)
class Selective:
    threshold: float
    covered: int
    accuracy_covered: float
    accuracy_rest: float


def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction for the incomplete beta function (modified Lentz)."""

    tiny = 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) >= tiny else tiny)
    h = d
    for m in range(1, 400):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) >= tiny else tiny)
        c = 1.0 + aa / (c if abs(c) >= tiny else tiny)
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) >= tiny else tiny)
        c = 1.0 + aa / (c if abs(c) >= tiny else tiny)
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-15:
            break
    return h


def regularized_incomplete_beta(a: float, b: float, x: float) -> float:
    """I_x(a, b) for a, b > 0 and x in [0, 1]."""

    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    log_front = (
        math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x)
    )
    front = math.exp(log_front)
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def beta_quantile(p: float, a: float, b: float) -> float:
    """The x with I_x(a, b) = p, by bisection to 1e-12."""

    low, high = 0.0, 1.0
    for _ in range(200):
        mid = (low + high) / 2
        if regularized_incomplete_beta(a, b, mid) < p:
            low = mid
        else:
            high = mid
        if high - low < 1e-12:
            break
    return (low + high) / 2


def clopper_pearson(successes: int, n: int, confidence: float = 0.95) -> tuple[float, float]:
    """Exact two-sided binomial interval for any n >= 1."""

    if n < 1 or not 0 <= successes <= n:
        raise ValueError("need 0 <= successes <= n and n >= 1")
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must be in (0, 1)")
    alpha = 1.0 - confidence
    low = 0.0 if successes == 0 else beta_quantile(alpha / 2, successes, n - successes + 1)
    high = 1.0 if successes == n else beta_quantile(1 - alpha / 2, successes + 1, n - successes)
    return low, high


def accuracy_interval(
    correct: Sequence[bool], confidence: float = 0.95
) -> tuple[float, float, float]:
    """(rate, lower, upper): the rate with its two-sided exact Clopper-Pearson interval."""
    n = len(correct)
    if n == 0:
        raise ValueError("accuracy of an empty sequence")
    successes = sum(1 for c in correct if c)
    low, high = clopper_pearson(successes, n, confidence)
    return successes / n, low, high


def reliability_bins(scores: Sequence[float], correct: Sequence[bool], bins: int = 15) -> list[Bin]:
    """Equal-width bins over [0, 1]; a score of exactly 1 falls in the last bin."""
    if len(scores) != len(correct):
        raise ValueError("scores and correct differ in length")
    counts = [0] * bins
    score_sums = [0.0] * bins
    hits = [0] * bins
    for score, hit in zip(scores, correct, strict=True):
        if not 0.0 <= score <= 1.0:
            raise ValueError(f"score {score} outside [0, 1]")
        index = min(int(score * bins), bins - 1)
        counts[index] += 1
        score_sums[index] += score
        hits[index] += 1 if hit else 0
    return [
        Bin(
            lower=i / bins,
            upper=(i + 1) / bins,
            count=counts[i],
            mean_score=score_sums[i] / counts[i] if counts[i] else math.nan,
            accuracy=hits[i] / counts[i] if counts[i] else math.nan,
        )
        for i in range(bins)
    ]


def ece(scores: Sequence[float], correct: Sequence[bool], bins: int = 15) -> float:
    n = len(scores)
    if n == 0:
        raise ValueError("ECE of an empty sequence")
    return sum(
        b.count / n * abs(b.accuracy - b.mean_score)
        for b in reliability_bins(scores, correct, bins)
        if b.count
    )


def mce(scores: Sequence[float], correct: Sequence[bool], bins: int = 15) -> float:
    gaps = [
        abs(b.accuracy - b.mean_score) for b in reliability_bins(scores, correct, bins) if b.count
    ]
    return max(gaps) if gaps else math.nan


def brier(scores: Sequence[float], correct: Sequence[bool]) -> float:
    if not scores:
        raise ValueError("Brier score of an empty sequence")
    return sum((s - (1.0 if c else 0.0)) ** 2 for s, c in zip(scores, correct, strict=True)) / len(
        scores
    )


def log_loss(true_probabilities: Sequence[float], clip: float = 0.005) -> float:
    """Mean negative log of the probability given to the true label, floored at `clip`."""
    if not true_probabilities:
        raise ValueError("log loss of an empty sequence")
    return -sum(math.log(max(p, clip)) for p in true_probabilities) / len(true_probabilities)


def _average_ranks(values: Sequence[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    start = 0
    while start < len(order):
        end = start
        while end + 1 < len(order) and values[order[end + 1]] == values[order[start]]:
            end += 1
        rank = (start + end) / 2 + 1  # 1-based average rank of the tied block
        for position in range(start, end + 1):
            ranks[order[position]] = rank
        start = end + 1
    return ranks


def auroc(scores: Sequence[float], positives: Sequence[bool]) -> float:
    """Probability that a random positive outranks a random negative; ties count one half."""
    n_pos = sum(1 for p in positives if p)
    n_neg = len(positives) - n_pos
    if n_pos == 0 or n_neg == 0:
        return math.nan
    ranks = _average_ranks(scores)
    rank_sum = sum(r for r, p in zip(ranks, positives, strict=True) if p)
    return (rank_sum - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)


def average_precision(scores: Sequence[float], positives: Sequence[bool]) -> float:
    """Area under the precision-recall curve stepped at each distinct score, positives first."""
    n_pos = sum(1 for p in positives if p)
    if n_pos == 0:
        return math.nan
    order = sorted(range(len(scores)), key=lambda i: -scores[i])
    tp = fp = 0
    previous_recall = 0.0
    total = 0.0
    index = 0
    while index < len(order):
        block_end = index
        while block_end + 1 < len(order) and scores[order[block_end + 1]] == scores[order[index]]:
            block_end += 1
        for position in range(index, block_end + 1):
            if positives[order[position]]:
                tp += 1
            else:
                fp += 1
        recall = tp / n_pos
        precision = tp / (tp + fp)
        total += (recall - previous_recall) * precision
        previous_recall = recall
        index = block_end + 1
    return total


def fpr_at_tpr(scores: Sequence[float], positives: Sequence[bool], tpr: float = 0.95) -> float:
    """False-positive rate at the lowest threshold that still recalls `tpr` of the positives."""
    positive_scores = sorted((s for s, p in zip(scores, positives, strict=True) if p), reverse=True)
    negative_scores = [s for s, p in zip(scores, positives, strict=True) if not p]
    if not positive_scores or not negative_scores:
        return math.nan
    needed = math.ceil(tpr * len(positive_scores))
    threshold = positive_scores[max(needed, 1) - 1]
    return sum(1 for s in negative_scores if s >= threshold) / len(negative_scores)


def selective(scores: Sequence[float], correct: Sequence[bool], threshold: float) -> Selective:
    """Accuracy when items scoring below `threshold` are abstained."""
    covered = [c for s, c in zip(scores, correct, strict=True) if s >= threshold]
    rest = [c for s, c in zip(scores, correct, strict=True) if s < threshold]
    return Selective(
        threshold=threshold,
        covered=len(covered),
        accuracy_covered=sum(covered) / len(covered) if covered else math.nan,
        accuracy_rest=sum(rest) / len(rest) if rest else math.nan,
    )


def threshold_for_coverage(scores: Sequence[float], coverage: float) -> float:
    """The score at or above which at least `coverage` of the items lie."""
    if not 0.0 < coverage <= 1.0:
        raise ValueError("coverage must be in (0, 1]")
    ordered = sorted(scores, reverse=True)
    index = min(len(ordered) - 1, max(0, math.ceil(coverage * len(ordered)) - 1))
    return ordered[index]


def bootstrap_interval(
    statistic: Callable[[Sequence[int]], float],
    n_items: int,
    resamples: int = 1000,
    seed: int = 0,
    level: float = 0.95,
) -> tuple[float, float]:
    """Percentile interval of `statistic` over resampled index lists."""
    rng = random.Random(seed)
    values = sorted(
        statistic([rng.randrange(n_items) for _ in range(n_items)]) for _ in range(resamples)
    )
    return percentile(values, (1 - level) / 2), percentile(values, 1 - (1 - level) / 2)


def percentile(values: Sequence[float], q: float) -> float:
    """Linear-interpolation percentile, `q` in [0, 1], on an unsorted sequence."""
    if not values:
        raise ValueError("percentile of an empty sequence")
    if not 0.0 <= q <= 1.0:
        raise ValueError("q must be in [0, 1]")
    ordered = sorted(values)
    position = q * (len(ordered) - 1)
    low = math.floor(position)
    high = math.ceil(position)
    if low == high:
        return ordered[low]
    weight = position - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


def agreement(first: Sequence[str], second: Sequence[str]) -> float:
    if not first:
        raise ValueError("agreement of empty sequences")
    return sum(1 for a, b in zip(first, second, strict=True) if a == b) / len(first)


def mean_abs_diff(first: Sequence[float], second: Sequence[float]) -> float:
    if not first:
        raise ValueError("mean absolute difference of empty sequences")
    return sum(abs(a - b) for a, b in zip(first, second, strict=True)) / len(first)


def choice_confidence(probabilities: Sequence[float]) -> float:
    """The vendor's Choice confidence: how far the top probability sits above an even split."""
    n = len(probabilities)
    if n < 2:
        raise ValueError("a Choice needs at least two options")
    return (max(probabilities) - 1 / n) / (1 - 1 / n)
