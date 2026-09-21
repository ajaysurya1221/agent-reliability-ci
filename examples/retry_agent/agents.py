"""Baseline, retry regression and repaired inventory agents."""

from __future__ import annotations

import random
from collections.abc import Callable

from pydantic import JsonValue

from arci.interfaces import ToolBoxProtocol, ToolFault

Task = dict[str, JsonValue]


def _reserve_arguments(task: Task) -> dict[str, JsonValue]:
    return {
        "order_id": task["order_id"],
        "sku": task["sku"],
        "quantity": task["quantity"],
    }


def _succeeded(value: JsonValue, key: str) -> bool:
    return isinstance(value, dict) and value.get(key) is True


def _reservation_state(task: Task, tools: ToolBoxProtocol) -> bool:
    tools.note_model_step("inspect_reservation")
    state = tools.call("get_reservation", order_id=task["order_id"])
    needs_reservation = not _succeeded(state, "reserved")
    tools.note_model_step("reservation_decision", needs_reservation=needs_reservation)
    return not needs_reservation


def agent_a(task: Task, tools: ToolBoxProtocol, rng: random.Random) -> Task:
    """Baseline: inspect state and retry transient reserve and confirm faults."""
    del rng
    reserved = _reservation_state(task, tools)
    if not reserved:
        for attempt in range(3):
            tools.note_model_step("reserve_attempt", attempt=attempt + 1)
            try:
                reserved = _succeeded(tools.call("reserve", **_reserve_arguments(task)), "reserved")
            except ToolFault:
                continue
            break

    confirmed = False
    if reserved:
        for attempt in range(3):
            tools.note_model_step("confirm_attempt", attempt=attempt + 1)
            try:
                confirmed = _succeeded(
                    tools.call("confirm", order_id=task["order_id"], sku=task["sku"]),
                    "confirmed",
                )
            except ToolFault:
                continue
            break
    tools.note_model_step("completion_decision", confirmed=confirmed)
    return {"success": True}


def agent_b(task: Task, tools: ToolBoxProtocol, rng: random.Random) -> Task:
    """Regression: a reserve timeout is treated as final before confirming."""
    del rng
    reserved = _reservation_state(task, tools)
    if not reserved:
        tools.note_model_step("reserve_once")
        try:
            reserved = _succeeded(tools.call("reserve", **_reserve_arguments(task)), "reserved")
        except ToolFault:
            tools.note_model_step("reserve_fault_skip_to_confirm")

    confirmed = False
    for attempt in range(3):
        tools.note_model_step("confirm_attempt", attempt=attempt + 1)
        try:
            confirmed = _succeeded(
                tools.call("confirm", order_id=task["order_id"], sku=task["sku"]),
                "confirmed",
            )
        except ToolFault:
            continue
        break
    tools.note_model_step("completion_decision", confirmed=confirmed, reserved=reserved)
    return {"success": True}


def _with_retry(
    tools: ToolBoxProtocol,
    operation: str,
    call: Callable[[], JsonValue],
    *,
    attempts: int = 3,
) -> JsonValue:
    for attempt in range(attempts):
        tools.note_model_step(f"{operation}_attempt", attempt=attempt + 1)
        try:
            return call()
        except ToolFault:
            continue
    return None


def agent_c(task: Task, tools: ToolBoxProtocol, rng: random.Random) -> Task:
    """Repair: share one bounded retry helper across both transient operations."""
    del rng
    reserved = _reservation_state(task, tools)
    if not reserved:
        reserved = _succeeded(
            _with_retry(
                tools,
                "reserve",
                lambda: tools.call("reserve", **_reserve_arguments(task)),
            ),
            "reserved",
        )

    confirmed = False
    if reserved:
        confirmed = _succeeded(
            _with_retry(
                tools,
                "confirm",
                lambda: tools.call("confirm", order_id=task["order_id"], sku=task["sku"]),
            ),
            "confirmed",
        )
    tools.note_model_step("completion_decision", confirmed=confirmed)
    return {"success": True}
