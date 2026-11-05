"""Public triage command behavior over real, sealed native stores."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import pytest

from arci.cli import main
from arci.gate import decide
from arci.schedule import build_schedule, spec_sha256
from arci.schema import (
    ArmSpec,
    Condition,
    ContractResult,
    ContractSpec,
    Event,
    Manifest,
    Outcome,
    Termination,
    TrialEnvelope,
    TrialSpec,
    Violation,
)
from arci.storage import ExperimentStore

SECRET = "triage-sensitive-payload-never-rendered"
TOP_KEYS = {
    "schema_version",
    "status",
    "reason",
    "exit_code",
    "gate",
    "group_counts",
    "groups",
    "selected_pairs",
    "limitations",
}


def _trial(
    spec: TrialSpec, outcome: Outcome, *, malformed: bool = False, drift: bool = False
) -> TrialEnvelope:
    events = (
        Event(
            trial_id=spec.trial_id,
            seq=0,
            kind="trial_start",
            payload={"seed": spec.seed, "arm": spec.arm, "variant": spec.variant},
        ),
        Event(
            trial_id=spec.trial_id,
            seq=1,
            kind="tool_start",
            payload={
                "call_id": "call",
                "tool": "inspect",
                "occurrence": 0,
                "arguments": {"secret": SECRET},
            },
        ),
        Event(
            trial_id=spec.trial_id,
            seq=9 if malformed else 2,
            kind="tool_finish",
            payload={
                "call_id": "call",
                "tool": "inspect",
                "ok": True,
                "value": {"secret": SECRET, "ok": outcome is Outcome.PASS and not drift},
                "error_kind": None,
                "injected_by": None,
            },
        ),
        Event(trial_id=spec.trial_id, seq=3, kind="agent_result", payload={"result": {}}),
        Event(trial_id=spec.trial_id, seq=4, kind="trial_end"),
    )
    violations = (
        (Violation(invariant="forbidden_tool", severity="hard", detail=SECRET),)
        if outcome is Outcome.FAIL
        else ()
    )
    return TrialEnvelope.create(
        spec_sha256=spec_sha256(spec),
        experiment_id=spec.experiment_id,
        trial_id=spec.trial_id,
        pair_id=spec.pair_id,
        arm=spec.arm,
        variant=spec.variant,
        task_id=spec.task_id,
        condition_id=spec.condition.condition_id,
        seed=spec.seed,
        outcome=outcome,
        termination=Termination.HARNESS_ERROR
        if outcome is Outcome.ERROR
        else Termination.COMPLETED,
        contract=ContractResult(success=outcome is Outcome.PASS, violations=violations),
        failure_fingerprint="fixture-failure" if outcome is not Outcome.PASS else None,
        failure_detail=SECRET,
        events=events,
        final_state={"secret": SECRET},
    )


def _store(
    root: Path, verdict: str, *, malformed: bool = False, drift: bool = False
) -> tuple[Path, str, str]:
    manifest = Manifest.create(
        experiment_id="cli-triage",
        task_id="fixture",
        task={"secret": SECRET},
        toolset="unimportable_fixture:tools",
        contract=ContractSpec(oracle="unimportable_fixture:oracle"),
        baseline=ArmSpec(label="base", agent="unimportable_fixture:base"),
        candidate=ArmSpec(label="candidate", agent="unimportable_fixture:candidate"),
        conditions=(Condition(condition_id="clean"),),
        n_per_arm=20 if verdict == "PASS" else 1,
        delta=0.5,
    )
    store = ExperimentStore(root, manifest)
    trials: list[TrialEnvelope] = []
    schedule = build_schedule(manifest)
    for spec in schedule:
        outcome = Outcome.PASS
        if spec.arm == "candidate":
            outcome = {"BLOCK": Outcome.FAIL, "ERROR": Outcome.ERROR}.get(verdict, Outcome.PASS)
        trial = _trial(
            spec,
            outcome,
            malformed=malformed and spec.arm == "candidate",
            drift=drift and spec.arm == "candidate",
        )
        trials.append(trial)
        store.append_trial(trial)
        for event in trial.events:
            store.append_event(event)
    assert decide(manifest, trials).verdict == verdict
    return store.run_dir, schedule[0].trial_id, schedule[1].trial_id


def _snapshot(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*")
        if path.is_file()
    }


def _document(capsys: pytest.CaptureFixture[str]) -> dict[str, Any]:
    captured = capsys.readouterr()
    assert captured.err == ""
    assert SECRET not in captured.out
    document = cast(dict[str, Any], json.loads(captured.out))
    assert set(document) == TOP_KEYS
    assert document["schema_version"] == "arci-triage/1"
    return document


def test_triage_help_explains_gate_exit_and_diagnostic_limit() -> None:
    done = subprocess.run(
        [sys.executable, "-m", "arci", "triage", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0
    assert done.stderr == ""
    for text in ("RUN_DIR", "CANDIDATE_ID", "--trial", "--format", "INVALID", "gate", "root cause"):
        assert text in done.stdout


@pytest.mark.parametrize(
    "argv", [[], ["run", "--format", "yaml"], ["run", "--trial"], ["run", "--out", "output"]]
)
def test_triage_argument_errors_return_three(
    argv: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["triage", *argv]) == 3
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "error:" in captured.err
    assert "Traceback" not in captured.err


@pytest.mark.parametrize(
    ("verdict", "exit_code"), [("PASS", 0), ("BLOCK", 1), ("INCONCLUSIVE", 2), ("ERROR", 3)]
)
def test_triage_json_preserves_gate_exit_and_never_writes(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    verdict: str,
    exit_code: int,
) -> None:
    run, _, _ = _store(tmp_path, verdict)
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    before = _snapshot(tmp_path)
    assert main(["triage", str(run), "--format", "json"]) == exit_code
    document = _document(capsys)
    assert document["gate"]["verdict"] == verdict
    assert document["gate"]["exit_code"] == exit_code
    assert document["exit_code"] == exit_code
    if verdict != "ERROR":
        condition = document["gate"]["conditions"][0]
        assert condition["condition_id"] == "clean"
        assert condition["baseline"]["successes"] == (20 if verdict == "PASS" else 1)
        assert condition["candidate"]["successes"] == (
            20 if verdict == "PASS" else int(verdict == "INCONCLUSIVE")
        )
    else:
        assert document["status"] == "INVALID"
    if verdict in ("PASS", "INCONCLUSIVE", "ERROR"):
        assert document["selected_pairs"] == []
    else:
        assert document["group_counts"] == {"total": 1, "shown": 1, "omitted": 0}
        assert len(document["selected_pairs"]) == 1
        assert document["selected_pairs"][0]["comparison"]["status"] == "DRIFT"
    assert _snapshot(tmp_path) == before
    assert not summary.exists()


def test_triage_trial_override_selects_pass_without_fabricating_failures(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run, _, candidate = _store(tmp_path, "INCONCLUSIVE")
    assert main(["triage", str(run), "--trial", candidate, "--format", "json"]) == 2
    document = _document(capsys)
    assert document["group_counts"] == {"total": 0, "shown": 0, "omitted": 0}
    assert document["groups"] == []
    assert len(document["selected_pairs"]) == 1
    assert document["selected_pairs"][0]["comparison"]["status"] == "MATCH"


@pytest.mark.parametrize(("verdict", "exit_code"), [("PASS", 0), ("INCONCLUSIVE", 2)])
def test_triage_drift_preserves_passing_candidate_gate_exit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], verdict: str, exit_code: int
) -> None:
    run, _, candidate = _store(tmp_path, verdict, drift=True)
    assert main(["triage", str(run), "--trial", candidate, "--format", "json"]) == exit_code
    document = _document(capsys)
    assert document["gate"]["verdict"] == verdict
    assert document["exit_code"] == exit_code
    assert document["selected_pairs"][0]["candidate_outcome"] == "PASS"
    assert document["selected_pairs"][0]["comparison"]["status"] == "DRIFT"


@pytest.mark.parametrize("selection", ["baseline", "missing-sensitive-trial"])
def test_triage_invalid_trial_selection_overrides_gate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], selection: str
) -> None:
    run, baseline, _ = _store(tmp_path, "BLOCK")
    assert (
        main(
            [
                "triage",
                str(run),
                "--trial",
                baseline if selection == "baseline" else selection,
                "--format",
                "json",
            ]
        )
        == 3
    )
    document = _document(capsys)
    assert document["status"] == "INVALID"
    assert document["gate"]["exit_code"] == 1
    assert document["exit_code"] == 3
    assert document["selected_pairs"] == []
    assert (baseline if selection == "baseline" else selection) not in document["reason"]


def test_triage_duplicated_candidate_is_invalid_without_comparison(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run, _, candidate = _store(tmp_path, "BLOCK")
    path = run / "trials.jsonl"
    records = path.read_text(encoding="utf-8").splitlines()
    duplicate = next(line for line in records if json.loads(line)["trial_id"] == candidate)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(duplicate + "\n")
    before = _snapshot(tmp_path)
    assert main(["triage", str(run), "--trial", candidate, "--format", "json"]) == 3
    document = _document(capsys)
    assert document["status"] == "INVALID"
    assert document["selected_pairs"] == []
    assert _snapshot(tmp_path) == before


def test_triage_malformed_store_never_dumps_parser_payload(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run, _, _ = _store(tmp_path, "BLOCK")
    (run / "manifest.json").write_text('{"' + SECRET, encoding="utf-8")
    before = _snapshot(tmp_path)
    assert main(["triage", str(run), "--format", "json"]) == 3
    document = _document(capsys)
    assert document["status"] == "INVALID"
    assert document["gate"] is None
    assert document["selected_pairs"] == []
    assert _snapshot(tmp_path) == before


def test_triage_invalid_selected_trace_overrides_block(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run, _, _ = _store(tmp_path, "BLOCK", malformed=True)
    assert main(["triage", str(run), "--format", "json"]) == 3
    document = _document(capsys)
    assert document["status"] == "INVALID"
    assert document["gate"]["exit_code"] == 1
    assert document["selected_pairs"] == []


def test_triage_missing_store_is_invalid_json_without_creation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = tmp_path / "missing"
    assert main(["triage", str(missing), "--format", "json"]) == 3
    document = _document(capsys)
    assert document["status"] == "INVALID"
    assert document["gate"] is None
    assert document["selected_pairs"] == []
    assert not missing.exists()


def test_triage_default_text_retains_gate_and_diagnostic_labels(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run, _, _ = _store(tmp_path, "BLOCK")
    assert main(["triage", str(run)]) == 1
    captured = capsys.readouterr()
    assert captured.err == ""
    assert "BLOCK" in captured.out
    assert "DRIFT" in captured.out
    assert "root cause" in captured.out
    assert SECRET not in captured.out
