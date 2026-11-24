"""Apply B1's registered criteria using summary.json as the sole data input."""

from __future__ import annotations

import argparse
import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, NamedTuple

from gates import CAP, GATES, MARGIN_GATES, OUTCOMES, RIVALS, TASKS
from pydantic import BaseModel, ConfigDict

RATES = (75, 84, 85, 86, 95, 98)
REGIMES = ("I", "P")
STREAMS = 10_000
SCHEMA = "b1.v1"


class Rate(NamedTuple):
    events: int
    rate: float
    low: float
    high: float


@lru_cache(maxsize=16384)
def rate(k: int, n: int) -> Rate:
    """Equal-tailed Clopper-Pearson, inverting binomial tails in binary64."""
    if not 0 <= k <= n or n < 1:
        raise ValueError("invalid binomial counts")

    def upper(x: int) -> float:
        if x == n:
            return 1.0
        if x == 0:
            return -math.expm1(math.log(0.025) / n)
        log_comb = math.lgamma(n + 1) - math.lgamma(x + 1) - math.lgamma(n - x + 1)
        lo, hi = x / n, 1.0
        for _ in range(54):
            p = (lo + hi) / 2
            if p in (hi, lo):
                break
            term = math.exp(log_comb + x * math.log(p) + (n - x) * math.log1p(-p))
            total = term
            odds = (1 - p) / p
            for j in range(x, 0, -1):
                # At and below x the terms decrease. Starting at the largest
                # included mass avoids underflow from summing up from zero.
                term *= (j / (n - j + 1)) * odds
                total += term
                if term <= 1e-16 * total:
                    break
            if total > 0.025:
                lo = p
            else:
                hi = p
        return (lo + hi) / 2

    return Rate(k, k / n, 1 - upper(n - k), upper(k))


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class GateSummary(Record):
    rates: dict[str, Rate]
    mean_pairs: float
    median_pairs: float
    pair_counts: dict[str, int]


class Cell(Record):
    panel: Literal["primary", "outage"]
    regime: Literal["I", "P"]
    candidate_percent: int
    streams: int
    gates: dict[str, GateSummary]
    exact_plan: dict[str, Any] | None
    crosscheck: dict[str, Any] | None


class Summary(Record):
    format: str
    run_id: str
    master_seed: Literal["ARCI-B1-20261125-v1"]
    cells: list[Cell]


def metric_counts(counts: dict[str, int], gate: str, panel: str, pc: int) -> dict[str, int]:
    metrics = {k: counts[k] for k in OUTCOMES}
    metrics["decided"] = counts["PASS"] + counts["BLOCK"]
    # Scale the true difference by 0.95 in outages. Integer comparisons
    # preserve both nulls at equality in the primary boundary cell.
    scaled = (pc - 95) * (95 if panel == "outage" else 100)
    if gate in MARGIN_GATES:
        metrics["wrong_PASS"] = counts["PASS"] if scaled <= -1000 else 0
        metrics["wrong_BLOCK"] = counts["BLOCK"] if scaled >= -1000 else 0
    if pc in (75, 95):
        metrics["correct"] = counts["BLOCK" if pc == 75 else "PASS"]
    return metrics


