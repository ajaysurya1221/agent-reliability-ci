"""ARCI grader entry points. Only the answer and registered key enter the score."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from tasks.reply0_grade import passes  # noqa: E402

KEY_FILE = HERE / "answer_key.json"


# Syntax only. Cross-record delivery comparisons belong to the independent audit.
LEDGER_FIELDS = {
    "arm": {"arm": str, "rules": str, "server": str},
    "task": {"key_id": str},
    "start": {
        "argv": list,
        "module_root": (str, type(None)),
        "sha256": dict,
        "protocolVersion": str,
        "serverInfo": dict,
    },
    "norm": {"code": str, "detail": str},
    "refused": {"tool": str, "arguments": dict},
    "call": {
        "seq": int,
        "tool": str,
        "arguments": dict,
        "server_reply": dict,
        "passed_on": dict,
        "rule": (str, type(None)),
    },
}


def snapshot(task: dict[str, Any], workdir: str) -> dict[str, Any]:
    directory = Path(workdir)
    ledger = [json.loads(line) for line in (directory / "ledger.jsonl").read_bytes().splitlines()]
    if not ledger or any(
        not isinstance(row, dict) or not isinstance(row.get("record"), str) for row in ledger
    ):
        raise ValueError("empty or invalid ledger")
    for tag in ("arm", "task", "start"):
        if sum(r["record"] == tag for r in ledger) != 1:
            raise ValueError(f"expected exactly one {tag} record")
    seq = 0
    for row in ledger:
        tag = row["record"]
        fields = LEDGER_FIELDS.get(tag)
        if fields is None or any(
            k not in row or not isinstance(row[k], kind) for k, kind in fields.items()
        ):
            raise ValueError("broken ledger record")
        if tag == "call":
            if type(row["seq"]) is not int or row["seq"] != seq:
                raise ValueError("broken call sequence")
            seq += 1
    answer = directory / "answer.json"
    return {
        "ledger": ledger,
        "answer_present": answer.is_file(),
        "answer": json.loads(answer.read_bytes())["answer"] if answer.is_file() else None,
        "world": json.loads((directory / "state.json").read_bytes())
        if task["cell"] == "C0"
        else None,
    }


def passed(task: dict[str, Any], final_state: dict[str, Any]) -> bool:
    key = json.loads(KEY_FILE.read_bytes())[task["key_id"]]
    expect = key["expect"]
    if key["world_key"] == "order.total_cents":
        cents = final_state["world"]["order"]["total_cents"]
        if type(cents) is not int:
            raise ValueError("invalid seeded order total")
        expect = [str(cents)]
    return passes(final_state["answer"], expect, key["decoys"])
