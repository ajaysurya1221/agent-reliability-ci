"""Real subprocess suite runs and routing of commands without suite support."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from arci.cli import main
from arci.suite_schema import SuiteDecision
from tests.unit.suite_cli.test_descriptor import TEXT


def cli(*args: str, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(sys.path)
    return subprocess.run(
        [sys.executable, "-m", "arci.cli", *args],
        input=input_text,
        capture_output=True,
        text=True,
        timeout=150,
        env=env,
    )


@pytest.mark.parametrize(
    "candidate,code,verdict,rounds",
    [
        ("control", 0, "PASS", 4),
        ("regression", 1, "BLOCK", 1),
        ("uncertain", 2, "INCONCLUSIVE", 4),
    ],
)
def test_run_gate_real_fixture(
    tmp_path: Path, candidate: str, code: int, verdict: str, rounds: int
) -> None:
    path = tmp_path / "arci.yaml"
    path.write_text(
        TEXT.replace(
            "candidate: arci.demo.suite:control", f"candidate: arci.demo.suite:{candidate}"
        )
        + "rule: {scenario_seeds: per_round, max_rounds: 4, max_errored_pairs: 1}\n"
    )
    result = cli("run", str(path), "--out", str(tmp_path / "runs"), "--workers", "2")
    assert result.returncode == code, result.stdout + result.stderr
    assert f"VERDICT: {verdict}" in result.stdout
    (run_dir,) = (tmp_path / "runs").iterdir()
    stored = (run_dir / "decision.json").read_bytes()
    decision = SuiteDecision.model_validate_json(stored)
    if candidate == "regression":
        rounds = decision.stopped_at_round
        assert 1 <= rounds <= 4
    else:
        assert decision.stopped_at_round == rounds
    from arci.suite_storage import load_suite_run
    from tests.unit.suite_cli.test_review_fixes import assert_summary
    from tests.unit.suite_runner.test_review_fixes import events_at

    _, trials = load_suite_run(run_dir)
    assert events_at(run_dir / "events.jsonl") == tuple(e for t in trials for e in t.events)
    assert_summary(result.stdout, decision, len(trials))
    gate = cli("gate", str(run_dir))
    assert gate.returncode == code, gate.stdout + gate.stderr
    assert_summary(gate.stdout, decision, len(trials))
    assert "stored decision: MATCH" in gate.stdout
    assert f"stopping round: {rounds}" in gate.stdout
    assert f"pairs: {20 * rounds}" in gate.stdout
    assert (
        "counts:" in gate.stdout
        and "PASS wealth:" in gate.stdout
        and "BLOCK wealth:" in gate.stdout
    )
    assert "errored pairs:" in gate.stdout and "threshold: 40/1" in gate.stdout
    assert (
        "Its error guarantee requires that in every round the suite mean "
        "over that round's scenario instances obey the relevant null" in gate.stdout
    )
    assert (run_dir / "decision.json").read_bytes() == stored
    report = cli("report", str(run_dir), "--format", "json")
    assert report.returncode == code, report.stdout + report.stderr
    assert json.loads(report.stdout)["decision"] == decision.model_dump(mode="json")
    diagnostic = cli("triage", str(run_dir), "--format", "json")
    assert diagnostic.returncode == code, diagnostic.stdout + diagnostic.stderr
    assert json.loads(diagnostic.stdout)["gate"]["verdict"] == verdict
    difference = cli("diff", str(run_dir), trials[0].trial_id, trials[1].trial_id)
    assert difference.returncode == 0, difference.stdout + difference.stderr
    assert (run_dir / "decision.json").read_bytes() == stored


@pytest.mark.parametrize("command", ["minimize", "bundle", "replay", "trace-check"])
@pytest.mark.parametrize("input_kind", ["descriptor", "store"])
def test_deferred_commands(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], command: str, input_kind: str
) -> None:
    path = tmp_path / "suite.yaml"
    if input_kind == "descriptor":
        path.write_text(TEXT)
    else:
        path = tmp_path / "store"
        path.mkdir()
        (path / "manifest.json").write_text(json.dumps({"schema_version": "arci-suite/1"}))
    assert main([command, str(path)]) == 3
    output = capsys.readouterr()
    lines = (output.out + output.err).splitlines()
    assert lines == [f"suite support for {command} is not built yet"]


def test_gate_does_not_overwrite_mismatched_decision(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from arci.suite_gate import decide_suite
    from arci.suite_schedule import build_suite_round
    from arci.suite_storage import SuiteStore
    from tests.unit.suite_runner.test_runner import envelope, manifest

    m = manifest()
    store = SuiteStore(tmp_path, m)
    # A partial round is invalid even without a saved decision.
    store.append_trial(envelope(build_suite_round(m, 1)[0]))
    assert main(["gate", str(store.run_dir)]) == 3
    assert "VERDICT: ERROR" in capsys.readouterr().out
    decision = decide_suite(m, ())
    store.write_decision(decision)
    saved = (store.run_dir / "decision.json").read_bytes()
    assert main(["gate", str(store.run_dir)]) == 3
    assert "stored decision: MISMATCH" in capsys.readouterr().out
    assert (store.run_dir / "decision.json").read_bytes() == saved


def test_mismatched_pass_store_prints_error_as_the_verdict(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from arci.suite_gate import decide_suite
    from arci.suite_schedule import build_suite_schedule
    from arci.suite_storage import SuiteStore
    from tests.unit.suite_runner.test_runner import envelope, manifest

    m = manifest()
    store = SuiteStore(tmp_path, m)
    trials = tuple(envelope(spec) for spec in build_suite_schedule(m))
    for trial in trials:
        store.append_trial(trial)
    decision = decide_suite(m, trials)
    assert decision.exit_code == 0
    # A validly sealed, contradictory stored decision must not look like a green gate.
    store.write_decision(
        SuiteDecision.create(
            **{
                **decision.model_dump(exclude={"record_sha256"}),
                "reasons": ("different reason",),
            }
        )
    )
    assert main(["gate", str(store.run_dir)]) == 3
    assert capsys.readouterr().out.startswith("VERDICT: ERROR (exit 3)")
