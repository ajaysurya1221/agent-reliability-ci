"""Review regressions that also run without the optional framework."""

from __future__ import annotations

import importlib
import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from pydantic import JsonValue

from arci import cli
from arci.descriptor import loads_suite_descriptor
from arci.schema import Outcome, Termination, TrialEnvelope
from arci.suite_gate import decide_suite
from arci.suite_schedule import build_suite_round
from arci.suite_storage import SuiteStore
from examples.langchain_quickstart.check import check
from examples.langchain_quickstart.configuration import resolve_settings, validate_registration
from tests.unit.examples.test_langchain_quickstart import EXAMPLE
from tests.unit.suite.helpers import envelope, gate_manifest


@pytest.fixture(autouse=True)
def clear_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("BASELINE", "CANDIDATE", "TEMPERATURE"):
        monkeypatch.delenv(f"ARCI_QUICKSTART_{name}", raising=False)


@pytest.mark.parametrize("arm", ["BASELINE", "CANDIDATE"])
def test_one_model_is_setup_error(monkeypatch: pytest.MonkeyPatch, arm: str) -> None:
    monkeypatch.setenv(f"ARCI_QUICKSTART_{arm}", "ollama:test")
    with pytest.raises(ValueError, match="set both"):
        resolve_settings()


@pytest.mark.parametrize("temperature", ["0", "-1", "nan", "inf"])
def test_real_temperature_must_vary(monkeypatch: pytest.MonkeyPatch, temperature: str) -> None:
    monkeypatch.setenv("ARCI_QUICKSTART_BASELINE", "ollama:a")
    monkeypatch.setenv("ARCI_QUICKSTART_CANDIDATE", "ollama:b")
    monkeypatch.setenv("ARCI_QUICKSTART_TEMPERATURE", temperature)
    with pytest.raises(ValueError, match="temperature"):
        resolve_settings()


