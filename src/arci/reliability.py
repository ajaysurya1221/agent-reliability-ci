"""Descriptive pass^k: how often k trials would all pass, estimated per arm and per condition.

Opt-in (`arci report RUN --pass-k 1,2,4`) and descriptive only. It never changes a verdict, a seal
or `decision.json`.

For one arm in one declared condition with n trials and s of them PASS, the all-success estimate
is C(s, k) / C(n, k): the share of k-trial subsets in which every trial passed. If the n trials are
an IID sample at one fixed success rate p, it is an unbiased estimate of p^k, the chance that k
fresh independent trials all pass.

It is unavailable when n < k, when the experiment is invalid (verdict ERROR), and when the manifest
declares sequential looks, because the stopping look depends on the outcomes and so does n.
Populations are never pooled across conditions.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise
from typing import Literal

from arci.schema import ArmStats, GateDecision, Verdict

IID_ASSUMPTION = (
    "If an arm's n trials in one condition are an IID sample at one fixed success rate p, this "
    "is an unbiased estimate of p^k, the chance that k fresh independent trials all pass. Drift "
    "over the run, or trials that differ systematically (a mix of tasks or scenarios), break that "
    "assumption."
)
UNAVAILABLE_INVALID = (
    "the experiment is invalid (verdict ERROR), so no population is a valid sample"
)
UNAVAILABLE_LOOKS = (
    "the manifest declares sequential looks, so n depends on the outcomes (outcome-selected "
    "stopping) and the sample is not a fixed-N sample"
)
UNAVAILABLE_SMALL_N = "n < k"


@dataclass(frozen=True, slots=True)
class PassKRow:
    """One arm of one declared condition: its counts and the estimate for each k."""

    condition_id: str
    arm: Literal["baseline", "candidate"]
    is_gating: bool
    n: int
    successes: int
    estimates: tuple[float | None, ...]  # aligned with PassKReport.ks; None when n < k


@dataclass(frozen=True, slots=True)
class PassKReport:
    """Per-population pass^k estimates, or one reason why none is available."""

    ks: tuple[int, ...]
    unavailable: str | None
    rows: tuple[PassKRow, ...]


def all_success_estimate(successes: int, n: int, k: int) -> float | None:
    """C(successes, k) / C(n, k), correctly rounded; None when n < k."""
    if k < 1:
        raise ValueError("k must be at least 1")
    if n < 0 or not 0 <= successes <= n:
        raise ValueError("successes must be between 0 and n")
    if n < k:
        return None
    # Python's int / int is correctly rounded, so the exact ratio becomes the nearest float.
    return math.comb(successes, k) / math.comb(n, k)


def validate_ks(ks: Sequence[int]) -> tuple[int, ...]:
    """Return the k values as a tuple; they must be positive and strictly increasing."""
    values = tuple(ks)
    if not values:
        raise ValueError("--pass-k needs at least one k")
    if any(type(k) is not int or k < 1 for k in values):
        raise ValueError("every k in --pass-k must be a positive integer")
    if any(right <= left for left, right in pairwise(values)):
        raise ValueError("--pass-k values must be strictly increasing")
    return values


def pass_k_report(decision: GateDecision, ks: Sequence[int]) -> PassKReport:
    """Estimate pass^k for each arm of each declared condition of a decided experiment."""
    values = validate_ks(ks)
    if decision.verdict is Verdict.ERROR:
        return PassKReport(ks=values, unavailable=UNAVAILABLE_INVALID, rows=())
    if len(decision.looks) > 1:
        return PassKReport(ks=values, unavailable=UNAVAILABLE_LOOKS, rows=())
    rows: list[PassKRow] = []
    for condition in decision.conditions:
        arms: tuple[tuple[Literal["baseline", "candidate"], ArmStats], ...] = (
            ("baseline", condition.baseline),
            ("candidate", condition.candidate),
        )
        for arm, stats in arms:
            rows.append(
                PassKRow(
                    condition_id=condition.condition_id,
                    arm=arm,
                    is_gating=condition.is_gating,
                    n=stats.n,
                    successes=stats.successes,
                    estimates=tuple(
                        all_success_estimate(stats.successes, stats.n, k) for k in values
                    ),
                )
            )
    return PassKReport(ks=values, unavailable=None, rows=tuple(rows))
