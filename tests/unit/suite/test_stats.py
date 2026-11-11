from __future__ import annotations

import itertools
import json
import random
from dataclasses import replace
from fractions import Fraction as F
from pathlib import Path
from typing import Any

import pytest

from arci.suite_schema import SuiteManifest
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
from tests.unit.suite.helpers import manifest_fields

DEFAULT = SuiteRule(F(1, 20), F(1, 10), (F(1, 4), F(1, 2)), 20, 20)


def direct_wealth(differences: list[int], rule: SuiteRule) -> tuple[F, F]:
    passed, blocked = F(0), F(0)
    for q in rule.stakes:
        p, b = F(1), F(1)
        for d in differences:
            p *= 1 + q * (d + rule.delta) / (1 - rule.delta)
            b *= 1 - q * (d + rule.delta) / (1 + rule.delta)
        passed += p / len(rule.stakes)
        blocked += b / len(rule.stakes)
    return passed, blocked


def test_wealth_against_pairwise_products() -> None:
    rng = random.Random(20261111)
    for rule in (DEFAULT, replace(DEFAULT, delta=F(2, 7), stakes=(F(1, 7), F(2, 3), F(4, 5)))):
        for _ in range(50):
            counts = [rng.randrange(15) for _ in range(3)]
            stream = [-1] * counts[0] + [0] * counts[1] + [1] * counts[2]
            rng.shuffle(stream)
            assert wealth(counts[0], counts[1], counts[2], rule) == direct_wealth(stream, rule)
    assert wealth(0, 0, 8, DEFAULT)[0] == F(151874368379777, 5642219814912)
    assert wealth(0, 0, 9, DEFAULT)[0] == F(316547748620285, 7522959753216)
    assert wealth(0, 100_000, 0, DEFAULT) == (
        (F(37, 36) ** 100_000 + F(19, 18) ** 100_000) / 2,
        (F(43, 44) ** 100_000 + F(21, 22) ** 100_000) / 2,
    )


def test_errored_scoring_and_inclusive_crossing() -> None:
    assert scored_wealth(2, 4, 3, 5, DEFAULT) == (
        wealth(7, 4, 3, DEFAULT)[0],
        wealth(2, 4, 8, DEFAULT)[1],
    )
    assert DEFAULT.threshold == 40
    assert crossed(F(40), DEFAULT)
    assert not crossed(F(40) - F(1, 10**100), DEFAULT)
    assert crossed(F(40) + F(1, 10**100), DEFAULT)
    assert not crossed(scored_wealth(0, 79, 0, 1, DEFAULT)[0], DEFAULT)


