"""Read-only comparison of selected observations from two native run stores.

This diagnostic neither executes user code nor establishes replay or statistical
success. The existing gate validates each complete store independently.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from enum import Enum
from hashlib import sha256
from pathlib import Path
from typing import Literal

from pydantic import JsonValue

from arci.gate import decide
from arci.hashing import canonical_json
from arci.schedule import build_schedule
from arci.schema import Event, Manifest, ToolCall, TrialEnvelope, TrialSpec, Verdict
from arci.storage import load_run

TraceCheckStatus = Literal["MATCH", "DRIFT", "INVALID"]
_LIMITATIONS = (
    "Compares only the selected observed tool/result trace and terminal state.",
    "Integrity seals and declared scenario equality do not authenticate execution "
    "or verify replay.",
    "Diagnostic status does not replace either source statistical gate verdict.",
)
_EMPTY_FIXTURES = "Fixture identities are empty; environment equality is declaration-only."


@dataclass(frozen=True)
class TraceSource:
    """Identifiers and independently derived gate status for one selected source."""

    experiment_id: str
    trial_id: str
    manifest_sha256: str
    trial_sha256: str
    decision_sha256: str
    trial_outcome: str
    gate_verdict: str
    gate_exit_code: int


@dataclass(frozen=True)
class TraceDifference:
    """First unequal normalized step, with hashes of the subtrees at its pointer."""

    step: int
    path: str
    baseline_kind: str | None
    candidate_kind: str | None
    baseline_sha256: str | None
    candidate_sha256: str | None


@dataclass(frozen=True)
class TraceCheckResult:
    """A diagnostic, kept separate from both sources' statistical decisions."""

    status: TraceCheckStatus
    reason: str
    baseline: TraceSource | None = None
    candidate: TraceSource | None = None
    first_difference: TraceDifference | None = None
    limitations: tuple[str, ...] = _LIMITATIONS
    schema_version: Literal["arci-trace-check/1"] = "arci-trace-check/1"

    @property
    def exit_code(self) -> int:
        return {"MATCH": 0, "DRIFT": 1, "INVALID": 3}[self.status]


@dataclass(frozen=True)
class _Loaded:
    source: TraceSource | None
    manifest: Manifest | None = None
    spec: TrialSpec | None = None
    trial: TrialEnvelope | None = None
    error: Literal["store", "selection", "events"] | None = None


def _load_source(path: Path | str, trial_id: str) -> _Loaded:
    source: TraceSource | None = None
    try:
        manifest, trials = load_run(path)
        decision = decide(manifest, trials)
        selected = [trial for trial in trials if trial.trial_id == trial_id]
        if len(selected) != 1:
            return _Loaded(None, error="selection")
        trial = selected[0]
        source = TraceSource(
            manifest.experiment_id,
            trial.trial_id,
            manifest.record_sha256,
            trial.record_sha256,
            decision.record_sha256,
            trial.outcome.value,
            decision.verdict.value,
            decision.exit_code,
        )
        if decision.verdict is Verdict.ERROR:
            return _Loaded(source, error="store")
        specs = [spec for spec in build_schedule(manifest) if spec.trial_id == trial_id]
        if len(specs) != 1:
            return _Loaded(source, error="selection")
        if not _valid_events(trial):
            return _Loaded(source, error="events")
        return _Loaded(source, manifest, specs[0], trial)
    except (OSError, ValueError, TypeError, UnicodeError, RecursionError):
        # Parser/OS exceptions can include user data and paths; never render them.
        return _Loaded(source, error="store")


def _start_call(event: Event) -> ToolCall | None:
    payload = event.payload
    call_id, tool = payload.get("call_id"), payload.get("tool")
    arguments, occurrence = payload.get("arguments"), payload.get("occurrence")
    if (
        not isinstance(call_id, str)
        or not isinstance(tool, str)
        or not isinstance(arguments, dict)
        or not isinstance(occurrence, int)
        or isinstance(occurrence, bool)
        or occurrence < 0
    ):
        return None
    return ToolCall(call_id=call_id, tool=tool, arguments=arguments, occurrence=occurrence)


