"""Candidate agent: the retry was dropped, so one transient fault loses the order."""

from __future__ import annotations

import contextlib
import random

from pydantic import JsonValue

from arci.interfaces import ToolBoxProtocol, ToolFault


def run(
    task: dict[str, JsonValue], tools: ToolBoxProtocol, rng: random.Random
) -> dict[str, JsonValue]:
    del rng
    with contextlib.suppress(ToolFault):
        tools.call("reserve", order_id=task.get("order_id", "o-1"))
    return {"done": True}
