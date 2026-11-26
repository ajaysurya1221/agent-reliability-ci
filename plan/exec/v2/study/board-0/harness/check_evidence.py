"""Offline K5 verifier. Run this trusted copy against an archive and its detached digest."""

from __future__ import annotations

import argparse
import base64
import hashlib
import itertools
import json
import random
import re
import subprocess
import sys
import tempfile
import zipfile
from collections import defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

Row = dict[str, Any]


def require(ok: object, reason: str) -> None:
    if not ok:
        raise ValueError(reason)


def equal_json(left: object, right: object) -> bool:
    return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(
        right, sort_keys=True, allow_nan=False
    )


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def seeded_snapshot(row: Row, seed: int) -> Row:
    # Independent implementation of the two registered deterministic worlds.
    rng = random.Random(seed)
    if row["family"] == "orders":
        order = {
            "sku": f"SKU-{rng.randrange(1000, 9999)}",
            "total_cents": rng.randrange(1000, 20000),
            "refunded_cents": 0,
            "notes": [],
        }
        return {"order": order, "stock": rng.randrange(1, 50), "order_id": row["task"]["order_id"]}
    target = row["task"]["event_id"]
    rng.seed(f"{rng.getrandbits(128)}:{target}")
    ids = [target]
    while len(ids) < 3:
        other = f"EVT-{rng.randrange(1000, 10000)}"
        if other not in ids:
            ids.append(other)

    def names(first: str, second: str) -> list[str]:
        pool = [" ".join(p) for p in itertools.product(first.split(), second.split())]
        return rng.sample(pool, 3)

    fields: Row = {}
    fields["title"] = names(
        "Budget Community Design Finance Garden Library Market "
        "Outreach Product Safety Service Travel",
        "Briefing Clinic Forum Handover Meeting Orientation "
        "Panel Review Seminar Session Talk Workshop",
    )
    fields["room"] = names(
        "Alder Ash Aspen Beech Birch Cedar Elm Hazel Juniper Linden Maple "
        "Oak Pine Rowan Spruce Willow",
        "Annex Atrium Gallery Hall Loft Lounge Pavilion Studio Suite Terrace Theatre Wing",
    )
    fields["organiser"] = names(
        "Ada Amir Anika Ben Elena Farah Hugo Iris Jonah Leila Maya Nora Ravi Sam Theo Zoe",
        "Bell Chen Costa Das Evans Fox Green Khan Lee Malik Park Reed Silva Stone West Wong",
    )
    for field, lo, hi in [
        ("start_minute", 420, 1200),
        ("duration_minutes", 15, 241),
        ("attendee_count", 2, 501),
    ]:
        fields[field] = rng.sample(range(lo, hi), 3)
    floors = rng.sample(range(1, 25), 3)
    events = {id_: {k: v[i] for k, v in fields.items()} for i, id_ in enumerate(ids)}
    rooms = {
        event["room"]: {"floor": floor, "capacity": rng.randint(event["attendee_count"], 600)}
        for event, floor in zip(events.values(), floors, strict=True)
    }
    return {"event_id": target, "event": events[target], "events": events, "rooms": rooms}


def target_record(row: Row, seed: int) -> Row:
    return seeded_snapshot(row, seed)[row["source"]["field"].split(".")[0]]


def answer_key(row: Row, seed: int) -> int | str:
    return target_record(row, seed)[row["source"]["field"].split(".")[1]]


def check_opening(row: Row, seed: int, reply: Row) -> None:
    blocks = reply["content"]
    require(
        reply["isError"] is False
        and len(blocks) == 1
        and blocks[0]["type"] == "text"
        and json.dumps(json.loads(blocks[0]["text"]), sort_keys=True)
        == json.dumps(target_record(row, seed), sort_keys=True),
        "original opening differs from seeded target",
    )


def check_deadline(trial: Row, receipt: Row) -> None:
    for event in trial["events"]:
        if event["kind"] in ("tool_start", "tool_finish"):
            require(0 <= event["at_ms"] <= 120_000, "tool deadline")
    if trial["termination"] == "completed":
        require(0 <= receipt["agent_seconds"] <= 120, "agent deadline")


def require_infra(trial: Row, receipt: Row, exchange: Row) -> None:
    require(
        exchange is receipt["exchanges"][-1]
        and not receipt["complete"]
        and trial["outcome"] == "ERROR"
        and trial["termination"] == "harness_error"
        and receipt.get("agent_exit") == 75
        and trial["agent_claimed_success"] is False
        and trial["failure_detail"] == "agent reported an infrastructure failure (exit <n>)",
        "backend failure differs from recorded exit",
    )


