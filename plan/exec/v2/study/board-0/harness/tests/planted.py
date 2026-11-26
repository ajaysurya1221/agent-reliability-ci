"""Exercise the independent comparisons on actual released FIFO trial records."""

from __future__ import annotations

import base64
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import audit
from common import ROOT, Row, lines, need, read, sha
from worlds import rows


def check(target: Path, receipts: Path, model: str, run: str, work: Path) -> None:
    doc = read(ROOT / "tasks/tasks.json")
    for side in ("baseline", "candidate"):
        trial = next(t for t in lines(target / "trials.jsonl") if t["arm"] == side)
        name = (
            sha(
                json.dumps(
                    [run, trial["task_id"], trial["seed"], side], separators=(",", ":")
                ).encode()
            )
            + ".json"
        )
        receipt = read(receipts / name)
        row = rows()[trial["task_id"]]
        audit.trial_audit(trial, receipt, row, doc, model, run, work)
        if side == "candidate":
            wrong_record_and_deadline(target, trial, receipt, row, doc, model, run, work)
        for fault in (
            "missing ledger",
            "source digest",
            "wrong injection",
            "wrong delivery",
            "wrong model",
            "receipt calls",
            "wrong original",
        ):
            t = copy.deepcopy(trial)
            r = copy.deepcopy(receipt)
            if fault == "missing ledger":
                del t["final_state"]["ledger"][:]
            elif fault == "source digest":
                t["final_state"]["ledger"][0]["world_sha256"] = "a" * 64
            elif fault == "wrong injection":
                t["recording"][2]["result"]["injected_by"] = None
            elif fault == "wrong original":
                t["final_state"]["ledger"][2]["server_reply"]["content"] = []
            elif fault == "receipt calls":
                r["calls"].clear()
            elif fault == "wrong model":
                x = r["exchanges"][0]
                resp = json.loads(base64.b64decode(x["response_b64"]))
                resp["model"] = "unregistered"
                x["response_b64"] = base64.b64encode(json.dumps(resp).encode()).decode()
            else:
                x = r["exchanges"][0]
                body = json.loads(base64.b64decode(x["request_b64"]))
                body["messages"][-1]["content"] = "different opening"
                raw = json.dumps(body).encode()
                x.update(request_b64=base64.b64encode(raw).decode(), sha256=sha(raw))
            try:
                audit.trial_audit(t, r, row, doc, model, run, work)
            except (ValueError, IndexError):
                continue
            raise AssertionError(f"accepted {side} {fault}")
    # Removing a receipt or trial must be detected even if the remaining records agree.
    key = next(receipts.glob("*.json"))
    data = key.read_bytes()
    key.unlink()
    try:
        try:
            audit.verify(target, receipts, model)
        except FileNotFoundError:
            pass
        else:
            raise AssertionError("accepted missing receipt")
    finally:
        key.write_bytes(data)
    tp = target / "trials.jsonl"
    original = tp.read_bytes()
    try:
        tp.write_bytes(original.split(b"\n", 1)[1])
        try:
            audit.verify(target, receipts, model)
        except ValueError:
            pass
        else:
            raise AssertionError("accepted missing scheduled trial")
    finally:
        tp.write_bytes(original)


