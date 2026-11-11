"""Suite statistics kernel: rule, wealth, thresholds, floors, plan checks and exact
operating characteristics. FROZEN.

Source of truth: the phase 1 contract (plan/exec/v2/tasks/P1-CONTRACT.md), section 4
(`src/arci/suite_stats.py`), with the stopping rule of section 5 for the operating
characteristics. Every expected value is derived inside this file independently of the
code under test: wealth by `reference_wealth` (exact `Fraction` arithmetic), text by the
contract's integer rule, verdict probabilities by brute-force enumeration, and two exact
rows copied from the reviewed S1c results.
"""

from __future__ import annotations

import dataclasses
import itertools
import math
import random
import time
from collections.abc import Sequence
from fractions import Fraction

import pytest

from arci.suite_stats import (
    OperatingCharacteristics,
    SuitePlanError,
    SuiteRule,
    check_suite_plan,
    crossed,
    default_max_errored_pairs,
    default_max_rounds,
    earliest_block_round,
    earliest_pass_round,
    never_differs_pass_round,
    operating_characteristics,
    rule_of,
    scored_wealth,
    wealth,
    wealth_text,
)
from tests.acceptance.suite_helpers import reference_wealth, suite_manifest

pytestmark = pytest.mark.acceptance

# Every `# pyright: ignore[reportArgumentType]` in this file marks a call that passes a
# deliberately wrong value or type, to check that the contract's ValueError is raised.

F = Fraction
Law = tuple[Fraction, Fraction, Fraction]

# Contract 2 defaults: alpha 1/20, delta 1/10, stakes 1/4 and 1/2.
ALPHA = F(1, 20)
DELTA = F(1, 10)
STAKES: tuple[Fraction, ...] = (F(1, 4), F(1, 2))
WARNING = "max_rounds below 3: few looks"

# (alpha, delta, stakes) triples used to compare wealth with the reference.
SPECS: tuple[tuple[Fraction, Fraction, tuple[Fraction, ...]], ...] = (
    (ALPHA, DELTA, STAKES),
    (F(1, 2), F(1, 2), (F(1, 100), F(99, 100))),
    (F(1, 1000), F(1, 20), (F(1, 8), F(1, 4), F(1, 2), F(3, 4))),
    (F(1, 3), F(1, 5), (F(9, 10),)),
)


def _rule(
    n_cells: int = 20,
    max_rounds: int = 20,
    max_errored_pairs: int = 0,
    *,
    alpha: Fraction = ALPHA,
    delta: Fraction = DELTA,
    stakes: tuple[Fraction, ...] = STAKES,
) -> SuiteRule:
    return SuiteRule(
        alpha=alpha,
        delta=delta,
        stakes=stakes,
        n_cells=n_cells,
        max_rounds=max_rounds,
        max_errored_pairs=max_errored_pairs,
    )


def _ref(
    minus: int,
    zero: int,
    plus: int,
    *,
    alpha: Fraction = ALPHA,
    delta: Fraction = DELTA,
    stakes: tuple[Fraction, ...] = STAKES,
) -> tuple[Fraction, Fraction]:
    return reference_wealth(minus, zero, plus, alpha, delta, stakes)


def _text_reference(value: Fraction) -> str:
    """Contract 4, wealth_text: 10**e <= value < 10**(e + 1), m = floor(value / 10**(e - 5))."""
    e = 0
    while F(10) ** e > value:
        e -= 1
    while F(10) ** (e + 1) <= value:
        e += 1
    m = math.floor(value / F(10) ** (e - 5))
    assert 100000 <= m <= 999999
    return f"{m // 100000}.{m % 100000:05d}e{e:+03d}"


# --------------------------------------------------------------------------- SuiteRule


def test_rule_holds_its_fields_and_errored_defaults_to_zero() -> None:
    """Contract 4, SuiteRule: the dataclass fields, with max_errored_pairs defaulting to 0."""
    rule = SuiteRule(alpha=ALPHA, delta=DELTA, stakes=STAKES, n_cells=20, max_rounds=20)
    assert rule.alpha == ALPHA
    assert rule.delta == DELTA
    assert rule.stakes == STAKES
    assert rule.n_cells == 20
    assert rule.max_rounds == 20
    assert rule.max_errored_pairs == 0


@pytest.mark.parametrize("alpha", [F(1, 20), F(1, 2), F(1, 1_000_000), F(3, 100), F(2, 7)], ids=str)
def test_threshold_is_two_over_alpha(alpha: Fraction) -> None:
    """Contract 4, SuiteRule.threshold: exactly 2 / alpha, as a Fraction."""
    threshold = _rule(alpha=alpha).threshold
    assert isinstance(threshold, Fraction)
    assert threshold == F(2) / alpha


def test_default_threshold_is_forty() -> None:
    """Contract 4, SuiteRule.threshold at the defaults (alpha 1/20): 40."""
    assert _rule().threshold == F(40)


def test_rule_is_frozen() -> None:
    """Contract 4: SuiteRule is @dataclass(frozen=True)."""
    rule = _rule()
    field = "alpha"
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(rule, field, F(1, 10))


@pytest.mark.parametrize(
    "fields",
    [
        {"alpha": F(1, 1_000_000)},
        {"alpha": F(1, 2)},
        {"delta": F(1, 10**9)},
        {"delta": F(10**9 - 1, 10**9)},
        {"stakes": (F(1, 2),)},
        {"stakes": tuple(F(i, 9) for i in range(1, 9))},
        {"stakes": (F(1, 1000), F(999, 1000))},
        {"n_cells": 1, "max_rounds": 1},
        {"n_cells": 20, "max_rounds": 20, "max_errored_pairs": 400},
        {"n_cells": 3, "max_rounds": 7, "max_errored_pairs": 21},
    ],
)
def test_rule_accepts_the_edges_of_its_domains(fields: dict[str, object]) -> None:
    """Contract 4, Domains (section 2 rule 4 ranges): the closed edges are accepted."""
    base: dict[str, object] = {
        "alpha": ALPHA,
        "delta": DELTA,
        "stakes": STAKES,
        "n_cells": 20,
        "max_rounds": 20,
        "max_errored_pairs": 0,
    }
    base.update(fields)
    rule = SuiteRule(**base)  # pyright: ignore[reportArgumentType]
    for name, value in fields.items():
        assert getattr(rule, name) == value


@pytest.mark.parametrize(
    "alpha",
    [
        F(0),
        F(-1, 20),
        F(1, 1_000_001),
        F(1, 2) + F(1, 10**12),
        F(3, 5),
        F(1),
        0.05,
        "1/20",
    ],
    ids=repr,
)
def test_rule_rejects_alpha_outside_its_domain(alpha: object) -> None:
    """Contract 4, Domains: alpha is a Fraction with 1/1000000 <= alpha <= 1/2."""
    with pytest.raises(ValueError):
        _rule(alpha=alpha)  # pyright: ignore[reportArgumentType]