def assistant(raw: bytes, tag: str) -> Row:
    response = json.loads(raw)
    json.dumps(response, ensure_ascii=False, allow_nan=False).encode("utf-8")
    require(
        isinstance(response, dict)
        and response.get("model") == tag
        and response.get("done") is True
        and response.get("done_reason") != "length",
        "model or done",
    )
    msg = response.get("message")
    if not isinstance(msg, dict) or msg.get("role") != "assistant":
        raise ValueError("response role")
    calls = msg.get("tool_calls", [])
    require(
        isinstance(calls, list) and (calls or isinstance(msg.get("content"), str)),
        "assistant content",
    )
    return msg


def function(wrapper: object) -> Row:
    fn = wrapper.get("function") if isinstance(wrapper, dict) else None
    if not isinstance(fn, dict):
        raise ValueError("assistant tool call")
    require(
        isinstance(fn.get("name"), str) and isinstance(fn.get("arguments", {}), dict),
        "assistant tool call",
    )
    return fn


def receipt_answer(r: Row, tag: str, trial: Row, known: set[str]) -> str | None:
    exchanges = r["exchanges"]
    require(1 <= len(exchanges) == r["steps"] <= 8, "missing or extra chat requests")
    calls = 1
    for i, x in enumerate(exchanges):
        body = base64.b64decode(x["request_b64"], validate=True)
        req = json.loads(body)
        require(digest(body) == x["sha256"] and req["model"] == tag, "request bytes or tag")
        require(
            {tool["function"]["name"] for tool in req["tools"]} == known,
            "tool catalogue",
        )
        if x["status"] != 200 or x["response_b64"] is None or x.get("incomplete_body"):
            if trial["termination"] != "timeout":
                require_infra(trial, r, x)
            break
        raw = base64.b64decode(x["response_b64"], validate=True)
        try:
            msg = assistant(raw, tag)
        except ValueError:
            require_infra(trial, r, x)
            break
        if not msg.get("tool_calls"):
            require(i == len(exchanges) - 1, "extra request after text")
            return msg["content"]
        for wrapper in msg["tool_calls"]:
            try:
                fn = function(wrapper)
            except ValueError:
                require_infra(trial, r, x)
                return None
            if fn["name"] in known:
                if calls == 12:
                    require(i == len(exchanges) - 1, "extra request after budget")
                    return None
                calls += 1
    require(len(exchanges) == 8 or not r["complete"], "short receipt")
    return None


def grade(text: str | None, key: int | str, snapshot: object, row_id: str) -> tuple[bool, bool]:
    if not text:
        return False, False
    exact = text.strip() in (str(key), str(key) + ".")
    answer = text.replace(row_id, "")
    values: set[int | str] = {key}

    def collect(obj: object) -> None:
        if isinstance(obj, dict):
            for child in obj.values():
                collect(child)
        elif isinstance(obj, list):
            for child in obj:
                collect(child)
        elif type(obj) is type(key):
            values.add(obj)

    collect(snapshot)
    if isinstance(key, int):
        hits = set()
        for match in re.finditer(r"(?<![\d.,])(?:\d{1,3}(?:,\d{3})+|\d+)(?![\d]|[.,]\d)", answer):
            number = Decimal(match[0].replace(",", ""))
            if number in values:
                hits.add(number)
        return hits == {key}, exact

    spans: list[tuple[int, int, str]] = []
    for word in values:
        if not isinstance(word, str) or not word:
            continue
        start = answer.find(word)
        while start >= 0:
            end = start + len(word)
            if (start == 0 or not answer[start - 1].isalnum()) and (
                end == len(answer) or not answer[end].isalnum()
            ):
                spans.append((start, -len(word), word))
            start = answer.find(word, start + 1)
    stop = 0
    matched = set()
    for start, _, word in sorted(spans):
        if start >= stop:
            matched.add(word)
            stop = start + len(word)
    return matched == {key}, exact


