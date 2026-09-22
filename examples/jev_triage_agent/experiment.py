"""Frozen manifests for the Jev-style support-triage demonstration."""

from __future__ import annotations

import sys
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

from .world import public_task

BASE = "examples.jev_triage_agent"
Variant = Literal["a", "b", "c"]


def _variant(value: str) -> Variant:
    if value not in {"a", "b", "c"}:
        raise ValueError("candidate must be 'a', 'b', or 'c'")
    return cast(Variant, value)


def _agent_command(variant: Variant) -> CommandSpec:
    return CommandSpec(
        argv=(
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
        ),
        infra_exit_codes=(),
    )


def _manifest(*, candidate: str, condition: Condition, n_per_arm: int) -> Manifest:
    candidate_variant = _variant(candidate)
    return Manifest.create(
        experiment_id=f"jev-triage-{candidate_variant}-{condition.condition_id}-{n_per_arm}",
        task_id="triage-support-ticket",
        task=public_task(),
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
        baseline=ArmSpec(label="a", command=_agent_command("a"), candidate_id="triage-a"),
        candidate=ArmSpec(
            label=candidate_variant,
            command=_agent_command(candidate_variant),
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


def build_manifest(n_per_arm: int = 200, candidate: str = "b") -> Manifest:
    return _manifest(
        candidate=candidate,
        condition=Condition(condition_id="low_confidence", faults=(_low_confidence(),)),
        n_per_arm=n_per_arm,
    )


def clean_manifest(candidate: str) -> Manifest:
    return _manifest(
        candidate=candidate,
        condition=Condition(condition_id="clean"),
        n_per_arm=1,
    )


def noisy_manifest(candidate: str) -> Manifest:
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
    )
