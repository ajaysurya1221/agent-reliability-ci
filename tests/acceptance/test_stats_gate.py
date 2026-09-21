"""Statistical contract. FROZEN. Golden values from scipy.stats.binomtest(...).proportion_ci."""

from __future__ import annotations

import pytest

from arci.schema import EXIT_CODES, Verdict
from tests.acceptance.helpers import (
    COND_CEILING,
    COND_CLEAN,
    COND_TIMEOUT,
    manifest,
    reseal,
    synthetic_trials,
)

pytestmark = pytest.mark.acceptance

CP_GOLDEN = [
    (190, 200, 0.975, 0.903744200551, 0.978351375522),
    (130, 200, 0.975, 0.569630393398, 0.724655682038),
    (0, 20, 0.975, 0.0, 0.196759679705),
    (20, 20, 0.975, 0.803240320295, 1.0),
    (19, 20, 0.975, 0.720677509796, 0.999371258630),
    (13, 20, 0.975, 0.377936165362, 0.865327076539),
    (1, 10000, 0.975, 0.000001257877, 0.000637920920),
    (9999, 10000, 0.975, 0.999362079080, 0.999998742123),
    (5000, 10000, 0.975, 0.488744692327, 0.511255307673),
    (190, 200, 0.9875, 0.897867622022, 0.980531985264),
    (3, 7, 0.95, 0.098988278443, 0.815948432360),
]


@pytest.mark.parametrize(("x", "n", "conf", "low", "high"), CP_GOLDEN)
def test_clopper_pearson_matches_exact_reference(
    x: int, n: int, conf: float, low: float, high: float
) -> None:
    from arci.stats import clopper_pearson

    got_low, got_high = clopper_pearson(x, n, conf)
    assert got_low == pytest.approx(low, rel=0, abs=1e-9)
    assert got_high == pytest.approx(high, rel=0, abs=1e-9)


def test_wilson_is_display_only_but_correct() -> None:
    from arci.stats import wilson

    assert wilson(19, 20, 0.95) == pytest.approx((0.7638688066, 0.9911185512), abs=1e-8)
    assert wilson(13, 20, 0.95) == pytest.approx((0.4328542767, 0.8188081759), abs=1e-8)


@pytest.mark.parametrize(
    ("x", "n", "conf"),
    [(-1, 10, 0.95), (11, 10, 0.95), (1, 0, 0.95), (1, 10, 0.0), (1, 10, 1.0), (1, 10001, 0.95)],
)
def test_invalid_inputs_raise(x: int, n: int, conf: float) -> None:
    from arci.stats import clopper_pearson

    with pytest.raises(ValueError):
        clopper_pearson(x, n, conf)


def test_per_arm_confidence_and_difference_bounds() -> None:
    from arci.stats import difference_bounds, per_arm_confidence

    assert per_arm_confidence(0.05, 1) == pytest.approx(0.975)
    assert per_arm_confidence(0.05, 2) == pytest.approx(0.9875)
    low, high = difference_bounds(baseline=(0.9037, 0.9784), candidate=(0.5696, 0.7247))
    assert (low, high) == pytest.approx((0.5696 - 0.9784, 0.7247 - 0.9037))


def test_block_on_clear_regression() -> None:
    from arci.gate import decide, replay_decision

    m = manifest()
    trials = synthetic_trials(
        m, condition_id="fetch_timeout", baseline_successes=190, candidate_successes=130
    )
    d = decide(m, trials)
    assert d.verdict is Verdict.BLOCK
    assert d.exit_code == EXIT_CODES[Verdict.BLOCK] == 1
    c = d.conditions[0]
    assert c.delta_low == pytest.approx(-0.4087, abs=1e-3)
    assert c.delta_high == pytest.approx(-0.1791, abs=1e-3)
    assert d.per_arm_confidence == pytest.approx(0.975)
    assert d.validate_seal()
    assert replay_decision(d, m, trials)
    assert decide(m, trials) == d  # pure


def test_pass_when_non_inferior() -> None:
    from arci.gate import decide

    m = manifest()
    d = decide(
        m,
        synthetic_trials(
            m, condition_id="fetch_timeout", baseline_successes=190, candidate_successes=190
        ),
    )
    assert d.verdict is Verdict.PASS
    assert d.exit_code == 0


