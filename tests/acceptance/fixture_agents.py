"""Deterministic fixture environment and agents for the acceptance suite. FROZEN."""

from __future__ import annotations

import atexit
import contextlib
import os
import random
import subprocess
import sys
import time
from collections.abc import Callable, Mapping
from pathlib import Path

from pydantic import JsonValue

from arci.interfaces import BudgetExceeded, ToolBoxProtocol, ToolFault
from arci.schema import Bucket, FaultSpec, ToolCall, ToolResult

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


def hanging_oracle(task: Task, final_state: dict[str, JsonValue]) -> bool:
    time.sleep(300)
    return True


def noisy_oracle(task: Task, final_state: dict[str, JsonValue]) -> bool:
    raise RuntimeError(
        f"grader exploded at {time.time()} in pid {os.getpid()} obj 0x{id(task):012x}"
    )


def dict_oracle(task: Task, final_state: dict[str, JsonValue]) -> bool:
    return {"success": False}  # pyright: ignore[reportReturnType]  # truthy, and wrong


async def async_oracle(task: Task, final_state: dict[str, JsonValue]) -> bool:
    return False  # calling this yields a truthy coroutine


def detaching_oracle(task: Task, final_state: dict[str, JsonValue]) -> bool:
    """Returns promptly but leaves a detached child holding the grader's stdout open."""
    subprocess.Popen([sys.executable, "-c", "import time; time.sleep(12)"], start_new_session=True)
    return final_state.get("stored") == 42


class BrokenPerturbation:
    """An injector with a bug. That is a harness fault, never an agent failure."""

    name = "broken_perturbation"
    bucket = Bucket.FALSIFY

    def before(self, call: ToolCall, rng: random.Random) -> ToolResult | None:
        raise RuntimeError("injector broken")

    def after(self, call: ToolCall, result: ToolResult, rng: random.Random) -> ToolResult:
        return result


def broken_perturbation(fault: FaultSpec) -> BrokenPerturbation:
    return BrokenPerturbation()


class BadBeforePerturbation(BrokenPerturbation):
    def before(self, call: ToolCall, rng: random.Random) -> ToolResult | None:
        return "bad"  # pyright: ignore[reportReturnType]


class BadAfterPerturbation(BrokenPerturbation):
    def before(self, call: ToolCall, rng: random.Random) -> ToolResult | None:
        return None

    def after(self, call: ToolCall, result: ToolResult, rng: random.Random) -> ToolResult:
        return None  # pyright: ignore[reportReturnType]


class ExitingPerturbation(BrokenPerturbation):
    def before(self, call: ToolCall, rng: random.Random) -> ToolResult | None:
        raise SystemExit("injector bailed out")


def bad_before_perturbation(fault: FaultSpec) -> BrokenPerturbation:
    return BadBeforePerturbation()


def bad_after_perturbation(fault: FaultSpec) -> BrokenPerturbation:
    return BadAfterPerturbation()


def exiting_perturbation(fault: FaultSpec) -> BrokenPerturbation:
    return ExitingPerturbation()


def exploding_factory(fault: FaultSpec) -> BrokenPerturbation:
    raise RuntimeError("this injector cannot even be built")


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


def swallowing_agent(task: Task, tools: ToolBoxProtocol, rng: random.Random) -> Task:
    """Does the work despite a broken injector by swallowing whatever it raised."""
    value: JsonValue = 42
    with contextlib.suppress(Exception):
        value = _value(tools.call("fetch", key="answer"))
    tools.call("store", value=42 if value is None else value)
    return {"success": True}


def budget_swallower(task: Task, tools: ToolBoxProtocol, rng: random.Random) -> Task:
    """Reaches the goal state, then blows its budget and hides it."""
    tools.call("store", value=42)
    for i in range(50):
        try:
            tools.call("log", msg=f"line {i}")
        except BudgetExceeded:
            break
    return {"success": True}


def garbage_agent(task: Task, tools: ToolBoxProtocol, rng: random.Random) -> Task:
    """Writes junk straight onto the protocol channel, as a stray fd write might."""
    tools.call("store", value=42)
    os.write(1, b"\xff\xfe not json\n")
    os.write(1, b'{"worker_result": 42}\n')
    os.write(1, b'{"kind": "tool_start", "payload": {"occurrence": -1}}\n')
    return {"success": True}


def mutating_agent(task: Task, tools: ToolBoxProtocol, rng: random.Random) -> Task:
    result = tools.call("fetch", key="answer")
    value = _value(result)
    if isinstance(result, dict):
        result["value"] = 999  # must not reach the recording or the emitted events
    tools.call("store", value=value)
    return {"success": True}


def atexit_hang_agent(task: Task, tools: ToolBoxProtocol, rng: random.Random) -> Task:
    tools.call("store", value=42)
    atexit.register(time.sleep, 300)
    return {"success": True}


def atexit_exit_agent(task: Task, tools: ToolBoxProtocol, rng: random.Random) -> Task:
    tools.call("store", value=42)
    atexit.register(os._exit, 7)
    return {"success": True}


def orphan_agent(task: Task, tools: ToolBoxProtocol, rng: random.Random) -> Task:
    """Succeeds, but leaves a background process behind."""
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(300)"])
    Path(str(task["pid_file"])).write_text(str(child.pid))
    tools.call("store", value=42)
    return {"success": True}


def swallow_everything_agent(task: Task, tools: ToolBoxProtocol, rng: random.Random) -> Task:
    """Reaches the goal state while swallowing anything at all, BaseException included."""
    with contextlib.suppress(BaseException):
        tools.call("fetch", key="answer")
    tools.call("store", value=42)
    return {"success": True}


def swallow_then_hang_agent(task: Task, tools: ToolBoxProtocol, rng: random.Random) -> Task:
    with contextlib.suppress(Exception):
        tools.call("fetch", key="answer")
    time.sleep(300)
    return {"success": True}


def swallow_then_exit_agent(task: Task, tools: ToolBoxProtocol, rng: random.Random) -> Task:
    with contextlib.suppress(Exception):
        tools.call("fetch", key="answer")
    os._exit(7)


def budget_then_exit_agent(task: Task, tools: ToolBoxProtocol, rng: random.Random) -> Task:
    tools.call("store", value=42)
    for i in range(50):
        try:
            tools.call("log", msg=f"line {i}")
        except BudgetExceeded:
            os._exit(7)
    return {"success": True}


def nan_agent(task: Task, tools: ToolBoxProtocol, rng: random.Random) -> Task:
    tools.call("store", value=42)
    tools.note_model_step("confidence", value=float("nan"))  # not JSON: the agent's own bug
    return {"success": True}


def surrogate_agent(task: Task, tools: ToolBoxProtocol, rng: random.Random) -> Task:
    tools.call("store", value=42)
    tools.call("log", msg=chr(0xD800))  # not encodable as UTF-8
    return {"success": True}
