"""Small valid inputs shared by suite tests."""

from collections.abc import Sequence
from typing import Any

from arci.schema import Outcome, TrialEnvelope, TrialSpec
from arci.suite_schema import SuiteManifest


def manifest_fields(**updates: Any) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "experiment_id": "supplied-id",
        "suite_id": "suite",
        "tasks": ({"task_id": "b", "task": {"value": 0.5}}, {"task_id": "a"}),
        "conditions": ({"condition_id": "z"}, {"condition_id": "clean"}),
        "toolset": "fixtures:tools",
        "contract": {"oracle": "fixtures:oracle"},
        "baseline": {"label": "base", "agent": "fixtures:baseline"},
        "candidate": {"label": "next", "agent": "fixtures:candidate"},
        "max_rounds": 100,
        "max_errored_pairs": 4,
    }
    fields.update(updates)
    return fields


def gate_manifest(**updates: Any) -> "SuiteManifest":
    from arci.suite_schedule import create_suite_manifest

    fields = manifest_fields(
        tasks=tuple({"task_id": f"t{i:02d}"} for i in range(20)),
        conditions=({"condition_id": "clean"},),
        max_rounds=4,
        max_errored_pairs=1,
    )
    del fields["experiment_id"]
    fields.update(updates)
    return create_suite_manifest(**fields)


def envelope(spec: "TrialSpec", outcome: "Outcome") -> "TrialEnvelope":
    from arci.schedule import spec_sha256
    from arci.schema import Termination, TrialEnvelope

    return TrialEnvelope.create(
        spec_sha256=spec_sha256(spec),
        experiment_id=spec.experiment_id,
        trial_id=spec.trial_id,
        pair_id=spec.pair_id,
        arm=spec.arm,
        variant=spec.variant,
        task_id=spec.task_id,
        condition_id=spec.condition.condition_id,
        seed=spec.seed,
        outcome=outcome,
        termination=Termination.COMPLETED,
    )


def store(manifest: "SuiteManifest", differences: "Sequence[int | None]") -> list["TrialEnvelope"]:
    from arci.schema import Outcome
    from arci.suite_schedule import build_suite_schedule

    specs = build_suite_schedule(manifest)
    trials: list[TrialEnvelope] = []
    for i, difference in enumerate(differences):
        a = Outcome.PASS if difference in (-1, 0) else Outcome.FAIL
        b = (
            Outcome.ERROR
            if difference is None
            else Outcome.PASS
            if difference in (0, 1)
            else Outcome.FAIL
        )
        trials.extend((envelope(specs[2 * i], a), envelope(specs[2 * i + 1], b)))
    return trials
