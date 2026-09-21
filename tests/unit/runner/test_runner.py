from __future__ import annotations

from arci.runner import run_trial
from arci.schema import Outcome, Termination
from tests.acceptance.helpers import COND_CLEAN, contract, spec


def test_same_spec_has_stable_seal() -> None:
    trial_spec = spec("fragile_agent")
    left = run_trial(trial_spec, lambda _event: None, contract())
    right = run_trial(trial_spec, lambda _event: None, contract())
    assert left.record_sha256 == right.record_sha256


def test_oracle_not_agent_claim_decides_outcome() -> None:
    trial = run_trial(spec("liar_agent", condition=COND_CLEAN), lambda _event: None, contract())
    assert trial.agent_claimed_success is True
    assert trial.outcome is Outcome.FAIL
    assert trial.termination is Termination.COMPLETED
