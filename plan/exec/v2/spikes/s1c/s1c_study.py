"""Recompute every S1c table offline; all writes remain in this directory."""

from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing
import os
import random
import re
import subprocess
import time
from concurrent.futures import ProcessPoolExecutor
from fractions import Fraction as F
from pathlib import Path
from typing import Any

from balanced import RULE, balanced_plan, decide_rounds, enumerate_balanced, enumerate_laws
from conditional import describe
from schedule import cell_index, schedule_key
from stake_selection import BASELINES, DEPENDENCES, REGRESSIONS, law
from suite_stats import Plan, classify, count_wealth, decide
from suite_stats_sim import Probabilities

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[4]
GRID = (5, 10, 20, 50, 100)
SEEDS = {n: 2026111000 + n for n in (5, 10, 20)}
SAMPLED = Plan(rule=RULE)
LawSet = tuple[Probabilities, ...]


def boundary_cases() -> list[tuple[int, str, LawSet]]:
    rows: list[tuple[int, str, LawSet]] = []
    for n in GRID:
        rows.append((n, "even", ((F(1, 10), F(9, 10), F(0)),) * n))
        for k in (1, 2, 3):
            loss = F(n, 10 * k)
            if loss <= 1:
                rows.append(
                    (
                        n,
                        f"concentrated-{k}",
                        ((loss, 1 - loss, F(0)),) * k + ((F(0), F(1), F(0)),) * (n - k),
                    )
                )
        h = n // 2
        regression = (-F(n, 10) - h * F(3, 10)) / (n - h)
        improvement = (F(7, 20), F(0), F(13, 20))
        compensator = ((1 - regression) / 2, F(0), (1 + regression) / 2)
        rows.append((n, "half-improving", (improvement,) * h + (compensator,) * (n - h)))
        # Heterogeneous two-sided laws, both signs possible in every cell.
        mean2 = (-F(n, 10) - h * F(-2, 5)) / (n - h)
        rows.append(
            (
                n,
                "mixed",
                ((F(7, 10), F(0), F(3, 10)),) * h
                + (((1 - mean2) / 2, F(0), (1 + mean2) / 2),) * (n - h),
            )
        )
    for n, _, laws in rows:
        assert sum((p[2] - p[0] for p in laws), F(0)) == -F(n, 10)
    return rows


def pack_laws(laws: LawSet) -> list[list[str]]:
    return [[str(p) for p in cell] for cell in laws]


def boundary_job(job: tuple[int, str, LawSet]) -> dict[str, Any]:
    n, name, laws = job
    result = enumerate_balanced(laws)
    assert result.probabilities["PASS"] <= F(1, 40)
    assert result.probabilities["BLOCK"] <= F(1, 40)
    return {"N": n, "law": name, "cells": pack_laws(laws), "balanced": result.record()}


def schedule_job(job: tuple[int, str, LawSet, int]) -> dict[str, Any]:
    n, name, laws, index = job
    cells = tuple({"task_id": f"task-{i:03d}", "condition_id": "clean"} for i in range(n))
    key = schedule_key(
        cells, "s1c-boundary-baseline-v1", f"s1c-boundary-candidate-{index:04d}", SAMPLED
    )
    if name == "even":
        # Identical laws make the conditional probability schedule-invariant.
        values = even_record()
    else:
        values = enumerate_laws([laws[cell_index(key, i, n)] for i in range(400)], SAMPLED).record()
    return {"N": n, "law": name, "index": index, "key": key.hex(), **values}


_even: dict[str, str] | None = None


def even_record() -> dict[str, str]:
    global _even
    if _even is None:
        _even = enumerate_laws([(F(1, 10), F(9, 10), F(0))] * 400, SAMPLED).record()
    return _even


def random_partition(rng: random.Random, n: int, total: int) -> tuple[int, ...]:
    remaining = total
    values: list[int] = []
    for left in range(n - 1, -1, -1):
        value = rng.randint(max(0, remaining - 100 * left), min(100, remaining))
        values.append(value)
        remaining -= value
    rng.shuffle(values)
    return tuple(values)


def search_candidates(n: int) -> list[tuple[int, int, str, LawSet]]:
    rng = random.Random(SEEDS[n])
    jobs: list[tuple[int, int, str, LawSet]] = []
    for family, total in (("loss-zero", 10 * n), ("loss-win", 55 * n)):
        seen: set[tuple[int, ...]] = set()
        while len(seen) < 1000:
            values = random_partition(rng, n, total)
            if values in seen:
                continue
            seen.add(values)
            laws = tuple(
                (F(v, 100), 1 - F(v, 100), F(0))
                if family == "loss-zero"
                else (F(v, 100), F(0), 1 - F(v, 100))
                for v in values
            )
            jobs.append((n, len(jobs), family, laws))
    return jobs


