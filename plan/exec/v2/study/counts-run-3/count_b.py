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

    # --- pass 1: trials.jsonl -> per-trial metadata, keyed by trial_id -----
    trials: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for rec in iter_jsonl(trials_path, "trials.jsonl"):
        trial_id = need(rec, "trial_id", "a trials.jsonl record")
        where = f"trial {trial_id!r} in trials.jsonl"
        arm = need(rec, "arm", where)
        task_id = need(rec, "task_id", where)
        condition_id = need(rec, "condition_id", where)
        outcome = need(rec, "outcome", where)
        termination = need(rec, "termination", where)
        if trial_id in trials:
            fail(f"duplicate trial_id in trials.jsonl: {trial_id!r}")
        trials[trial_id] = {
            "arm": arm,
            "task_id": task_id,
            "condition_id": condition_id,
            "outcome": outcome,
            "termination": termination,
            "first_tool_start": None,  # (seq, tool)
            "has_lookup_start": False,
            "empty_result_min_seq": None,
            "has_empty_result_ok": False,
            "has_later_lookup_start": False,
            "uninjected_error": False,
        }
        order.append(trial_id)

    if not trials:
        fail(f"trials.jsonl ({trials_path}) has no trial records")

    # --- pass 2: events.jsonl -> tool-start/tool-finish facts per trial ----
    # lookup_order tool-start seqs are buffered per trial because events for
    # a trial are not guaranteed contiguous in the file, and we only know
    # which empty-result tool-finish seq to compare against once we have
    # seen all events for that trial.
    lookup_start_seqs: dict[str, list[int]] = {}
    for ev in iter_jsonl(events_path, "events.jsonl"):
        trial_id = need(ev, "trial_id", "an events.jsonl record")
        if trial_id not in trials:
            fail(f"events.jsonl references unknown trial_id: {trial_id!r}")
        where = f"event for trial {trial_id!r} in events.jsonl"
        seq = need(ev, "seq", where)
        kind = need(ev, "kind", where)
        t = trials[trial_id]

        if kind == "tool_start":
            payload = need(ev, "payload", where)
            tool = need(payload, "tool", f"tool_start {where}")
            if t["first_tool_start"] is None or seq < t["first_tool_start"][0]:
                t["first_tool_start"] = (seq, tool)
            if tool == "lookup_order":
                t["has_lookup_start"] = True
                lookup_start_seqs.setdefault(trial_id, []).append(seq)
        elif kind == "tool_finish":
            payload = need(ev, "payload", where)
            tool = need(payload, "tool", f"tool_finish {where}")
            ok = need(payload, "ok", f"tool_finish {where}")
            injected_by = payload.get("injected_by")
            if tool == "lookup_order" and injected_by == "empty_result":
                if t["empty_result_min_seq"] is None or seq < t["empty_result_min_seq"]:
                    t["empty_result_min_seq"] = seq
                if ok is True:
                    t["has_empty_result_ok"] = True
            if ok is False and injected_by is None:
                t["uninjected_error"] = True
        # other kinds (trial_start, trial_end, model_step, agent_result)
        # carry no fact this spec needs.

    for trial_id, seqs in lookup_start_seqs.items():
        t = trials[trial_id]
        min_seq = t["empty_result_min_seq"]
        if min_seq is not None and any(s > min_seq for s in seqs):
            t["has_later_lookup_start"] = True

    # --- aggregate per arm ---------------------------------------------
    arms: dict[str, dict[str, Any]] = {}
    for trial_id in order:
        t = trials[trial_id]
        arm = t["arm"]
        a = arms.setdefault(
            arm,
            {
                "trials": 0,
                "passed": 0,
                "failed": 0,
                "errored": 0,
                "ended_on_budget_or_time": 0,
                "by_termination": {},
                "by_condition": {},
                "by_task": {},
                "first_call_not_lookup_order": 0,
                "never_called_lookup_order": 0,
                "empty_result_delivered": 0,
                "empty_result_delivered_ok": 0,
                "after_empty_result_read_again_trials": 0,
                "after_empty_result_read_again_passed": 0,
                "after_empty_result_not_read_again_trials": 0,
                "after_empty_result_not_read_again_passed": 0,
                "uninjected_tool_error_trials": 0,
                "uninjected_tool_error_passed": 0,
            },
        )

        a["trials"] += 1
        outcome = t["outcome"]
        is_pass = outcome == "PASS"
        if outcome == "PASS":
            a["passed"] += 1
        elif outcome == "FAIL":
            a["failed"] += 1
        elif outcome == "ERROR":
            a["errored"] += 1
        else:
            fail(
                f"trial {trial_id!r} has an unrecognised outcome: {outcome!r} "
                "(expected PASS, FAIL or ERROR)"
            )

        if t["termination"] != "completed":
            a["ended_on_budget_or_time"] += 1

        a["by_termination"][t["termination"]] = a["by_termination"].get(t["termination"], 0) + 1

        cond = a["by_condition"].setdefault(t["condition_id"], {"trials": 0, "passed": 0})
        cond["trials"] += 1
        if is_pass:
            cond["passed"] += 1

        task = a["by_task"].setdefault(t["task_id"], {"trials": 0, "passed": 0})
        task["trials"] += 1
        if is_pass:
            task["passed"] += 1

        first = t["first_tool_start"]
        if first is not None and first[1] != "lookup_order":
            a["first_call_not_lookup_order"] += 1

        if not t["has_lookup_start"]:
            a["never_called_lookup_order"] += 1

        if t["empty_result_min_seq"] is not None:
            a["empty_result_delivered"] += 1
            if t["has_empty_result_ok"]:
                a["empty_result_delivered_ok"] += 1
            if t["has_later_lookup_start"]:
                a["after_empty_result_read_again_trials"] += 1
                if is_pass:
                    a["after_empty_result_read_again_passed"] += 1
            else:
                a["after_empty_result_not_read_again_trials"] += 1
                if is_pass:
                    a["after_empty_result_not_read_again_passed"] += 1

        if t["uninjected_error"]:
            a["uninjected_tool_error_trials"] += 1
            if is_pass:
                a["uninjected_tool_error_passed"] += 1

    result_arms: dict[str, Any] = {}
    for arm, a in arms.items():
        result_arms[arm] = {
            "label": arm_label(arm),
            "trials": a["trials"],
            "passed": a["passed"],
            "failed": a["failed"],
            "errored": a["errored"],
            "ended_on_budget_or_time": a["ended_on_budget_or_time"],
            "by_termination": a["by_termination"],
            "by_condition": a["by_condition"],
            "by_task": a["by_task"],
            "first_call_not_lookup_order": a["first_call_not_lookup_order"],
            "never_called_lookup_order": a["never_called_lookup_order"],
            "empty_result_delivered": a["empty_result_delivered"],
            "empty_result_delivered_ok": a["empty_result_delivered_ok"],
            "after_empty_result": {
                "read_again": {
                    "trials": a["after_empty_result_read_again_trials"],
                    "passed": a["after_empty_result_read_again_passed"],
                },
                "not_read_again": {
                    "trials": a["after_empty_result_not_read_again_trials"],
                    "passed": a["after_empty_result_not_read_again_passed"],
                },
            },
            "uninjected_tool_error": {
                "trials": a["uninjected_tool_error_trials"],
                "passed": a["uninjected_tool_error_passed"],
            },
        }

    # --- optional audit file --------------------------------------------
    audit: dict[str, int] | None = None
    if audit_path is not None:
        if not os.path.isfile(audit_path):
            fail(f"missing audit file: {audit_path}")
        lines = 0
        tool_call_ids: set[Any] = set()
        try:
            with open(audit_path, encoding="utf-8") as f:
                for lineno, line in enumerate(f, start=1):
                    s = line.strip()
                    if not s:
                        continue
                    lines += 1
                    try:
                        obj = json.loads(s)
                    except json.JSONDecodeError as e:
                        fail(f"malformed JSON in audit file ({audit_path}) at line {lineno}: {e}")
                    if isinstance(obj, dict) and "tool_call_id" in obj:
                        tool_call_ids.add(obj["tool_call_id"])
        except OSError as e:
            fail(f"cannot read audit file ({audit_path}): {e}")
        audit = {"lines": lines, "distinct_tool_call_ids": len(tool_call_ids)}

    output = {
        "store": os.path.basename(os.path.normpath(store_dir)),
        "arms": result_arms,
        "audit": audit,
    }
    print(json.dumps(output, sort_keys=True))


if __name__ == "__main__":
    main()
