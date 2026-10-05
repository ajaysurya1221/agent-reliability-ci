"""Plan a fixed-sample gate run before paying for it: exact verdict probabilities per N.

This is planning under assumptions, not observed power. Given true success rates for the baseline
and the candidate, `plan` enumerates, for every tested N per arm, each pair of success counts
(x_baseline, x_candidate) of two independent binomial arms and classifies the pair with the gate's
own functions: the two-sided Clopper-Pearson interval per arm at tail alpha / (4K)
(`arci.stats.clopper_pearson_tail`), the bounds on the difference
(`arci.stats.difference_bounds`) and the strict margin test (`arci.gate.classify`). Summing the
pair probabilities per verdict gives P(PASS), P(BLOCK) and P(INCONCLUSIVE); they sum to one.

Certainty is decided from the support, not from the floats. A count pair is reachable when both
counts are possible under their arm's rate: every count when the rate is strictly between 0 and 1,
only 0 at rate 0 and only N at rate 1. A verdict that no reachable pair produces has probability
exactly 0; a verdict that every reachable pair produces (the certain verdict) has probability
exactly 1. Any other probability is the summed float clamped into [0, 1], after checking that the
unclamped sums meet one within 1e-12. A target probability of 1 is met only by the certain verdict,
so float rounding can neither create nor hide certainty.

Domain: `interval_method` clopper_pearson, exactly one gating condition (K=1), one look (fixed
sample), 1 <= N <= 400 per arm. Anything else raises `UnsupportedDesignError`; the planner never
extrapolates. It also assumes no trial ERROR and no candidate hard-invariant violation, each of
which overrides the rates in the real gate.

JSON output of `plan_to_json` (schema "arci.plan.v1"; these keys are stable):

- `schema`: "arci.plan.v1".
- `design`: `baseline_rate`, `candidate_rate`, `alpha`, `delta`, `interval_method`
  ("clopper_pearson"), `conditions` (K, always 1), `looks` (always 1), `per_arm_tail`
  (alpha / (4K), the tail each arm's interval uses).
- `target`: `verdict` ("PASS", "BLOCK" or "INCONCLUSIVE"), `probability`.
- `rows`: one object per tested N, in grid order: `n_per_arm`, `total_trials` (both arms),
  `PASS`, `BLOCK`, `INCONCLUSIVE` (probabilities), `certain_verdict` (the verdict every reachable
  count pair produces, whose probability is then exactly 1, or null), `meets_target`
  (P(target verdict) >= target probability; for a target probability of 1, the target verdict is
  the certain verdict).
- `target_reached`: whether any tested N meets the target.
- `smallest_n_per_arm`: the smallest tested N meeting the target, or null.
- `conclusion`: one sentence stating that N, or that the target was not reached.
- `assumptions`: the assumptions above, one sentence each.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from itertools import pairwise
from typing import Final

from arci.gate import classify
from arci.schema import Verdict
from arci.stats import clopper_pearson_tail, difference_bounds

SCHEMA: Final = "arci.plan.v1"
INTERVAL_METHOD: Final = "clopper_pearson"
MAX_N_PER_ARM: Final = 400
DEFAULT_N_GRID: Final = (20, 50, 100, 200, 400)
OUTCOMES: Final = (Verdict.PASS, Verdict.BLOCK, Verdict.INCONCLUSIVE)
CONDITIONS: Final = 1
LOOKS: Final = 1
# The manifest's supported alpha range; with K=1 and one look the per-arm tail alpha/4 then stays
# at or above the 2.5e-7 floor that `clopper_pearson_tail` accepts.
_ALPHA_MIN: Final = 1e-6
_ALPHA_MAX: Final = 0.5
_MASS_TOLERANCE: Final = 1e-12

ASSUMPTIONS: Final = (
    "This is planning under assumptions, not observed power: the true success rates are inputs, "
    "not measurements.",
    "Independent binomial arms: each arm is N independent trials at its stated true rate.",
    "No pairing: shared seeds or any other dependence between the arms is not modelled.",
    "Fixed sample: one look at N per arm, no early stopping and no extension.",
    "One gating condition (K=1), no trial ERROR and no candidate hard-invariant violation; "
    "either of those overrides the rates in the real gate.",
    "The gate's exact rule: two-sided Clopper-Pearson per arm with tail alpha/(4K), bounds "
    "[L_B - U_A, U_B - L_A] on the difference, PASS iff L > -delta, BLOCK iff U < -delta, "
    "otherwise INCONCLUSIVE.",
    "Probabilities enumerate every pair of success counts; they are not simulated. They need not "
    "rise monotonically with N, so only the tested N values are claimed.",
)


class UnsupportedDesignError(ValueError):
    """A design outside the planner's domain. The planner refuses rather than extrapolates."""


