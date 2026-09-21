"""Deterministic fixture environment and agents for the acceptance suite. FROZEN."""

from __future__ import annotations

import contextlib
import os
import random
import subprocess
import sys
import time
from collections.abc import Callable, Mapping
from pathlib import Path

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
            "block": self._block,
        }

    def _fetch(self, key: str) -> JsonValue:
        return {"key": key, "value": 42}

    def _store(self, value: JsonValue) -> JsonValue:
        self.stored = value
        return {"stored": True}

    def _log(self, msg: str) -> JsonValue:
        self.log.append(msg)
        return None

    def _block(self, pid_file: str, ack_file: str, acked_file: str) -> JsonValue:
        """Never returns. Spawns a descendant and publishes its pid, then waits for the
        parent harness to acknowledge that it has SEEN this call's tool_start, records
        that acknowledgment, and sleeps until killed."""
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(300)"])
        Path(pid_file).write_text(str(child.pid))
        while not Path(ack_file).exists():
            time.sleep(0.02)
        Path(acked_file).write_text("acknowledged while alive")
        time.sleep(300)
        return None

    def snapshot(self) -> dict[str, JsonValue]:
        return {"stored": self.stored, "log": list(self.log)}


def make_world(task: Task, seed: int) -> World:
    return World(task, seed)


class UntouchableWorld(World):
    """Any live tool execution is a test failure; its own state is never the goal state."""

    def __init__(self, task: Task, seed: int) -> None:
        super().__init__(task, seed)
        self.tools = {name: self._forbidden for name in ("fetch", "store", "log", "block")}

    def _forbidden(self, **_: JsonValue) -> JsonValue:
        raise AssertionError("live tool executed during replay")

    def snapshot(self) -> dict[str, JsonValue]:
        return {"stored": "UNTOUCHED", "log": []}


def make_untouchable_world(task: Task, seed: int) -> World:
    return UntouchableWorld(task, seed)


def make_broken_world(task: Task, seed: int) -> World:
    raise RuntimeError("environment factory exploded")


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


def exit_agent(task: Task, tools: ToolBoxProtocol, rng: random.Random) -> Task:
    tools.call("fetch", key="answer")
    os._exit(7)


def chatty_agent(task: Task, tools: ToolBoxProtocol, rng: random.Random) -> Task:
    for i in range(50):
        tools.call("log", msg=f"line {i}")
    return {"success": False}


def block_agent(task: Task, tools: ToolBoxProtocol, rng: random.Random) -> Task:
    tools.call(
        "block",
        pid_file=task["pid_file"],
        ack_file=task["ack_file"],
        acked_file=task["acked_file"],
    )
    return {"success": True}


def catchall_agent(task: Task, tools: ToolBoxProtocol, rng: random.Random) -> Task:
    """Swallows every exception, including ones it has no business swallowing."""
    value: JsonValue = None
    try:
        value = _value(tools.call("fetch", key="answer"))
    except Exception:
        value = None
    with contextlib.suppress(Exception):
        tools.call("store", value=value)
    return {"success": True}
