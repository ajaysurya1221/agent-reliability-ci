"""Shared round kernel parity, priority, and lazy trial-adapter boundaries."""

from collections import Counter
from collections.abc import Iterator
from dataclasses import fields, replace
from random import Random

import pytest

from arci.demo import suite
from arci.hashing import hash_record
from arci.perturb import build
from arci.schema import ContractResult, Outcome, TrialEnvelope, Verdict, Violation
from arci.suite_gate import RoundIncrement, evaluate_rounds, walk_rounds
from arci.suite_schedule import build_suite_schedule, pair_round
from arci.suite_schema import SuiteCounts, SuiteManifest
from arci.suite_stats import (
    RunningWealth,
    SuitePlanError,
    check_rule_plan,
    check_suite_plan,
    rule_of,
    scored_wealth,
    wealth_text,
)
from arci.toolbox import ToolBox
from tests.unit.suite.helpers import envelope, gate_manifest, manifest_fields, store


def demo_trials(manifest: SuiteManifest, candidate: str) -> list[TrialEnvelope]:
    """Exercise the packaged agents and tool faults in process for kernel inputs."""
    agents = {
        "control": suite.control,
        "regression": suite.regression,
        "uncertain": suite.uncertain,
    }
    trials: list[TrialEnvelope] = []
    for spec in build_suite_schedule(manifest):
        world = suite.make_world(spec.task, spec.seed)
        tools = ToolBox(
            world.tools,
            spec.budgets,
            lambda _kind, _payload: None,
            perturbations=tuple(build(fault) for fault in spec.condition.faults),
            seed=spec.seed,
        )
        agent = suite.control if spec.arm == "baseline" else agents[candidate]
        agent(spec.task, tools, Random(spec.seed))
        outcome = Outcome.PASS if suite.oracle(spec.task, world.snapshot()) else Outcome.FAIL
        trials.append(envelope(spec, outcome))
    return trials


@pytest.mark.parametrize("candidate", ["control", "regression", "uncertain"])
def test_packaged_demo_history_matches_field_for_field(candidate: str) -> None:
    manifest = suite.build_manifest(candidate)
    trials = demo_trials(manifest, candidate)
    by_id = {trial.trial_id: trial for trial in trials}
    increments: list[RoundIncrement] = []
    for r in range(1, manifest.max_rounds + 1):
        differences = Counter(
            int(by_id[f"{trial.pair_id}:candidate"].outcome is Outcome.PASS)
            - int(trial.outcome is Outcome.PASS)
            for trial in trials
            if pair_round(trial.pair_id) == r and trial.arm == "baseline"
        )
        increments.append(RoundIncrement(differences[-1], differences[0], differences[1], 0, 0))
    looks = walk_rounds(rule_of(manifest), increments)
    history = evaluate_rounds(manifest, trials)
    assert len(looks) == len(history) > 0
    for look, decision in zip(looks, history, strict=True):
        for field in fields(look):
            assert getattr(look, field.name) == getattr(decision, field.name)
        assert decision.trials_sha256 == hash_record(
            {
                "trials": sorted(
                    t.record_sha256 for t in trials if pair_round(t.pair_id) == look.round
                )
            }
        )


@pytest.mark.parametrize(
    "increment,verdict,reason,pass_crossed,block_crossed",
    [
        (
            RoundIncrement(0, 0, 18, 2, 1),
            Verdict.ERROR,
            "errored pairs exceed max_errored_pairs",
            True,
            False,
        ),
        (RoundIncrement(0, 0, 20, 0, 1), Verdict.BLOCK, "candidate hard violation", True, False),
        (RoundIncrement(0, 0, 20, 0, 0), Verdict.PASS, "non-inferiority established", True, False),
        (RoundIncrement(20, 0, 0, 0, 0), Verdict.BLOCK, "regression established", False, True),
        (RoundIncrement(0, 20, 0, 0, 0), Verdict.INCONCLUSIVE, "no test crossed", False, False),
    ],
)
def test_verdict_ladder(
    increment: RoundIncrement,
    verdict: Verdict,
    reason: str,
    pass_crossed: bool,
    block_crossed: bool,
) -> None:
    (look,) = walk_rounds(rule_of(gate_manifest()), [increment])
    assert look.verdict is verdict
    assert look.reasons == (reason,)
    assert (look.pass_crossed, look.block_crossed) == (pass_crossed, block_crossed)
    assert look.candidate_hard_violations == increment.candidate_hard_violations


@pytest.mark.parametrize(
    "errored,hard,verdict,reason",
    [
        (2, 1, Verdict.ERROR, "errored pairs exceed max_errored_pairs"),
        (1, 1, Verdict.BLOCK, "candidate hard violation"),
        (1, 0, Verdict.ERROR, "both tests crossed"),
    ],
)
def test_both_flags_survive_overrides(
    monkeypatch: pytest.MonkeyPatch, errored: int, hard: int, verdict: Verdict, reason: str
) -> None:
    def crossed(_self: RunningWealth) -> bool:
        return True

    monkeypatch.setattr(RunningWealth, "crossed", crossed)
    (look,) = walk_rounds(
        rule_of(gate_manifest()), [RoundIncrement(0, 20 - errored, 0, errored, hard)]
    )
    assert look.pass_crossed and look.block_crossed
    assert look.verdict is verdict
    assert look.reasons == (reason,)


