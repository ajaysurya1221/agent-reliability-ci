"""Independent path checks for the balanced statistical spike."""

from fractions import Fraction as F
from itertools import product

import pytest
from balanced import balanced_plan, decide_rounds, enumerate_laws, round_kernel
from stake_selection import CANDIDATES
from suite_stats import Plan, decide


def test_no_partial_round() -> None:
    with pytest.raises(ValueError, match="complete"):
        decide_rounds([[0] * 20, [0] * 19], 20)


def test_floors_and_midround_counterexample() -> None:
    rounds = [[0] * 20 for _ in range(20)]
    result = decide_rounds(rounds, 20)
    assert (result.verdict, result.stopping_pairs) == ("PASS", 80)
    ordered = [1] * 9 + [-1] * 11
    assert decide(ordered, batch=1, max_pairs=20, rule=CANDIDATES_RULE()).verdict == "PASS"
    assert decide_rounds([ordered] * 20, 20).verdict == "INCONCLUSIVE"


def CANDIDATES_RULE():
    from suite_stats import StakeRule

    return StakeRule("mixture", CANDIDATES[1])


def test_round_kernel() -> None:
    laws = [(F(1, 2), F(1, 2), F(0)), (F(0), F(1, 3), F(2, 3))]
    assert round_kernel(laws) == {
        (1, 0): F(1, 6),
        (1, 1): F(1, 3),
        (0, 0): F(1, 6),
        (0, 1): F(1, 3),
    }


def test_exhaustive_paths() -> None:
    laws = [(F(1, 2), F(1, 3), F(1, 6)), (F(1, 4), F(1, 4), F(1, 2))] * 3
    plan = Plan(alpha=F(4, 5), delta=F(1, 10), batch=2, max_pairs=6, rule=CANDIDATES_RULE())
    expected = {v: F(0) for v in ("PASS", "BLOCK", "INCONCLUSIVE", "ERROR")}
    cost = F(0)
    for path in product((-1, 0, 1), repeat=6):
        prob = F(1)
        for d, law in zip(path, laws, strict=True):
            prob *= law[d + 1]
        decision = decide(
            path, alpha=plan.alpha, delta=plan.delta, batch=2, max_pairs=6, rule=plan.rule
        )
        expected[decision.verdict] += prob
        cost += prob * decision.stopping_pairs
    actual = enumerate_laws(laws, plan)
    assert actual.probabilities == expected
    assert actual.expected_pairs == cost


def test_nozero_and_noplus_paths() -> None:
    from suite_stats_sim import characteristics

    for law in ((F(11, 20), F(0), F(9, 20)), (F(1, 10), F(9, 10), F(0))):
        plan = balanced_plan(5, 30)
        actual = enumerate_laws([law] * 30, plan)
        expected = characteristics(law, plan)[0]
        assert actual.probabilities == {k: F(v) for k, v in expected["lower"].items()}


def test_cap_rounding() -> None:
    assert balanced_plan(150).max_pairs == 300
    with pytest.raises(ValueError):
        balanced_plan(401)


def test_general_packed_dp_against_s1() -> None:
    from suite_stats_sim import characteristics

    law = (F(7, 20), F(1, 5), F(9, 20))
    plan = balanced_plan(5, 50)
    actual = enumerate_laws([law] * 50, plan)
    expected = characteristics(law, plan)[0]
    assert actual.probabilities == {k: F(v) for k, v in expected["lower"].items()}
    assert float(actual.expected_pairs) == expected["summary"]["mean"]


def test_permutations_preserve_round_end_probabilities() -> None:
    from balanced import enumerate_balanced

    laws = [(F(1, 3), F(1, 3), F(1, 3)), (F(1, 2), F(1, 2), F(0))]
    assert enumerate_balanced(laws, 20) == enumerate_balanced(laws[::-1], 20)


def test_grid_and_search_contracts() -> None:
    from s1c_study import boundary_cases, search_candidates

    for n, _, laws in boundary_cases():
        assert len(laws) == n
        assert sum((p[2] - p[0] for p in laws), F(0)) == -F(n, 10)
    for n in (5, 10, 20):
        jobs = search_candidates(n)
        assert len(jobs) == 2000
        assert len({laws for _, _, _, laws in jobs}) == 2000
        assert jobs == search_candidates(n)
        for _, _, _, laws in jobs:
            assert sum((p[2] - p[0] for p in laws), F(0)) == -F(n, 10)
            assert all(sum(p) == 1 and min(p) >= 0 for p in laws)


def test_binary_cost_matches_ordered_paths() -> None:
    for outcomes in ((-1, 0), (-1, 1)):
        law = (F(1, 2), F(1, 2), F(0)) if outcomes[1] == 0 else (F(1, 2), F(0), F(1, 2))
        plan = Plan(alpha=F(4, 5), batch=2, max_pairs=8, rule=CANDIDATES_RULE())
        cost = F(0)
        for path in product(outcomes, repeat=8):
            result = decide(path, alpha=plan.alpha, batch=2, max_pairs=8, rule=plan.rule)
            cost += F(result.stopping_pairs, 256)
        assert enumerate_laws([law] * 8, plan).expected_pairs == cost


def test_invalid_inputs() -> None:
    with pytest.raises(ValueError):
        decide_rounds([[True] * 20], 20)
    with pytest.raises(ValueError):
        decide_rounds([[0] * 20], 20)
    with pytest.raises(ValueError):
        enumerate_laws([(F(0), F(1), F(0))], balanced_plan(20))
    with pytest.raises(ValueError):
        round_kernel([(F(-1), F(1), F(1))])


def test_packed_digit_sum_matches_modulus_exactly() -> None:
    from balanced import digit_folds, digit_sum

    for width in (10, 100, 5000):
        folds = digit_folds(width, 400)
        coefficients = [1] * 401
        packed = sum(c << (width * i) for i, c in enumerate(coefficients))
        assert digit_sum(packed, folds) == sum(coefficients)
        assert digit_sum(packed, folds) == packed % ((1 << width) - 1)
        assert digit_sum(0, folds) == 0
