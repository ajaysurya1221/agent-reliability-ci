"""Hand-checked cases for the audit's estimators."""

from __future__ import annotations

import math

import pytest

from bench.jev_calibration.metrics import (
    accuracy_interval,
    agreement,
    auroc,
    average_precision,
    bootstrap_interval,
    brier,
    choice_confidence,
    ece,
    fpr_at_tpr,
    log_loss,
    mce,
    mean_abs_diff,
    percentile,
    reliability_bins,
    selective,
    threshold_for_coverage,
)


def test_accuracy_interval_is_exact_clopper_pearson() -> None:
    rate, low, high = accuracy_interval([True] * 95 + [False] * 5)
    assert rate == 0.95
    assert low == pytest.approx(0.8872, abs=0.001)
    assert high == pytest.approx(0.9836, abs=0.001)
    with pytest.raises(ValueError):
        accuracy_interval([])


def test_reliability_bins_and_ece_by_hand() -> None:
    scores = [0.95, 0.95, 0.95, 0.95, 0.55, 0.55, 0.05, 0.05]
    correct = [True, True, True, False, True, False, False, False]
    bins = reliability_bins(scores, correct, bins=10)
    assert sum(b.count for b in bins) == 8
    top = bins[9]
    assert top.count == 4 and top.mean_score == pytest.approx(0.95) and top.accuracy == 0.75
    middle = bins[5]
    assert middle.count == 2 and middle.accuracy == 0.5
    bottom = bins[0]
    assert bottom.count == 2 and bottom.accuracy == 0.0
    expected = (4 / 8) * abs(0.75 - 0.95) + (2 / 8) * abs(0.5 - 0.55) + (2 / 8) * abs(0.0 - 0.05)
    assert ece(scores, correct, bins=10) == pytest.approx(expected)
    assert mce(scores, correct, bins=10) == pytest.approx(0.2)


def test_score_of_exactly_one_lands_in_the_last_bin() -> None:
    bins = reliability_bins([1.0, 0.0], [True, False], bins=15)
    assert bins[-1].count == 1 and bins[0].count == 1
    with pytest.raises(ValueError):
        reliability_bins([1.2], [True])


def test_brier_and_log_loss() -> None:
    assert brier([1.0, 0.0, 0.5], [True, False, True]) == pytest.approx((0 + 0 + 0.25) / 3)
    assert log_loss([1.0, 0.5]) == pytest.approx((0 + math.log(2)) / 2)
    assert log_loss([0.0], clip=0.005) == pytest.approx(-math.log(0.005))


def test_auroc_with_and_without_ties() -> None:
    assert auroc([0.9, 0.8, 0.3, 0.1], [True, True, False, False]) == 1.0
    assert auroc([0.1, 0.3, 0.8, 0.9], [True, True, False, False]) == 0.0
    # Four positive-negative pairs: three ordered correctly, one tied (counts one half).
    assert auroc([0.9, 0.5, 0.5, 0.1], [True, True, False, False]) == pytest.approx(3.5 / 4)
    assert math.isnan(auroc([0.5, 0.5], [True, True]))


def test_average_precision_steps_on_distinct_scores() -> None:
    # Ranking: pos, neg, pos -> precision 1.0 at recall 0.5, then 2/3 at recall 1.0.
    assert average_precision([0.9, 0.8, 0.7], [True, False, True]) == pytest.approx(
        0.5 * 1.0 + 0.5 * (2 / 3)
    )
    # Two items tied at the top, one positive one negative: a single block at precision 0.5.
    assert average_precision([0.9, 0.9, 0.1], [True, False, False]) == pytest.approx(0.5)


def test_fpr_at_tpr() -> None:
    scores = [0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1, 0.05]
    positives = [True, True, True, True, True, False, False, False, False, False]
    # Recalling 95% of 5 positives needs all 5 -> threshold 0.5 -> no negative at or above it.
    assert fpr_at_tpr(scores, positives, tpr=0.95) == 0.0
    # Recalling 40% needs 2 -> threshold 0.8 -> still no negatives above.
    assert fpr_at_tpr(scores, positives, tpr=0.4) == 0.0
    mixed = [0.9, 0.2, 0.8, 0.85, 0.1]
    mixed_pos = [True, True, False, False, False]
    # Full recall needs the positive at 0.2, so both 0.8 and 0.85 negatives count: 2 of 3.
    assert fpr_at_tpr(mixed, mixed_pos, tpr=1.0) == pytest.approx(2 / 3)


def test_selective_and_coverage_threshold() -> None:
    scores = [0.9, 0.8, 0.7, 0.2]
    correct = [True, True, False, False]
    result = selective(scores, correct, 0.7)
    assert result.covered == 3
    assert result.accuracy_covered == pytest.approx(2 / 3)
    assert result.accuracy_rest == 0.0
    assert threshold_for_coverage(scores, 0.5) == 0.8
    assert threshold_for_coverage(scores, 1.0) == 0.2
    with pytest.raises(ValueError):
        threshold_for_coverage(scores, 0.0)


def test_percentile_interpolates_like_numpy_default() -> None:
    values = [1.0, 2.0, 3.0, 4.0]
    assert percentile(values, 0.5) == 2.5
    assert percentile(values, 0.0) == 1.0
    assert percentile(values, 1.0) == 4.0
    assert percentile(values, 0.25) == 1.75


def test_bootstrap_interval_brackets_the_mean() -> None:
    data = [1.0] * 50 + [0.0] * 50

    def mean_of(indices: list[int] | tuple[int, ...]) -> float:
        return sum(data[i] for i in indices) / len(indices)

    low, high = bootstrap_interval(lambda idx: mean_of(list(idx)), len(data), resamples=400, seed=1)
    assert low < 0.5 < high
    assert low > 0.35 and high < 0.65


def test_agreement_and_mean_abs_diff() -> None:
    assert agreement(["a", "b", "c"], ["a", "x", "c"]) == pytest.approx(2 / 3)
    assert mean_abs_diff([0.1, 0.5], [0.3, 0.5]) == pytest.approx(0.1)


def test_choice_confidence_matches_the_documented_examples() -> None:
    assert choice_confidence([0.6, 0.3, 0.1]) == pytest.approx(0.4)
    assert choice_confidence([0.6, 0.2, 0.2]) == pytest.approx(0.4)
    assert choice_confidence([1.0, 0.0, 0.0]) == pytest.approx(1.0)
    assert choice_confidence([0.88, 0.12, 0.0]) == pytest.approx(0.82)