def search_job(job: tuple[int, int, str, LawSet]) -> dict[str, Any]:
    n, index, family, laws = job
    result = enumerate_balanced(laws)
    if max(result.probabilities["PASS"], result.probabilities["BLOCK"]) > F(1, 40):
        raise AssertionError("balanced boundary error exceeded 1/40")
    return {"N": n, "index": index, "family": family, "cells": pack_laws(laws), **result.record()}


def power_job(job: tuple[int, int, str, int]) -> dict[str, Any]:
    a, b, dep, n = job
    cell = law(a, b, dep)
    balanced = enumerate_balanced((cell,) * n).record()
    sampled = enumerate_laws([cell] * 400, SAMPLED).record()
    return {
        "a": a,
        "b": b,
        "dependence": dep,
        "N": n,
        "correct_direction": "PASS" if a == b else "BLOCK",
        "balanced": balanced,
        "sampled": sampled,
    }


def heterogeneous_job(job: tuple[str, str]) -> dict[str, Any]:
    scenario, dep = job
    baselines = [99] * 12 + [80] * 6 + [30] * 2
    candidates = [
        a
        - (
            5
            if scenario == "all-minus-005"
            else 50
            if scenario == "concentrated-minus-05" and i < 2
            else 0
        )
        for i, a in enumerate(baselines)
    ]
    laws = tuple(law(a, b, dep) for a, b in zip(baselines, candidates, strict=True))
    marginal: Probabilities = (
        sum((p[0] for p in laws), F(0)) / 20,
        sum((p[1] for p in laws), F(0)) / 20,
        sum((p[2] for p in laws), F(0)) / 20,
    )
    return {
        "scenario": scenario,
        "dependence": dep,
        "N": 20,
        "baselines": baselines,
        "candidates": candidates,
        "mean_difference": str(
            sum((F(b - a, 100) for a, b in zip(baselines, candidates, strict=True)), F(0)) / 20
        ),
        "correct_direction": "PASS",
        "balanced": enumerate_balanced(laws).record(),
        "sampled": enumerate_laws([marginal] * 400, SAMPLED).record(),
    }


def floors() -> list[dict[str, int | None]]:
    rows: list[dict[str, int | None]] = []
    for n in (5, 10, 20, 50, 100, 150, 300):
        plan = balanced_plan(n)

        def first(d: int, target: str, n: int = n, plan: Plan = plan) -> int | None:
            return next(
                (
                    k
                    for k in range(n, plan.max_pairs + 1, n)
                    if classify(
                        *count_wealth(k, k if d == -1 else 0, k if d == 1 else 0, plan), plan.alpha
                    )
                    == target
                ),
                None,
            )

        rows.append(
            {
                "N": n,
                "rounds": 400 // n,
                "cap": plan.max_pairs,
                "zero_PASS": first(0, "PASS"),
                "earliest_PASS": first(1, "PASS"),
                "earliest_BLOCK": first(-1, "BLOCK"),
            }
        )
    return rows


def midround() -> dict[str, Any]:
    stream = [1] * 9 + [-1] * 11
    laws = tuple((F(0), F(0), F(1)) if d == 1 else (F(1), F(0), F(0)) for d in stream)
    plan = Plan(batch=1, max_pairs=400, rule=RULE)
    unsafe = enumerate_laws(list(laws) * 20, plan)
    safe = enumerate_balanced(laws)
    actual = decide(stream * 20, batch=1, rule=RULE)
    assert actual.stopping_pairs == 9 and unsafe.probabilities["PASS"] == 1
    assert decide_rounds([stream] * 20, 20).verdict == "INCONCLUSIVE"
    return {
        "N": 20,
        "order": stream,
        "mean_difference": "-1/10",
        "unsafe": unsafe.record(),
        "safe": safe.record(),
        "first_unsafe_PASS": 9,
        "wealth_at_8": str(count_wealth(8, 0, 8, plan)[0]),
        "wealth_at_9": str(count_wealth(9, 0, 9, plan)[0]),
    }


