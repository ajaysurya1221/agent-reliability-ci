"""The planner against hand-built small cases, the real gate and the published reference cells."""

from __future__ import annotations

import math
from collections.abc import Callable
from fractions import Fraction
from typing import Any

import pytest

from arci.gate import decide
from arci.planning import (
    DEFAULT_N_GRID,
    MAX_N_PER_ARM,
    Plan,
    UnsupportedDesignError,
    binomial_pmf,
    per_arm_tail,
    plan,
    reachable_verdicts,
    render_plan_markdown,
    verdict_probabilities,
    verdict_table,
)
from arci.schema import Manifest, Verdict
from tests.acceptance.helpers import manifest, synthetic_trials

PASS, BLOCK, INCONCLUSIVE = Verdict.PASS, Verdict.BLOCK, Verdict.INCONCLUSIVE

# ---------------------------------------------------------------------------------------------
# (a) Small counts, constructed independently of arci.stats.
# With alpha = 0.5 the per-arm tail is t = 1/8, so the one-sided Clopper-Pearson bounds at the
# extreme counts have closed forms: U(0) = 1 - t**(1/n) and L(n) = t**(1/n).
# ---------------------------------------------------------------------------------------------


def _pmf(n: int, p: Fraction) -> list[Fraction]:
    return [math.comb(n, x) * p**x * (1 - p) ** (n - x) for x in range(n + 1)]


def _mass(n: int, p_a: Fraction, p_b: Fraction, cells: set[tuple[int, int]]) -> Fraction:
    baseline, candidate = _pmf(n, p_a), _pmf(n, p_b)
    return sum((baseline[a] * candidate[b] for a, b in cells), Fraction(0))


def _table(n: int, cells: dict[Verdict, set[tuple[int, int]]]) -> tuple[tuple[Verdict, ...], ...]:
    def verdict(a: int, b: int) -> Verdict:
        return next((v for v, chosen in cells.items() if (a, b) in chosen), INCONCLUSIVE)

    return tuple(tuple(verdict(a, b) for b in range(n + 1)) for a in range(n + 1))


@pytest.mark.parametrize(("p_a", "p_b"), [(0.5, 0.5), (1.0, 0.0), (0.0, 1.0), (0.9, 0.2)])
def test_one_trial_per_arm_never_decides_under_the_default_rule(p_a: float, p_b: float) -> None:
    # t = 0.0125: x=0 gives [0, 0.9875], x=1 gives [0.0125, 1]; every L <= -0.975, every U >= 0.
    assert verdict_table(1) == ((INCONCLUSIVE, INCONCLUSIVE), (INCONCLUSIVE, INCONCLUSIVE))
    result = verdict_probabilities(p_a, p_b, 1)
    assert result[PASS] == 0.0
    assert result[BLOCK] == 0.0
    assert result[INCONCLUSIVE] == pytest.approx(1.0, abs=1e-15)


# N=1, t=1/8: x=0 gives [0, 7/8], x=1 gives [1/8, 1]. With delta 0.9:
# (0,0) L=-7/8 PASS; (0,1) L=-3/4 PASS; (1,1) L=-7/8 PASS; (1,0) L=-1, U=3/4 INCONCLUSIVE.
N1 = {PASS: {(0, 0), (0, 1), (1, 1)}, BLOCK: set[tuple[int, int]]()}
# N=2, t=1/8, delta 0.3: only (0,2) passes, L = 2 * 8**-0.5 - 1 = -0.2929 > -0.3; the next best L
# is -0.58. Every U is positive, so nothing blocks.
N2 = {PASS: {(0, 2)}, BLOCK: set[tuple[int, int]]()}
# N=3, t=1/8, delta 0.1: U(0) = L(3) = 1/2, so (0,3) has L = 0 and passes; L(2) ~ 0.2245 puts the
# next best L at -0.28. The smallest U is (3,0) with U = 0, not below -0.1: nothing blocks.
N3 = {PASS: {(0, 3)}, BLOCK: set[tuple[int, int]]()}
# N=4, t=1/8, delta 0.1: L(4) = 8**-0.25 = 0.5946 = 1 - U(0), so (0,4) has L = +0.189 and (4,0)
# has U = -0.189 (BLOCK). L(3) ~ 0.3484 and U(1) ~ 0.6516 give (0,3) and (1,4) L = -0.057 (PASS);
# every other pair has L <= -0.24 and U >= 0.057.
N4 = {PASS: {(0, 3), (0, 4), (1, 4)}, BLOCK: {(4, 0)}}
SMALL_CASES = [
    (1, 0.9, N1),
    (2, 0.3, N2),
    (3, 0.1, N3),
    (4, 0.1, N4),
]


