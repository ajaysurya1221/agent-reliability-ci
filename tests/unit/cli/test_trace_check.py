"""CLI integration for the read-only, non-statistical trace comparator."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import pytest

from arci.cli import main
from arci.diff import first_divergence
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
from arci.storage import ExperimentStore, load_run

REPO = Path(__file__).resolve().parents[3]
SECRET = "sensitive-payload-never-rendered"
TOP_KEYS = {
    "schema_version",
    "status",
    "reason",
    "baseline",
    "candidate",
    "first_difference",
    "limitations",
}
SOURCE_KEYS = {
    "experiment_id",
    "trial_id",
    "manifest_sha256",
    "trial_sha256",
    "decision_sha256",
    "trial_outcome",
    "gate_verdict",
    "gate_exit_code",
}
DIFFERENCE_KEYS = {
    "step",
    "path",
    "baseline_kind",
    "candidate_kind",
    "baseline_sha256",
    "candidate_sha256",
}


def _trial(spec: TrialSpec, *, no_tools: bool, drift: bool, blocked: bool) -> TrialEnvelope:
    events = [
        Event(
            trial_id=spec.trial_id,
            seq=0,
            kind="trial_start",
            payload={"seed": spec.seed, "arm": spec.arm, "variant": spec.variant},
        )
    ]
    if not no_tools:
        events.extend(
            (
                Event(
                    trial_id=spec.trial_id,
                    seq=1,
                    kind="tool_start",
                    payload={
                        "call_id": "c-0000",
                        "tool": "inspect",
                        "occurrence": 0,
                        "arguments": {"token": SECRET},
                    },
                ),
                Event(
                    trial_id=spec.trial_id,
                    seq=2,
                    kind="tool_finish",
                    payload={
                        "call_id": "c-0000",
                        "tool": "inspect",
                        "ok": True,
                        "value": {"token": SECRET, "amount": 2 if drift else 1},
                        "error_kind": None,
                        "injected_by": None,
                    },
                ),
            )
        )
    events.append(
        Event(
            trial_id=spec.trial_id,
            seq=len(events),
            kind="agent_result",
            payload={"result": {"success": True, "token": SECRET}},
        )
    )
    events.append(Event(trial_id=spec.trial_id, seq=len(events), kind="trial_end"))
    violations = (
        (Violation(invariant="forbidden_tool", severity="hard", detail="fixture"),)
        if blocked
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
        outcome=Outcome.FAIL if blocked else Outcome.PASS,
        termination=Termination.COMPLETED,
        agent_claimed_success=True,
        contract=ContractResult(success=True, violations=violations),
        failure_fingerprint="fixture-failure" if blocked else None,
        events=tuple(events),
        final_state={"token": SECRET},
    )


def _store(
    root: Path, *, no_tools: bool = False, drift: bool = False, blocked: bool = False
) -> tuple[Path, str, str]:
    manifest = Manifest.create(
        experiment_id="cli-trace",
        task_id="fixture",
        task={"token": SECRET},
        toolset="unimportable_fixture:tools",
        contract=ContractSpec(oracle="unimportable_fixture:oracle"),
        baseline=ArmSpec(label="base", agent="unimportable_fixture:base"),
        candidate=ArmSpec(label="candidate", agent="unimportable_fixture:candidate"),
        conditions=(Condition(condition_id="clean"),),
        n_per_arm=1,
    )
    store = ExperimentStore(root, manifest)
    for spec in build_schedule(manifest):
        trial = _trial(
            spec,
            no_tools=no_tools,
            drift=drift and spec.arm == "candidate",
            blocked=blocked and spec.arm == "candidate",
        )
        store.append_trial(trial)
        for event in trial.events:
            store.append_event(event)
    baseline, candidate = build_schedule(manifest)
    return store.run_dir, baseline.trial_id, candidate.trial_id


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
    assert document["schema_version"] == "arci-trace-check/1"
    for side in ("baseline", "candidate"):
        source = document[side]
        if source is not None:
            assert set(source) == SOURCE_KEYS
            for key in ("manifest_sha256", "trial_sha256", "decision_sha256"):
                assert re.fullmatch("[0-9a-f]{64}", source[key])
    return document


def test_trace_check_help_names_diagnostic_statuses() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "arci", "trace-check", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0
    assert completed.stderr == ""
    assert completed.stdout.startswith("usage: arci trace-check")
    for text in ("BASE_RUN", "BASE_TRIAL", "CAND_RUN", "CAND_TRIAL", "MATCH", "DRIFT", "INVALID"):
        assert text in completed.stdout


def test_missing_store_is_invalid_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    missing = tmp_path / "not-present"
    assert (
        main(["trace-check", str(missing), "base", str(missing), "cand", "--format", "json"]) == 3
    )
    captured = capsys.readouterr()
    assert captured.err == ""
    document = json.loads(captured.out)
    assert document["schema_version"] == "arci-trace-check/1"
    assert document["status"] == "INVALID"
    assert document["first_difference"] is None
    assert not missing.exists()


@pytest.mark.parametrize("no_tools", [False, True])
def test_match_json_and_no_source_or_summary_writes(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    no_tools: bool,
) -> None:
    run, baseline, candidate = _store(tmp_path, no_tools=no_tools)
    summary = tmp_path / "summary.md"
    summary.write_text("existing summary\n", encoding="utf-8")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    before = _snapshot(tmp_path)
    assert main(["trace-check", str(run), baseline, str(run), candidate, "--format", "json"]) == 0
    document = _document(capsys)
    assert document["status"] == "MATCH"
    assert document["first_difference"] is None
    manifest, trials = load_run(run)
    decision = decide(manifest, trials)
    assert decision.exit_code == 2
    for side in ("baseline", "candidate"):
        assert document[side]["trial_outcome"] == "PASS"
        assert document[side]["gate_verdict"] == "INCONCLUSIVE"
        assert document[side]["gate_exit_code"] == 2
        assert document[side]["decision_sha256"] == decision.record_sha256
    assert _snapshot(tmp_path) == before


def test_drift_json_and_source_hashes_are_unchanged(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    run, baseline, candidate = _store(tmp_path, drift=True)
    summary = tmp_path / "absent-summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    before = _snapshot(tmp_path)
    assert main(["trace-check", str(run), baseline, str(run), candidate, "--format", "json"]) == 1
    document = _document(capsys)
    assert document["status"] == "DRIFT"
    difference = document["first_difference"]
    assert set(difference) == DIFFERENCE_KEYS
    assert difference["step"] == 1
    assert difference["path"] == "/payload/value/amount"
    assert difference["baseline_kind"] == difference["candidate_kind"] == "tool_finish"
    for side in ("baseline_sha256", "candidate_sha256"):
        assert re.fullmatch("[0-9a-f]{64}", difference[side])
    assert difference["baseline_sha256"] != difference["candidate_sha256"]
    assert _snapshot(tmp_path) == before


def test_text_default_keeps_block_separate_from_match(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run, baseline, _candidate = _store(tmp_path, blocked=True)
    assert main(["trace-check", str(run), baseline, str(run), baseline]) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    assert "MATCH" in captured.out
    assert "BLOCK" in captured.out
    assert "PASS" in captured.out
    assert SECRET not in captured.out
    assert main(["trace-check", str(run), baseline, str(run), baseline, "--format", "text"]) == 0
    assert capsys.readouterr().out == captured.out


def test_unknown_trial_is_invalid_without_echoing_the_identifier(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run, baseline, _candidate = _store(tmp_path)
    assert main(["trace-check", str(run), baseline, str(run), SECRET, "--format", "json"]) == 3
    document = _document(capsys)
    assert document["status"] == "INVALID"
    assert document["first_difference"] is None


def test_malformed_store_is_invalid_without_payloads_or_writes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    run, baseline, candidate = _store(tmp_path)
    (run / "manifest.json").write_text(f'{{"invalid": "{SECRET}"}}', encoding="utf-8")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "absent-summary.md"))
    before = _snapshot(tmp_path)
    assert main(["trace-check", str(run), baseline, str(run), candidate, "--format", "json"]) == 3
    document = _document(capsys)
    assert document["status"] == "INVALID"
    assert document["first_difference"] is None
    assert _snapshot(tmp_path) == before


@pytest.mark.parametrize(
    "arguments",
    [
        [],
        ["run", "trial"],
        ["run", "trial", "run", "trial", "--format", "yaml"],
        ["run", "trial", "run", "trial", "--all-steps"],
        ["run", "trial", "run", "trial", "--out", "file"],
    ],
)
def test_invalid_arguments_return_three_without_a_traceback(
    arguments: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["trace-check", *arguments]) == 3
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("error: CliError:")
    assert "Traceback" not in captured.err


@pytest.mark.parametrize("all_steps", [False, True])
def test_legacy_diff_output_and_exit_code_stay_unchanged(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], all_steps: bool
) -> None:
    run, baseline, candidate = _store(tmp_path, drift=True)
    _manifest, trials = load_run(run)
    mode = "all" if all_steps else "boundary"
    difference = first_divergence(trials[0], trials[1], mode=mode)
    assert (
        main(["diff", str(run), baseline, candidate, *(["--all-steps"] if all_steps else [])]) == 0
    )
    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out == (
        f"mode: {mode}\ncommon_prefix: {difference.common_prefix}\n"
        f"left: {difference.left}\nright: {difference.right}\n"
        f"after_injection: {difference.after_injection}\n"
    )


@pytest.mark.parametrize("gate_exit", [0, 1, 2, 3])
@pytest.mark.parametrize("trace_exit", [0, 1, 3])
def test_documented_ci_composition_preserves_gate_failures(
    tmp_path: Path, gate_exit: int, trace_exit: int
) -> None:
    recipe = (REPO / "docs/recipes/trace-check.md").read_text(encoding="utf-8")
    blocks = re.findall(r"```bash\n(.*?)```", recipe, flags=re.DOTALL)
    [script] = [
        block
        for block in blocks
        if block.startswith("# CI gate composition (run in a separate shell)")
    ]
    arci_stub = tmp_path / "arci"
    arci_stub.write_text(
        "#!/bin/sh\n"
        'printf "%s\\n" "$@" >>"$CALL_LOG"\n'
        'case "$1" in\n'
        '  gate) exit "$GATE_EXIT" ;;\n'
        '  trace-check) printf \'{"status":"%s"}\\n\' "$TRACE_STATUS"; exit "$TRACE_EXIT" ;;\n'
        "  *) exit 99 ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    arci_stub.chmod(0o755)
    log = tmp_path / "calls.txt"
    env = {
        **os.environ,
        "PATH": f"{tmp_path}{os.pathsep}{os.environ.get('PATH', '')}",
        "CALL_LOG": str(log),
        "GATE_EXIT": str(gate_exit),
        "TRACE_EXIT": str(trace_exit),
        "TRACE_STATUS": {0: "MATCH", 1: "DRIFT", 3: "INVALID"}[trace_exit],
        "BASE_RUN": "base run",
        "BASE_TRIAL": "base trial",
        "CAND_RUN": "candidate run",
        "CAND_TRIAL": "candidate trial",
    }
    completed = subprocess.run(
        ["bash", "-eu", "-c", script],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == (gate_exit or trace_exit), completed.stderr
    assert completed.stderr == ""
    assert log.read_text(encoding="utf-8").splitlines() == [
        "gate",
        "candidate run",
        "trace-check",
        "base run",
        "base trial",
        "candidate run",
        "candidate trial",
        "--format",
        "json",
    ]
    assert json.loads((tmp_path / "trace-check.json").read_text(encoding="utf-8")) == {
        "status": {0: "MATCH", 1: "DRIFT", 3: "INVALID"}[trace_exit]
    }