def source_hashes() -> dict[str, str]:
    paths = [
        p
        for directory in (ROOT.parent / "s1", ROOT.parent / "s1b", ROOT)
        for p in directory.glob("*.py")
    ]
    paths += [
        ROOT / "PROOF.md",
        REPO / "FROZEN.sha256",
        REPO / "plan/exec/v2/tasks/S1c-balanced-rounds.md",
    ]
    return {
        str(p.relative_to(REPO)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)
    }


def compute(workers: int) -> dict[str, Any]:
    hashes = source_hashes()
    cases = boundary_cases()
    with ProcessPoolExecutor(
        max_workers=workers, mp_context=multiprocessing.get_context("spawn")
    ) as pool:
        print("A: exact balanced boundary laws", flush=True)
        a = list(pool.map(boundary_job, cases))
        print("A search: 2,000 distinct configurations per N; both objectives", flush=True)
        search = list(
            pool.map(
                search_job, [job for n in (5, 10, 20) for job in search_candidates(n)], chunksize=10
            )
        )
        maxima = []
        for n in (5, 10, 20):
            subset = [r for r in search if r["N"] == n]
            for direction in ("PASS", "BLOCK"):
                winner = max(subset, key=lambda r: F(r[direction]))
                maxima.append(
                    {
                        "N": n,
                        "direction": direction,
                        "index": winner["index"],
                        "probability": winner[direction],
                        "seed": SEEDS[n],
                    }
                )
        print(f"B: 500 fixed schedules for each of {len(cases)} boundary laws", flush=True)
        b = list(
            pool.map(
                schedule_job,
                [(n, name, laws, i) for n, name, laws in cases for i in range(500)],
                chunksize=10,
            )
        )
        stats = []
        for n, name, _ in cases:
            subset = [r for r in b if r["N"] == n and r["law"] == name]
            for direction in ("PASS", "BLOCK"):
                values = [F(r[direction]) for r in subset]
                stats.append(
                    {
                        "N": n,
                        "law": name,
                        "direction": direction,
                        "statistics": describe(values),
                        "exact_mean": str(sum(values, F(0)) / 500),
                    }
                )
        print(
            "C: 36 homogeneous scenarios x 3 grid sizes, then six feasible heterogeneous cases",
            flush=True,
        )
        c = list(
            pool.map(
                power_job,
                [
                    (a, a - drop, dep, n)
                    for a in BASELINES
                    for drop in REGRESSIONS
                    for dep in DEPENDENCES
                    for n in (10, 20, 50)
                ],
            )
        )
        h = list(
            pool.map(
                heterogeneous_job,
                [
                    (scenario, dep)
                    for scenario in ("equal", "all-minus-005", "concentrated-minus-05")
                    for dep in DEPENDENCES
                ],
            )
        )
    assert source_hashes() == hashes
    return {
        "design": {
            "alpha": "1/20",
            "delta": "1/10",
            "stakes": ["1/4", "1/2"],
            "sampled_batch": 10,
            "max_pairs": 400,
        },
        "A": a,
        "search": {
            "seeds": SEEDS,
            "candidate_count_per_N": 2000,
            "restriction": (
                "1000 loss-zero and 1000 loss-win laws on a 1/100 lattice; random "
                "restarts; no global optimality claim"
            ),
            "maxima": maxima,
            "rows": search,
        },
        "B": {"keys_per_law": 500, "rows": b, "statistics": stats},
        "C": c,
        "heterogeneous": h,
        "infeasible": {
            "count_mismatch": "four listed types x two couplings = eight, not twelve",
            "drop_1": (
                "A 1.0 drop requires baseline >=1; every specified baseline is below 1. "
                "Both couplings infeasible. No clipping or replacement."
            ),
        },
        "D": floors(),
        "E": midround(),
        "source_sha256": hashes,
    }