@pytest.mark.parametrize(("n", "delta", "cells"), SMALL_CASES)
def test_small_count_verdict_tables_match_the_hand_derivation(
    n: int, delta: float, cells: dict[Verdict, set[tuple[int, int]]]
) -> None:
    assert verdict_table(n, alpha=0.5, delta=delta) == _table(n, cells)


@pytest.mark.parametrize(("n", "delta", "cells"), SMALL_CASES)
@pytest.mark.parametrize(
    ("p_a", "p_b"), [(Fraction(1, 2), Fraction(1, 2)), (Fraction(9, 10), Fraction(1, 5))]
)
def test_small_count_probabilities_match_hand_computed_joint_masses(
    n: int,
    delta: float,
    cells: dict[Verdict, set[tuple[int, int]]],
    p_a: Fraction,
    p_b: Fraction,
) -> None:
    result = verdict_probabilities(float(p_a), float(p_b), n, alpha=0.5, delta=delta)
    expected_pass = _mass(n, p_a, p_b, cells[PASS])
    expected_block = _mass(n, p_a, p_b, cells[BLOCK])
    assert result[PASS] == pytest.approx(float(expected_pass), abs=1e-14)
    assert result[BLOCK] == pytest.approx(float(expected_block), abs=1e-14)
    assert result[INCONCLUSIVE] == pytest.approx(
        float(1 - expected_pass - expected_block), abs=1e-14
    )


def test_n4_closed_form_at_even_rates() -> None:
    # P(BLOCK) = P(x_A=4) P(x_B=0) = 1/256; P(PASS) = (1/16)(4/16 + 1/16) + (4/16)(1/16) = 9/256.
    result = verdict_probabilities(0.5, 0.5, 4, alpha=0.5, delta=0.1)
    assert result[BLOCK] == pytest.approx(1 / 256, abs=1e-15)
    assert result[PASS] == pytest.approx(9 / 256, abs=1e-15)
    assert result[INCONCLUSIVE] == pytest.approx(246 / 256, abs=1e-15)


def _cp_oracle(x: int, n: int, tail: float) -> tuple[float, float]:
    """Clopper-Pearson by float bisection on math.comb tails, independent of arci.stats."""

    def at_least(p: float) -> float:
        return math.fsum(math.comb(n, k) * p**k * (1 - p) ** (n - k) for k in range(x, n + 1))

    def at_most(p: float) -> float:
        return math.fsum(math.comb(n, k) * p**k * (1 - p) ** (n - k) for k in range(x + 1))

    def root(tail_probability: Callable[[float], float], *, rising: bool) -> float:
        low, high = 0.0, 1.0
        for _ in range(100):
            middle = (low + high) / 2
            if (tail_probability(middle) > tail) == rising:
                high = middle
            else:
                low = middle
        return (low + high) / 2

    # The lower bound solves P(X >= x) = tail (rising in p); the upper solves P(X <= x) = tail.
    lower = 0.0 if x == 0 else root(at_least, rising=True)
    upper = 1.0 if x == n else root(at_most, rising=False)
    return lower, upper


@pytest.mark.parametrize("n", range(1, 9))
@pytest.mark.parametrize(("alpha", "delta"), [(0.05, 0.10), (0.5, 0.1), (0.2, 0.25)])
def test_verdict_tables_match_an_independent_oracle(n: int, alpha: float, delta: float) -> None:
    intervals = [_cp_oracle(x, n, alpha / 4) for x in range(n + 1)]
    expected: list[tuple[Verdict, ...]] = []
    for low_a, high_a in intervals:
        row: list[Verdict] = []
        for low_b, high_b in intervals:
            lower, upper = low_b - high_a, high_b - low_a
            # A tie with the margin would make the comparison depend on rounding: refuse it.
            assert abs(lower + delta) > 1e-9
            assert abs(upper + delta) > 1e-9
            row.append(PASS if lower > -delta else BLOCK if upper < -delta else INCONCLUSIVE)
        expected.append(tuple(row))
    assert verdict_table(n, alpha=alpha, delta=delta) == tuple(expected)


# ---------------------------------------------------------------------------------------------
# The planner classifies exactly as the real gate does: run `arci.gate.decide` on sealed
# synthetic stores for every count pair.
# ---------------------------------------------------------------------------------------------


