"""One tool, `reserve`, whose first call times out on about a third of the seeds."""

from __future__ import annotations

import random
from collections.abc import Callable, Mapping

from pydantic import JsonValue

TRANSIENT_SHARE = 0.35


class World:
    def __init__(self, task: dict[str, JsonValue], seed: int) -> None:
        del task
        self._failures_left = (
            1 if random.Random(f"{seed}:reserve").random() < TRANSIENT_SHARE else 0
        )
        self._reserved = False
        self.tools: Mapping[str, Callable[..., JsonValue]] = {"reserve": self._reserve}

    def _reserve(self, order_id: str) -> JsonValue:
        if self._failures_left:
            self._failures_left -= 1
            raise TimeoutError("reserve backend transient timeout")
        self._reserved = True
        return {"order_id": order_id, "reserved": True}

    def snapshot(self) -> dict[str, JsonValue]:
        return {"reserved": self._reserved}


def make_world(task: dict[str, JsonValue], seed: int) -> World:
    return World(task, seed)


def passed(task: dict[str, JsonValue], final_state: dict[str, JsonValue]) -> bool:
    del task
    return final_state.get("reserved") is True
