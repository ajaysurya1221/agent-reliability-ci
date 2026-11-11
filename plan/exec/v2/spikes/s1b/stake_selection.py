"""Preregistered stake grid; exact absorbing enumeration imports S1 unchanged."""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from fractions import Fraction as F
from typing import TypedDict

from suite_stats import Plan, StakeRule
from suite_stats_sim import Enclosure, Probabilities, characteristics, make_boundary, trinomial

CANDIDATES = (
    (F(1, 2),),
    (F(1, 4), F(1, 2)),
    (F(1, 4), F(1, 2), F(3, 4)),
    (F(1, 8), F(1, 4), F(1, 2)),
    (F(1, 8), F(1, 4), F(1, 2), F(3, 4)),
)
BASELINES = (50, 65, 80, 90, 95, 99)
REGRESSIONS = (0, 20, 30)
DEPENDENCES = ("independent", "intermediate")


def plan_for(index: int, cap: int = 400) -> Plan:
    return Plan(max_pairs=cap, rule=StakeRule("mixture", CANDIDATES[index]))


def law(a: int, b: int, dependence: str) -> Probabilities:
    independent = trinomial(F(a, 100), F(b, 100), "independent")
    if dependence == "independent":
        return independent
    if dependence != "intermediate":
        raise ValueError("unknown dependence")
    positive = trinomial(F(a, 100), F(b, 100), "positive")
    return (
        (independent[0] + positive[0]) / 2,
        (independent[1] + positive[1]) / 2,
        (independent[2] + positive[2]) / 2,
    )


class Row(TypedDict):
    a: int
    b: int
    dependence: str
    candidate: int
    correct: float
    expected_pairs: float
    enumeration: list[Enclosure]


def enumerate_job(job: tuple[int, int, str, int]) -> Row:
    a, b, dependence, index = job
    plan = plan_for(index)
    boundaries = dict(make_boundary((plan, n)) for n in range(10, 401, 10))
    rows = characteristics(law(a, b, dependence), plan, boundaries, caps=(200, 400))
    if any(r["lost"] != "0" or r["lower"] != r["upper"] for r in rows):
        raise ArithmeticError("enumeration must be exact, without lost mass")
    final = rows[-1]["summary"]
    return Row(
        a=a,
        b=b,
        dependence=dependence,
        candidate=index,
        correct=final["PASS" if a == b else "BLOCK"],
        expected_pairs=final["mean"],
        enumeration=rows,
    )


def selection(pool: ProcessPoolExecutor) -> tuple[list[Row], int, list[dict[str, float | int]]]:
    jobs = [
        (a, a - regression, dep, index)
        for a in BASELINES
        for regression in REGRESSIONS
        for dep in DEPENDENCES
        for index in range(5)
    ]
    rows = list(pool.map(enumerate_job, jobs))
    scores = [
        {
            "candidate": index,
            "minimum_correct": min(r["correct"] for r in rows if r["candidate"] == index),
            "mean_expected_pairs": sum(r["expected_pairs"] for r in rows if r["candidate"] == index)
            / 36,
        }
        for index in range(5)
    ]
    # Exact rational probability comparisons determine inclusion in the 0.01 tie band.
    minima = [
        min(
            F(r["enumeration"][-1]["lower"]["PASS" if r["a"] == r["b"] else "BLOCK"])
            for r in rows
            if r["candidate"] == index
        )
        for index in range(5)
    ]
    best = max(minima)
    eligible = [i for i in range(5) if best - minima[i] <= F(1, 100)]
    winner = min(eligible, key=lambda i: (scores[i]["mean_expected_pairs"], len(CANDIDATES[i]), i))
    return rows, winner, scores