def test_twenty_per_arm_is_inconclusive_not_block() -> None:
    from arci.gate import decide

    m = manifest(n_per_arm=20)
    d = decide(
        m,
        synthetic_trials(
            m, condition_id="fetch_timeout", baseline_successes=19, candidate_successes=13
        ),
    )
    assert d.verdict is Verdict.INCONCLUSIVE
    assert d.exit_code == 2


def test_error_trial_invalidates_experiment() -> None:
    from arci.gate import decide

    m = manifest()
    d = decide(
        m,
        synthetic_trials(
            m,
            condition_id="fetch_timeout",
            baseline_successes=190,
            candidate_successes=190,
            candidate_errors=1,
        ),
    )
    assert d.verdict is Verdict.ERROR
    assert d.exit_code == 3


def test_short_or_duplicated_run_cannot_pass() -> None:
    from arci.gate import decide

    m = manifest()
    short = synthetic_trials(
        m, condition_id="fetch_timeout", baseline_successes=150, candidate_successes=150, n=150
    )
    assert decide(m, short).verdict is Verdict.ERROR
    full = synthetic_trials(
        m, condition_id="fetch_timeout", baseline_successes=190, candidate_successes=190
    )
    assert decide(m, [*full, full[0]]).verdict is Verdict.ERROR


def test_hard_violation_blocks_independently() -> None:
    from arci.gate import decide

    m = manifest()
    d = decide(
        m,
        synthetic_trials(
            m,
            condition_id="fetch_timeout",
            baseline_successes=190,
            candidate_successes=190,
            candidate_hard_violations=1,
        ),
    )
    assert d.verdict is Verdict.BLOCK
    assert d.conditions[0].candidate_hard_violations == 1


def test_two_conditions_split_alpha_and_any_block_blocks() -> None:
    from arci.gate import decide

    m = manifest(conditions=(COND_CLEAN, COND_TIMEOUT))
    trials = [
        *synthetic_trials(m, condition_id="clean", baseline_successes=195, candidate_successes=195),
        *synthetic_trials(
            m, condition_id="fetch_timeout", baseline_successes=190, candidate_successes=130
        ),
    ]
    d = decide(m, trials)
    assert d.k_conditions == 2
    assert d.per_arm_confidence == pytest.approx(0.9875)
    assert {c.condition_id: c.verdict for c in d.conditions} == {
        "clean": Verdict.PASS,
        "fetch_timeout": Verdict.BLOCK,
    }
    assert d.verdict is Verdict.BLOCK


def test_prior_runs_are_carried_into_the_decision() -> None:
    from arci.gate import decide

    m = manifest(prior_runs=("exp-earlier-1", "exp-earlier-2"))
    d = decide(
        m,
        synthetic_trials(
            m, condition_id="fetch_timeout", baseline_successes=190, candidate_successes=190
        ),
    )
    assert d.prior_runs == ("exp-earlier-1", "exp-earlier-2")


def test_forged_manifest_is_an_error_not_a_friendlier_verdict() -> None:
    from arci.gate import decide

    m = manifest()
    trials = synthetic_trials(
        m, condition_id="fetch_timeout", baseline_successes=190, candidate_successes=130
    )
    assert decide(m, trials).verdict is Verdict.BLOCK
    forged = m.model_copy(update={"delta": 0.9})  # specs and trial seals are untouched
    assert decide(forged, trials).verdict is Verdict.ERROR


def test_tampered_decision_fails_validation() -> None:
    from arci.gate import decide

    m = manifest()
    d = decide(
        m,
        synthetic_trials(
            m, condition_id="fetch_timeout", baseline_successes=190, candidate_successes=130
        ),
    )
    forged = d.model_copy(update={"verdict": Verdict.PASS, "exit_code": 0})
    assert not forged.validate_seal()


def test_gate_uses_clopper_pearson_not_wilson() -> None:
    """170/200 in both arms: CP lower bound -0.1177 (INCONCLUSIVE); Wilson would say PASS."""
    from arci.gate import decide

    m = manifest()
    d = decide(
        m,
        synthetic_trials(
            m, condition_id="fetch_timeout", baseline_successes=170, candidate_successes=170
        ),
    )
    assert d.verdict is Verdict.INCONCLUSIVE and d.exit_code == 2
    assert d.conditions[0].delta_low == pytest.approx(-0.117665507158, rel=0, abs=1e-8)


def test_boundaries_are_strict() -> None:
    from arci.gate import classify

    assert classify(-0.10, 0.05, 0.10) is Verdict.INCONCLUSIVE  # L == -delta is not a PASS
    assert classify(-0.30, -0.10, 0.10) is Verdict.INCONCLUSIVE  # U == -delta is not a BLOCK
    assert classify(-0.0999, 0.05, 0.10) is Verdict.PASS
    assert classify(-0.30, -0.1001, 0.10) is Verdict.BLOCK