def wrong_record_and_deadline(
    target: Path, trial: Row, receipt: Row, row: Row, doc: Row, model: str, run: str, work: Path
) -> None:
    from functools import partial
    from importlib import import_module
    from unittest.mock import patch

    from check_evidence import regrade, target_record
    from count_b import count
    from launcher import jsonl

    changed = copy.deepcopy(trial)
    original = changed["final_state"]["ledger"][2]
    bad = copy.deepcopy(original["server_reply"])
    bad["content"][0]["text"] = json.dumps(target_record(row, trial["seed"] + 1))
    original.update(server_reply=bad, passed_on=bad)
    bridge = import_module("arci.mcp_toolset_server").ToolSetServer

    # Replay reproduces the same server bug as the original. The measured opening
    # was blanked, so the sent bytes, trial grade and released recording still agree.
    def wrong_lookup(self: object, request_id: object, params: Row) -> Row:
        return {"jsonrpc": "2.0", "id": request_id, "result": bad}

    with patch.object(bridge, "_call", wrong_lookup):
        try:
            audit.trial_audit(changed, receipt, row, doc, model, run, work)
        except ValueError as exc:
            need("opening" in str(exc), "audit missed independent target comparison")
        else:
            raise AssertionError("audit accepted wrong record from replayed server")
    store = work / run
    store.mkdir()
    records = lines(target / "trials.jsonl")
    jsonl(store / "trials.jsonl", [changed if t["arm"] == "candidate" else t for t in records])
    jsonl(
        store / "receipts.jsonl", [read(f) for f in (target.parents[1] / "receipts").glob("*.json")]
    )
    try:
        count(store, rows(), model)
    except ValueError as exc:
        need("opening" in str(exc), "Count B missed independent target comparison")
    else:
        raise AssertionError("Count B accepted wrong original opening")
    try:
        regrade(row, changed, receipt, model)
    except ValueError as exc:
        need("opening" in str(exc), "K5 missed independent target comparison")
    else:
        raise AssertionError("K5 accepted wrong original opening")
    for late_event in (False, True):
        record = copy.deepcopy(trial)
        r = copy.deepcopy(receipt)
        if late_event:
            next(e for e in record["events"] if e["kind"] == "tool_finish")["at_ms"] = 121000
        else:
            r["agent_seconds"] = 121
        for verify in (
            partial(regrade, row, record, r, model),
            partial(audit.trial_audit, record, r, row, doc, model, run, work),
        ):
            try:
                verify()
            except ValueError as exc:
                need("deadline" in str(exc), "wrong deadline diagnostic")
            else:
                raise AssertionError("accepted completed trial beyond deadline")


def component(tmp: Path) -> None:
    import os
    import subprocess

    from audit import compiled, specs
    from check_evidence import verify as verify_zip
    from common import descriptor, models, write

    model = models(ROOT / "models.example.json", offline=True)[0]
    doc = read(ROOT / "tasks/tasks.json")
    run = "board0-d1-M1-E"
    # A single plain pair suffices to probe the released before/after fault path.
    cfg = descriptor(doc, model, run, offline=True)
    row = cfg.pop("tasks")[0]
    tid = row.pop("id")
    cfg.pop("suite_id")
    cfg.pop("rule")
    cfg.update(experiment_id=run + "-pair", task_id=tid, task=row, n_per_arm=1)
    target = tmp / run / tid
    path = target / "descriptor.yaml"
    write(path, cfg)
    receipts = tmp / "receipts"
    result = subprocess.run(
        [sys.executable, "-PB", str(ROOT / "harness/fifo.py"), str(path), str(tmp / "stores")],
        env=os.environ | {"BOARD0_RECEIPTS": str(receipts)},
        capture_output=True,
        text=True,
        timeout=90,
    )
    need(result.returncode in (0, 1, 2), result.stdout + result.stderr)
    import shutil

    store = tmp / "stores" / cfg["experiment_id"]
    for name in ("trials.jsonl", "events.jsonl", "decision.json", "manifest.json"):
        shutil.copyfile(store / name, target / name)
    work = tmp / "reference"
    work.mkdir()
    check(target, receipts, model["tag"], run, work)
    seed_sets = []
    for day in (1, 2):
        path = tmp / f"day{day}.yaml"
        write(path, descriptor(doc, model, f"board0-d{day}-M1-E", offline=True))
        manifest = compiled(path)
        seeds = {s.seed for s in specs(manifest, 26)}
        need(
            len(seeds) == 416 and seeds == {s.seed for s in specs(compiled(path), 26)},
            "frozen seeds",
        )
        seed_sets.append(seeds)
    need(seed_sets[0].isdisjoint(seed_sets[1]), "day seeds overlap")
    bad = tmp / "bad.zip"
    bad.write_bytes(b"not an archive")
    side = tmp / "bad.sha256"
    side.write_text("0" * 64)
    try:
        verify_zip(bad, side)
    except ValueError as e:
        need(str(e) == "zip digest", "digest must be checked first")
    else:
        raise AssertionError("accepted wrong archive digest")


if __name__ == "__main__":
    component(Path(sys.argv[1]))
