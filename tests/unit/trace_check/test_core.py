"""Stored, sealed fixtures exercise diagnostics without executing user code."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import JsonValue

from arci.hashing import canonical_json
from arci.schedule import build_schedule, spec_sha256
from arci.schema import (
    ArmSpec,
    Bucket,
    Budgets,
    CommandSpec,
    Condition,
    ContractResult,
    ContractSpec,
    DecisionSpec,
    Event,
    FaultSpec,
    Manifest,
    McpServerSpec,
    Outcome,
    RecordedCall,
    Termination,
    ToolCall,
    ToolResult,
    TrialEnvelope,
    TrialSpec,
    Violation,
)


def manifest(**changes: Any) -> Manifest:
    data: dict[str, Any] = {
        "experiment_id": "stored",
        "task_id": "task",
        "task": {"question": "private-payload"},
        "toolset": "never_import.environment:factory",
        "contract": ContractSpec(oracle="never_import.oracle:grade"),
        "baseline": ArmSpec(label="old", agent="never_import.old:agent"),
        "candidate": ArmSpec(label="new", agent="never_import.new:agent"),
        "conditions": (Condition(condition_id="clean"),),
        "n_per_arm": 1,
        "fixtures_sha256": "opaque fixture identity",
    }
    return Manifest.create(**(data | changes))


def events(spec: TrialSpec, *, value: JsonValue = 7) -> tuple[Event, ...]:
    payloads: tuple[tuple[str, dict[str, JsonValue]], ...] = (
        ("trial_start", {"seed": spec.seed, "arm": spec.arm, "variant": spec.variant}),
        (
            "tool_start",
            {"call_id": "first", "tool": "fetch", "occurrence": 0, "arguments": {"q": 1}},
        ),
        (
            "tool_finish",
            {
                "call_id": "first",
                "tool": "fetch",
                "ok": True,
                "value": value,
                "error_kind": None,
                "injected_by": None,
            },
        ),
        ("agent_result", {"result": {"success": True}}),
        ("trial_end", {}),
    )
    return tuple(
        Event.model_validate({"trial_id": spec.trial_id, "seq": i, "kind": k, "payload": p})
        for i, (k, p) in enumerate(payloads)
    )


def envelope(spec: TrialSpec, **changes: Any) -> TrialEnvelope:
    data: dict[str, Any] = {
        "spec_sha256": spec_sha256(spec),
        "experiment_id": spec.experiment_id,
        "trial_id": spec.trial_id,
        "pair_id": spec.pair_id,
        "arm": spec.arm,
        "variant": spec.variant,
        "task_id": spec.task_id,
        "condition_id": spec.condition.condition_id,
        "seed": spec.seed,
        "outcome": Outcome.PASS,
        "termination": Termination.COMPLETED,
        "agent_claimed_success": True,
        "contract": ContractResult(success=True),
        "events": events(spec),
        "final_state": {"answer": 7},
    }
    return TrialEnvelope.create(**(data | changes))


def reseal(trial: TrialEnvelope, **changes: Any) -> TrialEnvelope:
    return TrialEnvelope.create(**(trial.model_dump() | changes))


def replace_event(trial: TrialEnvelope, index: int, **payload: JsonValue) -> TrialEnvelope:
    items = list(trial.events)
    old = items[index]
    items[index] = old.model_copy(update={"payload": old.payload | payload})
    return reseal(trial, events=tuple(items))


def renumber(items: tuple[Event, ...]) -> tuple[Event, ...]:
    return tuple(item.model_copy(update={"seq": i}) for i, item in enumerate(items))


def store(
    path: Path,
    definition: Manifest | None = None,
    transform: Callable[[TrialEnvelope], TrialEnvelope] | None = None,
) -> tuple[Path, str]:
    definition = definition or manifest()
    path.mkdir()
    trials = [envelope(spec) for spec in build_schedule(definition)]
    if transform is not None:
        trials[0] = transform(trials[0])
    (path / "manifest.json").write_text(definition.model_dump_json())
    (path / "trials.jsonl").write_text("\n".join(trial.model_dump_json() for trial in trials))
    return path, trials[0].trial_id


def compare(left: tuple[Path, str], right: tuple[Path, str]) -> dict[str, Any]:
    # A missing new API is a test failure while the first red phase is recorded.
    try:
        from arci.trace_check import check_traces, render_trace_check
    except ImportError as exc:
        pytest.fail(f"trace-check API is not implemented: {exc}")
    result = check_traces(*left, *right)
    document = cast(dict[str, Any], json.loads(render_trace_check(result, output_format="json")))
    assert result.status == document["status"]
    assert result.exit_code == {"MATCH": 0, "DRIFT": 1, "INVALID": 3}[result.status]
    assert set(document) == {
        "schema_version",
        "status",
        "reason",
        "baseline",
        "candidate",
        "first_difference",
        "limitations",
    }
    assert document["schema_version"] == "arci-trace-check/1"
    return document


def test_match_keeps_trial_outcome_separate_from_inconclusive_gate(tmp_path: Path) -> None:
    left = store(tmp_path / "a")
    result = compare(left, left)
    assert result["status"] == "MATCH"
    assert result["first_difference"] is None
    assert result["baseline"]["trial_outcome"] == "PASS"
    assert result["baseline"]["gate_verdict"] == "INCONCLUSIVE"
    assert result["baseline"]["gate_exit_code"] == 2
    assert set(result["baseline"]) == {
        "experiment_id",
        "trial_id",
        "manifest_sha256",
        "trial_sha256",
        "decision_sha256",
        "trial_outcome",
        "gate_verdict",
        "gate_exit_code",
    }


@pytest.mark.parametrize("a,b", [(True, 1), (False, 0), (1, 1.0), ({"x": 1}, {"x": 1.0})])
def test_canonical_types_decide_equality_and_difference_location(
    tmp_path: Path, a: JsonValue, b: JsonValue
) -> None:
    left = store(tmp_path / "a", transform=lambda t: replace_event(t, 2, value=a))
    right = store(tmp_path / "b", transform=lambda t: replace_event(t, 2, value=b))
    result = compare(left, right)
    assert result["status"] == "DRIFT"
    difference = result["first_difference"]
    assert difference["step"] == 1
    assert difference["path"] == ("/payload/value/x" if isinstance(a, dict) else "/payload/value")
    assert difference["baseline_sha256"] != difference["candidate_sha256"]


def test_short_display_hash_collision_is_still_drift(tmp_path: Path) -> None:
    assert hashlib.sha256(b"69235").hexdigest()[:8] == hashlib.sha256(b"95303").hexdigest()[:8]
    left = store(tmp_path / "a", transform=lambda t: replace_event(t, 2, value=69235))
    right = store(tmp_path / "b", transform=lambda t: replace_event(t, 2, value=95303))
    result = compare(left, right)
    assert result["status"] == "DRIFT"
    assert len(result["first_difference"]["baseline_sha256"]) == 64
    assert (
        result["first_difference"]["baseline_sha256"]
        != result["first_difference"]["candidate_sha256"]
    )


def test_missing_null_and_json_pointer_escaping(tmp_path: Path) -> None:
    left = store(tmp_path / "a", transform=lambda t: replace_event(t, 2, value={}))
    right = store(tmp_path / "b", transform=lambda t: replace_event(t, 2, value={"a~/b": None}))
    difference = compare(left, right)["first_difference"]
    assert difference["path"] == "/payload/value/a~0~1b"
    assert difference["baseline_sha256"] is None
    assert difference["candidate_sha256"] == hashlib.sha256(b"null").hexdigest()
    assert difference["baseline_kind"] is None
    assert difference["candidate_kind"] == "tool_finish"


def test_ignores_only_wrappers_call_ids_annotations_and_discovery_recording(tmp_path: Path) -> None:
    def mutate(trial: TrialEnvelope) -> TrialEnvelope:
        items = [e.model_copy(update={"at_ms": 123.0}) for e in trial.events]
        for index in (1, 2):
            items[index] = items[index].model_copy(
                update={"payload": items[index].payload | {"call_id": "renamed"}}
            )
        items.insert(
            1,
            Event(
                trial_id=trial.trial_id,
                seq=0,
                kind="model_step",
                payload={"summary": "private annotation"},
            ),
        )
        recording = RecordedCall(
            tool="rpc:tools/list",
            arguments_sha256="0" * 64,
            occurrence=0,
            result=ToolResult(
                call_id="discovery", tool="rpc:tools/list", ok=True, value={"tools": []}
            ),
        )
        return reseal(trial, events=renumber(tuple(items)), recording=(recording,))

    left = store(tmp_path / "a")
    right = store(
        tmp_path / "b", manifest(experiment_id="other", task_id="renamed", alpha=0.1), mutate
    )
    assert compare(left, right)["status"] == "MATCH"


@pytest.mark.parametrize("field", ["call_id", "duration_ms", "at_ms", "record_sha256", "seq"])
def test_nested_user_metadata_is_never_ignored(tmp_path: Path, field: str) -> None:
    left = store(tmp_path / "a", transform=lambda t: replace_event(t, 2, value={field: 1}))
    right = store(tmp_path / "b", transform=lambda t: replace_event(t, 2, value={field: 2}))
    assert compare(left, right)["first_difference"]["path"] == f"/payload/value/{field}"


@pytest.mark.parametrize(
    "changes,path",
    [
        ({"agent_claimed_success": False}, "/payload/agent_claimed_success"),
        ({"final_state": {"answer": 8}}, "/payload/final_state/answer"),
        ({"failure_detail": "private failure"}, "/payload/failure_detail"),
        ({"failure_fingerprint": "different"}, "/payload/failure_fingerprint"),
        ({"contract": ContractResult(success=False)}, "/payload/contract/success"),
        ({"termination": Termination.CRASH}, "/payload/termination"),
        ({"outcome": Outcome.FAIL}, "/payload/outcome"),
    ],
)
def test_terminal_fields_are_compared(tmp_path: Path, changes: dict[str, Any], path: str) -> None:
    left = store(tmp_path / "a")
    right = store(tmp_path / "b", transform=lambda t: reseal(t, **changes))
    result = compare(left, right)
    assert result["status"] == "DRIFT"
    assert result["first_difference"]["step"] == 3
    assert result["first_difference"]["path"] == path
    assert result["first_difference"]["candidate_kind"] == "terminal"


@pytest.mark.parametrize(
    "termination", [Termination.CRASH, Termination.TIMEOUT, Termination.BUDGET]
)
def test_partial_failed_trace_with_outstanding_calls_is_valid(
    tmp_path: Path, termination: Termination
) -> None:
    def partial(t: TrialEnvelope) -> TrialEnvelope:
        start = t.events[1]
        second = start.model_copy(
            update={"payload": start.payload | {"call_id": "second", "occurrence": 1}}
        )
        items = renumber((t.events[0], start, second, t.events[-1]))
        calls = tuple(ToolCall.model_validate(e.payload) for e in (start, second))
        return reseal(
            t, events=items, incomplete_calls=calls, outcome=Outcome.FAIL, termination=termination
        )

    source = store(tmp_path / "a", transform=partial)
    assert compare(source, source)["status"] == "MATCH"


def test_python_agent_result_followed_by_process_crash_is_valid(tmp_path: Path) -> None:
    source = store(
        tmp_path / "a",
        transform=lambda t: reseal(t, outcome=Outcome.FAIL, termination=Termination.CRASH),
    )
    assert compare(source, source)["status"] == "MATCH"


def command_manifest(**changes: Any) -> Manifest:
    return manifest(
        **(
            {
                "toolset": None,
                "mcp_server": McpServerSpec(
                    argv=("never-run-server",), snapshot="never_import.state:snapshot"
                ),
                "baseline": ArmSpec(label="old", command=CommandSpec(argv=("never-run-agent",))),
                "candidate": ArmSpec(label="new", command=CommandSpec(argv=("never-run-agent",))),
            }
            | changes
        )
    )


def test_command_without_agent_result_and_zero_tools_are_valid(tmp_path: Path) -> None:
    def no_tools(t: TrialEnvelope) -> TrialEnvelope:
        return reseal(t, events=renumber((t.events[0], t.events[-1])))

    source = store(tmp_path / "a", command_manifest(), no_tools)
    assert compare(source, source)["status"] == "MATCH"


@pytest.mark.parametrize(
    "changes",
    [
        {"task": {"question": "changed"}},
        {"task": {"q": True}},
        {"base_seed": 1},
        {"contract": ContractSpec(oracle="never_import.other:grade")},
        {"budgets": Budgets(max_tool_calls=9)},
        {"toolset": "never_import.other:factory"},
        {"fixtures_sha256": "different opaque identity"},
        {
            "conditions": (
                Condition(
                    condition_id="clean",
                    faults=(FaultSpec(name="tool_timeout", bucket=Bucket.FALSIFY),),
                ),
            )
        },
    ],
)
def test_declared_scenario_mismatch_is_invalid(tmp_path: Path, changes: dict[str, Any]) -> None:
    left = store(tmp_path / "a")
    right = store(tmp_path / "b", manifest(**changes))
    result = compare(left, right)
    assert result["status"] == "INVALID"
    assert result["first_difference"] is None


def test_full_decision_spec_is_part_of_declared_scenario(tmp_path: Path) -> None:
    a = DecisionSpec(upstream="fixture", fixture="never_import.decision:answer")
    b = a.model_copy(update={"max_requests_per_minute": 99})
    left = store(tmp_path / "a", command_manifest(decisions=a))
    right = store(tmp_path / "b", command_manifest(decisions=b))
    assert compare(left, right)["status"] == "INVALID"


def test_empty_fixture_identity_has_declaration_only_limitation(tmp_path: Path) -> None:
    source = store(tmp_path / "a", manifest(fixtures_sha256=""))
    result = compare(source, source)
    assert result["status"] == "MATCH"
    assert any(
        "empty" in item.lower() and "declaration" in item.lower() for item in result["limitations"]
    )


def test_block_gate_does_not_prevent_matching_selected_trace(tmp_path: Path) -> None:
    source = store(tmp_path / "a")
    path, _trial_id = source
    lines = (path / "trials.jsonl").read_text().splitlines()
    other = TrialEnvelope.model_validate_json(lines[1])
    blocked = reseal(
        other,
        outcome=Outcome.FAIL,
        contract=ContractResult(
            success=True,
            violations=(Violation(invariant="forbidden", severity="hard", detail="violation"),),
        ),
    )
    (path / "trials.jsonl").write_text(lines[0] + "\n" + blocked.model_dump_json())
    result = compare(source, source)
    assert result["status"] == "MATCH"
    assert result["baseline"]["gate_verdict"] == "BLOCK"
    assert result["baseline"]["gate_exit_code"] == 1


@pytest.mark.parametrize("bad", [True, -1, 0.5, "0", None])
def test_invalid_occurrence_is_rejected(tmp_path: Path, bad: JsonValue) -> None:
    source = store(tmp_path / "a", transform=lambda t: replace_event(t, 1, occurrence=bad))
    assert compare(source, source)["status"] == "INVALID"


@pytest.mark.parametrize(
    "kind",
    [
        "empty",
        "missing_start",
        "missing_end",
        "duplicate_start",
        "duplicate_end",
        "seq",
        "trial_id",
        "duplicate_call",
        "unmatched_finish",
        "duplicate_finish",
        "wrong_tool",
        "incomplete",
        "payload_start",
        "payload_finish",
        "payload_result",
        "payload_annotation",
    ],
)
def test_invalid_selected_events_are_rejected(tmp_path: Path, kind: str) -> None:
    def corrupt(t: TrialEnvelope) -> TrialEnvelope:
        items = list(t.events)
        if kind == "empty":
            items = []
        elif kind == "missing_start":
            items.pop(0)
        elif kind == "missing_end":
            items.pop()
        elif kind == "duplicate_start":
            items.insert(1, items[0])
        elif kind == "duplicate_end":
            items.insert(-1, items[-1])
        elif kind == "seq":
            return reseal(t, events=(items[0].model_copy(update={"seq": 2}), *items[1:]))
        elif kind == "trial_id":
            items[1] = items[1].model_copy(update={"trial_id": "wrong"})
        elif kind == "duplicate_call":
            items.insert(2, items[1])
        elif kind == "unmatched_finish":
            items.pop(1)
        elif kind == "duplicate_finish":
            items.insert(3, items[2])
        elif kind == "wrong_tool":
            return replace_event(t, 2, tool="wrong")
        elif kind == "incomplete":
            return reseal(t, incomplete_calls=(ToolCall.model_validate(items[1].payload),))
        elif kind == "payload_start":
            return replace_event(t, 0, seed=True)
        elif kind == "payload_finish":
            return replace_event(t, 2, ok=1)
        elif kind == "payload_result":
            return replace_event(t, 3, result=[])
        elif kind == "payload_annotation":
            items.insert(
                1, Event(trial_id=t.trial_id, seq=1, kind="model_step", payload={"summary": 1})
            )
        return reseal(t, events=renumber(tuple(items)))

    source = store(tmp_path / "a", transform=corrupt)
    result = compare(source, source)
    assert result["status"] == "INVALID"
    assert result["first_difference"] is None


def test_unselected_trace_is_not_revalidated(tmp_path: Path) -> None:
    source = store(tmp_path / "a")
    path, _trial_id = source
    lines = (path / "trials.jsonl").read_text().splitlines()
    other = reseal(TrialEnvelope.model_validate_json(lines[1]), events=())
    (path / "trials.jsonl").write_text(lines[0] + "\n" + other.model_dump_json())
    assert compare(source, source)["status"] == "MATCH"


@pytest.mark.parametrize(
    "problem",
    [
        "manifest_seal",
        "trial_seal",
        "missing",
        "duplicate",
        "wrong_spec",
        "error",
        "malformed",
        "not_found",
    ],
)
def test_invalid_store_and_selection_never_become_drift(tmp_path: Path, problem: str) -> None:
    source = store(tmp_path / "a")
    path, trial_id = source
    trials_path = path / "trials.jsonl"
    lines = trials_path.read_text().splitlines()
    if problem == "manifest_seal":
        (path / "manifest.json").write_text(
            manifest().model_copy(update={"record_sha256": "bad"}).model_dump_json()
        )
    elif problem == "trial_seal":
        lines[0] = (
            TrialEnvelope.model_validate_json(lines[0])
            .model_copy(update={"record_sha256": "bad"})
            .model_dump_json()
        )
    elif problem == "missing":
        lines.pop()
    elif problem == "duplicate":
        lines.append(lines[0])
    elif problem == "wrong_spec":
        lines[0] = reseal(TrialEnvelope.model_validate_json(lines[0]), seed=99).model_dump_json()
    elif problem == "error":
        lines[1] = reseal(
            TrialEnvelope.model_validate_json(lines[1]),
            outcome=Outcome.ERROR,
            termination=Termination.HARNESS_ERROR,
        ).model_dump_json()
    elif problem == "malformed":
        lines[0] = "private-payload malformed JSON"
    elif problem == "not_found":
        source = (path, trial_id + "missing")
    trials_path.write_text("\n".join(lines))
    result = compare(source, source)
    assert result["status"] == "INVALID"
    assert result["first_difference"] is None
    assert "private-payload" not in json.dumps(result)


def test_missing_store_keeps_available_other_source(tmp_path: Path) -> None:
    source = store(tmp_path / "a")
    result = compare((tmp_path / "absent", "missing"), source)
    assert result["status"] == "INVALID"
    assert result["baseline"] is None
    assert result["candidate"]["trial_outcome"] == "PASS"


def test_no_source_writes_user_imports_or_raw_payload_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from arci.trace_check import check_traces, render_trace_check

    left = store(tmp_path / "a")
    right = store(
        tmp_path / "b", transform=lambda t: replace_event(t, 2, value="secret raw payload")
    )
    summary = tmp_path / "summary.md"
    summary.write_text("preserve")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in tmp_path.rglob("*") if p.is_file()}
    result = check_traces(*left, *right)
    assert result.status == "DRIFT"
    for output_format in ("text", "json"):
        output = render_trace_check(result, output_format=output_format)
        assert "secret raw payload" not in output
        assert "private-payload" not in output
    after = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in tmp_path.rglob("*") if p.is_file()}
    assert before == after
    text = render_trace_check(result)
    assert "INCONCLUSIVE" in text and "PASS" in text and "DRIFT" in text


def test_first_difference_hashes_the_whole_mismatching_subtree(tmp_path: Path) -> None:
    left = store(tmp_path / "a", transform=lambda t: replace_event(t, 2, value={"nested": 1}))
    right = store(tmp_path / "b", transform=lambda t: replace_event(t, 2, value=[1, 2]))
    difference = compare(left, right)["first_difference"]
    assert difference["path"] == "/payload/value"
    assert (
        difference["baseline_sha256"] == hashlib.sha256(canonical_json({"nested": 1})).hexdigest()
    )
    assert difference["candidate_sha256"] == hashlib.sha256(canonical_json([1, 2])).hexdigest()


@pytest.mark.parametrize("field,value", [("seed", 99), ("arm", "candidate"), ("variant", "other")])
def test_start_payload_must_correspond_to_selected_trial(
    tmp_path: Path, field: str, value: JsonValue
) -> None:
    source = store(tmp_path / "a", transform=lambda t: replace_event(t, 0, **{field: value}))
    assert compare(source, source)["status"] == "INVALID"


def test_trial_end_payload_must_be_empty(tmp_path: Path) -> None:
    source = store(tmp_path / "a", transform=lambda t: replace_event(t, 4, result="hidden"))
    assert compare(source, source)["status"] == "INVALID"


def test_multiple_agent_results_are_invalid(tmp_path: Path) -> None:
    def duplicate(t: TrialEnvelope) -> TrialEnvelope:
        return reseal(t, events=renumber((*t.events[:-1], t.events[-2], t.events[-1])))

    source = store(tmp_path / "a", transform=duplicate)
    assert compare(source, source)["status"] == "INVALID"


@pytest.mark.parametrize(
    "index,change,path",
    [
        (1, {"arguments": {"q": 2}}, "/payload/arguments/q"),
        (1, {"occurrence": 1}, "/payload/occurrence"),
        (2, {"ok": False}, "/payload/ok"),
        (2, {"error_kind": "timeout"}, "/payload/error_kind"),
        (2, {"injected_by": "tool_timeout"}, "/payload/injected_by"),
        (2, {"extra": None}, "/payload/extra"),
        (3, {"result": {"success": False}}, "/payload/result/success"),
    ],
)
def test_observed_arguments_results_and_agent_result_are_compared(
    tmp_path: Path, index: int, change: dict[str, JsonValue], path: str
) -> None:
    left = store(tmp_path / "a")
    right = store(tmp_path / "b", transform=lambda t: replace_event(t, index, **change))
    result = compare(left, right)
    assert result["status"] == "DRIFT"
    assert result["first_difference"]["path"] == path


def test_tool_identity_is_compared(tmp_path: Path) -> None:
    def rename(t: TrialEnvelope) -> TrialEnvelope:
        return replace_event(replace_event(t, 1, tool="reserve"), 2, tool="reserve")

    left = store(tmp_path / "a")
    right = store(tmp_path / "b", transform=rename)
    assert compare(left, right)["first_difference"]["path"] == "/payload/tool"


def test_order_of_valid_exchanges_is_compared(tmp_path: Path) -> None:
    def two_calls(t: TrialEnvelope, *, reverse: bool) -> TrialEnvelope:
        second_start = t.events[1].model_copy(
            update={"payload": t.events[1].payload | {"tool": "reserve", "call_id": "second"}}
        )
        second_finish = t.events[2].model_copy(
            update={"payload": t.events[2].payload | {"tool": "reserve", "call_id": "second"}}
        )
        first, second = (t.events[1], t.events[2]), (second_start, second_finish)
        pairs = (*second, *first) if reverse else (*first, *second)
        return reseal(t, events=renumber((t.events[0], *pairs, *t.events[3:])))

    left = store(tmp_path / "a", transform=lambda t: two_calls(t, reverse=False))
    right = store(tmp_path / "b", transform=lambda t: two_calls(t, reverse=True))
    result = compare(left, right)
    assert result["status"] == "DRIFT"
    assert result["first_difference"]["step"] == 0
    assert result["first_difference"]["path"] == "/payload/tool"


def test_traces_of_different_lengths_report_first_observed_step_difference(tmp_path: Path) -> None:
    def zero(t: TrialEnvelope) -> TrialEnvelope:
        return reseal(t, events=renumber((t.events[0], t.events[-2], t.events[-1])))

    left = store(tmp_path / "a", transform=zero)
    right = store(tmp_path / "b")
    result = compare(left, right)
    assert result["status"] == "DRIFT"
    assert result["first_difference"]["step"] == 0
    assert result["first_difference"]["path"] == "/kind"
    assert result["first_difference"]["baseline_kind"] == "agent_result"
    assert result["first_difference"]["candidate_kind"] == "tool_start"


def test_canonical_object_key_order_does_not_create_drift(tmp_path: Path) -> None:
    left = store(
        tmp_path / "a",
        transform=lambda t: replace_event(t, 1, arguments={"z": 1, "a": {"y": 2, "x": 3}}),
    )
    right = store(
        tmp_path / "b",
        transform=lambda t: replace_event(t, 1, arguments={"a": {"x": 3, "y": 2}, "z": 1}),
    )
    assert compare(left, right)["status"] == "MATCH"


@pytest.mark.parametrize("a,b", [(True, 1), (1, 1.0)])
def test_task_payload_comparability_is_type_sensitive(
    tmp_path: Path, a: JsonValue, b: JsonValue
) -> None:
    left = store(tmp_path / "a", manifest(task={"q": a}))
    right = store(tmp_path / "b", manifest(task={"q": b}))
    assert compare(left, right)["status"] == "INVALID"


def test_ordered_selected_faults_must_match(tmp_path: Path) -> None:
    a = FaultSpec(name="tool_timeout", bucket=Bucket.FALSIFY)
    b = FaultSpec(name="empty_result", bucket=Bucket.BENIGN)
    left = store(
        tmp_path / "a", manifest(conditions=(Condition(condition_id="left", faults=(a, b)),))
    )
    right = store(
        tmp_path / "b", manifest(conditions=(Condition(condition_id="right", faults=(b, a)),))
    )
    assert compare(left, right)["status"] == "INVALID"


def test_ids_agent_identities_and_statistical_design_can_differ(tmp_path: Path) -> None:
    left = store(tmp_path / "a")
    right = store(
        tmp_path / "b",
        manifest(
            experiment_id="other",
            task_id="other",
            conditions=(Condition(condition_id="other"),),
            baseline=ArmSpec(
                label="changed", agent="never_import.changed:agent", candidate_id="sha"
            ),
            candidate=ArmSpec(label="changed-again", agent="never_import.another:agent"),
            n_per_arm=2,
            alpha=0.1,
            delta=0.3,
            interval_method="newcombe",
            prior_runs=("prior",),
        ),
    )
    assert compare(left, right)["status"] == "MATCH"


def test_declared_environment_and_execution_kind_must_match(tmp_path: Path) -> None:
    left = store(tmp_path / "a")
    command = store(tmp_path / "b", command_manifest())
    changed_env = store(
        tmp_path / "c",
        command_manifest(
            mcp_server=McpServerSpec(
                argv=("never-run-server",),
                env={"MODE": "other"},
                snapshot="never_import.state:snapshot",
            )
        ),
    )
    assert compare(left, command)["status"] == "INVALID"
    assert compare(command, changed_env)["status"] == "INVALID"


def test_incomplete_calls_compare_before_call_id_normalization(tmp_path: Path) -> None:
    def wrong(t: TrialEnvelope) -> TrialEnvelope:
        call = ToolCall.model_validate(t.events[1].payload).model_copy(
            update={"call_id": "renamed"}
        )
        return reseal(
            t,
            events=renumber((t.events[0], t.events[1], t.events[-1])),
            incomplete_calls=(call,),
            outcome=Outcome.FAIL,
            termination=Termination.TIMEOUT,
        )

    source = store(tmp_path / "a", transform=wrong)
    assert compare(source, source)["status"] == "INVALID"


def test_incomplete_call_arguments_compare_with_canonical_types(tmp_path: Path) -> None:
    def wrong(t: TrialEnvelope) -> TrialEnvelope:
        call = ToolCall.model_validate(t.events[1].payload).model_copy(
            update={"arguments": {"q": True}}
        )
        return reseal(
            t,
            events=renumber((t.events[0], t.events[1], t.events[-1])),
            incomplete_calls=(call,),
            outcome=Outcome.FAIL,
            termination=Termination.TIMEOUT,
        )

    source = store(tmp_path / "a", transform=wrong)
    assert compare(source, source)["status"] == "INVALID"


def test_missing_list_element_has_null_kind_and_hash(tmp_path: Path) -> None:
    left = store(tmp_path / "a", transform=lambda t: replace_event(t, 2, value=[0, None]))
    right = store(tmp_path / "b", transform=lambda t: replace_event(t, 2, value=[0]))
    difference = compare(left, right)["first_difference"]
    assert difference["path"] == "/payload/value/1"
    assert difference["baseline_sha256"] == hashlib.sha256(b"null").hexdigest()
    assert difference["candidate_sha256"] is None
    assert difference["candidate_kind"] is None