def regrade(row: Row, t: Row, r: Row, tag: str) -> bool:
    check_deadline(t, r)
    check_opening(row, t["seed"], t["final_state"]["ledger"][2]["server_reply"])
    known = (
        {"lookup_order", "check_stock"}
        if row["family"] == "orders"
        else {"lookup_event", "check_room"}
    )
    ans = receipt_answer(r, tag, t, known)
    snapshot = seeded_snapshot(row, t["seed"])
    section, field = row["source"]["field"].split(".")
    correct, exact = grade(ans, snapshot[section][field], snapshot, row["task"][section + "_id"])
    if t["termination"] == "completed":
        require(
            r["complete"] and ans == r["answer"] == t["final_state"]["answer"],
            "receipt terminal answer",
        )
        require(
            t["contract"]["success"] is correct and t["outcome"] == ("PASS" if correct else "FAIL"),
            "trial grade",
        )
    else:
        require(
            t["outcome"]
            == (
                "ERROR"
                if t["termination"] in ("grader_error", "harness_error", "replay_miss")
                else "FAIL"
            ),
            "termination grade",
        )
    return exact and t["termination"] == "completed"


def examine(
    z: zipfile.ZipFile,
    run: str,
    tag: str,
    rows: dict[str, Row],
    rehearsal: bool,
    task_id: str | None = None,
) -> Row:
    prefix = f"clean/{run}/{task_id}/" if task_id else f"runs/{run}/"

    def obj(name: str) -> Any:
        return json.loads(z.read(prefix + name))

    def lines(name: str) -> list[Row]:
        return [json.loads(s) for s in z.read(prefix + name).splitlines()]

    desc = obj("descriptor.yaml")
    m = obj("manifest.json")
    decision = obj("decision.json")
    clean = run.endswith("-clean")
    rule = {
        "alpha": "1/20",
        "delta": "1/10",
        "max_errored_pairs": 4,
        "stakes": ["1/4", "1/2"],
        "scenario_seeds": "per_round",
        "max_rounds": 1 if clean else 26,
    }
    if clean:
        require(task_id in rows, "unknown clean task")
        row = rows[str(task_id)]
        public = {"key_id": row["id"], **{k: row[k] for k in ("ask", "family", "opening", "task")}}
        require(
            desc["experiment_id"] == m["experiment_id"] == run + "-" + str(task_id)
            and desc["task_id"] == m["task_id"] == task_id
            and desc["task"] == m["task"] == public
            and desc["n_per_arm"] == m["n_per_arm"] == 1
            and desc["conditions"] == [{"id": "E"}],
            "clean descriptor differs",
        )
    else:
        require(
            desc["rule"] == rule
            and all(m[k] == v for k, v in rule.items())
            and decision["threshold"] == "40/1",
            "descriptor rule",
        )
        require(
            desc["suite_id"] == run == m["suite_id"]
            and len(desc["tasks"]) == 16
            and {t["id"] for t in desc["tasks"]} == rows.keys(),
            "suite task inventory",
        )
        for task in desc["tasks"]:
            row = rows[task["id"]]
            public = {
                "key_id": row["id"],
                **{k: row[k] for k in ("ask", "family", "opening", "task")},
            }
            require(
                task == {"id": row["id"], **public}
                and {"task_id": row["id"], "task": public} in m["tasks"],
                "scheduled task contents",
            )
    faults = (
        []
        if clean
        else [
            {"name": "empty_result", "tool": name, "occurrence": 0}
            for name in sorted({r["opening"]["name"] for r in rows.values()})
        ]
    )
    sealed_faults = [
        {
            "name": "empty_result",
            "tool": f["tool"],
            "at_occurrence": 0,
            "bucket": "falsify",
            "params": {},
        }
        for f in faults
    ]
    require(
        desc["conditions"] == [{"id": "E", **({"faults": faults} if faults else {})}]
        and m["conditions"] == [{"condition_id": "E", "faults": sealed_faults}],
        "opening fault rule",
    )
    for k, v in {"max_tool_calls": 12, "max_seconds": 120, "grader_seconds": 20}.items():
        require(desc["budgets"].get(k) == m["budgets"].get(k) == v, "trial budget")
    for side, label in [("baseline", "stock-sentence"), ("candidate", "empty-as-given")]:
        arm = desc[side]
        argv = arm["command"]["argv"]
        require(
            arm["label"] == m[side]["label"] == ("clean" if clean else label)
            and arm["command"] == m[side]["command"]
            and ("--offline" in argv) == rehearsal
            and argv[argv.index("--model") + 1] == tag,
            "arm command",
        )
    receipts = lines("receipts.jsonl")
    index = {(r["key_id"], r["arci_arm"], r["seed"]): r for r in receipts}
    require(len(index) == len(receipts), "duplicate receipt")
    trials = lines("trials.jsonl")
    if clean:
        require(
            len(trials) == 2
            and {t["arm"] for t in trials} == {"baseline", "candidate"}
            and all(t["task_id"] == task_id for t in trials),
            "clean pair inventory",
        )
    ledger_export = lines("ledger.jsonl")
    require(
        ledger_export
        == [{"trial_id": t["trial_id"], "ledger": t["final_state"]["ledger"]} for t in trials],
        "exported ledger differs",
    )
    by_trial: dict[str, list[Row]] = defaultdict(list)
    for event in lines("events.jsonl"):
        by_trial[event["trial_id"]].append(event)
    require(by_trial == {t["trial_id"]: t["events"] for t in trials}, "exported events differ")
    first_counts = obj("count_a.json")
    require(equal_json(first_counts, obj("count_b.json")), "published counts disagree")
    arms = {
        s: {
            f: dict.fromkeys(
                (
                    "trials",
                    "passed",
                    "errored",
                    "exact",
                    "retrieved",
                ),
                0,
            )
            for f in ("all", "orders", "calendar")
        }
        for s in ("baseline", "candidate")
    }
    pairs: dict[str, dict[str, str]] = defaultdict(dict)
    for t in trials:
        try:
            r = index.pop((t["task_id"], t["arm"], t["seed"]))
            require(r["run"] == run and r["arm"] == t["variant"], "receipt assignment")
            row = rows[t["task_id"]]
            exact = regrade(row, t, r, tag)
            opening = t["final_state"]["ledger"][2]
            require(
                opening["tool"] == row["opening"]["name"]
                and opening["arguments"] == row["opening"]["arguments"],
                "scripted call",
            )
            real = opening["server_reply"]["content"][0]["text"]
            delivered = (
                real
                if clean
                else (
                    "The lookup returned no data. Repeat the same call with the same arguments."
                    if t["arm"] == "baseline"
                    else ""
                )
            )
            request = json.loads(base64.b64decode(r["exchanges"][0]["request_b64"], validate=True))
            require(
                request["messages"][-1]
                == {"role": "tool", "tool_name": opening["tool"], "content": delivered},
                "first request delivery",
            )
            record = target_record(row, t["seed"])
            charged = [c for c in t["recording"] if not c["tool"].startswith("rpc:")]
            recovered = not clean and any(
                c["tool"] == opening["tool"]
                and c["result"]["ok"]
                and any(
                    block.get("type") == "text" and json.loads(block["text"]) == record
                    for block in c["result"]["value"]["content"]
                )
                for c in charged[1:]
            )
            for family in ("all", row["family"]):
                bucket = arms[t["arm"]][family]
                bucket["trials"] += 1
                bucket["passed"] += int(t["outcome"] == "PASS")
                bucket["errored"] += int(t["outcome"] == "ERROR")
                bucket["exact"] += int(exact)
                bucket["retrieved"] += int(recovered)
            pairs[t["pair_id"]][t["arm"]] = t["outcome"]
        except (ValueError, KeyError, TypeError) as exc:
            raise ValueError(f"{t['trial_id']}: {exc}") from exc
    require(not index, "extra receipt")
    signs = dict.fromkeys(("minus", "zero", "plus", "errored"), 0)
    for pair in pairs.values():
        b, c = pair["baseline"], pair["candidate"]
        signs[
            "errored"
            if "ERROR" in (b, c)
            else ("zero" if b == c else "plus" if c == "PASS" else "minus")
        ] += 1
    counts = {"arms": arms, "signs": signs}
    require(equal_json(counts, first_counts), "regraded counts differ")
    audit = obj("audit.json")
    header = json.loads(z.read(prefix + "run.log").splitlines()[0])
    require(header["run"] == run and header["ollama"] == "0.32.14", "suite admission")
    start = header["part_ns"] if clean else header["claim_ns"]
    require(
        equal_json(
            audit,
            {
                "run": run,
                "started_local_date": header["date"],
                "claim_ns": start,
                "export_ns": audit["export_ns"],
                "seconds": seconds(audit),
                "model_digest": header["model_digest"],
                "ollama": header["ollama"],
                "verified_trials": len(trials),
                "counts_agree": True,
                "transport": "FIFO stand-in" if rehearsal else "native Ollama",
                "verdict": decision["verdict"],
                "stopping_round": decision.get("stopped_at_round"),
            },
        ),
        "published audit figures differ",
    )
    if not clean:
        require(signs == decision["history"][-1]["counts"], "released pair signs")
    with tempfile.TemporaryDirectory() as tmp:
        store = Path(tmp)
        for name in ("manifest.json", "trials.jsonl", "events.jsonl", "decision.json"):
            (store / name).write_bytes(z.read(prefix + name))
        # The archive never supplies an executable or a Python import path.
        p = subprocess.run(
            ["arci", "gate", str(store)],
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            timeout=180,
        )
        matched = (
            json.loads((store / "decision.json").read_bytes()) == decision
            if clean
            else "stored decision: MATCH" in p.stdout.splitlines()
        )
        require(matched and p.returncode == decision["exit_code"], "arci gate decision mismatch")

    return {
        "counts": counts,
        "audit": audit,
        "claim_ns": header["claim_ns"],
        "win": any(t["outcome"] == "PASS" for t in trials),
    }


