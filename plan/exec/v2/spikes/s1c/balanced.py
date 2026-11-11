"""Exact round-end inference; no floats, pruning, or mid-round absorption.

The round increment polynomial is the convolution of its cell trinomials.
The DP applies its linear factors successively, absorbing only after all N
factors. This is exactly convolution with round_kernel, without a dense kernel
multiplication. General trinomials pack the plus-count polynomial into integers;
a base larger than the final denominator prevents all coefficient carries.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction as F
from functools import lru_cache

from stake_selection import CANDIDATES
from suite_stats import Decision, Plan, StakeRule, decide
from suite_stats_sim import (
    Boundary,
    Probabilities,
    boundary_verdict,
    make_boundary,
    validate_probabilities,
)

RULE = StakeRule("mixture", CANDIDATES[1])


@dataclass(frozen=True)
class ExactResult:
    probabilities: dict[str, F]
    expected_pairs: F

    def record(self) -> dict[str, str]:
        return {
            **{v: str(p) for v, p in self.probabilities.items()},
            "expected_pairs": str(self.expected_pairs),
        }


def balanced_plan(n_cells: int, cap: int = 400) -> Plan:
    if type(n_cells) is not int or type(cap) is not int or not 1 <= n_cells <= cap:
        raise ValueError("positive grid must fit at least one whole round")
    return Plan(batch=n_cells, max_pairs=cap // n_cells * n_cells, rule=RULE)


def decide_rounds(rounds: Sequence[Sequence[int]], n_cells: int, cap: int = 400) -> Decision:
    """Validate complete supplied rounds, then stop at the first decisive round.

    Short input is allowed only if it reaches a decisive round. No incomplete
    suffix, including one after a decision, is accepted. Cell identity and law
    independence are caller contracts, not detectable from differences alone.
    """
    plan = balanced_plan(n_cells, cap)
    if any(len(row) != n_cells for row in rounds):
        raise ValueError("only complete rounds are accepted")
    return decide(
        [d for row in rounds for d in row],
        alpha=plan.alpha,
        delta=plan.delta,
        batch=plan.batch,
        max_pairs=plan.max_pairs,
        rule=plan.rule,
    )


@lru_cache(maxsize=128)
def frontiers(plan: Plan) -> dict[int, Boundary]:
    return dict(
        make_boundary((plan, n)) for n in range(1, plan.max_pairs + 1) if plan.checkpoint(n)
    )


def round_kernel(laws: Sequence[Probabilities]) -> dict[tuple[int, int], F]:
    """Distribution of (minus, plus) increments in one independent round."""
    states = {(0, 0): F(1)}
    for law in laws:
        validate_probabilities(law)
        incoming: dict[tuple[int, int], F] = {}
        for (m, p), mass in states.items():
            for (dm, dp), probability in zip(((1, 0), (0, 0), (0, 1)), law, strict=True):
                if probability:
                    key = (m + dm, p + dp)
                    incoming[key] = incoming.get(key, F(0)) + mass * probability
        states = incoming
    return states


def enumerate_balanced(laws: Sequence[Probabilities], cap: int = 400) -> ExactResult:
    plan = balanced_plan(len(laws), cap)
    return enumerate_laws(list(laws) * (plan.max_pairs // len(laws)), plan)


def enumerate_laws(laws: Sequence[Probabilities], plan: Plan) -> ExactResult:
    """Position-dependent absorbing DP, usable for a fixed sampled schedule too."""
    if len(laws) != plan.max_pairs:
        raise ValueError("one law is required for every scheduled pair")
    if plan.rule.name == "adaptive":
        raise ValueError("count-based enumeration requires fixed stakes")
    weights: list[tuple[int, int, int, int]] = []
    final_scale = 1
    for law in laws:
        validate_probabilities(law)
        den = math.lcm(*(p.denominator for p in law))
        weights.append((int(law[0] * den), int(law[1] * den), int(law[2] * den), den))
        final_scale *= den
    boundaries = frontiers(plan)
    no_plus = all(w[2] == 0 for w in weights)
    no_zero = all(w[1] == 0 for w in weights)
    if no_plus or no_zero:
        return _binary(weights, plan, boundaries, no_plus)
    # Each coefficient is at most final_scale. Sum of ALL coefficients is also
    # at most final_scale, so binary folding sums digits without carries or wrap.
    width = final_scale.bit_length() + 1
    folds = digit_folds(width, plan.max_pairs)
    states = {0: 1}
    absorbed: dict[str, int] = dict.fromkeys(("PASS", "BLOCK", "ERROR"), 0)
    scale = 1
    cost = 0
    for n, (wm, wz, wp, den) in enumerate(weights, 1):
        cost = (cost + sum(digit_sum(value, folds) for value in states.values())) * den
        scale *= den
        absorbed = {v: mass * den for v, mass in absorbed.items()}
        incoming: dict[int, int] = {}
        for m, row in states.items():
            if wm:
                incoming[m + 1] = incoming.get(m + 1, 0) + row * wm
            if wz or wp:
                incoming[m] = incoming.get(m, 0) + row * wz + ((row * wp) << width)
        if plan.checkpoint(n):
            for m, row in list(incoming.items()):
                pass_min, block_max = boundaries[n][m]
                if pass_min <= block_max:
                    raise ArithmeticError("overlapping boundaries")
                low_bits = width * (block_max + 1)
                high_bits = width * pass_min
                low = row & ((1 << low_bits) - 1)
                high = row >> high_bits
                absorbed["BLOCK"] += digit_sum(low, folds)
                absorbed["PASS"] += digit_sum(high, folds)
                kept = row - low - (high << high_bits)
                if kept:
                    incoming[m] = kept
                else:
                    del incoming[m]
        states = incoming
    return _finish(absorbed, sum(digit_sum(row, folds) for row in states.values()), cost, scale)


def digit_folds(width: int, max_degree: int) -> tuple[tuple[int, int], ...]:
    """Masks for exact binary folding of at most max_degree+1 packed digits."""
    return tuple(
        (width * (1 << i), (1 << (width * (1 << i))) - 1)
        for i in range(max_degree.bit_length() - 1, -1, -1)
    )


def digit_sum(value: int, folds: tuple[tuple[int, int], ...]) -> int:
    """Sum digits with no carries: caller guarantees total < packing base.

    Fold the upper half onto the lower half, repeatedly. At each level the
    coefficients are sums of disjoint original digits, so the same no-carry
    bound holds. This equals value modulo base-1 but avoids long division.
    """
    for bits, mask in folds:
        value = (value & mask) + (value >> bits)
    return value


def _binary(
    weights: Sequence[tuple[int, int, int, int]],
    plan: Plan,
    boundaries: dict[int, Boundary],
    no_plus: bool,
) -> ExactResult:
    states = [1]
    absorbed: dict[str, int] = dict.fromkeys(("PASS", "BLOCK", "ERROR"), 0)
    scale = 1
    cost = 0
    for n, (wm, wz, wp, den) in enumerate(weights, 1):
        cost = (cost + sum(states)) * den
        scale *= den
        absorbed = {v: mass * den for v, mass in absorbed.items()}
        incoming = [0] * (len(states) + 1)
        for m, mass in enumerate(states):
            incoming[m] += mass * (wz if no_plus else wp)
            incoming[m + 1] += mass * wm
        if plan.checkpoint(n):
            for m, mass in enumerate(incoming):
                if mass:
                    v = boundary_verdict(boundaries[n], m, 0 if no_plus else n - m)
                    if v != "INCONCLUSIVE":
                        absorbed[v] += mass
                        incoming[m] = 0
        while len(incoming) > 1 and not incoming[-1]:
            incoming.pop()
        states = incoming
    return _finish(absorbed, sum(states), cost, scale)


def _finish(absorbed: dict[str, int], remaining: int, cost: int, scale: int) -> ExactResult:
    values = {v: F(mass, scale) for v, mass in absorbed.items()}
    values["INCONCLUSIVE"] = F(remaining, scale)
    if sum(values.values()) != 1:
        raise ArithmeticError("mass not conserved")
    return ExactResult(values, F(cost, scale))
