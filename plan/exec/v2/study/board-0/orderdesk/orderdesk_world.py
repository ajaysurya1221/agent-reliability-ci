"""The order desk as a plain tool set, for the probe only (benchmark Reply-0, study code).

The order desk of runs 2 to 6 (`plan/exec/v2/study/order-desk*/tools.py`, the same file in all six
folders) is built for the LangChain adapter: `make_tools` returns `ToolEnv` holding
`StructuredTool` objects, which the released stdio bridge `arci.mcp_toolset_server` cannot serve
(it wants an object with a `tools` mapping of plain functions and a `snapshot()` method).

This file is that same order desk with the LangChain wrapping taken off. `make_tools` below is the
original function line for line up to its `return`: the four tool functions, their names,
arguments, docstrings and error texts ("unknown order", "unknown SKU") are unchanged, and the
seeded values come from the same `random.Random(seed)` draws in the same order. Only the last
statement differs: it returns the plain functions instead of `StructuredTool` objects. Served with:

    PYTHONPATH=plan/exec/v2/study/reply-0/orderdesk python -P -m arci.mcp_toolset_server \
        --toolset orderdesk_world:make_tools --workdir STATE_DIR --seed 0 --task-file task.json

What this does NOT reproduce: in runs 2 to 6 the model's call passed through LangChain's own
argument check before it reached these functions, so a missing or wrongly typed argument got
LangChain's text there. Over the bridge it gets Python's `TypeError` text instead. Only the two
"unknown ..." replies are the order desk's own words in both settings.

Nothing under src/ uses this file.
"""

from __future__ import annotations

import copy
import random
from collections.abc import Callable, Mapping
from typing import cast

from pydantic import JsonValue


class PlainToolSet:
    """What `arci.mcp_toolset_server` serves: a mapping of functions, and a snapshot."""

    def __init__(
        self,
        tools: Mapping[str, Callable[..., JsonValue]],
        snapshot: Callable[[], dict[str, JsonValue]],
    ) -> None:
        self.tools = tools
        self._snapshot = snapshot

    def snapshot(self) -> dict[str, JsonValue]:
        return self._snapshot()


def make_tools(task: dict[str, JsonValue], seed: int) -> PlainToolSet:
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

    return PlainToolSet(
        {fn.__name__: fn for fn in (lookup_order, check_stock, issue_refund, add_note)},
        snapshot,
    )