SOURCE_FILES = (
    "PREREGISTRATION-board-0.draft.md",
    "models.json",
    "scenario-collisions.json",
    "tasks/tasks.json",
    "tasks/make_tasks.py",
    "calendardesk/calendar_world.py",
    "calendardesk/tasks.json",
    "calendardesk/key.py",
    "orderdesk/orderdesk_world.py",
    "orderdesk/task.json",
    "projections/project.py",
    "projections/board0_plan_stub.py",
    "projections/plan-16x20.yaml",
    "projections/plan-16x26.yaml",
    "projections/registered-rows.json",
    "harness/agent.py",
    "harness/admission.py",
    "harness/audit.py",
    "harness/board_oracle.py",
    "harness/board_relay.py",
    "harness/common.py",
    "harness/check_evidence.py",
    "harness/count_a.py",
    "harness/count_b.py",
    "harness/fifo.py",
    "harness/grade.py",
    "harness/inputs.py",
    "harness/launcher.py",
    "harness/offline_model.py",
    "harness/pin.py",
    "harness/privacy.py",
    "harness/publication.py",
    "harness/suite_process.py",
    "harness/worlds.py",
    "harness/run-board0.sh",
    "harness/check-offline.sh",
    "harness/INTERFACE.md",
    "harness/DEVIATIONS.md",
    "harness/tests/test_board.py",
    "harness/tests/test_amendment.py",
    "harness/tests/test_grade.py",
    "harness/tests/planted.py",
    "harness/tests/rehearsal.py",
    "harness/tests/fake_ollama.py",
    "harness/tests/native_rehearsal.py",
    "harness/tests/native-rehearsal.sh",
    "harness/tests/test_fake_ollama.py",
)


