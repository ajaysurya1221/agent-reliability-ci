"""Replay desk replies and join the released schedule, seals, ledger and sent bytes."""

from __future__ import annotations

import base64
import json
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from importlib import import_module
from pathlib import Path
from typing import Any

from common import (
    ROOT,
    Row,
    assistant,
    check_deadline,
    function,
    lines,
    need,
    read,
    require_infra,
    sha,
)
from grade import grade
from worlds import check_opening, expected, record_id, rows, world


def same(actual: Any, expected: Any, field: str) -> None:
    # Python otherwise equates JSON true, 1 and 1.0.
    need(json.dumps(actual, sort_keys=True) == json.dumps(expected, sort_keys=True), field)


def compiled(path: Path) -> Any:
    return import_module("arci.descriptor").compile_run_descriptor(path)


def specs(manifest: Any, stop: int) -> list[Any]:
    if not hasattr(manifest, "suite_id"):
        return list(import_module("arci.schedule").build_schedule(manifest))
    build = import_module("arci.suite_schedule").build_suite_round
    return [s for r in range(1, stop + 1) for s in build(manifest, r)]


def gate(store: Path) -> str:
    p = subprocess.run(
        [sys.executable, "-PB", "-m", "arci", "gate", str(store)],
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        timeout=180,
    )
    need(
        p.returncode == read(store / "decision.json")["exit_code"]
        and "stored decision: MATCH" in p.stdout.splitlines(),
        "arci gate: stored decision mismatch",
    )
    return p.stdout


def trial_audit(t: Row, r: Row, row: Row, doc: Row, model: str, run: str, work: Path) -> Row:
    check_deadline(t, r)
    state = t["final_state"]
    side = t["arm"]
    fault = not run.endswith("-clean")
    opening = row["opening"]
    same(
        [r[k] for k in ("run", "key_id", "arci_arm", "arm", "opening", "seed")],
        [run, row["id"], side, t["variant"], "fault" if fault else "clean", t["seed"]],
        "receipt identity",
    )
    module = import_module("arci.mcp_toolset_server")
    desk = world(row, t["seed"])
    allowed = (
        {"lookup_order", "check_stock"}
        if row["family"] == "orders"
        else {"lookup_event", "check_room"}
    )
    ref = module.ToolSetServer(desk, work, allowed)

    def rpc(method: str, params: Row) -> Row:
        return ref.handle({"id": 1, "method": method, "params": params})["result"]

    tools = rpc("tools/list", {})["tools"]
    ledger = state["ledger"]
    path = Path(sys.modules[type(desk).__module__].__file__ or "")
    same(
        ledger[:2],
        [
            {
                "record": "start",
                "family": row["family"],
                "key_id": row["id"],
                "module": path.stem,
                "seed": t["seed"],
                "world_sha256": sha(path.read_bytes()),
                "bridge_sha256": sha(Path(module.__file__ or "").read_bytes()),
            },
            {"record": "tools", "tools": tools},
        ],
        "ledger startup",
    )
    check_opening(row, t["seed"], ledger[2]["server_reply"])
    records = t["recording"]
    same([x["tool"] for x in records[:2]], ["rpc:initialize", "rpc:tools/list"], "RPC startup")
    same(records[1]["result"]["value"], {"tools": tools}, "advertised catalogue")
    starts = [e["payload"] for e in t["events"] if e["kind"] == "tool_start"]
    finishes = [e["payload"] for e in t["events"] if e["kind"] == "tool_finish"]
    counter: Counter[str] = Counter()
    calls: list[Row] = []
    n = 0
    retrieved = False
    hist = [
        {"role": "system", "content": doc["system_prompt"]},
        {"role": "user", "content": row["ask"]},
        {"role": "assistant", "content": "", "tool_calls": [{"function": opening}]},
    ]

    def deliver(fn: Row) -> None:
        nonlocal n, retrieved
        name = fn["name"]
        args = fn.get("arguments", {})
        call = {"name": name, "arguments": args}
        calls.append(call)
        if name not in allowed:
            text = "MCP RPC error: " + str({"code": -32601, "message": f"unknown tool {name}"})
        else:
            orig = rpc("tools/call", call)
            same(
                ledger[n + 2],
                {
                    "record": "call",
                    "seq": n,
                    "tool": name,
                    "arguments": args,
                    "passed_on": orig,
                    "server_reply": orig,
                },
                "original seeded desk result",
            )
            blank = fault and n == 0
            value = orig | {"content": []} if blank else orig
            cid = f"c-{n:04d}"
            same(
                starts[n],
                {"call_id": cid, "tool": name, "occurrence": counter[name], "arguments": args},
                "tool_start",
            )
            record = records[n + 2]
            same(
                [record["tool"], record["occurrence"], record["arguments_sha256"]],
                [name, counter[name], import_module("arci.hashing").hash_record(args)],
                "recorded call",
            )
            counter[name] += 1
            finish = {
                "call_id": cid,
                "tool": name,
                "ok": not orig["isError"],
                "value": value,
                "error_kind": "tool_error" if orig["isError"] else None,
                "injected_by": "empty_result" if blank else None,
            }
            same(finishes[n], finish, "tool_finish injection")
            same({k: record["result"][k] for k in finish}, finish, "recorded delivery")
            text = (
                doc["stock_sentence"]
                if blank and side == "baseline"
                else "\n".join(b["text"] for b in value["content"])
            )
            if fault and n > 0 and not orig["isError"] and call == opening:
                retrieved = True
            n += 1
        hist.append({"role": "tool", "tool_name": name, "content": text})

    deliver(opening)
    tool_defs = [
        {
            "type": "function",
            "function": {
                "name": x["name"],
                "description": x["description"],
                "parameters": x["inputSchema"],
            },
        }
        for x in tools
    ]
    exchanges = r["exchanges"]
    need(1 <= len(exchanges) == r["steps"] <= 8, "exchange count")
    terminal = False
    answer = None
    for exchange in exchanges:
        need(not terminal, "request after terminal response")
        body = base64.b64decode(exchange["request_b64"], validate=True)
        same(sha(body), exchange["sha256"], "sent byte digest")
        same(
            json.loads(body),
            {
                "model": model,
                "messages": hist,
                "tools": tool_defs,
                "stream": False,
                "think": False,
                "options": {"temperature": 0.7},
            },
            "sent request history",
        )
        if (
            exchange["status"] != 200
            or exchange["response_b64"] is None
            or exchange.get("incomplete_body")
        ):
            if t["termination"] != "timeout":
                require_infra(t, r, exchange)
            else:
                need(exchange is exchanges[-1] and not r["complete"], "unanswered request")
            break
        raw = base64.b64decode(exchange["response_b64"], validate=True)
        try:
            msg = assistant(raw, model)
        except (ValueError, UnicodeError):
            require_infra(t, r, exchange)
            break
        hist.append(msg)
        if not msg.get("tool_calls"):
            need(isinstance(msg["content"], str), "terminal content")
            terminal = True
            answer = msg["content"]
        for wrapper in msg.get("tool_calls", []):
            try:
                fn = function(wrapper)
            except ValueError:
                require_infra(t, r, exchange)
                terminal = True
                break
            if fn["name"] in allowed and n >= 12:
                terminal = True
                break
            deliver(fn)
    same(
        [len(ledger) - 2, len(records) - 2, len(starts), len(finishes)],
        [n] * 4,
        "boundary inventory",
    )
    if r["complete"]:
        same(r["calls"], calls, "receipt calls")
        same([state["answer"], r["answer"]], [answer, answer], "terminal receipt")
        need(terminal or len(exchanges) == 8, "premature completion")
    else:
        need(t["termination"] != "completed", "unfinished receipt")
    same(state["world"], desk.snapshot(), "seeded final world")
    exact = False
    if t["termination"] == "completed":
        passed, exact = grade(answer, expected(row, t["seed"]), desk.snapshot(), record_id(row))
        same(
            [t["contract"]["success"], t["outcome"]],
            [passed, "PASS" if passed else "FAIL"],
            "grade",
        )
    else:
        need(t["outcome"] != "PASS", "noncompleted pass")
    return {
        "task": row["id"],
        "family": row["family"],
        "side": side,
        "pair": t["pair_id"],
        "outcome": t["outcome"],
        "retrieved": retrieved,
        "exact": exact,
    }


