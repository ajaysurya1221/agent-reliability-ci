"""Tests belong to the isolated spike, as explicitly required by the S1 brief."""

from __future__ import annotations

from collections import defaultdict
from fractions import Fraction
from itertools import product

import pytest
from suite_stats import (
    RULES,
    Checkpoint,
    Plan,
    StakeRule,
    adaptive_stakes,
    classify,
    count_wealth,
    decide,
)
from suite_stats_sim import (
    binomial_cdf_le,
    binomial_upper,
    boundary_verdict,
    cell_probabilities,
    characteristics,
    fast_decide,
    golden_check,
    joint,
    make_boundary,
    make_cells,
    simulate_cells,
    summarize,
)

F = Fraction


def test_golden_inclusive_threshold_and_exact_history() -> None:
    rule = StakeRule("fixed", (F(1),))
    result = decide([1] * 10, alpha=F(1, 2), delta=F(1, 2), batch=1, max_pairs=10, rule=rule)
    assert result.verdict == "PASS"
    assert result.stopping_pairs == 1
    assert result.history == (Checkpoint(1, F(4), F(0)),)


def test_golden_block_and_zero_factors() -> None:
    rule = StakeRule("fixed", (F(1),))
    result = decide([-1] * 10, alpha=F(1, 2), delta=F(1, 2), batch=1, max_pairs=10, rule=rule)
    assert result.verdict == "BLOCK"
    assert result.stopping_pairs == 5
    assert result.history[-1] == Checkpoint(5, F(0), F(1024, 243))


def test_golden_mixture_is_average_of_products() -> None:
    rule = StakeRule("mixture", (F(1, 4), F(1, 2)))
    result = decide([1] * 10, alpha=F(1, 2), delta=F(1, 2), batch=1, max_pairs=10, rule=rule)
    assert (result.verdict, result.stopping_pairs) == ("PASS", 2)
    assert result.history[-1] == Checkpoint(2, F(149, 32), F(13, 32))


def test_final_partial_batch_and_first_checkpoint_only() -> None:
    result = decide([1] * 13, batch=10, max_pairs=13)
    assert result.verdict == "PASS"
    assert result.stopping_pairs == 10
    tiny = decide([0] * 13, batch=10, max_pairs=13)
    assert tiny.verdict == "INCONCLUSIVE"
    assert [row.pairs for row in tiny.history] == [10, 13]
    assert decide([0] * 13, batch=20, max_pairs=13).stopping_pairs == 13


def test_error_collision_is_explicit() -> None:
    assert classify(F(40), F(40), F(1, 20)) == "ERROR"
    assert classify(F(40) - F(1, 10**100), F(1), F(1, 20)) == "INCONCLUSIVE"


@pytest.mark.parametrize("stream", [[2], [-2], [True], [0, False]])
def test_reject_invalid_outcomes(stream: list[int]) -> None:
    with pytest.raises(ValueError, match="each difference"):
        decide(stream, max_pairs=1)


def test_reject_missing_pairs_without_turning_them_into_zeroes() -> None:
    with pytest.raises(ValueError, match="incomplete"):
        decide([0] * 9, max_pairs=10)


@pytest.mark.parametrize("value", [F(0), F(1), F(-1)])
def test_reject_invalid_alpha_and_delta(value: Fraction) -> None:
    with pytest.raises(ValueError):
        Plan(alpha=value)
    with pytest.raises(ValueError):
        Plan(delta=value)


def test_reject_invalid_counts_and_stakes() -> None:
    with pytest.raises(ValueError):
        Plan(batch=0)
    with pytest.raises(ValueError):
        Plan(max_pairs=0)
    with pytest.raises(ValueError):
        StakeRule("mixture", ())
    with pytest.raises(ValueError):
        StakeRule("fixed", (F(2),))
    with pytest.raises(ValueError):
        count_wealth(2, 2, 1, Plan())
    with pytest.raises(ValueError):
        count_wealth(2, 0, 0, Plan(rule=RULES["adaptive"]))


def test_adaptive_stakes_are_predictable_bounded_rationals() -> None:
    assert adaptive_stakes(F(0), F(0), F(1, 10)) == (0, 0)
    for total in range(-100, 101):
        plus, minus = adaptive_stakes(F(total), F(100), F(1, 10))
        assert isinstance(plus, Fraction) and isinstance(minus, Fraction)
        assert 0 <= plus <= F(10, 9)
        assert 0 <= minus <= F(10, 11)
        assert (plus * F(9, 10) * 64).denominator == 1
        assert (minus * F(11, 10) * 64).denominator == 1
    for d in (-1, 0, 1):
        result = decide([d], batch=1, max_pairs=1, rule=RULES["adaptive"])
        assert result.history == (Checkpoint(1, F(1), F(1)),)


def test_count_reduction_is_not_valid_for_general_adaptive_rule() -> None:
    first = decide([1, 0, -1, 0], batch=4, max_pairs=4, rule=RULES["adaptive"])
    second = decide([-1, 0, 1, 0], batch=4, max_pairs=4, rule=RULES["adaptive"])
    assert first.history != second.history


@pytest.mark.parametrize("rule_name", ["fixed", "mixture"])
def test_integer_frontier_matches_rational_wealth_exhaustively(rule_name: str) -> None:
    plan = Plan(alpha=F(1, 2), delta=F(1, 3), max_pairs=25, rule=RULES[rule_name])
    for n in range(1, 26):
        boundary = make_boundary((plan, n))[1]
        for m in range(n + 1):
            for p in range(n - m + 1):
                plus, minus = count_wealth(n, m, p, plan)
                assert boundary_verdict(boundary, m, p) == classify(plus, minus, plan.alpha)