def members(slots: list[Row], rows: dict[str, Row]) -> tuple[set[str], set[str]]:
    expected = set(SOURCE_FILES) | {
        "board0-digests.sha256",
        "descriptor-digests.sha256",
        "result.md",
    }
    expected.update(f"pins/board0-pin-M{i}.json" for i in range(1, 6))
    failed = sum(bool(m.get("vacant")) or m["pin"] != f"board0-pin2-{m['slot']}" for m in slots)
    expected.update(f"pins/board0-pin2-S{i}.json" for i in range(1, min(2, failed) + 1))
    descriptors = set()
    files = (
        "descriptor.yaml",
        "manifest.json",
        "trials.jsonl",
        "events.jsonl",
        "decision.json",
        "ledger.jsonl",
        "receipts.jsonl",
        "audit.json",
        "count_a.json",
        "count_b.json",
        "run.log",
    )
    for m in slots:
        slot = m["slot"]
        expected.add(f"pins/board0-pin2-{slot}.json")
        for day in (1, 2):
            name = f"board0-d{day}-{slot}"
            if not m.get("vacant"):
                expected.add(f"clean/{name}-clean.json")
            for prefix in [f"runs/{name}-E", *(f"clean/{name}-clean/{tid}" for tid in rows)]:
                if not m.get("vacant"):
                    expected.update(f"{prefix}/{f}" for f in files)
                descriptors.add(f"{prefix}/descriptor.yaml")
    return expected | descriptors, descriptors


def check_inventory(names: list[str], slots: list[Row], rows: dict[str, Row]) -> None:
    required, _ = members(slots, rows)
    require(
        len(names) == len(required) and set(names) == required,
        f"archive inventory differs: {sorted(required.symmetric_difference(names))}",
    )


def seconds(summary: Row) -> float:
    start, end = summary["claim_ns"], summary["export_ns"]
    require(
        type(start) is int
        and type(end) is int
        and end > start
        and summary["seconds"] == (end - start) / 1e9,
        "invocation elapsed time",
    )
    return summary["seconds"]


