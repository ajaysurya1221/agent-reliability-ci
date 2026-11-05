"""Read-only triage over sealed, never-executed fixture declarations."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import JsonValue

from arci.gate import decide
from arci.schedule import build_schedule, spec_sha256
from arci.schema import (
    ArmSpec,
    Bucket,
    Condition,
    ContractResult,
    ContractSpec,
    Event,
    FaultSpec,
    Manifest,
    Outcome,
    Termination,
    ToolCall,
    TrialEnvelope,
    TrialSpec,
    Violation,
)
from arci.trace_check import check_traces


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


def write_run(
    path: Path,
    definition: Manifest | None = None,
    mutate: Callable[[TrialEnvelope], TrialEnvelope] | None = None,
    *,
    prefix: int | None = None,
) -> tuple[Manifest, tuple[TrialEnvelope, ...]]:
    definition = definition or manifest()
    trials = tuple(envelope(s) for s in build_schedule(definition))
    if prefix is not None:
        trials = trials[:prefix]
    if mutate:
        trials = tuple(mutate(t) for t in trials)
    path.mkdir()
    (path / "manifest.json").write_text(definition.model_dump_json())
    (path / "trials.jsonl").write_text("\n".join(t.model_dump_json() for t in trials))
    return definition, trials


def fail(
    t: TrialEnvelope, *, fingerprint: str | None = "oracle", hard: bool = False
) -> TrialEnvelope:
    return reseal(
        t,
        outcome=Outcome.FAIL,
        failure_fingerprint=fingerprint,
        contract=ContractResult(
            success=False,
            violations=(Violation(invariant="never", severity="hard", detail="PRIVATE VIOLATION"),)
            if hard
            else (),
        ),
        failure_detail="PRIVATE FAILURE",
    )


def triage(path: Path, trial_id: str | None = None) -> dict[str, Any]:
    try:
        from arci.triage import render_triage, triage_run
    except ImportError:
        pytest.fail("triage API is not implemented")
    result = triage_run(path, trial_id=trial_id)
    document = cast(dict[str, Any], json.loads(render_triage(result, output_format="json")))
    assert result.exit_code == document["exit_code"]
    return document


def test_no_failures_preserves_complete_gate(tmp_path: Path) -> None:
    definition, trials = write_run(tmp_path / "run")
    doc = triage(tmp_path / "run")
    expected = decide(definition, trials).model_dump(mode="json")
    assert doc["gate"] == expected | {"decision_sha256": expected["record_sha256"]}
    assert doc["status"] == "OK" and doc["exit_code"] == 2
    assert doc["group_counts"] == {"total": 0, "shown": 0, "omitted": 0}
    assert doc["selected_pairs"] == []
    assert "no candidate failures" in doc["reason"].lower()


def test_explicit_pass_compares_scheduled_pair(tmp_path: Path) -> None:
    _, trials = write_run(tmp_path / "run")
    doc = triage(tmp_path / "run", trials[1].trial_id)
    pair = doc["selected_pairs"][0]
    assert pair["candidate_trial_id"] == trials[1].trial_id
    assert pair["baseline_trial_id"] == trials[0].trial_id
    assert pair["candidate_outcome"] == pair["baseline_outcome"] == "PASS"
    assert pair["comparison"] == json.loads(
        json.dumps(
            asdict(
                check_traces(
                    tmp_path / "run", trials[0].trial_id, tmp_path / "run", trials[1].trial_id
                )
            )
        )
    )
    assert pair["first_difference_context"] is None
    assert doc["group_counts"]["total"] == 0


@pytest.mark.parametrize("trial_id", ["clean:00000:baseline", "missing"])
def test_bad_override_is_invalid(tmp_path: Path, trial_id: str) -> None:
    write_run(tmp_path / "run")
    doc = triage(tmp_path / "run", trial_id)
    assert doc["status"] == "INVALID" and doc["exit_code"] == 3
    assert doc["selected_pairs"] == []


def test_groups_prioritize_ceiling_hard_then_gating_and_cap_at_three(tmp_path: Path) -> None:
    conditions = tuple(
        Condition(
            condition_id=name,
            faults=(FaultSpec(name="tool_timeout", bucket=Bucket.CEILING),)
            if name in {"ceiling", "descriptive"}
            else (),
        )
        for name in ("ordinary", "ceiling", "blocked", "descriptive", "another")
    )

    def mutate(t: TrialEnvelope) -> TrialEnvelope:
        if t.arm == "baseline":
            return t
        return fail(t, hard=t.condition_id in {"ceiling", "blocked"})

    write_run(tmp_path / "run", manifest(conditions=conditions), mutate)
    doc = triage(tmp_path / "run")
    assert [g["condition_id"] for g in doc["groups"]] == ["blocked", "ceiling", "another"]
    assert doc["group_counts"] == {"total": 5, "shown": 3, "omitted": 2}
    assert len(doc["selected_pairs"]) == 3
    assert doc["gate"]["verdict"] == "BLOCK" and doc["exit_code"] == 1


def test_missing_fingerprint_separate_count_order_and_baseline_pass_preference(
    tmp_path: Path,
) -> None:
    def mutate(t: TrialEnvelope) -> TrialEnvelope:
        if t.arm == "baseline":
            return fail(t) if t.pair_id.endswith("00000") else t
        return fail(t, fingerprint=None if t.pair_id.endswith("00002") else "<missing>")

    _, trials = write_run(tmp_path / "run", manifest(n_per_arm=3), mutate)
    doc = triage(tmp_path / "run")
    assert [(g["failure_fingerprint"], g["count"]) for g in doc["groups"]] == [
        ("<missing>", 2),
        (None, 1),
    ]
    assert doc["selected_pairs"][0]["candidate_trial_id"] == trials[3].trial_id


def test_actual_hard_trial_wins_over_baseline_pass(tmp_path: Path) -> None:
    def mutate(t: TrialEnvelope) -> TrialEnvelope:
        if t.arm == "baseline":
            return fail(t) if t.pair_id.endswith("00001") else t
        return fail(t, hard=t.pair_id.endswith("00001"))

    _, trials = write_run(tmp_path / "run", manifest(n_per_arm=3), mutate)
    doc = triage(tmp_path / "run")
    assert doc["groups"][0]["hard_violation_trials"] == 1
    assert doc["selected_pairs"][0]["candidate_trial_id"] == trials[3].trial_id


def test_early_stop_only_observed_trials_and_complete_history(tmp_path: Path) -> None:
    definition, trials = write_run(
        tmp_path / "run",
        manifest(n_per_arm=3, looks=(1, 3)),
        lambda t: fail(t, hard=True) if t.arm == "candidate" else t,
        prefix=2,
    )
    doc = triage(tmp_path / "run")
    assert doc["exit_code"] == 1
    assert doc["gate"]["history"] == decide(definition, trials).model_dump(mode="json")["history"]
    assert doc["gate"]["stopped_at_look"] == 1
    assert doc["groups"][0]["count"] == 1


@pytest.mark.parametrize(
    "problem", ["malformed", "duplicate", "error", "missing", "seal", "events"]
)
def test_invalid_sources_never_gain_context(tmp_path: Path, problem: str) -> None:
    path = tmp_path / "run"
    _, trials = write_run(path, mutate=lambda t: fail(t) if t.arm == "candidate" else t)
    lines = [t.model_dump_json() for t in trials]
    if problem == "malformed":
        lines[0] = "PRIVATE MALFORMED"
    elif problem == "duplicate":
        lines.append(lines[1])
    elif problem == "error":
        lines[0] = reseal(trials[0], outcome=Outcome.ERROR).model_dump_json()
    elif problem == "missing":
        lines.pop(0)
    elif problem == "seal":
        lines[0] = trials[0].model_copy(update={"record_sha256": "bad"}).model_dump_json()
    else:
        lines[1] = reseal(trials[1], events=()).model_dump_json()
    (path / "trials.jsonl").write_text("\n".join(lines))
    doc = triage(path)
    assert doc["status"] == "INVALID" and doc["exit_code"] == 3
    assert doc["selected_pairs"] == []
    assert "PRIVATE" not in json.dumps(doc)


def test_missing_store_returns_safe_invalid(tmp_path: Path) -> None:
    doc = triage(tmp_path / "missing")
    assert doc["gate"] is None and doc["exit_code"] == 3


def test_missing_value_is_distinct_from_null_in_containing_event(tmp_path: Path) -> None:
    def mutate(t: TrialEnvelope) -> TrialEnvelope:
        return replace_event(t, 2, value={"new": None} if t.arm == "candidate" else {})

    _, trials = write_run(tmp_path / "run", mutate=mutate)
    doc = triage(tmp_path / "run", trials[1].trial_id)
    context = doc["selected_pairs"][0]["first_difference_context"]
    assert context["baseline"] == {
        "location": "event",
        "event_kind": "tool_finish",
        "seq": 2,
        "tool": "fetch",
        "occurrence": 0,
        "value_present": False,
    }
    assert context["candidate"] == context["baseline"] | {"value_present": True}


def test_terminal_context_and_payload_canaries_no_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "run"
    write_run(path, mutate=lambda t: fail(t) if t.arm == "candidate" else t)
    summary = tmp_path / "summary.md"
    summary.write_text("unchanged")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in tmp_path.rglob("*") if p.is_file()}
    doc = triage(path)
    context = doc["selected_pairs"][0]["first_difference_context"]
    assert context["candidate"]["location"] == "terminal"
    from arci.triage import render_triage, triage_run

    for fmt in ("text", "json"):
        text = render_triage(triage_run(path), output_format=fmt)
        assert "PRIVATE FAILURE" not in text and "PRIVATE VIOLATION" not in text
        assert "private-payload" not in text
    after = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in tmp_path.rglob("*") if p.is_file()}
    assert before == after


def test_concurrent_change_discards_all_diagnosis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import arci.trace_check as tc

    # Import through module after API red checks, so the initial failure stays purposeful.
    try:
        import arci.triage as module
    except ImportError:
        pytest.fail("triage API is not implemented")
    path = tmp_path / "run"
    write_run(path, mutate=lambda t: fail(t) if t.arm == "candidate" else t)
    original = tc.check_traces

    def changing(a: Path | str, b: str, c: Path | str, d: str) -> tc.TraceCheckResult:
        result = original(a, b, c, d)
        assert result.baseline is not None
        return replace(result, baseline=replace(result.baseline, decision_sha256="0" * 64))

    monkeypatch.setattr(module, "check_traces", changing)
    doc = triage(path)
    assert doc["status"] == "INVALID" and doc["exit_code"] == 3
    assert doc["selected_pairs"] == []


@pytest.mark.parametrize(
    "termination", [Termination.CRASH, Termination.TIMEOUT, Termination.BUDGET]
)
def test_incomplete_calls_have_context(tmp_path: Path, termination: Termination) -> None:
    def mutate(t: TrialEnvelope) -> TrialEnvelope:
        if t.arm == "baseline":
            return t
        start = t.events[1]
        return reseal(
            fail(t),
            events=renumber((t.events[0], start, t.events[-1])),
            incomplete_calls=(ToolCall.model_validate(start.payload),),
            termination=termination,
        )

    write_run(tmp_path / "run", mutate=mutate)
    doc = triage(tmp_path / "run")
    assert doc["status"] == "OK"
    context = doc["selected_pairs"][0]["first_difference_context"]
    assert context["baseline"]["event_kind"] == "tool_finish"
    assert context["candidate"]["location"] == "terminal"


def test_pass_gate_exit_zero_even_with_drift(tmp_path: Path) -> None:
    _, trials = write_run(
        tmp_path / "run",
        manifest(n_per_arm=50, delta=0.5),
        lambda t: replace_event(t, 2, value=99) if t.arm == "candidate" else t,
    )
    doc = triage(tmp_path / "run", trials[1].trial_id)
    assert doc["gate"]["verdict"] == "PASS" and doc["exit_code"] == 0
    assert doc["selected_pairs"][0]["comparison"]["status"] == "DRIFT"


def test_context_escapes_controls_once_and_bounds_tool_names(tmp_path: Path) -> None:
    def mutate(t: TrialEnvelope) -> TrialEnvelope:
        tool = "fetch\n\x1b[31m\u202e" if t.arm == "baseline" else "x" * 1000
        return replace_event(replace_event(t, 1, tool=tool), 2, tool=tool)

    _, trials = write_run(tmp_path / "run", mutate=mutate)
    doc = triage(tmp_path / "run", trials[1].trial_id)
    context = doc["selected_pairs"][0]["first_difference_context"]
    assert context["baseline"]["tool"] == "fetch\\n\\u001b[31m\\u202e"
    assert len(context["candidate"]["tool"]) <= 120
    assert "\x1b" not in context["baseline"]["tool"]


def test_context_absent_step_does_not_invent_an_event(tmp_path: Path) -> None:
    from arci.trace_check import trace_step_context

    _, trials = write_run(tmp_path / "run")
    context = trace_step_context(trials[0], 4, value_present=False)
    assert asdict(context) == {
        "location": "absent",
        "event_kind": None,
        "seq": None,
        "tool": None,
        "occurrence": None,
        "value_present": False,
    }
    assert trace_step_context(trials[0], 3, value_present=True).location == "terminal"


@pytest.mark.parametrize("side", ["baseline", "candidate"])
@pytest.mark.parametrize("field", ["manifest_sha256", "trial_sha256", "decision_sha256"])
def test_every_source_hash_is_bound_to_initial_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, side: str, field: str
) -> None:
    import arci.triage as module

    path = tmp_path / "run"
    write_run(path, mutate=lambda t: fail(t) if t.arm == "candidate" else t)

    def mismatched(a: Path | str, b: str, c: Path | str, d: str) -> module.TraceCheckResult:
        result = check_traces(a, b, c, d)
        source = result.baseline if side == "baseline" else result.candidate
        assert source is not None
        changed = replace(source, **{field: "0" * 64})
        return replace(result, **{side: changed})

    monkeypatch.setattr(module, "check_traces", mismatched)
    doc = triage(path)
    assert doc["status"] == "INVALID" and doc["exit_code"] == 3
    assert doc["selected_pairs"] == []


def test_fingerprint_ties_are_stable_and_override_does_not_change_groups(tmp_path: Path) -> None:
    fingerprints = ("z", None, "a", "", "z")

    def mutate(t: TrialEnvelope) -> TrialEnvelope:
        index = t.seed
        return fail(t, fingerprint=fingerprints[index]) if t.arm == "candidate" else t

    _, trials = write_run(tmp_path / "run", manifest(n_per_arm=5), mutate)
    doc = triage(tmp_path / "run")
    assert [(g["failure_fingerprint"], g["count"]) for g in doc["groups"]] == [
        ("z", 2),
        (None, 1),
        ("", 1),
    ]
    explicit = triage(tmp_path / "run", trials[5].trial_id)
    assert explicit["group_counts"] == doc["group_counts"]
    assert explicit["groups"] == doc["groups"]
    assert len(explicit["selected_pairs"]) == 1


def test_later_pair_invalidation_discards_earlier_context(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import arci.triage as module

    path = tmp_path / "run"

    def mutate(t: TrialEnvelope) -> TrialEnvelope:
        return fail(t, fingerprint=str(t.seed)) if t.arm == "candidate" else t

    write_run(path, manifest(n_per_arm=2), mutate)
    count = 0

    def changing(a: Path | str, b: str, c: Path | str, d: str) -> module.TraceCheckResult:
        nonlocal count
        count += 1
        if count == 2:
            lines = (path / "trials.jsonl").read_text().splitlines()
            old = TrialEnvelope.model_validate_json(lines[0])
            lines[0] = reseal(old, final_state={"changed": True}).model_dump_json()
            (path / "trials.jsonl").write_text("\n".join(lines))
        return check_traces(a, b, c, d)

    monkeypatch.setattr(module, "check_traces", changing)
    doc = triage(path)
    assert doc["status"] == "INVALID" and doc["exit_code"] == 3
    assert doc["selected_pairs"] == []


def test_comparator_source_identity_must_match_selected_pair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import arci.triage as module

    path = tmp_path / "run"
    write_run(path, mutate=lambda t: fail(t) if t.arm == "candidate" else t)

    def wrong_identity(a: Path | str, b: str, c: Path | str, d: str) -> module.TraceCheckResult:
        result = check_traces(a, b, c, d)
        assert result.candidate is not None
        return replace(result, candidate=replace(result.candidate, trial_id="wrong"))

    monkeypatch.setattr(module, "check_traces", wrong_identity)
    doc = triage(path)
    assert doc["status"] == "INVALID" and doc["selected_pairs"] == []


def test_text_explains_containing_event_and_missing_value_without_json_dump(tmp_path: Path) -> None:
    from arci.triage import render_triage, triage_run

    def mutate(t: TrialEnvelope) -> TrialEnvelope:
        return replace_event(t, 2, value={"new": None} if t.arm == "candidate" else {})

    _, trials = write_run(tmp_path / "run", mutate=mutate)
    text = render_triage(triage_run(tmp_path / "run", trial_id=trials[1].trial_id))
    lines = text.splitlines()
    assert lines[0].startswith("Statistical gate: INCONCLUSIVE")
    baseline = next(line for line in lines if "Baseline context:" in line)
    candidate = next(line for line in lines if "Candidate context:" in line)
    assert all(
        part in baseline
        for part in ("tool_finish", "seq 2", 'tool "fetch"', "occurrence 0", "absent")
    )
    assert all(
        part in candidate
        for part in ("tool_finish", "seq 2", 'tool "fetch"', "occurrence 0", "present")
    )
    assert "Complete gate:" not in text and '"alpha":' not in text
    assert len([line for line in lines if line.startswith("Limitation: First difference")]) == 1
    assert "First difference: step 1" in text and '"/payload/value/new"' in text


def test_truncated_tool_display_is_marked(tmp_path: Path) -> None:
    def mutate(t: TrialEnvelope) -> TrialEnvelope:
        return replace_event(replace_event(t, 1, tool="x" * 121), 2, tool="x" * 121, value=t.arm)

    _, trials = write_run(tmp_path / "run", mutate=mutate)
    context = triage(tmp_path / "run", trials[1].trial_id)["selected_pairs"][0][
        "first_difference_context"
    ]
    assert context["baseline"]["tool"].endswith("...")
    assert len(context["baseline"]["tool"]) <= 120


def test_block_condition_group_precedes_larger_other_gating_group(tmp_path: Path) -> None:
    conditions = (
        Condition(condition_id="ordinary"),
        Condition(condition_id="blocked"),
        Condition(
            condition_id="ceiling", faults=(FaultSpec(name="tool_timeout", bucket=Bucket.CEILING),)
        ),
    )

    def mutate(t: TrialEnvelope) -> TrialEnvelope:
        if t.arm == "baseline":
            return t
        hard = t.condition_id == "blocked" and t.seed == 2
        return fail(t, fingerprint="hard" if hard else "ordinary", hard=hard)

    write_run(tmp_path / "run", manifest(n_per_arm=2, conditions=conditions), mutate)
    doc = triage(tmp_path / "run")
    assert [(g["condition_id"], g["failure_fingerprint"]) for g in doc["groups"]] == [
        ("blocked", "hard"),
        ("blocked", "ordinary"),
        ("ordinary", "ordinary"),
    ]
    assert doc["group_counts"] == {"total": 4, "shown": 3, "omitted": 1}


def test_schedule_order_wins_over_store_order_with_opaque_condition_names(tmp_path: Path) -> None:
    path = tmp_path / "run"
    _, trials = write_run(
        path,
        manifest(n_per_arm=2, conditions=(Condition(condition_id="a:candidate:00003:baseline"),)),
        lambda t: fail(t) if t.arm == "candidate" else t,
    )
    (path / "trials.jsonl").write_text("\n".join(t.model_dump_json() for t in reversed(trials)))
    pair = triage(path)["selected_pairs"][0]
    assert pair["candidate_trial_id"] == trials[1].trial_id
    assert pair["baseline_trial_id"] == trials[0].trial_id


def test_finish_context_resolves_occurrence_via_matching_start(tmp_path: Path) -> None:
    def mutate(t: TrialEnvelope) -> TrialEnvelope:
        return replace_event(replace_event(t, 1, occurrence=9), 2, value=t.arm)

    _, trials = write_run(tmp_path / "run", mutate=mutate)
    pair = triage(tmp_path / "run", trials[1].trial_id)["selected_pairs"][0]
    assert pair["comparison"]["first_difference"]["step"] == 1
    assert pair["first_difference_context"]["baseline"]["occurrence"] == 9
    assert pair["first_difference_context"]["candidate"]["occurrence"] == 9