@pytest.mark.parametrize("batch", [1, 3, 10])
def test_absorbing_dp_matches_exhaustive_ordered_paths(batch: int) -> None:
    probabilities = (F(1, 4), F(1, 2), F(1, 4))
    plan = Plan(alpha=F(1, 2), delta=F(1, 3), batch=batch, max_pairs=6)
    brute: defaultdict[str, Fraction] = defaultdict(Fraction)
    expected = F(0)
    for path in product((-1, 0, 1), repeat=6):
        mass = F(1)
        for d in path:
            mass *= probabilities[d + 1]
        decision = decide(path, alpha=plan.alpha, delta=plan.delta, batch=batch, max_pairs=6)
        brute[decision.verdict] += mass
        expected += decision.stopping_pairs * mass
    row = characteristics(probabilities, plan)[0]
    assert F(row["lost"]) == 0
    assert sum(F(p) for p in row["lower"].values()) == 1
    for verdict, p in row["lower"].items():
        assert F(p) == brute[verdict]
        assert row["lower"][verdict] == row["upper"][verdict]
    assert row["summary"]["mean"] == float(expected)


def test_enclosure_contains_exact_probability_and_accounts_for_every_loss() -> None:
    probabilities = (F(1, 5), F(7, 10), F(1, 10))
    plan = Plan(alpha=F(1, 2), max_pairs=20, batch=3)
    exact = characteristics(probabilities, plan)[0]
    bounded = characteristics(probabilities, plan, bits=12)[0]
    assert F(bounded["lost"]) > 0
    assert sum(F(p) for p in bounded["lower"].values()) + F(bounded["lost"]) == 1
    for verdict in exact["lower"]:
        assert F(bounded["lower"][verdict]) <= F(exact["lower"][verdict])
        assert F(exact["upper"][verdict]) <= F(bounded["upper"][verdict])


def test_extra_terminal_cap_does_not_change_longer_plan() -> None:
    probabilities = (F(1, 5), F(7, 10), F(1, 10))
    plan = Plan(alpha=F(1, 2), max_pairs=30, batch=10)
    rows = characteristics(probabilities, plan, caps=(15, 30))
    assert rows[-1] == characteristics(probabilities, plan)[0]
    shorter = Plan(alpha=F(1, 2), max_pairs=15, batch=10)
    assert rows[0] == characteristics(probabilities, shorter)[0]


def test_sampler_marginals_dependence_and_exact_suite_boundary() -> None:
    for tasks in (10, 20, 50, 100):
        for k in (1, 3):
            for difficulty in ("equal", "mixed", "concentrated"):
                for dependence in ("independent", "positive", "negative"):
                    cells = make_cells(tasks, k, difficulty, dependence)
                    minus, zero, plus = cell_probabilities(cells)
                    assert plus - minus == -F(1, 10)
                    assert minus + zero + plus == 1
                    for cell in cells:
                        j = joint(cell.a, cell.b, dependence)
                        assert sum(j) == 1 and min(j) >= 0
                        assert j[1] + j[3] == cell.a
                        assert j[2] + j[3] == cell.b


def test_seeded_cell_sampler_is_repeatable() -> None:
    plan = Plan(max_pairs=30)
    cells = make_cells(10, 3, "concentrated", "negative")
    boundaries = dict(make_boundary((plan, n)) for n in (10, 20, 30))
    assert simulate_cells(cells, plan, boundaries, 200, 71) == simulate_cells(
        cells, plan, boundaries, 200, 71
    )


def test_exact_binomial_upper_matches_known_extremes() -> None:
    upper = binomial_upper(0, 20)
    assert (1 - upper) ** 20 <= F(1, 100)
    assert (1 - (upper - F(1, 2**20))) ** 20 > F(1, 100)
    assert binomial_upper(20, 20) == 1
    assert binomial_cdf_le(0, 2, 1, 2, F(1, 4))
    assert not binomial_cdf_le(0, 2, 1, 2, F(1, 5))
    assert binomial_upper(3, 20) < binomial_upper(4, 20)


def test_float_exact_agreement_on_golden_corpus() -> None:
    assert golden_check() == 351


def test_stopping_quantiles_use_integer_cumulative_mass() -> None:
    # Summing nine binary64 copies of .1 is below .9; integer mass must still stop at 90.
    row = summarize(
        {"PASS": 1.0, "BLOCK": 0.0, "INCONCLUSIVE": 0.0, "ERROR": 0.0},
        {10 * n: 1 for n in range(1, 11)},
        10,
    )
    assert row["median"] == 50
    assert row["p90"] == 90
    assert row["mean"] == 55


def test_float_exact_threshold_fallback_and_nondefault_delta() -> None:
    for rule in (StakeRule("fixed", (F(1),)), RULES["adaptive"]):
        plan = Plan(alpha=F(1, 2), delta=F(1, 2), batch=1, max_pairs=50, rule=rule)
        for path in ([1] * 50, [-1] * 50, [0] * 50, [1, 0, -1, 0, 0] * 10):
            exact = decide(
                path, alpha=plan.alpha, delta=plan.delta, batch=1, max_pairs=50, rule=rule
            )
            assert fast_decide(path, plan) == (exact.verdict, exact.stopping_pairs)
