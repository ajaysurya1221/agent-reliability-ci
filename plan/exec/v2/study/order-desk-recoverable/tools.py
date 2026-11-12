"""A fresh, seeded order desk for each trial; no external service or shared state."""

from __future__ import annotations

import copy
import random
from typing import cast

from langchain_core.tools import StructuredTool
from pydantic import JsonValue

from arci.adapters.langchain import ToolEnv


def make_tools(task: dict[str, JsonValue], seed: int) -> ToolEnv:
    rng = random.Random(seed)
    order_id = str(task["order_id"])
    sku = f"SKU-{rng.randrange(1000, 9999)}"
    order: dict[str, JsonValue] = {
        "sku": sku,
        "total_cents": rng.randrange(1000, 20000),
        "refunded_cents": 0,
        "notes": [],
    }
    stock = rng.randrange(1, 50)

    def lookup_order(order_id: str) -> dict[str, JsonValue]:
        """Read an order's SKU, paid amount, refund and notes before changing it."""
        if order_id != str(task["order_id"]):
            raise ValueError("unknown order")
        return copy.deepcopy(order)

    def check_stock(sku: str) -> int:
        """Return the current available quantity for a SKU."""
        if sku != order["sku"]:
            raise ValueError("unknown SKU")
        return stock

    def issue_refund(order_id: str, amount_cents: int) -> str:
        """Refund the full paid amount; repeating the same refund is idempotent."""
        lookup_order(order_id)
        if amount_cents != order["total_cents"]:
            raise ValueError("refund must equal the paid amount")
        order["refunded_cents"] = amount_cents
        return "refunded"

    def add_note(order_id: str, note: str) -> str:
        """Append an exact service note once; repeating the same note is idempotent."""
        lookup_order(order_id)
        notes = cast(list[JsonValue], order["notes"])
        if note not in notes:
            notes.append(note)
        return "saved"

    def snapshot() -> dict[str, JsonValue]:
        return {"order_id": order_id, "order": copy.deepcopy(order), "stock": stock}

    return ToolEnv(
        [
            StructuredTool.from_function(fn)
            for fn in (lookup_order, check_stock, issue_refund, add_note)
        ],
        snapshot=snapshot,
    )