def _manifest(n: int, alpha: float, delta: float) -> Manifest:
    draft = manifest(n_per_arm=n, alpha=alpha)
    return Manifest.create(**(draft.model_dump(exclude={"record_sha256"}) | {"delta": delta}))


@pytest.mark.parametrize(("n", "alpha", "delta"), [(4, 0.5, 0.1), (8, 0.05, 0.10), (6, 0.2, 0.2)])
def test_verdict_table_equals_the_gate_on_every_count_pair(
    n: int, alpha: float, delta: float
) -> None:
    experiment = _manifest(n, alpha, delta)
    table = verdict_table(n, alpha=alpha, delta=delta)
    seen: set[Verdict] = set()
    for baseline in range(n + 1):
        for candidate in range(n + 1):
            trials = synthetic_trials(
                experiment,
                condition_id="fetch_timeout",
                baseline_successes=baseline,
                candidate_successes=candidate,
            )
            decision = decide(experiment, trials)
            assert decision.verdict is table[baseline][candidate], (baseline, candidate)
            seen.add(decision.verdict)
    assert BLOCK in seen  # every configuration above reaches a decisive BLOCK somewhere


def test_per_arm_tail_is_the_gate_allocation() -> None:
    assert per_arm_tail(0.05) == 0.05 / 4.0
    assert per_arm_tail(1e-6) == 2.5e-7


# ---------------------------------------------------------------------------------------------
# (b) Published reference cells (alpha 0.05, delta 0.10, K=1, Clopper-Pearson), to the printed
# precision. README.md "The gate, measured against itself" prints PASS / BLOCK / INCONCLUSIVE;
# docs/STATISTICS.md (frozen) prints the reference points and the side-by-side table.
# ---------------------------------------------------------------------------------------------

README_TABLE = {
    (0.95, 0.95): {
        20: ".000 / .000 / 1.000",
        100: ".443 / .000 / .557",
        200: ".889 / .000 / .111",
        400: ".999 / .000 / .001",
    },
    (0.95, 0.85): {
        20: ".000 / .000 / 1.000",
        100: ".001 / .000 / .999",
        200: ".001 / .000 / .999",
        400: ".001 / .001 / .999",
    },
    (0.95, 0.75): {
        20: ".000 / .000 / 1.000",
        100: ".000 / .093 / .907",
        200: ".000 / .365 / .635",
        400: ".000 / .828 / .172",
    },
    (0.95, 0.65): {
        20: ".000 / .008 / .992",
        100: ".000 / .685 / .315",
        200: ".000 / .985 / .015",
        400: ".000 / 1.000 / .000",
    },
    (0.80, 0.80): {
        20: ".003 / .000 / .997",
        100: ".059 / .000 / .941",
        200: ".218 / .000 / .782",
        400: ".615 / .000 / .385",
    },
}
README_CELLS = [
    (p_a, p_b, n, cell) for (p_a, p_b), row in README_TABLE.items() for n, cell in row.items()
]
# STATISTICS.md, Clopper-Pearson column of the side-by-side table: PASS / BLOCK only.
STATISTICS_CELLS = [
    (0.95, 0.65, 50, ".000 / .205"),
    (0.94, 0.77, 400, ".000 / .372"),
    (0.95, 0.95, 100, ".443 / .000"),
    (0.80, 0.80, 200, ".218 / .000"),
    (0.95, 0.75, 200, ".000 / .365"),
    (0.95, 0.85, 200, ".001 / .000"),
    (0.95, 0.95, 200, ".889 / .000"),
]


def _printed(value: float) -> str:
    text = f"{value:.3f}"
    return text[1:] if text.startswith("0.") else text


@pytest.mark.parametrize(("p_a", "p_b", "n", "cell"), README_CELLS)
def test_readme_operating_characteristics(p_a: float, p_b: float, n: int, cell: str) -> None:
    result = verdict_probabilities(p_a, p_b, n)
    printed = " / ".join(_printed(result[verdict]) for verdict in (PASS, BLOCK, INCONCLUSIVE))
    assert printed == cell


@pytest.mark.parametrize(("p_a", "p_b", "n", "cell"), STATISTICS_CELLS)
def test_statistics_side_by_side_clopper_pearson(p_a: float, p_b: float, n: int, cell: str) -> None:
    result = verdict_probabilities(p_a, p_b, n)
    assert f"{_printed(result[PASS])} / {_printed(result[BLOCK])}" == cell


