from __future__ import annotations

from arci.replay import make_bundle, replay
from arci.runner import run_trial
from arci.schema import Outcome, ReplayStatus
from tests.acceptance.helpers import contract, manifest, spec


def test_tampered_bundle_is_invalid() -> None:
    trial_spec = spec("fragile_agent")
    trial = run_trial(trial_spec, lambda _event: None, contract())
    bundle = make_bundle(manifest(), trial, trial_spec)
    forged = bundle.model_copy(update={"expected_outcome": Outcome.PASS})
    assert replay(forged).status is ReplayStatus.INVALID


def test_bundle_reproduces_failure() -> None:
    trial_spec = spec("fragile_agent")
    trial = run_trial(trial_spec, lambda _event: None, contract())
    bundle = make_bundle(manifest(), trial, trial_spec)
    result = replay(bundle)
    assert result.status is ReplayStatus.REPRODUCED
    assert result.observed_fingerprint == trial.failure_fingerprint
