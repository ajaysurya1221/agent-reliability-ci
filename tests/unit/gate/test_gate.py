from __future__ import annotations

import pytest

import arci.gate as gate_module
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


def test_gate_passes_the_bonferroni_tail_directly(monkeypatch: pytest.MonkeyPatch) -> None:
    experiment = manifest(alpha=0.04, conditions=(COND_CLEAN, COND_TIMEOUT))
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
    observed: list[float] = []
    original = gate_module.clopper_pearson_tail

    def recording_interval(successes: int, n: int, tail: float) -> tuple[float, float]:
        observed.append(tail)
        return original(successes, n, tail)

    monkeypatch.setattr(gate_module, "clopper_pearson_tail", recording_interval)
    decision = decide(experiment, trials)

    assert decision.verdict is Verdict.PASS
    assert decision.per_arm_confidence == pytest.approx(0.99)
    assert observed == pytest.approx([0.005] * 4)


def test_gate_returns_error_when_adjusted_tail_is_outside_supported_range() -> None:
    experiment = manifest(alpha=1e-6, conditions=(COND_CLEAN, COND_TIMEOUT))
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

    decision = decide(experiment, trials)

    assert decision.verdict is Verdict.ERROR
    assert "statistical interval error" in decision.reasons