@pytest.mark.parametrize(
    "updates",
    [
        {"alpha": F(1, 1000001)},
        {"alpha": F(2, 3)},
        {"alpha": 0.05},
        {"delta": F(0)},
        {"delta": F(1)},
        {"delta": 0.1},
        {"stakes": ()},
        {"stakes": (F(0),)},
        {"stakes": (F(1),)},
        {"stakes": (0.5,)},
        {"stakes": (F(1, 2), F(1, 4))},
        {"stakes": (F(1, 4), F(1, 4))},
        {"stakes": tuple(F(1, n) for n in range(11, 2, -1))},
        {"n_cells": 0},
        {"n_cells": 1.5},
        {"max_rounds": 0},
        {"max_rounds": 2.5},
        {"max_errored_pairs": -1},
        {"max_errored_pairs": 401},
        {"max_errored_pairs": 0.5},
    ],
)
def test_rule_domains(updates: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        replace(DEFAULT, **updates)


@pytest.mark.parametrize("bad", [-1, 0.5, "1", None])
def test_count_domains(bad: Any) -> None:
    for index in range(4):
        counts = [0, 0, 0, 0]
        counts[index] = bad
        with pytest.raises(ValueError):
            scored_wealth(counts[0], counts[1], counts[2], counts[3], DEFAULT)
        if index < 3:
            with pytest.raises(ValueError):
                wealth(counts[0], counts[1], counts[2], DEFAULT)


@pytest.mark.parametrize(
    "value,text",
    [
        (F(1, 3), "3.33333e-01"),
        (F(1, 10**20), "1.00000e-20"),
        (F(123456789, 100000000), "1.23456e+00"),
        (F(99999999, 10000000), "9.99999e+00"),
        (F(1), "1.00000e+00"),
        (F(10), "1.00000e+01"),
        (F(10**100), "1.00000e+100"),
        (F(10**100 - 1), "9.99999e+99"),
        (F(10**5000), "1.00000e+5000"),
        (F(1, 10**5000), "1.00000e-5000"),
    ],
)
def test_wealth_text(value: F, text: str) -> None:
    assert wealth_text(value) == text


def test_wealth_text_example_and_invalid() -> None:
    assert wealth_text(wealth(0, 80, 0, DEFAULT)[0]) == "4.22732e+01"
    for value in (F(0), F(-1)):
        with pytest.raises(ValueError):
            wealth_text(value)


def test_floors_defaults_and_manifest_rule() -> None:
    single = replace(DEFAULT, n_cells=1, max_rounds=400)
    assert never_differs_pass_round(single) == 79
    assert earliest_pass_round(single) == 9
    assert earliest_block_round(single) == 13
    assert never_differs_pass_round(DEFAULT) == 4
    assert never_differs_pass_round(replace(DEFAULT, n_cells=10)) == 8
    assert earliest_pass_round(DEFAULT) == earliest_block_round(DEFAULT) == 1
    for f in (earliest_pass_round, earliest_block_round, never_differs_pass_round):
        assert f(replace(single, max_rounds=1)) is None
    assert [default_max_rounds(n) for n in (1, 20, 150, 400, 401)] == [400, 20, 3, 1, 1]
    assert [default_max_errored_pairs(n, r) for n, r in ((1, 1), (20, 20), (150, 3), (101, 1))] == [
        1,
        4,
        5,
        2,
    ]
    m = SuiteManifest(**manifest_fields())
    assert rule_of(m) == replace(DEFAULT, n_cells=4, max_rounds=100, max_errored_pairs=4)


def test_plan_refusals_and_warning() -> None:
    fields = manifest_fields(tasks=tuple({"task_id": f"t{i}"} for i in range(10)))
    assert (
        check_suite_plan(
            SuiteManifest.model_validate(fields | {"max_rounds": 4, "max_errored_pairs": 1})
        )
        == ()
    )
    with pytest.raises(SuitePlanError):
        check_suite_plan(SuiteManifest.model_validate(fields | {"max_rounds": 3}))
    # (a) is satisfied, but using the entire error tolerance makes PASS unreachable.
    with pytest.raises(SuitePlanError):
        check_suite_plan(SuiteManifest.model_validate(fields | {"max_errored_pairs": 2000}))
    for rounds in (1, 2):
        m = SuiteManifest(
            **manifest_fields(
                tasks=tuple({"task_id": f"t{i}"} for i in range(50)),
                max_rounds=rounds,
                max_errored_pairs=1,
                acknowledge_single_round=rounds == 1,
            )
        )
        assert check_suite_plan(m) == ("max_rounds below 3: few looks",)


@pytest.mark.parametrize(
    "laws",
    [
        [],
        [(F(0), F(1), F(0))],
        [(F(0), F(1), F(0))] * 3,
        [(F(-1), F(2), F(0))] * 2,
        [(F(0), F(0), F(0))] * 2,
        [(0, F(1), F(0))] * 2,
        [(F(1), F(0))] * 2,
    ],
)
def test_law_domains(laws: Any) -> None:
    with pytest.raises(ValueError):
        operating_characteristics(laws, replace(DEFAULT, n_cells=2))


def brute_force(laws: list[tuple[F, F, F]], rule: SuiteRule) -> OperatingCharacteristics:
    masses = {"pass": F(0), "block": F(0), "inconclusive": F(0)}
    cost = F(0)
    size = rule.n_cells * rule.max_rounds
    for path in itertools.product((-1, 0, 1), repeat=size):
        probability = F(1)
        for i, d in enumerate(path):
            probability *= laws[i % rule.n_cells][d + 1]
        verdict, used = "inconclusive", size
        for end in range(rule.n_cells, size + 1, rule.n_cells):
            p, b = direct_wealth(list(path[:end]), rule)
            assert not (p >= rule.threshold and b >= rule.threshold)
            if p >= rule.threshold or b >= rule.threshold:
                verdict, used = ("pass" if p >= rule.threshold else "block"), end
                break
        masses[verdict] += probability
        cost += probability * used
    return OperatingCharacteristics(masses["pass"], masses["block"], masses["inconclusive"], cost)


@pytest.mark.parametrize("rounds", [2, 3])
@pytest.mark.parametrize(
    "laws",
    [
        [(F(1, 3), F(1, 2), F(1, 6)), (F(1, 5), F(1, 5), F(3, 5))],
        [(F(1, 3), F(2, 3), F(0)), (F(1, 2), F(1, 2), F(0))],
        [(F(1, 3), F(0), F(2, 3)), (F(1, 2), F(0), F(1, 2))],
    ],
)
def test_exact_enumeration_matches_paths(rounds: int, laws: list[tuple[F, F, F]]) -> None:
    rule = replace(DEFAULT, alpha=F(1, 2), stakes=(F(3, 4),), n_cells=2, max_rounds=rounds)
    actual = operating_characteristics(laws, rule)
    assert actual == brute_force(laws, rule)
    assert actual.p_pass + actual.p_block + actual.p_inconclusive == 1


@pytest.mark.parametrize("b", [95, 75])
def test_table_c_exact_fractions(b: int) -> None:
    rows = json.loads(Path(__file__).with_name("table_c.json").read_text())
    row = next(row for row in rows if row["b"] == b)
    a, candidate = F(95, 100), F(b, 100)
    law = (a * (1 - candidate), a * candidate + (1 - a) * (1 - candidate), (1 - a) * candidate)
    actual = operating_characteristics([law] * 20, DEFAULT)
    expected = row["balanced"]
    assert actual == OperatingCharacteristics(
        *(F(expected[key]) for key in ("PASS", "BLOCK", "INCONCLUSIVE", "expected_pairs"))
    )
    assert actual.p_pass + actual.p_block + actual.p_inconclusive == 1


def test_heterogeneous_margin_and_no_midround_absorption() -> None:
    laws = [(F(2, 5), F(1, 2), F(1, 10))] * 10 + [(F(1, 5), F(1, 2), F(3, 10))] * 10
    assert sum(p - m for m, _, p in laws) / 20 == -DEFAULT.delta
    result = operating_characteristics(laws, DEFAULT)
    assert result.p_pass <= DEFAULT.alpha / 2
    assert result.p_block <= DEFAULT.alpha / 2
    assert result.p_pass + result.p_block + result.p_inconclusive == 1
    deterministic = [(F(0), F(0), F(1))] * 9 + [(F(1), F(0), F(0))] * 11
    assert operating_characteristics(deterministic, DEFAULT) == OperatingCharacteristics(
        F(0), F(0), F(1), F(400)
    )
