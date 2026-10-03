"""Frozen manifests for the Jev-style support-triage demonstration."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
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
LiveCondition = Literal["clean", "low_confidence", "unavailable"]

# TypeSafe direct. Through the Vercel AI Gateway use `https://ai-gateway.vercel.sh/typesafe`
# and the model id `typesafe-ai/jev` (see docs/DECISIONS.md, "Day one with a key").
DEFAULT_BASE_URL = "https://api.typesafe.ai"
DEFAULT_MODEL = "jev-1.13.0"
# The agent sends at most three decisions per trial, so 200 paced trial starts per minute keep
# admitted requests at or under 600/min, half the vendor's published 1,200/min.
DEFAULT_RPM = 200


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
    decisions: DecisionSpec | None = None,
    experiment_id: str | None = None,
    prior_runs: tuple[str, ...] = (),
) -> Manifest:
    candidate_variant = _variant(candidate)
    selected_runtime = _runtime(runtime)
    if decisions is None:
        decisions = DecisionSpec(
            upstream="fixture",
            fixture=f"{BASE}.decisions:fixture",
            model=DEFAULT_MODEL,
        )
    if experiment_id is None:
        experiment_id = f"jev-triage-{candidate_variant}-{condition.condition_id}-{n_per_arm}"
    return Manifest.create(
        experiment_id=experiment_id,
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
        decisions=decisions,
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
        prior_runs=prior_runs,
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


def _unavailable() -> FaultSpec:
    return FaultSpec(name="decision_unavailable", bucket=Bucket.FALSIFY, tool=DECISION_TOOL)


def _live_condition(name: str) -> Condition:
    if name == "clean":
        return Condition(condition_id="clean")
    if name == "low_confidence":
        return Condition(condition_id="low_confidence", faults=(_low_confidence(),))
    if name == "unavailable":
        return Condition(condition_id="provider_down", faults=(_unavailable(),))
    raise ValueError("condition must be 'clean', 'low_confidence', or 'unavailable'")


def live_manifest(
    candidate: str,
    *,
    n_per_arm: int = 50,
    runtime: str = "python",
    condition: str = "low_confidence",
    base_url: str = DEFAULT_BASE_URL,
    model: str = DEFAULT_MODEL,
    max_requests_per_minute: int = DEFAULT_RPM,
    prior_runs: tuple[str, ...] = (),
) -> Manifest:
    """The same triage experiment with decisions answered by the real System One endpoint.

    Only the decision upstream changes: the MCP world, the agents, the oracle, the budgets and
    the seeds are those of :func:`build_manifest`. The harness reads the real key from its own
    environment at run time; the manifest never contains it. Live answers are sampled, so a
    minimised failure from a live run is reported as ``reduced``, never ``1-minimal``.
    """
    selected = _live_condition(condition)
    suffix = "" if _runtime(runtime) == "python" else f"-{runtime}"
    return _manifest(
        candidate=candidate,
        condition=selected,
        n_per_arm=n_per_arm,
        runtime=runtime,
        decisions=DecisionSpec(
            upstream="http",
            base_url=base_url,
            model=model,
            max_requests_per_minute=max_requests_per_minute,
        ),
        experiment_id=(
            f"jev-live-{_variant(candidate)}-{selected.condition_id}-{n_per_arm}{suffix}"
        ),
        prior_runs=prior_runs,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Write a sealed manifest JSON for `arci preflight` / `arci run`."""
    parser = argparse.ArgumentParser(
        prog="python -m examples.jev_triage_agent.experiment",
        description="Write a sealed support-triage manifest, live (default) or seeded fixture.",
    )
    parser.add_argument("--candidate", default="b", choices=["a", "b", "c"])
    parser.add_argument("--n-per-arm", type=int, default=50)
    parser.add_argument(
        "--condition", default="low_confidence", choices=["clean", "low_confidence", "unavailable"]
    )
    parser.add_argument("--runtime", default="python", choices=["python", "node"])
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument(
        "--rpm", type=int, default=DEFAULT_RPM, help="paced trial starts per minute (http only)"
    )
    parser.add_argument("--prior-run", action="append", default=[], metavar="EXPERIMENT_ID")
    parser.add_argument(
        "--fixture",
        action="store_true",
        help="seeded fixture upstream instead of the live endpoint",
    )
    parser.add_argument("--out", required=True, metavar="PATH")
    args = parser.parse_args(argv)
    candidate = cast(str, args.candidate)
    n_per_arm = cast(int, args.n_per_arm)
    condition = cast(str, args.condition)
    runtime = cast(str, args.runtime)
    prior_runs = tuple(cast(list[str], args.prior_run))
    if cast(bool, args.fixture):
        manifest = _manifest(
            candidate=candidate,
            condition=_live_condition(condition),
            n_per_arm=n_per_arm,
            runtime=runtime,
            prior_runs=prior_runs,
        )
    else:
        manifest = live_manifest(
            candidate,
            n_per_arm=n_per_arm,
            runtime=runtime,
            condition=condition,
            base_url=cast(str, args.base_url),
            model=cast(str, args.model),
            max_requests_per_minute=cast(int, args.rpm),
            prior_runs=prior_runs,
        )
    out = Path(cast(str, args.out))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(f"{manifest.experiment_id} -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
