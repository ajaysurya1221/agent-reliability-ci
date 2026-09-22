"""Human-readable comparison of deterministic trial traces."""

from __future__ import annotations

import hashlib
from typing import Literal

from pydantic import JsonValue

from arci.hashing import canonical_json
from arci.schema import DECISION_TOOL_PREFIX, Divergence, Event, TrialEnvelope

DiffMode = Literal["boundary", "all"]
_BOUNDARY_KINDS = frozenset({"tool_start", "tool_finish", "agent_result", "trial_end"})


def _json(value: object) -> str:
    return canonical_json(value).decode("utf-8")


def _payload_without_ids(event: Event, *excluded: str) -> dict[str, JsonValue]:
    ignored = {"call_id", *excluded}
    return {key: value for key, value in event.payload.items() if key not in ignored}


def _value_digest(value: object) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()[:8]


def step_signature(event: Event) -> str:
    """Return a stable signature containing only the event's semantic content."""
    if event.kind == "tool_start":
        tool = event.payload.get("tool")
        if isinstance(tool, str) and tool.startswith(DECISION_TOOL_PREFIX):
            return (
                f"tool_start tool={_json(tool)} "
                f"occurrence={_json(event.payload.get('occurrence'))} "
                f"arguments#{_value_digest(event.payload.get('arguments', {}))}"
            )
        return (
            f"tool_start tool={_json(tool)} arguments={_json(event.payload.get('arguments', {}))}"
        )
    if event.kind == "tool_finish":
        tool = event.payload.get("tool")
        value = event.payload.get("value")
        status = value.get("status") if isinstance(value, dict) else None
        status_field = (
            (f"status={_json(status)}",)
            if isinstance(tool, str) and tool.startswith(DECISION_TOOL_PREFIX)
            else ()
        )
        return " ".join(
            (
                "tool_finish",
                f"tool={_json(tool)}",
                f"ok={_json(event.payload.get('ok'))}",
                *status_field,
                f"value#{_value_digest(value)}",
                f"error_kind={_json(event.payload.get('error_kind'))}",
                f"injected_by={_json(event.payload.get('injected_by'))}",
            )
        )
    if event.kind == "model_step":
        payload = _payload_without_ids(event, "summary")
        return f"model_step summary={_json(event.payload.get('summary'))} payload={_json(payload)}"
    if event.kind == "agent_result":
        return f"agent_result result={_json(event.payload.get('result'))}"
    if event.kind == "trial_end":
        payload = _payload_without_ids(event)
        return f"trial_end payload={_json(payload)}"
    return event.kind


def _indexed_signatures(trial: TrialEnvelope, mode: DiffMode) -> tuple[tuple[int, str], ...]:
    return tuple(
        (index, step_signature(event))
        for index, event in enumerate(trial.events)
        if mode == "all" or event.kind in _BOUNDARY_KINDS
    )


def _alignment(
    a: TrialEnvelope, b: TrialEnvelope, mode: DiffMode
) -> tuple[Divergence, int | None, int | None]:
    if mode not in {"boundary", "all"}:
        raise ValueError(f"unknown diff mode: {mode}")

    left_steps = _indexed_signatures(a, mode)
    right_steps = _indexed_signatures(b, mode)
    aligned = 0
    while (
        aligned < len(left_steps)
        and aligned < len(right_steps)
        and left_steps[aligned][1] == right_steps[aligned][1]
    ):
        aligned += 1

    left_entry = left_steps[aligned] if aligned < len(left_steps) else None
    right_entry = right_steps[aligned] if aligned < len(right_steps) else None
    left_index = left_entry[0] if left_entry is not None else None
    right_index = right_entry[0] if right_entry is not None else None
    left = left_entry[1] if left_entry is not None else None
    right = right_entry[1] if right_entry is not None else None
    common_prefix = left_index if left_index is not None else len(a.events)
    if left is None and right is None:
        return (
            Divergence(common_prefix=len(a.events), left=None, right=None),
            None,
            None,
        )

    after_injection: str | None = None
    limits = (
        (a.events, left_index if left_index is not None else len(a.events) - 1),
        (b.events, right_index if right_index is not None else len(b.events) - 1),
    )
    for events, limit in limits:
        for event in events[: limit + 1]:
            injected_by = event.payload.get("injected_by")
            if event.kind == "tool_finish" and isinstance(injected_by, str) and injected_by:
                after_injection = injected_by

    return (
        Divergence(
            common_prefix=common_prefix,
            left=left,
            right=right,
            after_injection=after_injection,
        ),
        left_index,
        right_index,
    )


def first_divergence(
    a: TrialEnvelope, b: TrialEnvelope, *, mode: DiffMode = "boundary"
) -> Divergence:
    """Locate the first unequal boundary or full-trace step in two trials."""
    divergence, _left_index, _right_index = _alignment(a, b, mode)
    return divergence


def render_divergence(
    a: TrialEnvelope,
    b: TrialEnvelope,
    d: Divergence,
    *,
    mode: DiffMode = "boundary",
) -> str:
    """Render a compact explanation around a trace divergence."""
    _computed, left_index, right_index = _alignment(a, b, mode)
    mode_line = f"Mode: {mode}."
    if d.left is None and d.right is None:
        return f"{mode_line}\nNo divergence: {d.common_prefix} normalized steps are identical."

    injection = (
        f" after injection {_json(d.after_injection)}" if d.after_injection is not None else ""
    )
    lines = [mode_line, f"First divergence at step {d.common_prefix}{injection}.", "Context:"]

    def append_context(side: str, trial: TrialEnvelope, index: int | None) -> None:
        if index is None:
            lines.append(f"  {side}: <end>")
            return
        start = max(0, index - 2)
        stop = min(len(trial.events), index + 2)
        for position in range(start, stop):
            event = trial.events[position]
            marker = "annotation" if event.kind == "model_step" else "event"
            lines.append(f"  {side} {position} [{marker}]: {step_signature(event)}")

    append_context("left", a, left_index)
    append_context("right", b, right_index)
    return "\n".join(lines)