@pytest.mark.parametrize("delta", [F(0), F(1), F(-1, 10), F(3, 2), 0.1, "1/10"], ids=repr)
def test_rule_rejects_delta_outside_its_domain(delta: object) -> None:
    """Contract 4, Domains: delta is a Fraction with 0 < delta < 1."""
    with pytest.raises(ValueError):
        _rule(delta=delta)  # pyright: ignore[reportArgumentType]


@pytest.mark.parametrize(
    "stakes",
    [
        (),
        tuple(F(i, 10) for i in range(1, 10)),
        (F(1, 2), F(1, 4)),
        (F(1, 4), F(1, 4)),
        (F(0), F(1, 2)),
        (F(1, 4), F(1)),
        (F(-1, 4),),
        (F(1, 4), F(3, 2)),
        (0.25, 0.5),
        (F(1, 4), "1/2"),
    ],
    ids=repr,
)
def test_rule_rejects_stakes_outside_their_domain(stakes: tuple[object, ...]) -> None:
    """Contract 4, Domains: 1 to 8 Fraction stakes, each 0 < q < 1, strictly increasing."""
    with pytest.raises(ValueError):
        _rule(stakes=stakes)  # pyright: ignore[reportArgumentType]


@pytest.mark.parametrize(
    ("n_cells", "max_rounds", "max_errored_pairs"),
    [
        (0, 20, 0),
        (-1, 20, 0),
        (20, 0, 0),
        (20, -3, 0),
        (20, 20, -1),
        (20, 20, 401),
        (1, 1, 2),
    ],
)
def test_rule_rejects_bad_sizes(n_cells: int, max_rounds: int, max_errored_pairs: int) -> None:
    """Contract 4, Domains: n_cells >= 1, max_rounds >= 1, 0 <= E <= n_cells * max_rounds."""
    with pytest.raises(ValueError):
        _rule(n_cells, max_rounds, max_errored_pairs)


def test_suite_plan_error_is_a_value_error() -> None:
    """Contract 4: class SuitePlanError(ValueError)."""
    assert issubclass(SuitePlanError, ValueError)


# --------------------------------------------------------------------------- rule_of


def test_rule_of_the_default_manifest() -> None:
    """Contract 4, rule_of: the manifest's rule as exact Fractions and its grid sizes."""
    rule = rule_of(suite_manifest())
    assert isinstance(rule, SuiteRule)
    assert rule.alpha == ALPHA and isinstance(rule.alpha, Fraction)
    assert rule.delta == DELTA and isinstance(rule.delta, Fraction)
    assert rule.stakes == STAKES
    assert all(isinstance(q, Fraction) for q in rule.stakes)
    assert rule.n_cells == 20
    assert rule.max_rounds == 20
    assert rule.max_errored_pairs == 4
    assert rule.threshold == F(40)


def test_rule_of_a_non_default_manifest() -> None:
    """Contract 4, rule_of, with the section 2 fields alpha, delta, stakes, sizes and E."""
    manifest = suite_manifest(
        n_tasks=3,
        n_conditions=2,
        alpha="1/100",
        delta="1/5",
        stakes=("1/8", "1/4", "1/2"),
        max_rounds=70,
        max_errored_pairs=5,
    )
    rule = rule_of(manifest)
    assert rule.alpha == F(1, 100)
    assert rule.delta == F(1, 5)
    assert rule.stakes == (F(1, 8), F(1, 4), F(1, 2))
    assert rule.n_cells == 6
    assert rule.max_rounds == 70
    assert rule.max_errored_pairs == 5
    assert rule.threshold == F(200)


# --------------------------------------------------------------------------- wealth


def test_wealth_of_one_pair_by_hand() -> None:
    """Contract 4, wealth: one pair, defaults, worked by hand from x = d + delta.

    d = +1: PASS mean(1 + q*11/9) = 35/24; BLOCK mean(1 - q) = 5/8.
    d = -1: PASS mean(1 - q) = 5/8; BLOCK mean(1 + q*9/11) = 115/88.
    d = 0: PASS mean(1 + q/9) = 25/24; BLOCK mean(1 - q/11) = 85/88.
    """
    rule = _rule()
    assert wealth(0, 0, 1, rule) == (F(35, 24), F(5, 8))
    assert wealth(1, 0, 0, rule) == (F(5, 8), F(115, 88))
    assert wealth(0, 1, 0, rule) == (F(25, 24), F(85, 88))


def test_wealth_of_an_empty_stream_is_one() -> None:
    """Contract 4, wealth: the empty product is 1 for every stake, so both wealths are 1."""
    for alpha, delta, stakes in SPECS:
        assert wealth(0, 0, 0, _rule(alpha=alpha, delta=delta, stakes=stakes)) == (F(1), F(1))


def test_wealth_returns_two_fractions() -> None:
    """Contract 4, wealth -> tuple[Fraction, Fraction]; exact, no float."""
    result = wealth(3, 5, 7, _rule())
    assert isinstance(result, tuple)
    assert len(result) == 2
    assert all(isinstance(w, Fraction) for w in result)


def test_wealth_matches_the_reference_on_a_seeded_sample() -> None:
    """Contract 4, wealth: PASS and BLOCK wealth from the counts, equal stake weights."""
    rng = random.Random(20261111)
    triples = [(rng.randrange(61), rng.randrange(61), rng.randrange(61)) for _ in range(150)]
    for alpha, delta, stakes in SPECS:
        rule = _rule(alpha=alpha, delta=delta, stakes=stakes)
        for minus, zero, plus in triples:
            expected = _ref(minus, zero, plus, alpha=alpha, delta=delta, stakes=stakes)
            assert wealth(minus, zero, plus, rule) == expected, (minus, zero, plus, stakes)


EDGE_TRIPLES = (
    (1, 0, 0),
    (0, 1, 0),
    (0, 0, 1),
    (1, 1, 1),
    (0, 78, 0),
    (0, 79, 0),
    (0, 80, 0),
    (0, 0, 8),
    (0, 0, 9),
    (12, 0, 0),
    (13, 0, 0),
    (400, 0, 0),
    (0, 400, 0),
    (0, 0, 400),
    (133, 134, 133),
    (200, 0, 200),
    (1, 79, 0),
    (9, 0, 11),
    (0, 5000, 0),
)


@pytest.mark.parametrize(("minus", "zero", "plus"), EDGE_TRIPLES)
def test_wealth_matches_the_reference_on_edge_cases(minus: int, zero: int, plus: int) -> None:
    """Contract 4, wealth, at the floors, at the registered-pair cap and at large counts."""
    for alpha, delta, stakes in SPECS:
        rule = _rule(alpha=alpha, delta=delta, stakes=stakes)
        expected = _ref(minus, zero, plus, alpha=alpha, delta=delta, stakes=stakes)
        assert wealth(minus, zero, plus, rule) == expected


