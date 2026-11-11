"""Offline S1 calibration. All output and subprocess caches stay beside this file.

Full run uses up to 15 worker processes. --quick is a smoke check, not full evidence.
The DP supports exact rational probabilities and certified dyadic enclosures: in
the latter each discarded/rounded unit is charged to an explicit lost-mass ledger.
No floating-point approximation can turn a failed error-control check into a pass.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import multiprocessing
import os
import random
import subprocess
import time
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import TypedDict, cast

from suite_stats import RULES, Plan, Verdict, decide

F = Fraction
BINOMIAL_TAIL = F(1, 100)
ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[4]
OUTCOMES: tuple[Verdict, ...] = ("PASS", "BLOCK", "INCONCLUSIVE", "ERROR")
CAPS = (50, 100, 200, 400, 1000)
SCENARIOS = ((95, 95), (95, 75), (95, 65), (80, 80), (95, 85))
Boundary = tuple[tuple[int, int], ...]  # indexed by minus count: min PASS +, max BLOCK +
Probabilities = tuple[Fraction, Fraction, Fraction]


class Summary(TypedDict):
    PASS: float
    BLOCK: float
    INCONCLUSIVE: float
    ERROR: float
    mean: float
    median: int
    p90: int


class Enclosure(TypedDict):
    n: int
    lower: dict[str, str]
    upper: dict[str, str]
    lost: str
    summary: Summary


@dataclass(frozen=True)
class IntegerWealth:
    """Common-denominator products: compare sum of component numerators exactly."""

    powers: tuple[tuple[tuple[int, ...], ...], ...]
    threshold: int
    alpha_numerator: int

    def crossed(self, n: int, m: int, p: int) -> bool:
        z = n - m - p
        numerator = sum(row[0][m] * row[1][z] * row[2][p] for row in self.powers)
        return numerator * self.alpha_numerator >= self.threshold


def integer_wealth(plan: Plan, n: int, sign: int) -> IntegerWealth:
    factors = [
        tuple(1 + sign * q * (d + plan.delta) / (1 - sign * plan.delta) for d in (-1, 0, 1))
        for q in plan.rule.fractions
    ]
    denominator = math.lcm(*(f.denominator for row in factors for f in row))
    powers: list[tuple[tuple[int, ...], ...]] = []
    for row in factors:
        arrays: list[tuple[int, ...]] = []
        for f in row:
            base = int(f * denominator)
            values = [1]
            for _ in range(n):
                values.append(values[-1] * base)
            arrays.append(tuple(values))
        powers.append(tuple(arrays))
    return IntegerWealth(
        tuple(powers),
        2 * plan.alpha.denominator * len(factors) * denominator**n,
        plan.alpha.numerator,
    )


def make_boundary(job: tuple[Plan, int]) -> tuple[int, Boundary]:
    """Monotone frontiers, certified entirely with integer products/comparisons."""
    plan, n = job
    if plan.rule.name == "adaptive":
        raise ValueError("counts do not suffice for adaptive stakes")
    plus, minus = integer_wealth(plan, n, 1), integer_wealth(plan, n, -1)
    rows: list[tuple[int, int]] = []
    pass_min, block_max = 0, -1
    for m in range(n + 1):
        limit = n - m
        while pass_min <= limit and not plus.crossed(n, m, pass_min):
            pass_min += 1
        pass_at = min(pass_min, limit + 1)
        block_max = min(block_max, limit)
        while block_max < limit and minus.crossed(n, m, block_max + 1):
            block_max += 1
        rows.append((pass_at, block_max))
    return n, tuple(rows)


def boundary_verdict(boundary: Boundary, m: int, p: int) -> Verdict:
    a, b = boundary[m]
    if p >= a and p <= b:
        return "ERROR"
    return "PASS" if p >= a else "BLOCK" if p <= b else "INCONCLUSIVE"


def validate_probabilities(probabilities: Probabilities) -> None:
    if any(type(p) is not Fraction or p < 0 for p in probabilities) or sum(probabilities) != 1:
        raise ValueError("three nonnegative rational probabilities must sum to one")


def characteristics(
    probabilities: Probabilities,
    plan: Plan,
    boundaries: dict[int, Boundary] | None = None,
    *,
    bits: int | None = None,
    caps: tuple[int, ...] | None = None,
) -> list[Enclosure]:
    """Absorbing trinomial DP, with exact or rigorously enclosed rational masses.

    bits=None: common denominator D**n, exact mass at every state.
    bits=N: lower masses in units 2**-N. Round each incoming state's mass DOWN;
    lost = 1 - all retained/absorbed lower mass. Thus each probability lies in
    [absorbed, absorbed+lost]. Tiny states disappear only with accounted mass.
    Additional caps are hypothetical terminal looks; they do not affect longer runs.
    """
    validate_probabilities(probabilities)
    if bits is not None and bits < 1:
        raise ValueError("bits must be positive")
    cap_set = set(caps or (plan.max_pairs,))
    if not cap_set or min(cap_set) < 1 or max(cap_set) > plan.max_pairs:
        raise ValueError("caps must lie within the plan")
    denominator = math.lcm(*(p.denominator for p in probabilities))
    weights = tuple(int(p * denominator) for p in probabilities)
    scale = 1 if bits is None else 1 << bits
    states: dict[tuple[int, int], int] = {(0, 0): scale}
    absorbed: dict[str, int] = {v: 0 for v in OUTCOMES}
    stops: dict[int, int] = {}
    rows: list[Enclosure] = []
    for n in range(1, plan.max_pairs + 1):
        incoming: dict[tuple[int, int], int] = {}
        for (m, p), mass in states.items():
            if weights[0]:
                key = (m + 1, p)
                incoming[key] = incoming.get(key, 0) + mass * weights[0]
            if weights[1]:
                key = (m, p)
                incoming[key] = incoming.get(key, 0) + mass * weights[1]
            if weights[2]:
                key = (m, p + 1)
                incoming[key] = incoming.get(key, 0) + mass * weights[2]
        if bits is None:
            scale *= denominator
            absorbed = {v: mass * denominator for v, mass in absorbed.items()}
            stops = {at: mass * denominator for at, mass in stops.items()}
            states = incoming
        else:
            states = {
                key: mass // denominator for key, mass in incoming.items() if mass >= denominator
            }
        if not (plan.checkpoint(n) or n in cap_set):
            continue
        boundary = boundaries[n] if boundaries is not None else make_boundary((plan, n))[1]
        at_look: dict[str, int] = {v: 0 for v in OUTCOMES}
        survivors: dict[tuple[int, int], int] = {}
        for (m, p), mass in states.items():
            verdict = boundary_verdict(boundary, m, p)
            if verdict == "INCONCLUSIVE":
                survivors[m, p] = mass
            else:
                at_look[verdict] += mass
        if n in cap_set:
            lower = {v: absorbed[v] + at_look[v] for v in OUTCOMES}
            lower["INCONCLUSIVE"] = sum(survivors.values())
            lost = scale - sum(lower.values())
            if lost < 0:
                raise ArithmeticError("probability mass increased")
            terminal_stops = {**stops, n: sum(at_look.values()) + lower["INCONCLUSIVE"]}
            summary = summarize(
                {v: mass / scale for v, mass in lower.items()},
                terminal_stops,
                scale,
            )
            rows.append(
                Enclosure(
                    n=n,
                    lower={v: str(F(mass, scale)) for v, mass in lower.items()},
                    upper={v: str(F(mass + lost, scale)) for v, mass in lower.items()},
                    lost=str(F(lost, scale)),
                    summary=summary,
                )
            )
        if plan.checkpoint(n):
            states = survivors
            stops[n] = sum(at_look.values())
            for v in OUTCOMES:
                absorbed[v] += at_look[v]
    return rows


def summarize(masses: dict[str, float], stops: dict[int, int], scale: int) -> Summary:
    """Quantiles use integer mass, so a cumulative probability of exactly .9 is inclusive."""

    def quantile(target: Fraction) -> int:
        total = 0
        for n, mass in sorted(stops.items()):
            total += mass
            if total * target.denominator >= scale * target.numerator:
                return n
        return max(stops)

    return Summary(
        PASS=masses["PASS"],
        BLOCK=masses["BLOCK"],
        INCONCLUSIVE=masses["INCONCLUSIVE"],
        ERROR=masses["ERROR"],
        mean=sum(n * mass for n, mass in stops.items()) / scale,
        median=quantile(F(1, 2)),
        p90=quantile(F(9, 10)),
    )


def joint(a: Fraction, b: Fraction, dependence: str) -> tuple[Fraction, ...]:
    """Order: 00, 10, 01, 11. Positive/negative use Frechet-extreme couplings."""
    if dependence == "independent":
        both = a * b
    elif dependence == "positive":
        both = min(a, b)
    elif dependence == "negative":
        both = max(F(0), a + b - 1)
    else:
        raise ValueError("unknown dependence")
    if not (0 <= a <= 1 and 0 <= b <= 1):
        raise ValueError("invalid marginal probability")
    return 1 - a - b + both, a - both, b - both, both


def trinomial(a: Fraction, b: Fraction, dependence: str) -> Probabilities:
    j = joint(a, b, dependence)
    return j[1], j[0] + j[3], j[2]


@dataclass(frozen=True)
class Cell:
    a: Fraction
    b: Fraction
    dependence: str


def make_cells(tasks: int, conditions: int, difficulty: str, dependence: str) -> tuple[Cell, ...]:
    """All scenarios are exactly on the suite boundary, including concentrated loss.

    Concentrated: a loss of 1/2 on exactly one fifth of tasks, zero elsewhere.
    Mixed: alternate a=0.55/0.95; condition offsets sum to zero.
    """
    cells: list[Cell] = []
    for t in range(tasks):
        for k in range(conditions):
            offset = F(k - (conditions - 1) // 2, 50)
            if difficulty == "concentrated":
                a = F(4, 5) + offset
                b = a - (F(1, 2) if t < tasks // 5 else 0)
            else:
                a = (
                    F(3, 4) if difficulty == "equal" else F(11, 20) if t % 2 == 0 else F(19, 20)
                ) + offset
                b = a - F(1, 10)
            cells.append(Cell(a, b, dependence))
    if sum((cell.b - cell.a for cell in cells), F(0)) / len(cells) != -F(1, 10):
        raise ArithmeticError("cell mixture is not on the boundary")
    return tuple(cells)


def cell_probabilities(cells: Sequence[Cell]) -> Probabilities:
    rows = [trinomial(c.a, c.b, c.dependence) for c in cells]
    return cast(Probabilities, tuple(sum((r[j] for r in rows), F(0)) / len(rows) for j in range(3)))


def simulate_cells(
    cells: tuple[Cell, ...], plan: Plan, boundaries: dict[int, Boundary], reps: int, seed: int
) -> tuple[Summary, dict[str, int]]:
    """Draw a cell uniformly with replacement, then TWO paired Bernoulli outcomes.

    Joint categorical draws preserve the requested marginals and dependence;
    this deliberately does not sample the pre-collapsed trinomial distribution.
    """
    rng = random.Random(seed)
    cutoffs: list[tuple[float, float, float]] = []
    for cell in cells:
        row = joint(cell.a, cell.b, cell.dependence)
        cutoffs.append((float(row[0]), float(row[0] + row[1]), float(row[0] + row[1] + row[2])))
    counts = {v: 0 for v in OUTCOMES}
    stops: dict[int, int] = {}
    for _ in range(reps):
        m = p = 0
        verdict: Verdict = "INCONCLUSIVE"
        n = 0
        for n in range(1, plan.max_pairs + 1):
            c0, c1, c2 = cutoffs[rng.randrange(len(cells))]
            draw = rng.random()
            baseline = int(c0 <= draw < c1 or draw >= c2)
            candidate = int(draw >= c1)
            difference = candidate - baseline
            m += difference == -1
            p += difference == 1
            if plan.checkpoint(n):
                verdict = boundary_verdict(boundaries[n], m, p)
                if verdict != "INCONCLUSIVE":
                    break
        counts[verdict] += 1
        stops[n] = stops.get(n, 0) + 1
    return summarize(
        {v: count / reps for v, count in counts.items()},
        stops,
        reps,
    ), counts


def fast_decide(differences: Sequence[int], plan: Plan) -> tuple[Verdict, int]:
    """Simulation-only binary64 wealth path; rational adaptive stake quantization.

    Any near-threshold look is recomputed by the rational reference. A golden
    vector test is required before this path is used in a calibration run.
    """
    wp = [1.0] * len(plan.rule.fractions)
    wm = wp.copy()
    plus_stakes = [float(q / (1 - plan.delta)) for q in plan.rule.fractions]
    minus_stakes = [float(q / (1 + plan.delta)) for q in plan.rule.fractions]
    delta = float(plan.delta)
    threshold = float(2 / plan.alpha)
    m = p = 0
    for n, d in enumerate(differences[: plan.max_pairs], 1):
        if plan.rule.name == "adaptive":
            # Derive the exact quantized stake using integer counts, for ANY rational delta.
            a, b = plan.delta.numerator, plan.delta.denominator
            total = b * (p - m) + (n - 1) * a
            squares = b * b * (p + m) + 2 * a * b * (p - m) + (n - 1) * a * a
            qp = min(48, max(0, 32 * total * (b - a) // (b * b + squares)))
            qm = min(48, max(0, -32 * total * (b + a) // (b * b + squares)))
            wp[0] *= 1 + (qp * b / (64 * (b - a))) * (d + delta)
            wm[0] *= 1 - (qm * b / (64 * (b + a))) * (d + delta)
        else:
            for j in range(len(wp)):
                wp[j] *= 1 + plus_stakes[j] * (d + delta)
                wm[j] *= 1 - minus_stakes[j] * (d + delta)
        m += d == -1
        p += d == 1
        if plan.checkpoint(n):
            plus, minus = sum(wp) / len(wp), sum(wm) / len(wm)
            if min(abs(plus - threshold), abs(minus - threshold)) <= threshold * 1e-10:
                exact = decide(
                    differences,
                    alpha=plan.alpha,
                    delta=plan.delta,
                    batch=plan.batch,
                    max_pairs=plan.max_pairs,
                    rule=plan.rule,
                )
                return exact.verdict, exact.stopping_pairs
            passed, blocked = plus >= threshold, minus >= threshold
            verdict: Verdict = (
                "ERROR"
                if passed and blocked
                else "PASS"
                if passed
                else "BLOCK"
                if blocked
                else "INCONCLUSIVE"
            )
            if verdict != "INCONCLUSIVE" or n == plan.max_pairs:
                return verdict, n
    raise ValueError("incomplete simulation stream")


def simulate_rule(probabilities: Probabilities, plan: Plan, reps: int, seed: int) -> Summary:
    rng = random.Random(seed)
    a, b = float(probabilities[0]), float(probabilities[0] + probabilities[1])
    counts: dict[str, int] = {v: 0 for v in OUTCOMES}
    stops: dict[int, int] = {}
    for _ in range(reps):
        draws = [rng.random() for _ in range(plan.max_pairs)]
        differences = [-1 if draw < a else 0 if draw < b else 1 for draw in draws]
        verdict, n = fast_decide(differences, plan)
        counts[verdict] += 1
        stops[n] = stops.get(n, 0) + 1
    return summarize(
        {v: count / reps for v, count in counts.items()},
        stops,
        reps,
    )


def binomial_cdf_le(k: int, n: int, numerator: int, denominator: int, target: Fraction) -> bool:
    """Exact integer test P_p(X <= k) <= target, without special functions."""
    if numerator == 0:
        return False
    if numerator == denominator:
        return k < n
    q = denominator - numerator
    term = q**n
    total = term
    for j in range(k):
        term = term * (n - j) * numerator // ((j + 1) * q)
        total += term
    return total * target.denominator <= target.numerator * denominator**n


def binomial_upper(
    k: int, n: int, tail: Fraction = BINOMIAL_TAIL, resolution: int = 20
) -> Fraction:
    """Conservative dyadic bracket for the exact one-sided Clopper-Pearson upper.

    Returned endpoint is ABOVE the true root, at most 2**-resolution away.
    Every inversion comparison is exact; displayed decimals are not used to pass.
    """
    if not 0 <= k <= n or n < 1 or not 0 < tail < 1:
        raise ValueError("invalid binomial bound arguments")
    if k == n:
        return F(1)
    denominator = 1 << resolution
    lo, hi = 0, denominator
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if binomial_cdf_le(k, n, mid, denominator, tail):
            hi = mid
        else:
            lo = mid
    return F(hi, denominator)


def golden_check() -> int:
    """Fixed, versioned corpus: adversarial patterns plus seeded random streams."""
    rng = random.Random(77391)
    vectors = [[d] * 100 for d in (-1, 0, 1)]
    vectors += [
        [-1, 1] * 50,
        [1, -1] * 50,
        [1] * 50 + [-1] * 50,
        [-1] * 50 + [1] * 50,
        [0] * 50 + [-1] * 50,
    ]
    vectors += [[rng.choice((-1, 0, 0, 0, 1)) for _ in range(100)] for _ in range(24)]
    vectors += [[d] * 400 for d in (-1, 0, 1)]
    vectors += [[1] * 200 + [-1] * 200, [-1] * 200 + [1] * 200]
    vectors += [[rng.choice((-1,) * 3 + (0,) * 16 + (1,)) for _ in range(400)] for _ in range(2)]
    checked = 0
    for rule in RULES.values():
        for batch in (1, 10, 20):
            for vector in vectors:
                plan = Plan(batch=batch, max_pairs=len(vector), rule=rule)
                exact = decide(vector, batch=batch, max_pairs=len(vector), rule=rule)
                if fast_decide(vector, plan) != (exact.verdict, exact.stopping_pairs):
                    raise AssertionError("float/exact golden-vector disagreement")
                checked += 1
    return checked


class ARow(TypedDict):
    region: str
    p_zero: str
    probabilities: list[str]
    batch: int
    rows: list[Enclosure]


class BRow(TypedDict):
    tasks: int
    conditions: int
    difficulty: str
    dependence: str
    reps: int
    seed: int
    probabilities: list[str]
    summary: Summary
    counts: dict[str, int]
    upper99: dict[str, str]
    ok: bool


class CRow(TypedDict):
    baseline: int
    candidate: int
    dependence: str
    rule: str
    cap: int
    reps: int
    seed: int
    summary: Summary


class Agreement(TypedDict):
    probabilities: list[str]
    cap: int
    reps: int
    seed: int
    enumerated: Summary
    simulated: Summary
    upper_distance: dict[str, float]
    ok: bool


def a_worker(
    job: tuple[str, Fraction, Probabilities, int, int, dict[int, Boundary], tuple[int, ...]],
) -> ARow:
    region, p_zero, probabilities, batch, cap, boundaries, caps = job
    rows = characteristics(
        probabilities, Plan(batch=batch, max_pairs=cap), boundaries, bits=None, caps=caps
    )
    return ARow(
        region=region,
        p_zero=str(p_zero),
        probabilities=list(map(str, probabilities)),
        batch=batch,
        rows=rows,
    )


def b_worker(job: tuple[int, int, str, str, int, int, int, dict[int, Boundary]]) -> BRow:
    tasks, conditions, difficulty, dependence, reps, seed, cap, boundaries = job
    cells = make_cells(tasks, conditions, difficulty, dependence)
    summary, counts = simulate_cells(cells, Plan(max_pairs=cap), boundaries, reps, seed)
    upper = {v: binomial_upper(counts[v], reps) for v in ("PASS", "BLOCK")}
    return BRow(
        tasks=tasks,
        conditions=conditions,
        difficulty=difficulty,
        dependence=dependence,
        reps=reps,
        seed=seed,
        probabilities=list(map(str, cell_probabilities(cells))),
        summary=summary,
        counts=counts,
        upper99={v: str(p) for v, p in upper.items()},
        ok=all(p <= F(1, 20) for p in upper.values()) and counts["ERROR"] == 0,
    )


def c_worker(job: tuple[int, int, str, str, int, int, int]) -> CRow:
    a, b, dependence, rule, cap, reps, seed = job
    summary = simulate_rule(
        trinomial(F(a, 100), F(b, 100), dependence),
        Plan(max_pairs=cap, rule=RULES[rule]),
        reps,
        seed,
    )
    return CRow(
        baseline=a,
        candidate=b,
        dependence=dependence,
        rule=rule,
        cap=cap,
        reps=reps,
        seed=seed,
        summary=summary,
    )


def agreement_worker(job: tuple[int, int, int, int, dict[int, Boundary]]) -> Agreement:
    a, b, reps, seed, boundaries = job
    plan = Plan(max_pairs=100)
    probabilities = trinomial(F(a, 100), F(b, 100), "independent")
    exact = characteristics(probabilities, plan, boundaries)[0]["summary"]
    simulated, counts = simulate_cells(
        (Cell(F(a, 100), F(b, 100), "independent"),), plan, boundaries, reps, seed
    )
    # Predeclared five-sigma Bernoulli MC band + 1/reps continuity allowance.
    distances: dict[str, float] = {}
    ok = True
    for verdict in ("PASS", "BLOCK", "INCONCLUSIVE"):
        p = exact[verdict]
        band = 5 * math.sqrt(p * (1 - p) / reps) + 1 / reps
        distances[verdict] = abs(counts[verdict] / reps - p) - band
        ok &= distances[verdict] <= 0
    return Agreement(
        probabilities=list(map(str, probabilities)),
        cap=100,
        reps=reps,
        seed=seed,
        enumerated=exact,
        simulated=simulated,
        upper_distance=distances,
        ok=ok,
    )


def commands_check() -> dict[str, dict[str, object]]:
    commands = {
        "pytest": [str(REPO / ".venv/bin/pytest"), str(ROOT), "-q", "-p", "no:cacheprovider"],
        "ruff_format": [str(REPO / ".venv/bin/ruff"), "format", "--check", "--no-cache", str(ROOT)],
        "ruff_check": [str(REPO / ".venv/bin/ruff"), "check", "--no-cache", str(ROOT)],
        "basedpyright": [str(REPO / ".venv/bin/basedpyright"), str(ROOT)],
        "frozen": ["shasum", "-a", "256", "-c", "FROZEN.sha256"],
    }
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    results: dict[str, dict[str, object]] = {}
    for name, command in commands.items():
        process = subprocess.run(
            command, cwd=REPO, env=env, capture_output=True, text=True, check=False
        )
        results[name] = {
            "command": command,
            "exit": process.returncode,
            "last_lines": (process.stdout + process.stderr).splitlines()[-5:],
        }
    return results


def table_a(rows: list[ARow]) -> tuple[list[str], bool]:
    lines = [
        "## A. Certified error enumeration",
        "",
        "| cap | batch | boundary PASS | null BLOCK | no-change-or-above BLOCK | "
        "below-boundary PASS supremum | max lost mass |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    groups = sorted({(entry["n"], row["batch"]) for row in rows for entry in row["rows"]})
    ok = True
    for cap, batch in groups:
        candidates = [
            (row, entry)
            for row in rows
            if row["batch"] == batch
            for entry in row["rows"]
            if entry["n"] == cap
        ]
        boundary = [entry for row, entry in candidates if row["region"] == "boundary"]
        null = [entry for row, entry in candidates if row["region"] in ("boundary", "null_edge")]
        nochange = [entry for row, entry in candidates if row["region"] == "nochange"]
        bp = max(F(entry["upper"]["PASS"]) for entry in boundary)
        below = max(
            F(entry["upper"]["PASS"])
            for row, entry in candidates
            if row["region"] == "boundary" and F(row["p_zero"]) < F(9, 10)
        )
        nb = max(F(entry["upper"]["BLOCK"]) for entry in null)
        zb = max(F(entry["upper"]["BLOCK"]) for entry in nochange)
        loss = max(F(entry["lost"]) for _, entry in candidates)
        ok &= max(bp, below, nb, zb) <= F(1, 40) and loss == 0
        lines.append(
            f"| {cap} | {batch} | {float(bp):.8f} | {float(nb):.8f} | "
            f"{float(zb):.8f} | {float(below):.8f} | {float(loss):.2e} |"
        )
    lines += [
        "",
        "Entries are exact rational probabilities, displayed rounded to eight decimals;",
        "the pass check uses the rationals in results.json. No Monte Carlo in A.",
        "p_zero grid: " + ", ".join(str(z) for z in sorted({F(r["p_zero"]) for r in rows})),
        "At Delta=-.10, p_zero=.95 is infeasible (negative p_plus),",
        "so it is recorded as a null-edge point Delta=-.05, not a fabricated boundary point.",
        "For fixed p_zero, increasing Delta increases PASS and decreases BLOCK even with",
        "first-stop absorption (pathwise monotone coupling). Boundary values therefore bound",
        "all smaller means for false PASS and all larger means for false BLOCK. For p_zero<.90,",
        "the strictly-below-boundary supremum equals the boundary value by continuity. At .90,",
        "no smaller mean is feasible; that point is excluded from the below-boundary column.",
        "The no-change line bounds all Delta>=0 at each grid p_zero. Between-grid p_zero",
        "values are covered by the theorem, not an assertion of exhaustive enumeration.",
    ]
    return lines, ok


def results_markdown(
    a_rows: list[ARow],
    b_rows: list[BRow],
    c_rows: list[CRow],
    agreements: list[Agreement],
    checks: dict[str, dict[str, object]],
    quick: bool,
    elapsed: float,
    golden: int,
) -> tuple[str, dict[str, bool]]:
    a_lines, a_ok = table_a(a_rows)
    selected = [row for row in c_rows if row["rule"] == "mixture"]
    ratios: list[float] = []
    for row in selected:
        other = next(
            r
            for r in c_rows
            if r["rule"] == "adaptive"
            and all(r[k] == row[k] for k in ("baseline", "candidate", "dependence", "cap"))
        )
        ratios.append(row["summary"]["mean"] / other["summary"]["mean"])
    all_near = max(ratios) <= 1.15
    passed = {
        "1_A_exact_error_control": a_ok,
        "2_B_upper99_le_alpha": all(row["ok"] and row["reps"] >= 20_000 for row in b_rows)
        and not quick,
        "3_five_shared_points": len(agreements) >= 5 and all(row["ok"] for row in agreements),
        "4_tests_and_lint": all(
            checks[name]["exit"] == 0
            for name in ("pytest", "ruff_format", "ruff_check", "basedpyright")
        ),
        "5_frozen": checks["frozen"]["exit"] == 0,
    }
    lines = [
        "# S1 suite statistics spike",
        "",
        f"Run: {'QUICK SMOKE ONLY' if quick else 'FULL'}, {elapsed:.1f} seconds including checks.",
        "Standard library only; no network, product edits, or git-state changes.",
        "",
        "## Decision and preregistered comparison",
        "",
        "Proposed default: equal mixture q=(1/8,1/4,1/2,3/4), with lambda_plus=q/(1-delta)",
        "and lambda_minus=q/(1+delta); alpha=1/20, delta=1/10, batch=10, max_pairs=400.",
        "A final partial batch is a checkpoint. Maximum cost is 800 agent sessions per suite,",
        "not per cell. This is a budget choice, not a guarantee of a verdict or task coverage.",
        f"Mixture/adaptive capped mean-cost ratio: min {min(ratios):.3f}, max {max(ratios):.3f}.",
        f"Mixture within 15% at every comparison point: {'YES' if all_near else 'NO'}.",
        "Recommend the mixture: exact count-based calibration and simple fixed stakes.",
        f"It has lower or equal measured capped mean cost at {sum(r <= 1 for r in ratios)}"
        f"/{len(ratios)} comparison points. The 15% condition above is not concealed or relaxed.",
        "The largest disadvantage is the deterministic d=0 positive-coupling case: 70 pairs",
        "versus adaptive's 60. This simplicity/cost tradeoff does not imply universal superiority.",
        "No stake parameters were tuned in response to errors. All three rules and the grids",
        "are constants in the source. Expected pairs below are capped stopping times, including",
        "INCONCLUSIVE at the cap; they are not uncapped expected time to a decision.",
        "",
        "| pass condition | result |",
        "|---|---|",
    ]
    lines += [f"| {name} | {'GO' if ok else 'NO-GO'} |" for name, ok in passed.items()]
    if quick:
        lines += [
            "",
            "Quick mode returns nonzero: the full Table B requirement is not satisfied.",
        ]
    lines += [
        "",
        *a_lines,
        "",
        "## B. Actual cell-sampling simulations",
        "",
        "Every point has suite mean exactly -.10, so BOTH directions count as errors.",
        "Positive/negative mean the maximal feasible positive/negative Bernoulli coupling,",
        "not a universal Pearson correlation coefficient. Cells are sampled with replacement.",
        "99% bounds are one-sided Clopper-Pearson roots enclosed upward on a 2^-20 grid,",
        "using exact integer binomial-tail comparisons. They are pointwise, not simultaneous.",
        "Full B uses 20,000 replications at max_pairs=400, batch=10 at every point.",
        "",
        "| T | K | difficulty | dependence | reps | false PASS | upper99 | false BLOCK | upper99 |",
        "|---:|---:|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in b_rows:
        lines.append(
            f"| {row['tasks']} | {row['conditions']} | {row['difficulty']} | "
            f"{row['dependence']} | {row['reps']} | {row['summary']['PASS']:.5f} | "
            f"{float(F(row['upper99']['PASS'])):.6f} | {row['summary']['BLOCK']:.5f} | "
            f"{float(F(row['upper99']['BLOCK'])):.6f} |"
        )
    lines += [
        "",
        "## C. Power and cost, and stake comparison",
        "",
        "Seeded Monte Carlo; each full-run row has 20,000 replications. Maximum Bernoulli",
        "standard error is 0.00354 (roughly +/-0.00693 at 95%); means/quantiles are empirical.",
        "Seeds and exact trinomial inputs are reproducible from source/results.json.",
        "Positive uses the Frechet upper coupling (d=0 deterministically for equal arms).",
        "The fixed comparator uses q=1/2. Adaptive uses ONLY previous outcomes, rational",
        "mean/second-moment stakes damped by 1/2, clipped at 3/4 of the legal cap and rounded",
        "down to 1/64-cap increments. No superiority claim beyond these scenarios.",
        "",
        "| A -> B | dependence | rule | cap | PASS | BLOCK | INC | ERROR | "
        "mean pairs | median | p90 |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in c_rows:
        s = row["summary"]
        lines.append(
            f"| {row['baseline'] / 100:.2f}->{row['candidate'] / 100:.2f} | "
            f"{row['dependence']} | {row['rule']} | {row['cap']} | {s['PASS']:.5f} | "
            f"{s['BLOCK']:.5f} | {s['INCONCLUSIVE']:.5f} | {s['ERROR']:.5f} | "
            f"{s['mean']:.2f} | {s['median']} | {s['p90']} |"
        )
    lines += [
        "",
        "## D. Published v1 comparison, K=1",
        "",
        "v1 inputs below are the rounded published values in docs/STATISTICS.md, not reruns.",
        "Fixed v1 costs 400 sessions. Sequential v1 uses looks 50/100/200. v2 rows use the",
        "same 200-pair cap, independent arms, batch=10. Multi-task suite-mean and per-condition",
        "v1 claims differ; this homogeneous K=1 comparison does not equate their guarantees.",
        "At the margin both decisions are errors; fewer decisions there is better error control.",
        "Higher/lower labels compare measured point estimates with the published rounded numbers;",
        "they are not significance tests. Table C states Monte Carlo uncertainty.",
        "",
        "| rates | method | PASS | BLOCK | expected sessions | comparison with v2 |",
        "|---|---|---:|---:|---:|---|",
    ]
    published = (
        (95, 95, "CP fixed", 0.889, 0.000, 400.0),
        (95, 95, "Newcombe fixed", 0.989, 0.000, 400.0),
        (95, 75, "CP fixed", 0.000, 0.365, 400.0),
        (95, 75, "Newcombe fixed", 0.000, 0.838, 400.0),
        (95, 65, "CP fixed", 0.000, 0.985, 400.0),
        (95, 65, "Newcombe fixed", None, 0.9998, 400.0),
        (80, 80, "CP fixed", 0.218, 0.000, 400.0),
        (80, 80, "Newcombe fixed", 0.706, 0.000, 400.0),
        (95, 85, "CP fixed", 0.001, 0.000, 400.0),
        (95, 85, "Newcombe fixed", 0.025, 0.022, 400.0),
        (95, 95, "CP sequential", 0.735, None, 350.0),
        (95, 95, "Newcombe sequential", 0.969, None, 239.0),
        (95, 65, "CP sequential", None, 0.943, 302.0),
        (95, 65, "Newcombe sequential", None, 0.9989, 159.0),
    )
    for a, b, method, pp, pb, sessions in published:
        comparable = next(
            (
                r
                for r in selected
                if r["baseline"] == a
                and r["candidate"] == b
                and r["dependence"] == "independent"
                and r["cap"] == 200
            ),
            None,
        )
        comparison = "not in quick subset"
        if comparable is not None:
            s = comparable["summary"]
            direction = "PASS" if a == b else "BLOCK"
            old = pp if direction == "PASS" else pb
            power = s[direction]
            if a - b == 10:
                pass_label = "higher" if pp is not None and s["PASS"] > pp else "lower"
                block_label = "higher" if pb is not None and s["BLOCK"] > pb else "lower"
                comparison = f"v2 measured false-PASS {pass_label}, false-BLOCK {block_label}"
            elif old is not None:
                quality = "higher" if power > old else "lower" if power < old else "equal"
                comparison = f"v2 measured correct-decision probability {quality}"
            cost = 2 * s["mean"]
            cost_label = "lower" if cost < sessions else "higher" if cost > sessions else "equal"
            comparison += f"; v2 cost {cost:.1f} ({cost_label})"
        lines.append(
            f"| {a / 100:.2f}->{b / 100:.2f} | {method} | "
            f"{pp if pp is not None else 'not published'} | "
            f"{pb if pb is not None else 'not published'} | {sessions:g} | {comparison} |"
        )
    for row in selected:
        if row["cap"] == 200 and row["dependence"] == "independent":
            s = row["summary"]
            lines.append(
                f"| {row['baseline'] / 100:.2f}->{row['candidate'] / 100:.2f} | v2 mixture | "
                f"{s['PASS']:.5f} | {s['BLOCK']:.5f} | {2 * s['mean']:.1f} | reference |"
            )
    lines += [
        "",
        "Other v1 sequential scenarios are not published; no values were invented.",
        "The full C table shows how increasing v2's cap to 400 trades additional sessions",
        "for decisions. Strong-positive v2 cases are not compared with independent v1 numbers.",
        "",
        "## Independent implementation checks",
        "",
        f"Float/reference corpus: {golden} exact verdict/stopping-count agreements.",
        "Five shared points use unrounded rational DP mass (not the enclosure optimization),",
        "and independently generated cell simulations. Prespecified tolerance: five binomial",
        "standard errors plus 1/reps, for each of PASS/BLOCK/INCONCLUSIVE.",
        "",
        "| trinomial (-,0,+) | reps | exact PASS/BLOCK | simulated PASS/BLOCK | check |",
        "|---|---:|---|---|---|",
    ]
    for row in agreements:
        e, s = row["enumerated"], row["simulated"]
        lines.append(
            f"| {', '.join(row['probabilities'])} | {row['reps']} | "
            f"{e['PASS']:.6f}/{e['BLOCK']:.6f} | {s['PASS']:.6f}/{s['BLOCK']:.6f} | "
            f"{'GO' if row['ok'] else 'NO-GO'} |"
        )
    lines += ["", "## Verification and limits", ""]
    for name, check in checks.items():
        lines += [f"- {name}: exit {check['exit']}; last lines: `{check['last_lines']}`"]
    lines += [
        "",
        "A uses exact integer decision frontiers and exact common-denominator probability mass.",
        "Its lost-mass column is zero. Full rational numerators/denominators are in results.json.",
        "An optional faster dyadic-enclosure implementation is included and tested against exact",
        "probabilities, but is not used for Table A or the five shared exact/simulation points.",
        "No provider stationarity, future runner implementation, cross-platform CI, or suite",
        "sampling independence is established by this spike. Golden vectors ran on this host.",
        "A hard-invariant BLOCK is outside these statistical false-BLOCK rates.",
        "",
    ]
    return "\n".join(lines), passed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--workers", type=int, default=min(15, os.cpu_count() or 1))
    args = parser.parse_args()
    quick = bool(args.quick)
    workers = int(args.workers)
    if workers < 1 or workers > 15:
        parser.error("workers must be in 1..15")
    started = time.monotonic()
    golden = golden_check()
    cap = 100 if quick else 1000
    caps = (50, 100) if quick else CAPS
    checkpoints = range(1, cap + 1)
    print(f"Building integer decision frontiers through {cap}, workers={workers}", flush=True)
    with ProcessPoolExecutor(
        max_workers=workers, mp_context=multiprocessing.get_context("spawn")
    ) as pool:
        boundaries = dict(
            pool.map(make_boundary, ((Plan(max_pairs=cap), n) for n in checkpoints), chunksize=10)
        )
        print("A: enumerating certified rational probability bounds", flush=True)
        a_jobs: list[
            tuple[str, Fraction, Probabilities, int, int, dict[int, Boundary], tuple[int, ...]]
        ] = []
        for batch in (1, 10, 20):
            needed = {n: b for n, b in boundaries.items() if n % batch == 0 or n in caps}
            for z in (0, 10, 18, 19) if quick else range(20):
                pz = F(z, 20)
                mean = max(-F(1, 10), pz - 1)
                probabilities = ((1 - pz - mean) / 2, pz, (1 - pz + mean) / 2)
                region = "boundary" if mean == -F(1, 10) else "null_edge"
                a_jobs.append((region, pz, probabilities, batch, cap, needed, caps))
                a_jobs.append(
                    ("nochange", pz, ((1 - pz) / 2, pz, (1 - pz) / 2), batch, cap, needed, caps)
                )
        a_rows = list(pool.map(a_worker, a_jobs))
        print("B: sampling actual task/condition cells", flush=True)
        b_cap, reps = (100, 1000) if quick else (400, 20_000)
        b_boundaries = {n: b for n, b in boundaries.items() if n <= b_cap and n % 10 == 0}
        b_jobs = [
            (t, k, difficulty, dependence, reps, 20261110 + index, b_cap, b_boundaries)
            for index, (t, k, difficulty, dependence) in enumerate(
                (t, k, difficulty, dependence)
                for t in ((10,) if quick else (10, 20, 50, 100))
                for k in ((1,) if quick else (1, 3))
                for difficulty in ("equal", "mixed", "concentrated")
                for dependence in ("independent", "positive", "negative")
            )
        ]
        b_rows = list(pool.map(b_worker, b_jobs))
        print("C: comparing fixed, mixture, adaptive power and capped cost", flush=True)
        c_jobs = [
            (a, b, dependence, rule, n, reps, 110000 + index)
            for index, (a, b, dependence, rule, n) in enumerate(
                (a, b, dependence, rule, n)
                for a, b in SCENARIOS
                for dependence in ("independent", "positive")
                for rule in RULES
                for n in ((100,) if quick else (100, 200, 400))
            )
        ]
        c_rows = list(pool.map(c_worker, c_jobs))
        print("Cross-checking five exact rational DP / Monte Carlo points", flush=True)
        agreements = list(
            pool.map(
                agreement_worker,
                ((a, b, reps, 88100 + j, b_boundaries) for j, (a, b) in enumerate(SCENARIOS)),
            )
        )
    print("Running owned-directory tests/lint/typecheck and frozen hash verification", flush=True)
    checks = commands_check()
    elapsed = time.monotonic() - started
    markdown, passed = results_markdown(
        a_rows, b_rows, c_rows, agreements, checks, quick, elapsed, golden
    )
    source_hashes = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(ROOT.glob("*.py"))
    }
    result = {
        "mode": "quick" if quick else "full",
        "elapsed_seconds": elapsed,
        "workers": workers,
        "source_sha256": source_hashes,
        "recommended_rule": "mixture",
        "alpha": "1/20",
        "delta": "1/10",
        "batch": 10,
        "max_pairs": 400,
        "golden_vectors": golden,
        "A": a_rows,
        "B": b_rows,
        "C": c_rows,
        "agreement": agreements,
        "checks": checks,
        "pass_conditions": passed,
    }
    # Quick artifacts have distinct names so a smoke run cannot overwrite full evidence.
    suffix = "-quick" if quick else ""
    (ROOT / f"results{suffix}.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (ROOT / f"RESULTS{suffix}.md").write_text(markdown)
    print(markdown)
    print(
        f"FINAL: {'GO' if all(passed.values()) else 'NO-GO'}; elapsed={elapsed:.1f}s; "
        f"results{suffix}.json",
        flush=True,
    )
    return 0 if all(passed.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
