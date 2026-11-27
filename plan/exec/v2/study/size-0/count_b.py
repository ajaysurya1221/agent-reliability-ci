"""Independently classify the events embedded in each trial envelope."""

from pathlib import Path

from descriptors import read
from records import Row, assignment_receipts, counter_cli, require, rows


def classify(trial: Row, order_id: str) -> dict[str, int]:
    facts = {
        "trials": 1,
        "passed": int(trial["outcome"] == "PASS"),
        "final_state_passes": int(
            bool(trial["contract"])
            and trial["contract"]["success"] is True
            and trial["contract"]["grader_error"] is None
        ),
        "errored": int(trial["outcome"] == "ERROR"),
        "scripted_opening_recorded": 0,
        "model_step_after_opening": 0,
        "delivered": 0,
        "read_again": 0,
        "read_again_right_id": 0,
    }
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
        facts["scripted_opening_recorded"] = 1
        reply = observable[3]["payload"]
        expected_reply = (
            reply["injected_by"] is None and isinstance(reply["value"], dict)
            if trial["condition_id"] == "clean"
            else reply["injected_by"] == "empty_result" and reply["value"] is None
        )
        facts["model_step_after_opening"] = int(
            reply["ok"] is True
            and expected_reply
            and len(observable) > 4
            and observable[4]["kind"] == "model_step"
        )
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
        facts["delivered"] = 1
        steps = [
            e["seq"] for e in observable if e["kind"] == "model_step" and e["seq"] > finish["seq"]
        ]
        for e in starts.values():
            if steps and e["seq"] > min(steps) and e["payload"]["tool"] == "lookup_order":
                facts["read_again"] = 1
                if e["payload"]["arguments"].get("order_id") == order_id:
                    facts["read_again_right_id"] = 1
        break
    return facts


def count(store: Path, audit: Path) -> Row:
    require(audit.stat().st_size == 0, "nonempty replacement log")
    trials = rows(store / "trials.jsonl")
    events = rows(store / "events.jsonl")
    timeline: dict[str, list[Row]] = {}
    for event in events:
        group = timeline.setdefault(event["trial_id"], [])
        require(event["seq"] == len(group), f"event sequence differs: {event['trial_id']}")
        group.append(event)
    manifest = read(store / "manifest.json")
    ids = {t["task_id"]: t["task"]["order_id"] for t in manifest["tasks"]}
    require(len({t["trial_id"] for t in trials}) == len(trials), "duplicate trial")
    receipts = assignment_receipts(audit, trials, manifest)
    facts = []
    for trial in trials:
        require(
            trial["events"] == timeline.pop(trial["trial_id"], []),
            f"events differ: {trial['trial_id']}",
        )
        oid = ids[trial["task_id"]]
        obs = classify(trial, oid)
        confirmed = receipts[trial["trial_id"]]["stream_completed"] is True
        obs["exposed"] = int(confirmed and obs["delivered"])
        obs["unexposed"] = int(not confirmed and obs["delivered"])
        obs["boundary_read_again"] = obs["read_again"]
        obs["boundary_read_again_right_id"] = obs["read_again_right_id"]
        if not obs["exposed"]:
            obs.update(read_again=0, read_again_right_id=0)
        passed = bool(obs["final_state_passes"])
        obs.update(
            passes_read_again=int(passed and obs["read_again"]),
            passes_no_read_again=int(passed and obs["exposed"] and not obs["read_again"]),
            passes_unexposed=int(passed and obs["unexposed"]),
        )
        facts.append((trial["arm"], oid, trial["termination"], obs, trial["trial_id"]))
    require(not timeline, "unassigned event")
    fields = (
        "exposed",
        "unexposed",
        "boundary_read_again",
        "boundary_read_again_right_id",
        "passes_read_again",
        "passes_no_read_again",
        "passes_unexposed",
        "trials",
        "passed",
        "final_state_passes",
        "errored",
        "scripted_opening_recorded",
        "model_step_after_opening",
        "delivered",
        "read_again",
        "read_again_right_id",
    )
    result: Row = {}
    for arm in ("pooled", "baseline", "candidate"):
        selected = [row for row in facts if arm == "pooled" or row[0] == arm]
        result[arm] = {f: sum(row[3][f] for row in selected) for f in fields}
        result[arm]["by_order"] = {
            oid: {f: sum(row[3][f] for row in selected if row[1] == oid) for f in fields}
            for oid in ids.values()
        }
        result[arm]["unexposed_trials"] = [row[4] for row in selected if row[3]["unexposed"]]
        result[arm]["unexposed_details"] = {
            r[4]: dict(reason=receipts[r[4]]["incomplete_reason"], termination=r[2])
            for r in selected
            if r[3]["unexposed"]
        }
        result[arm]["terminations"] = {
            t: sum(row[2] == t for row in selected) for t in {row[2] for row in selected}
        }
    return result


if __name__ == "__main__":
    counter_cli(count)