def histogram_median(hist: dict[str, int], n: int) -> float:
    positions = ((n - 1) // 2, n // 2)
    seen = total = 0
    for pairs, freq in sorted((int(k), v) for k, v in hist.items()):
        total += pairs * sum(seen <= i < seen + freq for i in positions)
        seen += freq
    return total / 2


def checked_primary(summary: Summary) -> dict[tuple[int, str], Cell]:
    if summary.format != SCHEMA:
        raise ValueError("unrecognized summary format")
    expected = {(p, r) for p in RATES for r in REGIMES}
    primary: dict[tuple[int, str], Cell] = {}
    for cell in summary.cells:
        if cell.panel == "outage":
            continue
        key = (cell.candidate_percent, cell.regime)
        if key in primary or key not in expected or cell.streams != STREAMS:
            raise ValueError("duplicate, unexpected or incomplete primary cell")
        if set(cell.gates) != set(GATES):
            raise ValueError("incomplete gate roster")
        for gate, stats in cell.gates.items():
            hist = stats.pair_counts
            n = cell.streams
            if sum(hist.values()) != n or any(
                int(k) not in range(TASKS, CAP + 1, TASKS) or v <= 0 for k, v in hist.items()
            ):
                raise ValueError("invalid pair histogram")
            if gate not in ("arci", "cs_zero", "cs_margin") and set(hist) != {str(CAP)}:
                raise ValueError("fixed gate has an early stop")
            if (
                sum(int(k) * v for k, v in hist.items()) / n != stats.mean_pairs
                or histogram_median(hist, n) != stats.median_pairs
            ):
                raise ValueError("inconsistent pair statistics")
            counts = {v: stats.rates[v].events for v in OUTCOMES}
            if sum(counts.values()) != n or counts["INCONCLUSIVE"] > hist.get(str(CAP), 0):
                raise ValueError("invalid verdict counts")
            metrics = metric_counts(counts, gate, cell.panel, key[0])
            if stats.rates.keys() != metrics.keys():
                raise ValueError("missing or unexpected rates")
            for name, events in metrics.items():
                supplied, expected_rate = stats.rates[name], rate(events, n)
                # libm tail inversion can differ in its last digits across platforms.
                if (
                    supplied[:2] != expected_rate[:2]
                    or abs(supplied.low - expected_rate.low) > 2e-12
                    or abs(supplied.high - expected_rate.high) > 2e-12
                ):
                    raise ValueError("inconsistent rate or Clopper-Pearson interval")
        primary[key] = cell
    if set(primary) != expected:
        raise ValueError("missing primary cells")
    return primary


def evaluate(summary: Summary) -> dict[str, Any]:
    primary = checked_primary(summary)
    failures: dict[str, list[str]] = {g: [] for g in MARGIN_GATES}
    for (pc, regime), cell in primary.items():
        for g in MARGIN_GATES:
            metrics = cell.gates[g].rates
            for applies, name in ((pc <= 85, "wrong_PASS"), (pc >= 85, "wrong_BLOCK")):
                if applies and metrics[name].low > 0.025:
                    failures[g].append(f"{regime}/{pc}/{name}")

    clear = [primary[p, r] for p in (75, 95) for r in REGIMES]
    eligible = [g for g in RIVALS if not failures[g]]
    c2 = all(c.gates["arci"].rates["correct"].events >= 4 * STREAMS // 5 for c in clear)
    matches = [
        g
        for g in eligible
        if all(
            c.gates[g].rates["correct"].events >= c.gates["arci"].rates["correct"].events
            for c in clear
        )
    ]
    comparisons: list[dict[str, Any]] = []
    c3 = bool(eligible)
    for cell in clear:
        a = cell.gates["arci"]
        for g in RIVALS:
            b = cell.gates[g]
            cost = a.mean_pairs - 0.8 * b.mean_pairs
            # Paired stream variable A - 0.8*B. All 3 rivals x 4 clear cells
            # are covered simultaneously, including selection after calibration.
            spread = (CAP - TASKS) * (1.8 if g == "cs_margin" else 1.0)
            radius = spread * math.sqrt(math.log(2 * 12 / 0.05) / (2 * cell.streams))
            gap = a.rates["correct"].events - b.rates["correct"].events
            supported = cost + radius <= 0 and 20 * gap >= -cell.streams
            if g in eligible:
                c3 = c3 and supported
            comparisons.append(
                {
                    "cell": [cell.regime, cell.candidate_percent],
                    "rival": g,
                    "calibrated": g in eligible,
                    "mean_contrast_pairs": cost,
                    "simultaneous_95": [cost - radius, cost + radius],
                    "correct_rate_difference": gap / cell.streams,
                    "meets_contrast": supported,
                }
            )
    stop = bool(matches) and not c3
    return {
        "C1": not failures["arci"],
        "C1_failures": failures,
        "C2": c2,
        "C3": c3,
        "calibrated_rivals": eligible,
        "comparisons": comparisons,
        "efficiency_claim": "supported" if c3 else "dropped",
        "matches_or_beats_correctness": matches,
        "stop": stop,
        "conclusion": (
            'The benchmark gives no support for continuing the "release decision" direction.'
            if stop
            else "The registered stop rule did not trigger."
        ),
    }


def read_evaluation(path: Path) -> dict[str, Any]:
    return evaluate(Summary.model_validate_json(path.read_bytes()))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("summary", type=Path)
    print(json.dumps(read_evaluation(parser.parse_args().summary), indent=2, sort_keys=True))
