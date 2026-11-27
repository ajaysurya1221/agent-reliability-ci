"""Read the store's JSON records and report local integrity failures."""

import argparse
import json
import os
from collections.abc import Callable
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

Row = dict[str, Any]


def atomic_json(path: Path, value: object) -> None:
    with NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        tmp = Path(stream.name)
        try:
            stream.write((json.dumps(value) + "\n").encode())
            stream.flush()
            os.fsync(stream.fileno())
            stream.close()
            tmp.replace(path)
        finally:
            tmp.unlink(missing_ok=True)


def require_receipt_intact(trial: Row) -> None:
    if "SIZE_ZERO_RECEIPT_LOST" in (trial.get("failure_detail") or ""):
        raise ValueError(f"receipt lost for {trial['trial_id']}")


def assignment_receipts(audit: Path, trials: list[Row], manifest: Row) -> dict[str, Row]:
    orders = {t["task_id"]: t["task"]["order_id"] for t in manifest["tasks"]}
    keys = ("run", "round", "order_id", "arm", "seed")
    found: dict[tuple[object, ...], list[Row]] = {}
    receipt_path = audit.with_name("exchanges.jsonl")
    for receipt in rows(receipt_path) if receipt_path.exists() else []:
        found.setdefault(tuple(receipt[k] for k in keys), []).append(receipt)
    result = {}
    for t in trials:
        require_receipt_intact(t)
        key = (
            manifest["suite_id"],
            int(t["pair_id"].split(":")[0][1:]),
            orders[t["task_id"]],
            t["arm"],
            t["seed"],
        )
        matches = found.pop(key, [])
        require(matches, f"missing receipt for {t['trial_id']} {key}")
        require(len(matches) == 1, f"duplicate receipt for {t['trial_id']} {key}")
        require(type(matches[0]["stream_completed"]) is bool, f"invalid completion for {key}")
        result[t["trial_id"]] = matches[0]
    require(not found, f"unexpected receipt {next(iter(found), None)}")
    return result


def rows(path: Path) -> list[Row]:
    return [json.loads(line) for line in path.read_bytes().splitlines()]


def require(value: object, detail: str) -> None:
    if not value:
        raise ValueError(detail)


def counter_cli(counter: Callable[[Path, Path], Row]) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("store", type=Path)
    parser.add_argument("--audit", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(counter(args.store, args.audit), sort_keys=True))
