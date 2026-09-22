"""Calibration self-checks for the frozen statistical gate."""

from __future__ import annotations

import argparse
import json
import math
import random
from functools import cache
from pathlib import Path
from typing import TypedDict

from arci.gate import classify
from arci.stats import clopper_pearson_tail, difference_bounds, newcombe

_OUTCOMES = ("PASS", "BLOCK", "INCONCLUSIVE")
_SAMPLE_SIZES = (20, 50, 100, 200, 400)
_SCENARIOS = (
    (0.95, 0.95),
    (0.95, 0.90),
    (0.95, 0.85),
    (0.95, 0.75),
    (0.95, 0.65),
    (0.80, 0.80),
    (0.80, 0.70),
    (0.80, 0.50),
)


class Row(TypedDict):
    p_a: float
    p_b: float
    n: int
    PASS: float
    BLOCK: float
    INCONCLUSIVE: float


def _validate_probability(value: float, name: str) -> None:
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be between 0 and 1")


@cache
def _intervals(n: int, tail: float) -> tuple[tuple[float, float], ...]:
    return tuple(clopper_pearson_tail(successes, n, tail) for successes in range(n + 1))


def _binomial_pmf(p: float, n: int) -> tuple[float, ...]:
    if p == 0.0:
        return (1.0, *([0.0] * n))
    if p == 1.0:
        return (*([0.0] * n), 1.0)
    log_p = math.log(p)
    log_q = math.log1p(-p)
    log_n_factorial = math.lgamma(n + 1)
    logs = tuple(
        log_n_factorial - math.lgamma(x + 1) - math.lgamma(n - x + 1) + x * log_p + (n - x) * log_q
        for x in range(n + 1)
    )
    largest = max(logs)
    weights = tuple(math.exp(value - largest) for value in logs)
    total = math.fsum(weights)
    return tuple(weight / total for weight in weights)


@cache
def _verdict_table(method: str, n: int, alpha: float, delta: float, k: int) -> tuple[str, ...]:
    """Verdict for every (x_a, x_b) pair, flattened as x_a * (n + 1) + x_b."""
    if method == "newcombe":
        confidence = 1.0 - alpha / k
        return tuple(
            classify(*newcombe(a, n, b, n, confidence), delta).value
            for a in range(n + 1)
            for b in range(n + 1)
        )
    intervals = _intervals(n, alpha / (4.0 * k))
    return tuple(
        classify(*difference_bounds(baseline=intervals[a], candidate=intervals[b]), delta).value
        for a in range(n + 1)
        for b in range(n + 1)
    )


def operating_characteristics(
    p_a: float,
    p_b: float,
    n: int,
    *,
    alpha: float = 0.05,
    delta: float = 0.10,
    k: int = 1,
    method: str = "clopper_pearson",
) -> dict[str, float]:
    """Exactly enumerate gate verdict probabilities for independent binomial arms."""
    _validate_probability(p_a, "p_a")
    _validate_probability(p_b, "p_b")
    if not 1 <= n <= 10_000:
        raise ValueError("n must be between 1 and 10000")
    if not 0.0 < delta < 1.0:
        raise ValueError("delta must be strictly between 0 and 1")
    if method not in {"clopper_pearson", "newcombe"}:
        raise ValueError(f"unknown interval method {method!r}")
    table = _verdict_table(method, n, alpha, delta, k)
    pmf_a = _binomial_pmf(p_a, n)
    pmf_b = _binomial_pmf(p_b, n)
    masses: dict[str, list[float]] = {outcome: [] for outcome in _OUTCOMES}
    width = n + 1
    for successes_a, probability_a in enumerate(pmf_a):
        row = successes_a * width
        for successes_b, probability_b in enumerate(pmf_b):
            masses[table[row + successes_b]].append(probability_a * probability_b)
    result = {outcome: math.fsum(masses[outcome]) for outcome in _OUTCOMES}
    total = math.fsum(result.values())
    if abs(total - 1.0) > 1e-9:
        raise ArithmeticError("enumerated probabilities do not sum to one")
    result["INCONCLUSIVE"] += 1.0 - total
    return result


def correlated_boundary(
    p_a: float,
    p_b: float,
    n: int,
    rho: float,
    *,
    reps: int = 10_000,
    seed: int = 0,
) -> dict[str, float]:
    """Simulate paired Bernoulli arms with positive shared-uniform dependence."""
    _validate_probability(p_a, "p_a")
    _validate_probability(p_b, "p_b")
    if not 1 <= n <= 10_000:
        raise ValueError("n must be between 1 and 10000")
    if not 0.0 <= rho <= 1.0:
        raise ValueError("rho must be between 0 and 1")
    if reps < 1:
        raise ValueError("reps must be at least 1")
    intervals = _intervals(n, 0.05 / 4.0)
    rng = random.Random(seed)
    counts = {outcome: 0 for outcome in _OUTCOMES}
    for _ in range(reps):
        successes_a = 0
        successes_b = 0
        for _ in range(n):
            if rng.random() < rho:
                draw = rng.random()
                successes_a += draw < p_a
                successes_b += draw < p_b
            else:
                successes_a += rng.random() < p_a
                successes_b += rng.random() < p_b
        bounds = difference_bounds(
            baseline=intervals[successes_a], candidate=intervals[successes_b]
        )
        counts[classify(*bounds, 0.10).value] += 1
    return {outcome: counts[outcome] / reps for outcome in _OUTCOMES}


