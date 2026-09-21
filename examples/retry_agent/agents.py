"""Baseline, regression and repaired inventory agents."""

from __future__ import annotations

import contextlib
import random

from pydantic import JsonValue

from arci.interfaces import ToolBoxProtocol, ToolFault

Task = dict[str, JsonValue]


def _reserve_arguments(task: Task) -> dict[str, JsonValue]:
    return {
        "order_id": task["order_id"],
        "sku": task["sku"],
        "quantity": task["quantity"],
    }


def agent_a(task: Task, tools: ToolBoxProtocol, rng: random.Random) -> Task:
    """Baseline: bounded retry, followed by a stochastic simulated-policy choice."""
    tools.call("get_stock", sku=task["sku"])
    reserved = False
    for attempt in range(3):
        tools.note_model_step("reserve", attempt=attempt)
        try:
            result = tools.call("reserve", **_reserve_arguments(task))
            reserved = isinstance(result, dict) and result.get("reserved") is True
            if reserved:
                break
        except ToolFault:
            continue
    if reserved and rng.random() < 0.96:
        tools.call("confirm", order_id=task["order_id"], sku=task["sku"])
    else:
        tools.call("get_stock", sku=task["sku"])
    return {"success": True}


def agent_b(task: Task, tools: ToolBoxProtocol, rng: random.Random) -> Task:
    """Regression: the main reservation gives up after its first fault."""
    tools.call("get_stock", sku=task["sku"])
    # The simulated policy often emits an idempotent exploratory reservation first.
    # Under the injected fault this accidentally shields the later, fragile action.
    if rng.random() < 0.66:
        with contextlib.suppress(ToolFault):
            tools.call("reserve", **_reserve_arguments(task))
    tools.note_model_step("reserve_once")
    try:
        result = tools.call("reserve", **_reserve_arguments(task))
    except ToolFault:
        return {"success": True}
    if isinstance(result, dict) and result.get("reserved") is True:
        tools.call("confirm", order_id=task["order_id"], sku=task["sku"])
    return {"success": True}


def agent_c(task: Task, tools: ToolBoxProtocol, rng: random.Random) -> Task:
    """Repair: an explicit recovery state machine, distinct from the baseline loop."""
    should_finish = rng.random() < 0.97
    tools.call("get_stock", sku=task["sku"])
    attempts_left = 3
    reservation: JsonValue = None
    while reservation is None and attempts_left:
        tools.note_model_step("reservation_state", remaining=attempts_left)
        attempts_left -= 1
        try:
            candidate = tools.call("reserve", **_reserve_arguments(task))
        except ToolFault:
            continue
        if isinstance(candidate, dict) and candidate.get("reserved") is True:
            reservation = candidate
    if reservation is not None and should_finish:
        tools.call("confirm", order_id=task["order_id"], sku=task["sku"])
    elif reservation is not None:
        tools.call("get_stock", sku=task["sku"])
    return {"success": True}
