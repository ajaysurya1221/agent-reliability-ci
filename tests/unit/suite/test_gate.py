"""Contract section 5, synthetic scheduled stores only."""

from __future__ import annotations

from fractions import Fraction
from time import perf_counter_ns
from typing import Any

import pytest

import arci.suite_gate as gate
from arci.hashing import hash_record
from arci.schema import ContractResult, Outcome, TrialEnvelope, Verdict, Violation
from arci.suite_schema import SuiteDecision, SuiteManifest
from arci.suite_stats import rule_of, scored_wealth, wealth_text
from tests.unit.suite.helpers import gate_manifest, store


def reseal(trial: TrialEnvelope, **changes: Any) -> TrialEnvelope:
    fields = trial.model_dump(mode="python", exclude={"record_sha256"})
    fields.update(changes)
    return TrialEnvelope.create(**fields)


def hard(trial: TrialEnvelope, severity: str = "hard") -> TrialEnvelope:
    return reseal(
        trial,
        contract=ContractResult(
            success=False,
            violations=(
                Violation.model_validate(
                    {"invariant": "rule", "severity": severity, "detail": "test"}
                ),
            ),
        ),
    )


def assert_error(decision: SuiteDecision, *reasons: str, history: bool = False) -> None:
    assert decision.validate_seal()
    assert decision.verdict is Verdict.ERROR
    assert decision.exit_code == 3
    assert decision.stopped_at_round == 0
    assert decision.reasons == reasons
    assert bool(decision.history) is history
    assert bool(decision.cells) is history


@pytest.mark.parametrize(
    ("differences", "verdict", "reason", "round"),
    [
        ([1] * 20, Verdict.PASS, "non-inferiority established", 1),
        ([-1] * 20, Verdict.BLOCK, "regression established", 1),
        ([0] * 80, Verdict.PASS, "non-inferiority established", 4),
        ([None] + [0] * 79, Verdict.INCONCLUSIVE, "no test crossed", 4),
    ],
)
def test_terminal_rows(
    differences: list[int | None], verdict: Verdict, reason: str, round: int
) -> None:
    m = gate_manifest()
    result = gate.decide_suite(m, store(m, differences))
    assert result.validate_seal()
    assert result.verdict is verdict
    assert result.reasons == (reason,)
    assert result.stopped_at_round == round
    assert len(result.history) == round
    assert len(result.cells) == 20


@pytest.mark.parametrize(
    ("differences", "reason", "length"),
    [
        ([1] * 40, "trials stored after the stopping round", 1),
        ([None, None] + [0] * 38, "trials stored after the stopping round", 1),
        ([0] * 20, "stopped without a decision", 1),
        ([None, None] + [0] * 18, "errored pairs exceed max_errored_pairs", 1),
    ],
)
def test_stopping_error_rows(differences: list[int | None], reason: str, length: int) -> None:
    m = gate_manifest()
    result = gate.decide_suite(m, store(m, differences))
    assert_error(result, reason, history=True)
    assert len(result.history) == length
    assert sum(cell.pairs for cell in result.cells) == len(differences)


def test_priority_and_crossing_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    m = gate_manifest()
    trials = store(m, [1] * 20)
    trials[1] = hard(trials[1])
    result = gate.decide_suite(m, trials)
    assert result.reasons == ("candidate hard violation",)
    assert result.history[0].pass_crossed
    assert result.history[0].candidate_hard_violations == 1

    def both(*args: object) -> tuple[Fraction, Fraction]:
        return Fraction(40), Fraction(40)

    monkeypatch.setattr(gate, "scored_wealth", both)
    assert gate.decide_suite(m, trials).reasons == ("candidate hard violation",)
    trials[1] = reseal(trials[1], contract=None)
    assert_error(gate.decide_suite(m, trials), "both tests crossed", history=True)
    trials[1] = hard(reseal(trials[1], outcome=Outcome.ERROR))
    trials[3] = reseal(trials[3], outcome=Outcome.ERROR)
    result = gate.decide_suite(m, trials)
    assert_error(result, "errored pairs exceed max_errored_pairs", history=True)
    assert result.history[0].pass_crossed and result.history[0].block_crossed


