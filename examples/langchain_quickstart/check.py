"""Grade business state only; an agent's claimed success never decides the grade."""

from __future__ import annotations

from pydantic import JsonValue


def check(task: dict[str, JsonValue], final_state: dict[str, JsonValue]) -> bool:
    state = final_state.get("state")
    if not isinstance(state, dict) or state.get("order_id") != task["order_id"]:
        return False
    order = state.get("order")
    if not isinstance(order, dict):
        return False
    action = task["action"]
    refund = order.get("total_cents") if action in {"refund", "refund_note"} else 0
    notes = (
        []
        if action == "refund"
        else ["refunded" if action == "refund_note" else f"stock: {state.get('stock')}"]
    )
    return order.get("refunded_cents") == refund and order.get("notes") == notes
