"""Reproducible calibration, power and end-to-end experiments; no real-log access."""

from __future__ import annotations

import argparse
import json
import math
import random
import tempfile
from collections import Counter
from datetime import date, timedelta
from fractions import Fraction
from itertools import combinations
from pathlib import Path
from time import perf_counter

from daytable import build_daytable
from decide import Measure, Point, decide, decide_days
from rank_test import Exact, brute_p_lower, p_lower
from readers import discover_claude, discover_codex, read_claude, read_codex
from records import JSON, ReadResult, Tool
from synth import generate, schedule

HERE = Path(__file__).resolve().parent
DESIGNS = ((5, 10), (7, 21), (14, 42), (28, 84))
SEED = 15112026


def exact_checks() -> dict[str, JSON]:
    labelings = comparisons = 0
    worst = {Fraction(1, 40): Fraction(0), Fraction(1, 120): Fraction(0)}
    for total in range(2, 15):
        for m in range(1, total):
            for pooled in (list(range(total)), [i % 3 for i in range(total)], [0] * total):
                rejected = dict.fromkeys(worst, 0)
                seen: dict[int, Fraction] = {}
                all_count = math.comb(total, m)
                for chosen in combinations(range(total), m):
                    subset = set(chosen)
                    before = [v for i, v in enumerate(pooled) if i not in subset]
                    after = [v for i, v in enumerate(pooled) if i in subset]
                    p = p_lower(before, after)
                    # Independent midrank formula. Enumerate brute force once per
                    # attainable statistic, then check EVERY labeling against it.
                    signature = sum(
                        sum(x < v for x in pooled) + sum(x <= v for x in pooled) + 1 for v in after
                    )
                    if signature not in seen:
                        seen[signature] = brute_p_lower(before, after)
                        comparisons += 1
                    assert p == seen[signature]
                    for alpha in worst:
                        rejected[alpha] += p <= alpha
                    labelings += 1
                for alpha in worst:
                    rate = Fraction(rejected[alpha], all_count)
                    assert rate <= alpha
                    worst[alpha] = max(worst[alpha], rate)
    return {
        "labelings": labelings,
        "comparisons": comparisons,
        "equal": True,
        "max_rate_40": float(worst[Fraction(1, 40)]),
        "max_rate_120": float(worst[Fraction(1, 120)]),
    }


def samples(rng: random.Random, count: int, sd: float, rho: float = 0.0) -> list[int]:
    value = rng.gauss(0, sd)
    result: list[int] = []
    for i in range(count):
        if i:
            value = rho * value + rng.gauss(0, sd * math.sqrt(1 - rho * rho))
        result.append(max(1, round(math.exp(value) * 10**9)))
    return result


def run_trial(
    rng: random.Random,
    before_n: int,
    after_n: int,
    sd: float,
    drop: Fraction = Fraction(0),
    identical: bool = False,
    rho: float = 0.0,
) -> str:
    total = before_n + after_n
    m1 = samples(rng, total, sd, rho)
    before: dict[Measure, list[Point]] = {}
    after: dict[Measure, list[Point]] = {}
    for name in ("m1", "m2", "m3"):
        if name == "m1":
            values: list[Exact] = [
                *m1[:before_n],
                *(Fraction(v) * (1 - drop) for v in m1[before_n:]),
            ]
        elif identical:
            # Higher-is-worse shares have the same adverse ranks as lower-is-worse m1.
            values = [Fraction(1, 1 + v) for v in m1]
        else:
            raw = samples(rng, total, sd, rho)
            # Smooth bounded shares, independent across gating measures.
            values = [Fraction(v, 20 * (10**9 + v)) for v in raw]
        points = [(date(2026, 1, 1) + timedelta(days=i), v) for i, v in enumerate(values)]
        before[name], after[name] = points[:before_n], points[before_n:]
    return decide(before, after, "claude").verdict


def experiment(
    seed: int,
    after: int,
    before: int,
    count: int,
    sd: float = 0.45,
    drop: Fraction = Fraction(0),
    identical: bool = False,
    rho: float = 0.0,
    time_budget: float = 40.0,
) -> dict[str, JSON]:
    rng = random.Random(seed)
    outcomes: Counter[str] = Counter()
    start = perf_counter()
    used = 0
    for used in range(1, count + 1):
        outcomes[run_trial(rng, before, after, sd, drop, identical, rho)] += 1
        # Predeclared wall-time truncation at fixed blocks, never based on outcomes.
        if used >= 1000 and used % 250 == 0 and perf_counter() - start >= time_budget:
            break
    return {
        "seed": seed,
        "after": after,
        "before": before,
        "count": used,
        "requested": count,
        "sd": sd,
        "drop": float(drop),
        "rho": rho,
        "real_drop": outcomes["REAL DROP"] / used,
        "no_drop": outcomes["NO DROP"] / used,
        "real_drop_count": outcomes["REAL DROP"],
        "no_drop_count": outcomes["NO DROP"],
        "cannot_tell": outcomes["CANNOT TELL"] / used,
        "seconds": round(perf_counter() - start, 3),
    }