def boundary_calibration(
    method: str,
    n: int,
    *,
    alpha: float = 0.05,
    delta: float = 0.10,
    k: int = 1,
    step: float = 0.01,
) -> dict[str, float]:
    """Worst directional errors around the margin, by exact enumeration.

    Sweeps p_a from 0.5 to 0.99 in `step`s along the boundary p_b = p_a - delta and the no-change
    line p_b = p_a, each with offsets of 0.001 and 0.01 on both sides. false_pass is the largest
    P(PASS) where the true difference is <= -delta; false_block the largest P(BLOCK) where it is
    >= -delta. Both must stay <= alpha.
    """
    offsets = (-0.01, -0.001, 0.0, 0.001, 0.01)
    worst_pass, worst_block = 0.0, 0.0
    where_pass: tuple[float, float] = (0.0, 0.0)
    where_block: tuple[float, float] = (0.0, 0.0)
    steps = round((0.99 - 0.5) / step)
    for index in range(steps + 1):
        p_a = round(0.5 + index * step, 6)
        for base in (p_a - delta, p_a):
            for offset in offsets:
                p_b = round(base + offset, 6)
                if not 0.0 < p_b < 1.0:
                    continue
                result = operating_characteristics(
                    p_a, p_b, n, alpha=alpha, delta=delta, k=k, method=method
                )
                difference = p_b - p_a
                if difference <= -delta + 1e-12 and result["PASS"] > worst_pass:
                    worst_pass, where_pass = result["PASS"], (p_a, p_b)
                if difference >= -delta - 1e-12 and result["BLOCK"] > worst_block:
                    worst_block, where_block = result["BLOCK"], (p_a, p_b)
    return {
        "false_pass": worst_pass,
        "false_pass_at_p_a": where_pass[0],
        "false_pass_at_p_b": where_pass[1],
        "false_block": worst_block,
        "false_block_at_p_a": where_block[0],
        "false_block_at_p_b": where_block[1],
    }


def _row(p_a: float, p_b: float, n: int, values: dict[str, float]) -> Row:
    return {
        "p_a": p_a,
        "p_b": p_b,
        "n": n,
        "PASS": values["PASS"],
        "BLOCK": values["BLOCK"],
        "INCONCLUSIVE": values["INCONCLUSIVE"],
    }


def _print_table(title: str, rows: list[Row]) -> None:
    print(f"## {title}")
    print("| p_A | p_B | N | PASS | BLOCK | INCONCLUSIVE |")
    print("|---:|---:|---:|---:|---:|---:|")
    for row in rows:
        print(
            f"| {row['p_a']:.2f} | {row['p_b']:.2f} | {row['n']} | "
            f"{row['PASS']:.6f} | {row['BLOCK']:.6f} | {row['INCONCLUSIVE']:.6f} |"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, metavar="PATH")
    parser.add_argument(
        "--method", choices=("clopper_pearson", "newcombe"), default="clopper_pearson"
    )
    parser.add_argument("--no-sweep", action="store_true", help="skip the boundary sweep")
    args = parser.parse_args()
    method = str(args.method)

    print(f"Interval method: {method}")
    exact_rows = [
        _row(p_a, p_b, n, operating_characteristics(p_a, p_b, n, method=method))
        for n in _SAMPLE_SIZES
        for p_a, p_b in _SCENARIOS
    ]
    correlated_rows = [
        _row(p_a, p_b, 200, correlated_boundary(p_a, p_b, 200, 0.5, seed=index))
        for index, (p_a, p_b) in enumerate(_SCENARIOS)
    ]
    _print_table("Exact independent-binomial calibration", exact_rows)
    print()
    _print_table("Correlated paired calibration (rho=0.5, reps=10000)", correlated_rows)

    boundary_rows = [row for row in exact_rows if math.isclose(row["p_a"] - row["p_b"], 0.10)]
    equal_rows = [row for row in exact_rows if row["p_a"] == row["p_b"]]
    false_pass_ok = all(row["PASS"] <= 0.05 + 1e-12 for row in boundary_rows)
    false_block_ok = all(row["BLOCK"] <= 0.05 + 1e-12 for row in equal_rows)
    calibration = {
        "false_PASS_at_boundary_le_alpha": false_pass_ok,
        "false_BLOCK_when_equal_le_alpha": false_block_ok,
    }
    print()
    print(f"Calibration false-PASS at boundary <= alpha: {'PASS' if false_pass_ok else 'FAIL'}")
    print(f"Calibration false-BLOCK when equal <= alpha: {'PASS' if false_block_ok else 'FAIL'}")

    sweep: dict[str, dict[str, float]] = {}
    if not args.no_sweep:
        print()
        print("Boundary sweep (p_a 0.50..0.99 step 0.01, offsets +/-0.001 and +/-0.01):")
        for n in _SAMPLE_SIZES:
            worst = boundary_calibration(method, n)
            sweep[str(n)] = worst
            ok = worst["false_pass"] <= 0.05 + 1e-12 and worst["false_block"] <= 0.05 + 1e-12
            calibration[f"sweep_n{n}_le_alpha"] = ok
            print(
                f"  N={n:>4}: max false-PASS {worst['false_pass']:.4f} at "
                f"({worst['false_pass_at_p_a']:.3f}, {worst['false_pass_at_p_b']:.3f}); "
                f"max false-BLOCK {worst['false_block']:.4f} at "
                f"({worst['false_block_at_p_a']:.3f}, {worst['false_block_at_p_b']:.3f}) "
                f"{'PASS' if ok else 'FAIL'}"
            )

    if args.json is not None:
        args.json.write_text(
            json.dumps(
                {
                    "method": method,
                    "exact": exact_rows,
                    "correlated": correlated_rows,
                    "sweep": sweep,
                    "calibration": calibration,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
    return 0 if all(calibration.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