def test_wealth_of_100000_zero_pairs_returns_promptly() -> None:
    """Contract 4, wealth: computed with integer powers, so wealth(0, 100_000, 0) is prompt."""
    rule = _rule()
    start = time.perf_counter()
    result = wealth(0, 100_000, 0, rule)
    elapsed = time.perf_counter() - start
    assert elapsed < 5.0
    assert result == _ref(0, 100_000, 0)


@pytest.mark.parametrize(
    "counts",
    [
        (-1, 0, 0),
        (0, -1, 0),
        (0, 0, -1),
        (1.0, 0, 0),
        (0, 2.5, 0),
        (0, "3", 0),
        (0, 0, F(2)),
        (None, 0, 0),
    ],
    ids=repr,
)
def test_wealth_rejects_bad_counts(counts: tuple[object, object, object]) -> None:
    """Contract 4, Domains: counts passed to wealth are non-negative ints, else ValueError."""
    with pytest.raises(ValueError):
        wealth(*counts, _rule())  # pyright: ignore[reportArgumentType]


# --------------------------------------------------------------------------- scored_wealth


def test_scored_wealth_applies_the_errored_pair_rule() -> None:
    """Contract 4, scored_wealth: errored pairs count -1 in PASS and +1 in BLOCK."""
    for alpha, delta, stakes in SPECS[:2]:
        rule = _rule(alpha=alpha, delta=delta, stakes=stakes)
        for minus, zero, plus, errored in itertools.product(range(5), range(5), range(5), range(4)):
            pass_w, block_w = scored_wealth(minus, zero, plus, errored, rule)
            ref_pass = _ref(minus + errored, zero, plus, alpha=alpha, delta=delta, stakes=stakes)
            ref_block = _ref(minus, zero, plus + errored, alpha=alpha, delta=delta, stakes=stakes)
            assert pass_w == ref_pass[0]
            assert block_w == ref_block[1]
            assert pass_w == wealth(minus + errored, zero, plus, rule)[0]
            assert block_w == wealth(minus, zero, plus + errored, rule)[1]


def test_scored_wealth_without_errored_pairs_is_wealth() -> None:
    """Contract 4, scored_wealth with errored = 0 is wealth of the same counts."""
    rule = _rule()
    for minus, zero, plus in EDGE_TRIPLES[:16]:
        assert scored_wealth(minus, zero, plus, 0, rule) == wealth(minus, zero, plus, rule)


def test_scored_wealth_at_the_errored_floor_example() -> None:
    """Contract 4, known facts: one errored pair and 79 pairs of 0 give PASS wealth about
    21.17 at the defaults, which has not crossed 40."""
    rule = _rule(20, 4, 1)
    pass_w, _ = scored_wealth(0, 79, 0, 1, rule)
    assert pass_w == _ref(1, 79, 0)[0]
    assert F(21165, 1000) <= pass_w < F(21175, 1000)
    assert not crossed(pass_w, rule)


@pytest.mark.parametrize(
    "counts",
    [
        (0, 0, 0, -1),
        (-1, 0, 0, 0),
        (0, 0, -2, 1),
        (0, 0, 0, 1.0),
        (0, 0, 0, "1"),
        (0, 0, 0, None),
        (0, F(1), 0, 0),
    ],
    ids=repr,
)
def test_scored_wealth_rejects_bad_counts(counts: tuple[object, object, object, object]) -> None:
    """Contract 4, Domains: counts passed to scored_wealth are non-negative ints."""
    with pytest.raises(ValueError):
        scored_wealth(*counts, _rule())  # pyright: ignore[reportArgumentType]


def test_pass_and_block_never_both_cross_at_the_defaults() -> None:
    """ADR 0011 item 5 (PASS and BLOCK cannot both cross), at the contract defaults: swept
    over small counts with 0 to 3 errored pairs, scored as in contract 4, scored_wealth."""
    rule = _rule(max_errored_pairs=3)
    seen_pass = seen_block = False
    for minus, zero, plus, errored in itertools.product(range(17), range(9), range(17), range(4)):
        pass_w, block_w = scored_wealth(minus, zero, plus, errored, rule)
        pass_hit, block_hit = crossed(pass_w, rule), crossed(block_w, rule)
        assert not (pass_hit and block_hit), (minus, zero, plus, errored)
        seen_pass = seen_pass or pass_hit
        seen_block = seen_block or block_hit
    # The sweep is wide enough to reach each crossing on its own.
    assert seen_pass and seen_block


# --------------------------------------------------------------------------- crossed


def test_crossed_is_inclusive_at_the_default_threshold() -> None:
    """Contract 4, crossed: value >= threshold, inclusive, exact."""
    rule = _rule()
    tiny = F(1, 10**40)
    assert crossed(F(40), rule) is True
    assert crossed(F(40) - tiny, rule) is False
    assert crossed(F(40) + tiny, rule) is True
    assert crossed(F(39), rule) is False
    assert crossed(F(10**60), rule) is True


def test_crossed_at_an_exact_pass_wealth_equal_to_the_threshold() -> None:
    """Contract 4, crossed: inclusive. alpha is chosen so that 2 / alpha is exactly the
    PASS wealth of four +1 pairs at the default delta and stakes."""
    target = _ref(0, 0, 4)[0]
    alpha = F(2) / target
    rule = _rule(alpha=alpha)
    assert rule.threshold == target
    assert crossed(wealth(0, 0, 4, rule)[0], rule) is True
    assert crossed(target - F(1, target.denominator * 10**6), rule) is False
    assert crossed(wealth(0, 0, 3, rule)[0], rule) is False


def test_crossed_at_an_exact_block_wealth_equal_to_the_threshold() -> None:
    """Contract 4, crossed: inclusive, for the BLOCK wealth of five -1 pairs."""
    target = _ref(5, 0, 0)[1]
    alpha = F(2) / target
    rule = _rule(alpha=alpha)
    assert rule.threshold == target
    assert crossed(wealth(5, 0, 0, rule)[1], rule) is True
    assert crossed(wealth(4, 0, 0, rule)[1], rule) is False


# --------------------------------------------------------------------------- wealth_text


def test_wealth_text_verified_example() -> None:
    """Contract 4, wealth_text: PASS wealth of 80 pairs all 0 at the defaults is 4.22732e+01."""
    pass_w = wealth(0, 80, 0, _rule())[0]
    assert wealth_text(pass_w) == "4.22732e+01"
    assert _text_reference(pass_w) == "4.22732e+01"


