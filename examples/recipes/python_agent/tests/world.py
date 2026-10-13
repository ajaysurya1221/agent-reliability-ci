"""Two tools. `confirm` succeeds only for a held order; `reserve` places the hold.

Per seed: 75% of orders arrive already held, and 20% of reserve backends fail twice before
they work. The oracle reads only the final state.
"""

from __future__ import annotations

import random
from collections.abc import Callable, Mapping

from pydantic import JsonValue

HELD_SHARE = 0.75
FLAKY_SHARE = 0.20
FLAKY_FAILURES = 2


class World:
    def __init__(self, task: dict[str, JsonValue], seed: int) -> None:
        self._order_id = str(task["order_id"])
        self._held = random.Random(f"{seed}:held").random() < HELD_SHARE
        flaky = random.Random(f"{seed}:reserve").random() < FLAKY_SHARE
        self._failures_left = FLAKY_FAILURES if flaky else 0
        self._confirmed = False
        self.tools: Mapping[str, Callable[..., JsonValue]] = {
            "reserve": self._reserve,
            "confirm": self._confirm,
        }

    def _reserve(self, order_id: str) -> JsonValue:
        if self._failures_left:
            self._failures_left -= 1
            raise TimeoutError("reserve backend transient timeout")
        self._held = self._held or order_id == self._order_id
        return {"order_id": order_id, "held": self._held}

    def _confirm(self, order_id: str) -> JsonValue:
        self._confirmed = self._confirmed or (self._held and order_id == self._order_id)
        return {"order_id": order_id, "confirmed": self._confirmed}

    def snapshot(self) -> dict[str, JsonValue]:
        return {"order_id": self._order_id, "held": self._held, "confirmed": self._confirmed}


def make_world(task: dict[str, JsonValue], seed: int) -> World:
    return World(task, seed)


def passed(task: dict[str, JsonValue], final_state: dict[str, JsonValue]) -> bool:
    return final_state.get("order_id") == task["order_id"] and final_state.get("confirmed") is True