def test_errors_scored_against_both_and_successes_stay_descriptive() -> None:
    m = gate_manifest()
    trials = store(m, [None] + [0] * 79)
    trials[0] = reseal(trials[0], outcome=Outcome.PASS)
    result = gate.decide_suite(m, trials)
    wp, wb = scored_wealth(0, 79, 0, 1, rule_of(m))
    assert result.history[-1].pass_wealth == wealth_text(wp)
    assert result.history[-1].block_wealth == wealth_text(wb)
    assert result.cells[0].baseline_successes == 4
    assert result.cells[0].candidate_successes == 3
    assert result.cells[0].counts.errored == 1
    trials[0] = reseal(trials[0], outcome=Outcome.ERROR)
    assert gate.decide_suite(m, trials).history[-1].counts.errored == 1
    trials[1] = reseal(trials[1], outcome=Outcome.PASS)
    assert gate.decide_suite(m, trials).cells[0].candidate_successes == 4


def test_only_candidate_hard_entries_count() -> None:
    m = gate_manifest()
    trials = store(m, [0] * 80)
    trials[0] = hard(trials[0])
    trials[1] = hard(trials[1], "soft")
    assert gate.decide_suite(m, trials).verdict is Verdict.PASS
    trials[1] = reseal(
        trials[1],
        contract=ContractResult(
            success=False,
            violations=(
                Violation(invariant="a", severity="hard", detail=""),
                Violation(invariant="b", severity="hard", detail=""),
            ),
        ),
    )
    result = gate.decide_suite(m, trials[:40])
    assert result.history[0].candidate_hard_violations == 2


def test_partial_round_ignored_by_walk_rejected_by_gate() -> None:
    m = gate_manifest()
    trials = store(m, [0] * 40)
    assert gate.evaluate_rounds(m, ()) == ()
    assert gate.evaluate_rounds(m, trials[:39]) == ()
    assert len(gate.evaluate_rounds(m, trials[:79])) == 1
    assert_error(gate.decide_suite(m, trials[:79]), "trial set is not a whole number of rounds")
    assert_error(gate.decide_suite(m, ()), "trial set is not a whole number of rounds")
    assert_error(gate.decide_suite(m, trials[40:]), "trial set is not a whole number of rounds")


@pytest.mark.parametrize(
    "field",
    [
        "experiment_id",
        "trial_id",
        "pair_id",
        "arm",
        "task_id",
        "condition_id",
        "seed",
        "spec_sha256",
    ],
)
def test_each_schedule_identity_field(field: str) -> None:
    m = gate_manifest()
    trials = store(m, [1] * 20)
    value = {"seed": 1, "arm": "candidate", "spec_sha256": "0" * 64}.get(field, "wrong")
    trials[0] = reseal(trials[0], **{field: value})
    assert_error(gate.decide_suite(m, trials), "trial schedule mismatch")


def test_duplicate_and_replayed_specs_rejected() -> None:
    m = gate_manifest()
    trials = store(m, [1] * 20)
    assert_error(gate.decide_suite(m, trials + trials[:1]), "trial schedule mismatch")
    from arci.schedule import spec_sha256
    from arci.schema import ToolMode
    from arci.suite_schedule import build_suite_round

    replay_spec = build_suite_round(m, 1)[0].model_copy(update={"tool_mode": ToolMode.REPLAY})
    trials[0] = reseal(trials[0], spec_sha256=spec_sha256(replay_spec))
    assert_error(gate.decide_suite(m, trials), "trial schedule mismatch")


