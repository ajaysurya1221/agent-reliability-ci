from __future__ import annotations

import pytest

from bench.selfcheck import (
    correlated_boundary,
    operating_characteristics,
    sequential_characteristics,
)


def test_operating_characteristics_are_probabilities() -> None:
    result = operating_characteristics(0.8, 0.7, 12)
    assert set(result) == {"PASS", "BLOCK", "INCONCLUSIVE"}
    assert sum(result.values()) == pytest.approx(1.0, abs=1e-12)
    assert all(0.0 <= value <= 1.0 for value in result.values())


def test_correlated_boundary_is_seeded() -> None:
    first = correlated_boundary(0.8, 0.7, 12, 0.5, reps=200, seed=9)
    second = correlated_boundary(0.8, 0.7, 12, 0.5, reps=200, seed=9)
    assert first == second
    assert sum(first.values()) == pytest.approx(1.0)


def test_operating_characteristics_keep_the_published_tail_calibration() -> None:
    result = operating_characteristics(0.95, 0.65, 20)
    assert result["INCONCLUSIVE"] == pytest.approx(0.992345533306, abs=1e-9)


def test_one_sequential_look_equals_the_fixed_design() -> None:
    fixed = operating_characteristics(0.8, 0.7, 30)
    sequential = sequential_characteristics(0.8, 0.7, (30,))

    for outcome in ("PASS", "BLOCK", "INCONCLUSIVE"):
        assert sequential[outcome] == pytest.approx(fixed[outcome], abs=1e-9)
    assert sequential["expected_trials"] == pytest.approx(60.0)