def test_non_default_alpha_widens_the_intervals() -> None:
    from arci.gate import decide

    m = manifest(alpha=0.01)
    same = synthetic_trials(
        m, condition_id="fetch_timeout", baseline_successes=190, candidate_successes=190
    )
    d = decide(m, same)
    assert d.per_arm_confidence == pytest.approx(0.995)
    assert d.conditions[0].delta_low == pytest.approx(-0.092432736643, rel=0, abs=1e-8)
    assert d.verdict is Verdict.PASS
    weaker = synthetic_trials(
        m, condition_id="fetch_timeout", baseline_successes=176, candidate_successes=176
    )
    assert decide(m, weaker).verdict is Verdict.INCONCLUSIVE


def test_error_outranks_block() -> None:
    from arci.gate import decide

    m = manifest(conditions=(COND_CLEAN, COND_TIMEOUT))
    trials = [
        *synthetic_trials(
            m,
            condition_id="clean",
            baseline_successes=195,
            candidate_successes=195,
            candidate_errors=1,
        ),
        *synthetic_trials(
            m, condition_id="fetch_timeout", baseline_successes=190, candidate_successes=130
        ),
    ]
    assert decide(m, trials).verdict is Verdict.ERROR


@pytest.mark.parametrize(
    "mutation",
    [
        "unknown_id",
        "foreign_experiment",
        "foreign_task",
        "wrong_spec_hash",
        "wrong_seed",
        "broken_seal",
        "replaced_duplicate",
    ],
)
def test_trials_must_match_the_schedule_exactly(mutation: str) -> None:
    from arci.gate import decide

    m = manifest()
    trials = synthetic_trials(
        m, condition_id="fetch_timeout", baseline_successes=190, candidate_successes=190
    )
    assert decide(m, trials).verdict is Verdict.PASS
    victim = trials[-1]
    impostor = {
        "unknown_id": lambda: reseal(victim, trial_id="fetch_timeout:99999:candidate"),
        "foreign_experiment": lambda: reseal(victim, experiment_id="someone-elses-run"),
        "foreign_task": lambda: reseal(victim, task_id="another-task"),
        "wrong_spec_hash": lambda: reseal(victim, spec_sha256="1" * 64),
        "wrong_seed": lambda: reseal(victim, seed=victim.seed + 1),
        "broken_seal": lambda: victim.model_copy(update={"outcome": "PASS", "seed": 123}),
        "replaced_duplicate": lambda: trials[0],  # count unchanged, one id twice, one missing
    }[mutation]()
    assert decide(m, [*trials[:-1], impostor]).verdict is Verdict.ERROR


def test_ceiling_conditions_are_reported_but_never_gate_on_rates() -> None:
    from arci.gate import decide

    m = manifest(conditions=(COND_TIMEOUT, COND_CEILING))
    trials = [
        *synthetic_trials(
            m, condition_id="fetch_timeout", baseline_successes=190, candidate_successes=190
        ),
        *synthetic_trials(
            m, condition_id="dead_backend", baseline_successes=100, candidate_successes=40
        ),
    ]
    d = decide(m, trials)
    assert d.k_conditions == 1 and d.per_arm_confidence == pytest.approx(0.975)
    gating = {c.condition_id: c.is_gating for c in d.conditions}
    assert gating == {"fetch_timeout": True, "dead_backend": False}
    assert d.verdict is Verdict.PASS


def test_ceiling_conditions_still_block_on_hard_violations_and_need_a_gating_peer() -> None:
    from arci.gate import decide

    m = manifest(conditions=(COND_TIMEOUT, COND_CEILING))
    trials = [
        *synthetic_trials(
            m, condition_id="fetch_timeout", baseline_successes=190, candidate_successes=190
        ),
        *synthetic_trials(
            m,
            condition_id="dead_backend",
            baseline_successes=100,
            candidate_successes=100,
            candidate_hard_violations=1,
        ),
    ]
    assert decide(m, trials).verdict is Verdict.BLOCK
    only_ceiling = manifest(conditions=(COND_CEILING,))
    lonely = synthetic_trials(
        only_ceiling,
        condition_id="dead_backend",
        baseline_successes=100,
        candidate_successes=100,
    )
    assert decide(only_ceiling, lonely).verdict is Verdict.ERROR