def _valid_payload(event: Event) -> bool:
    payload = event.payload
    if event.kind == "trial_start":
        seed = payload.get("seed")
        return (
            isinstance(seed, int)
            and not isinstance(seed, bool)
            and isinstance(payload.get("arm"), str)
            and isinstance(payload.get("variant"), str)
        )
    if event.kind == "model_step":
        return isinstance(payload.get("summary"), str)
    if event.kind == "tool_start":
        return _start_call(event) is not None
    if event.kind == "tool_finish":
        return (
            isinstance(payload.get("call_id"), str)
            and isinstance(payload.get("tool"), str)
            and isinstance(payload.get("ok"), bool)
            and "value" in payload
            and (payload.get("error_kind") is None or isinstance(payload.get("error_kind"), str))
            and (payload.get("injected_by") is None or isinstance(payload.get("injected_by"), str))
        )
    if event.kind == "agent_result":
        return isinstance(payload.get("result"), dict)
    return event.kind == "trial_end" and not payload


def _valid_events(trial: TrialEnvelope) -> bool:
    events = trial.events
    if not events or events[0].kind != "trial_start" or events[-1].kind != "trial_end":
        return False
    initial = events[0].payload
    if (
        initial.get("seed") != trial.seed
        or initial.get("arm") != trial.arm
        or initial.get("variant") != trial.variant
    ):
        return False
    starts: dict[str, ToolCall] = {}
    finished: set[str] = set()
    result_seen = False
    for index, event in enumerate(events):
        if (
            event.trial_id != trial.trial_id
            or event.seq != index
            or (event.kind == "trial_start" and index != 0)
            or (event.kind == "trial_end" and index != len(events) - 1)
            or not _valid_payload(event)
        ):
            return False
        if event.kind == "agent_result":
            if result_seen:
                return False
            result_seen = True
        elif event.kind == "tool_start":
            call = _start_call(event)
            if call is None or call.call_id in starts:
                return False
            starts[call.call_id] = call
        elif event.kind == "tool_finish":
            call_id = event.payload["call_id"]
            if not isinstance(call_id, str):
                return False
            start = starts.get(call_id)
            if start is None or start.tool != event.payload["tool"] or call_id in finished:
                return False
            finished.add(call_id)
    unfinished = [
        call.model_dump(mode="json") for key, call in starts.items() if key not in finished
    ]
    declared = [call.model_dump(mode="json") for call in trial.incomplete_calls]
    return canonical_json(unfinished) == canonical_json(declared)


def _scenario(manifest: Manifest, spec: TrialSpec) -> bytes:
    """Compare declarations without resolving imports or verifying fixture contents."""
    return canonical_json(
        {
            "task": spec.task,
            "seed": spec.seed,
            "faults": [fault.model_dump(mode="json") for fault in spec.condition.faults],
            "contract": manifest.contract.model_dump(mode="json"),
            "budgets": spec.budgets.model_dump(mode="json"),
            "execution_kind": "python" if spec.agent is not None else "command",
            "toolset": spec.toolset,
            "mcp_server": spec.mcp_server.model_dump(mode="json") if spec.mcp_server else None,
            "decisions": spec.decisions.model_dump(mode="json") if spec.decisions else None,
            "fixtures_sha256": manifest.fixtures_sha256,
        }
    )


def _projection(trial: TrialEnvelope) -> list[dict[str, JsonValue]]:
    steps: list[dict[str, JsonValue]] = []
    for event in trial.events:
        if event.kind not in {"tool_start", "tool_finish", "agent_result"}:
            continue
        payload = {
            key: value
            for key, value in event.payload.items()
            if event.kind == "agent_result" or key != "call_id"
        }
        steps.append({"kind": event.kind, "payload": payload})
    terminal: dict[str, JsonValue] = {
        "outcome": trial.outcome.value,
        "termination": trial.termination.value,
        "agent_claimed_success": trial.agent_claimed_success,
        "contract": trial.contract.model_dump(mode="json") if trial.contract else None,
        "failure_fingerprint": trial.failure_fingerprint,
        "failure_detail": trial.failure_detail,
        "final_state": trial.final_state,
    }
    steps.append({"kind": "terminal", "payload": terminal})
    return steps