@pytest.mark.parametrize(
    ("value", "text"),
    [
        (F(1), "1.00000e+00"),
        (F(10), "1.00000e+01"),
        (F(40), "4.00000e+01"),
        (F(1, 10), "1.00000e-01"),
        (F(1, 10**12), "1.00000e-12"),
        (F(10**100), "1.00000e+100"),
        (F(1, 10**100), "1.00000e-100"),
        (F(1, 3), "3.33333e-01"),
        (F(2, 3), "6.66666e-01"),
        (F(1, 7), "1.42857e-01"),
        (F(5, 8), "6.25000e-01"),
        (F(35, 24), "1.45833e+00"),
        (F(9_999_999, 10**7), "9.99999e-01"),
        (F(10) - F(1, 10**20), "9.99999e+00"),
        (F(10**6 - 1, 10**5), "9.99999e+00"),
        (F(123_456_789), "1.23456e+08"),
        (F(1_999_999_999, 10**9), "1.99999e+00"),
    ],
    ids=str,
)
def test_wealth_text_exact_rule(value: Fraction, text: str) -> None:
    """Contract 4, wealth_text: six significant digits, truncated (never rounded), exponent
    with sign and at least two digits; values below 1 and exact powers of ten included."""
    assert _text_reference(value) == text
    assert wealth_text(value) == text


def test_wealth_text_matches_the_rule_on_wealth_values() -> None:
    """Contract 4, wealth_text over real wealths, from tiny to huge."""
    rule = _rule()
    for minus, zero, plus in (*EDGE_TRIPLES[:16], (300, 0, 0), (0, 0, 300), (37, 41, 5)):
        for value in wealth(minus, zero, plus, rule):
            assert wealth_text(value) == _text_reference(value)


@pytest.mark.parametrize("value", [F(0), F(-1, 3), F(-40)], ids=str)
def test_wealth_text_rejects_non_positive(value: Fraction) -> None:
    """Contract 4, wealth_text: ValueError for value <= 0."""
    with pytest.raises(ValueError):
        wealth_text(value)


# --------------------------------------------------------------------------- floors


def test_all_zero_pass_wealth_first_crosses_at_79_pairs() -> None:
    """Contract 4, known facts: all-zero PASS wealth first crosses 40 at 79 pairs."""
    rule = _rule()
    first = next(n for n in range(1, 200) if crossed(wealth(0, n, 0, rule)[0], rule))
    assert first == 79
    assert _ref(0, 78, 0)[0] < 40 <= _ref(0, 79, 0)[0]


def test_all_plus_crosses_pass_at_9_and_all_minus_crosses_block_at_13() -> None:
    """Contract 4, known facts: all +1 crosses PASS at 9 pairs; all -1 crosses BLOCK at 13."""
    rule = _rule()
    first_pass = next(n for n in range(1, 100) if crossed(wealth(0, 0, n, rule)[0], rule))
    first_block = next(n for n in range(1, 100) if crossed(wealth(n, 0, 0, rule)[1], rule))
    assert (first_pass, first_block) == (9, 13)
    assert _ref(0, 0, 8)[0] < 40 <= _ref(0, 0, 9)[0]
    assert _ref(12, 0, 0)[1] < 40 <= _ref(13, 0, 0)[1]


@pytest.mark.parametrize(
    ("n_cells", "max_rounds", "max_errored_pairs", "expected"),
    [
        (20, 20, 0, 4),
        (10, 40, 0, 8),
        (20, 3, 0, None),
        (20, 4, 0, 4),
        (20, 20, 4, 4),
        (20, 20, 400, 4),
        (1, 400, 0, 79),
        (1, 79, 0, 79),
        (1, 78, 0, None),
        (79, 1, 0, 1),
        (78, 1, 0, None),
        (78, 2, 0, 2),
        (40, 2, 0, 2),
        (5, 16, 0, 16),
    ],
)
def test_never_differs_pass_round(
    n_cells: int, max_rounds: int, max_errored_pairs: int, expected: int | None
) -> None:
    """Contract 4, never_differs_pass_round: the first round r <= max_rounds at which
    r * n_cells pairs all 0 have crossed PASS wealth (79 pairs at the defaults), else None.
    Contract facts: 4 for 20 cells, 8 for 10 cells, None for 20 cells and 3 rounds."""
    rule = _rule(n_cells, max_rounds, max_errored_pairs)
    assert never_differs_pass_round(rule) == expected


@pytest.mark.parametrize(
    ("n_cells", "max_rounds", "expected"),
    [
        (20, 20, 1),
        (20, 1, 1),
        (1, 9, 9),
        (1, 400, 9),
        (1, 8, None),
        (4, 3, 3),
        (5, 2, 2),
        (9, 1, 1),
        (8, 1, None),
        (8, 2, 2),
    ],
)
def test_earliest_pass_round(n_cells: int, max_rounds: int, expected: int | None) -> None:
    """Contract 4, earliest_pass_round: the first round end with r * n_cells >= 9 pairs
    (all +1 crosses PASS at 9 pairs) within max_rounds, else None; 1 for 20 cells."""
    assert earliest_pass_round(_rule(n_cells, max_rounds)) == expected


@pytest.mark.parametrize(
    ("n_cells", "max_rounds", "expected"),
    [
        (20, 20, 1),
        (20, 1, 1),
        (1, 13, 13),
        (1, 400, 13),
        (1, 12, None),
        (6, 3, 3),
        (7, 2, 2),
        (13, 1, 1),
        (12, 1, None),
        (12, 2, 2),
    ],
)
def test_earliest_block_round(n_cells: int, max_rounds: int, expected: int | None) -> None:
    """Contract 4, earliest_block_round: the first round end with r * n_cells >= 13 pairs
    (all -1 crosses BLOCK at 13 pairs) within max_rounds, else None; 1 for 20 cells."""
    assert earliest_block_round(_rule(n_cells, max_rounds)) == expected


# --------------------------------------------------------------------------- defaults


