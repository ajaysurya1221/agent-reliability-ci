"""Reconstruct Reply-0 counts from verified trials, keeping every scheduled pair."""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness import audit


def counters() -> dict[str, Any]:
    return {
        "trials": 0,
        "passed": 0,
        "failed": 0,
        "errored": 0,
        "by_termination": {},
        "wall_timeouts": 0,
        "call_budget": 0,
        "step_exhausted": 0,
        "same_tool": {k: {"trials": 0, "passed": 0} for k in ("yes", "no")},
        "corrected_same_tool": {k: {"trials": 0, "passed": 0} for k in ("yes", "no")},
        "unscripted_exposed": 0,
        "unscripted_trials": 0,
    }


def tally(count: dict[str, Any], observation: audit.Observation, phase: str) -> None:
    t = observation.trial
    count["trials"] += 1
    count[{"PASS": "passed", "FAIL": "failed", "ERROR": "errored"}[t.outcome]] += 1
    terms = count["by_termination"]
    terms[t.termination] = terms.get(t.termination, 0) + 1
    count["wall_timeouts"] += t.termination == "timeout"
    count["call_budget"] += t.termination == "budget"
    count["step_exhausted"] += observation.exhausted and t.termination == "completed"
    if phase == "unscripted":
        count["unscripted_trials"] += 1
        count["unscripted_exposed"] += observation.exposure
    else:
        for name, yes in (
            ("same_tool", observation.retry),
            ("corrected_same_tool", observation.corrected),
        ):
            group = count[name]["yes" if yes else "no"]
            group["trials"] += 1
            group["passed"] += t.outcome == "PASS"


def count(data: audit.Evidence) -> dict[str, Any]:
    arms: dict[str, Any] = {}
    pairs: dict[str, dict[str, str]] = defaultdict(dict)
    for o in data.observations:
        t = o.trial
        arm = arms.setdefault(t.arm, {"label": t.variant, "all": counters(), "by_task": {}})
        tally(arm["all"], o, data.phase)
        tally(arm["by_task"].setdefault(t.task_id, counters()), o, data.phase)
        pairs[t.pair_id][t.arm] = t.outcome.value
    counts = dict.fromkeys(("minus", "zero", "plus", "errored"), 0)
    for index, (pair_id, outcomes) in enumerate(sorted(pairs.items()), 1):
        a, b = outcomes["baseline"], outcomes["candidate"]
        key = (
            "errored"
            if "ERROR" in (a, b)
            else ("minus", "zero", "plus")[1 + (b == "PASS") - (a == "PASS")]
        )
        counts[key] += 1
        if data.history:
            rd = int(pair_id.split(":")[0][1:])
            look = data.history[rd - 1]
            if index == look["pairs"]:
                audit.same(counts, look["counts"], f"pair counts after round {rd}")
    return {
        "experiment_id": data.experiment,
        "model": data.model,
        "cell": data.cell,
        "phase": data.phase,
        "pairs": counts,
        "arms": arms,
    }


def verified_count(args: Any) -> dict[str, Any]:
    """Count A tallies only after replay, receiver and contract verification succeeds."""
    data = audit.verify(
        args.store,
        args.receipts,
        args.check_dir,
        args.descriptor,
        args.descriptor_sha256,
        args.edited,
    )
    return count(data)


def main() -> int:
    args = audit.arguments()
    try:
        print(audit.encoded(verified_count(args)))
    except (ValueError, OSError, TypeError, KeyError, IndexError) as exc:
        print(f"invalid count: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
