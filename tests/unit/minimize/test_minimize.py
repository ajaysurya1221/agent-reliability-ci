from __future__ import annotations

from collections.abc import Callable

from arci.interfaces import RunTrial
from arci.minimize import minimize_faults
from arci.schedule import spec_sha256
from arci.schema import (
    Bucket,
    Condition,
    ContractResult,
    ContractSpec,
    Event,
    FaultSpec,
    Manifest,
    Outcome,
    Termination,
    TrialEnvelope,
    TrialSpec,
)
from tests.acceptance.helpers import manifest
from tests.acceptance.helpers import spec as make_spec

FINGERPRINT = "a" * 64


def _fault(name: str) -> FaultSpec:
    return FaultSpec(name=name, bucket=Bucket.FALSIFY)


def _envelope(trial_spec: TrialSpec, fails: bool) -> TrialEnvelope:
    outcome = Outcome.FAIL if fails else Outcome.PASS
    return TrialEnvelope.create(
        spec_sha256=spec_sha256(trial_spec),
        experiment_id=trial_spec.experiment_id,
        trial_id=trial_spec.trial_id,
        pair_id=trial_spec.pair_id,
        arm=trial_spec.arm,
        variant=trial_spec.variant,
        task_id=trial_spec.task_id,
        condition_id=trial_spec.condition.condition_id,
        seed=trial_spec.seed,
        outcome=outcome,
        termination=Termination.COMPLETED,
        contract=ContractResult(success=not fails),
        failure_fingerprint=FINGERPRINT if fails else None,
        final_state={"fails": fails},
    )


def _setup(*names: str) -> tuple[Manifest, TrialSpec, TrialEnvelope]:
    condition = Condition(condition_id="fake-faults", faults=tuple(_fault(name) for name in names))
    trial_spec = make_spec("fragile_agent", condition=condition)
    return manifest(conditions=(condition,)), trial_spec, _envelope(trial_spec, True)


def _fake_runner(
    predicate: Callable[[tuple[str, ...]], bool], calls: list[tuple[str, ...]]
) -> RunTrial:
    def run(
        spec: TrialSpec,
        emit_event: Callable[[Event], None],
        contract: ContractSpec,
    ) -> TrialEnvelope:
        del emit_event, contract
        names = tuple(fault.name for fault in spec.condition.faults)
        assert names not in calls
        calls.append(names)
        return _envelope(spec, predicate(names))

    return run


def test_ddmin_keeps_two_jointly_necessary_faults() -> None:
    experiment, trial_spec, original = _setup("fault_a", "fault_b")
    calls: list[tuple[str, ...]] = []
    runner = _fake_runner(lambda names: names == ("fault_a", "fault_b"), calls)

    result = minimize_faults(experiment, original, trial_spec, run=runner)

    assert result.kept == ("fault_a", "fault_b")
    assert result.removed == ()
    assert result.minimality == "1-minimal"
    assert result.trials_run == 2
    assert calls == [("fault_a",), ("fault_b",)]
    assert result.bundle.minimality == result.minimality
    assert result.bundle.validate_seal()


def test_reports_reduced_when_postcheck_finds_single_fault_is_not_necessary() -> None:
    experiment, trial_spec, original = _setup("fault_a", "fault_b")
    calls: list[tuple[str, ...]] = []
    runner = _fake_runner(lambda names: names in {("fault_a",), ()}, calls)

    result = minimize_faults(experiment, original, trial_spec, run=runner)

    assert result.kept == ("fault_a",)
    assert result.removed == ("fault_b",)
    assert result.minimality == "reduced"
    assert result.trials_run == 2
    assert calls == [("fault_a",), ()]
    assert result.bundle.minimality == "reduced"
    assert result.bundle.validate_seal()