@dataclass(frozen=True)
class TraceStepContext:
    """Containing record only; presence comes from the comparator's subtree hash."""

    location: Literal["event", "terminal", "absent"]
    event_kind: str | None = None
    seq: int | None = None
    tool: str | None = None
    occurrence: int | None = None
    value_present: bool = False


def trace_step_context(trial: TrialEnvelope, step: int, *, value_present: bool) -> TraceStepContext:
    """Map a normalized position after check_traces validates the selected events.

    This does not evaluate pointers or compare values. In particular a missing
    subtree can still have a containing event. Finishes resolve occurrence via
    the validated call link, never a payload guess or event position.
    """
    if step < 0:
        return TraceStepContext("absent", value_present=value_present)
    starts: dict[str, ToolCall] = {}
    position = 0
    for event in trial.events:
        if event.kind not in {"tool_start", "tool_finish", "agent_result"}:
            continue
        call = None
        if event.kind == "tool_start":
            call = _start_call(event)
            if call is not None:
                starts[call.call_id] = call
        elif event.kind == "tool_finish":
            call_id = event.payload.get("call_id")
            if isinstance(call_id, str):
                call = starts.get(call_id)
        if position == step:
            tool = None
            if call is not None:
                # Bound before escaping too; escaped controls never reach terminals.
                tool = json.dumps(call.tool[:120], ensure_ascii=True)[1:-1]
                if len(call.tool) > 120 or len(tool) > 120:
                    tool = tool[:117] + "..."
            return TraceStepContext(
                "event",
                event.kind,
                event.seq,
                tool,
                call.occurrence if call is not None else None,
                value_present,
            )
        position += 1
    return TraceStepContext(
        "terminal" if position == step else "absent", value_present=value_present
    )


class _Missing(Enum):
    VALUE = 0


_Compared = JsonValue | _Missing


def _pointer_token(key: str) -> str:
    return key.replace("~", "~0").replace("/", "~1")


def _locate(left: JsonValue, right: JsonValue, path: str = "") -> tuple[str, _Compared, _Compared]:
    """Descend only via canonical-byte inequality, never Python scalar equality."""
    if isinstance(left, dict) and isinstance(right, dict):
        for key in sorted(left.keys() | right.keys()):
            child_path = path + "/" + _pointer_token(key)
            if key not in left:
                return child_path, _Missing.VALUE, right[key]
            if key not in right:
                return child_path, left[key], _Missing.VALUE
            if canonical_json(left[key]) != canonical_json(right[key]):
                return _locate(left[key], right[key], child_path)
    elif isinstance(left, list) and isinstance(right, list):
        for index in range(max(len(left), len(right))):
            child_path = f"{path}/{index}"
            if index >= len(left):
                return child_path, _Missing.VALUE, right[index]
            if index >= len(right):
                return child_path, left[index], _Missing.VALUE
            if canonical_json(left[index]) != canonical_json(right[index]):
                return _locate(left[index], right[index], child_path)
    return path, left, right


def _digest(value: _Compared) -> str | None:
    return None if isinstance(value, _Missing) else sha256(canonical_json(value)).hexdigest()


