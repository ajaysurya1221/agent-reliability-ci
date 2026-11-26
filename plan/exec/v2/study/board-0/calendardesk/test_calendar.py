import json
import os
import re
import subprocess
import sys
from itertools import pairwise
from pathlib import Path
from typing import Any

import pytest
from calendar_world import make_tools
from key import answer

DESK = Path(__file__).resolve().parent
ROWS: list[dict[str, Any]] = json.loads((DESK / "tasks.json").read_text(encoding="utf-8"))
FIELDS = {
    "title": "string",
    "room": "string",
    "start_minute": "integer",
    "duration_minutes": "integer",
    "attendee_count": "integer",
    "organiser": "string",
}


def test_task_rows() -> None:
    assert [row["id"] for row in ROWS] == [f"K-k{i}" for i in range(1, 9)]
    assert len({row["task"]["event_id"] for row in ROWS}) == 8
    assert {row["source"]["field"] for row in ROWS} == {f"event.{field}" for field in FIELDS}
    for row in ROWS:
        assert set(row) == {"id", "family", "ask", "opening", "source", "answer_type", "task"}
        assert row["family"] == "calendar"
        event_id = row["task"]["event_id"]
        assert row["task"] == {"event_id": event_id}
        assert re.fullmatch(r"EVT-[\w-]+", event_id)
        assert row["opening"] == {"name": "lookup_event", "arguments": {"event_id": event_id}}
        field = row["source"]["field"].removeprefix("event.")
        assert row["source"] == {"kind": "world_state", "field": f"event.{field}"}
        assert row["answer_type"] == FIELDS[field]
        assert re.fullmatch(r"[^.!?\n]+\?", row["ask"])
        assert event_id in row["ask"]
        assert not re.search(r"retry|try again|format", row["ask"], re.IGNORECASE)


@pytest.mark.parametrize("row", ROWS, ids=[row["id"] for row in ROWS])
def test_lookup_and_key(row: dict[str, Any]) -> None:
    field = row["source"]["field"].removeprefix("event.")
    for seed in range(100):
        desk = make_tools(row["task"], seed)
        event = desk.tools[row["opening"]["name"]](**row["opening"]["arguments"])
        expected = answer(row, seed)
        assert type(expected) is (int if row["answer_type"] == "integer" else str)
        assert expected == event[field]


def test_seed_variation() -> None:
    values = [tuple(answer(row, seed) for row in ROWS) for seed in range(101)]
    assert (
        sum(
            all(a != b for a, b in zip(left, right, strict=True))
            for left, right in pairwise(values)
        )
        >= 95
    )
    for column in zip(*values, strict=True):
        assert len(set(column)) >= 12


def test_snapshot_and_distractors() -> None:
    task = ROWS[0]["task"]
    desk = make_tools(task, 42)
    snapshot = desk.snapshot()
    assert snapshot == make_tools(task, 42).snapshot()
    assert json.loads(json.dumps(snapshot, allow_nan=False)) == snapshot
    events = snapshot["events"]
    rooms = snapshot["rooms"]
    assert isinstance(events, dict) and isinstance(rooms, dict)
    assert 3 <= len(events) == len(rooms) <= 4
    assert snapshot["event"] == events[task["event_id"]]
    seen_rooms: set[str] = set()
    for event_id, record in events.items():
        event = desk.tools["lookup_event"](event_id=event_id)
        assert event == record
        for field, kind in FIELDS.items():
            assert type(event[field]) is (int if kind == "integer" else str)
        room = event["room"]
        attendees = event["attendee_count"]
        assert isinstance(room, str) and isinstance(attendees, int)
        seen_rooms.add(room)
        details = desk.tools["check_room"](room=room)
        assert details == rooms[room]
        assert type(details["floor"]) is int
        capacity = details["capacity"]
        assert type(capacity) is int and capacity >= attendees
        event.clear()
        details.clear()
    assert seen_rooms == set(rooms)
    events.clear()
    rooms.clear()
    assert desk.snapshot() == make_tools(task, 42).snapshot()


def test_unknown_ids() -> None:
    desk = make_tools(ROWS[0]["task"], 0)
    with pytest.raises(ValueError, match=r"^unknown event$"):
        desk.tools["lookup_event"](event_id="missing")
    with pytest.raises(ValueError, match=r"^unknown room$"):
        desk.tools["check_room"](room="missing")


def test_stdio_bridge(tmp_path: Path) -> None:
    row = ROWS[0]
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps(row["task"]), encoding="utf-8")
    requests = [
        {"id": 1, "method": "initialize"},
        {"method": "notifications/initialized"},
        {"id": 2, "method": "tools/list"},
        {"id": 3, "method": "tools/call", "params": row["opening"]},
    ]
    process = subprocess.run(
        [
            sys.executable,
            "-P",
            "-m",
            "arci.mcp_toolset_server",
            "--toolset",
            "calendar_world:make_tools",
            "--workdir",
            str(tmp_path),
            "--seed",
            "73",
            "--task-file",
            str(task_file),
        ],
        env={**os.environ, "PYTHONPATH": str(DESK)},
        input="".join(json.dumps({"jsonrpc": "2.0", **req}) + "\n" for req in requests),
        capture_output=True,
        text=True,
        timeout=15,
        check=True,
    )
    replies = [json.loads(line) for line in process.stdout.splitlines()]
    assert [reply["id"] for reply in replies] == [1, 2, 3]
    assert "tools" in replies[0]["result"]["capabilities"]
    schemas = {tool["name"]: tool["inputSchema"] for tool in replies[1]["result"]["tools"]}
    assert set(schemas) == {"lookup_event", "check_room"}
    for name, arg in (("lookup_event", "event_id"), ("check_room", "room")):
        assert schemas[name]["required"] == [arg]
        assert schemas[name]["properties"] == {arg: {"type": "string"}}
    result = replies[2]["result"]
    assert result["isError"] is False
    expected = make_tools(row["task"], 73).snapshot()
    assert json.loads(result["content"][0]["text"]) == expected["event"]
    assert json.loads((tmp_path / "state.json").read_text(encoding="utf-8")) == expected
