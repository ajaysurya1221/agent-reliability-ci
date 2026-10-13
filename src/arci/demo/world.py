"""Seeded inventory scenarios for the retry example.

Each seed independently selects two realistic conditions: 65% of customers
already hold a reservation for the order, while 4% of backend sessions have a
four-call transient ``confirm`` outage. The remaining customers need a new
reservation, and the remaining backend sessions confirm normally.
"""

from __future__ import annotations

import random
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from pydantic import JsonValue

Task = dict[str, JsonValue]
PREEXISTING_RESERVATION_SHARE = 0.65
FLAKY_CONFIRM_SHARE = 0.04
CONFIRM_TRANSIENT_FAILURES = 4


@dataclass(frozen=True)
class Scenario:
    """Environment conditions selected independently from a trial seed."""

    has_reservation: bool
    flaky_confirm: bool


def scenario_for_seed(seed: int) -> Scenario:
    """Return the deterministic scenario for one schedule seed."""
    return Scenario(
        has_reservation=(
            random.Random(f"{seed}:reservation").random() < PREEXISTING_RESERVATION_SHARE
        ),
        flaky_confirm=(random.Random(f"{seed}:backend-confirm").random() < FLAKY_CONFIRM_SHARE),
    )


def _integer(task: Task, key: str) -> int:
    value = task[key]
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{key} must be an integer")
    return value


def _string(task: Task, key: str) -> str:
    value = task[key]
    if not isinstance(value, str):
        raise TypeError(f"{key} must be a string")
    return value


class InventoryWorld:
    def __init__(self, task: Task, seed: int) -> None:
        stock = _integer(task, "stock")
        quantity = _integer(task, "quantity")
        order_id = _string(task, "order_id")
        scenario = scenario_for_seed(seed)
        self._stock = stock
        self._reservations: dict[str, int] = {}
        self._confirmed: list[dict[str, JsonValue]] = []
        self._confirm_failures_remaining = (
            CONFIRM_TRANSIENT_FAILURES if scenario.flaky_confirm else 0
        )
        if scenario.has_reservation:
            self._stock -= quantity
            self._reservations[order_id] = quantity
        self.tools: Mapping[str, Callable[..., JsonValue]] = {
            "get_stock": self._get_stock,
            "get_reservation": self._get_reservation,
            "reserve": self._reserve,
            "confirm": self._confirm,
        }

    def _get_stock(self, sku: str) -> JsonValue:
        return {"sku": sku, "available": self._stock}

    def _get_reservation(self, order_id: str) -> JsonValue:
        quantity = self._reservations.get(order_id)
        return {"order_id": order_id, "reserved": quantity is not None, "quantity": quantity}

    def _reserve(self, order_id: str, sku: str, quantity: int) -> JsonValue:
        existing = self._reservations.get(order_id)
        if existing is not None:
            return {"reserved": existing == quantity, "quantity": existing}
        if quantity <= 0 or quantity > self._stock:
            return {"reserved": False, "quantity": 0}
        self._stock -= quantity
        self._reservations[order_id] = quantity
        return {"reserved": True, "quantity": quantity, "sku": sku}

    def _confirm(self, order_id: str, sku: str) -> JsonValue:
        if self._confirm_failures_remaining:
            self._confirm_failures_remaining -= 1
            raise TimeoutError("confirm backend transient timeout")
        quantity = self._reservations.get(order_id)
        if quantity is None or any(item["order_id"] == order_id for item in self._confirmed):
            return {"confirmed": False}
        self._confirmed.append({"order_id": order_id, "sku": sku, "quantity": quantity})
        return {"confirmed": True}

    def snapshot(self) -> dict[str, JsonValue]:
        return {
            "stock": self._stock,
            "reservations": dict(self._reservations),
            "confirmed": list(self._confirmed),
        }


def make_world(task: Task, seed: int) -> InventoryWorld:
    return InventoryWorld(task, seed)


def oracle(task: Task, final_state: dict[str, JsonValue]) -> bool:
    confirmed = final_state.get("confirmed")
    if not isinstance(confirmed, list) or len(confirmed) != 1:
        return False
    item = confirmed[0]
    return isinstance(item, dict) and item == {
        "order_id": task["order_id"],
        "sku": task["sku"],
        "quantity": task["quantity"],
    }
