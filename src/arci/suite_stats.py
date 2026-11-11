"""Exact betting wealth and balanced-round operating characteristics.

Probabilities are projected under independent cell laws, identical across rounds.
The packed polynomial DP retains every path's mass and absorbs only at round ends.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
from math import lcm
from typing import TypeGuard

from arci.suite_schema import SuiteManifest, parse_rational


def _is_fraction(value: object) -> TypeGuard[Fraction]:
    return isinstance(value, Fraction)


@dataclass(frozen=True)
class SuiteRule:
    alpha: Fraction
    delta: Fraction
    stakes: tuple[Fraction, ...]
    n_cells: int
    max_rounds: int
    max_errored_pairs: int = 0

    def __post_init__(self) -> None:
        if not _is_fraction(self.alpha) or not Fraction(1, 1_000_000) <= self.alpha <= Fraction(
            1, 2
        ):
            raise ValueError("alpha must be a Fraction in [1/1000000, 1/2]")
        if not _is_fraction(self.delta) or not 0 < self.delta < 1:
            raise ValueError("delta must be a Fraction in (0, 1)")
        if not 1 <= len(self.stakes) <= 8 or any(
            not _is_fraction(q) or not 0 < q < 1 for q in self.stakes
        ):
            raise ValueError("stakes must contain 1 to 8 Fractions in (0, 1)")
        if any(a >= b for a, b in zip(self.stakes, self.stakes[1:], strict=False)):
            raise ValueError("stakes must be strictly increasing")
        if type(self.n_cells) is not int or self.n_cells < 1:
            raise ValueError("n_cells must be a positive integer")
        if type(self.max_rounds) is not int or self.max_rounds < 1:
            raise ValueError("max_rounds must be a positive integer")
        if (
            type(self.max_errored_pairs) is not int
            or not 0 <= self.max_errored_pairs <= self.n_cells * self.max_rounds
        ):
            raise ValueError("max_errored_pairs must be an integer within the registered budget")

    @property
    def threshold(self) -> Fraction:
        return 2 / self.alpha


class SuitePlanError(ValueError):
    """A structurally valid suite cannot reach the required PASS floor."""


def rule_of(manifest: SuiteManifest) -> SuiteRule:
    return SuiteRule(
        parse_rational(manifest.alpha),
        parse_rational(manifest.delta),
        tuple(parse_rational(q) for q in manifest.stakes),
        manifest.n_cells,
        manifest.max_rounds,
        manifest.max_errored_pairs,
    )


def _counts(*counts: int) -> None:
    if any(type(count) is not int or count < 0 for count in counts):
        raise ValueError("counts must be non-negative integers")


def _factors(rule: SuiteRule, sign: int) -> tuple[tuple[Fraction, ...], ...]:
    return tuple(
        tuple(1 + sign * q * (d + rule.delta) / (1 - sign * rule.delta) for d in (-1, 0, 1))
        for q in rule.stakes
    )


def wealth(minus: int, zero: int, plus: int, rule: SuiteRule) -> tuple[Fraction, Fraction]:
    _counts(minus, zero, plus)

    def direction(sign: int) -> Fraction:
        return sum(
            (m**minus * z**zero * p**plus for m, z, p in _factors(rule, sign)), Fraction(0)
        ) / len(rule.stakes)

    return direction(1), direction(-1)


def scored_wealth(
    minus: int, zero: int, plus: int, errored: int, rule: SuiteRule
) -> tuple[Fraction, Fraction]:
    _counts(minus, zero, plus, errored)
    return wealth(minus + errored, zero, plus, rule)[0], wealth(minus, zero, plus + errored, rule)[
        1
    ]


def crossed(value: Fraction, rule: SuiteRule) -> bool:
    return value.numerator * rule.alpha.numerator >= 2 * value.denominator * rule.alpha.denominator


def wealth_text(value: Fraction) -> str:
    """Six significant digits, truncated with integers even for enormous wealths."""
    if value <= 0:
        raise ValueError("wealth must be positive")
    numerator, denominator = value.numerator, value.denominator
    # An integer estimate only: the loops below certify the exponent exactly.
    # Avoid str(huge_int), which is limited by CPython's decimal digit guard.
    e = (numerator.bit_length() - denominator.bit_length()) * 30103 // 100000
    if e >= 0:
        denominator *= 10**e
    else:
        numerator *= 10 ** (-e)
    while numerator < denominator:
        numerator *= 10
        e -= 1
    while numerator >= denominator * 10:
        denominator *= 10
        e += 1
    m = numerator * 100000 // denominator
    return f"{m // 100000}.{m % 100000:05d}e{e:+03d}"


def _first_round(rule: SuiteRule, difference: int, direction: int) -> int | None:
    def reaches(round: int) -> bool:
        n = round * rule.n_cells
        counts = (
            n if difference == -1 else 0,
            n if difference == 0 else 0,
            n if difference == 1 else 0,
        )
        return crossed(wealth(*counts, rule)[direction], rule)

    # The selected best-case factors are all > 1, so crossing is monotone.
    if not reaches(rule.max_rounds):
        return None
    low, high = 1, rule.max_rounds
    while low < high:
        middle = (low + high) // 2
        if reaches(middle):
            high = middle
        else:
            low = middle + 1
    return low


def earliest_pass_round(rule: SuiteRule) -> int | None:
    return _first_round(rule, 1, 0)


def earliest_block_round(rule: SuiteRule) -> int | None:
    return _first_round(rule, -1, 1)


def never_differs_pass_round(rule: SuiteRule) -> int | None:
    return _first_round(rule, 0, 0)


def default_max_rounds(n_cells: int) -> int:
    return (400 + n_cells - 1) // n_cells


def default_max_errored_pairs(n_cells: int, max_rounds: int) -> int:
    return (n_cells * max_rounds + 99) // 100


def check_suite_plan(manifest: SuiteManifest) -> tuple[str, ...]:
    rule = rule_of(manifest)
    if never_differs_pass_round(rule) is None:
        raise SuitePlanError("budget cannot establish PASS for a candidate that never differs")
    if not crossed(
        scored_wealth(
            0, 0, manifest.registered_pairs - rule.max_errored_pairs, rule.max_errored_pairs, rule
        )[0],
        rule,
    ):
        raise SuitePlanError("PASS unreachable once max_errored_pairs is used")
    return ("max_rounds below 3: few looks",) if rule.max_rounds < 3 else ()


@dataclass(frozen=True)
class OperatingCharacteristics:
    p_pass: Fraction
    p_block: Fraction
    p_inconclusive: Fraction
    expected_pairs: Fraction


@dataclass(frozen=True)
class _IntegerWealth:
    powers: tuple[tuple[tuple[int, ...], ...], ...]
    target: int
    alpha_numerator: int

    def crossed(self, n: int, minus: int, plus: int) -> bool:
        zero = n - minus - plus
        numerator = sum(row[0][minus] * row[1][zero] * row[2][plus] for row in self.powers)
        return numerator * self.alpha_numerator >= self.target


def _integer_wealth(rule: SuiteRule, n: int, sign: int) -> _IntegerWealth:
    factors = _factors(rule, sign)
    denominator = lcm(*(f.denominator for row in factors for f in row))
    powers: list[tuple[tuple[int, ...], ...]] = []
    for row in factors:
        arrays: list[tuple[int, ...]] = []
        for factor in row:
            base = factor.numerator * (denominator // factor.denominator)
            values = [1]
            for _ in range(n):
                values.append(values[-1] * base)
            arrays.append(tuple(values))
        powers.append(tuple(arrays))
    return _IntegerWealth(
        tuple(powers),
        2 * rule.alpha.denominator * len(factors) * denominator**n,
        rule.alpha.numerator,
    )


@lru_cache(maxsize=128)
def _boundary(rule: SuiteRule, n: int) -> tuple[tuple[int, int], ...]:
    """For each minus count, first PASS plus count and last BLOCK plus count.

    Replacing a zero by a plus raises every PASS factor and lowers every BLOCK
    factor. Replacing a zero by a minus has the reverse effect. Hence both
    frontiers advance monotonically as minus increases: only O(n) comparisons.
    """
    passed, blocked = _integer_wealth(rule, n, 1), _integer_wealth(rule, n, -1)
    rows: list[tuple[int, int]] = []
    pass_min, block_max = 0, -1
    for minus in range(n + 1):
        limit = n - minus
        while pass_min <= limit and not passed.crossed(n, minus, pass_min):
            pass_min += 1
        pass_at = min(pass_min, limit + 1)
        block_max = min(block_max, limit)
        while block_max < limit and blocked.crossed(n, minus, block_max + 1):
            block_max += 1
        # For positive stakes, log(1 + lambda*x) <= lambda*x implies
        # a crossing requires a positive sum x for PASS, negative for BLOCK.
        # Both cannot cross on the same count state.
        if pass_at <= block_max:
            raise ArithmeticError("overlapping wealth boundaries")
        rows.append((pass_at, block_max))
    return tuple(rows)


def _digit_sum(value: int, folds: tuple[tuple[int, int], ...]) -> int:
    for bits, mask in folds:
        value = (value & mask) + (value >> bits)
    return value


def operating_characteristics(
    laws: Sequence[tuple[Fraction, Fraction, Fraction]], rule: SuiteRule
) -> OperatingCharacteristics:
    """Exact absorbing DP for independent cell laws, with complete-round looks.

    A row indexed by minus count packs its plus-count polynomial into base 2**w.
    The base exceeds the final common denominator and thus the sum of *all*
    coefficients at every stage. Polynomial shifts, additions, and digit folds
    cannot carry into neighbouring coefficients. No pruning or floats are used.
    """
    if len(laws) != rule.n_cells:
        raise ValueError("one law is required per cell")
    weights: list[tuple[int, int, int, int]] = []
    round_scale = 1
    for law in laws:
        if len(law) != 3 or any(not _is_fraction(p) or p < 0 for p in law) or sum(law) != 1:
            raise ValueError("a law must contain three nonnegative Fractions summing to one")
        den = lcm(*(p.denominator for p in law))
        wm, wz, wp = (p.numerator * (den // p.denominator) for p in law)
        weights.append((wm, wz, wp, den))
        round_scale *= den
    max_pairs = rule.n_cells * rule.max_rounds
    final_scale = round_scale**rule.max_rounds
    width = final_scale.bit_length() + 1
    folds = tuple(
        (width * (1 << i), (1 << (width * (1 << i))) - 1)
        for i in range(max_pairs.bit_length() - 1, -1, -1)
    )
    states = {0: 1}
    pass_mass, block_mass, cost, scale = 0, 0, 0, 1
    for round in range(1, rule.max_rounds + 1):
        # Every survivor runs the full next round, including paths that would
        # cross mid-round. The denominator is advanced alongside the masses.
        cost += rule.n_cells * sum(_digit_sum(row, folds) for row in states.values())
        for wm, wz, wp, den in weights:
            cost *= den
            scale *= den
            pass_mass *= den
            block_mass *= den
            incoming: dict[int, int] = {}
            for minus, row in states.items():
                if wm:
                    incoming[minus + 1] = incoming.get(minus + 1, 0) + row * wm
                if wz or wp:
                    incoming[minus] = incoming.get(minus, 0) + row * wz + ((row * wp) << width)
            states = incoming
        boundary = _boundary(rule, round * rule.n_cells)
        for minus, row in list(states.items()):
            pass_min, block_max = boundary[minus]
            low_bits, high_bits = width * (block_max + 1), width * pass_min
            low, high = row & ((1 << low_bits) - 1), row >> high_bits
            block_mass += _digit_sum(low, folds)
            pass_mass += _digit_sum(high, folds)
            kept = row - low - (high << high_bits)
            if kept:
                states[minus] = kept
            else:
                del states[minus]
    remaining = sum(_digit_sum(row, folds) for row in states.values())
    if pass_mass + block_mass + remaining != scale:
        raise ArithmeticError("probability mass not conserved")
    return OperatingCharacteristics(
        Fraction(pass_mass, scale),
        Fraction(block_mass, scale),
        Fraction(remaining, scale),
        Fraction(cost, scale),
    )