@dataclass(frozen=True, slots=True)
class PlanRow:
    """Verdict probabilities at one tested N per arm."""

    n_per_arm: int
    pass_probability: float
    block_probability: float
    inconclusive_probability: float
    certain_verdict: Verdict | None
    meets_target: bool

    @property
    def total_trials(self) -> int:
        """Trials across both arms of the single gating condition."""
        return 2 * self.n_per_arm * CONDITIONS

    def probability(self, verdict: Verdict) -> float:
        """Return the probability of one condition verdict."""
        return {
            Verdict.PASS: self.pass_probability,
            Verdict.BLOCK: self.block_probability,
            Verdict.INCONCLUSIVE: self.inconclusive_probability,
        }[verdict]


@dataclass(frozen=True, slots=True)
class Plan:
    """A sample-size plan over a grid of N per arm for one fixed-sample design."""

    baseline_rate: float
    candidate_rate: float
    alpha: float
    delta: float
    target_verdict: Verdict
    target_probability: float
    rows: tuple[PlanRow, ...]

    @property
    def smallest_n_per_arm(self) -> int | None:
        """The smallest tested N per arm that meets the target, or None."""
        return min((row.n_per_arm for row in self.rows if row.meets_target), default=None)

    @property
    def conclusion(self) -> str:
        """One sentence: the smallest tested N meeting the target, or that none did."""
        target = f"P({self.target_verdict.value}) >= {self.target_probability:g}"
        smallest = self.smallest_n_per_arm
        if smallest is None:
            largest = max(row.n_per_arm for row in self.rows)
            return (
                f"target not reached: no tested N per arm gives {target} (largest tested "
                f"{largest}); the planner does not extrapolate beyond the tested grid."
            )
        return (
            f"smallest tested N per arm meeting {target}: {smallest} "
            f"({2 * smallest * CONDITIONS} trials in total)."
        )


def per_arm_tail(alpha: float) -> float:
    """The gate's per-arm Clopper-Pearson tail for one gating condition and one look."""
    # The same expression as `arci.gate._decide`: alpha / (4.0 * K * L), here with K = L = 1.
    return alpha / (4.0 * CONDITIONS * LOOKS)


def binomial_pmf(p: float, n: int) -> tuple[float, ...]:
    """Binomial(n, p) probabilities of 0..n successes, normalised to sum to one.

    The same computation as `bench/selfcheck.py`, which the package must not import.
    """
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


def _support(rate: float, n: int) -> range:
    """The success counts with nonzero probability under Binomial(n, rate), decided exactly."""
    if rate == 0.0:
        return range(1)
    if rate == 1.0:
        return range(n, n + 1)
    return range(n + 1)


@lru_cache(maxsize=32)
def _intervals(n: int, tail: float) -> tuple[tuple[float, float], ...]:
    return tuple(clopper_pearson_tail(successes, n, tail) for successes in range(n + 1))


@lru_cache(maxsize=32)
def _verdict_table(n: int, alpha: float, delta: float) -> tuple[tuple[Verdict, ...], ...]:
    intervals = _intervals(n, per_arm_tail(alpha))
    return tuple(
        tuple(
            classify(*difference_bounds(baseline=baseline, candidate=candidate), delta)
            for candidate in intervals
        )
        for baseline in intervals
    )


def _check_design(
    *,
    alpha: float,
    delta: float,
    n_grid: Sequence[int],
    interval_method: str,
    conditions: int,
    looks: Sequence[int],
) -> None:
    if interval_method != INTERVAL_METHOD:
        raise UnsupportedDesignError(
            f"unsupported design: interval_method {interval_method!r}; the planner covers only "
            f"the default {INTERVAL_METHOD} rule"
        )
    if conditions < 1:
        raise ValueError("conditions (K) must be at least 1")
    if conditions != CONDITIONS:
        raise UnsupportedDesignError(
            f"unsupported design: K={conditions} gating conditions; the planner covers exactly "
            "one (K=1)"
        )
    if looks:
        raise UnsupportedDesignError(
            "unsupported design: sequential looks; the planner covers one fixed-sample look at N "
            "(bench/selfcheck.py --looks enumerates sequential plans)"
        )
    if not n_grid:
        raise ValueError("the N grid must not be empty")
    for n in n_grid:
        # A bool is an int to Python but not a sample size; reject it like any other non-int.
        if type(n) is not int or n < 1:
            raise ValueError(f"N per arm must be a positive integer, got {n!r}")
        if n > MAX_N_PER_ARM:
            raise UnsupportedDesignError(
                f"unsupported design: N={n} per arm; the planner covers 1 <= N <= {MAX_N_PER_ARM}"
            )
    if any(right <= left for left, right in pairwise(n_grid)):
        raise ValueError("the N grid must be strictly increasing")
    if not (math.isfinite(alpha) and _ALPHA_MIN <= alpha <= _ALPHA_MAX):
        raise ValueError(f"alpha must be between {_ALPHA_MIN:g} and {_ALPHA_MAX:g}")
    if not (math.isfinite(delta) and 0.0 < delta < 1.0):
        raise ValueError("delta must be strictly between 0 and 1")


