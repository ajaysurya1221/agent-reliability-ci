"""S1 research reference; deliberately independent of the ARCI product package.

Only rational/integer arithmetic enters decisions. Inputs are a planned stream,
not a store validator: an unused suffix is ignored after the first decisive look.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction
from typing import Literal

Verdict = Literal["PASS", "BLOCK", "INCONCLUSIVE", "ERROR"]
RuleName = Literal["fixed", "mixture", "adaptive"]
F = Fraction
DEFAULT_ALPHA = F(1, 20)
DEFAULT_DELTA = F(1, 10)


@dataclass(frozen=True)
class StakeRule:
    """Fractions of each direction's maximum legal stake; equal mixture weights.

    Adaptive: clipped, rational, regularized past mean / past second moment,
    damped by 1/2; quantized down to multiples of 1/64 of the legal maximum.
    The pseudodata have sum zero and squared sum one. No current observation
    enters its own stake. This is a heuristic, not a claim of optimality.
    """

    name: RuleName
    fractions: tuple[Fraction, ...] = (F(1, 2),)

    def __post_init__(self) -> None:
        if self.name not in ("fixed", "mixture", "adaptive"):
            raise ValueError("unknown stake rule")
        if not self.fractions or any(
            type(q) is not Fraction or not 0 <= q <= 1 for q in self.fractions
        ):
            raise ValueError("stakes must be Fractions in [0, 1]")
        if self.name != "mixture" and len(self.fractions) != 1:
            raise ValueError("only a mixture accepts multiple fractions")


RULES: dict[str, StakeRule] = {
    "fixed": StakeRule("fixed"),
    "mixture": StakeRule("mixture", (F(1, 8), F(1, 4), F(1, 2), F(3, 4))),
    "adaptive": StakeRule("adaptive"),
}


@dataclass(frozen=True)
class Plan:
    alpha: Fraction = DEFAULT_ALPHA
    delta: Fraction = DEFAULT_DELTA
    batch: int = 10
    max_pairs: int = 400
    rule: StakeRule = RULES["mixture"]

    def __post_init__(self) -> None:
        if type(self.alpha) is not Fraction or not 0 < self.alpha < 1:
            raise ValueError("alpha must be a Fraction strictly between 0 and 1")
        if type(self.delta) is not Fraction or not 0 < self.delta < 1:
            raise ValueError("delta must be a Fraction strictly between 0 and 1")
        if type(self.batch) is not int or self.batch < 1:
            raise ValueError("batch must be a positive integer")
        if type(self.max_pairs) is not int or self.max_pairs < 1:
            raise ValueError("max_pairs must be a positive integer")

    def checkpoint(self, n: int) -> bool:
        return n % self.batch == 0 or n == self.max_pairs


@dataclass(frozen=True)
class Checkpoint:
    pairs: int
    plus: Fraction
    minus: Fraction


@dataclass(frozen=True)
class Decision:
    verdict: Verdict
    stopping_pairs: int
    history: tuple[Checkpoint, ...]


def classify(plus: Fraction, minus: Fraction, alpha: Fraction) -> Verdict:
    """Inclusive integer comparisons, with explicit simultaneous-crossing handling."""
    passed = plus.numerator * alpha.numerator >= 2 * plus.denominator * alpha.denominator
    blocked = minus.numerator * alpha.numerator >= 2 * minus.denominator * alpha.denominator
    if passed and blocked:
        return "ERROR"
    return "PASS" if passed else "BLOCK" if blocked else "INCONCLUSIVE"


def adaptive_stakes(
    total: Fraction, squares: Fraction, delta: Fraction
) -> tuple[Fraction, Fraction]:
    """Only past shifted observations are inputs; rational quantization is explicit."""
    plus_cap, minus_cap = 1 / (1 - delta), 1 / (1 + delta)

    def stake(signed_total: Fraction, cap: Fraction) -> Fraction:
        raw = min(cap * F(3, 4), max(F(0), signed_total / (2 * (1 + squares))))
        ticks = (64 * raw / cap).__floor__()
        return cap * F(ticks, 64)

    return stake(total, plus_cap), stake(-total, minus_cap)


def decide(
    differences: Sequence[int],
    *,
    alpha: Fraction = DEFAULT_ALPHA,
    delta: Fraction = DEFAULT_DELTA,
    batch: int = 10,
    max_pairs: int = 400,
    rule: StakeRule = RULES["mixture"],
) -> Decision:
    """Decide a schedule-ordered stream, requiring enough pairs to reach a verdict.

    A terminal partial batch is always checked. Short inconclusive input raises;
    a future runner must turn missing/errored observations into ERROR, never 0.
    For arbitrary user stakes both tests can cross together: return ERROR.
    """
    plan = Plan(alpha, delta, batch, max_pairs, rule)
    if any(type(d) is not int or d not in (-1, 0, 1) for d in differences):
        raise ValueError("each difference must be an integer in {-1, 0, 1}")
    plus = [F(1) for _ in rule.fractions]
    minus = plus.copy()
    total, squares = F(0), F(0)
    history: list[Checkpoint] = []
    for n, d in enumerate(differences[:max_pairs], 1):
        x = d + delta
        if rule.name == "adaptive":
            lp, lm = adaptive_stakes(total, squares, delta)
            plus[0] *= 1 + lp * x
            minus[0] *= 1 - lm * x
        else:
            for j, q in enumerate(rule.fractions):
                plus[j] *= 1 + q * x / (1 - delta)
                minus[j] *= 1 - q * x / (1 + delta)
        total += x
        squares += x * x
        if plan.checkpoint(n):
            wp, wm = sum(plus, F(0)) / len(plus), sum(minus, F(0)) / len(minus)
            history.append(Checkpoint(n, wp, wm))
            verdict = classify(wp, wm, alpha)
            if verdict != "INCONCLUSIVE" or n == max_pairs:
                return Decision(verdict, n, tuple(history))
    raise ValueError("incomplete stream: no decisive checkpoint and max_pairs not reached")


def count_wealth(
    n: int, minus_count: int, plus_count: int, plan: Plan
) -> tuple[Fraction, Fraction]:
    """Recombining wealth for fixed/mixture rules; adaptive wealth is path-dependent."""
    if plan.rule.name == "adaptive":
        raise ValueError("adaptive wealth cannot be reduced to these counts")
    if min(n, minus_count, plus_count, n - minus_count - plus_count) < 0:
        raise ValueError("invalid counts")
    zero = n - minus_count - plus_count
    wp, wm = F(0), F(0)
    for q in plan.rule.fractions:
        lp, lm = q / (1 - plan.delta), q / (1 + plan.delta)
        wp += (
            (1 + lp * (-1 + plan.delta)) ** minus_count
            * (1 + lp * plan.delta) ** zero
            * (1 + lp * (1 + plan.delta)) ** plus_count
        )
        wm += (
            (1 - lm * (-1 + plan.delta)) ** minus_count
            * (1 - lm * plan.delta) ** zero
            * (1 - lm * (1 + plan.delta)) ** plus_count
        )
    return wp / len(plan.rule.fractions), wm / len(plan.rule.fractions)