def render(data: dict[str, Any]) -> str:
    lines = [
        "# S1c: balanced rounds versus sampled cells",
        "",
        (
            "All probabilities and expected costs are exact rational absorbing-DP "
            "results; decimal table entries are rounded. Full fractions, cell laws, "
            "candidate configurations, schedule keys and source hashes are in "
            "`results.json`. Fixed alpha=1/20, delta=1/10, stakes={1/4,1/2}; sampled "
            "batch=10, cap=400; balanced cap=N*floor(400/N). Each pair runs both "
            "arms. No outcome simulation is used."
        ),
        "",
        "## A and B. Boundary error control and conditional sampled schedules",
        "",
        (
            "Even: every cell has P(-1)=0.1 and P(0)=0.9. Concentrated-k: k cells "
            "have P(-1)=N/(10k), the others are deterministic zero; infeasible k are "
            "omitted (N=20: k=1; N=50 and 100: k=1,2,3). Half-improving: floor(N/2) "
            "cells have mean +0.3, others compensate; all have only -1/+1 support. "
            "Mixed: floor(N/2) cells have mean -0.4 and the rest compensate, again "
            "both signs possible. Every suite mean is exactly -0.1. Exact cell "
            "probabilities are recorded."
        ),
        "",
        (
            "For B, 500 synthetic schedule keys per law use S1b "
            "schedule_key/cell_index with task-000...task-(N-1), clean condition, "
            "baseline s1c-boundary-baseline-v1 and candidate "
            "s1c-boundary-candidate-0000...0499. The same keys are used across laws "
            "at each N. Ordered, position-dependent laws feed the absorbing DP; "
            "allocations alone do not suffice. The mean over these keys is a finite "
            "schedule sample, not an exact expectation over all schedules. Median "
            "averages the central pair; p90/p99 use nearest rank."
        ),
        "",
        "| N | law | error | balanced | sampled mean | median | p90 | p99 | max |",
        "|---:|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in data["B"]["statistics"]:
        balanced = next(a for a in data["A"] if a["N"] == row["N"] and a["law"] == row["law"])[
            "balanced"
        ][row["direction"]]
        s = row["statistics"]
        lines.append(
            f"| {row['N']} | {row['law']} | {row['direction']} | {float(F(balanced)):.9f} | "
            + " | ".join(f"{s[k]:.9f}" for k in ("mean", "median", "p90", "p99", "max"))
            + " |"
        )
    lines += [
        "",
        "### Adversarial search",
        "",
        data["search"]["restriction"]
        + (
            ". Exactly 2,000 distinct ordered configurations per N; both maxima use "
            "all 2,000 evaluations. Boundary total loss units are fixed at 10N "
            "(loss-zero) or 55N (loss-win). Each restart draws a feasible bounded "
            "integer partition sequentially and shuffles its coordinates. This search"
            " is not uniform over the simplex and does not include general "
            "three-support laws. The proof, not the search, supplies the universal "
            "guarantee."
        ),
        "",
        "| N | direction | maximum found | candidate index | seed |",
        "|---:|---|---:|---:|---:|",
    ]
    for r in data["search"]["maxima"]:
        lines.append(
            f"| {r['N']} | {r['direction']} | {float(F(r['probability'])):.9f} | "
            f"{r['index']} | {r['seed']} |"
        )
    lines += [
        "",
        "## C. Power and cost",
        "",
        (
            "Correct means PASS for equal arms, BLOCK for drops of 0.20 or 0.30. "
            "Intermediate coupling is S1b's equal mixture of independent and Frechet "
            "upper joint laws. Homogeneous cells give both designs the same marginal "
            "law; only registered looks differ. Values are correct-decision "
            "probability / expected pairs."
        ),
        "",
        "| baseline → candidate | coupling | N | balanced | sampled |",
        "|---|---|---:|---:|---:|",
    ]
    for r in data["C"]:
        d = r["correct_direction"]
        lines.append(
            f"| {r['a'] / 100:.2f} → {r['b'] / 100:.2f} | {r['dependence']} | {r['N']} | "
            + " | ".join(
                f"{float(F(r[k][d])):.6f} / {float(F(r[k]['expected_pairs'])):.3f}"
                for k in ("balanced", "sampled")
            )
            + " |"
        )
    lines += [
        "",
        "### Heterogeneous grid (N=20)",
        "",
        (
            "Baseline cells: twelve at 0.99, six at 0.80, two at 0.30. The 0.5 drop "
            "affects the first two 0.99 cells, fixed before outcomes. Equal, "
            "every-cell -0.05, and concentrated -0.5 in 10% have means 0, -0.05, "
            "-0.05: all three are no-regression/within-margin cases. PASS is the "
            "correct directional decision; INCONCLUSIVE makes no directional error. "
            "BLOCK is erroneous. Sampled unconditional laws average cells before "
            "enumeration, assuming independent uniform cell draws; these are not "
            "conditional guarantees for a hashed manifest."
        ),
        "",
        (
            "**Brief defect:** four listed scenario types times two couplings define "
            "eight combinations, not twelve. A 1.0 drop in 20% of cells is impossible"
            " from every specified baseline (<1); both corresponding combinations are"
            " infeasible. Six feasible combinations are evaluated; no probabilities "
            "are clipped and no missing scenarios are invented."
        ),
        "",
        "| scenario | coupling | mean | balanced PASS / cost | sampled PASS / cost |",
        "|---|---|---:|---:|---:|",
    ]
    for r in data["heterogeneous"]:
        lines.append(
            f"| {r['scenario']} | {r['dependence']} | {r['mean_difference']} | "
            + " | ".join(
                f"{float(F(r[k]['PASS'])):.6f} / {float(F(r[k]['expected_pairs'])):.3f}"
                for k in ("balanced", "sampled")
            )
            + " |"
        )
    lines += [
        "",
        "## D. Floors",
        "",
        (
            "Floors are earliest registered complete-round looks, not promises of "
            "power for arbitrary laws. Earliest possible PASS uses all +1; earliest "
            "BLOCK uses all -1. All-zero PASS is a useful low-noise feasibility "
            "diagnostic."
        ),
        "",
        (
            "| N | whole rounds | actual cap | all-zero PASS | earliest possible PASS"
            " | earliest BLOCK |"
        ),
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for r in data["D"]:
        lines.append(
            "| "
            + " | ".join(
                str(r[k])
                for k in ("N", "rounds", "cap", "zero_PASS", "earliest_PASS", "earliest_BLOCK")
            )
            + " |"
        )
    lines += [
        "",
        (
            "Every listed N can reach both a verdict and an all-zero PASS under 400 "
            "pairs. N=150 and 300 have only 300 usable pairs; every other listed N "
            "uses 400. N>400 admits no whole round and hence no protected look. "
            "Within 1<=N<=400 no size is excluded by the all-zero floor: for N<79 its"
            " rounded-up floor is <=156, and for N>=79 the first round suffices. This"
            " is attainability, not a power guarantee."
        ),
        "",
        "## E. Mid-round counterexample",
        "",
        (
            "Nine deterministic +1 cells, then eleven deterministic -1 cells, have "
            "suite mean -0.1. Pairwise looks stop with PASS at pair 9 with exact "
            "probability 1. Twenty complete rounds remain INCONCLUSIVE with exact "
            "probability 1. A terminal partial round ending after the ninth cell is "
            "equally unprotected."
        ),
        "",
        f"Exact PASS wealth at pair 8: `{data['E']['wealth_at_8']}`; "
        f"at pair 9: `{data['E']['wealth_at_9']}`. Threshold: 40. "
        "See `PROOF.md` for the line-by-line proof and assumptions.",
        "",
        "## Conclusions",
        "",
    ]
    max_a = max(F(r["balanced"][d]) for r in data["A"] for d in ("PASS", "BLOCK"))
    max_search = max(F(r["probability"]) for r in data["search"]["maxima"])
    max_b = max(r["statistics"]["max"] for r in data["B"]["statistics"])
    lines.append(
        "(1) Balanced controls each directional error at 1/40=2.5% conditional on every "
        "frozen manifest satisfying independent cell/round differences and stationary laws. "
        f"The largest A error is {float(max_a):.6%}; "
        f"the largest searched error is {float(max_search):.6%}. "
        "This is a theorem under assumptions, not empirical provider validation. "
        f"Sampled conditional errors reach {max_b:.6%} in B; "
        "mid-round balanced looks reach 100%."
    )
    lines.append("")
    summaries = []
    for n in (10, 20, 50):
        rows = [r for r in data["C"] if r["N"] == n]
        gaps = [
            F(r["balanced"][r["correct_direction"]]) - F(r["sampled"][r["correct_direction"]])
            for r in rows
        ]
        costs = [
            F(r["balanced"]["expected_pairs"]) - F(r["sampled"]["expected_pairs"]) for r in rows
        ]
        summaries.append(
            f"N={n}: mean probability change {float(sum(gaps, F(0)) / 36):+.6f} "
            f"(range {float(min(gaps)):+.6f} to {float(max(gaps)):+.6f}), "
            f"mean cost change {float(sum(costs, F(0)) / 36):+.3f} pairs "
            f"(range {float(min(costs)):+.3f} to {float(max(costs)):+.3f})"
        )
    lines.append(
        "(2) Against sampled on the 36 homogeneous cases, "
        + "; ".join(summaries)
        + (
            ". Differences come from checkpoint spacing. Heterogeneous comparisons "
            "additionally remove cell-allocation randomness; their six exact rows "
            "appear above."
        )
    )
    lines += [
        "",
        (
            "(3) All seven requested sizes (5,10,20,50,100,150,300) can decide within"
            " 400 pairs. Their whole-round counts are 80,40,20,8,4,2,1; N=150 and 300"
            " use only 300 pairs. N>400 cannot yield a complete round. A large grid "
            "can meet a best-case floor yet have weak power; floors alone do not "
            "promise utility."
        ),
        "",
        (
            "(4) Recommend balanced only for the claimed conditional-per-manifest "
            "guarantee, with N<=400 and round-end checks enforced. For N>400, require"
            " a larger preregistered budget or an explicitly narrower grid. Sampled "
            "is not an equivalent fallback: B has errors above 2.5% for fixed "
            "schedules, and deterministic hashing does not prove honest "
            "randomization. An unconditional sampled research option would require a "
            "separately stated randomization contract, not the balanced guarantee."
        ),
        "",
        "## Verification and limits",
        "",
        (
            "The adversarial search covers two restricted rational-law families, not "
            "every configuration; the analytic proof supplies the general result. "
            "Within-pair dependence is unrestricted but across-cell or across-round "
            "dependence is not. No runtime integration, network, dependency "
            "installation, or git mutation was performed. All source and artifact "
            "writes stay in s1c."
        ),
    ]
    for name, check in data.get("checks", {}).items():
        lines.append(f"- {name}: exit {check['exit']}; `{check['last_line']}`")
    lines += [
        "",
        (
            "Regenerate and independently repeat: `PYTHONDONTWRITEBYTECODE=1 "
            "PYTHONPATH=plan/exec/v2/spikes/s1:plan/exec/v2/spikes/s1b:plan/exec/v2/spikes/s1c"
            " .venv/bin/python plan/exec/v2/spikes/s1c/run_all.py --verify-repeat`. "
            "All computation reruns; elapsed time is written only to `elapsed.txt`."
        ),
        "",
    ]
    return "\n".join(lines)


def checks() -> dict[str, Any]:
    commands = {
        "pytest": [".venv/bin/pytest", str(ROOT), "-q", "-p", "no:cacheprovider", "-o", "addopts="],
        "ruff_format": [".venv/bin/ruff", "format", "--check", "--no-cache", str(ROOT)],
        "ruff_check": [".venv/bin/ruff", "check", "--no-cache", str(ROOT)],
        "basedpyright": [".venv/bin/basedpyright", str(ROOT)],
        "frozen": ["shasum", "-a", "256", "-c", "FROZEN.sha256"],
    }
    result: dict[str, Any] = {}
    for name, command in commands.items():
        proc = subprocess.run(command, cwd=REPO, capture_output=True, text=True, check=False)
        output = (proc.stdout + proc.stderr).strip().splitlines()
        last = re.sub(r" in [0-9.]+s", " (elapsed excluded)", output[-1] if output else "")
        result[name] = {"command": command, "exit": proc.returncode, "last_line": last}
        print(f"{name}: {proc.returncode}; {last}", flush=True)
        if proc.returncode:
            raise RuntimeError("\n".join(output))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=min(15, os.cpu_count() or 1))
    parser.add_argument("--verify-repeat", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.workers <= 15:
        parser.error("workers must be in 1..15")
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    os.environ["PYTHONPATH"] = ":".join(str(ROOT.parent / d) for d in ("s1", "s1b", "s1c"))
    started = time.monotonic()
    previous: tuple[bytes, bytes] | None = None
    for iteration in range(2 if args.verify_repeat else 1):
        data = compute(args.workers)
        # Stable first-run formatter discovery includes both generated files.
        (ROOT / "results.json").write_text(json.dumps(data, sort_keys=True, indent=2) + "\n")
        (ROOT / "RESULTS.md").write_text(render(data))
        data["checks"] = checks()
        encoded = (json.dumps(data, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
        markdown = render(data).encode()
        if previous is not None and previous != (encoded, markdown):
            raise AssertionError("repeat outputs differ")
        (ROOT / "results.json").write_bytes(encoded)
        (ROOT / "RESULTS.md").write_bytes(markdown)
        previous = (encoded, markdown)
        print(f"Generation {iteration + 1}: all checks passed", flush=True)
    elapsed = time.monotonic() - started
    (ROOT / "elapsed.txt").write_text(f"{elapsed:.3f} seconds\n")
    if args.verify_repeat:
        print("Repeat verification: results.json and RESULTS.md are byte-identical", flush=True)
    print(f"PASS: S1c; elapsed={elapsed:.3f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
