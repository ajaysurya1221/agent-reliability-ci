"""Resolve the selected desk and its independent scoring key."""

import importlib
import json
import sys
from pathlib import Path
from typing import Any

from common import ROOT, Row, need

sys.path[:0] = [str(ROOT / "orderdesk"), str(ROOT / "calendardesk")]


def world(row: Row, seed: int) -> Any:
    module = {"orders": "orderdesk_world", "calendar": "calendar_world"}[row["family"]]
    return importlib.import_module(module).make_tools(row["task"], seed)


def expected(row: Row, seed: int) -> int | str:
    if row["family"] == "calendar":
        return importlib.import_module("key").answer(row, seed)
    return world(row, seed).snapshot()["order"]["total_cents"]


def record_id(row: Row) -> str:
    return row["task"]["order_id" if row["family"] == "orders" else "event_id"]


def rows(root: Path = ROOT) -> dict[str, Row]:
    return {r["id"]: r for r in json.loads((root / "tasks/tasks.json").read_bytes())["tasks"]}


def check_opening(row: Row, seed: int, reply: Row) -> None:
    section = row["source"]["field"].split(".")[0]
    target = world(row, seed).snapshot()[section]
    content = reply["content"]
    need(
        reply["isError"] is False
        and len(content) == 1
        and content[0]["type"] == "text"
        and json.dumps(json.loads(content[0]["text"]), sort_keys=True)
        == json.dumps(target, sort_keys=True),
        "original opening differs from seeded target",
    )


def collisions(row: Row, seed: int) -> list[Row]:
    import re

    state = world(row, seed).snapshot()
    section, field = row["source"]["field"].split(".")
    key = state[section][field]
    # The calendar snapshot exposes the target twice. Visit each physical event once.
    if section == "event":
        del state["event"]
        target = f"events.{state['event_id']}.{field}"
    else:
        target = f"{section}.{field}"
    found = []

    def visit(path: str, value: Any) -> None:
        if isinstance(value, dict):
            for name, item in value.items():
                visit(f"{path}.{name}" if path else name, item)
        elif isinstance(value, list):
            for i, item in enumerate(value):
                visit(f"{path}.{i}", item)
        elif path != target:
            same = type(value) is type(key) and key == value
            digits = (
                isinstance(value, str)
                and type(key) is int
                and str(key) in re.findall(r"[0-9]+", value)
            )
            if same or digits:
                found.append({"path": path, "value": value, "key": key})

    visit("", state)
    return found
