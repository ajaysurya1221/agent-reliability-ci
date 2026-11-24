"""Release gates for complete binary pairs, ordered by round. Costs are pairs."""

from __future__ import annotations

import math
from collections.abc import Sequence
from fractions import Fraction
from functools import lru_cache
from random import Random
from statistics import NormalDist
from typing import NamedTuple

from arci.outcome_schema import OutcomeRule
from arci.outcomes import rule_of
from arci.suite_gate import RoundIncrement, walk_rounds

TASKS = 20
ROUNDS = 20
CAP = TASKS * ROUNDS
RESAMPLES = 2_000
OUTCOMES = ("PASS", "BLOCK", "INCONCLUSIVE", "ERROR")
RIVALS = ("score_margin", "bootstrap_margin", "cs_margin")
MARGIN_GATES = ("arci", *RIVALS)
GATES = ("arci", "threshold", "mcnemar", "bootstrap_zero", "cs_zero", *RIVALS)
RULE = OutcomeRule(
    schema_version="arci-outcomes/1",
    suite_id="b1",
    tasks=tuple(f"task-{i:02}" for i in range(1, TASKS + 1)),
    fixed_before_runs=True,
    alpha="1/20",
    margin="1/10",
    max_rounds=ROUNDS,
    max_errored_pairs=0,
)
STATS_RULE = rule_of(RULE)
Z = NormalDist().inv_cdf(0.975)


class Counts(NamedTuple):
    neither: int
    plus: int  # candidate alone passed
    minus: int  # baseline alone passed
    both: int


class Decision(NamedTuple):
    verdict: str
    pairs: int


def arci_gate(rounds: Sequence[Counts]) -> Decision:
    increments = (RoundIncrement(c.minus, c.neither + c.both, c.plus, 0, 0) for c in rounds)
    last = walk_rounds(STATS_RULE, increments)[-1]
    return Decision(last.verdict.value, last.pairs)


def classify(lower: float | Fraction, upper: float | Fraction, target: float | Fraction) -> str:
    if lower > target:
        return "PASS"
    if upper < target:
        return "BLOCK"
    return "INCONCLUSIVE"


@lru_cache(maxsize=4096)
def mcnemar(plus: int, minus: int) -> str:
    discordant = plus + minus
    tail = sum(math.comb(discordant, i) for i in range(min(plus, minus) + 1))
    # Twice the smaller exact Binomial(d, 1/2) tail <= 1/20.
    if 40 * tail <= 2**discordant:
        return "PASS" if plus > minus else "BLOCK"
    return "INCONCLUSIVE"


def bootstrap_interval(plus: int, minus: int, n: int, rng: Random) -> tuple[Fraction, Fraction]:
    """2,000 iid bootstrap means via the exact multinomial resampling law."""
    if plus + minus == 0 or plus == n or minus == n:
        value = Fraction(plus - minus, n)
        return value, value
    binomial = rng.binomialvariate
    if plus == 0 or minus == 0:
        sign = 1 if plus else -1
        p = (plus + minus) / n
        values = sorted(sign * binomial(n, p) for _ in range(RESAMPLES))
    else:
        p = plus / n
        conditional_minus = minus / (n - plus)
        values = []
        for _ in range(RESAMPLES):
            pos = binomial(n, p)
            neg = binomial(n - pos, conditional_minus)
            values.append(pos - neg)
        values.sort()

    def percentile(numerator: int) -> Fraction:
        index, remainder = divmod((RESAMPLES - 1) * numerator, 40)
        return Fraction(values[index] * (40 - remainder) + values[index + 1] * remainder, 40 * n)

    return percentile(1), percentile(39)


@lru_cache(maxsize=64)
def cs_width(n: int) -> float:
    # Howard et al. (2021), two-sided normal mixture. Range 2 gives V_n=n.
    rho = 20
    return math.sqrt((n + rho) * math.log((n + rho) / (rho * 0.05**2))) / n


def cs_gate(rounds: Sequence[Counts], target: float) -> Decision:
    total = n = 0
    for counts in rounds:
        n += sum(counts)
        total += counts.plus - counts.minus
        width = cs_width(n)
        verdict = classify(total / n - width, total / n + width, target)
        if verdict != "INCONCLUSIVE":
            return Decision(verdict, n)
    return Decision("INCONCLUSIVE", n)


@lru_cache(maxsize=8192)
def tango_interval(plus: int, minus: int, n: int) -> tuple[float, float]:
    """Invert Tango's uncorrected paired score test (1998), including boundary MLEs."""
    difference = (plus - minus) / n
    discordance = (plus + minus) / n

    def accepted(d: float) -> bool:
        # Under D=d the nuisance s=P(discordant) is in [|d|,1].
        # The larger likelihood root includes the endpoint when a cell is empty.
        b = discordance + difference * d
        c = difference * d - (1 - discordance) * d * d
        s = (b + math.sqrt(max(0.0, b * b - 4 * c))) / 2
        s = min(1.0, max(abs(d), s))
        return n * (difference - d) ** 2 <= Z**2 * (s - d * d)

    def endpoint(outside: float) -> float:
        inside = difference
        for _ in range(54):
            mid = (inside + outside) / 2
            if accepted(mid):
                inside = mid
            else:
                outside = mid
        return (inside + outside) / 2

    return endpoint(-1.0), endpoint(1.0)


def decisions(rounds: Sequence[Counts], bootstrap_rng: Random) -> dict[str, Decision]:
    if len(rounds) != ROUNDS or any(sum(r) != TASKS or min(r) < 0 for r in rounds):
        raise ValueError("expected twenty complete rounds of twenty pairs")
    plus = sum(r.plus for r in rounds)
    minus = sum(r.minus for r in rounds)
    candidate = plus + sum(r.both for r in rounds)
    bootstrap = bootstrap_interval(plus, minus, CAP, bootstrap_rng)
    return {
        "arci": arci_gate(rounds),
        "threshold": Decision("PASS" if 5 * candidate >= 4 * CAP else "BLOCK", CAP),
        "mcnemar": Decision(mcnemar(plus, minus), CAP),
        "bootstrap_zero": Decision(classify(*bootstrap, 0), CAP),
        "cs_zero": cs_gate(rounds, 0),
        "score_margin": Decision(classify(*tango_interval(plus, minus, CAP), -0.1), CAP),
        "bootstrap_margin": Decision(classify(*bootstrap, Fraction(-1, 10)), CAP),
        "cs_margin": cs_gate(rounds, -0.1),
    }