def test_statistics_reference_points() -> None:
    # "At p_A=0.95, p_B=0.65 and N=20, P(INCONCLUSIVE) = 0.992"
    assert f"{verdict_probabilities(0.95, 0.65, 20)[INCONCLUSIVE]:.3f}" == "0.992"
    # "1.0 vs 0.0 at N=20 is BLOCK with probability 1"
    assert verdict_probabilities(1.0, 0.0, 20) == {PASS: 0.0, BLOCK: 1.0, INCONCLUSIVE: 0.0}


def test_the_brief_example_blocks_with_probability_0_365_at_n_200() -> None:
    rows = {
        row.n_per_arm: row
        for row in plan(baseline_rate=0.95, candidate_rate=0.75, target_verdict=BLOCK).rows
    }
    assert round(rows[200].block_probability, 3) == 0.365


# ---------------------------------------------------------------------------------------------
# (c) Probability mass is conserved.
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("p_a", "p_b", "n", "alpha", "delta"),
    [
        (0.0, 1.0, 50, 0.05, 0.10),
        (1.0, 1.0, 13, 0.05, 0.10),
        (1e-9, 1 - 1e-9, 100, 0.05, 0.10),
        (0.5, 0.5, 400, 0.05, 0.10),
        (0.999, 0.001, 200, 0.05, 0.10),
        (0.3, 0.7, 37, 0.5, 0.05),
        (0.62, 0.61, 111, 1e-6, 0.3),
        (0.95, 0.75, 400, 0.05, 0.10),
        (0.9, 0.9, 1, 0.05, 0.10),
        (0.3, 0.3, 1, 0.05, 0.10),
        (0.999, 0.001, 20, 0.05, 0.10),
    ],
)
def test_probability_mass_is_conserved(
    p_a: float, p_b: float, n: int, alpha: float, delta: float
) -> None:
    result = verdict_probabilities(p_a, p_b, n, alpha=alpha, delta=delta)
    assert set(result) == {PASS, BLOCK, INCONCLUSIVE}
    assert all(0.0 <= value <= 1.0 for value in result.values())
    assert abs(math.fsum(result.values()) - 1.0) <= 1e-12


@pytest.mark.parametrize("n", [1, 2, 7, 50, 400])
@pytest.mark.parametrize("p", [0.0, 0.03, 0.5, 0.97, 1.0])
def test_binomial_pmf_is_a_distribution(n: int, p: float) -> None:
    pmf = binomial_pmf(p, n)
    assert len(pmf) == n + 1
    assert abs(math.fsum(pmf) - 1.0) <= 1e-12
    exact = _pmf(n, Fraction(p))
    assert max(abs(value - float(truth)) for value, truth in zip(pmf, exact, strict=True)) < 1e-13


def test_every_plan_row_conserves_mass() -> None:
    result = plan(baseline_rate=0.8, candidate_rate=0.6, target_verdict=BLOCK)
    assert [row.n_per_arm for row in result.rows] == list(DEFAULT_N_GRID)
    for row in result.rows:
        total = math.fsum(
            (row.pass_probability, row.block_probability, row.inconclusive_probability)
        )
        assert abs(total - 1.0) <= 1e-12
        assert row.total_trials == 2 * row.n_per_arm


# ---------------------------------------------------------------------------------------------
# (d) The target: smallest tested N meeting it, or an explicit "target not reached".
# ---------------------------------------------------------------------------------------------


def test_smallest_tested_n_meeting_the_target() -> None:
    result = plan(
        baseline_rate=0.95, candidate_rate=0.75, target_verdict=BLOCK, target_probability=0.80
    )
    assert [row.meets_target for row in result.rows] == [False, False, False, False, True]
    assert result.smallest_n_per_arm == 400
    assert result.conclusion == (
        "smallest tested N per arm meeting P(BLOCK) >= 0.8: 400 (800 trials in total)."
    )


def test_target_not_reached_is_explicit() -> None:
    result = plan(
        baseline_rate=0.95,
        candidate_rate=0.75,
        target_verdict=BLOCK,
        target_probability=0.80,
        n_grid=(20, 50, 100, 200),
    )
    assert not any(row.meets_target for row in result.rows)
    assert result.smallest_n_per_arm is None
    assert result.conclusion.startswith("target not reached: no tested N per arm gives P(BLOCK)")
    assert "largest tested 200" in result.conclusion


def test_target_is_met_at_equality() -> None:
    result = plan(
        baseline_rate=1.0,
        candidate_rate=0.0,
        target_verdict=INCONCLUSIVE,
        target_probability=1.0,
        n_grid=(1, 2),
    )
    assert result.rows[0].inconclusive_probability == 1.0
    assert result.smallest_n_per_arm == 1