def _check_rate(value: float, name: str) -> None:
    if not (math.isfinite(value) and 0.0 <= value <= 1.0):
        raise ValueError(f"{name} must be between 0 and 1")


def verdict_table(
    n: int, *, alpha: float = 0.05, delta: float = 0.10
) -> tuple[tuple[Verdict, ...], ...]:
    """The gate's condition verdict for every count pair, as table[x_baseline][x_candidate]."""
    _check_design(
        alpha=alpha,
        delta=delta,
        n_grid=(n,),
        interval_method=INTERVAL_METHOD,
        conditions=CONDITIONS,
        looks=(),
    )
    return _verdict_table(n, alpha, delta)


def _enumerate(
    baseline_rate: float, candidate_rate: float, n: int, *, alpha: float, delta: float
) -> tuple[dict[Verdict, float], frozenset[Verdict]]:
    _check_rate(baseline_rate, "baseline rate")
    _check_rate(candidate_rate, "candidate rate")
    table = verdict_table(n, alpha=alpha, delta=delta)
    baseline_pmf = binomial_pmf(baseline_rate, n)
    candidate_pmf = binomial_pmf(candidate_rate, n)
    masses: dict[Verdict, list[float]] = {verdict: [] for verdict in OUTCOMES}
    for baseline_probability, row in zip(baseline_pmf, table, strict=True):
        for candidate_probability, verdict in zip(candidate_pmf, row, strict=True):
            masses[verdict].append(baseline_probability * candidate_probability)
    sums = {verdict: math.fsum(masses[verdict]) for verdict in OUTCOMES}
    if abs(math.fsum(sums.values()) - 1.0) > _MASS_TOLERANCE:
        raise ArithmeticError("enumerated verdict probabilities do not sum to one")
    # Decided from the support, not from the floats: a reachable pair whose float mass underflows
    # to zero still counts, and the summed floats may miss 1 by a rounding error.
    reachable = frozenset(
        table[baseline][candidate]
        for baseline in _support(baseline_rate, n)
        for candidate in _support(candidate_rate, n)
    )

    def probability(verdict: Verdict) -> float:
        if verdict not in reachable:
            return 0.0
        if len(reachable) == 1:
            return 1.0
        return min(1.0, max(0.0, sums[verdict]))

    return {verdict: probability(verdict) for verdict in OUTCOMES}, reachable


def verdict_probabilities(
    baseline_rate: float,
    candidate_rate: float,
    n: int,
    *,
    alpha: float = 0.05,
    delta: float = 0.10,
) -> dict[Verdict, float]:
    """Exactly enumerate P(PASS), P(BLOCK) and P(INCONCLUSIVE) at N per arm.

    Each probability lies in [0, 1]: exactly 0 for a verdict no reachable count pair produces and
    exactly 1 for the certain verdict (see the module docstring).
    """
    return _enumerate(baseline_rate, candidate_rate, n, alpha=alpha, delta=delta)[0]


def reachable_verdicts(
    baseline_rate: float,
    candidate_rate: float,
    n: int,
    *,
    alpha: float = 0.05,
    delta: float = 0.10,
) -> frozenset[Verdict]:
    """The verdicts some count pair with nonzero probability produces at N per arm."""
    return _enumerate(baseline_rate, candidate_rate, n, alpha=alpha, delta=delta)[1]


