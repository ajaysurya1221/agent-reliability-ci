from __future__ import annotations

from pathlib import Path

import pytest

from arci.diff import step_signature
from arci.runner import run_experiment, run_trial
from arci.schedule import build_schedule
from arci.schema import Outcome
from arci.storage import load_run
from examples.retry_agent.experiment import build_manifest, clean_manifest
from examples.retry_agent.world import (
    FLAKY_CONFIRM_SHARE,
    PREEXISTING_RESERVATION_SHARE,
    scenario_for_seed,
)


@pytest.mark.parametrize(
    ("candidate", "expected"),
    [("agent_a", 192), ("agent_b", 132), ("agent_c", 192)],
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


def test_fixed_seed_scenario_mix_is_environment_driven() -> None:
    scenarios = [scenario_for_seed(seed) for seed in range(12_000, 12_200)]

    assert PREEXISTING_RESERVATION_SHARE == 0.65
    assert FLAKY_CONFIRM_SHARE == 0.04
    assert sum(scenario.has_reservation for scenario in scenarios) == 135
    assert sum(scenario.flaky_confirm for scenario in scenarios) == 8
    assert (
        sum(scenario.has_reservation and not scenario.flaky_confirm for scenario in scenarios)
        == 132
    )


def test_agent_a_and_b_share_the_trace_prefix_through_the_reserve_fault() -> None:
    manifest = build_manifest(candidate="agent_b")
    schedule = build_schedule(manifest)
    target_seed = next(
        seed
        for seed in range(12_000, 12_200)
        if not scenario_for_seed(seed).has_reservation and not scenario_for_seed(seed).flaky_confirm
    )
    pair = [trial_spec for trial_spec in schedule if trial_spec.seed == target_seed]
    baseline_spec = next(trial_spec for trial_spec in pair if trial_spec.arm == "baseline")
    candidate_spec = next(trial_spec for trial_spec in pair if trial_spec.arm == "candidate")

    baseline = run_trial(baseline_spec, lambda _event: None, manifest.contract)
    candidate = run_trial(candidate_spec, lambda _event: None, manifest.contract)
    baseline_fault = next(
        index
        for index, event in enumerate(baseline.events)
        if event.kind == "tool_finish" and event.payload.get("injected_by") == "tool_timeout"
    )
    candidate_fault = next(
        index
        for index, event in enumerate(candidate.events)
        if event.kind == "tool_finish" and event.payload.get("injected_by") == "tool_timeout"
    )

    assert baseline_fault == candidate_fault
    assert [step_signature(event) for event in baseline.events[: baseline_fault + 1]] == [
        step_signature(event) for event in candidate.events[: candidate_fault + 1]
    ]