def verify_probe(probe: Row, tag: str, number: int) -> bool:
    delivery = number > 20
    exchanges = probe["exchanges"]
    require(probe["seconds"] >= 0 and len(exchanges) <= (1 if delivery else 2), "pin trial length")
    prefix: list[Row] = [
        {"role": "system", "content": "Use the pebble reader to answer the question."},
        {"role": "user", "content": f"What token is on pebble stone-{number}?"},
    ]
    expected = {"name": "read_pebble", "arguments": {"pebble": f"stone-{number}"}}
    schema = [
        {
            "type": "function",
            "function": {
                "name": "read_pebble",
                "description": "Read a pebble's token.",
                "parameters": {
                    "type": "object",
                    "properties": {"pebble": {"type": "string"}},
                    "required": ["pebble"],
                },
            },
        }
    ]
    passed = False
    if delivery:
        prefix.append({"role": "assistant", "content": "", "tool_calls": [{"function": expected}]})
    for step, x in enumerate(exchanges):
        raw = base64.b64decode(x["request_b64"], validate=True)
        req = json.loads(raw)
        history = req["messages"]
        require(
            digest(raw) == x["sha256"]
            and req
            == {
                "model": tag,
                "messages": history,
                "tools": schema,
                "stream": False,
                "think": False,
                "options": {"temperature": 0.7},
            },
            "pin request",
        )
        token = ""
        if step or delivery:
            token = history[-1]["content"]
            require(
                history[:-1] == prefix
                and history[-1] == {"role": "tool", "tool_name": "read_pebble", "content": token}
                and (
                    token == ""
                    if delivery
                    else re.fullmatch(r"[0-9a-f]{24}", token)
                    and token not in json.dumps([prefix, schema])
                ),
                "pin tool delivery",
            )
        else:
            require(history == prefix, "scripted scored pin opening")
        if x["status"] != 200 or x["response_b64"] is None or x.get("incomplete_body"):
            require(step + 1 == len(exchanges), "request after failed pin exchange")
            break
        try:
            msg = assistant(base64.b64decode(x["response_b64"], validate=True), tag)
        except ValueError:
            require(step + 1 == len(exchanges), "request after invalid pin response")
            break
        if delivery:
            passed = True
        elif step:
            passed = not msg.get("tool_calls") and grade(msg["content"], token, {}, "")[0]
        else:
            calls = msg.get("tool_calls", [])
            fn = (
                calls[0].get("function") if len(calls) == 1 and isinstance(calls[0], dict) else None
            )
            if (
                not isinstance(fn, dict)
                or fn.get("name") != expected["name"]
                or fn.get("arguments") != expected["arguments"]
            ):
                require(len(exchanges) == 1, "pin result without correct native call")
                break
            prefix.append(msg)
    require(probe["passed"] is passed, "pin grade")
    return passed


