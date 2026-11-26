"""Read-only calendar tools for Board-0's stdio MCP server."""

from __future__ import annotations

import random
from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass

from pydantic import JsonValue


def _pairs(first: str, second: str) -> tuple[str, ...]:
    return tuple(f"{a} {b}" for a in first.split() for b in second.split())


_TITLES = _pairs(
    "Budget Community Design Finance Garden Library Market Outreach Product Safety Service Travel",
    "Briefing Clinic Forum Handover Meeting Orientation Panel Review Seminar Session Talk Workshop",
)
_ROOMS = _pairs(
    "Alder Ash Aspen Beech Birch Cedar Elm Hazel Juniper Linden Maple Oak Pine Rowan Spruce Willow",
    "Annex Atrium Gallery Hall Loft Lounge Pavilion Studio Suite Terrace Theatre Wing",
)
_ORGANISERS = _pairs(
    "Ada Amir Anika Ben Elena Farah Hugo Iris Jonah Leila Maya Nora Ravi Sam Theo Zoe",
    "Bell Chen Costa Das Evans Fox Green Khan Lee Malik Park Reed Silva Stone West Wong",
)


@dataclass
class CalendarDesk:
    tools: Mapping[str, Callable[..., dict[str, JsonValue]]]
    _state: dict[str, JsonValue]

    def snapshot(self) -> dict[str, JsonValue]:
        return deepcopy(self._state)


def make_tools(task: dict[str, JsonValue], seed: int) -> CalendarDesk:
    target = str(task["event_id"])
    rng = random.Random(seed)
    # A shared trial seed should not give different task IDs identical event details.
    rng.seed(f"{rng.getrandbits(128)}:{target}")
    event_ids = [target]
    while len(event_ids) < 3:
        candidate = f"EVT-{rng.randrange(1000, 10000)}"
        if candidate not in event_ids:
            event_ids.append(candidate)
    count = len(event_ids)
    titles = rng.sample(_TITLES, count)
    rooms = rng.sample(_ROOMS, count)
    organisers = rng.sample(_ORGANISERS, count)
    starts = rng.sample(range(7 * 60, 20 * 60), count)
    durations = rng.sample(range(15, 241), count)
    attendance = rng.sample(range(2, 501), count)
    floors = rng.sample(range(1, 25), count)
    events: dict[str, JsonValue] = {}
    room_details: dict[str, JsonValue] = {}
    for i, event_id in enumerate(event_ids):
        events[event_id] = {
            "title": titles[i],
            "room": rooms[i],
            "start_minute": starts[i],
            "duration_minutes": durations[i],
            "attendee_count": attendance[i],
            "organiser": organisers[i],
        }
        room_details[rooms[i]] = {"capacity": rng.randint(attendance[i], 600), "floor": floors[i]}

    def lookup_event(event_id: str) -> dict[str, JsonValue]:
        """Look up a calendar event by its event ID."""
        event = events.get(event_id)
        if not isinstance(event, dict):
            raise ValueError("unknown event")
        return event.copy()

    def check_room(room: str) -> dict[str, JsonValue]:
        """Look up a room's capacity and floor by name."""
        details = room_details.get(room)
        if not isinstance(details, dict):
            raise ValueError("unknown room")
        return details.copy()

    return CalendarDesk(
        {"lookup_event": lookup_event, "check_room": check_room},
        {"event_id": target, "event": events[target], "events": events, "rooms": room_details},
    )
