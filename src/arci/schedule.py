"""The experiment schedule. FROZEN (orchestrator-owned).

Both the runner (which executes it) and the gate (which checks every trial
against it) derive the schedule from the manifest alone, so neither can drift.
"""

from __future__ import annotations

from typing import Literal

from arci.hashing import hash_record
from arci.schema import ArmSpec, Manifest, TrialSpec, digest_payload

Arm = Literal["baseline", "candidate"]


def spec_sha256(spec: TrialSpec) -> str:
    """Identity of a trial spec: its non-volatile content."""
    return hash_record(digest_payload(spec, top=False))


def build_schedule(manifest: Manifest) -> tuple[TrialSpec, ...]:
    """For condition index j and repetition i, one baseline and one candidate trial.

    pair_id  = f"{condition_id}:{i:05d}"
    trial_id = f"{pair_id}:{arm}"
    seed     = base_seed + j * n_per_arm + i      (shared by both arms of the pair)
    variant  = the arm's label
    """
    arms: tuple[tuple[Arm, ArmSpec], ...] = (
        ("baseline", manifest.baseline),
        ("candidate", manifest.candidate),
    )
    out: list[TrialSpec] = []
    for j, condition in enumerate(manifest.conditions):
        for i in range(manifest.n_per_arm):
            pair_id = f"{condition.condition_id}:{i:05d}"
            for arm, arm_spec in arms:
                out.append(
                    TrialSpec(
                        experiment_id=manifest.experiment_id,
                        trial_id=f"{pair_id}:{arm}",
                        pair_id=pair_id,
                        arm=arm,
                        variant=arm_spec.label,
                        agent=arm_spec.agent,
                        command=arm_spec.command,
                        toolset=manifest.toolset,
                        mcp_server=manifest.mcp_server,
                        task_id=manifest.task_id,
                        task=manifest.task,
                        condition=condition,
                        seed=manifest.base_seed + j * manifest.n_per_arm + i,
                        budgets=manifest.budgets,
                        alpha=manifest.alpha,
                        delta=manifest.delta,
                        interval_method=manifest.interval_method,
                        looks=manifest.looks,
                        decisions=manifest.decisions,
                    )
                )
    return tuple(out)