def check_report(report: str, slots: list[Row], results: dict[str, Row], rehearsal: bool) -> None:
    expected = ["# Board-0" + (" FIFO stand-in rehearsal" if rehearsal else "")]
    criteria = [
        "## Criteria",
        "| Slot | Day | BLOCK | PASS | INCONCLUSIVE | Orders stock | Orders empty | "
        "Calendar stock | Calendar empty |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for m in slots:
        for day in (1, 2):
            if m.get("vacant"):
                expected.extend(
                    [
                        f"## {m['slot']} · day {day} · {m['tag']}",
                        "vacant: pin failed. Model-day undecided.",
                    ]
                )
                criteria.append(f"| {m['slot']} | {day} | undecided | — | — | — | — | — | — |")
                continue
            run = results[f"board0-d{day}-{m['slot']}-E"]
            clean, audit, counts = run["clean"], run["audit"], run["counts"]
            elapsed = seconds(clean) + seconds(audit)
            verdict = audit["verdict"]
            families = clean["families"]
            rating = "rated" if clean["rated"] else "not rated"
            expected.extend(
                [
                    f"## {m['slot']} · day {day} · {m['tag']}",
                    f"Clean tasks passing at least once: orders {families['orders']}/8, "
                    f"calendar {families['calendar']}/8. Status: {rating}.",
                    f"{verdict} at round {audit['stopping_round']}. "
                    f"Clean plus measured elapsed time {elapsed:.2f} seconds.",
                    "| Arm | Passes | Orders | Calendar | Retrieved | Exact |",
                    "|---|---:|---:|---:|---:|---:|",
                ]
            )
            rates = {}
            for side, label in (("baseline", "stock-sentence"), ("candidate", "empty-as-given")):
                arm = counts["arms"][side]
                for family, bucket in arm.items():
                    rates[family, side] = f"{bucket['passed']}/{bucket['trials']}"
                values = [
                    label,
                    *(rates[f, side] for f in ("all", "orders", "calendar")),
                    *(str(arm["all"][f]) for f in ("retrieved", "exact")),
                ]
                expected.append("| " + " | ".join(values) + " |")
            expected.append(
                "Pair signs "
                + ", ".join(
                    f"{k} {counts['signs'][k]}" for k in ("minus", "zero", "plus", "errored")
                )
                + "."
            )
            values = [
                m["slot"],
                str(day),
                *(str(int(verdict == v)) for v in ("BLOCK", "PASS", "INCONCLUSIVE")),
                *(rates[f, s] for f in ("orders", "calendar") for s in ("baseline", "candidate")),
            ]
            criteria.append("| " + " | ".join(values) + " |")
    require(
        [line for line in report.splitlines() if line] == expected + criteria,
        "published result.md differs",
    )


def verify_pins(z: zipfile.ZipFile, config: Row, rehearsal: bool) -> None:
    for i in range(1, 6):
        run = f"board0-pin-M{i}"
        require(json.loads(z.read(f"pins/{run}.json"))["run"] == run, f"historical pin {run}")

    def corrected(slot: str) -> tuple[Row, bool]:
        run = f"board0-pin2-{slot}"
        pin = json.loads(z.read(f"pins/{run}.json"))
        model = pin["model"]
        require(
            pin["run"] == run
            and pin["ollama"] == config["ollama"]
            and model["slot"] == slot
            and model["pin"] == run
            and set(model) == {"slot", "tag", "digest", "pin", "family", "size"}
            and re.fullmatch("[0-9a-f]{64}", model["digest"])
            and len(pin["trials"]) == 20
            and len(pin["delivery"]) == 2
            and pin["transport"] == ("stand-in" if rehearsal else "Ollama"),
            f"model pin {run}",
        )
        passed = sum(verify_probe(x, model["tag"], i) for i, x in enumerate(pin["trials"], 1))
        delivery = [verify_probe(x, model["tag"], i) for i, x in enumerate(pin["delivery"], 21)]
        require(
            passed == pin["passed"] and pin["ok"] is (passed >= 16 and all(delivery)),
            f"corrected pin grade {run}",
        )
        return model, pin["ok"]

    spares = config["spares"]
    require([s["slot"] for s in spares] == ["S1", "S2"], "spare inventory")
    # models.json contains the final roster. The registration retains the identities
    # of originals even when neither model-day carries their tag or digest.
    registration = "" if rehearsal else z.read("PREREGISTRATION-board-0.draft.md").decode()
    if not rehearsal:
        prose = " ".join(registration.split())
        for spare in spares:
            run = f"board0-pin2-{spare['slot']}"
            identity = f"`{spare['tag']}` (`{spare['digest']}`, pin run `{run}`)"
            require(spare["pin"] == run and identity in prose, f"registered spare differs: {run}")
    remaining = iter(spares)
    for slot in config["slots"]:
        model, passed = corrected(slot["slot"])
        if not rehearsal:
            require(
                f"| {model['slot']} | `{model['tag']}` | `{model['digest']}` |" in registration,
                f"registered model differs for {model['slot']}",
            )
        expected = model
        if not passed:
            spare = next(remaining, None)
            if spare is not None:
                substitute, passed = corrected(spare["slot"])
                require(substitute == spare, "spare pin model differs")
                if passed:
                    expected = substitute | {"slot": slot["slot"]}
            if not passed:
                expected = model | {"vacant": True}
        require(equal_json(slot, expected), f"roster differs for {slot['slot']}")


def verify(path: Path, sidecar: Path, *, rehearsal: bool = False) -> int:
    fields = sidecar.read_text().split(maxsplit=1)
    with path.open("rb") as f:
        require(fields and fields[0] == hashlib.file_digest(f, "sha256").hexdigest(), "zip digest")
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        require(
            len(set(names)) == len(names)
            and all(not Path(n).is_absolute() and ".." not in Path(n).parts for n in names),
            "invalid archive paths",
        )
        config = json.loads(z.read("models.json"))
        require(config["ollama"] == "0.32.14", "registered server version")
        slots = config["slots"]
        size = 2 if rehearsal else 5
        require([m["slot"] for m in slots] == [f"M{i + 1}" for i in range(size)], "model inventory")
        registration = z.read("PREREGISTRATION-board-0.draft.md")
        require(
            rehearsal or (registration.strip() and b"PLACEHOLDER" not in registration),
            "unfinished registration",
        )
        verify_pins(z, config, rehearsal)
        tasks = json.loads(z.read("tasks/tasks.json"))["tasks"]
        rows = {r["id"]: r for r in tasks}
        require(
            len(rows) == len(tasks) == 16
            and sum(r["family"] == "orders" for r in tasks) == 8
            and sum(r["family"] == "calendar" for r in tasks) == 8,
            "task inventory",
        )
        check_inventory(names, slots, rows)
        _, descriptors = members(slots, rows)
        pins = {}
        for fn in ("board0-digests.sha256", "descriptor-digests.sha256"):
            listed = set()
            for line in z.read(fn).decode().splitlines():
                h, n = line.split("  ", 1)
                require(n not in pins and digest(z.read(n)) == h, f"digest differs: {n}")
                pins[n] = h
                listed.add(n)
            require(
                listed == (descriptors if fn.startswith("descriptor") else set(SOURCE_FILES)),
                "digest inventory",
            )
        expected = {
            f"board0-d{d}-{m['slot']}-E" for m in slots if not m.get("vacant") for d in (1, 2)
        }
        require(
            expected
            == {
                n.split("/")[1]
                for n in names
                if n.startswith("runs/") and n.endswith("/decision.json")
            },
            "run inventory",
        )
        results: dict[str, Row] = {}
        for run in sorted(expected):
            require(f"runs/{run}/descriptor.yaml" in pins, "unpinned descriptor")
            try:
                results[run] = examine(
                    z, run, slots[int(run.split("-")[2][1:]) - 1]["tag"], rows, rehearsal
                )
            except (ValueError, KeyError, TypeError) as exc:
                raise ValueError(f"{run}: {exc}") from exc
        for run in sorted(expected):
            clean = run[:-1] + "clean"
            summary = json.loads(z.read(f"clean/{clean}.json"))
            wins = {"orders": 0, "calendar": 0}
            model = slots[int(run.split("-")[2][1:]) - 1]
            measured = results[run]["audit"]
            seconds(summary)
            require(
                summary["run"] == clean
                and date.fromisoformat(summary["started_local_date"])
                <= date.fromisoformat(measured["started_local_date"])
                and measured["model_digest"] == model["digest"],
                "model-day metadata",
            )
            previous_end = summary["claim_ns"]
            for tid, row in rows.items():
                part = examine(z, clean, model["tag"], rows, rehearsal, tid)
                audit = part["audit"]
                require(
                    part["claim_ns"] == summary["claim_ns"]
                    and audit["model_digest"] == model["digest"]
                    and audit["started_local_date"] == summary["started_local_date"]
                    and previous_end
                    <= audit["claim_ns"]
                    < audit["export_ns"]
                    <= summary["export_ns"],
                    "clean audit timing or metadata",
                )
                previous_end = audit["export_ns"]
                wins[row["family"]] += int(part["win"])
            results[run]["clean"] = summary
            require(
                set(summary)
                == {
                    "families",
                    "rated",
                    "claim_ns",
                    "export_ns",
                    "seconds",
                    "run",
                    "started_local_date",
                }
                and equal_json(summary["families"], wins)
                and summary["rated"] is (min(wins.values()) >= 6),
                f"{clean}: clean rating",
            )
            if "-d2-" in clean:
                d1 = json.loads(z.read("clean/" + clean.replace("-d2-", "-d1-") + ".json"))
                require(
                    date.fromisoformat(summary["started_local_date"])
                    > date.fromisoformat(d1["started_local_date"]),
                    f"{clean}: local date",
                )
        check_report(z.read("result.md").decode(), slots, results, rehearsal)
    return len(results)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("zip", type=Path)
    parser.add_argument("digestfile", type=Path)
    parser.add_argument("--rehearsal", action="store_true", help="require two stand-in slots")
    args = parser.parse_args()
    try:
        n = verify(args.zip, args.digestfile, rehearsal=args.rehearsal)
    except (ValueError, KeyError, TypeError, OSError, zipfile.BadZipFile) as exc:
        sys.exit(f"evidence differs: {exc}")
    print(
        f"{n} measured suites and {n} clean rows matched; corrected pins and Board trials regraded"
    )
    if not args.rehearsal and n < 10:
        print("K5 cannot hold with vacant model-days.")
