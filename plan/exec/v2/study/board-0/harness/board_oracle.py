"""ARCI snapshot and final text scoring."""

import json
from pathlib import Path
from typing import Any

from common import Row, lines, read
from grade import grade
from worlds import expected, record_id, rows, world


def snapshot(task: Row, workdir: str) -> Row:
    work = Path(workdir)
    ledger = lines(work / "ledger.jsonl")
    if not ledger or ledger[0].get("record") != "start" or ledger[0]["key_id"] != task["key_id"]:
        raise ValueError("missing ledger startup")
    answer = read(work / "answer.json") if (work / "answer.json").exists() else {"answer": None}
    return {**answer, "ledger": ledger, "world": json.loads((work / "state.json").read_bytes())}


def passed(task: Row, final_state: dict[str, Any]) -> bool:
    row = rows()[task["key_id"]]
    seed = final_state["ledger"][0]["seed"]
    success, _ = grade(
        final_state["answer"], expected(row, seed), world(row, seed).snapshot(), record_id(row)
    )
    return success
