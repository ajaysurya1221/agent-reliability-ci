"""The optional tighter interval for the margin. FROZEN.

Golden values were computed independently with scipy's inverse normal CDF.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from arci.schema import Manifest, Verdict
from tests.acceptance.helpers import COND_CLEAN, COND_TIMEOUT, manifest, synthetic_trials

pytestmark = pytest.mark.acceptance

NEWCOMBE_GOLDEN = [  # (x_a, n, x_b, n, confidence, low, high)
    (376, 400, 308, 400, 0.95, -0.217786635877, -0.122511742965),
    (190, 200, 130, 200, 0.95, -0.372009490406, -0.225843446057),
    (190, 200, 190, 200, 0.95, -0.045584805913, 0.045584805913),
    (19, 20, 13, 20, 0.95, -0.521004525760, -0.048721227669),
    (170, 200, 170, 200, 0.95, -0.070566138665, 0.070566138665),
    (0, 20, 0, 20, 0.95, -0.161125158053, 0.161125158053),
    (20, 20, 0, 20, 0.95, -1.0, -0.772134616242),
    (376, 400, 308, 400, 0.975, -0.224756441132, -0.115609031895),
]


def _with_method(method: str, **kw: object) -> Manifest:
    data = manifest(**kw).model_dump(exclude={"record_sha256"})  # pyright: ignore[reportArgumentType]
    return Manifest.create(**{**data, "interval_method": method})


@pytest.mark.parametrize(("xa", "na", "xb", "nb", "conf", "low", "high"), NEWCOMBE_GOLDEN)
def test_newcombe_matches_independent_reference(
    xa: int, na: int, xb: int, nb: int, conf: float, low: float, high: float
) -> None:
    from arci.stats import newcombe

    got = newcombe(xa, na, xb, nb, conf)
    assert got[0] == pytest.approx(low, rel=0, abs=1e-9)
    assert got[1] == pytest.approx(high, rel=0, abs=1e-9)


def test_the_default_method_is_unchanged() -> None:
    from arci.gate import decide

    assert manifest().interval_method == "clopper_pearson"
    m400 = manifest(n_per_arm=400)
    d = decide(
        m400,
        synthetic_trials(
            m400, condition_id="fetch_timeout", baseline_successes=376, candidate_successes=308
        ),
    )
    assert d.interval_method == "clopper_pearson"
    assert d.conditions[0].delta_high == pytest.approx(-0.0921, abs=1e-3)
    assert d.verdict is Verdict.INCONCLUSIVE  # the sealed result of the real run stays what it was


def test_newcombe_decides_the_real_regression() -> None:
    from arci.gate import decide

    m = _with_method("newcombe", n_per_arm=400)
    d = decide(
        m,
        synthetic_trials(
            m, condition_id="fetch_timeout", baseline_successes=376, candidate_successes=308
        ),
    )
    assert d.interval_method == "newcombe"
    assert d.per_arm_confidence == pytest.approx(0.95)
    assert d.conditions[0].delta_low == pytest.approx(-0.217786635877, rel=0, abs=1e-8)
    assert d.conditions[0].delta_high == pytest.approx(-0.122511742965, rel=0, abs=1e-8)
    assert d.verdict is Verdict.BLOCK and d.validate_seal()


def test_newcombe_with_k_conditions_uses_alpha_over_k() -> None:
    from arci.gate import decide

    m = _with_method("newcombe", n_per_arm=400, conditions=(COND_CLEAN, COND_TIMEOUT))
    trials = [
        *synthetic_trials(m, condition_id="clean", baseline_successes=376, candidate_successes=376),
        *synthetic_trials(
            m, condition_id="fetch_timeout", baseline_successes=376, candidate_successes=308
        ),
    ]
    d = decide(m, trials)
    assert d.k_conditions == 2 and d.per_arm_confidence == pytest.approx(0.975)
    assert d.conditions[1].delta_high == pytest.approx(-0.115609031895, rel=0, abs=1e-8)
    assert d.verdict is Verdict.BLOCK


def test_the_method_is_sealed_and_cannot_be_chosen_after_the_fact() -> None:
    from arci.gate import decide

    m = manifest(n_per_arm=400)
    trials = synthetic_trials(
        m, condition_id="fetch_timeout", baseline_successes=376, candidate_successes=308
    )
    assert decide(m, trials).verdict is Verdict.INCONCLUSIVE
    switched = m.model_copy(update={"interval_method": "newcombe"})  # breaks the manifest seal
    assert decide(switched, trials).verdict is Verdict.ERROR
    # A VALIDLY resealed manifest with a different rule must not match the old trials either.
    data = m.model_dump(exclude={"record_sha256"})
    for change in ({"interval_method": "newcombe"}, {"delta": 0.2}, {"alpha": 0.2}):
        resealed = Manifest.create(**{**data, **change})
        assert resealed.validate_seal()
        assert decide(resealed, trials).verdict is Verdict.ERROR, change
    with pytest.raises(ValidationError):
        _with_method("barnard")


def test_newcombe_calibration_by_exact_enumeration() -> None:
    """Both directional errors stay <= alpha around the boundary. A subset of the bench sweep."""
    from bench.selfcheck import boundary_calibration

    for n in (50, 200):
        worst = boundary_calibration("newcombe", n, alpha=0.05, delta=0.10, step=0.05)
        assert worst["false_pass"] <= 0.05, worst
        assert worst["false_block"] <= 0.05, worst
        assert worst["false_pass"] > 0.0 and worst["false_block"] > 0.0  # the sweep is not vacuous
    cp = boundary_calibration("clopper_pearson", 200, alpha=0.05, delta=0.10, step=0.05)
    assert cp["false_pass"] <= 0.05 and cp["false_block"] <= 0.05
