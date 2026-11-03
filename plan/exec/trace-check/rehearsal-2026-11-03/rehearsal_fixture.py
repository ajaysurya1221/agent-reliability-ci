"""Offline QA fixture: change reporting metadata, preserve the packaged agent's policy."""

from __future__ import annotations

import random

from pydantic import JsonValue

from arci.demo.agents import agent_a
from arci.interfaces import ToolBoxProtocol


def variant(
    task: dict[str, JsonValue], tools: ToolBoxProtocol, rng: random.Random
) -> dict[str, JsonValue]:
    result = agent_a(task, tools, rng)
    return {**result, "diagnostic_label": "rehearsal-v2"}
