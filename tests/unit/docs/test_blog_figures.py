"""Every figure in docs/blog/2026-11-eval-noise.md, recomputed exactly.

The post compares one agent with itself (independent tasks, the same pass rate in both runs)
and quotes the suite rule's operating characteristics at the defaults.
"""

from __future__ import annotations

from fractions import Fraction
from math import comb
from pathlib import Path

import pytest

from arci.suite_stats import (
    SuiteRule,
    default_max_errored_pairs,
    operating_characteristics,
)

POST = Path(__file__).resolve().parents[3] / "docs" / "blog" / "2026-11-eval-noise.md"
ALPHA, MARGIN, STAKES = Fraction(1, 20), Fraction(1, 10), (Fraction(1, 4), Fraction(1, 2))


def _worse_by(tasks: int, rate: Fraction, points: int) -> Fraction:
    """P(second run passes at least `points` percentage points fewer tasks than the first)."""
    law = [comb(tasks, k) * rate**k * (1 - rate) ** (tasks - k) for k in range(tasks + 1)]
    needed = -(-points * tasks // 100)
    tail = [Fraction(0)] * (tasks + 2)  # tail[b] = P(first run passes at least b tasks)
    for b in range(tasks, -1, -1):
        tail[b] = tail[b + 1] + law[b]
    return sum((law[c] * tail[min(c + needed, tasks + 1)] for c in range(tasks + 1)), Fraction(0))


def _gate(tasks: int, rounds: int, baseline: Fraction, candidate: Fraction) -> tuple[float, float]:
    rule = SuiteRule(ALPHA, MARGIN, STAKES, tasks, rounds, default_max_errored_pairs(tasks, rounds))
    minus, plus = baseline * (1 - candidate), (1 - baseline) * candidate
    result = operating_characteristics([(minus, 1 - minus - plus, plus)] * tasks, rule)
    return float(result.p_pass), float(result.p_block)


def _percent(value: float, digits: int) -> str:
    return f"{100 * value:.{digits}f}%"


@pytest.mark.parametrize(
    ("tasks", "points", "quoted"),
    [(50, 4, "35.3%"), (50, 6, "26.5%"), (50, 10, "13.0%"), (200, 6, "7.5%")],
)
def test_self_comparison_figures(tasks: int, points: int, quoted: str) -> None:
    assert _percent(float(_worse_by(tasks, Fraction(8, 10), points)), 1) == quoted
    assert quoted in POST.read_text(encoding="utf-8")


def test_gate_figures() -> None:
    text = POST.read_text(encoding="utf-8")
    same = Fraction(8, 10)
    one_pass, one_block = _gate(50, 1, same, same)
    eight_pass, eight_block = _gate(50, 8, same, same)
    quoted = (
        _percent(one_pass, 1),
        _percent(eight_pass, 1),
        _percent(one_block, 4),
        _percent(eight_block, 4),
        _percent(_gate(50, 1, same, Fraction(6, 10))[1], 1),
        _percent(_gate(50, 8, same, Fraction(6, 10))[1], 1),
    )
    assert quoted == ("4.0%", "75.9%", "0.0004%", "0.0006%", "2.4%", "63.3%")
    assert all(figure in text for figure in quoted)


def test_study_figures() -> None:
    text = POST.read_text(encoding="utf-8")
    assert f"{100 * (96 - 85) / 96:.1f} points" == "11.5 points"
    assert "85 of 96 against 96 of 96" in text and "11.5 points" in text
    assert f"{100 * (480 - 428) / 480:.1f} points" == "10.8 points" and "10.8 points" in text