def test_all_checks_collected_in_order_and_skip_eight() -> None:
    m = gate_manifest(max_rounds=3).model_copy(update={"experiment_id": "wrong"})
    trials = store(m, [0] * 20)
    trials[0] = trials[0].model_copy(update={"seed": -1})
    assert_error(
        gate.decide_suite(m, trials),
        "manifest seal invalid",
        "suite rule digest mismatch",
        "suite plan invalid",
        "trial schedule mismatch",
        "trial seal invalid",
    )


def test_bad_trial_values_skip_six_to_eight_but_not_manifest_checks() -> None:
    m = gate_manifest().model_copy(update={"record_sha256": "bad"})
    trials = store(m, [1] * 20)
    trials[0] = trials[0].model_copy(update={"outcome": "unknown"})
    assert_error(gate.decide_suite(m, trials), "manifest seal invalid", "trial values invalid")


def test_bad_seal_does_not_skip_whole_round_check() -> None:
    m = gate_manifest()
    trials = store(m, [1] * 20)[:-1]
    trials[0] = trials[0].model_copy(update={"record_sha256": "bad"})
    assert_error(
        gate.decide_suite(m, trials),
        "trial seal invalid",
        "trial set is not a whole number of rounds",
    )


@pytest.mark.parametrize("value", [None, "bad", float("inf"), 10**400])
def test_invalid_manifest_fixed_template(value: object) -> None:
    m = gate_manifest().model_copy(update={"alpha": value})
    result = gate.decide_suite(m, ())
    assert_error(result, "manifest values invalid")
    for name in (
        "experiment_id",
        "manifest_sha256",
        "alpha",
        "delta",
        "threshold",
        "scenario_seeds",
    ):
        assert getattr(result, name) == ""
    assert result.stakes == result.prior_runs == ()
    assert result.n_cells == result.max_rounds == result.max_errored_pairs == 0
    assert result.trials_sha256 == hash_record({"trials": []})


def test_model_construct_and_normalized_enums() -> None:
    assert_error(gate.decide_suite(SuiteManifest.model_construct(), ()), "manifest values invalid")
    m = gate_manifest()
    assert_error(gate.decide_suite(m, (TrialEnvelope.model_construct(),)), "trial values invalid")
    trials = store(m, [None, None] + [0] * 18)
    trials[1] = trials[1].model_copy(update={"outcome": "ERROR"})
    assert trials[1].validate_seal()
    assert_error(
        gate.decide_suite(m, trials), "errored pairs exceed max_errored_pairs", history=True
    )
    trials = store(m, [1] * 20)
    trials = [t.model_copy(update={"outcome": t.outcome.value}) for t in trials]
    assert gate.decide_suite(m, trials).verdict is Verdict.PASS


@pytest.mark.parametrize(
    "field", ["created_at", "experiment_id", "record_sha256", "fixtures_sha256"]
)
def test_manifest_surrogates(field: str) -> None:
    m = gate_manifest().model_copy(update={field: "\ud800"})
    assert_error(gate.decide_suite(m, ()), "manifest values invalid")


@pytest.mark.parametrize("field", ["failure_detail", "record_sha256", "final_state"])
def test_trial_surrogates(field: str) -> None:
    m = gate_manifest()
    trials = store(m, [1] * 20)
    trials[0] = trials[0].model_copy(
        update={field: {"bad": "\ud800"} if field == "final_state" else "\ud800"}
    )
    result = gate.decide_suite(m, trials)
    assert_error(result, "trial values invalid")
    assert (result.trials_sha256 == "") is (field == "record_sha256")


def test_nonstring_seal_digest_falls_back() -> None:
    m = gate_manifest()
    trials = store(m, [1] * 20)
    trials[0] = trials[0].model_copy(update={"record_sha256": 3})
    result = gate.decide_suite(m, trials)
    assert_error(result, "trial values invalid")
    assert result.trials_sha256 == ""