def test_settings_are_sealed_and_environment_must_match(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shutil.copytree(EXAMPLE, tmp_path, dirs_exist_ok=True)
    monkeypatch.syspath_prepend(str(EXAMPLE))
    register = importlib.import_module("register").register

    def manifest() -> Any:
        path = tmp_path / "arci.yaml"
        return loads_suite_descriptor(path.read_text(), str(path))

    offline = manifest()
    register(tmp_path)
    assert manifest().experiment_id == offline.experiment_id
    assert validate_registration(offline.tasks[0].task) == resolve_settings()
    monkeypatch.setenv("ARCI_QUICKSTART_BASELINE", "ollama:a")
    monkeypatch.setenv("ARCI_QUICKSTART_CANDIDATE", "ollama:b")
    with pytest.raises(ValueError, match="disagrees with registered"):
        validate_registration(offline.tasks[0].task)
    register(tmp_path)
    live = manifest()
    assert live.experiment_id != offline.experiment_id
    assert live.scenario_seeds == "per_round"
    settings = validate_registration(live.tasks[0].task)
    assert settings["temperature"] == 0.7
    assert settings["baseline_reasoning"] is False
    assert settings["candidate_reasoning"] is False
    ids = {offline.experiment_id, live.experiment_id}
    for variable, value in (
        ("BASELINE", "ollama:c"),
        ("CANDIDATE", "ollama:d"),
        ("TEMPERATURE", "0.9"),
    ):
        monkeypatch.setenv(f"ARCI_QUICKSTART_{variable}", value)
        with pytest.raises(ValueError, match="disagrees with registered"):
            validate_registration(live.tasks[0].task)
        register(tmp_path)
        live = manifest()
        assert live.experiment_id not in ids
        ids.add(live.experiment_id)
    # Reasoning policy is part of the sealed task too, even without a new model id.
    path = tmp_path / "tasks.jsonl"
    tasks = [json.loads(line) for line in path.read_text().splitlines()]
    for task in tasks:
        task["quickstart_settings"]["baseline_reasoning"] = True
    path.write_text("".join(json.dumps(task) + "\n" for task in tasks))
    changed = manifest()
    assert changed.experiment_id not in ids
    with pytest.raises(ValueError, match="disagrees with registered"):
        validate_registration(changed.tasks[0].task)


def test_plain_refund_does_not_require_unrequested_empty_notes() -> None:
    task: dict[str, JsonValue] = {"order_id": "ORD-101", "action": "refund"}
    state: dict[str, JsonValue] = {
        "state": {
            "order_id": "ORD-101",
            "order": {"total_cents": 50, "refunded_cents": 50, "notes": ["refunded"]},
        }
    }
    assert check(task, state)
    with pytest.raises(ValueError, match="unknown grading action"):
        check({"action": "typo"}, {})


@pytest.mark.parametrize("passed", [0, 47, 48])
def test_run_and_gate_show_arm_success_and_threshold(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], passed: int
) -> None:
    manifest = gate_manifest(
        max_rounds=1,
        acknowledge_single_round=True,
        tasks=tuple({"task_id": f"task-{i:03d}"} for i in range(96)),
    )
    trials = tuple(
        envelope(spec, Outcome.PASS if i // 2 < passed else Outcome.FAIL)
        for i, spec in enumerate(build_suite_round(manifest, 1))
    )
    store = SuiteStore(tmp_path, manifest)
    store.write_round(1, trials, [])
    store.write_decision(decide_suite(manifest, trials))
    run_dir = tmp_path / manifest.experiment_id

    def recorded_run(*args: Any, **kwargs: Any) -> tuple[TrialEnvelope, ...]:
        return trials

    monkeypatch.setattr(cli, "run_suite", recorded_run)
    for args in (["run", str(run_dir / "manifest.json")], ["gate", str(run_dir)]):
        assert cli.main(args) == 0
        output = capsys.readouterr().out
        assert f"baseline {passed}/96 passed, candidate {passed}/96 passed" in output
        assert output.count("WARNING: baseline") == (1 if passed < 48 else 0)


def test_error_summary_reports_first_detail_and_frequency(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    manifest = gate_manifest(max_errored_pairs=0)
    trials = tuple(
        TrialEnvelope.create(
            **{
                **envelope(spec, Outcome.ERROR).model_dump(exclude={"record_sha256"}),
                "termination": Termination.HARNESS_ERROR,
                "failure_detail": "first setup problem" if i < 7 else "second problem",
            }
        )
        for i, spec in enumerate(build_suite_round(manifest, 1))
    )
    store = SuiteStore(tmp_path, manifest)
    store.write_round(1, trials, [])
    store.write_decision(decide_suite(manifest, trials))
    run_dir = tmp_path / manifest.experiment_id

    def recorded_run(*args: Any, **kwargs: Any) -> tuple[TrialEnvelope, ...]:
        return trials

    monkeypatch.setattr(cli, "run_suite", recorded_run)
    for args in (["run", str(run_dir / "manifest.json")], ["gate", str(run_dir)]):
        assert cli.main(args) == 3
        output = capsys.readouterr().out
        assert "first harness error (7 trials): first setup problem" in output


def test_readme_and_recipe_cover_review_limits() -> None:
    readme = (EXAMPLE / "README.md").read_text()
    recipe = (EXAMPLE.parents[1] / "docs/recipes/langchain.md").read_text()
    assert "agent-reliability-ci[langchain]>=2.0.0" in readme
    for text in (readme, recipe):
        for command in (
            "report",
            "triage",
            "diff",
            "plan",
            "minimize",
            "bundle",
            "replay",
            "trace-check",
        ):
            assert f"`{command}`" in text
        assert "trials.jsonl" in text
        assert "diluted into ties" in text
        assert "ValueError" in text
        assert "any model turn" in text


def test_end_to_end_timeout_has_threefold_headroom(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import subprocess

    from tests.unit.examples.test_langchain_quickstart import arci

    def record_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        # Measured offline runs are below two minutes, including the loaded-host run.
        assert kwargs["timeout"] >= 3 * 120
        return subprocess.CompletedProcess(args[0], 0, "", "")

    monkeypatch.setattr(subprocess, "run", record_run)
    arci(tmp_path, "run", "arci.yaml")
