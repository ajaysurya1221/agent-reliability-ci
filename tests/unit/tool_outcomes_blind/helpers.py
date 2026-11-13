"""Fixture builders for the blind tool-outcomes tests. Not a test module itself.

Built only from src/arci/schema.py (TrialEnvelope, Event, Outcome, Termination); no
implementation module (report.py, suite_report.py, html_report.py) is read here.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from pydantic import JsonValue

from arci.schema import Event, EventKind, Outcome, Termination, TrialEnvelope

SHA = "0" * 64

_counter = 0


def _next_id() -> str:
    global _counter
    _counter += 1
    return f"auto-{_counter}"


def ev(
    trial_id: str,
    seq: int,
    kind: EventKind,
    payload: dict[str, JsonValue],
) -> Event:
    return Event(trial_id=trial_id, seq=seq, kind=kind, payload=payload)


def start(trial_id: str, seq: int, tool: JsonValue) -> Event:
    return ev(trial_id, seq, "tool_start", {"tool": tool})


def finish(
    trial_id: str,
    seq: int,
    tool: JsonValue,
    *,
    ok: JsonValue,
    injected_by: JsonValue = "__absent__",
) -> Event:
    """A tool_finish event. `injected_by` left at the sentinel omits the key entirely."""
    payload: dict[str, JsonValue] = {"tool": tool, "ok": ok}
    if injected_by != "__absent__":
        payload["injected_by"] = injected_by
    return ev(trial_id, seq, "tool_finish", payload)


def trial(
    trial_id: str | None = None,
    arm: Literal["baseline", "candidate"] = "baseline",
    *,
    outcome: Outcome = Outcome.PASS,
    events: Sequence[Event] = (),
    task_id: str = "task",
    condition_id: str = "clean",
    pair_id: str | None = None,
    variant: str = "v",
    seed: int = 0,
    termination: Termination | None = None,
) -> TrialEnvelope:
    """A minimal, validly-sealed TrialEnvelope with the given arm/outcome/events."""
    tid = trial_id or _next_id()
    if termination is None:
        termination = (
            Termination.COMPLETED if outcome is not Outcome.ERROR else Termination.HARNESS_ERROR
        )
    return TrialEnvelope.create(
        spec_sha256=SHA,
        experiment_id="exp-blind",
        trial_id=tid,
        pair_id=pair_id or tid,
        arm=arm,
        variant=variant,
        task_id=task_id,
        condition_id=condition_id,
        seed=seed,
        outcome=outcome,
        termination=termination,
        events=tuple(events),
    )
