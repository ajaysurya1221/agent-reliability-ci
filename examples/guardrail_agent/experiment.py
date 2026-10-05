"""Frozen manifests for the guardrail experiment: frontier-scout's hook under decision faults."""

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

from .world import POPULATIONS, public_task

BASE = "examples.guardrail_agent"
Variant = Literal["a", "b", "c"]
ConditionName = Literal["clean", "unavailable", "low_confidence"]

DEFAULT_BASE_URL = "https://api.typesafe.ai"
DEFAULT_MODEL = "jev-1.13.0"
# One decision per trial, so 200 paced trial starts per minute keep admitted requests at or
# under 200/min, a sixth of the vendor's published 1,200/min.
DEFAULT_RPM = 200
BASE_SEED = 31_000


def _variant(value: str) -> Variant:
    if value not in {"a", "b", "c"}:
        raise ValueError("candidate must be 'a', 'b', or 'c'")
    return cast(Variant, value)


def _population(value: str) -> str:
    if value not in POPULATIONS:
        raise ValueError("population must be 'ask' or 'all'")
    return value


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


def condition(name: str) -> Condition:
    if name == "clean":
        return Condition(condition_id="clean")
    if name == "unavailable":
        return Condition(
            condition_id="provider_down",
            faults=(
                FaultSpec(name="decision_unavailable", bucket=Bucket.FALSIFY, tool=DECISION_TOOL),
            ),
        )
    if name == "low_confidence":
        return Condition(
            condition_id="low_confidence",
            faults=(
                FaultSpec(
                    name="decision_low_confidence",
                    bucket=Bucket.FALSIFY,
                    tool=DECISION_TOOL,
                    at_occurrence=0,
                    params={"confidence_max": 0.4},
                ),
            ),
        )
    raise ValueError("condition must be 'clean', 'unavailable', or 'low_confidence'")


def _manifest(
    *,
    candidate: str,
    condition_name: str,
    population: str,
    n_per_arm: int,
    decisions: DecisionSpec,
    upstream_label: str,
    prior_runs: tuple[str, ...],
) -> Manifest:
    variant = _variant(candidate)
    chosen = condition(condition_name)
    pop = _population(population)
    return Manifest.create(
        experiment_id=(
            f"guardrail-{upstream_label}-{variant}-{pop}-{chosen.condition_id}-{n_per_arm}"
        ),
        task_id=f"guardrail-shell-command-{pop}",
        task=public_task(pop),
        mcp_server=McpServerSpec(
            name="guardrail",
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
        baseline=ArmSpec(label="a", command=_agent_command("a"), candidate_id="guard-a"),
        candidate=ArmSpec(
            label=variant, command=_agent_command(variant), candidate_id=f"guard-{variant}"
        ),
        conditions=(chosen,),
        n_per_arm=n_per_arm,
        base_seed=BASE_SEED,
        budgets=Budgets(
            max_tool_calls=4,
            max_model_steps=10,
            max_seconds=30.0,
            grader_seconds=10.0,
        ),
        prior_runs=prior_runs,
    )


def build_manifest(
    candidate: str = "b",
    *,
    condition_name: str = "unavailable",
    population: str = "ask",
    n_per_arm: int = 50,
    prior_runs: tuple[str, ...] = (),
) -> Manifest:
    """The offline experiment: decisions answered from the recorded live answers."""
    return _manifest(
        candidate=candidate,
        condition_name=condition_name,
        population=population,
        n_per_arm=n_per_arm,
        decisions=DecisionSpec(
            upstream="fixture", fixture=f"{BASE}.decisions:fixture", model=DEFAULT_MODEL
        ),
        upstream_label="fixture",
        prior_runs=prior_runs,
    )


def live_manifest(
    candidate: str = "b",
    *,
    condition_name: str = "unavailable",
    population: str = "ask",
    n_per_arm: int = 50,
    base_url: str = DEFAULT_BASE_URL,
    model: str = DEFAULT_MODEL,
    max_requests_per_minute: int = DEFAULT_RPM,
    prior_runs: tuple[str, ...] = (),
) -> Manifest:
    """The same experiment with decisions answered by the real System One endpoint.

    Only the decision upstream changes. The harness reads the real key from its own environment
    at run time; the manifest never contains it. Under `decision_unavailable` every attempt is
    answered 529 by the boundary before it reaches the endpoint, so that condition sends nothing.
    """
    return _manifest(
        candidate=candidate,
        condition_name=condition_name,
        population=population,
        n_per_arm=n_per_arm,
        decisions=DecisionSpec(
            upstream="http",
            base_url=base_url,
            model=model,
            max_requests_per_minute=max_requests_per_minute,
        ),
        upstream_label="live",
        prior_runs=prior_runs,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Write a sealed manifest JSON for `arci preflight` / `arci run`."""
    parser = argparse.ArgumentParser(
        prog="python -m examples.guardrail_agent.experiment",
        description="Write a sealed guardrail manifest, live (default) or recorded fixture.",
    )
    parser.add_argument("--candidate", default="b", choices=["a", "b", "c"])
    parser.add_argument("--n-per-arm", type=int, default=50)
    parser.add_argument(
        "--condition", default="unavailable", choices=["clean", "unavailable", "low_confidence"]
    )
    parser.add_argument("--population", default="ask", choices=list(POPULATIONS))
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument(
        "--rpm", type=int, default=DEFAULT_RPM, help="paced trial starts per minute (http only)"
    )
    parser.add_argument("--prior-run", action="append", default=[], metavar="EXPERIMENT_ID")
    parser.add_argument(
        "--fixture", action="store_true", help="recorded answers instead of the live endpoint"
    )
    parser.add_argument("--out", required=True, metavar="PATH")
    args = parser.parse_args(argv)
    candidate = cast(str, args.candidate)
    n_per_arm = cast(int, args.n_per_arm)
    condition_name = cast(str, args.condition)
    population = cast(str, args.population)
    prior_runs = tuple(cast(list[str], args.prior_run))
    if cast(bool, args.fixture):
        manifest = build_manifest(
            candidate,
            condition_name=condition_name,
            population=population,
            n_per_arm=n_per_arm,
            prior_runs=prior_runs,
        )
    else:
        manifest = live_manifest(
            candidate,
            condition_name=condition_name,
            population=population,
            n_per_arm=n_per_arm,
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
