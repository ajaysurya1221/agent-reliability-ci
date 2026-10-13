"""Baseline: confirm the order, reserving it first when needed, with a bounded retry on reserve."""

from __future__ import annotations

import random

from pydantic import JsonValue

from arci.interfaces import ToolBoxProtocol, ToolFault

RESERVE_ATTEMPTS = 3


def _confirmed(value: JsonValue) -> bool:
    return isinstance(value, dict) and value.get("confirmed") is True


def run(
    task: dict[str, JsonValue], tools: ToolBoxProtocol, rng: random.Random
) -> dict[str, JsonValue]:
    del rng
    order_id = task["order_id"]
    if _confirmed(tools.call("confirm", order_id=order_id)):
        return {"confirmed": True}  # the order was already held
    for _attempt in range(RESERVE_ATTEMPTS):
        try:
            tools.call("reserve", order_id=order_id)
        except ToolFault:
            continue  # transient: try again, at most RESERVE_ATTEMPTS times in all
        break
    return {"confirmed": _confirmed(tools.call("confirm", order_id=order_id))}
