"""Compute descriptive store counts according to the adjacent SPEC.md (stdlib only)."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import cast


class InputError(ValueError):
    """A required input is absent, malformed, or inconsistent."""


def object_value(value: object, location: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise InputError(f"{location}: expected a JSON object")
    return cast("dict[str, object]", value)


def required(record: dict[str, object], key: str, location: str) -> object:
    if key not in record:
        raise InputError(f"{location}: missing field {key!r}")
    return record[key]


def string_field(record: dict[str, object], key: str, location: str) -> str:
    value = required(record, key, location)
    if not isinstance(value, str):
        raise InputError(f"{location}: field {key!r} must be a string")
    return value


def parse_object(text: str, location: str) -> dict[str, object]:
    try:
        value: object = json.loads(text)
    except ValueError as exc:
        raise InputError(f"{location}: invalid JSON: {exc}") from exc
    return object_value(value, location)


def records(path: Path) -> Iterator[tuple[str, dict[str, object]]]:
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if line.strip():
                location = f"{path}:{line_number}"
                yield location, parse_object(line, location)


@dataclass
class Tally:
    trials: int = 0
    passed: int = 0

    def add(self, passed: bool) -> None:
        self.trials += 1
        self.passed += int(passed)


@dataclass
class ArmCounts:
    label: str
    trials: int = 0
    passed: int = 0
    failed: int = 0
    errored: int = 0
    ended_on_budget_or_time: int = 0
    by_termination: dict[str, int] = field(default_factory=dict)
    by_condition: dict[str, Tally] = field(default_factory=dict)
    by_task: dict[str, Tally] = field(default_factory=dict)
    first_call_not_lookup_order: int = 0
    never_called_lookup_order: int = 0
    empty_result_delivered: int = 0
    empty_result_delivered_ok: int = 0
    after_empty_result: dict[str, Tally] = field(
        default_factory=lambda: {"read_again": Tally(), "not_read_again": Tally()}
    )
    uninjected_tool_error: Tally = field(default_factory=Tally)

    def check(self, arm: str) -> None:
        totals = (
            self.passed + self.failed + self.errored,
            sum(t.trials for t in self.by_condition.values()),
            sum(t.trials for t in self.by_task.values()),
        )
        if any(total != self.trials for total in totals):
            raise InputError(f"arm {arm!r}: inconsistent trial totals")
        if sum(t.trials for t in self.after_empty_result.values()) != self.empty_result_delivered:
            raise InputError(f"arm {arm!r}: inconsistent empty-result partition")


@dataclass(frozen=True)
class ToolEvent:
    seq: int
    kind: str
    tool: str
    ok: bool | None
    injected_by: str | None


def read_events(path: Path, trial_ids: set[str]) -> dict[str, list[ToolEvent]]:
    events: dict[str, list[ToolEvent]] = {trial_id: [] for trial_id in trial_ids}
    sequences: dict[str, set[int]] = {trial_id: set() for trial_id in trial_ids}
    for location, record in records(path):
        trial_id = string_field(record, "trial_id", location)
        if trial_id not in events:
            raise InputError(f"{location}: unknown trial_id {trial_id!r}")
        seq = required(record, "seq", location)
        if not isinstance(seq, int) or isinstance(seq, bool) or seq < 0:
            raise InputError(f"{location}: seq must be a non-negative integer")
        if seq in sequences[trial_id]:
            raise InputError(f"{location}: duplicate seq {seq} for trial {trial_id!r}")
        sequences[trial_id].add(seq)
        kind = string_field(record, "kind", location)
        if kind not in {"tool_start", "tool_finish"}:
            continue
        payload = object_value(required(record, "payload", location), f"{location}.payload")
        tool = string_field(payload, "tool", f"{location}.payload")
        ok: bool | None = None
        injected_by: str | None = None
        if kind == "tool_finish":
            raw_ok = required(payload, "ok", f"{location}.payload")
            if not isinstance(raw_ok, bool):
                raise InputError(f"{location}: tool-finish ok must be a boolean")
            ok = raw_ok
            injection = required(payload, "injected_by", f"{location}.payload")
            if injection is not None and not isinstance(injection, str):
                raise InputError(f"{location}: injected_by must be a string or null")
            injected_by = injection
        events[trial_id].append(ToolEvent(seq, kind, tool, ok, injected_by))
    for trial_events in events.values():
        trial_events.sort(key=lambda event: event.seq)
    return events


def count_store(store: Path, audit_path: Path | None) -> dict[str, object]:
    manifest_path = store / "manifest.json"
    manifest = parse_object(manifest_path.read_text(encoding="utf-8"), str(manifest_path))
    trials: dict[str, tuple[str, dict[str, object]]] = {}
    for location, record in records(store / "trials.jsonl"):
        trial_id = string_field(record, "trial_id", location)
        if trial_id in trials:
            raise InputError(f"{location}: duplicate trial_id {trial_id!r}")
        trials[trial_id] = location, record
    events = read_events(store / "events.jsonl", set(trials))
    arms: dict[str, ArmCounts] = {}
    for trial_id, (location, trial) in trials.items():
        arm = string_field(trial, "arm", location)
        if arm not in arms:
            arm_location = f"{manifest_path}.{arm}"
            arm_spec = object_value(required(manifest, arm, str(manifest_path)), arm_location)
            arms[arm] = ArmCounts(string_field(arm_spec, "label", arm_location))
        counts = arms[arm]
        outcome = string_field(trial, "outcome", location)
        if outcome not in {"PASS", "FAIL", "ERROR"}:
            raise InputError(f"{location}: unknown outcome {outcome!r}")
        passed = outcome == "PASS"
        counts.trials += 1
        counts.passed += int(passed)
        counts.failed += int(outcome == "FAIL")
        counts.errored += int(outcome == "ERROR")
        termination = string_field(trial, "termination", location)
        counts.ended_on_budget_or_time += int(termination != "completed")
        counts.by_termination[termination] = counts.by_termination.get(termination, 0) + 1
        for key, grouped in (("condition_id", counts.by_condition), ("task_id", counts.by_task)):
            group = string_field(trial, key, location)
            grouped.setdefault(group, Tally()).add(passed)

        trial_events = events[trial_id]
        starts = [event for event in trial_events if event.kind == "tool_start"]
        counts.first_call_not_lookup_order += int(bool(starts) and starts[0].tool != "lookup_order")
        lookup_starts = [event.seq for event in starts if event.tool == "lookup_order"]
        counts.never_called_lookup_order += int(not lookup_starts)
        empty_finishes = [
            event.seq
            for event in trial_events
            if event.kind == "tool_finish"
            and event.tool == "lookup_order"
            and event.injected_by == "empty_result"
        ]
        if empty_finishes:
            counts.empty_result_delivered += 1
            read_again = any(seq > empty_finishes[0] for seq in lookup_starts)
            counts.after_empty_result["read_again" if read_again else "not_read_again"].add(passed)
        counts.empty_result_delivered_ok += int(
            any(
                event.kind == "tool_finish"
                and event.tool == "lookup_order"
                and event.injected_by == "empty_result"
                and event.ok is True
                for event in trial_events
            )
        )
        if any(
            event.kind == "tool_finish" and event.ok is False and event.injected_by is None
            for event in trial_events
        ):
            counts.uninjected_tool_error.add(passed)

    for arm, counts in arms.items():
        counts.check(arm)
    audit: dict[str, int] | None = None
    if audit_path is not None:
        lines = 0
        call_ids: set[str] = set()
        for location, record in records(audit_path):
            lines += 1
            call_ids.add(string_field(record, "tool_call_id", location))
        audit = {"lines": lines, "distinct_tool_call_ids": len(call_ids)}
    return {
        "store": store.name,
        "arms": {arm: asdict(counts) for arm, counts in arms.items()},
        "audit": audit,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("store_dir", type=Path)
    parser.add_argument("--audit", type=Path)
    args = parser.parse_args()
    try:
        result = count_store(cast("Path", args.store_dir), cast("Path | None", args.audit))
    except (OSError, UnicodeError, InputError) as exc:
        print(f"count_a.py: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