@pytest.mark.parametrize(
    ("n_cells", "expected"),
    [
        (1, 400),
        (3, 134),
        (7, 58),
        (20, 20),
        (133, 4),
        (134, 3),
        (399, 2),
        (400, 1),
        (401, 1),
        (100_000, 1),
    ],
)
def test_default_max_rounds(n_cells: int, expected: int) -> None:
    """Contract 4, Defaults: default_max_rounds(N) = ceil(400 / N), so 1 for N >= 400."""
    assert -(-400 // n_cells) == expected
    assert default_max_rounds(n_cells) == expected


@pytest.mark.parametrize(
    ("n_cells", "max_rounds", "expected"),
    [
        (20, 20, 4),
        (1, 400, 4),
        (7, 58, 5),
        (399, 2, 8),
        (400, 1, 4),
        (401, 1, 5),
        (1, 1, 1),
        (100, 1, 1),
        (101, 1, 2),
        (50, 8, 4),
        (3, 134, 5),
    ],
)
def test_default_max_errored_pairs(n_cells: int, max_rounds: int, expected: int) -> None:
    """Contract 4, Defaults: default_max_errored_pairs(N, R) = ceil(N * R / 100)."""
    assert -(-(n_cells * max_rounds) // 100) == expected
    assert default_max_errored_pairs(n_cells, max_rounds) == expected


# --------------------------------------------------------------------------- check_suite_plan


def test_default_plan_passes_without_warnings() -> None:
    """Contract 4, check_suite_plan: a valid plan with max_rounds >= 3 returns ()."""
    assert check_suite_plan(suite_manifest()) == ()


def test_twenty_cells_three_rounds_is_refused() -> None:
    """Contract 4, check_suite_plan (a) and known facts: a 20-cell plan with max_rounds = 3
    is refused, because never_differs_pass_round is None."""
    manifest = suite_manifest(max_rounds=3, max_errored_pairs=0)
    assert never_differs_pass_round(rule_of(manifest)) is None
    with pytest.raises(SuitePlanError):
        check_suite_plan(manifest)


def test_twenty_cells_four_rounds_one_errored_pair_passes() -> None:
    """Contract 4, known facts: 20 cells, 4 rounds, max_errored_pairs = 1 passes."""
    assert check_suite_plan(suite_manifest(max_rounds=4, max_errored_pairs=1)) == ()


@pytest.mark.parametrize(("max_rounds", "refused"), [(78, True), (79, False), (400, False)])
def test_single_cell_budget_floor(max_rounds: int, refused: bool) -> None:
    """Contract 4, check_suite_plan (a): one cell needs 79 rounds (the 79-pair floor)."""
    manifest = suite_manifest(n_tasks=1, n_conditions=1, max_rounds=max_rounds, max_errored_pairs=0)
    if refused:
        with pytest.raises(SuitePlanError):
            check_suite_plan(manifest)
    else:
        assert check_suite_plan(manifest) == ()


def test_errored_tolerance_that_makes_pass_unreachable_is_refused() -> None:
    """Contract 4, check_suite_plan (b): refused when scored_wealth(0, 0, registered - E, E)
    PASS wealth has not crossed. The boundary E is found here with the reference wealth."""
    registered = 20 * 4
    boundary = next(e for e in range(registered + 1) if _ref(e, 0, registered - e)[0] < 40)
    assert 0 < boundary < registered
    assert check_suite_plan(suite_manifest(max_rounds=4, max_errored_pairs=boundary - 1)) == ()
    with pytest.raises(SuitePlanError):
        check_suite_plan(suite_manifest(max_rounds=4, max_errored_pairs=boundary))
    with pytest.raises(SuitePlanError):
        check_suite_plan(suite_manifest(max_rounds=4, max_errored_pairs=registered))


def test_two_rounds_warns_of_few_looks() -> None:
    """Contract 4, check_suite_plan: exactly ("max_rounds below 3: few looks",) when
    max_rounds < 3; 40 cells x 2 rounds = 80 pairs clears the 79-pair floor."""
    manifest = suite_manifest(n_tasks=10, n_conditions=4, max_rounds=2, max_errored_pairs=0)
    assert check_suite_plan(manifest) == (WARNING,)


def test_one_round_warns_of_few_looks() -> None:
    """Contract 4, check_suite_plan: the warning also for max_rounds = 1 (80 cells, 1 round)."""
    manifest = suite_manifest(
        n_tasks=20,
        n_conditions=4,
        max_rounds=1,
        max_errored_pairs=1,
        acknowledge_single_round=True,
    )
    assert check_suite_plan(manifest) == (WARNING,)


def test_one_round_below_the_floor_is_refused() -> None:
    """Contract 4, check_suite_plan (a): 40 cells and one round is 40 pairs, below 79."""
    manifest = suite_manifest(
        n_tasks=10,
        n_conditions=4,
        max_rounds=1,
        max_errored_pairs=0,
        acknowledge_single_round=True,
    )
    with pytest.raises(SuitePlanError):
        check_suite_plan(manifest)


# ------------------------------------------------------------------- operating characteristics


def _brute_force(
    laws: Sequence[Law],
    max_rounds: int,
    *,
    alpha: Fraction,
    delta: Fraction,
    stakes: tuple[Fraction, ...],
) -> tuple[dict[str, Fraction], Fraction]:
    """Every full outcome path of every cell in every round, walked with the round verdict of
    contract 5 (no errored pairs, no hard violations): both crossed ERROR, then PASS, then
    BLOCK, else continue; INCONCLUSIVE after max_rounds. Returns masses and expected pairs."""
    n = len(laws)
    threshold = F(2) / alpha
    mass = dict.fromkeys(("PASS", "BLOCK", "INCONCLUSIVE", "ERROR"), F(0))
    expected_pairs = F(0)
    for path in itertools.product((-1, 0, 1), repeat=n * max_rounds):
        probability = F(1)
        for i, d in enumerate(path):
            probability *= laws[i % n][d + 1]
        if probability == 0:
            continue
        minus = zero = plus = 0
        verdict, rounds_run = "INCONCLUSIVE", max_rounds
        for r in range(1, max_rounds + 1):
            for d in path[(r - 1) * n : r * n]:
                minus += d == -1
                zero += d == 0
                plus += d == 1
            pass_w, block_w = reference_wealth(minus, zero, plus, alpha, delta, stakes)
            pass_hit, block_hit = pass_w >= threshold, block_w >= threshold
            if pass_hit and block_hit:
                verdict = "ERROR"
            elif pass_hit:
                verdict = "PASS"
            elif block_hit:
                verdict = "BLOCK"
            else:
                continue
            rounds_run = r
            break
        mass[verdict] += probability
        expected_pairs += probability * rounds_run * n
    return mass, expected_pairs


BRUTE_LAWS: dict[str, tuple[Law, Law]] = {
    "mixed": ((F(1, 5), F(1, 2), F(3, 10)), (F(0), F(1, 3), F(2, 3))),
    "worse": ((F(3, 5), F(1, 5), F(1, 5)), (F(1, 2), F(1, 2), F(0))),
}
# (alpha, delta, stakes): alpha 1/2 gives threshold 4 so that decisions happen within 3 rounds.
BRUTE_RULES: dict[str, tuple[Fraction, Fraction, tuple[Fraction, ...]]] = {
    "default-stakes": (F(1, 2), F(1, 10), (F(1, 4), F(1, 2))),
    "wide-stakes": (F(1, 2), F(1, 10), (F(1, 2), F(9, 10))),
    "one-stake": (F(1, 2), F(1, 10), (F(9, 10),)),
}


@pytest.mark.parametrize("max_rounds", [1, 2, 3])
@pytest.mark.parametrize("rule_name", sorted(BRUTE_RULES))
@pytest.mark.parametrize("laws_name", sorted(BRUTE_LAWS))
def test_operating_characteristics_match_brute_force(
    laws_name: str, rule_name: str, max_rounds: int
) -> None:
    """Contract 4, operating_characteristics: exact verdict probabilities and expected
    pairs under the stopping rule of contract 5, on 2 heterogeneous cells and 1 to 3 rounds."""
    laws = BRUTE_LAWS[laws_name]
    alpha, delta, stakes = BRUTE_RULES[rule_name]
    mass, expected_pairs = _brute_force(laws, max_rounds, alpha=alpha, delta=delta, stakes=stakes)
    assert mass["ERROR"] == 0
    rule = _rule(2, max_rounds, alpha=alpha, delta=delta, stakes=stakes)
    result = operating_characteristics(laws, rule)
    assert result.p_pass == mass["PASS"]
    assert result.p_block == mass["BLOCK"]
    assert result.p_inconclusive == mass["INCONCLUSIVE"]
    assert result.expected_pairs == expected_pairs


def test_brute_force_grid_reaches_every_verdict() -> None:
    """Self-check of the brute-force grid above: across it, PASS, BLOCK and INCONCLUSIVE
    each have positive probability, so the comparison exercises every branch."""
    seen: set[str] = set()
    for laws in BRUTE_LAWS.values():
        for alpha, delta, stakes in BRUTE_RULES.values():
            mass, _ = _brute_force(laws, 3, alpha=alpha, delta=delta, stakes=stakes)
            seen.update(v for v, p in mass.items() if p > 0)
    assert seen == {"PASS", "BLOCK", "INCONCLUSIVE"}


def test_operating_characteristics_types_and_total() -> None:
    """Contract 4, operating_characteristics: an OperatingCharacteristics of exact
    Fractions whose three probabilities sum to 1 exactly."""
    laws: list[Law] = [
        (F(1, 7), F(4, 7), F(2, 7)),
        (F(0), F(1), F(0)),
        (F(9, 20), F(1, 4), F(3, 10)),
    ]
    result = operating_characteristics(laws, _rule(3, 20))
    assert isinstance(result, OperatingCharacteristics)
    for value in (result.p_pass, result.p_block, result.p_inconclusive, result.expected_pairs):
        assert isinstance(value, Fraction)
        assert value >= 0
    assert result.p_pass + result.p_block + result.p_inconclusive == 1
    assert 3 <= result.expected_pairs <= 60


@pytest.mark.parametrize(
    ("law", "max_rounds", "verdict", "pairs"),
    [
        ((F(0), F(1), F(0)), 20, "PASS", 80),
        ((F(0), F(1), F(0)), 16, "PASS", 80),
        ((F(0), F(1), F(0)), 15, "INCONCLUSIVE", 75),
        ((F(0), F(0), F(1)), 20, "PASS", 10),
        ((F(0), F(0), F(1)), 1, "INCONCLUSIVE", 5),
        ((F(1), F(0), F(0)), 20, "BLOCK", 15),
        ((F(1), F(0), F(0)), 2, "INCONCLUSIVE", 10),
    ],
)
def test_operating_characteristics_of_deterministic_streams(
    law: Law, max_rounds: int, verdict: str, pairs: int
) -> None:
    """Contract 4, operating_characteristics with the known floors on 5 cells: all 0 stops
    at the round end after 79 pairs (round 16), all +1 after 9 (round 2), all -1 after 13
    (round 3); otherwise INCONCLUSIVE after max_rounds."""
    result = operating_characteristics([law] * 5, _rule(5, max_rounds))
    probabilities = {
        "PASS": result.p_pass,
        "BLOCK": result.p_block,
        "INCONCLUSIVE": result.p_inconclusive,
    }
    assert probabilities == {v: F(int(v == verdict)) for v in probabilities}
    assert result.expected_pairs == pairs


# Copied from plan/exec/v2/spikes/s1c/results.json, record C[73]: N=20, a=95, b=95,
# dependence "independent", field "balanced" (exact fractions; ERROR there is "0").
TABLE_C_095_095: dict[str, str] = {
    "PASS": (
        "6664425904337895535464152079715133500279493539198895245380690561485966574923183572575927"
        "1374646122731673100836565318722253131773919319907313660247328958235688523323537524480330"
        "1004149009621330040514215531823648152257339876359958155193840240999284229506548285524707"
        "6071785091883708859742343245377093277615607152365652963606807718015763626924095564685075"
        "9246631498047005449775946015222682167908844614502388183332486424725815643218677555326263"
        "1196216744589810852091239829413177498530993287347738992710659018474043324872182864303869"
        "2153987567637810117601239424731431524162492879144328172487580060200052035717122089404900"
        "4561355841293085745391086739583112483757303229660751326583912747108773064642848340338274"
        "0803402041511200304741159698596301154021919083053603537215944817093128710328944645659514"
        "5933959817196397486098745540730614498532562406549998956984114546754683247735719758848755"
        "9579410838071766795355857111685443459266630510171031256249009368253385012989642750339373"
        "8790787563346800399491556061387732267653780611608133222814064269821749807/66680144328798"
        "5427407985179072125779714475832231590816039625781176403723781763207152143220087155429074"
        "2929910593433240445888801654119365080363356052330830046095157579514014558463078285911814"
        "0247289650161358866019816907480374764612911638773760000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "00000000000000000000000000000000000000000000000000000000000"
    ),
    "BLOCK": (
        "6250473435019948067645372512231460878966448302672529722490187460403766601756954592727684"
        "1455848535694814171879471442002292925571302344134054304379145730687425999096986349487445"
        "2630546894696159338566990587060601756915509567142086546525467247090473399807588076460375"
        "2266538207102256415687893808731886546409389013389846065917994673098396407112901749227016"
        "2331937592543095669791364502320100534130989922689856948777129916148126091412619469186359"
        "0508786365687174033894193460796390781450408939369402442608734576217852916624172516775836"
        "0859548266485797227255653970638783681150748469471938116129637415558096541673474546520932"
        "8880400460537310375915964431400181027427275180370668315539011201571625201176197224848814"
        "3185835073502968841490465957797457681699065745491344931830086881725169259252507841111427"
        "8460399458535320492520156360292254626231766016794081817859073306715733468053500572393296"
        "3992366187933600776657473422253153040342515145424059571367622293268454805782494143043044"
        "23010571598447155532791251455739516146275518143872271545242277/3334007216439927137039925"
        "8953606288985723791611579540801981289058820186189088160357607161004357771453714649552967"
        "1662022294440082705968254018167802616541502304757878975700727923153914295590701236448250"
        "8067943300990845374018738230645581938688000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "000000000000000000000000000000000000000000000000"
    ),
    "INCONCLUSIVE": (
        "3588528416949269915300749653216846620635565537683948962116655828266913686373166910365971"
        "5523883346639227555472730244616327402576015232063926430513263977189513638509095683314803"
        "3782092507461494488362894993672234170522892249377782579705765670206425551642246479140631"
        "2922833070960376115611626309148846209755116706159256125395360665876479613936507172666040"
        "3523098706355798373192071381490542044753374814992018213716436298641758458359922845484490"
        "9945983600013420595016689908938632253078897023252828501952932673781983603460077363647334"
        "2657265144998917069044630723455396424731447232656858122981177477355215971715979761630052"
        "9339972129306245398167052898568227614693149790703169808673886580446711325719155638201975"
        "1628195625082993788780924573889526822131763312415147874228284270269552036551969155435249"
        "7817897234394524730548049418982374261592500925365722680003816888135286129965571790174030"
        "6110502648385880885470872781407072288306429022118440842509440319262541144988153544976238"
        "0603827807178457311549627546685229434740356099315740898191187087765639/66680144328798542"
        "7407985179072125779714475832231590816039625781176403723781763207152143220087155429074292"
        "9910593433240445888801654119365080363356052330830046095157579514014558463078285911814024"
        "7289650161358866019816907480374764612911638773760000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "00000000000000000000000000000000000000000000000000000000"
    ),
    "expected_pairs": (
        "5963294962985291633296939590358250381354389371664380887566992546683792238369190400794979"
        "9258855371813363842771362294385809526375162183684606368625854750372583735983282234646848"
        "0892585203563899149442677809172676513304071627619771634160534163316775540632012338782298"
        "9632552664166686975365630665886804165913212825173249255945705500127080442583403677708072"
        "6693508242720661230774319322328366018402383840550887535374088581634515139459081656174341"
        "4269633564484095627099857010471759759247461761961815115055083415215747822859732724518006"
        "3703978801709150840112136635404328731580804272957338089171751223297870206955220280413190"
        "3701667748426260124300743788799298506426120452241017447189629180467349808944193741777543"
        "6932467811667346706043728995569694741522576276904891699522973602411753217987684013379816"
        "7320493669458317936961182265146025282406679251662147487689197862369561315691283383275724"
        "9413508036194777092564653022135577791718356498256450147582881221497131432640559512767382"
        "84707430289588290381/4737909217226284592129454005317695786306414847157887607235876580890"
        "0480733837185251796826441303908628860099203403658239934435426150964794660775368501012608"
        "0079484550787612886215290919687377455085834655515660543442044936173649920000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "000000000000000000000000000000000000000"
    ),
}

# Copied from plan/exec/v2/spikes/s1c/results.json, record C[79]: N=20, a=95, b=75,
# dependence "independent", field "balanced" (exact fractions; ERROR there is "0").
TABLE_C_095_075: dict[str, str] = {
    "PASS": (
        "8527934857946525678593085375212475085534695916403774373750773092313367147216784408221744"
        "3723812767541763918822218783649016642233991365305347976058564649756283102724212582329422"
        "6549840913999348991357102378064197563901980580060505079856934039306042170300795787169847"
        "4777594368923905525190262805035430786506803273763481435297415627049612553920517585204539"
        "9401832217171413472566212897595221969893249711729074030887088691038554223564913536832848"
        "9039010890407536395902851677284965537089212088503090064164446916816648902513056573804871"
        "4756479391650914555356997548443531482300369230960671703432475718783081516969475998386478"
        "4641819664255423579352956817151089373235211136762558946714453566538657038066278859058260"
        "4492763271585878286855631170670231453335291102655791/17218479456385750618067377696052635"
        "4835799247454486899217332368164007406912417456193974845372360461732863709190319615877885"
        "8492729081666102499160988272871734465950347165599088088467989652005512390646706441905652"
        "6231345685268240569209892573766037966584735183775739433978714578587782701380797240772477"
        "6478745559867127462713628922275162053189144359135111410362613760000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "00000000000000000000000"
    ),
    "BLOCK": (
        "1598463941782661681301088951293790922250832961229432349324455496862701809374232277141271"
        "7535690343227675223070932322465980687526910303171462495442806209209866306032455259468830"
        "0642852486315547283092304037143309606874679992621918829346029606065512047175728452257511"
        "2368236292514339685288876126327982350371742174696221313604119109255585569640790702836251"
        "3147810093384144728792597062534221068236577598929968048536446723451319455082219709051255"
        "6700847165956989759471286259269581694721756207521822571941903950927583001322164529917580"
        "4820606328951462697455035521804974605538302078697838781651877029506609763670158392858873"
        "9970635372929425935332928118326721547475721565936441047739760743220473619599674661036210"
        "359471682521019706929168908701129599585573447805551189761/172184794563857506180673776960"
        "5263548357992474544868992173323681640074069124174561939748453723604617328637091903196158"
        "7788584927290816661024991609882728717344659503471655990880884679896520055123906467064419"
        "0565262313456852682405692098925737660379665847351837757394339787145785877827013807972407"
        "7247764787455598671274627136289222751620531891443591351114103626137600000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "000000000000000000000000000"
    ),
    "INCONCLUSIVE": (
        "1233754759210554339799702252260974136320739786195202390744944340042799463827950680140684"
        "7841019791328436060841808169030242483837382794981971908191004609428285971879136723094684"
        "9097199290440899566233752499448775912412129580799068022478162746608283126294530847040959"
        "3311603877500696609436784074864603789849269171717795500507348160804079126380989679972775"
        "8430518807836380997939303712528813365414525078203202223895223894599895063635567260352074"
        "9706637950321198329923178378787410203127067032660889249680318846255001820289329570258457"
        "1306789145691456516304091211974769509302156209329302576764195380176714532483246376651276"
        "1645799852509098092434925287164613014349051988524221897012925423259598417432872726849305"
        "822678682026531344830024057357533333912812186653385446599/172184794563857506180673776960"
        "5263548357992474544868992173323681640074069124174561939748453723604617328637091903196158"
        "7788584927290816661024991609882728717344659503471655990880884679896520055123906467064419"
        "0565262313456852682405692098925737660379665847351837757394339787145785877827013807972407"
        "7247764787455598671274627136289222751620531891443591351114103626137600000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000"
    ),
    "expected_pairs": (
        "2362967231574451372713899796771132168091441108844854640457241979852589829884862145040987"
        "9562909021472865821637979718158407397899548773147307410624092351054970528402156678148188"
        "0093348921188711225871387919989647468630127860515980747233460976169416111143235624778650"
        "0768228074288297911271286343230022327869807913988039273688435227705542756238068488433478"
        "4728384733640344750247145815609192446326190767542013756025811140991964240386137712483343"
        "2410912866389531308479372215991103909231930460189337914710204263535612442559945511610810"
        "9446069360228527552534487277064717193927781359736354318973693720271935582119624350615645"
        "7165087918277511061167346550392150197705496633976238011128572217638153962201344151263754"
        "8748512746619148017/11667695520944036383062819236603875505282557247818145570792274011787"
        "3569099601666110585906864467567047721566213366525738800924317083427716541926606922551394"
        "8174752673558819237768359817447966659538498932116352613870394092141625093433171236651540"
        "7566613178223031973793768238983650878076934454545156206117103092679258950964840557990668"
        "9471086592000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000"
    ),
}


@pytest.mark.parametrize(
    ("record", "law"),
    [
        # Identical independent arms at 0.95: P(-1) = P(+1) = 0.95 * 0.05 = 19/400.
        (TABLE_C_095_095, (F(19, 400), F(181, 200), F(19, 400))),
        # Baseline 0.95, candidate 0.75, independent: P(-1) = 0.95 * 0.25, P(+1) = 0.05 * 0.75.
        (TABLE_C_095_075, (F(19, 80), F(29, 40), F(3, 80))),
    ],
    ids=["0.95-0.95", "0.95-0.75"],
)
def test_operating_characteristics_reproduce_table_c(record: dict[str, str], law: Law) -> None:
    """Contract 4, known facts: 20 cells, 20 rounds, defaults. Identical arms at 0.95 PASS
    0.999462, 125.863 pairs; 0.95 against 0.75 BLOCK 0.928342, 202.522 pairs; exactly the
    two matching Table C records of spikes/s1c/results.json."""
    assert sum(law) == 1
    result = operating_characteristics([law] * 20, _rule(20, 20, 4))
    assert result.p_pass == F(record["PASS"])
    assert result.p_block == F(record["BLOCK"])
    assert result.p_inconclusive == F(record["INCONCLUSIVE"])
    assert result.expected_pairs == F(record["expected_pairs"])


def test_table_c_literals_match_the_rounded_contract_figures() -> None:
    """Contract 4, known facts: the copied fractions round to the stated figures."""
    assert round(float(F(TABLE_C_095_095["PASS"])), 6) == 0.999462
    assert round(float(F(TABLE_C_095_095["expected_pairs"])), 3) == 125.863
    assert round(float(F(TABLE_C_095_075["BLOCK"])), 6) == 0.928342
    assert round(float(F(TABLE_C_095_075["expected_pairs"])), 3) == 202.522
    for record in (TABLE_C_095_095, TABLE_C_095_075):
        total = F(record["PASS"]) + F(record["BLOCK"]) + F(record["INCONCLUSIVE"])
        assert total == 1


MARGIN_GRIDS: dict[str, tuple[Law, ...]] = {
    # Homogeneous: every cell has mean difference exactly -1/10.
    "homogeneous-even": ((F(1, 10), F(9, 10), F(0)),) * 2,
    "homogeneous-mixed": ((F(3, 10), F(1, 2), F(1, 5)),) * 2,
    # Strongly heterogeneous: cell means +1/2 and -7/10; then -1, +1/2 and +1/5.
    "heterogeneous-2": ((F(0), F(1, 2), F(1, 2)), (F(7, 10), F(3, 10), F(0))),
    "heterogeneous-3": (
        (F(1), F(0), F(0)),
        (F(0), F(1, 2), F(1, 2)),
        (F(0), F(4, 5), F(1, 5)),
    ),
}


@pytest.mark.parametrize("grid_name", sorted(MARGIN_GRIDS))
def test_directional_errors_on_the_margin_are_at_most_half_alpha(grid_name: str) -> None:
    """Contract 4, known facts at the defaults: for every law with suite mean difference
    exactly -delta, p_pass <= alpha / 2 and p_block <= alpha / 2. 120 registered pairs."""
    laws = MARGIN_GRIDS[grid_name]
    assert sum(law[2] - law[0] for law in laws) / len(laws) == -DELTA
    result = operating_characteristics(laws, _rule(len(laws), 120 // len(laws)))
    assert result.p_pass + result.p_block + result.p_inconclusive == 1
    assert result.p_pass <= ALPHA / 2
    assert result.p_block <= ALPHA / 2


def test_operating_characteristics_on_twenty_different_laws_and_400_pairs() -> None:
    """Contract 4, operating_characteristics: it must handle 20 cells and 400 registered pairs
    with different laws per cell; the three probabilities sum to exactly 1. Known facts at the
    defaults: suite mean difference exactly -delta gives p_pass <= alpha / 2 and
    p_block <= alpha / 2. Rounds hold n_cells pairs each, so 20 <= expected pairs <= 400."""
    laws = tuple(
        (F(1, 2), F(1, 2), F(0)) if i % 2 == 0 else (F(1, 10), F(1, 2), F(2, 5)) for i in range(20)
    )
    assert sum(law[2] - law[0] for law in laws) / 20 == -DELTA
    result = operating_characteristics(laws, _rule(20, 20, 4))
    assert result.p_pass + result.p_block + result.p_inconclusive == 1
    assert result.p_pass <= ALPHA / 2
    assert result.p_block <= ALPHA / 2
    assert 20 <= result.expected_pairs <= 400


GOOD_LAW: Law = (F(1, 10), F(4, 5), F(1, 10))


@pytest.mark.parametrize(
    "laws",
    [
        [GOOD_LAW],
        [GOOD_LAW, GOOD_LAW, GOOD_LAW],
        [],
        [GOOD_LAW, (F(1, 2), F(1, 2), F(1, 2))],
        [GOOD_LAW, (F(1, 3), F(1, 3), F(1, 4))],
        [GOOD_LAW, (F(-1, 10), F(1, 2), F(3, 5))],
        [GOOD_LAW, (0.25, 0.5, 0.25)],
        [GOOD_LAW, (0, 1, 0)],
        [GOOD_LAW, (F(1, 2), F(1, 2))],
        [GOOD_LAW, (F(1, 4), F(1, 4), F(1, 4), F(1, 4))],
        [GOOD_LAW, (F(1, 4), "1/2", F(1, 4))],
    ],
    ids=[
        "too-few",
        "too-many",
        "empty",
        "sum-above-1",
        "sum-below-1",
        "negative",
        "floats",
        "ints",
        "two-entries",
        "four-entries",
        "string-entry",
    ],
)
def test_operating_characteristics_rejects_bad_laws(laws: list[object]) -> None:
    """Contract 4, Domains: each law is three Fractions, each >= 0, summing to exactly 1,
    and there is one law per cell (here 2 cells), else ValueError."""
    with pytest.raises(ValueError):
        operating_characteristics(laws, _rule(2, 3))  # pyright: ignore[reportArgumentType]