def test_target_verdict_selects_the_probability() -> None:
    result = plan(
        baseline_rate=0.95, candidate_rate=0.95, target_verdict=PASS, target_probability=0.8
    )
    assert result.smallest_n_per_arm == 200
    for row in result.rows:
        assert row.meets_target == (row.probability(PASS) >= 0.8)


# ---------------------------------------------------------------------------------------------
# (e) Designs outside the domain are refused, never extrapolated.
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"n_grid": (20, MAX_N_PER_ARM + 1)}, "N=401 per arm"),
        ({"n_grid": (1000,)}, "N=1000 per arm"),
        ({"conditions": 2}, "K=2"),
        ({"looks": (50, 100, 200)}, "sequential looks"),
        ({"looks": (200,)}, "sequential looks"),
        ({"interval_method": "newcombe"}, "'newcombe'"),
        ({"interval_method": "wald"}, "'wald'"),
    ],
)
def test_unsupported_designs_are_rejected(overrides: dict[str, Any], message: str) -> None:
    arguments: dict[str, Any] = {
        "baseline_rate": 0.95,
        "candidate_rate": 0.75,
        "target_verdict": BLOCK,
        **overrides,
    }
    with pytest.raises(UnsupportedDesignError, match=r"^unsupported design") as raised:
        plan(**arguments)
    assert message in str(raised.value)


def test_verdict_table_refuses_n_above_the_domain() -> None:
    with pytest.raises(UnsupportedDesignError):
        verdict_table(MAX_N_PER_ARM + 1)


@pytest.mark.parametrize(
    "overrides",
    [
        {"baseline_rate": -0.1},
        {"baseline_rate": 1.1},
        {"candidate_rate": math.nan},
        {"alpha": 0.6},
        {"alpha": 1e-7},
        {"alpha": math.nan},
        {"delta": 0.0},
        {"delta": 1.0},
        {"delta": math.inf},
        {"target_probability": 0.0},
        {"target_probability": 1.1},
        {"target_probability": math.nan},
        {"target_verdict": Verdict.ERROR},
        {"n_grid": ()},
        {"n_grid": (50, 20)},
        {"n_grid": (20, 20)},
        {"n_grid": (0, 20)},
        {"n_grid": (True, 20)},
        {"n_grid": (20.0, 50)},
        {"conditions": 0},
    ],
)
def test_invalid_values_are_rejected(overrides: dict[str, Any]) -> None:
    arguments: dict[str, Any] = {
        "baseline_rate": 0.95,
        "candidate_rate": 0.75,
        "target_verdict": BLOCK,
        **overrides,
    }
    with pytest.raises(ValueError) as raised:
        plan(**arguments)
    assert not isinstance(raised.value, UnsupportedDesignError)


# ---------------------------------------------------------------------------------------------
# (f) The probability endpoints: certainty comes from the reachable count pairs, never from the
# summed floats, and every probability stays in [0, 1].
# ---------------------------------------------------------------------------------------------


def _single_row_plan(
    p_a: float, p_b: float, n: int, target: Verdict, probability: float = 1.0
) -> Plan:
    return plan(
        baseline_rate=p_a,
        candidate_rate=p_b,
        target_verdict=target,
        target_probability=probability,
        n_grid=(n,),
    )


@pytest.mark.parametrize(("p_a", "p_b"), [(0.9, 0.9), (0.3, 0.3)])
def test_a_certain_verdict_is_exactly_one_although_the_floats_miss_it(
    p_a: float, p_b: float
) -> None:
    # Every pair at N=1 is INCONCLUSIVE; the float sums are 0.9999999999999998 at 0.9 and
    # 1.0000000000000002 at 0.3.
    result = _single_row_plan(p_a, p_b, 1, INCONCLUSIVE)
    row = result.rows[0]
    assert row.inconclusive_probability == 1.0
    assert (row.pass_probability, row.block_probability) == (0.0, 0.0)
    assert row.certain_verdict is INCONCLUSIVE
    assert row.meets_target
    assert result.smallest_n_per_arm == 1
    assert verdict_probabilities(p_a, p_b, 1) == {PASS: 0.0, BLOCK: 0.0, INCONCLUSIVE: 1.0}


