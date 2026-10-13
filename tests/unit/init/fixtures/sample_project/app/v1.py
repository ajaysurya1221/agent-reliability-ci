"""Baseline agent: reserves the order and retries a transient fault twice."""

from __future__ import annotations

import random

from pydantic import JsonValue

from arci.interfaces import ToolBoxProtocol, ToolFault

NAME = "v1"  # not callable: `arci init --baseline app.v1:NAME` is refused


def run(
    task: dict[str, JsonValue], tools: ToolBoxProtocol, rng: random.Random
) -> dict[str, JsonValue]:
    del rng
    for _attempt in range(3):
        try:
            tools.call("reserve", order_id=task.get("order_id", "o-1"))
        except ToolFault:
            continue
        break
    return {"done": True}
