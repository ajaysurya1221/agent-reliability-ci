"""Descriptive pass^k: the estimator, its availability rules and its report section."""

from __future__ import annotations

import math
from fractions import Fraction

import pytest

from arci.gate import decide
from arci.reliability import (
    UNAVAILABLE_INVALID,
    UNAVAILABLE_LOOKS,
    all_success_estimate,
    pass_k_report,
    validate_ks,
)
from arci.report import render_markdown
from arci.schema import Manifest, Verdict
from tests.acceptance.helpers import (
    COND_CEILING,
    COND_CLEAN,
    COND_TIMEOUT,
    manifest,
    synthetic_trials,
)

# ---------------------------------------------------------------------------------------------
# The estimator C(s, k) / C(n, k).
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("successes", "n", "k", "expected"),
    [
        (12, 12, 4, 1.0),
        (0, 12, 1, 0.0),
        (3, 5, 2, 3 / 10),  # C(3,2)/C(5,2): 3 of the 10 pairs are both PASS
        (8, 10, 3, 56 / 120),
        (1, 2, 2, 0.0),  # the only pair holds one failure
        (7, 9, 1, 7 / 9),  # k=1 is the plain success rate
        (190, 200, 2, (190 * 189) / (200 * 199)),
    ],
)
def test_all_success_estimate_hand_values(successes: int, n: int, k: int, expected: float) -> None:
    assert all_success_estimate(successes, n, k) == pytest.approx(expected, rel=1e-15)


def test_all_success_estimate_is_unavailable_below_k() -> None:
    assert all_success_estimate(1, 1, 2) is None
    assert all_success_estimate(3, 3, 4) is None
    assert all_success_estimate(3, 4, 4) == 0.0


@pytest.mark.parametrize("p", [Fraction(3, 10), Fraction(9, 10)])
@pytest.mark.parametrize("k", [1, 2, 4, 10])
def test_all_success_estimate_is_unbiased_for_p_to_the_k(p: Fraction, k: int) -> None:
    n = 10
    expectation = math.fsum(
        float(math.comb(n, s) * p**s * (1 - p) ** (n - s)) * (all_success_estimate(s, n, k) or 0.0)
        for s in range(n + 1)
    )
    assert expectation == pytest.approx(float(p**k), abs=1e-14)


@pytest.mark.parametrize(("successes", "n", "k"), [(1, 2, 0), (3, 2, 1), (-1, 2, 1), (0, -1, 1)])
def test_all_success_estimate_rejects_invalid_counts(successes: int, n: int, k: int) -> None:
    with pytest.raises(ValueError):
        all_success_estimate(successes, n, k)


@pytest.mark.parametrize("ks", [(), (0,), (2, 1), (1, 1), (True, 2)])
def test_invalid_k_lists_are_rejected(ks: tuple[int, ...]) -> None:
    with pytest.raises(ValueError):
        validate_ks(ks)


# ---------------------------------------------------------------------------------------------
# Availability: per arm and per declared condition, never pooled; unavailable for invalid
# experiments and for sequential looks.
# ---------------------------------------------------------------------------------------------


def test_each_arm_of_each_condition_is_its_own_population() -> None:
    experiment = manifest(n_per_arm=12, conditions=(COND_CLEAN, COND_TIMEOUT, COND_CEILING))
    trials = [
        *synthetic_trials(
            experiment, condition_id="clean", baseline_successes=12, candidate_successes=11
        ),
        *synthetic_trials(
            experiment, condition_id="fetch_timeout", baseline_successes=10, candidate_successes=6
        ),
        *synthetic_trials(
            experiment, condition_id="dead_backend", baseline_successes=0, candidate_successes=0
        ),
    ]
    decision = decide(experiment, trials)
    assert decision.verdict is not Verdict.ERROR
    report = pass_k_report(decision, (1, 2, 13))

    assert report.unavailable is None
    assert [(row.condition_id, row.arm, row.n, row.successes) for row in report.rows] == [
        ("clean", "baseline", 12, 12),
        ("clean", "candidate", 12, 11),
        ("fetch_timeout", "baseline", 12, 10),
        ("fetch_timeout", "candidate", 12, 6),
        ("dead_backend", "baseline", 12, 0),
        ("dead_backend", "candidate", 12, 0),
    ]
    assert [row.is_gating for row in report.rows] == [True, True, True, True, False, False]
    candidate_timeout = report.rows[3]
    assert candidate_timeout.estimates == (6 / 12, 15 / 66, None)  # C(6,2)/C(12,2); n < 13
    assert all(row.n == 12 for row in report.rows)  # nothing pooled across conditions