def test_mirrored_fields_hashes_determinism_order_and_replay() -> None:
    m = gate_manifest(prior_runs=("previous",))
    trials = store(m, [0] * 80)
    result = gate.decide_suite(m, trials)
    for name in (
        "experiment_id",
        "alpha",
        "delta",
        "stakes",
        "scenario_seeds",
        "max_rounds",
        "max_errored_pairs",
        "prior_runs",
        "n_cells",
    ):
        assert getattr(result, name) == getattr(m, name)
    assert result.manifest_sha256 == m.record_sha256
    assert result.threshold == "40/1"
    assert result.trials_sha256 == hash_record({"trials": sorted(t.record_sha256 for t in trials)})
    for r in result.history:
        assert r.trials_sha256 == hash_record(
            {"trials": sorted(t.record_sha256 for t in trials[: r.round * 40])}
        )
    assert [(c.task_id, c.condition_id) for c in result.cells] == sorted(
        (c.task_id, c.condition_id) for c in result.cells
    )
    assert result == gate.decide_suite(m, list(reversed(trials))) == gate.decide_suite(m, trials)
    assert gate.replay_suite_decision(result, m, trials)
    assert not gate.replay_suite_decision(
        result.model_copy(update={"record_sha256": "bad"}), m, trials
    )
    fields = result.model_dump(exclude={"record_sha256"})
    fields["reasons"] = ("changed",)
    assert not gate.replay_suite_decision(SuiteDecision.create(**fields), m, trials)
    assert not gate.replay_suite_decision(SuiteDecision.model_construct(), m, trials)


def raises(*args: object, **kwargs: object) -> Any:
    raise RuntimeError("injected")


@pytest.mark.parametrize(
    ("target", "reason"),
    [
        ("suite_experiment_id", "suite rule digest mismatch"),
        ("check_suite_plan", "suite plan invalid"),
        ("build_suite_schedule", "trial schedule mismatch"),
    ],
)
def test_exceptions_inside_checks(
    monkeypatch: pytest.MonkeyPatch, target: str, reason: str
) -> None:
    m = gate_manifest()
    trials = store(m, [1] * 20)
    monkeypatch.setattr(gate, target, raises)
    assert_error(gate.decide_suite(m, trials), reason)


@pytest.mark.parametrize("target", ["evaluate_rounds", "_cells"])
def test_computation_failure_preserves_manifest_fields(
    monkeypatch: pytest.MonkeyPatch, target: str
) -> None:
    m = gate_manifest()
    trials = store(m, [1] * 20)
    monkeypatch.setattr(gate, target, raises)
    result = gate.decide_suite(m, trials)
    assert_error(result, "gate computation failed")
    assert result.experiment_id == m.experiment_id


def test_last_resort_on_unsealable_decision(monkeypatch: pytest.MonkeyPatch) -> None:
    m = gate_manifest()
    trials = store(m, [1] * 20)
    original = SuiteDecision.create

    def broken(**fields: Any) -> SuiteDecision:
        if fields["experiment_id"]:
            fields["experiment_id"] = "\ud800"
        return original(**fields)

    monkeypatch.setattr(SuiteDecision, "create", broken)
    result = gate.decide_suite(m, trials)
    assert_error(result, "gate computation failed")
    assert result.experiment_id == result.trials_sha256 == ""


def test_twenty_cells_twenty_rounds_uses_cumulative_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    m = gate_manifest(max_rounds=20)
    trials = store(m, ([-1, 0, 0, 0, 0, 0, 0, 0, 0, 0] * 40))
    calls: list[tuple[int, int, int, int]] = []
    original = gate.scored_wealth

    def measured(
        minus: int, zero: int, plus: int, errored: int, rule: Any
    ) -> tuple[Fraction, Fraction]:
        calls.append((minus, zero, plus, errored))
        return original(minus, zero, plus, errored, rule)

    monkeypatch.setattr(gate, "scored_wealth", measured)
    started = perf_counter_ns()
    result = gate.decide_suite(m, trials)
    elapsed = perf_counter_ns() - started
    assert result.verdict is Verdict.INCONCLUSIVE
    assert calls == [(2 * r, 18 * r, 0, 0) for r in range(1, 21)]
    assert elapsed < 800_000_000
