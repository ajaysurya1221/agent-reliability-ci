from __future__ import annotations

from pathlib import Path

import pytest

from arci.runner import run_experiment, run_trial
from arci.schedule import build_schedule
from arci.schema import Outcome
from arci.storage import load_run
from examples.retry_agent.experiment import build_manifest, clean_manifest


@pytest.mark.parametrize(
    ("candidate", "expected"),
    [("agent_a", 189), ("agent_b", 135), ("agent_c", 190)],
)
def test_fixed_200_seed_success_counts(tmp_path: Path, candidate: str, expected: int) -> None:
    manifest = build_manifest(candidate=candidate)
    trials = run_experiment(manifest, tmp_path, max_workers=8)
    successes = sum(trial.outcome is Outcome.PASS for trial in trials if trial.arm == "candidate")
    assert successes == expected

    loaded_manifest, loaded_trials = load_run(tmp_path / manifest.experiment_id)
    assert loaded_manifest == manifest
    assert len(loaded_trials) == len(trials)
    assert {trial.record_sha256 for trial in loaded_trials} == {
        trial.record_sha256 for trial in trials
    }


@pytest.mark.parametrize("candidate", ["agent_a", "agent_b", "agent_c"])
def test_clean_manifest_passes_both_arms(candidate: str) -> None:
    manifest = clean_manifest(candidate)
    outcomes = [
        run_trial(spec, lambda _event: None, manifest.contract).outcome
        for spec in build_schedule(manifest)
    ]
    assert outcomes == [Outcome.PASS, Outcome.PASS]
