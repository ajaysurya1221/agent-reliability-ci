from __future__ import annotations

from arci.gate import decide
from arci.schema import Verdict
from tests.acceptance.helpers import COND_CLEAN, COND_TIMEOUT, manifest, synthetic_trials


def test_gate_priority_error_over_block() -> None:
    experiment = manifest(conditions=(COND_CLEAN, COND_TIMEOUT))
    trials = [
        *synthetic_trials(
            experiment,
            condition_id="clean",
            baseline_successes=195,
            candidate_successes=195,
            candidate_errors=1,
        ),
        *synthetic_trials(
            experiment,
            condition_id="fetch_timeout",
            baseline_successes=190,
            candidate_successes=130,
        ),
    ]
    assert decide(experiment, trials).verdict is Verdict.ERROR


def test_gate_priority_block_over_inconclusive() -> None:
    experiment = manifest(conditions=(COND_CLEAN, COND_TIMEOUT))
    trials = [
        *synthetic_trials(
            experiment, condition_id="clean", baseline_successes=170, candidate_successes=170
        ),
        *synthetic_trials(
            experiment,
            condition_id="fetch_timeout",
            baseline_successes=190,
            candidate_successes=130,
        ),
    ]
    assert decide(experiment, trials).verdict is Verdict.BLOCK


def test_gate_priority_inconclusive_over_pass() -> None:
    experiment = manifest(conditions=(COND_CLEAN, COND_TIMEOUT))
    trials = [
        *synthetic_trials(
            experiment, condition_id="clean", baseline_successes=190, candidate_successes=190
        ),
        *synthetic_trials(
            experiment,
            condition_id="fetch_timeout",
            baseline_successes=170,
            candidate_successes=170,
        ),
    ]
    assert decide(experiment, trials).verdict is Verdict.INCONCLUSIVE


def test_gate_passes_only_when_all_gating_conditions_pass() -> None:
    experiment = manifest(conditions=(COND_CLEAN, COND_TIMEOUT))
    trials = [
        *synthetic_trials(
            experiment, condition_id="clean", baseline_successes=195, candidate_successes=195
        ),
        *synthetic_trials(
            experiment,
            condition_id="fetch_timeout",
            baseline_successes=195,
            candidate_successes=195,
        ),
    ]
    assert decide(experiment, trials).verdict is Verdict.PASS
