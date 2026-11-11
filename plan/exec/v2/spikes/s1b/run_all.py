"""Regenerate S1b evidence offline, with deterministic outputs and enforced checks."""

from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing
import os
import re
import subprocess
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from fractions import Fraction as F
from pathlib import Path
from typing import Any

from compare_v1 import comparison, simulation_agreement
from conditional import conditional_study
from floors import decision_floors, validate_plan
from schedule import coverage
from stake_selection import CANDIDATES, plan_for, selection
from suite_stats import Plan
from suite_stats_sim import characteristics

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[4]
S1 = ROOT.parent / "s1"


def inputs() -> dict[str, str]:
    paths = [
        S1 / name
        for name in (
            "suite_stats.py",
            "suite_stats_sim.py",
            "CONTRACT.md",
            "RESULTS.md",
            "results.json",
        )
    ]
    paths += [
        REPO / "docs/STATISTICS.md",
        REPO / "FROZEN.sha256",
        REPO / "plan/exec/v2/tasks/S1b-stake-set-and-schedule.md",
    ]
    return {str(p.relative_to(REPO)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def check_commands() -> dict[str, dict[str, object]]:
    commands = {
        "pytest": [
            ".venv/bin/pytest",
            str(ROOT.relative_to(REPO)),
            "-q",
            "-p",
            "no:cacheprovider",
            "-o",
            "addopts=",
        ],
        "ruff_format": [".venv/bin/ruff", "format", "--check", "--no-cache", str(ROOT)],
        "ruff_check": [".venv/bin/ruff", "check", "--no-cache", str(ROOT)],
        "basedpyright": [".venv/bin/basedpyright", str(ROOT)],
        "frozen": ["shasum", "-a", "256", "-c", "FROZEN.sha256"],
    }
    env = {
        **os.environ,
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": f"{S1}:{ROOT}",
        "RUFF_CACHE_DIR": str(ROOT / ".ruff_cache"),
    }
    checked: dict[str, dict[str, object]] = {}
    for name, command in commands.items():
        process = subprocess.run(
            command, cwd=REPO, env=env, capture_output=True, text=True, check=False
        )
        lines = (process.stdout + process.stderr).splitlines()
        stable_lines = [re.sub(r" in [0-9.]+s", " (elapsed excluded)", line) for line in lines[-5:]]
        checked[name] = {"command": command, "exit": process.returncode, "last_lines": stable_lines}
        print(
            f"{name}: exit {process.returncode}; {stable_lines[-1] if stable_lines else ''}",
            flush=True,
        )
        if process.returncode:
            raise RuntimeError(f"{name} failed:\n{process.stdout}\n{process.stderr}")
    return checked


def compute(workers: int) -> dict[str, Any]:
    original_inputs = inputs()
    with ProcessPoolExecutor(
        max_workers=workers, mp_context=multiprocessing.get_context("spawn")
    ) as pool:
        print("Enumerating the 36 x 5 preregistered selection grid", flush=True)
        rows, winner, scores = selection(pool)
        plan = plan_for(winner)
        validate_plan(plan)
        if winner != 1:
            raise AssertionError("recommended-default tests must be updated for a changed winner")
        print("Enumerating 2,000 schedules for each boundary suite", flush=True)
        conditional = conditional_study(pool, plan)
        comparisons = comparison(pool, rows, winner)
    # S1's original table uses different stakes. Reproduce its exact cell first,
    # then compare the new conditional means with its method under the selected stakes.
    old_result = characteristics((F(1, 10), F(9, 10), F(0)), Plan())[0]
    old_data = json.loads((S1 / "results.json").read_text())
    old_cell = next(
        r
        for group in old_data["A"]
        if group["batch"] == 10 and group["p_zero"] == "9/10" and group["region"] == "boundary"
        for r in group["rows"]
        if r["n"] == 400
    )
    if old_result["lower"] != old_cell["lower"]:
        raise AssertionError("S1 Table A original-stake cell did not reproduce exactly")
    floor_rows = []
    for delta in (F(1, 20), F(1, 10), F(1, 5)):
        for batch in (1, 10):
            p = replace(plan, delta=delta, batch=batch)
            validate_plan(p)
            floor_rows.append({"delta": str(delta), "batch": batch, "floors": decision_floors(p)})
    disadvantages = []
    for row in rows:
        if row["candidate"] == winner:
            continue
        reference = next(
            r
            for r in rows
            if r["candidate"] == winner
            and r["a"] == row["a"]
            and r["b"] == row["b"]
            and r["dependence"] == row["dependence"]
        )
        direction = "PASS" if row["a"] == row["b"] else "BLOCK"
        gap = F(row["enumeration"][-1]["lower"][direction]) - F(
            reference["enumeration"][-1]["lower"][direction]
        )
        if gap > F(1, 50):
            disadvantages.append(
                {
                    "a": row["a"],
                    "b": row["b"],
                    "dependence": row["dependence"],
                    "other_candidate": row["candidate"],
                    "gap": float(gap),
                    "gap_exact": str(gap),
                }
            )
    print("Checking simulated streams through rational suite_stats.decide", flush=True)
    agreement = simulation_agreement()
    if inputs() != original_inputs:
        raise AssertionError("read-only inputs changed during the run")
    return {
        "winner": winner,
        "stakes": [str(q) for q in CANDIDATES[winner]],
        "alpha": "1/20",
        "delta": "1/10",
        "batch": 10,
        "max_pairs": 400,
        "selection": rows,
        "scores": scores,
        "disadvantages_over_002": disadvantages,
        "floors": floor_rows,
        "coverage": coverage(),
        "conditional": conditional,
        "s1_table_a_original_stakes": old_result,
        "comparison": comparisons,
        "stream_agreement": agreement,
        "input_sha256": original_inputs,
        "source_sha256": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(ROOT.glob("*.py"))
        },
    }


def render(data: dict[str, Any]) -> str:
    # Values are generated locally, not parsed from an untrusted schema.
    names = ["{" + ", ".join(str(q) for q in fractions) + "}" for fractions in CANDIDATES]
    winner = data["winner"]
    score = data["scores"][winner]
    best = max(s["minimum_correct"] for s in data["scores"])
    lines = [
        "# S1b stake selection, decision floors and schedule limits",
        "",
        f"Selected equal-weight stake set: **{names[winner]}**. "
        "alpha=1/20, delta=1/10, batch=10, max_pairs=400 (800 sessions).",
        "",
        "Offline standard-library research spike. S1 is imported unchanged. "
        "All probability enumerations use exact rational mass and integer decision frontiers; "
        "displayed decimals are rounded. Expected pairs are capped first-stop expectations, "
        "including INCONCLUSIVE at the cap. Fractions are retained in results.json.",
        "",
        "## 1. Preregistered stake selection",
        "",
        "The five candidates, 36 scenarios and tie rule are exactly the task brief's grid. "
        "An earlier informal reviewer grid favoured {1/4, 1/2}; that prior information was "
        "disclosed before this systematic run. No grid or criterion was changed.",
        "",
        f"Winner minimum correct-decision probability: {score['minimum_correct']:.9f}; "
        f"maximum across sets: {best:.9f}; shortfall: "
        f"{best - score['minimum_correct']:.9f}. The inclusive 0.01 band ties candidates "
        "1 and 3 (zero-based); candidate 1 has lower mean stopping pairs. "
        "Probability tie-band membership uses exact fractions; mean costs are displayed "
        "as binary64 values from S1's exact integer stopping-mass sum. "
        "The cost gap is over ten pairs, far above display rounding.",
        "",
        "| stakes | minimum correct probability | mean expected pairs |",
        "|---|---:|---:|",
    ]
    for s in data["scores"]:
        lines.append(
            f"| {names[s['candidate']]} | {s['minimum_correct']:.9f} | "
            f"{s['mean_expected_pairs']:.6f} |"
        )
    lines += [
        "",
        "Each cell below is **correct-decision probability / expected pairs**. "
        "Correct means PASS for no change, BLOCK for either regression. "
        "Intermediate coupling is the equal mixture of independent and Frechet upper laws.",
        "",
        "| baseline → candidate | dependence | " + " | ".join(names) + " |",
        "|---|---|" + "---:|" * 5,
    ]
    rows = data["selection"]
    for start in range(0, len(rows), 5):
        group = rows[start : start + 5]
        first = group[0]
        lines.append(
            f"| {first['a'] / 100:.2f} → {first['b'] / 100:.2f} | {first['dependence']} | "
            + " | ".join(f"{r['correct']:.6f} / {r['expected_pairs']:.3f}" for r in group)
            + " |"
        )
    lines += [
        "",
        "Winner disadvantages exceeding 0.02 probability (strict, exact comparison):",
        "",
        "| other stakes | baseline → candidate | dependence | other minus winner |",
        "|---|---|---|---:|",
    ]
    for row in data["disadvantages_over_002"]:
        lines.append(
            f"| {names[row['other_candidate']]} | {row['a'] / 100:.2f} → "
            f"{row['b'] / 100:.2f} | {row['dependence']} | {row['gap']:.6f} |"
        )
    for index in range(5):
        if index != winner and not any(
            r["other_candidate"] == index for r in data["disadvantages_over_002"]
        ):
            lines.append(f"| {names[index]} | none | — | — |")
    lines += [
        "",
        "## 2. Decision floors",
        "",
        "Floors are earliest registered checkpoints within the 400-pair horizon, including "
        "a terminal partial batch. Earliest possible PASS uses all +1; earliest BLOCK all -1. "
        "The loss rows use exactly k differences -1 and zeros otherwise; they describe "
        "attainable checkpoint wealth, not an ordering-independent first-stop promise. "
        "Counts alone cannot certify that a supplied ordered stream did not stop earlier. "
        "validate_plan rejects a cap at which the all-zero stream cannot PASS.",
        "",
        "| delta | batch | any PASS | all-zero PASS | 1 loss | 2 losses | 3 losses | 5 losses | "
        "any BLOCK | max losses / zeros at 200, 400 | max losses / wins at 200, 400 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in data["floors"]:
        f = row["floors"]
        losses = f["pass_with_losses_and_zeros"]
        zeros, wins = f["max_losses_with_zeros"], f["max_losses_with_wins"]
        lines.append(
            f"| {row['delta']} | {row['batch']} | {f['earliest_possible_pass']} | "
            f"{f['all_zero_pass']} | "
            + " | ".join(str(losses[str(k)]) for k in (1, 2, 3, 5))
            + f" | {f['earliest_block']} | {zeros['200']}, {zeros['400']} | "
            f"{wins['200']}, {wins['400']} |"
        )
    lines += [
        "",
        "## 3. Portable schedule and coverage",
        "",
        "schedule_key hashes b'arci-suite/1 key' followed by compact sorted-key ASCII-escaped "
        "JSON encoded as UTF-8. Cells sort by (task_id, condition_id); cell field order and "
        "cosmetic fields do not matter. Arm identities and prior-run list order are bound. "
        "Rule fractions are reduced numerator/denominator strings and stakes sort numerically. "
        "The caller supplies immutable content identities; this spike is not a product manifest "
        "parser or a verifier of those identities. See schedule.py for the exact field contract.",
        "",
        "Cell draw: SHA-256(b'arci-suite/1 cell' + key + uint64be(i) + uint32be(attempt)); "
        "the first uint64 is accepted below 2**64 - (2**64 % n_cells), then reduced modulo "
        "n_cells. Attempts start at zero. Seed: first uint64 of SHA-256(b'arci-suite/1 seed' "
        "+ key + uint64be(i)), high bit cleared. Both arms use the same pair seed. "
        "Repeated cells use distinct indices; 63-bit truncation cannot promise collision "
        "freedom over arbitrary inputs. Tests confirm distinct seeds in the exercised sample.",
        "",
        "Tests freeze 24 literal (key,index,n_cells) vectors with expected draws and seeds, "
        "exercise rejection with a 4-bit helper, and check 200,000 draws for each of "
        "7, 20, 60 and 150 cells. The conservative chi-square diagnostic threshold is "
        "df + 2*sqrt(df*log(1e6)) + 2*log(1e6), fixed before results. These finite checks "
        "do not prove IID behavior or cross-version execution; only this host was run.",
        "",
        "Exact formulas: P(given cell unseen)=(1-1/C)^n; E(unseen cells)=C*(1-1/C)^n. "
        "The following decimals are rounded; full exact fractions are in results.json.",
        "",
        "| cells | pairs | P(given cell unseen) | E(unseen cells) |",
        "|---:|---:|---:|---:|",
    ]
    for r in data["coverage"]:
        lines.append(
            f"| {r['cells']} | {r['pairs']} | {r['probability']:.10f} | {r['expected']:.8f} |"
        )
    lines += [
        "",
        "## 4. Conditional on a frozen schedule",
        "",
        "Declared before computation: concentrated law has 3/20 cells with P(-1)=2/3 "
        "and 17/20 deterministic-zero cells; even law has P(-1)=1/10 in all 20 cells. "
        "Both have P(+1)=0, suite mean -1/10 and marginal law (-,0,+)=(1/10,9/10,0). "
        "One realization is baseline always succeeds, with candidate success 1/3 in "
        "the three affected cells and 1 elsewhere; the even candidate succeeds with 9/10. "
        "Both PASS and BLOCK are directional errors at this boundary.",
        "",
        "Exactly 2,000 keys: schedule_key on task-00 through task-19, condition clean, "
        "baseline identity boundary-baseline-v1 and candidate identity "
        "boundary-candidate-0000 through boundary-candidate-1999, empty prior runs, "
        "selected rule. The same keys are used for both laws. These are synthetic identities, "
        "not actual campaign history or an assertion that changed laws share a valid "
        "production manifest. There was no key selection by observed outcomes. "
        "An exact position-dependent absorbing DP evaluates each concentrated schedule. "
        "The even-law result is schedule-invariant and computed once, recorded for every key. "
        "Median averages the middle two; p90/p99 use nearest rank.",
        "",
        "| law | direction | mean | min | median | p90 | p99 | max |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for scenario, directions in data["conditional"]["statistics"].items():
        for direction, stats in directions.items():
            lines.append(
                f"| {scenario} | false {direction} | "
                + " | ".join(
                    f"{stats[k]:.9f}" for k in ("mean", "min", "median", "p90", "p99", "max")
                )
                + " |"
            )
    reference = data["conditional"]["iid_reference"]["summary"]
    old = data["s1_table_a_original_stakes"]["summary"]
    lines += [
        "",
        f"Selected-stake S1 Table-A-method IID reference: false PASS={reference['PASS']:.9f}, "
        f"false BLOCK={reference['BLOCK']:.9f}. Original S1 Table A at p_zero=0.90, "
        f"cap=400, batch=10: PASS={old['PASS']:.9f}, BLOCK={old['BLOCK']:.9f}; "
        "its rational values reproduce exactly. The original stakes differ, so equality "
        "between the new means and the old numeric table is not expected and is not claimed. "
        "The even schedule agrees exactly with S1's enumeration under the selected rule. "
        "Concentrated means satisfy the predeclared finite-key agreement diagnostic "
        "(five empirical standard errors plus 1e-12); the individual probabilities are "
        "exact, but their 2,000-key mean is a finite schedule sample, not an exact average "
        "over all possible keys.",
        "",
        "| mean comparison | absolute difference | schedule-sample standard error | check |",
        "|---|---:|---:|---|",
    ]
    for name, check in data["conditional"]["checks"].items():
        lines.append(
            f"| {name} | {check['absolute_difference']:.9f} | "
            f"{check['standard_error']:.9f} | {check['within_five_se']} |"
        )
    lines += [
        "",
        "**A single manifest does not receive a conditional 2.5% error guarantee.** "
        "The theorem averages over an honest schedule draw as well as trial outcomes; "
        "hashing a chosen manifest does not itself establish that randomization assumption. "
        "Some conditional errors are much larger than 2.5%, even before any cherry-picking. "
        "A user may interpret PASS as suite-mean noninferiority under the stated sampling "
        "contract, not per-cell reliability, absolute reliability or a posterior probability. "
        "Key grinding and selecting manifests by allocations are disclosed risks, not "
        "detected violations. A future report must show draws per cell and cells never drawn.",
        "",
        "## 5. Published v1 comparison",
        "",
        "v1 values are rounded published inputs from docs/STATISTICS.md, K=1, independent "
        "arms: fixed N=200 or sequential looks 50/100/200. The ceiling is 400 sessions. "
        "N=400 v1 values for this complete scenario set are not published, nor are "
        "intermediate-coupling values; neither is invented. v2 cap 200 has the same ceiling; "
        "v2 cap 400 has twice that ceiling. Intermediate rows are v2-only, not claims "
        "against independent-arm v1. At 0.95→0.85 both decisions are errors, so correct "
        "probability is N/A and directional errors are shown. No significance claim is "
        "made about comparisons with rounded published values.",
        "",
        "| rates | v1 method | correct probability | false/total PASS | false/total BLOCK | "
        "expected sessions | ceiling sessions |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for r in data["comparison"]["v1"]:

        def display(value: object) -> str:
            return "not published / N/A" if value is None else str(value)

        lines.append(
            f"| {r['a'] / 100:.2f} → {r['b'] / 100:.2f} | {r['method']} | "
            f"{display(r['correct'])} | {display(r['PASS'])} | {display(r['BLOCK'])} | "
            f"{r['expected_sessions']:.1f} | {r['ceiling_sessions']} |"
        )
    lines += [
        "",
        "| rates | v2 dependence | cap | correct probability | PASS | BLOCK | "
        "expected sessions | ceiling sessions |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in data["comparison"]["v2"]:
        for e in r["enumeration"]:
            s = e["summary"]
            correct = (
                "N/A (boundary)"
                if r["a"] - r["b"] == 10
                else (f"{s['PASS'] if r['a'] == r['b'] else s['BLOCK']:.6f}")
            )
            lines.append(
                f"| {r['a'] / 100:.2f} → {r['b'] / 100:.2f} | {r['dependence']} | {e['n']} | "
                f"{correct} | {s['PASS']:.6f} | {s['BLOCK']:.6f} | "
                f"{2 * s['mean']:.3f} | {2 * e['n']} |"
            )
    lines += [
        "",
        *data["comparison"]["bottom_lines"],
        "",
        "## 6. Verification and limits",
        "",
        "Every checkpoint through 400 pairs compares S1's integer frontier with rational "
        "count_wealth plus classify at both sides of both frontiers for every minus count. "
        "The agreement point uses 1,000 seeded paired Bernoulli streams (0.80→0.80, "
        "independent, cap 400) through suite_stats.decide, never the shared frontier; "
        "each verdict frequency is checked within five binomial SE plus 1/reps of exact "
        "enumeration. An exhaustive six-pair ordered-path test independently checks "
        "the conditional recurrence.",
        "",
        "Stream agreement: `" + json.dumps(data["stream_agreement"], sort_keys=True) + "`.",
        "",
    ]
    for name, check in data.get("checks", {}).items():
        lines.append(f"- {name}: exit {check['exit']}; last line: `{check['last_lines'][-1]}`")
    lines += [
        "",
        "Regenerate: `PYTHONDONTWRITEBYTECODE=1 "
        "PYTHONPATH=plan/exec/v2/spikes/s1:plan/exec/v2/spikes/s1b "
        ".venv/bin/python plan/exec/v2/spikes/s1b/run_all.py --verify-repeat`. "
        "The repeat option recomputes all results and checks, comparing output bytes; "
        "elapsed.txt is the only output allowed to change. Source/input hashes are "
        "recorded in results.json. No frozen or S1 file is modified; bytecode and test "
        "caches are disabled. This is a statistical spike, not production runner "
        "integration, cross-platform validation, or evidence of provider stationarity.",
        "",
        "Unexpected result: the concentrated schedule's conditional errors have a much "
        "wider spread than the earlier review's illustrative range. That is a valid "
        "result for this explicitly declared sparse-loss law, not a failed unconditional "
        "error bound. The selected set's all-zero floor rises from S1's 70 to 80 pairs.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=min(15, os.cpu_count() or 1))
    parser.add_argument("--verify-repeat", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.workers <= 15:
        parser.error("workers must be in 1..15")
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    started = time.monotonic()
    prior: tuple[bytes, bytes] | None = None
    data: dict[str, Any] = {}
    for iteration in range(2 if args.verify_repeat else 1):
        data = compute(args.workers)
        # Materialize both outputs before checking: Ruff also discovers Markdown,
        # so its file count must not depend on whether this is a first generation.
        (ROOT / "results.json").write_text(json.dumps(data, sort_keys=True, indent=2) + "\n")
        (ROOT / "RESULTS.md").write_text(render(data))
        data["checks"] = check_commands()
        encoded = (json.dumps(data, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
        markdown = render(data).encode()
        if prior is not None and prior != (encoded, markdown):
            raise AssertionError("second regeneration was not byte-identical")
        (ROOT / "results.json").write_bytes(encoded)
        (ROOT / "RESULTS.md").write_bytes(markdown)
        prior = (encoded, markdown)
        print(f"Generation {iteration + 1}: all checks passed", flush=True)
    elapsed = time.monotonic() - started
    (ROOT / "elapsed.txt").write_text(f"{elapsed:.3f} seconds\n")
    if args.verify_repeat:
        print("Repeat verification: results.json and RESULTS.md are byte-identical", flush=True)
    print(f"PASS: winner={data['stakes']}; elapsed={elapsed:.3f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
