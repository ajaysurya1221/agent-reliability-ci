"""Published rounded v1 inputs; never infer missing power or dependence results."""

from __future__ import annotations

import math
import random
from concurrent.futures import ProcessPoolExecutor
from typing import TypedDict

from stake_selection import Row, enumerate_job, law, plan_for
from suite_stats import decide
from suite_stats_sim import characteristics

SCENARIOS = ((95, 95), (95, 75), (95, 65), (80, 80), (95, 85))


class V1Row(TypedDict):
    a: int
    b: int
    method: str
    correct: float | None
    PASS: float | None
    BLOCK: float | None
    expected_sessions: float
    ceiling_sessions: int


def published() -> list[V1Row]:
    rows: list[V1Row] = []
    cp = ((0.889, 0.000), (0.000, 0.365), (0.000, 0.985), (0.218, 0.000), (0.001, 0.000))
    nc = ((0.989, None), (None, 0.838), (None, 0.9998), (0.706, None), (0.025, 0.022))
    for method, values in (("Clopper-Pearson fixed", cp), ("Newcombe fixed", nc)):
        for (a, b), (passed, blocked) in zip(SCENARIOS, values, strict=True):
            rows.append(
                V1Row(
                    a=a,
                    b=b,
                    method=method,
                    correct=None if a - b == 10 else passed if a == b else blocked,
                    PASS=passed,
                    BLOCK=blocked,
                    expected_sessions=400.0,
                    ceiling_sessions=400,
                )
            )
    for method, values in (
        ("Clopper-Pearson sequential", ((95, 0.735, None, 350.0), (65, None, 0.943, 302.0))),
        ("Newcombe sequential", ((95, 0.969, None, 239.0), (65, None, 0.9989, 159.0))),
    ):
        for b, passed, blocked, cost in values:
            rows.append(
                V1Row(
                    a=95,
                    b=b,
                    method=method,
                    correct=passed if b == 95 else blocked,
                    PASS=passed,
                    BLOCK=blocked,
                    expected_sessions=cost,
                    ceiling_sessions=400,
                )
            )
    return rows


def comparison(pool: ProcessPoolExecutor, selected: list[Row], winner: int) -> dict[str, object]:
    rows = [r for r in selected if r["candidate"] == winner and (r["a"], r["b"]) in SCENARIOS]
    rows.extend(
        pool.map(enumerate_job, [(95, 85, d, winner) for d in ("independent", "intermediate")])
    )
    ordered = sorted(rows, key=lambda r: (SCENARIOS.index((r["a"], r["b"])), r["dependence"]))
    return {
        "v1": published(),
        "v2": ordered,
        "bottom_lines": [
            "Clopper-Pearson fixed: mixed overall; at the same 400-session ceiling, v2 "
            "has higher correct-decision probability and lower expected sessions in all four "
            "measured non-margin independent cases, but higher boundary error rates.",
            "Newcombe fixed: mixed; at cap 200, v2 has lower correct-decision probability "
            "and lower expected sessions in all four measured independent cases; at cap 400 "
            "power is higher in all four, but the ceiling doubles and the 0.80 no-change "
            "case averages 482.76 sessions versus 400.",
            "Newcombe sequential: mixed; for both published independent cases v2 at cap 200 "
            "uses fewer expected sessions with lower power; at cap 400 it has higher power "
            "and lower expected sessions, with twice the ceiling (800 versus 400).",
        ],
    }


def simulation_agreement() -> dict[str, object]:
    plan = plan_for(1)
    probabilities = law(80, 80, "independent")
    exact = characteristics(probabilities, plan)[0]
    rng = random.Random(20261110)
    reps = 1000
    counts = dict.fromkeys(("PASS", "BLOCK", "INCONCLUSIVE", "ERROR"), 0)
    total_pairs = 0
    for _ in range(reps):
        # Independently sample paired Bernoulli outcomes; no frontier classifies a stream.
        stream = [int(rng.random() < 0.8) - int(rng.random() < 0.8) for _ in range(400)]
        result = decide(
            stream,
            alpha=plan.alpha,
            delta=plan.delta,
            batch=plan.batch,
            max_pairs=plan.max_pairs,
            rule=plan.rule,
        )
        counts[result.verdict] += 1
        total_pairs += result.stopping_pairs
    for direction, count in counts.items():
        probability = exact["summary"][direction]
        tolerance = 5 * math.sqrt(probability * (1 - probability) / reps) + 1 / reps
        assert abs(count / reps - probability) <= tolerance
    return {
        "reps": reps,
        "seed": 20261110,
        "counts": counts,
        "expected_counts": {v: reps * exact["summary"][v] for v in counts},
        "mean_pairs": total_pairs / reps,
        "exact_mean_pairs": exact["summary"]["mean"],
        "check": "within five binomial SE plus 1/reps",
    }
