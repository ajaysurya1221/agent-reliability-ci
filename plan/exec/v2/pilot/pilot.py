"""Small measurement pilot: two local Ollama models on the LangChain quickstart example.

Drives real ARCI trials against a COPY of the quickstart example
(plan/exec/v2/pilot/quickstart-copy, budgets raised, everything else identical).
Writes one row per session to results.json and prints a summary table.

Run with the pinned pilot venv only:
  /Users/ajay/Developer/.arci-worktrees/v2-pilot-venv/bin/python plan/exec/v2/pilot/pilot.py [--smoke] [--tasks N]
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Literal

os.environ["LANGSMITH_TRACING"] = "false"
os.environ["LANGSMITH_TRACING_V2"] = "false"

PILOT_DIR = Path(__file__).resolve().parent
QUICKSTART_DIR = PILOT_DIR / "quickstart-copy"
ARCI_YAML = QUICKSTART_DIR / "arci.yaml"

from arci import descriptor  # noqa: E402
from arci.runner import run_trial  # noqa: E402
from arci.schema import Event, Outcome, TrialSpec  # noqa: E402
from arci.suite_schedule import build_suite_round  # noqa: E402
from arci.suite_schema import SuiteManifest  # noqa: E402

MODELS = ["qwen3.5:4b-mlx-ctx32k", "gemma4:12b-mlx-ctx32k"]
Arm = Literal["baseline", "candidate"]

# (condition_id, arm, session-arm label)
SESSION_GROUPS: tuple[tuple[str, Arm, str], ...] = (
    ("clean", "baseline", "clean"),
    ("tool_timeout", "baseline", "tool_timeout_baseline_settings"),
    ("tool_timeout", "candidate", "tool_timeout_candidate_settings"),
)


def load_manifest() -> SuiteManifest:
    manifest = descriptor.compile_run_descriptor(str(ARCI_YAML))
    assert isinstance(manifest, SuiteManifest), "expected a suite descriptor"
    return manifest


def select_specs(
    manifest: SuiteManifest, condition_id: str, arm: Arm, task_ids: set[str]
) -> list[TrialSpec]:
    round1 = build_suite_round(manifest, 1)
    return [
        s
        for s in round1
        if s.condition.condition_id == condition_id and s.arm == arm and s.task_id in task_ids
    ]


_CONTRACT_CACHE: Any = None


def _contract() -> Any:
    global _CONTRACT_CACHE
    if _CONTRACT_CACHE is None:
        _CONTRACT_CACHE = load_manifest().contract
    return _CONTRACT_CACHE


def row_for(model: str, arm_label: str, condition_id: str, spec: TrialSpec) -> dict[str, Any]:
    events: list[Event] = []
    start = time.monotonic()
    trial = run_trial(
        spec, events.append, _contract(), extra_pythonpath=(str(QUICKSTART_DIR),)
    )
    wall = time.monotonic() - start
    return {
        "model": model,
        "settings_arm": arm_label,
        "condition": condition_id,
        "task_id": spec.task_id,
        "outcome": trial.outcome.value,
        "termination": trial.termination.value,
        "wall_seconds": wall,
        "tool_calls": trial.usage.tool_calls,
        "model_steps": trial.usage.model_steps,
        "failure_detail": trial.failure_detail,
    }


def event_summary(trial: Any, events: list[Event]) -> str:
    kinds = [e.kind for e in events]
    tool_starts = [e for e in events if e.kind == "tool_start"]
    tool_finishes = [e for e in events if e.kind == "tool_finish"]
    agent_results = [e for e in events if e.kind == "agent_result"]
    lines = [
        f"outcome={trial.outcome.value} termination={trial.termination.value} "
        f"failure_detail={trial.failure_detail!r}",
        f"event kinds in order: {kinds}",
    ]
    for e in tool_starts:
        lines.append(f"  tool_start: {e.payload}")
    for e in tool_finishes:
        lines.append(f"  tool_finish: {e.payload}")
    for e in agent_results:
        lines.append(f"  agent_result: {e.payload}")
    return "\n".join(lines)


def smoke_test(manifest: SuiteManifest, task_ids: set[str]) -> bool:
    ok = True
    for model in MODELS:
        os.environ["ARCI_QUICKSTART_BASELINE"] = f"ollama:{model}"
        os.environ["ARCI_QUICKSTART_CANDIDATE"] = f"ollama:{model}"
        specs = select_specs(manifest, "clean", "baseline", task_ids)[:2]
        print(f"\n=== SMOKE {model}: {len(specs)} session(s) ===")
        for spec in specs:
            events: list[Event] = []
            start = time.monotonic()
            trial = run_trial(
                spec, events.append, manifest.contract, extra_pythonpath=(str(QUICKSTART_DIR),)
            )
            wall = time.monotonic() - start
            print(f"-- task {spec.task_id} wall={wall:.1f}s --")
            print(event_summary(trial, events))
            tool_calls = sum(1 for e in events if e.kind == "tool_start")
            if tool_calls == 0:
                ok = False
                print(f"!!! {model} produced ZERO tool calls on task {spec.task_id}")
    return ok


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true", help="run only the 2-session smoke test")
    parser.add_argument("--tasks", type=int, default=24, help="number of leading tasks to use")
    parser.add_argument(
        "--out", default=str(PILOT_DIR / "results.json"), help="path to write results.json"
    )
    args = parser.parse_args()

    manifest = load_manifest()
    all_task_ids = sorted({t.task_id for t in manifest.tasks})
    task_ids = set(all_task_ids[: args.tasks])
    print(f"Using {len(task_ids)} of {len(all_task_ids)} tasks: {sorted(task_ids)}")

    if args.smoke:
        ok = smoke_test(manifest, task_ids)
        print(f"\nSMOKE RESULT: {'OK, tool calls observed' if ok else 'FAILED'}")
        sys.exit(0 if ok else 1)

    rows: list[dict[str, Any]] = []
    out_path = Path(args.out)
    for model in MODELS:
        os.environ["ARCI_QUICKSTART_BASELINE"] = f"ollama:{model}"
        os.environ["ARCI_QUICKSTART_CANDIDATE"] = f"ollama:{model}"
        for condition_id, arm, arm_label in SESSION_GROUPS:
            specs = select_specs(manifest, condition_id, arm, task_ids)
            print(f"\n=== {model} / {arm_label} / {condition_id}: {len(specs)} sessions ===")
            for spec in specs:
                row = row_for(model, arm_label, condition_id, spec)
                rows.append(row)
                print(
                    f"  {spec.task_id}: outcome={row['outcome']} term={row['termination']} "
                    f"wall={row['wall_seconds']:.1f}s tools={row['tool_calls']} "
                    f"steps={row['model_steps']}"
                )
                out_path.write_text(json.dumps(rows, indent=2))

    print_summary(rows)
    out_path.write_text(json.dumps(rows, indent=2))
    print(f"\nWrote {len(rows)} rows to {out_path}")


def print_summary(rows: list[dict[str, Any]]) -> None:
    print("\n=== SUMMARY ===")
    header = (
        f"{'model':22} {'arm':30} {'cond':14} {'n':3} {'pass%':6} "
        f"{'p50s':6} {'p90s':6} {'tools':6} {'steps':6} {'end(completed/budget/crash/err)'}"
    )
    print(header)
    print("-" * len(header))
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for r in rows:
        groups.setdefault((r["model"], r["settings_arm"], r["condition"]), []).append(r)
    for key in sorted(groups):
        model, arm, cond = key
        group = groups[key]
        n = len(group)
        passed = sum(1 for r in group if r["outcome"] == "PASS")
        walls = [r["wall_seconds"] for r in group]
        tools = [r["tool_calls"] for r in group]
        steps = [r["model_steps"] for r in group]
        p50 = statistics.median(walls) if walls else float("nan")
        p90 = (
            statistics.quantiles(walls, n=10)[8]
            if len(walls) >= 2
            else (walls[0] if walls else float("nan"))
        )
        term_counts: dict[str, int] = {}
        for r in group:
            term_counts[r["termination"]] = term_counts.get(r["termination"], 0) + 1
        term_str = ", ".join(f"{k}:{v}" for k, v in sorted(term_counts.items()))
        print(
            f"{model:22} {arm:30} {cond:14} {n:3} {100 * passed / n:5.0f}% "
            f"{p50:6.1f} {p90:6.1f} {statistics.mean(tools):6.1f} {statistics.mean(steps):6.1f} "
            f"{term_str}"
        )


if __name__ == "__main__":
    main()
