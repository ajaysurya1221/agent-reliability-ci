"""Fresh Reply-0 stand-in stores for the C0 delivery check and full server rehearsals."""

from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from harness import audit, count_a, count_b, make_suites  # noqa: E402

SCENARIOS = {
    "directional": ("corrected", "gives-up"),
    "equal": ("corrected", "corrected"),
    "swapped": ("gives-up", "corrected"),
    "control-pair": ("corrected", "corrected"),
    "edited-pair": ("corrected", "gives-up"),
}


def first_requests(receipts: Path) -> int:
    """Replace just the parsed tool text and reproduce the other arm's exact bytes."""
    paired: dict[tuple[str, int], dict[str, bytes]] = defaultdict(dict)
    for file in receipts.glob("*.json"):
        row = audit.read(file)
        paired[row["key_id"], row["seed"]][row["arci_arm"]] = base64.b64decode(
            row["exchanges"][0]["request_b64"], validate=True
        )
    for arms in paired.values():
        baseline = json.loads(arms["baseline"])
        original = json.dumps(baseline, ensure_ascii=False, allow_nan=False).encode()
        audit.require(original == arms["baseline"], "first baseline request serialization")
        tool = baseline["messages"][-1]
        other = json.loads(arms["candidate"])["messages"][-1]
        audit.require(tool["role"] == "tool" and tool["content"] != other["content"], "opening")
        tool["content"] = other["content"]
        body = json.dumps(baseline, ensure_ascii=False, allow_nan=False).encode()
        audit.require(body == arms["candidate"], "first request differs outside delivered text")
    return len(paired)


def rehearse(cell: str, scenario: str, output: Path, checks: Path, pipes: bool) -> None:
    run = f"offline-{cell}-{scenario}"
    work = output / run
    work.mkdir(parents=True, exist_ok=False)
    print(f"Starting {run}", flush=True)
    doc = make_suites.register()
    phase = "confirmation" if scenario == "edited-pair" else "main"
    tasks = doc["cells"][cell]["held_out" if phase == "confirmation" else "main"]
    plain = scenario.endswith("-pair")
    if plain:
        tasks = tasks[:1]
    edited = None
    if phase == "confirmation":
        edited = work / "edited"
        audit.build(audit.ENV, edited, cell)
    baseline, candidate = SCENARIOS[scenario]
    for script in {baseline, candidate}:
        make_suites.write_json(
            work / f"{script}.json",
            {
                task["key_id"]: {
                    "script": script,
                    "good": task["good"],
                    "expect": task["expect"],
                    "world_key": "order.total_cents" if cell == "C0" else None,
                }
                for task in tasks
            },
        )
    descriptor = work / "descriptor.yaml"
    make_suites.write_json(
        descriptor,
        make_suites.descriptor(
            doc,
            audit.ENV,
            audit.FX,
            cell,
            phase,
            "4B",
            tasks,
            run=run,
            plain=plain,
            edited=edited,
            plans=(work / f"{baseline}.json", work / f"{candidate}.json"),
        ),
    )
    stores = work / "stores"
    receipts = work / "receipts"
    command = (
        [
            sys.executable,
            "-B",
            str(ROOT / "harness/tests/core/offline_run.py"),
            str(descriptor),
            str(stores),
        ]
        if pipes
        else [
            sys.executable,
            "-B",
            "-m",
            "arci",
            "run",
            "--workers",
            "1",
            "--out",
            str(stores),
            str(descriptor),
        ]
    )
    store = stores / audit.compile_run_descriptor(descriptor).experiment_id
    with (work / "run.log").open("xb") as log:
        process = subprocess.Popen(
            command,
            env={**os.environ, "REPLY0_RECEIPTS": str(receipts)},
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        # The released CLI prints the absolute output directory as an informational line.
        # Log its study-relative location at emission. Preserve every other diagnostic.
        assert process.stdout
        location = f"run store: {store}".encode()
        with process.stdout:
            for line in process.stdout:
                log.write(
                    line.replace(location, f"run store: {store.relative_to(ROOT)}".encode())
                    if line.rstrip(b"\r\n") == location
                    else line
                )
        process.wait()
    decision = audit.read(store / "decision.json")
    expected = "INCONCLUSIVE" if plain else "BLOCK" if scenario == "directional" else "PASS"
    audit.same(
        [decision["verdict"], process.returncode],
        [expected, {"BLOCK": 1, "PASS": 0, "INCONCLUSIVE": 2}[expected]],
        run,
    )
    data = audit.verify(store, receipts, checks, descriptor, edit_root=edited)
    report = audit.summary(data)
    report["transport"] = "local FIFO" if pipes else "native Unix socket"
    make_suites.write_json(work / "audit.json", report)
    audit.require(report["valid"], str(report["reasons"]))
    if not plain:
        audit.require("stored decision: MATCH" in data.gate.splitlines(), "gate mismatch")
        with (work / "run.log").open("a", encoding="utf-8") as log:
            log.write(data.gate)
        if scenario == "directional":
            audit.require(
                data.statistical_block and len(data.history) == 2, "expected round-2 BLOCK"
            )
    counts = count_a.count(data)
    make_suites.write_json(work / "count_a.json", counts)
    independent, verdict = count_b.verified_count(
        store, receipts, checks, descriptor, edited=edited
    )
    make_suites.write_json(work / "count_b.json", independent)
    audit.same(counts, independent, "independent counts")
    audit.same(verdict, expected, "blind verdict")
    pairs = first_requests(receipts)
    audit.same(2 * pairs, len(data.observations), "paired first requests")
    for side, script in (("baseline", baseline), ("candidate", candidate)):
        group = counts["arms"][side]["all"]
        audit.same(
            [group["trials"], group["passed"], group["by_termination"]],
            [pairs, pairs if script == "corrected" else 0, {"completed": pairs}],
            side,
        )
    unit = "pair" if pairs == 1 else "pairs"
    summary = f"{run}: {expected}, {pairs} {unit}, audit clean, counts equal, requests matched"
    if not plain:
        summary += f", round {len(data.history)}, gate MATCH"
    print(summary, flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cell", choices=("F1", "G1", "C0"))
    parser.add_argument("output", type=Path)
    parser.add_argument("--checks", required=True, type=Path)
    parser.add_argument("--pair", action="store_true")
    parser.add_argument("--pipes", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    audit.require(output.is_relative_to(ROOT), "write rehearsal evidence inside reply-0")
    scenarios = ["directional", "equal", "swapped"]
    if args.pair:
        audit.require(args.cell in ("C0", "F1"), "plain rehearsal must use C0 or F1")
        scenarios = ["control-pair" if args.cell == "C0" else "edited-pair"]
    for scenario in scenarios:
        rehearse(args.cell, scenario, output, args.checks.resolve(), args.pipes)


if __name__ == "__main__":
    main()
