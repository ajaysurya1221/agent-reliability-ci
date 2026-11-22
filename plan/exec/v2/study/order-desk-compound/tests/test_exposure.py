"""First-exchange receipts follow the serialized request and its own streamed answer."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import httpx
import pytest

STUDY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STUDY))

from exposure import FirstExchange, verify  # noqa: E402


@pytest.mark.parametrize("damage", ["none", "extra", "argument", "reply", "system", "task"])
def test_first_request_only(tmp_path: Path, damage: str) -> None:
    task = json.loads((STUDY / "tasks.jsonl").read_text().splitlines()[0])
    output = tmp_path / "evidence"
    exchange = FirstExchange(str(output), "candidate", task, 17, "system", "null")
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": "system"},
        {"role": "user", "content": task["input"]},
        {
            "role": "assistant",
            "tool_calls": [
                {"function": {"name": "check_stock", "arguments": {"sku": task["order_id"]}}}
            ],
        },
        {"role": "tool", "content": "Error: unknown SKU"},
        {
            "role": "assistant",
            "tool_calls": [
                {"function": {"name": "lookup_order", "arguments": {"order_id": task["order_id"]}}}
            ],
        },
        {"role": "tool", "content": "null"},
    ]
    valid = json.dumps({"messages": messages})
    if damage == "extra":
        messages.append({"role": "tool", "content": "real order"})
    elif damage == "argument":
        messages[2]["tool_calls"][0]["function"]["arguments"] = {"sku": "wrong"}
    elif damage == "reply":
        messages[5]["content"] = "different"
    elif damage in ("system", "task"):
        messages[int(damage == "task")]["content"] = "different"
    first = httpx.Request("POST", "http://localhost/api/chat", json={"messages": messages})
    exchange.on_request(first)
    second = httpx.Request("POST", first.url, content=valid)
    exchange.on_request(second)
    assistant = '{"done":true,"message":{"role":"assistant","content":"ok"}}'
    unrelated = httpx.Response(200, request=second, text=assistant)
    exchange.on_response(unrelated)
    assert list(unrelated.iter_lines()) == [assistant]
    assert not exchange.assistant
    response = httpx.Response(200, request=first, text=assistant)
    exchange.on_response(response)
    assert list(response.iter_lines()) == [assistant]
    exchange.record()
    assert json.loads(output.read_text()) == {
        "arm": "candidate",
        "task_id": task["id"],
        "seed": 17,
        "first_request_matches": damage == "none",
        "assistant_response": True,
    }


@pytest.mark.parametrize(
    ("status", "frame"),
    [
        (500, {"done": True, "message": {"role": "assistant"}}),
        (200, {"done": False, "message": {"role": "assistant"}}),
        (200, {"done": True, "message": {"role": "tool"}}),
        (200, {"done": True, "message": {"role": "assistant"}, "done_reason": "load"}),
        (200, {"error": "backend failed"}),
    ],
)
def test_no_completed_assistant(tmp_path: Path, status: int, frame: dict[str, Any]) -> None:
    task = json.loads((STUDY / "tasks.jsonl").read_text().splitlines()[0])
    exchange = FirstExchange(str(tmp_path), "candidate", task, 17, "system", "null")
    first = httpx.Request("POST", "http://localhost/api/chat", json={"messages": exchange.messages})
    exchange.on_request(first)
    response = httpx.Response(status, request=first, json=frame)
    exchange.on_response(response)
    assert list(response.iter_lines()) == [response.text]
    assert exchange.matches and not exchange.assistant
    exchange.record()  # Unwritable destination leaves the trial alone.


def test_receipts_must_cover_all_assignments(tmp_path: Path) -> None:
    trial = {"arm": "baseline", "task_id": "desk-03", "seed": 1}
    trials = tmp_path / "trials.jsonl"
    trials.write_text(json.dumps(trial) + "\n")
    receipts = tmp_path / "receipts.jsonl"
    good = {**trial, "first_request_matches": True, "assistant_response": True}
    for rows in (
        [],
        [good, good],
        [{**good, "seed": 2}],
        [{**good, "assistant_response": False}],
        [{**good, "first_request_matches": False}],
    ):
        receipts.write_text("".join(json.dumps(row) + "\n" for row in rows))
        with pytest.raises(ValueError):
            verify(trials, receipts)
    receipts.write_text(json.dumps(good) + "\n")
    assert verify(trials, receipts).startswith("1 assignments")
