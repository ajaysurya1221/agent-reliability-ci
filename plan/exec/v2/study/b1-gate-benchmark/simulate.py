"""Run the single registered B1 design after publication, or resume its journal."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import math
import os
import platform
import sys
from collections import Counter
from collections.abc import Callable, Iterator
from fractions import Fraction
from importlib.metadata import version
from pathlib import Path
from random import Random
from subprocess import run
from typing import Any, BinaryIO, Literal, NamedTuple

from evaluate import (
    RATES,
    REGIMES,
    SCHEMA,
    STREAMS,
    Cell,
    GateSummary,
    Summary,
    histogram_median,
    metric_counts,
    rate,
    read_evaluation,
)
from gates import (
    CAP,
    GATES,
    OUTCOMES,
    ROUNDS,
    RULE,
    TASKS,
    Counts,
    Decision,
    decisions,
)

from arci.suite_schedule import create_suite_manifest
from arci.suite_schema import SuiteManifest

HERE = Path(__file__).resolve().parent
MASTER = "ARCI-B1-20261125-v1"
Panel = Literal["primary", "outage"]
Regime = Literal["I", "P"]
PANELS: tuple[Panel, ...] = ("primary", "outage")


class Key(NamedTuple):
    panel: Panel
    regime: Regime
    pc: int
    replicate: int


def seed(key: Key, purpose: str) -> int:
    label = f"{MASTER}|{key.panel}|{key.regime}|{key.pc}|{key.replicate}|{purpose}"
    return int.from_bytes(hashlib.sha256(label.encode("ascii")).digest(), "big")


def draw_rounds(
    pc: int,
    regime: Regime,
    panel: Panel,
    draw: Callable[[int], int],
    outage_draw: Callable[[int], int],
    *,
    tasks: int = TASKS,
    rounds: int = ROUNDS,
) -> tuple[Counts, ...]:
    stream: list[Counts] = []
    for _ in range(rounds):
        if panel == "outage" and outage_draw(100) < 5:
            stream.append(Counts(tasks, 0, 0, 0))
            continue
        counts = [0, 0, 0, 0]
        for _ in range(tasks):
            u = draw(100)
            v = u if regime == "P" else draw(100)
            counts[2 * (u < 95) + (v < pc)] += 1
        stream.append(Counts(*counts))
    return tuple(stream)


def one_stream(key: Key) -> dict[str, Decision]:
    stream = draw_rounds(
        key.pc,
        key.regime,
        key.panel,
        Random(seed(key, "pairs")).randrange,
        Random(seed(key, "outage")).randrange,
    )
    return decisions(stream, Random(seed(key, "bootstrap")))


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def identity() -> str:
    versions = {name: version(name) for name in ("agent-reliability-ci", "pydantic", "pyyaml")}
    if versions["agent-reliability-ci"] != "2.4.1" or platform.python_version() != "3.13.12":
        raise RuntimeError("the registration specifies CPython 3.13.12 and released ARCI 2.4.1")
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in HERE.glob("*.py")}
    return hashlib.sha256(
        canonical([MASTER, versions, platform.python_version(), hashes])
    ).hexdigest()


def atomic_write(path: Path, data: str) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(data, encoding="utf-8")
    temp.replace(path)


def write_design(path: Path, content: str) -> None:
    if path.exists():
        if path.read_text(encoding="utf-8") != content:
            raise ValueError(f"cannot resume with a different design in {path.name}")
    else:
        atomic_write(path, content)


def journal_entry(
    journal: BinaryIO,
    key: Key,
    run_id: str,
    produce: Callable[[Key], dict[str, Decision]],
) -> dict[str, Decision]:
    offset = journal.tell()
    line = journal.readline()
    if line.endswith(b"\n"):
        record = json.loads(line)
        checksum = record.pop("sha256")
        if (
            hashlib.sha256(canonical(record)).hexdigest() != checksum
            or record["run_id"] != run_id
            or record["stream"] != list(key)
            or set(record["gates"]) != set(GATES)
        ):
            raise ValueError(f"journal identity, order, roster or checksum mismatch at {offset}")
        result = {g: Decision(*record["gates"][g]) for g in GATES}
        for decision in result.values():
            if (
                decision.verdict not in OUTCOMES
                or type(decision.pairs) is not int
                or decision.pairs not in range(TASKS, CAP + 1, TASKS)
                or (decision.verdict == "INCONCLUSIVE" and decision.pairs != CAP)
            ):
                raise ValueError(f"invalid journal decision at {offset}")
        return result
    if line:
        # Only a final, uncommitted fragment can lack the newline.
        journal.seek(offset)
        journal.truncate()
    result = produce(key)
    record = {"run_id": run_id, "stream": key, "gates": result}
    checksum = hashlib.sha256(canonical(record)).hexdigest()
    journal.write(canonical({**record, "sha256": checksum}) + b"\n")
    return result


def plan_manifest() -> SuiteManifest:
    # Mandatory runner identifiers on a planning-only manifest. No agent is executed.
    return create_suite_manifest(
        suite_id=RULE.suite_id,
        tasks=[{"task_id": t} for t in RULE.tasks],
        conditions=[{"condition_id": "binary"}],
        contract={"oracle": "b1:unused"},
        toolset="b1:unused",
        baseline={"label": "baseline", "agent": "b1:unused"},
        candidate={"label": "candidate", "agent": "b1:unused"},
        scenario_seeds="per_round",
        alpha=RULE.alpha,
        delta=RULE.margin,
        stakes=RULE.stakes,
        max_rounds=RULE.max_rounds,
        max_errored_pairs=RULE.max_errored_pairs,
    )


def agreement(b: Fraction, p: Fraction, regime: Regime) -> Fraction:
    return b * p + (1 - b) * (1 - p) if regime == "I" else 1 - abs(b - p)


def exact_plan(manifest: Path, b: Fraction, p: Fraction, regime: Regime) -> dict[str, Any]:
    cmd = [
        sys.executable,
        "-m",
        "arci",
        "plan",
        str(manifest),
        "--baseline-rate",
        str(b),
        "--candidate-rate",
        str(p),
        "--agreement",
        str(agreement(b, p, regime)),
        "--format",
        "json",
    ]
    proc = run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(proc.stdout)
    if data["schema"] != "arci.plan.suite.v1" or data["status"] != "exact projection":
        raise ValueError(f"required exact projection unavailable: {data.get('status')}")
    return data


class Tallies:
    def __init__(self) -> None:
        self.verdicts = {g: Counter[str]() for g in GATES}
        self.costs = {g: Counter[int]() for g in GATES}

    def add(self, row: dict[str, Decision]) -> None:
        for g, (verdict, pairs) in row.items():
            self.verdicts[g][verdict] += 1
            self.costs[g][pairs] += 1

    def cell(self, panel: Panel, regime: Regime, pc: int, plan: dict[str, Any] | None) -> Cell:
        gates: dict[str, GateSummary] = {}
        n = self.costs["arci"].total()
        for g in GATES:
            counts = self.verdicts[g]
            hist = {str(k): v for k, v in sorted(self.costs[g].items())}
            metrics = metric_counts({v: counts[v] for v in OUTCOMES}, g, panel, pc)
            gates[g] = GateSummary(
                rates={k: rate(v, n) for k, v in metrics.items()},
                mean_pairs=sum(int(k) * v for k, v in hist.items()) / n,
                median_pairs=histogram_median(hist, n),
                pair_counts=hist,
            )
        check: dict[str, Any] | None = None
        if plan is not None:
            projection = plan["projection"]
            check = {}
            for verdict in ("PASS", "BLOCK", "INCONCLUSIVE"):
                target = float(Fraction(projection[verdict]))
                observed = gates["arci"].rates[verdict]
                check[verdict] = {
                    "exact": target,
                    "observed_minus_exact": observed.rate - target,
                    "in_mc_95": observed.low <= target <= observed.high,
                }
            expected = float(Fraction(projection["expected_pairs"]))
            diff = gates["arci"].mean_pairs - expected
            radius = (CAP - TASKS) * math.sqrt(math.log(40) / (2 * n))
            check["pairs"] = {
                "exact": expected,
                "observed_minus_exact": diff,
                "in_mc_95": abs(diff) <= radius,
            }
        return Cell(
            panel=panel,
            regime=regime,
            candidate_percent=pc,
            streams=n,
            gates=gates,
            exact_plan=plan,
            crosscheck=check,
        )


def markdown(cells: list[Cell], panel: Panel) -> str:
    def percent(r: tuple[int, float, float, float]) -> str:
        return f"{100 * r[1]:.3f} [{100 * r[2]:.3f}, {100 * r[3]:.3f}]"

    sections = [
        f"# B1 {'primary results' if panel == 'primary' else 'correlated outage stress'}",
        "Rates are percentages with two-sided exact 95% Clopper-Pearson intervals.",
        "A dash marks a measure outside its defined scope. Costs count trial pairs.",
    ]
    if panel == "outage":
        sections.append(
            "Candidate percentages label the outage-free law. The marginal difference "
            "equals 0.95 times the labeled difference. This panel is descriptive."
        )
    for cell in cells:
        if cell.panel != panel:
            continue
        cols = [*OUTCOMES, "decided", "wrong_PASS", "wrong_BLOCK", "correct"]
        rows = [
            "| Gate | " + " | ".join(cols) + " | Mean pairs | Median pairs |",
            "|" + "---|" * (len(cols) + 3),
        ]
        for g in GATES:
            stat = cell.gates[g]
            data = [percent(stat.rates[k]) if k in stat.rates else "—" for k in cols]
            rows.append(
                "| "
                + " | ".join([g, *data, f"{stat.mean_pairs:.3f}", f"{stat.median_pairs:g}"])
                + " |"
            )
        sections.extend([f"## {cell.regime}, candidate {cell.candidate_percent}%", "\n".join(rows)])
        if cell.crosscheck is not None:
            sections.append("Exact verdict probabilities use the 0 to 1 scale. Cost uses pairs.")
            check_rows = [
                "| ARCI measure | Exact | Observed minus exact | Inside MC 95% interval |",
                "|---|---:|---:|---|",
            ]
            for name, c in cell.crosscheck.items():
                check_rows.append(
                    f"| {name} | {c['exact']:.8g} | {c['observed_minus_exact']:.6g} "
                    f"| {c['in_mc_95']} |"
                )
            sections.append("\n".join(check_rows))
    return "\n\n".join(sections) + "\n"


def cell_roster() -> Iterator[tuple[Panel, Regime, int]]:
    for panel in PANELS:
        for regime in REGIMES:
            for pc in RATES:
                yield panel, regime, pc


def write_outputs(out: Path, summary: Summary) -> None:
    path = out / "summary.json"
    atomic_write(path, summary.model_dump_json(indent=2) + "\n")
    result = read_evaluation(path)
    atomic_write(out / "criteria.json", json.dumps(result, indent=2) + "\n")
    headline = (
        f"C1 {result['C1']} · C2 {result['C2']} · C3 {result['C3']}. "
        f"Efficiency claim {result['efficiency_claim']}. {result['conclusion']}"
    )
    eligible = [c for c in result["comparisons"] if c["calibrated"]]
    if eligible:
        lines = [
            "### C3 comparisons with every C1-eligible margin rival",
            "",
            "| Regime | Candidate | Rival | A - 0.8 R pairs (simultaneous 95%) "
            "| Correct-rate gap (points) |",
            "|---|---:|---|---:|---:|",
        ]
        for c in eligible:
            regime, pc = c["cell"]
            lo, hi = c["simultaneous_95"]
            lines.append(
                f"| {regime} | {pc}% | {c['rival']} | {c['mean_contrast_pairs']:.3f} "
                f"[{lo:.3f}, {hi:.3f}] | {100 * c['correct_rate_difference']:.3f} |"
            )
        headline += "\n\n" + "\n".join(lines)
    else:
        headline += " No margin-matched rival passed C1."
    atomic_write(
        out / "results.md",
        markdown(summary.cells, "primary").replace("\n\n", "\n\n" + headline + "\n\n", 1),
    )
    atomic_write(out / "stress.md", markdown(summary.cells, "outage"))
    names = (
        "results.jsonl",
        "summary.json",
        "criteria.json",
        "results.md",
        "stress.md",
        "planner-manifest.json",
        "fixed-rule.json",
    )
    lines = []
    for name in names:
        with (out / name).open("rb") as f:
            lines.append(f"{hashlib.file_digest(f, 'sha256').hexdigest()}  {name}")
    atomic_write(out / "digests.sha256", "\n".join(lines) + "\n")


def registered_run() -> None:
    run_id = identity()
    out = HERE / "output"
    out.mkdir(exist_ok=True)
    manifest = out / "planner-manifest.json"
    with (out / "results.jsonl").open("a+b") as journal:
        fcntl.flock(journal, fcntl.LOCK_EX | fcntl.LOCK_NB)
        journal.seek(0)
        write_design(manifest, plan_manifest().model_dump_json(indent=2) + "\n")
        write_design(
            out / "fixed-rule.json", RULE.model_dump_json(exclude_none=True, indent=2) + "\n"
        )
        cells: list[Cell] = []
        for panel, regime, pc in cell_roster():
            tallies = Tallies()
            for i in range(STREAMS):
                row = journal_entry(journal, Key(panel, regime, pc, i), run_id, one_stream)
                tallies.add(row)
            journal.flush()
            os.fsync(journal.fileno())
            plan = (
                exact_plan(manifest, Fraction(95, 100), Fraction(pc, 100), regime)
                if panel == "primary"
                else None
            )
            cells.append(tallies.cell(panel, regime, pc, plan))
            print(f"{panel} {regime} {pc}%: {STREAMS} streams recorded", flush=True)
        if journal.read(1):
            raise ValueError("unexpected records after registered stream inventory")
        summary = Summary(format=SCHEMA, master_seed=MASTER, run_id=run_id, cells=cells)
        write_outputs(out, summary)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run-registered",
        action="store_true",
        required=True,
        help="execute all primary and outage streams using the frozen design",
    )
    parser.parse_args()
    registered_run()
