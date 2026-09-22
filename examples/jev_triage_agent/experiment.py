"""Frozen manifests for the Jev-style support-triage demonstration."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Literal, cast

from arci.schema import (
    DECISION_TOOL,
    ArmSpec,
    Bucket,
    Budgets,
    CommandSpec,
    Condition,
    ContractSpec,
    DecisionSpec,
    FaultSpec,
    Manifest,
    McpServerSpec,
)

from .world import Task, public_task

BASE = "examples.jev_triage_agent"
Variant = Literal["a", "b", "c"]
Runtime = Literal["python", "node"]


def _variant(value: str) -> Variant:
    if value not in {"a", "b", "c"}:
        raise ValueError("candidate must be 'a', 'b', or 'c'")
    return cast(Variant, value)


def _runtime(value: str) -> Runtime:
    if value not in {"python", "node"}:
        raise ValueError("runtime must be 'python' or 'node'")
    return cast(Runtime, value)


def _agent_command(variant: Variant, runtime: Runtime) -> CommandSpec:
    if runtime == "node":
        argv = (
            "node",
            str(Path(__file__).with_name("agent.mjs").resolve()),
            "--mcp-config",
            "{mcp_config}",
            "--task-file",
            "{task_file}",
            "--variant",
            variant,
        )
    else:
        argv = (
            sys.executable,
            "-P",
            "-m",
            f"{BASE}.agent",
            "--mcp-config",
            "{mcp_config}",
            "--task-file",
            "{task_file}",
            "--variant",
            variant,
        )
    return CommandSpec(
        argv=argv,
        infra_exit_codes=(),
    )


def _manifest(
    *,
    candidate: str,
    condition: Condition,
    n_per_arm: int,
    runtime: str,
    task: Task | None = None,
) -> Manifest:
    candidate_variant = _variant(candidate)
    selected_runtime = _runtime(runtime)
    return Manifest.create(
        experiment_id=f"jev-triage-{candidate_variant}-{condition.condition_id}-{n_per_arm}",
        task_id="triage-support-ticket",
        task=public_task() if task is None else task,
        mcp_server=McpServerSpec(
            name="support",
            argv=(
                sys.executable,
                "-P",
                "-m",
                "arci.mcp_toolset_server",
                "--toolset",
                f"{BASE}.world:make_world",
                "--workdir",
                "{workdir}",
                "--seed",
                "{seed}",
                "--task-file",
                "{task_file}",
            ),
            snapshot="arci.mcp_toolset_server:snapshot",
        ),
        decisions=DecisionSpec(
            upstream="fixture",
            fixture=f"{BASE}.decisions:fixture",
            model="jev-1.13.0",
        ),
        contract=ContractSpec(oracle=f"{BASE}.world:oracle"),
        baseline=ArmSpec(
            label="a",
            command=_agent_command("a", selected_runtime),
            candidate_id="triage-a",
        ),
        candidate=ArmSpec(
            label=candidate_variant,
            command=_agent_command(candidate_variant, selected_runtime),
            candidate_id=f"triage-{candidate_variant}",
        ),
        conditions=(condition,),
        n_per_arm=n_per_arm,
        base_seed=22_000,
        budgets=Budgets(
            max_tool_calls=8,
            max_model_steps=10,
            max_seconds=20.0,
            grader_seconds=10.0,
        ),
    )


def _low_confidence() -> FaultSpec:
    return FaultSpec(
        name="decision_low_confidence",
        bucket=Bucket.FALSIFY,
        tool=DECISION_TOOL,
        at_occurrence=0,
        params={"confidence_max": 0.4},
    )


def build_manifest(n_per_arm: int = 200, candidate: str = "b", runtime: str = "python") -> Manifest:
    return _manifest(
        candidate=candidate,
        condition=Condition(condition_id="low_confidence", faults=(_low_confidence(),)),
        n_per_arm=n_per_arm,
        runtime=runtime,
    )


def clean_manifest(candidate: str, runtime: str = "python") -> Manifest:
    return _manifest(
        candidate=candidate,
        condition=Condition(condition_id="clean"),
        n_per_arm=1,
        runtime=runtime,
    )


def noisy_manifest(candidate: str, runtime: str = "python") -> Manifest:
    return _manifest(
        candidate=candidate,
        condition=Condition(
            condition_id="low_confidence_noisy",
            faults=(
                _low_confidence(),
                FaultSpec(
                    name="empty_result",
                    bucket=Bucket.BENIGN,
                    tool="reply",
                    at_occurrence=0,
                ),
            ),
        ),
        n_per_arm=1,
        runtime=runtime,
    )


def calibrated_manifest(
    candidate: str,
    runtime: str = "python",
    *,
    n_per_arm: int = 200,
    ambiguous_share: float = 0.5,
    confidence: float = 0.7,
) -> Manifest:
    """Build an offline experiment with labelled synthetic miscalibration."""
    return _manifest(
        candidate=candidate,
        condition=Condition(condition_id="synthetic_miscalibration"),
        n_per_arm=n_per_arm,
        runtime=runtime,
        task=public_task(
            calibration={"ambiguous_share": ambiguous_share, "confidence": confidence}
        ),
    )
