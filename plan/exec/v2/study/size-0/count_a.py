"""Count the ordered event ledger, reconciling it with the sealed trials."""

from collections import Counter, defaultdict
from pathlib import Path

from descriptors import read
from records import Row, assignment_receipts, counter_cli, require, rows

FIELDS: tuple[str, ...] = (
    "exposed",
    "unexposed",
    "boundary_read_again",
    "boundary_read_again_right_id",
    "passes_read_again",
    "passes_no_read_again",
    "passes_unexposed",
    "trials",
    "scripted_opening_recorded",
    "delivered",
    "model_step_after_opening",
    "read_again",
    "read_again_right_id",
    "passed",
    "final_state_passes",
    "errored",
)


def classify(events: list[Row], recording: list[Row], order_id: str, clean: bool) -> dict[str, int]:
    facts = dict.fromkeys(FIELDS, 0)
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
    facts["scripted_opening_recorded"] = int(opening)
    handoff = opening and kinds[4:5] == ["model_step"]
    if clean and handoff:
        reply = payloads[3]
        facts["model_step_after_opening"] = int(
            reply["ok"] is True
            and reply["injected_by"] is None
            and isinstance(reply["value"], dict)
        )

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
        return facts
    facts["delivered"] = 1
    if not clean:
        facts["model_step_after_opening"] = int(handoff and delivery_index == 3)
    later = timeline[delivery_index + 1 :]
    step = next((i for i, event in enumerate(later) if event["kind"] == "model_step"), None)
    retries = (
        [
            e["payload"]["arguments"]
            for e in later[step + 1 :]
            if e["kind"] == "tool_start" and e["payload"]["tool"] == "lookup_order"
        ]
        if step is not None
        else []
    )
    facts["read_again"] = int(bool(retries))
    facts["read_again_right_id"] = int(any(a.get("order_id") == order_id for a in retries))
    return facts


def count(store: Path, audit: Path) -> Row:
    require(audit.read_bytes() == b"", "replacement audit contains data")
    manifest = read(store / "manifest.json")
    ids = {t["task_id"]: t["task"]["order_id"] for t in manifest["tasks"]}
    trials = rows(store / "trials.jsonl")
    receipts = assignment_receipts(audit, trials, manifest)
    ledger: dict[str, list[Row]] = defaultdict(list)
    for e in rows(store / "events.jsonl"):
        ledger[e["trial_id"]].append(e)
    result: Row = {}
    for key in ("baseline", "candidate", "pooled"):
        result[key] = dict.fromkeys(FIELDS, 0) | {
            "by_order": {oid: dict.fromkeys(FIELDS, 0) for oid in ids.values()},
            "terminations": Counter(),
            "unexposed_trials": [],
            "unexposed_details": {},
        }
    seen: set[str] = set()
    for t in trials:
        tid = t["trial_id"]
        require(tid not in seen, f"duplicate trial {tid}")
        seen.add(tid)
        events = ledger.pop(tid, [])
        require(
            events == t["events"] and all(e["seq"] == i for i, e in enumerate(events)),
            f"event stream differs: {tid}",
        )
        oid = ids[t["task_id"]]
        facts = classify(events, t["recording"], oid, t["condition_id"] == "clean")
        grade = t["contract"]
        facts["final_state_passes"] = int(
            grade is not None and grade["grader_error"] is None and grade["success"] is True
        )
        receipt = receipts[tid]
        facts["exposed"] = int(bool(facts["delivered"] and receipt["stream_completed"] is True))
        facts["unexposed"] = facts["delivered"] - facts["exposed"]
        for field in ("read_again", "read_again_right_id"):
            facts["boundary_" + field] = facts[field]
            facts[field] *= facts["exposed"]
        facts["passes_read_again"] = facts["read_again"] * facts["final_state_passes"]
        facts["passes_no_read_again"] = (facts["exposed"] - facts["read_again"]) * facts[
            "final_state_passes"
        ]
        facts["passes_unexposed"] = facts["unexposed"] * facts["final_state_passes"]
        facts.update(
            trials=1, passed=int(t["outcome"] == "PASS"), errored=int(t["outcome"] == "ERROR")
        )
        for key in (t["arm"], "pooled"):
            group = result[key]
            if facts["unexposed"]:
                group["unexposed_trials"].append(tid)
                group["unexposed_details"][tid] = dict(
                    reason=receipt["incomplete_reason"], termination=t["termination"]
                )
            group["terminations"][t["termination"]] += 1
            for field, value in facts.items():
                group[field] += value
                group["by_order"][oid][field] += value
    require(not ledger, "orphan events")
    return result


if __name__ == "__main__":
    counter_cli(count)
