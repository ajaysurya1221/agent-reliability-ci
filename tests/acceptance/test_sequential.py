"""Group-sequential looks with equal Bonferroni spending. FROZEN.

Golden bounds from scipy at the per-look tail alpha/(4KL) = 0.05/12.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from arci.schema import Manifest, TrialEnvelope, Verdict
from tests.acceptance.helpers import (
    COND_CLEAN,
    COND_TIMEOUT,
    cumulative_fail_sets,
    manifest,
    synthetic_trials,
    synthetic_trials_by_pair,
)

pytestmark = pytest.mark.acceptance
LOOKS = (50, 100, 200)


def _seq(**kw: object) -> Manifest:
    data = manifest(**kw).model_dump(exclude={"record_sha256"})  # pyright: ignore[reportArgumentType]
    return Manifest.create(**{**data, "looks": LOOKS})


def _counts(m: Manifest, *, baseline: int, candidate: int, n: int) -> list[TrialEnvelope]:
    """Trials for pairs 0..n-1 of the ONE condition, with the given cumulative successes."""
    return synthetic_trials(
        m,
        condition_id="fetch_timeout",
        baseline_successes=baseline,
        candidate_successes=candidate,
        n=n,
    )


def _cumulative(
    m: Manifest, *, baseline: tuple[int, ...], candidate: tuple[int, ...], n: int
) -> list[TrialEnvelope]:
    """Trials for pairs 0..n-1 whose cumulative successes at each of LOOKS are as given."""
    return synthetic_trials_by_pair(
        m,
        condition_id="fetch_timeout",
        baseline_fail=cumulative_fail_sets(LOOKS, baseline),
        candidate_fail=cumulative_fail_sets(LOOKS, candidate),
        n=n,
    )


def test_looks_must_be_a_plan() -> None:
    data = manifest().model_dump(exclude={"record_sha256"})
    for bad in ((50, 50, 200), (100, 50, 200), (50, 100), (0, 200), (50, 100, 300)):
        with pytest.raises(ValidationError):
            Manifest.create(**{**data, "looks": bad})
    assert Manifest.create(**{**data, "looks": (200,)}).validate_seal()


def test_no_looks_is_the_fixed_design_unchanged() -> None:
    from arci.gate import decide

    m = manifest()
    d = decide(
        m,
        synthetic_trials(
            m, condition_id="fetch_timeout", baseline_successes=190, candidate_successes=130
        ),
    )
    assert d.verdict is Verdict.BLOCK and d.looks == (200,) and d.stopped_at_look == 1
    assert len(d.history) == 1 and d.history[0].verdict is Verdict.BLOCK
    assert d.per_arm_confidence == pytest.approx(0.975)


def test_a_clear_regression_stops_at_the_first_look() -> None:
    from arci.gate import decide

    m = _seq()
    d = decide(m, _counts(m, baseline=48, candidate=20, n=50))
    assert d.verdict is Verdict.BLOCK and d.stopped_at_look == 1 and d.exit_code == 1
    assert d.per_arm_confidence == pytest.approx(1 - 0.05 / 6)
    c = d.history[0].conditions[0]
    assert (c.delta_low, c.delta_high) == pytest.approx(
        (-0.772889857701, -0.228611415627), rel=0, abs=1e-8
    )
    assert d.validate_seal()


def test_continuing_past_a_decisive_look_is_an_error() -> None:
    """The trap: padding an early BLOCK with more trials must never manufacture a later PASS."""
    from arci.gate import decide

    m = _seq()
    padded = _counts(m, baseline=48, candidate=20, n=50) + [
        t
        for t in _counts(m, baseline=190, candidate=190, n=200)
        if int(t.pair_id.rsplit(":", 1)[1]) >= 50
    ]
    assert len(padded) == 400
    assert decide(m, padded).verdict is Verdict.ERROR


def test_inconclusive_looks_continue_and_the_final_look_decides() -> None:
    from arci.gate import decide

    m = _seq()
    # Look 1: 48/50 vs 47/50 INCONCLUSIVE; look 2: 96/100 vs 95/100 INCONCLUSIVE; look 3 PASS.
    trials = _cumulative(m, baseline=(48, 96, 192), candidate=(47, 95, 191), n=200)
    d = decide(m, trials)
    assert [h.verdict for h in d.history] == [
        Verdict.INCONCLUSIVE,
        Verdict.INCONCLUSIVE,
        Verdict.PASS,
    ]
    assert d.verdict is Verdict.PASS and d.stopped_at_look == 3
    assert d.history[2].conditions[0].delta_low == pytest.approx(-0.086099984316, rel=0, abs=1e-8)


def test_stopping_where_no_look_was_decisive_is_an_error() -> None:
    from arci.gate import decide

    m = _seq()
    assert decide(m, _counts(m, baseline=48, candidate=44, n=50)).verdict is Verdict.ERROR
    half_pair = _counts(m, baseline=48, candidate=20, n=50)[:-1]  # one arm of pair 49 missing
    assert decide(m, half_pair).verdict is Verdict.ERROR


def test_the_final_look_without_a_decision_is_inconclusive() -> None:
    from arci.gate import decide

    m = _seq()
    # 48/50 vs 44/50, 95/100 vs 90/100, 190/200 vs 182/200: INCONCLUSIVE at every look.
    trials = _cumulative(m, baseline=(48, 95, 190), candidate=(44, 90, 182), n=200)
    d = decide(m, trials)
    assert d.verdict is Verdict.INCONCLUSIVE and d.stopped_at_look == 3 and len(d.history) == 3
    assert d.history[2].conditions[0].delta_high == pytest.approx(0.060598722790, rel=0, abs=1e-8)


def test_the_plan_is_bound_into_trial_identity() -> None:
    from arci.gate import decide

    m = _seq()
    trials = _counts(m, baseline=48, candidate=20, n=50)
    replanned = Manifest.create(**{**m.model_dump(exclude={"record_sha256"}), "looks": (50, 200)})
    assert decide(replanned, trials).verdict is Verdict.ERROR


def test_history_is_sealed() -> None:
    from arci.gate import decide

    m = _seq()
    d = decide(m, _counts(m, baseline=48, candidate=20, n=50))
    forged_look = d.history[0].model_copy(update={"verdict": Verdict.INCONCLUSIVE})
    assert not d.model_copy(update={"history": (forged_look,)}).validate_seal()


def test_two_conditions_share_the_per_look_alpha() -> None:
    from arci.gate import decide

    m = _seq(conditions=(COND_CLEAN, COND_TIMEOUT))
    trials = [
        *synthetic_trials(
            m, condition_id="clean", baseline_successes=48, candidate_successes=48, n=50
        ),
        *synthetic_trials(
            m, condition_id="fetch_timeout", baseline_successes=48, candidate_successes=20, n=50
        ),
    ]
    d = decide(m, trials)
    assert d.k_conditions == 2 and d.per_arm_confidence == pytest.approx(1 - 0.05 / 12)
    assert d.verdict is Verdict.BLOCK and d.stopped_at_look == 1


def test_run_experiment_stops_early_and_the_store_gates(tmp_path: Path) -> None:
    from arci.gate import decide
    from arci.runner import run_experiment
    from arci.storage import load_run

    data = manifest(n_per_arm=48).model_dump(exclude={"record_sha256"})
    m = Manifest.create(**{**data, "looks": (12, 24, 48)})
    trials = run_experiment(m, tmp_path, max_workers=6)
    assert len(trials) == 24  # 12 pairs: 12/12 vs 0/12 is BLOCK at look 1
    d = decide(m, trials)
    assert d.verdict is Verdict.BLOCK and d.stopped_at_look == 1
    _, stored = load_run(tmp_path / m.experiment_id)
    assert len(stored) == 24 and decide(m, stored) == d


def test_sequential_enumeration_matches_the_review_and_the_fixed_design() -> None:
    from bench.selfcheck import operating_characteristics, sequential_characteristics

    one = sequential_characteristics(0.95, 0.65, (200,), alpha=0.05, delta=0.10)
    fixed = operating_characteristics(0.95, 0.65, 200, alpha=0.05, delta=0.10)
    for key in ("PASS", "BLOCK", "INCONCLUSIVE"):
        assert one[key] == pytest.approx(fixed[key], abs=1e-9)
    assert one["expected_trials"] == pytest.approx(400.0)

    seq = sequential_characteristics(0.95, 0.65, LOOKS, alpha=0.05, delta=0.10)
    assert seq["BLOCK"] == pytest.approx(0.943, abs=0.01)
    assert seq["expected_trials"] == pytest.approx(302, abs=6)
    same = sequential_characteristics(0.95, 0.95, LOOKS, alpha=0.05, delta=0.10)
    assert same["PASS"] == pytest.approx(0.735, abs=0.01) and same["BLOCK"] <= 0.05
    boundary = sequential_characteristics(0.95, 0.85, LOOKS, alpha=0.05, delta=0.10)
    assert boundary["PASS"] <= 0.05
    newcombe = sequential_characteristics(
        0.95, 0.65, LOOKS, alpha=0.05, delta=0.10, method="newcombe"
    )
    assert newcombe["expected_trials"] == pytest.approx(159, abs=6)
