"""Statistical contract. FROZEN. Golden values from scipy.stats.binomtest(...).proportion_ci."""

from __future__ import annotations

import pytest

from arci.schema import EXIT_CODES, Verdict
from tests.acceptance.helpers import COND_CLEAN, COND_TIMEOUT, manifest, synthetic_trials

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
    assert got_low == pytest.approx(low, abs=1e-9)
    assert got_high == pytest.approx(high, abs=1e-9)


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
