"""Candidate: v1 with the retry removed; one transient reserve fault loses the order."""

from __future__ import annotations

import random

from pydantic import JsonValue

from arci.interfaces import ToolBoxProtocol, ToolFault


def _confirmed(value: JsonValue) -> bool:
    return isinstance(value, dict) and value.get("confirmed") is True


def run(
    task: dict[str, JsonValue], tools: ToolBoxProtocol, rng: random.Random
) -> dict[str, JsonValue]:
    del rng
    order_id = task["order_id"]
    if _confirmed(tools.call("confirm", order_id=order_id)):
        return {"confirmed": True}  # the order was already held
    try:
        tools.call("reserve", order_id=order_id)
    except ToolFault:
        return {"confirmed": False}  # gives up on the first fault
    return {"confirmed": _confirmed(tools.call("confirm", order_id=order_id))}
