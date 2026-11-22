"""Compute descriptive store counts according to the adjacent SPEC.md (stdlib only)."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, cast


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
    scripted_opening_recorded: int = 0
    empty_result_delivered_ok: int = 0
    model_step_after_opening: int = 0
    after_empty_result: dict[str, Tally] = field(
        default_factory=lambda: {"read_again": Tally(), "not_read_again": Tally()}
    )

    def check(self, arm: str) -> None:
        totals = (
            self.passed + self.failed + self.errored,
            sum(t.trials for t in self.by_condition.values()),
            sum(t.trials for t in self.by_task.values()),
        )
        if any(total != self.trials for total in totals):
            raise InputError(f"arm {arm!r}: inconsistent trial totals")
        if (
            sum(t.trials for t in self.after_empty_result.values())
            != self.empty_result_delivered_ok
        ):
            raise InputError(f"arm {arm!r}: inconsistent empty-result partition")


def classify(
    events: list[dict[str, Any]],
    recording: list[dict[str, Any]],
    order_id: str,
    counts: ArmCounts,
    passed: bool,
) -> None:
    timeline = [e for e in events if e["kind"] in {"model_step", "tool_start", "tool_finish"}]
    kinds = [e["kind"] for e in timeline]
    payloads = [e["payload"] for e in timeline]
    opening = False
    if kinds[:4] == ["tool_start", "tool_finish", "tool_start", "tool_finish"]:
        stock, error, lookup, reply = payloads[:4]
        opening = (
            stock["tool"] == error["tool"] == "check_stock"
            and stock["occurrence"] == 0
            and stock["arguments"] == {"sku": order_id}
            and stock["call_id"] == error["call_id"]
            and error["ok"] is False
            and error["injected_by"] is None
            and error["error_kind"] == "error"
            and bool(recording)
            and recording[0]["result"]["error_detail"] == "ValueError: unknown SKU"
            and lookup["tool"] == reply["tool"] == "lookup_order"
            and lookup["occurrence"] == 0
            and lookup["arguments"] == {"order_id": order_id}
            and lookup["call_id"] == reply["call_id"]
        )
    counts.scripted_opening_recorded += int(opening)

    first_lookup_id = None
    delivery_index = None
    for i, (kind, payload) in enumerate(zip(kinds, payloads, strict=True)):
        if (
            kind == "tool_start"
            and payload["tool"] == "lookup_order"
            and payload["occurrence"] == 0
            and payload["arguments"] == {"order_id": order_id}
        ):
            first_lookup_id = payload["call_id"]
        if (
            kind == "tool_finish"
            and first_lookup_id is not None
            and payload["call_id"] == first_lookup_id
            and payload["tool"] == "lookup_order"
            and payload["injected_by"] == "empty_result"
            and payload["ok"] is True
            and payload["value"] is None
        ):
            delivery_index = i
            break
    if delivery_index is None:
        return
    counts.empty_result_delivered_ok += 1
    later = timeline[delivery_index + 1 :]
    step = next((i for i, event in enumerate(later) if event["kind"] == "model_step"), None)
    counts.model_step_after_opening += int(opening and step == 0)
    retried = step is not None and any(
        e["kind"] == "tool_start" and e["payload"]["tool"] == "lookup_order"
        for e in later[step + 1 :]
    )
    counts.after_empty_result["read_again" if retried else "not_read_again"].add(passed)


def count_store(store: Path, audit_path: Path | None) -> dict[str, object]:
    manifest_path = store / "manifest.json"
    manifest = parse_object(manifest_path.read_text(encoding="utf-8"), str(manifest_path))
    trials: dict[str, tuple[str, dict[str, object]]] = {}
    for location, record in records(store / "trials.jsonl"):
        trial_id = string_field(record, "trial_id", location)
        if trial_id in trials:
            raise InputError(f"{location}: duplicate trial_id {trial_id!r}")
        trials[trial_id] = location, record
    events: dict[str, list[dict[str, Any]]] = {key: [] for key in trials}
    for location, event in records(store / "events.jsonl"):
        trial_id = string_field(event, "trial_id", location)
        if trial_id not in events:
            raise InputError(f"{location}: unknown trial id {trial_id}")
        events[trial_id].append(event)
    tasks: dict[str, str] = {
        item["task_id"]: item["task"]["order_id"] for item in cast(list[Any], manifest["tasks"])
    }
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
        if trial_events != trial["events"] or any(
            event["seq"] != i for i, event in enumerate(trial_events)
        ):
            raise InputError(f"event stream differs from ordered trial {trial_id}")
        classify(
            trial_events,
            cast(list[Any], trial["recording"]),
            tasks[string_field(trial, "task_id", location)],
            counts,
            passed,
        )

    for arm, counts in arms.items():
        counts.check(arm)
    audit: dict[str, object] | None = None
    if audit_path is not None:
        lines = 0
        call_ids: set[str] = set()
        by_arm = {"baseline": 0, "candidate": 0}
        arm_ids: dict[str, set[str]] = {arm: set() for arm in by_arm}
        for location, record in records(audit_path):
            arm = string_field(record, "arm", location)
            if arm not in by_arm:
                raise InputError(f"{location}: unknown audit arm {arm!r}")
            call_id = string_field(record, "tool_call_id", location)
            lines += 1
            call_ids.add(call_id)
            by_arm[arm] += 1
            arm_ids[arm].add(call_id)
        audit = {
            "lines": lines,
            "distinct_tool_call_ids": len(call_ids),
            "by_arm": {
                arm: {"lines": count, "distinct_tool_call_ids": len(arm_ids[arm])}
                for arm, count in by_arm.items()
            },
        }
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
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        print(f"count_a.py: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