def plan(
    *,
    baseline_rate: float,
    candidate_rate: float,
    target_verdict: Verdict,
    target_probability: float = 0.80,
    alpha: float = 0.05,
    delta: float = 0.10,
    n_grid: Sequence[int] = DEFAULT_N_GRID,
    interval_method: str = INTERVAL_METHOD,
    conditions: int = CONDITIONS,
    looks: Sequence[int] = (),
) -> Plan:
    """Verdict probabilities for each tested N, and the smallest N meeting the target.

    Raises `UnsupportedDesignError` for designs outside the domain (newcombe, K != 1, looks,
    N > 400) and `ValueError` for invalid values.
    """
    grid = tuple(n_grid)
    _check_design(
        alpha=alpha,
        delta=delta,
        n_grid=grid,
        interval_method=interval_method,
        conditions=conditions,
        looks=tuple(looks),
    )
    _check_rate(baseline_rate, "baseline rate")
    _check_rate(candidate_rate, "candidate rate")
    if target_verdict not in OUTCOMES:
        raise ValueError("the target verdict must be PASS, BLOCK or INCONCLUSIVE")
    if not (math.isfinite(target_probability) and 0.0 < target_probability <= 1.0):
        raise ValueError("the target probability must be in (0, 1]")
    rows: list[PlanRow] = []
    for n in grid:
        probabilities, reachable = _enumerate(
            baseline_rate, candidate_rate, n, alpha=alpha, delta=delta
        )
        certain = next(iter(reachable)) if len(reachable) == 1 else None
        rows.append(
            PlanRow(
                n_per_arm=n,
                pass_probability=probabilities[Verdict.PASS],
                block_probability=probabilities[Verdict.BLOCK],
                inconclusive_probability=probabilities[Verdict.INCONCLUSIVE],
                certain_verdict=certain,
                # A target of 1 asks for certainty, which the floats cannot decide.
                meets_target=(
                    certain is target_verdict
                    if target_probability == 1.0
                    else probabilities[target_verdict] >= target_probability
                ),
            )
        )
    return Plan(
        baseline_rate=baseline_rate,
        candidate_rate=candidate_rate,
        alpha=alpha,
        delta=delta,
        target_verdict=target_verdict,
        target_probability=target_probability,
        rows=tuple(rows),
    )


def _verdict_name(verdict: Verdict | None) -> str | None:
    return None if verdict is None else verdict.value


def plan_to_json(result: Plan) -> dict[str, object]:
    """The machine-readable plan; see the module docstring for the stable keys."""
    smallest = result.smallest_n_per_arm
    return {
        "schema": SCHEMA,
        "design": {
            "baseline_rate": result.baseline_rate,
            "candidate_rate": result.candidate_rate,
            "alpha": result.alpha,
            "delta": result.delta,
            "interval_method": INTERVAL_METHOD,
            "conditions": CONDITIONS,
            "looks": LOOKS,
            "per_arm_tail": per_arm_tail(result.alpha),
        },
        "target": {
            "verdict": result.target_verdict.value,
            "probability": result.target_probability,
        },
        "rows": [
            {
                "n_per_arm": row.n_per_arm,
                "total_trials": row.total_trials,
                "PASS": row.pass_probability,
                "BLOCK": row.block_probability,
                "INCONCLUSIVE": row.inconclusive_probability,
                "certain_verdict": _verdict_name(row.certain_verdict),
                "meets_target": row.meets_target,
            }
            for row in result.rows
        ],
        "target_reached": smallest is not None,
        "smallest_n_per_arm": smallest,
        "conclusion": result.conclusion,
        "assumptions": list(ASSUMPTIONS),
    }


def _cell(row: PlanRow, verdict: Verdict) -> str:
    return "exactly 1" if row.certain_verdict is verdict else f"{row.probability(verdict):.3f}"


def _exactness_notes(result: Plan) -> list[str]:
    notes: list[str] = []
    if any(row.certain_verdict is not None for row in result.rows):
        notes.append(
            '"exactly 1" marks the only verdict any reachable pair of success counts produces.'
        )
    if any(_cell(row, verdict) == "1.000" for row in result.rows for verdict in OUTCOMES):
        notes.append("1.000 is rounded: another verdict remains possible at that N.")
    return notes


def render_plan_markdown(result: Plan) -> str:
    """A small Markdown table with the conclusion and the assumptions paragraph."""
    lines = [
        "# ARCI plan",
        "",
        (
            f"Baseline rate {result.baseline_rate:g}, candidate rate {result.candidate_rate:g}; "
            f"alpha {result.alpha:g}, delta {result.delta:g}; Clopper-Pearson, one gating "
            f"condition (K=1), one look. Target: P({result.target_verdict.value}) >= "
            f"{result.target_probability:g}."
        ),
        "",
        "| N per arm | Total trials | P(PASS) | P(BLOCK) | P(INCONCLUSIVE) | Meets target |",
        "|---:|---:|---:|---:|---:|---|",
    ]
    lines.extend(
        f"| {row.n_per_arm} | {row.total_trials} | {_cell(row, Verdict.PASS)} | "
        f"{_cell(row, Verdict.BLOCK)} | {_cell(row, Verdict.INCONCLUSIVE)} | "
        f"{'yes' if row.meets_target else 'no'} |"
        for row in result.rows
    )
    lines.extend(
        [
            "",
            f"Result: {result.conclusion}",
            "",
            " ".join(
                [
                    "Probabilities are rounded to three decimals here; `--format json` carries "
                    "full precision.",
                    *_exactness_notes(result),
                ]
            ),
            "",
            "Assumptions: " + " ".join(ASSUMPTIONS),
        ]
    )
    return "\n".join(lines) + "\n"
