"""Human-readable comparison of deterministic trial traces."""

from __future__ import annotations

from pydantic import JsonValue

from arci.hashing import canonical_json
from arci.schema import Divergence, Event, TrialEnvelope


def _json(value: object) -> str:
    return canonical_json(value).decode("utf-8")


def _payload_without_ids(event: Event, *excluded: str) -> dict[str, JsonValue]:
    ignored = {"call_id", *excluded}
    return {key: value for key, value in event.payload.items() if key not in ignored}


def step_signature(event: Event) -> str:
    """Return a stable signature containing only the event's semantic content."""
    if event.kind == "tool_start":
        return (
            f"tool_start tool={_json(event.payload.get('tool'))} "
            f"arguments={_json(event.payload.get('arguments', {}))}"
        )
    if event.kind == "tool_finish":
        return " ".join(
            (
                "tool_finish",
                f"tool={_json(event.payload.get('tool'))}",
                f"ok={_json(event.payload.get('ok'))}",
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


def first_divergence(a: TrialEnvelope, b: TrialEnvelope) -> Divergence:
    """Locate the first unequal semantic step in two trial traces."""
    left_signatures = tuple(step_signature(event) for event in a.events)
    right_signatures = tuple(step_signature(event) for event in b.events)
    common = 0
    while (
        common < len(left_signatures)
        and common < len(right_signatures)
        and left_signatures[common] == right_signatures[common]
    ):
        common += 1

    left = left_signatures[common] if common < len(left_signatures) else None
    right = right_signatures[common] if common < len(right_signatures) else None
    if left is None and right is None:
        return Divergence(common_prefix=common, left=None, right=None)

    after_injection: str | None = None
    for position in range(common + 1):
        for events in (a.events, b.events):
            if position >= len(events):
                continue
            event = events[position]
            injected_by = event.payload.get("injected_by")
            if event.kind == "tool_finish" and isinstance(injected_by, str) and injected_by:
                after_injection = injected_by

    return Divergence(
        common_prefix=common,
        left=left,
        right=right,
        after_injection=after_injection,
    )


def render_divergence(a: TrialEnvelope, b: TrialEnvelope, d: Divergence) -> str:
    """Render a compact explanation around a trace divergence."""
    if d.left is None and d.right is None:
        return f"No divergence: {d.common_prefix} normalized steps are identical."

    injection = (
        f" after injection {_json(d.after_injection)}" if d.after_injection is not None else ""
    )
    lines = [f"First divergence at step {d.common_prefix}{injection}.", "Context:"]
    start = max(0, d.common_prefix - 2)
    for index in range(start, d.common_prefix):
        lines.append(f"  {index}: both  {step_signature(a.events[index])}")

    def signature_at(trial: TrialEnvelope, index: int) -> str:
        return step_signature(trial.events[index]) if index < len(trial.events) else "<end>"

    for index in range(d.common_prefix, d.common_prefix + 2):
        left = signature_at(a, index)
        right = signature_at(b, index)
        if index > d.common_prefix and left == "<end>" and right == "<end>":
            break
        lines.append(f"  {index}: left  {left}")
        lines.append(f"  {index}: right {right}")
    return "\n".join(lines)
