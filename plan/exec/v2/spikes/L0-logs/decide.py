"""Predeclared three-measure decision; all comparisons use exact arithmetic."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from fractions import Fraction
from typing import Literal

from daytable import Day
from rank_test import Exact, p_lower
from records import Tool

Verdict = Literal["REAL DROP", "NO DROP", "CANNOT TELL"]
Measure = Literal["m1", "m2", "m3", "m4"]
Direction = Literal["lower", "higher"]
Point = tuple[date, Exact]
ALPHA = Fraction(1, 40)
K = 3
SPECS: dict[Measure, tuple[Direction, Fraction]] = {
    "m1": ("lower", Fraction(1, 4)),
    "m2": ("higher", Fraction(1, 10)),
    "m3": ("higher", Fraction(3, 100)),
    "m4": ("higher", Fraction(1, 10)),
}


@dataclass(frozen=True)
class MeasureResult:
    verdict: Verdict
    before_days: int
    after_days: int
    p_drop: Fraction | None
    p_no_drop: Fraction | None
    p_self: Fraction | None


@dataclass(frozen=True)
class Result:
    verdict: Verdict
    reason: str
    measures: dict[Measure, MeasureResult]
    self_check_fired: bool


def drop_p(before: list[Exact], after: list[Exact], direction: Direction) -> Fraction:
    return p_lower(before, after) if direction == "lower" else p_lower(after, before)


def measure_decision(
    before: list[Point],
    after: list[Point],
    direction: Direction,
    margin: Fraction,
) -> MeasureResult:
    if direction not in ("lower", "higher") or type(margin) is not Fraction:
        raise ValueError("invalid_values")
    if len({d for d, _ in before + after}) != len(before) + len(after):
        raise ValueError("invalid_values")
    b = [v for _, v in sorted(before)]
    a = [v for _, v in sorted(after)]
    # Same minimum sizes for the historical pseudo-comparison; never relax them.
    half = len(b) // 2
    self_p = drop_p(b[:half], b[half:], direction) if half >= 10 and len(b) - half >= 5 else None
    if len(b) < 10 or len(a) < 5:
        return MeasureResult("CANNOT TELL", len(b), len(a), None, None, self_p)
    real = drop_p(b, a, direction)
    moved = [v * (1 - margin) for v in b] if direction == "lower" else [v + margin for v in b]
    noninferior = p_lower(a, moved) if direction == "lower" else p_lower(moved, a)
    verdict: Verdict = "CANNOT TELL"
    if real <= ALPHA / K:
        verdict = "REAL DROP"
    elif noninferior <= ALPHA:
        verdict = "NO DROP"
    return MeasureResult(verdict, len(b), len(a), real, noninferior, self_p)


def decide(
    before: dict[Measure, list[Point]],
    after: dict[Measure, list[Point]],
    tool: Tool,
) -> Result:
    names: tuple[Measure, ...] = ("m1", "m2", "m3") if tool == "claude" else ("m1", "m2", "m4")
    measures: dict[Measure, MeasureResult] = {
        name: measure_decision(before.get(name, []), after.get(name, []), *SPECS[name])
        for name in names
    }
    self_fired = any(r.p_self is not None and r.p_self <= ALPHA / K for r in measures.values())
    if any(r.verdict == "REAL DROP" for r in measures.values()):
        return Result(
            "CANNOT TELL" if self_fired else "REAL DROP",
            "self_check" if self_fired else "detected",
            measures,
            self_fired,
        )
    if all(r.verdict == "NO DROP" for r in measures.values()):
        return Result("NO DROP", "within_margin", measures, self_fired)
    reason = "too_few_days" if any(r.p_drop is None for r in measures.values()) else "uncertain"
    return Result("CANNOT TELL", reason, measures, self_fired)


def decide_days(days: list[Day], cutoff: date, tool: Tool) -> Result:
    before: dict[Measure, list[Point]] = {name: [] for name in SPECS}
    after: dict[Measure, list[Point]] = {name: [] for name in SPECS}
    for day in days:
        target = after if day.date > cutoff else before
        for name in SPECS:
            value = getattr(day, name)
            if isinstance(value, Fraction):
                target[name].append((day.date, value))
    return decide(before, after, tool)
