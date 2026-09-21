"""Deterministic fixture environment and agents for the acceptance suite. FROZEN."""

from __future__ import annotations

import os
import random
import time
from collections.abc import Callable, Mapping

from pydantic import JsonValue

from arci.interfaces import ToolBoxProtocol, ToolFault

Task = dict[str, JsonValue]


class World:
    def __init__(self, task: Task, seed: int) -> None:
        self.stored: JsonValue = None
        self.log: list[str] = []
        self.tools: Mapping[str, Callable[..., JsonValue]] = {
            "fetch": self._fetch,
            "store": self._store,
            "log": self._log,
        }

    def _fetch(self, key: str) -> JsonValue:
        return {"key": key, "value": 42}

    def _store(self, value: JsonValue) -> JsonValue:
        self.stored = value
        return {"stored": True}

    def _log(self, msg: str) -> JsonValue:
        self.log.append(msg)
        return None

    def snapshot(self) -> dict[str, JsonValue]:
        return {"stored": self.stored, "log": list(self.log)}


def make_world(task: Task, seed: int) -> World:
    return World(task, seed)


def oracle(task: Task, final_state: dict[str, JsonValue]) -> bool:
    return final_state.get("stored") == 42


def raising_oracle(task: Task, final_state: dict[str, JsonValue]) -> bool:
    raise RuntimeError("grader exploded")


def _value(result: JsonValue) -> JsonValue:
    return result.get("value") if isinstance(result, dict) else None


def good_agent(task: Task, tools: ToolBoxProtocol, rng: random.Random) -> Task:
    """Retries a failed fetch up to three times."""
    tools.call("log", msg="start")
    value: JsonValue = None
    for attempt in range(3):
        tools.note_model_step("fetch", attempt=attempt)
        try:
            value = _value(tools.call("fetch", key="answer"))
            break
        except ToolFault:
            continue
    tools.call("store", value=value)
    return {"success": True}


def fragile_agent(task: Task, tools: ToolBoxProtocol, rng: random.Random) -> Task:
    """The regression: treats any fetch failure as final and stores nothing useful."""
    tools.call("log", msg="start")
    tools.note_model_step("fetch", attempt=0)
    try:
        value = _value(tools.call("fetch", key="answer"))
    except ToolFault:
        value = None
    tools.call("store", value=value)
    return {"success": True}


def uncaught_agent(task: Task, tools: ToolBoxProtocol, rng: random.Random) -> Task:
    value = _value(tools.call("fetch", key="answer"))  # a ToolFault propagates
    tools.call("store", value=value)
    return {"success": True}


def liar_agent(task: Task, tools: ToolBoxProtocol, rng: random.Random) -> Task:
    return {"success": True}


def hang_agent(task: Task, tools: ToolBoxProtocol, rng: random.Random) -> Task:
    tools.call("fetch", key="answer")
    time.sleep(120)
    return {"success": True}


def exit_agent(task: Task, tools: ToolBoxProtocol, rng: random.Random) -> Task:
    tools.call("fetch", key="answer")
    os._exit(7)


def chatty_agent(task: Task, tools: ToolBoxProtocol, rng: random.Random) -> Task:
    for i in range(50):
        tools.call("log", msg=f"line {i}")
    return {"success": False}
