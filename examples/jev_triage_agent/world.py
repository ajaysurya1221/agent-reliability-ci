"""Seeded support tickets and the MCP-backed triage environment."""

from __future__ import annotations

import random
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TypeAlias, cast

JsonPrimitive: TypeAlias = bool | int | float | str | None
JsonValue: TypeAlias = JsonPrimitive | list["JsonValue"] | dict[str, "JsonValue"]
Task: TypeAlias = dict[str, JsonValue]


@dataclass(frozen=True)
class Scenario:
    ticket_id: str
    text: str
    department: str
    refund_requested: bool
    policy_supports: bool
    frustration: int
    action: str


SCENARIOS = (
    Scenario(
        ticket_id="ticket-refund",
        text="I was charged twice for order A-104. Please refund the duplicate charge.",
        department="billing",
        refund_requested=True,
        policy_supports=True,
        frustration=1,
        action="issue_refund",
    ),
    Scenario(
        ticket_id="ticket-bug",
        text="The desktop app crashes whenever I attach a PDF to a new message.",
        department="technical",
        refund_requested=False,
        policy_supports=False,
        frustration=2,
        action="reply",
    ),
    Scenario(
        ticket_id="ticket-pricing",
        text="Which plan includes audit-log exports, and what does it cost for 20 seats?",
        department="sales",
        refund_requested=False,
        policy_supports=False,
        frustration=0,
        action="reply",
    ),
)


def ticket_index_for_seed(seed: int) -> int:
    """Select a public ticket without exposing its hidden label in the task."""
    return random.Random(f"{seed}:triage-ticket").randrange(len(SCENARIOS))


def scenario_for_seed(seed: int) -> Scenario:
    """Return one of the seeded ticket scenarios, including its hidden ground truth."""
    return SCENARIOS[ticket_index_for_seed(seed)]


def public_task(*, calibration: dict[str, float] | None = None) -> Task:
    """Return the task shown to the agent; no expected department or action is included."""
    tickets: list[JsonValue] = []
    for scenario in SCENARIOS:
        ticket: dict[str, JsonValue] = {
            "ticket_id": scenario.ticket_id,
            "text": scenario.text,
        }
        if calibration is not None:
            ticket["calibration"] = dict(calibration)
        tickets.append(ticket)
    return {"tickets": tickets}


def _ticket_from_task(task: Task, seed: int) -> dict[str, JsonValue]:
    raw_tickets = task.get("tickets")
    if not isinstance(raw_tickets, list) or len(raw_tickets) != len(SCENARIOS):
        raise TypeError("task tickets do not match the triage fixture")
    raw_ticket = raw_tickets[ticket_index_for_seed(seed)]
    if not isinstance(raw_ticket, dict):
        raise TypeError("selected ticket must be an object")
    return cast(dict[str, JsonValue], raw_ticket)


class TriageWorld:
    def __init__(self, task: Task, seed: int) -> None:
        self._scenario = scenario_for_seed(seed)
        ticket = _ticket_from_task(task, seed)
        if ticket.get("ticket_id") != self._scenario.ticket_id or ticket.get("text") != (
            self._scenario.text
        ):
            raise ValueError("selected task ticket does not match the seeded scenario")
        self._action: str | None = None
        self._detail: JsonValue = None
        self.tools: Mapping[str, Callable[..., JsonValue]] = {
            "issue_refund": self._issue_refund,
            "escalate": self._escalate,
            "reply": self._reply,
        }

    def _record(self, action: str, detail: JsonValue) -> JsonValue:
        if self._action is not None:
            return {"accepted": False, "reason": "an action was already taken"}
        self._action = action
        self._detail = detail
        return {"accepted": True, "action": action}

    def _issue_refund(self, ticket_id: str) -> JsonValue:
        return self._record("issue_refund", {"ticket_id": ticket_id})

    def _escalate(self, ticket_id: str, reason: str) -> JsonValue:
        return self._record("escalate", {"ticket_id": ticket_id, "reason": reason})

    def _reply(self, ticket_id: str, message: str) -> JsonValue:
        return self._record("reply", {"ticket_id": ticket_id, "message": message})

    def snapshot(self) -> dict[str, JsonValue]:
        return {
            "ticket_id": self._scenario.ticket_id,
            "action": self._action,
            "detail": self._detail,
            "ground_truth_action": self._scenario.action,
        }


def make_world(task: Task, seed: int) -> TriageWorld:
    return TriageWorld(task, seed)


def oracle(task: Task, final_state: dict[str, JsonValue]) -> bool:
    """Accept the seeded ground-truth action or the approved human-escalation fallback."""
    del task
    action = final_state.get("action")
    expected = final_state.get("ground_truth_action")
    ticket_id = final_state.get("ticket_id")
    detail = final_state.get("detail")
    acted_on_ticket = isinstance(detail, dict) and detail.get("ticket_id") == ticket_id
    return (
        isinstance(action, str) and acted_on_ticket and (action == expected or action == "escalate")
    )
