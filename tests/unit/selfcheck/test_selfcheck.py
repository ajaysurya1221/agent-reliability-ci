from __future__ import annotations

import pytest

from bench.selfcheck import correlated_boundary, operating_characteristics


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
