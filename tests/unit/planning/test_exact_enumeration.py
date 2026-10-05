"""The planner's probabilities are exact integer sums, each rounded to a float exactly once."""

from __future__ import annotations

import json
import math
from fractions import Fraction

import pytest

from arci.planning import (
    DEFAULT_N_GRID,
    OUTCOMES,
    exact_verdict_masses,
    plan,
    plan_to_json,
    verdict_probabilities,
    verdict_table,
)
from arci.schema import Verdict

PASS, BLOCK, INCONCLUSIVE = Verdict.PASS, Verdict.BLOCK, Verdict.INCONCLUSIVE


def _is_power_of_two(value: int) -> bool:
    return value > 0 and value & (value - 1) == 0


@pytest.mark.parametrize(
    ("p_a", "p_b", "n", "alpha", "delta"),
    [
        (0.95, 0.75, 20, 0.05, 0.10),
        (0.95, 0.75, 200, 0.05, 0.10),
        (0.94, 0.77, 400, 0.05, 0.10),
        (0.5, 0.5, 400, 0.05, 0.10),
        (0.0, 1.0, 50, 0.05, 0.10),
        (1.0, 1.0, 13, 0.05, 0.10),
        (1.0, 0.5, 4, 0.5, 0.10),
        (1e-9, 1 - 1e-9, 100, 0.05, 0.10),
        (0.1, 0.3, 37, 0.5, 0.05),
        (0.62, 0.61, 111, 1e-6, 0.3),
    ],
)
def test_exact_numerators_sum_to_the_denominator(
    p_a: float, p_b: float, n: int, alpha: float, delta: float
) -> None:
    numerators, denominator = exact_verdict_masses(p_a, p_b, n, alpha=alpha, delta=delta)
    assert set(numerators) == set(OUTCOMES)
    assert all(numerator >= 0 for numerator in numerators.values())
    assert sum(numerators.values()) == denominator
    # The common denominator is b_A**n * b_B**n, the rates' exact binary denominators.
    assert denominator == Fraction(p_a).denominator ** n * Fraction(p_b).denominator ** n
    assert _is_power_of_two(denominator)


def _pmf(n: int, p: Fraction) -> list[Fraction]:
    return [math.comb(n, x) * p**x * (1 - p) ** (n - x) for x in range(n + 1)]


@pytest.mark.parametrize("n", [1, 7, 30])
@pytest.mark.parametrize(
    ("p_a", "p_b"), [(0.95, 0.75), (0.1, 0.3), (1.0, 0.5), (0.0, 1.0), (0.8, 0.8)]
)
def test_exact_masses_equal_a_rational_oracle(p_a: float, p_b: float, n: int) -> None:
    # The pair masses of the floats' exact binary values, summed per verdict as Fractions.
    baseline, candidate = _pmf(n, Fraction(p_a)), _pmf(n, Fraction(p_b))
    table = verdict_table(n)
    expected: dict[Verdict, Fraction] = dict.fromkeys(OUTCOMES, Fraction(0))
    for a in range(n + 1):
        for b in range(n + 1):
            expected[table[a][b]] += baseline[a] * candidate[b]
    numerators, denominator = exact_verdict_masses(p_a, p_b, n)
    assert {verdict: Fraction(numerators[verdict], denominator) for verdict in OUTCOMES} == expected
    probabilities = verdict_probabilities(p_a, p_b, n)
    assert probabilities == {verdict: float(expected[verdict]) for verdict in OUTCOMES}


@pytest.mark.parametrize(
    ("p_a", "p_b", "n_grid"),
    [
        (0.95, 0.75, DEFAULT_N_GRID),
        (0.999, 0.001, (20, 25)),
        (1.0, 0.0, (1, 20)),
        (0.9, 0.9, (1,)),
    ],
)
def test_json_probabilities_are_the_exact_sums_rounded_once(
    p_a: float, p_b: float, n_grid: tuple[int, ...]
) -> None:
    result = plan(baseline_rate=p_a, candidate_rate=p_b, target_verdict=BLOCK, n_grid=n_grid)
    document = json.loads(json.dumps(plan_to_json(result)))
    for row in document["rows"]:
        numerators, denominator = exact_verdict_masses(p_a, p_b, row["n_per_arm"])
        for verdict in OUTCOMES:
            assert row[verdict.value] == float(Fraction(numerators[verdict], denominator))
        certain = [verdict.value for verdict in OUTCOMES if numerators[verdict] == denominator]
        assert row["certain_verdict"] == (certain[0] if certain else None)


def test_the_brief_example_n_200_row_is_pinned() -> None:
    # The JSON is a pure function of the exact sums, so its full-precision floats are fixed on
    # every platform; these are the correctly rounded values.
    row = plan_to_json(
        plan(baseline_rate=0.95, candidate_rate=0.75, target_verdict=BLOCK, n_grid=(200,))
    )["rows"]
    assert row == [
        {
            "n_per_arm": 200,
            "total_trials": 400,
            "PASS": 6.964950797580904e-10,
            "BLOCK": 0.3647316956588898,
            "INCONCLUSIVE": 0.6352683036446152,
            "certain_verdict": None,
            "meets_target": False,
        }
    ]
