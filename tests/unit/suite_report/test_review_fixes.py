"""Regression evidence for P2b2 report attribution and saved-decision checks."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from arci.cli import main
from arci.interfaces import Perturbation
from arci.perturb import build
from arci.report import fault_accounting, fault_markdown
from arci.schema import Bucket, Condition, Event, FaultSpec, TrialEnvelope
from arci.suite_gate import decide_suite
from arci.suite_report import render_suite_json, render_suite_markdown
from arci.suite_storage import load_suite_run
from tests.unit.suite_report.test_reports import evidence, store_at


def factory(fault: FaultSpec) -> Perturbation:
    print("factory diagnostics must not pollute JSON")
    return build(fault.model_copy(update={"name": "tool_timeout"}))


def broken_factory(fault: FaultSpec) -> Perturbation:
    del fault
    raise SystemExit("unavailable factory")


def hanging_factory(fault: FaultSpec) -> Perturbation:
    time.sleep(10)
    return factory(fault)


def trial_with_injections(*injections: tuple[str, str, int]) -> TrialEnvelope:
    _, trials = evidence("BLOCK")
    trial = trials[0]
    events: list[Event] = []
    for i, (name, tool, occurrence) in enumerate(injections):
        events.extend(
            (
                Event(
                    trial_id=trial.trial_id,
                    seq=2 * i,
                    kind="tool_start",
                    payload={
                        "call_id": str(i),
                        "tool": tool,
                        "occurrence": occurrence,
                    },
                ),
                Event(
                    trial_id=trial.trial_id,
                    seq=2 * i + 1,
                    kind="tool_finish",
                    payload={
                        "call_id": str(i),
                        "tool": tool,
                        "injected_by": name,
                    },
                ),
            )
        )
    return TrialEnvelope.create(
        **(
            trial.model_dump(exclude={"record_sha256"})
            | {
                "condition_id": "faults",
                "events": tuple(events),
            }
        )
    )


def fault(name: str, tool: str | None = "fetch", occurrence: int = 0) -> FaultSpec:
    return FaultSpec(name=name, bucket=Bucket.FALSIFY, tool=tool, at_occurrence=occurrence)


def test_custom_name_is_resolved_for_v1_and_suite() -> None:
    from arci.gate import decide
    from arci.report import render_markdown
    from tests.acceptance.helpers import manifest

    condition = Condition(condition_id="faults", faults=(fault(f"{__name__}:factory"),))
    trial = trial_with_injections(("tool_timeout", "fetch", 0))
    rows = fault_accounting((condition,), (trial,))
    assert rows[0]["injections"] == rows[0]["trials_fired"] == 1
    assert rows[0]["status"] == "observed"
    assert rows[1]["status"] == "declared, never fired"
    v1 = manifest(conditions=(condition,), n_per_arm=1)
    assert "| baseline | 1 | 1 | 1 | observed |" in render_markdown(
        v1, decide(v1, (trial,)), (trial,)
    )
    suite, _ = evidence("BLOCK")
    suite = suite.model_copy(update={"conditions": (condition,)})
    document = json.loads(render_suite_json(suite, decide_suite(suite, (trial,)), (trial,)))
    assert document["fault_accounting"] == rows


@pytest.mark.parametrize(
    "factory_name",
    ["does_not_exist:factory", f"{__name__}:broken_factory", f"{__name__}:hanging_factory"],
)
def test_unresolvable_factory_never_claims_never_fired(factory_name: str) -> None:
    condition = Condition(condition_id="faults", faults=(fault(factory_name),))
    rows = fault_accounting((condition,), (trial_with_injections(("internal", "fetch", 0)),))
    assert [r["status"] for r in rows] == ["cannot attribute", "cannot attribute", "unattributed"]
    assert rows[-1]["injections"] == 1


def test_duplicate_scopes_unknown_and_ambiguous_injections() -> None:
    condition = Condition(
        condition_id="faults",
        faults=(
            fault("tool_timeout"),
            fault("tool_timeout", "store", 5),
        ),
    )
    trial = trial_with_injections(("tool_timeout", "fetch", 0), ("other", "fetch", 1))
    rows = [r for r in fault_accounting((condition,), (trial,)) if r["arm"] == "baseline"]
    assert [r["status"] for r in rows] == ["observed", "declared, never fired", "unattributed"]
    assert [r["injections"] for r in rows] == [1, 0, 1]
    assert "declaration 2; tool=store; occurrence=5" in "\n".join(
        fault_markdown((condition,), (trial,))
    )
    ambiguous = condition.model_copy(
        update={"faults": (fault("tool_timeout"), fault("tool_timeout"))}
    )
    rows = [r for r in fault_accounting((ambiguous,), (trial,)) if r["arm"] == "baseline"]
    assert [r["status"] for r in rows[:2]] == ["cannot attribute", "cannot attribute"]
    assert sum(r["injections"] for r in rows) == 2


def test_decision_unavailable_matches_later_occurrences() -> None:
    condition = Condition(
        condition_id="faults",
        faults=(
            fault("decision_unavailable", occurrence=1),
            fault("decision_unavailable", occurrence=5),
        ),
    )
    rows = [
        r
        for r in fault_accounting(
            (condition,),
            (trial_with_injections(("decision_unavailable", "decision:systemone", 3)),),
        )
        if r["arm"] == "baseline"
    ]
    assert [r["status"] for r in rows] == ["observed", "declared, never fired"]


@pytest.mark.parametrize("declare_condition", [False, True])
def test_unknown_injection_without_declarations_is_retained(declare_condition: bool) -> None:
    rows = fault_accounting(
        (Condition(condition_id="faults"),) if declare_condition else (),
        (trial_with_injections(("other", "fetch", 0)),),
    )
    assert len(rows) == 1 and rows[0]["status"] == "unattributed"


@pytest.mark.parametrize("status", ["absent", "match", "mismatch", "malformed", "unsealed"])
def test_stored_decision_status(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], status: str
) -> None:
    store = store_at(tmp_path, "PASS")
    m, trials = load_suite_run(store.run_dir)
    decision = decide_suite(m, trials)
    path = store.run_dir / "decision.json"
    if status == "match":
        store.write_decision(decision)
    elif status == "mismatch":
        store.write_decision(decide_suite(*evidence("BLOCK")))
    elif status == "malformed":
        path.write_text("{broken")
    elif status == "unsealed":
        path.write_text(decision.model_copy(update={"record_sha256": "0" * 64}).model_dump_json())
    expected_status = status if status in {"absent", "match"} else "mismatch"
    expected_exit = 3 if expected_status == "mismatch" else 0
    before = {p: p.read_bytes() for p in store.run_dir.iterdir()}
    assert main(["report", str(store.run_dir), "--format", "json"]) == expected_exit
    doc = json.loads(capsys.readouterr().out)
    assert doc["stored_decision_status"] == expected_status
    assert doc["exit_code"] == expected_exit and doc["decision"]["verdict"] == "PASS"
    assert main(["report", str(store.run_dir)]) == expected_exit
    text = capsys.readouterr().out
    assert f"stored decision: {expected_status}" in text.splitlines()[2]
    if expected_exit == 3:
        assert "VERDICT: ERROR (exit 3)" in text and "recomputed verdict: PASS" in text
    assert {p: p.read_bytes() for p in store.run_dir.iterdir()} == before


def test_standalone_guarantees_match_json() -> None:
    m, trials = evidence("PASS")
    m = m.model_copy(update={"scenario_seeds": "per_round"})
    d = decide_suite(m, trials)
    doc = json.loads(render_suite_json(m, d, trials))
    text = render_suite_markdown(m, d, trials)
    assert "per_round" in doc["guarantee"] and "above" not in doc["guarantee"]
    for key in (
        "guarantee",
        "assumptions",
        "cell_warning",
        "wealth_display",
        "seed_limitation",
        "prior_runs_scope",
        "integrity_limitation",
    ):
        assert doc[key] in text
    assert "manifest" in doc["prior_runs_scope"] and "output root only" in doc["prior_runs_scope"]
