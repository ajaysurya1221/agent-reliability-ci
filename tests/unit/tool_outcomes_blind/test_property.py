"""Property-style check: ~200 random fixtures against a reference implementation.

Reference implementation is written directly from R1-tool-outcomes.md's "Contract"
section, independently of src/arci/report.py.

One deliberate reading of an ambiguous point: "events whose `tool` is not a string are
ignored" is treated as ignoring the event for EVERY purpose, including the arm-level
"any tool" uninjected-failure aggregate, not only for building the per-tool rows. See the
final report for this ambiguity.
"""

from __future__ import annotations

import random
from typing import Literal

from pydantic import JsonValue

from arci.report import tool_outcomes
from arci.schema import Event, Outcome, Termination, TrialEnvelope

TOOLS: list[JsonValue] = ["alpha", "beta", "gamma"]
MALFORMED_TOOLS: list[JsonValue] = [7, [], None, {}]
ARMS: list[Literal["baseline", "candidate"]] = ["baseline", "candidate"]
OUTCOMES = [Outcome.PASS, Outcome.FAIL, Outcome.ERROR]
OK_VALUES: list[JsonValue] = [True, False, 0, 1, None]
INJECTED_VALUES: list[JsonValue] = [None, "", "tool_timeout", "empty_result", 7, []]
KINDS = ["tool_start", "tool_finish", "model_step", "trial_start", "agent_result"]


def _random_trial(rng: random.Random, idx: int) -> TrialEnvelope:
    arm = rng.choice(ARMS)
    outcome = rng.choice(OUTCOMES)
    n_events = rng.randint(0, 5)
    events: list[Event] = []
    for seq in range(n_events):
        kind = rng.choice(KINDS)
        payload: dict[str, JsonValue] = {}
        roll = rng.random()
        if roll < 0.8:
            payload["tool"] = rng.choice(TOOLS)
        elif roll < 0.95:
            payload["tool"] = rng.choice(MALFORMED_TOOLS)
        # else: tool key omitted entirely
        if kind == "tool_finish":
            payload["ok"] = rng.choice(OK_VALUES)
            if rng.random() < 0.85:
                payload["injected_by"] = rng.choice(INJECTED_VALUES)
        events.append(Event(trial_id=f"p{idx}", seq=seq, kind=kind, payload=payload))  # type: ignore[arg-type]
    return TrialEnvelope.create(
        spec_sha256="0" * 64,
        experiment_id="prop",
        trial_id=f"p{idx}",
        pair_id=f"p{idx}",
        arm=arm,
        variant="v",
        task_id="task",
        condition_id="cond",
        seed=idx,
        outcome=outcome,
        termination=(
            Termination.COMPLETED if outcome is not Outcome.ERROR else Termination.HARNESS_ERROR
        ),
        events=tuple(events),
    )


def _reference(trials: list[TrialEnvelope]) -> dict[str, object]:
    arms = {
        a: {
            "trials": 0,
            "uninjected_failure_trials": 0,
            "uninjected_then_passed": 0,
            "uninjected_then_not_passed": 0,
        }
        for a in ARMS
    }
    tool_stats: dict[str, dict[str, dict[str, object]]] = {}

    for t in trials:
        if t.arm not in arms:
            continue
        arms[t.arm]["trials"] += 1  # type: ignore[operator]
        trial_failed = False
        for e in t.events:
            if e.kind not in ("tool_start", "tool_finish"):
                continue
            tool = e.payload.get("tool")
            if not isinstance(tool, str):
                continue
            row = tool_stats.setdefault(
                tool,
                {
                    a: {
                        "trials_started": set(),
                        "starts": 0,
                        "uninjected_failures": 0,
                        "uninjected_failure_trials": set(),
                    }
                    for a in ARMS
                },
            )
            if e.kind == "tool_start":
                row[t.arm]["starts"] += 1  # type: ignore[operator]
                row[t.arm]["trials_started"].add(t.trial_id)  # type: ignore[attr-defined]
            else:  # tool_finish
                ok = e.payload.get("ok")
                injected_by = e.payload.get("injected_by", None)
                if ok is False and (injected_by is None or injected_by == ""):
                    row[t.arm]["uninjected_failures"] += 1  # type: ignore[operator]
                    row[t.arm]["uninjected_failure_trials"].add(t.trial_id)  # type: ignore[attr-defined]
                    trial_failed = True
        if trial_failed:
            arms[t.arm]["uninjected_failure_trials"] += 1  # type: ignore[operator]
            if t.outcome is Outcome.PASS:
                arms[t.arm]["uninjected_then_passed"] += 1  # type: ignore[operator]
            else:
                arms[t.arm]["uninjected_then_not_passed"] += 1  # type: ignore[operator]

    tools_out = []
    for name in sorted(tool_stats):
        total_starts = sum(tool_stats[name][a]["starts"] for a in ARMS)  # type: ignore[misc]
        total_failures = sum(tool_stats[name][a]["uninjected_failures"] for a in ARMS)  # type: ignore[misc]
        if total_starts == 0 and total_failures == 0:
            continue
        for a in ARMS:
            r = tool_stats[name][a]
            n = arms[a]["trials"]
            started = len(r["trials_started"])  # type: ignore[arg-type]
            tools_out.append(
                {
                    "arm": a,
                    "tool": name,
                    "trials": n,
                    "trials_started": started,
                    "trials_not_started": n - started,
                    "starts": r["starts"],
                    "uninjected_failures": r["uninjected_failures"],
                    "uninjected_failure_trials": len(r["uninjected_failure_trials"]),  # type: ignore[arg-type]
                }
            )

    return {
        "arms": [{"arm": a, **arms[a]} for a in ARMS],
        "tools": tools_out,
    }


def test_random_fixtures_match_reference_and_invariants() -> None:
    rng = random.Random(0)
    for case in range(200):
        n_trials = rng.randint(0, 6)
        trials = [_random_trial(rng, case * 10 + i) for i in range(n_trials)]

        actual = tool_outcomes(trials)
        expected = _reference(trials)
        assert actual == expected, f"case {case}: {actual} != {expected}"

        for arm_row in actual["arms"]:
            assert (
                arm_row["uninjected_then_passed"] + arm_row["uninjected_then_not_passed"]
                == arm_row["uninjected_failure_trials"]
            )

        arm_failures = {row["arm"]: row["uninjected_failure_trials"] for row in actual["arms"]}
        for tool_row in actual["tools"]:
            assert tool_row["trials_started"] + tool_row["trials_not_started"] == tool_row["trials"]
            assert tool_row["uninjected_failure_trials"] <= arm_failures[tool_row["arm"]]

        total_starts_actual = sum(row["starts"] for row in actual["tools"])
        total_starts_raw = sum(
            1
            for t in trials
            for e in t.events
            if e.kind == "tool_start" and isinstance(e.payload.get("tool"), str)
        )
        assert total_starts_actual == total_starts_raw
