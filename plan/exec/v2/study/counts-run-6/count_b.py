#!/usr/bin/env python3
"""Descriptive counts for a sealed order-desk suite store.

See SPEC.md in this directory for the definitions this script implements.
Standard library only. Reads only manifest.json, trials.jsonl, events.jsonl
inside STORE_DIR, and, if given, an audit file. Never guesses: any missing
file or required field is a clear error on stderr with exit status 2.

Usage:
    python count_b.py STORE_DIR [--audit FILE]
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Iterator
from typing import Any, NoReturn


def fail(msg: str) -> NoReturn:
    print(f"count_b.py: {msg}", file=sys.stderr)
    sys.exit(2)


def need(d: Any, key: str, where: str) -> Any:
    if not isinstance(d, dict) or key not in d:
        fail(f"missing required field {key!r} in {where}")
    return d[key]


def read_json_file(path: str, what: str) -> Any:
    if not os.path.isfile(path):
        fail(f"missing {what}: {path}")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except OSError as e:
        fail(f"cannot read {what} ({path}): {e}")
    except json.JSONDecodeError as e:
        fail(f"malformed JSON in {what} ({path}): {e}")


def iter_jsonl(path: str, what: str) -> Iterator[Any]:
    if not os.path.isfile(path):
        fail(f"missing {what}: {path}")
    try:
        with open(path, encoding="utf-8") as f:
            for lineno, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as e:
                    fail(f"malformed JSON in {what} ({path}) at line {lineno}: {e}")
    except OSError as e:
        fail(f"cannot open {what} ({path}): {e}")


def parse_args(argv: list[str]) -> tuple[str, str | None]:
    positional: list[str] = []
    audit_path: str | None = None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--audit":
            i += 1
            if i >= len(argv):
                fail("--audit requires a FILE argument")
            audit_path = argv[i]
        else:
            positional.append(a)
        i += 1
    if len(positional) != 1:
        fail("usage: count_b.py STORE_DIR [--audit FILE]")
    return positional[0], audit_path


def count_exchanges(
    trial: dict[str, Any], order_id: str, arm: dict[str, Any], passed: bool
) -> None:
    events = trial["events"]
    observable = [e for e in events if e["kind"] in ("tool_start", "tool_finish", "model_step")]
    starts = {e["payload"]["call_id"]: e for e in observable if e["kind"] == "tool_start"}
    finishes = {e["payload"]["call_id"]: e for e in observable if e["kind"] == "tool_finish"}
    opening = False
    if len(observable) >= 4 and [e["kind"] for e in observable[:4]] == [
        "tool_start",
        "tool_finish",
        "tool_start",
        "tool_finish",
    ]:
        first, second = observable[0]["payload"], observable[2]["payload"]
        error, reply = observable[1]["payload"], observable[3]["payload"]
        opening = (
            (first["tool"], first["arguments"], first["occurrence"])
            == ("check_stock", {"sku": order_id}, 0)
            and (second["tool"], second["arguments"], second["occurrence"])
            == ("lookup_order", {"order_id": order_id}, 0)
            and (error["call_id"], error["tool"], error["error_kind"], error["injected_by"])
            == (first["call_id"], "check_stock", "error", None)
            and error["ok"] is False
            and bool(trial["recording"])
            and trial["recording"][0]["result"]["error_detail"] == "ValueError: unknown SKU"
            and (reply["call_id"], reply["tool"]) == (second["call_id"], "lookup_order")
        )
    if opening:
        arm["scripted_opening_recorded"] += 1
    for call_id, start in starts.items():
        p = start["payload"]
        if (p["tool"], p["arguments"], p["occurrence"]) != (
            "lookup_order",
            {"order_id": order_id},
            0,
        ):
            continue
        finish = finishes.get(call_id)
        if finish is None or finish["seq"] <= start["seq"]:
            continue
        q = finish["payload"]
        if (q["tool"], q["injected_by"], q["value"]) != ("lookup_order", "empty_result", None) or q[
            "ok"
        ] is not True:
            continue
        arm["empty_result_delivered_ok"] += 1
        steps = [
            e["seq"] for e in observable if e["kind"] == "model_step" and e["seq"] > finish["seq"]
        ]
        if opening and len(observable) > 4 and observable[4]["kind"] == "model_step":
            arm["model_step_after_opening"] += 1
        again = bool(steps) and any(
            e["payload"]["tool"] == "lookup_order" and e["seq"] > min(steps)
            for e in starts.values()
        )
        group = arm["after_empty_result"]["read_again" if again else "not_read_again"]
        group["trials"] += 1
        group["passed"] += int(passed)
        return


def main() -> None:
    store_dir, audit_path = parse_args(sys.argv[1:])

    if not os.path.isdir(store_dir):
        fail(f"not a directory: {store_dir}")

    manifest_path = os.path.join(store_dir, "manifest.json")
    trials_path = os.path.join(store_dir, "trials.jsonl")
    events_path = os.path.join(store_dir, "events.jsonl")

    manifest = read_json_file(manifest_path, "manifest.json")
    if not isinstance(manifest, dict):
        fail(f"manifest.json ({manifest_path}) is not a JSON object")

    def arm_label(arm: str) -> str:
        entry = manifest.get(arm)
        if not isinstance(entry, dict) or "label" not in entry:
            fail(f"manifest.json has no label for arm {arm!r}")
        return entry["label"]

    tasks = {t["task_id"]: t["task"]["order_id"] for t in manifest["tasks"]}
    by_trial: dict[str, list[dict[str, Any]]] = {}
    for event in iter_jsonl(events_path, "events.jsonl"):
        by_trial.setdefault(event["trial_id"], []).append(event)
    result_arms: dict[str, Any] = {}
    seen: set[str] = set()
    for trial in iter_jsonl(trials_path, "trials.jsonl"):
        trial_id = trial["trial_id"]
        if trial_id in seen:
            fail(f"duplicate trial {trial_id}")
        seen.add(trial_id)
        events = trial["events"]
        if by_trial.pop(trial_id, []) != events or [e["seq"] for e in events] != list(
            range(len(events))
        ):
            fail(f"event stream differs from ordered trial {trial_id}")
        key = trial["arm"]
        if key not in result_arms:
            result_arms[key] = {
                "label": arm_label(key),
                "trials": 0,
                "passed": 0,
                "failed": 0,
                "errored": 0,
                "ended_on_budget_or_time": 0,
                "by_condition": {},
                "by_task": {},
                "by_termination": {},
                "scripted_opening_recorded": 0,
                "empty_result_delivered_ok": 0,
                "model_step_after_opening": 0,
                "after_empty_result": {
                    k: {"trials": 0, "passed": 0} for k in ("read_again", "not_read_again")
                },
            }
        arm = result_arms[key]
        outcome, termination = trial["outcome"], trial["termination"]
        arm["trials"] += 1
        arm[{"PASS": "passed", "FAIL": "failed", "ERROR": "errored"}[outcome]] += 1
        passed = outcome == "PASS"
        arm["ended_on_budget_or_time"] += int(termination != "completed")
        terms = arm["by_termination"]
        terms[termination] = terms.get(termination, 0) + 1
        for table, value in (
            ("by_condition", trial["condition_id"]),
            ("by_task", trial["task_id"]),
        ):
            group = arm[table].setdefault(value, {"trials": 0, "passed": 0})
            group["trials"] += 1
            group["passed"] += int(passed)
        count_exchanges(trial, tasks[trial["task_id"]], arm, passed)
    if by_trial:
        fail("events for unknown trial")

    # --- optional audit file --------------------------------------------
    audit: dict[str, object] | None = None
    if audit_path is not None:
        if not os.path.isfile(audit_path):
            fail(f"missing audit file: {audit_path}")
        deliveries: dict[str, list[str]] = {"baseline": [], "candidate": []}
        for record in iter_jsonl(audit_path, "audit file"):
            arm = need(record, "arm", audit_path)
            call_id = need(record, "tool_call_id", audit_path)
            if arm not in ("baseline", "candidate") or not isinstance(call_id, str):
                fail(f"invalid arm or tool_call_id in audit file ({audit_path})")
            deliveries[arm].append(call_id)
        all_ids = deliveries["baseline"] + deliveries["candidate"]
        audit = {
            "lines": len(all_ids),
            "distinct_tool_call_ids": len(set(all_ids)),
            "by_arm": {
                arm: {"lines": len(ids), "distinct_tool_call_ids": len(set(ids))}
                for arm, ids in deliveries.items()
            },
        }

    output = {
        "store": os.path.basename(os.path.normpath(store_dir)),
        "arms": result_arms,
        "audit": audit,
    }
    print(json.dumps(output, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, TypeError, KeyError, IndexError, OSError) as exc:
        fail(str(exc))
