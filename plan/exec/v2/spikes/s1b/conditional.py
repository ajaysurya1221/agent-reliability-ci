"""Exact conditional-on-schedule enumeration for two declared boundary suites."""

from __future__ import annotations

import math
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from fractions import Fraction as F
from typing import TypedDict

from schedule import cell_index, schedule_key
from suite_stats import Plan
from suite_stats_sim import Boundary, boundary_verdict, characteristics, make_boundary

CELLS = tuple({"task_id": f"task-{i:02d}", "condition_id": "clean"} for i in range(20))


class ConditionalRow(TypedDict):
    index: int
    key: str
    draws_in_regressed_cells: int
    PASS: str
    BLOCK: str
    INCONCLUSIVE: str


def binary_enumeration(
    losses: Sequence[F], plan: Plan, boundaries: dict[int, Boundary]
) -> dict[str, F]:
    """Absorbing Poisson-binomial DP, integer masses with a common denominator.

    Outcomes are -1 and 0 only. Position-specific probabilities preserve schedule
    order and every checkpoint, rather than reducing to final allocation counts.
    """
    masses = [1]
    scale = 1
    passed = blocked = 0
    for n, loss in enumerate(losses, 1):
        if not 0 <= loss <= 1:
            raise ValueError("invalid loss probability")
        numerator, denominator = loss.numerator, loss.denominator
        incoming = [0] * (len(masses) + 1)
        for m, mass in enumerate(masses):
            incoming[m] += mass * (denominator - numerator)
            incoming[m + 1] += mass * numerator
        scale *= denominator
        passed *= denominator
        blocked *= denominator
        if plan.checkpoint(n):
            for m, mass in enumerate(incoming):
                if not mass:
                    continue
                verdict = boundary_verdict(boundaries[n], m, 0)
                if verdict == "PASS":
                    passed += mass
                    incoming[m] = 0
                elif verdict == "BLOCK":
                    blocked += mass
                    incoming[m] = 0
                elif verdict == "ERROR":
                    raise ArithmeticError("simultaneous crossing")
        while len(incoming) > 1 and incoming[-1] == 0:
            incoming.pop()
        masses = incoming
    result = {
        "PASS": F(passed, scale),
        "BLOCK": F(blocked, scale),
        "INCONCLUSIVE": F(sum(masses), scale),
    }
    if sum(result.values()) != 1:
        raise ArithmeticError("mass not conserved")
    return result


def conditional_worker(job: tuple[int, Plan, dict[int, Boundary]]) -> ConditionalRow:
    index, plan, boundaries = job
    # Synthetic identities fixed independently of outcomes; no search for favourable keys.
    key = schedule_key(CELLS, "boundary-baseline-v1", f"boundary-candidate-{index:04d}", plan)
    draws = [cell_index(key, i, 20) for i in range(plan.max_pairs)]
    values = binary_enumeration([F(2, 3) if c < 3 else F(0) for c in draws], plan, boundaries)
    return ConditionalRow(
        index=index,
        key=key.hex(),
        draws_in_regressed_cells=sum(c < 3 for c in draws),
        PASS=str(values["PASS"]),
        BLOCK=str(values["BLOCK"]),
        INCONCLUSIVE=str(values["INCONCLUSIVE"]),
    )


def describe(values: list[F]) -> dict[str, float]:
    ordered = sorted(values)
    n = len(values)
    return {
        "mean": float(sum(values, F(0)) / n),
        "min": float(ordered[0]),
        "median": float((ordered[(n - 1) // 2] + ordered[n // 2]) / 2),
        "p90": float(ordered[math.ceil(F(9, 10) * n) - 1]),
        "p99": float(ordered[math.ceil(F(99, 100) * n) - 1]),
        "max": float(ordered[-1]),
    }


def conditional_study(pool: ProcessPoolExecutor, plan: Plan) -> dict[str, object]:
    boundaries = dict(make_boundary((plan, n)) for n in range(10, 401, 10))
    rows = list(
        pool.map(conditional_worker, ((i, plan, boundaries) for i in range(2000)), chunksize=10)
    )
    uniform = binary_enumeration([F(1, 10)] * 400, plan, boundaries)
    reference = characteristics((F(1, 10), F(9, 10), F(0)), plan, boundaries)[0]
    if any(uniform[v] != F(reference["lower"][v]) for v in uniform):
        raise AssertionError("conditional recurrence disagrees with S1 enumeration")
    statistics: dict[str, dict[str, dict[str, float]]] = {}
    checks: dict[str, dict[str, float | bool]] = {}
    for scenario in ("concentrated", "even"):
        statistics[scenario] = {}
        for direction in ("PASS", "BLOCK"):
            values = (
                [F(r[direction]) for r in rows]
                if scenario == "concentrated"
                else [uniform[direction]] * 2000
            )
            statistics[scenario][direction] = describe(values)
            mean = sum(values, F(0)) / len(values)
            variance = sum(((v - mean) ** 2 for v in values), F(0)) / (len(values) - 1)
            se = math.sqrt(float(variance / len(values)))
            difference = abs(float(mean - uniform[direction]))
            # Declared before results: five SE plus numerical 1e-12 for this finite-key check.
            checks[f"{scenario}_{direction}"] = {
                "absolute_difference": difference,
                "standard_error": se,
                "within_five_se": difference <= 5 * se + 1e-12,
            }
            if difference > 5 * se + 1e-12:
                raise AssertionError("finite-key mean failed predeclared five-SE agreement")
    return {
        "laws": {
            "concentrated": "3/20 cells: P(-1)=2/3; 17/20: P(0)=1",
            "even": "20/20 cells: P(-1)=1/10, P(0)=9/10",
        },
        "rows": rows,
        "even_rows": [
            {"index": r["index"], "key": r["key"], **{v: str(p) for v, p in uniform.items()}}
            for r in rows
        ],
        "statistics": statistics,
        "iid_reference": reference,
        "checks": checks,
    }