def test_cumulative_counts_wealth_and_error_tolerance() -> None:
    rule = rule_of(gate_manifest())
    looks = walk_rounds(rule, [RoundIncrement(2, 15, 2, 1, 0), RoundIncrement(1, 17, 1, 1, 2)])
    first, last = looks
    assert first.verdict is Verdict.INCONCLUSIVE  # Exactly at tolerance is allowed.
    assert last.round == 2 and last.pairs == 40
    assert last.counts == SuiteCounts(minus=3, zero=32, plus=3, errored=2)
    assert last.candidate_hard_violations == 2
    assert last.verdict is Verdict.ERROR
    expected = scored_wealth(3, 32, 3, 2, rule)
    assert (last.pass_wealth, last.block_wealth) == tuple(wealth_text(value) for value in expected)


@pytest.mark.parametrize(
    "increment",
    [
        RoundIncrement(0, 0, 20, 0, 0),
        RoundIncrement(20, 0, 0, 0, 0),
        RoundIncrement(0, 18, 0, 2, 0),
        RoundIncrement(0, 20, 0, 0, 1),
    ],
)
def test_decisive_round_does_not_consume_later_entries(increment: RoundIncrement) -> None:
    def source() -> Iterator[RoundIncrement]:
        yield RoundIncrement(0, 20, 0, 0, 0)
        yield increment
        raise AssertionError("consumed after a decision")

    looks = walk_rounds(rule_of(gate_manifest()), source())
    assert len(looks) == 2
    assert looks[-1].verdict is not Verdict.INCONCLUSIVE


def test_cap_does_not_consume_an_extra_entry_and_empty_input() -> None:
    rule = replace(rule_of(gate_manifest()), max_rounds=2)

    def source() -> Iterator[RoundIncrement]:
        for _ in range(rule.max_rounds):
            yield RoundIncrement(0, 20, 0, 0, 0)
        raise AssertionError("consumed beyond cap")

    looks = walk_rounds(rule, source())
    assert len(looks) == rule.max_rounds
    assert all(look.verdict is Verdict.INCONCLUSIVE for look in looks)
    assert walk_rounds(rule, []) == ()


@pytest.mark.parametrize("bad_field", ["record_sha256", "trial_id"])
def test_evaluate_does_not_digest_or_pair_after_stop(bad_field: str) -> None:
    manifest = gate_manifest()
    trials = store(manifest, [1] * 40)
    expected = evaluate_rounds(manifest, trials[:40])
    trials[41] = trials[41].model_copy(update={bad_field: None})
    assert evaluate_rounds(manifest, trials) == expected


def test_evaluate_hard_violations_on_errored_trials() -> None:
    manifest = gate_manifest()
    trials = store(manifest, [None] + [0] * 19)
    trials[1] = trials[1].model_copy(
        update={
            "contract": ContractResult(
                success=False,
                violations=(
                    Violation(invariant="a", severity="hard", detail=""),
                    Violation(invariant="b", severity="hard", detail=""),
                ),
            ),
        }
    )
    (look,) = evaluate_rounds(manifest, trials)
    assert look.counts.errored == 1
    assert look.candidate_hard_violations == 2
    assert look.verdict is Verdict.BLOCK


@pytest.mark.parametrize(
    "rounds,tolerance,message",
    [
        (3, 1, "budget cannot establish PASS for a candidate that never differs"),
        (3, 60, "budget cannot establish PASS for a candidate that never differs"),
        (4, 80, "PASS unreachable once max_errored_pairs is used"),
    ],
)
def test_rule_and_manifest_plan_errors_match(rounds: int, tolerance: int, message: str) -> None:
    manifest = gate_manifest(max_rounds=rounds, max_errored_pairs=tolerance)
    with pytest.raises(SuitePlanError) as direct:
        check_rule_plan(rule_of(manifest))
    with pytest.raises(SuitePlanError) as delegated:
        check_suite_plan(manifest)
    assert str(direct.value) == str(delegated.value) == message


@pytest.mark.parametrize("rounds", [1, 2, 3])
def test_rule_and_manifest_plan_warnings_match(rounds: int) -> None:
    manifest = SuiteManifest(
        **manifest_fields(
            tasks=tuple({"task_id": f"t{i}"} for i in range(50)),
            max_rounds=rounds,
            max_errored_pairs=1,
            acknowledge_single_round=rounds == 1,
        )
    )
    assert manifest.registered_pairs == rule_of(manifest).n_cells * rounds
    expected = ("max_rounds below 3: few looks",) if rounds < 3 else ()
    assert check_rule_plan(rule_of(manifest)) == check_suite_plan(manifest) == expected