def _first_difference(
    left: list[dict[str, JsonValue]], right: list[dict[str, JsonValue]]
) -> TraceDifference | None:
    for index in range(max(len(left), len(right))):
        a, b = (
            left[index] if index < len(left) else None,
            right[index] if index < len(right) else None,
        )
        if a is not None and b is not None:
            if canonical_json(a) == canonical_json(b):
                continue
            path, left_value, right_value = _locate(a, b)
        else:
            path = ""
            left_value, right_value = (
                a if a is not None else _Missing.VALUE,
                b if b is not None else _Missing.VALUE,
            )
        return TraceDifference(
            index,
            path,
            str(a["kind"]) if a is not None and not isinstance(left_value, _Missing) else None,
            str(b["kind"]) if b is not None and not isinstance(right_value, _Missing) else None,
            _digest(left_value),
            _digest(right_value),
        )
    return None


def check_traces(
    baseline_run: Path | str,
    baseline_trial_id: str,
    candidate_run: Path | str,
    candidate_trial_id: str,
) -> TraceCheckResult:
    """Validate both stores, then compare their selected declared scenarios and traces."""
    baseline = _load_source(baseline_run, baseline_trial_id)
    candidate = _load_source(candidate_run, candidate_trial_id)
    for label, loaded in (("Baseline", baseline), ("Candidate", candidate)):
        if loaded.error is not None:
            messages = {
                "store": f"{label} store is invalid or unavailable.",
                "selection": f"{label} trial selection is not unique and available.",
                "events": f"{label} selected trace is invalid.",
            }
            return TraceCheckResult(
                "INVALID", messages[loaded.error], baseline.source, candidate.source
            )
    assert (
        baseline.manifest is not None and baseline.spec is not None and baseline.trial is not None
    )
    assert (
        candidate.manifest is not None
        and candidate.spec is not None
        and candidate.trial is not None
    )
    if _scenario(baseline.manifest, baseline.spec) != _scenario(candidate.manifest, candidate.spec):
        return TraceCheckResult(
            "INVALID",
            "Selected trials declare different scenarios.",
            baseline.source,
            candidate.source,
        )
    limitations = _LIMITATIONS
    if not baseline.manifest.fixtures_sha256:
        limitations += (_EMPTY_FIXTURES,)
    difference = _first_difference(_projection(baseline.trial), _projection(candidate.trial))
    return TraceCheckResult(
        "MATCH" if difference is None else "DRIFT",
        "Selected normalized traces match."
        if difference is None
        else "Selected normalized traces differ.",
        baseline.source,
        candidate.source,
        difference,
        limitations,
    )


def render_trace_check(
    result: TraceCheckResult, *, output_format: Literal["text", "json"] = "text"
) -> str:
    """Render only provenance, fixed diagnostics, paths and full comparison hashes."""
    if output_format == "json":
        return canonical_json(asdict(result)).decode("utf-8")
    if output_format != "text":
        raise ValueError("Unsupported trace-check output format.")
    lines = [f"{result.status}: {result.reason}"]
    for label, source in (("Baseline", result.baseline), ("Candidate", result.candidate)):
        if source is None:
            lines.append(f"{label}: unavailable.")
            continue
        lines.append(
            f"{label}: trial outcome {source.trial_outcome}; statistical gate "
            f"{source.gate_verdict} (exit {source.gate_exit_code})."
        )
        lines.append(
            f"  Experiment {canonical_json(source.experiment_id).decode()}; "
            f"trial {canonical_json(source.trial_id).decode()}."
        )
        lines.append(f"  Manifest SHA-256: {source.manifest_sha256}")
        lines.append(f"  Trial SHA-256: {source.trial_sha256}")
        lines.append(f"  Decision SHA-256: {source.decision_sha256}")
    difference = result.first_difference
    if difference is not None:
        lines.append(
            f"First difference: step {difference.step}, "
            f"path {canonical_json(difference.path).decode()}."
        )
        lines.append(
            f"  Baseline {difference.baseline_kind or '<missing>'}: "
            f"{difference.baseline_sha256 or '<missing>'}"
        )
        lines.append(
            f"  Candidate {difference.candidate_kind or '<missing>'}: "
            f"{difference.candidate_sha256 or '<missing>'}"
        )
    lines.extend(f"Limitation: {limitation}" for limitation in result.limitations)
    return "\n".join(lines)