def test_a_float_of_one_is_not_certainty() -> None:
    # 0.999 -> 0.001 at N=20: BLOCK sums to the float 1.0, yet INCONCLUSIVE keeps 7.45e-17.
    assert reachable_verdicts(0.999, 0.001, 20) == {PASS, BLOCK, INCONCLUSIVE}
    result = _single_row_plan(0.999, 0.001, 20, BLOCK)
    row = result.rows[0]
    assert row.block_probability == 1.0
    assert 0.0 < row.inconclusive_probability < 1e-15
    assert row.certain_verdict is None
    assert not row.meets_target
    assert result.smallest_n_per_arm is None
    assert result.conclusion.startswith("target not reached")


def test_a_certain_block_is_exactly_one_and_meets_a_target_of_one() -> None:
    # Rates 1 and 0 leave the single pair (20, 0), which blocks.
    assert reachable_verdicts(1.0, 0.0, 20) == {BLOCK}
    row = _single_row_plan(1.0, 0.0, 20, BLOCK).rows[0]
    assert (row.pass_probability, row.block_probability, row.inconclusive_probability) == (
        0.0,
        1.0,
        0.0,
    )
    assert row.certain_verdict is BLOCK
    assert row.meets_target


def test_an_almost_certain_verdict_meets_targets_below_one_only() -> None:
    # 0.9 -> 0.3 at N=100: P(BLOCK) = 0.99999922, printed 1.000, but INCONCLUSIVE stays reachable.
    certain_target = _single_row_plan(0.9, 0.3, 100, BLOCK)
    row = certain_target.rows[0]
    assert 0.99999 < row.block_probability < 1.0
    assert row.certain_verdict is None
    assert not row.meets_target
    assert _single_row_plan(0.9, 0.3, 100, BLOCK, 0.999).rows[0].meets_target
    markdown = render_plan_markdown(certain_target)
    assert "| 100 | 200 | 0.000 | 1.000 | 0.000 | no |" in markdown
    assert "exactly 1" not in markdown
    assert "1.000 is rounded: another verdict remains possible at that N." in markdown


def test_markdown_says_exactly_one_for_a_certain_verdict() -> None:
    markdown = render_plan_markdown(_single_row_plan(0.9, 0.9, 1, INCONCLUSIVE))
    assert "| 1 | 2 | 0.000 | 0.000 | exactly 1 | yes |" in markdown
    assert '"exactly 1" marks the only verdict any reachable pair' in markdown


@pytest.mark.parametrize(
    ("p_a", "p_b", "n", "expected"),
    [
        # A rate at 0 or 1 confines its arm to one count: only that row or column is reachable.
        (1.0, 0.5, 4, {BLOCK, INCONCLUSIVE}),
        (0.0, 1.0, 50, {PASS}),
        (1.0, 1.0, 13, {INCONCLUSIVE}),
        # Rates strictly inside (0, 1) reach every pair, so every verdict in the table.
        (0.5, 0.5, 4, {PASS, BLOCK, INCONCLUSIVE}),
        # Pairs whose float mass underflows to zero are still reachable.
        (1e-9, 1 - 1e-9, 100, {PASS, BLOCK, INCONCLUSIVE}),
    ],
)
def test_reachable_verdicts_follow_the_support(
    p_a: float, p_b: float, n: int, expected: set[Verdict]
) -> None:
    alpha = 0.5 if n == 4 else 0.05
    delta = 0.1
    assert reachable_verdicts(p_a, p_b, n, alpha=alpha, delta=delta) == expected
    table = verdict_table(n, alpha=alpha, delta=delta)
    present = {verdict for row in table for verdict in row}
    assert expected <= present
    probabilities = verdict_probabilities(p_a, p_b, n, alpha=alpha, delta=delta)
    for verdict in (PASS, BLOCK, INCONCLUSIVE):
        if verdict not in expected:
            assert probabilities[verdict] == 0.0
        if expected == {verdict}:
            assert probabilities[verdict] == 1.0


def test_an_underflowed_rival_still_denies_certainty() -> None:
    # 1e-9 -> 1 - 1e-9 at N=100: P(PASS) is the float 1.0 and P(BLOCK) underflows to 0.0, but
    # both BLOCK and INCONCLUSIVE pairs are reachable, so a target of P(PASS) = 1 is not met.
    probabilities = verdict_probabilities(1e-9, 1 - 1e-9, 100)
    assert probabilities[PASS] == 1.0
    assert probabilities[BLOCK] == 0.0
    row = _single_row_plan(1e-9, 1 - 1e-9, 100, PASS).rows[0]
    assert row.certain_verdict is None
    assert not row.meets_target
