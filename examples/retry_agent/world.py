"""Small deterministic inventory-reservation environment for the retry example."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from pydantic import JsonValue

Task = dict[str, JsonValue]


class InventoryWorld:
    def __init__(self, task: Task, seed: int) -> None:
        del seed
        stock = task["stock"]
        if not isinstance(stock, int) or isinstance(stock, bool):
            raise TypeError("stock must be an integer")
        self._stock = stock
        self._reservations: dict[str, int] = {}
        self._confirmed: list[dict[str, JsonValue]] = []
        self.tools: Mapping[str, Callable[..., JsonValue]] = {
            "get_stock": self._get_stock,
            "reserve": self._reserve,
            "confirm": self._confirm,
        }

    def _get_stock(self, sku: str) -> JsonValue:
        return {"sku": sku, "available": self._stock}

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