def pipeline(count: int = 50) -> list[dict[str, JSON]]:
    scratch = HERE / ".scratch"
    scratch.mkdir(exist_ok=True)
    rows: list[dict[str, JSON]] = []
    for drop in (0.0, 0.45):
        outcomes: dict[str, Counter[str]] = {"claude": Counter(), "codex": Counter()}
        for i in range(count):
            seed = SEED + 10000 + i + (1000 if drop else 0)
            with tempfile.TemporaryDirectory(dir=scratch) as directory:
                generated = generate(Path(directory), seed, schedule(drop=drop), compressed=False)
                results: tuple[tuple[Tool, ReadResult], ...] = (
                    ("claude", read_claude(discover_claude(generated.claude_root))),
                    ("codex", read_codex(discover_codex(generated.codex_root, generated.cwd))),
                )
                for tool, result in results:
                    for key, value in generated.expected[tool].items():
                        assert getattr(result.counters, key) == value
                    groups = build_daytable(result.records)
                    assert len(groups) == 1
                    days = next(iter(groups.values()))
                    assert len(days) == 56
                    decision = decide_days(days, days[-1].date - timedelta(days=14), tool)
                    outcomes[tool][decision.verdict] += 1
        for tool, counts in outcomes.items():
            rows.append(
                {
                    "tool": tool,
                    "count": count,
                    "seed_first": SEED + 10000 + (1000 if drop else 0),
                    "seed_last": SEED + 10000 + count - 1 + (1000 if drop else 0),
                    "drop": drop,
                    "sd": 0.4,
                    "real_drop": counts["REAL DROP"] / count,
                    "no_drop": counts["NO DROP"] / count,
                }
            )
    return rows


def table(rows: list[dict[str, JSON]], columns: list[str]) -> str:
    output = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for row in rows:
        output.append(
            "| "
            + " | ".join(
                f"{row[c]:.5f}" if isinstance(row[c], float) else str(row[c]) for c in columns
            )
            + " |"
        )
    return "\n".join(output)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--null-count", type=int, default=20000)
    parser.add_argument("--power-count", type=int, default=2000)
    args = parser.parse_args()
    null_count: int = args.null_count
    power_count: int = args.power_count
    started = perf_counter()
    exact = exact_checks()
    print("exact", json.dumps(exact), flush=True)
    null_rows: list[dict[str, JSON]] = []
    power_rows: list[dict[str, JSON]] = []
    ar_rows: list[dict[str, JSON]] = []
    seed = SEED
    for after, before in DESIGNS:
        for scenario in ("independent", "identical", "margin"):
            seed += 1
            row = experiment(
                seed,
                after,
                before,
                null_count,
                drop=Fraction(1, 4) if scenario == "margin" else Fraction(0),
                identical=scenario == "identical",
                time_budget=60,
            )
            row["scenario"] = scenario
            wrong = row["no_drop_count"] if scenario == "margin" else row["real_drop_count"]
            count = row["count"]
            assert isinstance(wrong, int) and isinstance(count, int)
            row["pass"] = Fraction(wrong, count) <= Fraction(283, 10000)
            null_rows.append(row)
            print("null", json.dumps(row), flush=True)
        seed += 1
        row = experiment(seed, after, before, null_count, rho=0.5, time_budget=45)
        ar_rows.append(row)
        print("ar1", json.dumps(row), flush=True)
        for sd in (0.35, 0.45, 0.55):
            for drop in (0, 33, 45, 50, 55):
                seed += 1
                row = experiment(
                    seed, after, before, power_count, sd=sd, drop=Fraction(drop, 100), time_budget=5
                )
                power_rows.append(row)
                print("power", json.dumps(row), flush=True)
    pipeline_rows = pipeline()
    result: dict[str, JSON] = {
        "seed": SEED,
        "exact": exact,
        "null": list(null_rows),
        "power": list(power_rows),
        "ar1": list(ar_rows),
        "pipeline": list(pipeline_rows),
        "seconds": round(perf_counter() - started, 3),
    }
    (HERE / "simulation.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    sections = [
        "## Exact enumeration\n\n" + table([exact], list(exact)),
        "## Null calibration\n\n"
        + table(
            null_rows,
            [
                "scenario",
                "after",
                "before",
                "seed",
                "requested",
                "count",
                "real_drop",
                "no_drop",
                "pass",
            ],
        ),
        "## Power and unchanged NO DROP\n\n"
        + table(
            power_rows, ["after", "before", "sd", "drop", "seed", "count", "real_drop", "no_drop"]
        ),
        "## AR(1), descriptive only\n\n"
        + table(ar_rows, ["after", "before", "seed", "count", "rho", "real_drop", "no_drop"]),
        "## Synthetic logs through the full pipeline\n\n"
        + table(
            pipeline_rows,
            ["tool", "drop", "sd", "seed_first", "seed_last", "count", "real_drop", "no_drop"],
        ),
    ]
    tables = "\n\n".join(sections) + "\n"
    (HERE / "simulation-tables.md").write_text(tables, encoding="utf-8")
    print(tables, flush=True)


if __name__ == "__main__":
    main()