def test_an_invalid_experiment_has_no_estimate() -> None:
    experiment = manifest(n_per_arm=12)
    trials = synthetic_trials(
        experiment,
        condition_id="fetch_timeout",
        baseline_successes=12,
        candidate_successes=12,
        candidate_errors=1,
    )
    decision = decide(experiment, trials)
    assert decision.verdict is Verdict.ERROR
    report = pass_k_report(decision, (1, 2))
    assert report.unavailable == UNAVAILABLE_INVALID
    assert report.rows == ()


def test_sequential_looks_are_outcome_selected_and_unavailable() -> None:
    data = manifest(n_per_arm=48).model_dump(exclude={"record_sha256"})
    experiment = Manifest.create(**{**data, "looks": (12, 24, 48)})
    trials = synthetic_trials(
        experiment,
        condition_id="fetch_timeout",
        baseline_successes=12,
        candidate_successes=0,
        n=12,
    )
    decision = decide(experiment, trials)
    assert decision.verdict is Verdict.BLOCK  # a valid store that stopped at the first look
    report = pass_k_report(decision, (1, 2))
    assert report.unavailable == UNAVAILABLE_LOOKS
    assert report.rows == ()


def test_sequential_looks_stay_unavailable_at_the_final_look() -> None:
    data = manifest(n_per_arm=48).model_dump(exclude={"record_sha256"})
    experiment = Manifest.create(**{**data, "looks": (12, 24, 48)})
    trials = synthetic_trials(
        experiment, condition_id="fetch_timeout", baseline_successes=46, candidate_successes=40
    )
    decision = decide(experiment, trials)
    assert decision.verdict is not Verdict.ERROR
    assert decision.stopped_at_look == 3
    assert pass_k_report(decision, (1,)).unavailable == UNAVAILABLE_LOOKS


# ---------------------------------------------------------------------------------------------
# The report section: opt-in, before the verdict line, never changing the decision.
# ---------------------------------------------------------------------------------------------


def test_default_markdown_is_unchanged_without_pass_k() -> None:
    experiment = manifest(n_per_arm=12, prior_runs=("exp-earlier",))
    trials = synthetic_trials(
        experiment, condition_id="fetch_timeout", baseline_successes=12, candidate_successes=0
    )
    decision = decide(experiment, trials)
    assert render_markdown(experiment, decision, trials, pass_k=()) == render_markdown(
        experiment, decision, trials
    )
    assert "pass^k" not in render_markdown(experiment, decision, trials)


def test_pass_k_section_is_descriptive_and_keeps_the_verdict_last() -> None:
    experiment = manifest(n_per_arm=3, conditions=(COND_CLEAN, COND_TIMEOUT))
    trials = [
        *synthetic_trials(
            experiment, condition_id="clean", baseline_successes=3, candidate_successes=2
        ),
        *synthetic_trials(
            experiment, condition_id="fetch_timeout", baseline_successes=3, candidate_successes=0
        ),
    ]
    decision = decide(experiment, trials)
    before = decision.model_dump_json()
    default = render_markdown(experiment, decision, trials)
    with_pass_k = render_markdown(experiment, decision, trials, pass_k=(1, 2, 4))

    assert decision.model_dump_json() == before
    lines = with_pass_k.splitlines()
    assert lines[-1] == default.splitlines()[-1]
    assert lines[-1].startswith("VERDICT: ")
    start = lines.index("## Descriptive pass^k (not part of the verdict)")
    assert start < lines.index("## Candidate failure clusters")
    assert "| Condition | Arm | Role | n | Successes | pass^1 | pass^2 | pass^4 |" in lines
    assert (
        "| `clean` | candidate | Gating | 3 | 2 | 0.6667 | 0.3333 | unavailable (n < k) |" in lines
    )
    assert (
        "| `fetch_timeout` | candidate | Gating | 3 | 0 | 0.0000 | 0.0000 | unavailable (n < k) |"
        in lines
    )
    assert any("IID sample" in line for line in lines[start:])
    # Removing the section gives back the default report byte for byte.
    end = lines.index("## Candidate failure clusters")
    assert "\n".join(lines[:start] + lines[end:]) + "\n" == default


def test_pass_k_section_states_why_it_is_unavailable() -> None:
    experiment = manifest(n_per_arm=4)
    trials = synthetic_trials(
        experiment,
        condition_id="fetch_timeout",
        baseline_successes=4,
        candidate_successes=4,
        candidate_errors=1,
    )
    decision = decide(experiment, trials)
    text = render_markdown(experiment, decision, trials, pass_k=(1,))
    assert f"Unavailable: {UNAVAILABLE_INVALID}." in text.splitlines()
    assert "| Condition | Arm |" not in text