def verify(store: Path, receipts: Path, model: str) -> tuple[list[Row], list[Row], list[Row], str]:
    manifest = compiled(store / "descriptor.yaml")
    same(
        manifest.record_sha256,
        read(store / "manifest.json")["record_sha256"],
        "descriptor manifest",
    )
    decision = read(store / "decision.json")
    suite = hasattr(manifest, "suite_id")
    run = manifest.suite_id if suite else store.parent.name
    if suite:
        gate_text = gate(store)
        stop = decision["stopped_at_round"] or len(decision["history"])
    else:
        schema = import_module("arci.schema")
        d = schema.GateDecision.model_validate(decision)
        trials = [schema.TrialEnvelope.model_validate(t) for t in lines(store / "trials.jsonl")]
        need(
            import_module("arci.gate").replay_decision(d, manifest, trials), "clean decision replay"
        )
        gate_text = "Plain pair decision replay matched.\n"
        stop = 1
    items = lines(store / "trials.jsonl")
    schedule = {s.trial_id: s for s in specs(manifest, stop)}
    same(sorted(t["trial_id"] for t in items), sorted(schedule), "scheduled trials")
    events: dict[str, list[Row]] = defaultdict(list)
    for e in lines(store / "events.jsonl"):
        events[e["trial_id"]].append(e)
    same(sorted(events), sorted(schedule), "event inventory")
    doc = read(ROOT / "tasks/tasks.json")
    index = rows()
    observations = []
    exports = []
    ledgers = []
    names = set()
    with tempfile.TemporaryDirectory() as tmp:
        for t in items:
            tid = t["trial_id"]
            s = schedule[tid]
            same(
                [t["spec_sha256"], t["seed"], t["variant"], t["arm"], t["task_id"]],
                [
                    import_module("arci.schedule").spec_sha256(s),
                    s.seed,
                    s.variant,
                    s.arm,
                    s.task_id,
                ],
                tid,
            )
            same(events[tid], t["events"], f"{tid} events")
            name = (
                sha(json.dumps([run, s.task_id, s.seed, s.arm], separators=(",", ":")).encode())
                + ".json"
            )
            names.add(name)
            r = read(receipts / name)
            try:
                observations.append(trial_audit(t, r, index[s.task_id], doc, model, run, Path(tmp)))
            except (ValueError, IndexError, KeyError, TypeError) as exc:
                raise ValueError(f"{tid}: {exc}") from exc
            exports.append(r)
            ledgers.append({"trial_id": tid, "ledger": t["final_state"]["ledger"]})
    same(sorted(names), sorted(p.name for p in receipts.iterdir()), "receipt inventory")
    return observations, exports, ledgers, gate_text
