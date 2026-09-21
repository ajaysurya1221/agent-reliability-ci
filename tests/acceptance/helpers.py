"""Builders shared by the acceptance suite. FROZEN."""

from __future__ import annotations

from typing import Literal

from pydantic import JsonValue

from arci.schedule import build_schedule, spec_sha256
from arci.schema import (
    ArmSpec,
    Bucket,
    Budgets,
    Condition,
    ContractResult,
    ContractSpec,
    FaultSpec,
    Manifest,
    Outcome,
    Termination,
    TrialEnvelope,
    TrialSpec,
    Violation,
)

MOD = "tests.acceptance.fixture_agents"
TIMEOUT = FaultSpec(name="tool_timeout", bucket=Bucket.FALSIFY, tool="fetch", at_occurrence=0)
EMPTY_LOG = FaultSpec(name="empty_result", bucket=Bucket.BENIGN, tool="log", at_occurrence=0)
NEVER = FaultSpec(name="tool_error_once", bucket=Bucket.FALSIFY, tool="store", at_occurrence=9)

COND_TIMEOUT = Condition(condition_id="fetch_timeout", faults=(TIMEOUT,))
COND_CLEAN = Condition(condition_id="clean", faults=())
COND_NOISY = Condition(condition_id="noisy", faults=(EMPTY_LOG, TIMEOUT, NEVER))
DEAD = FaultSpec(name="tool_error_once", bucket=Bucket.CEILING, tool="fetch", at_occurrence=0)
COND_CEILING = Condition(condition_id="dead_backend", faults=(DEAD,))


def contract(oracle: str = "oracle", **kw: object) -> ContractSpec:
    return ContractSpec(oracle=f"{MOD}:{oracle}", **kw)  # pyright: ignore[reportArgumentType]


def manifest(
    *,
    baseline: str = "good_agent",
    candidate: str = "fragile_agent",
    conditions: tuple[Condition, ...] = (COND_TIMEOUT,),
    n_per_arm: int = 200,
    oracle: str = "oracle",
    prior_runs: tuple[str, ...] = (),
    max_seconds: float = 10.0,
    alpha: float = 0.05,
) -> Manifest:
    return Manifest.create(
        experiment_id="exp-acceptance",
        task_id="store-the-answer",
        task={"goal": "store 42"},
        toolset=f"{MOD}:make_world",
        contract=contract(oracle),
        baseline=ArmSpec(label="A", agent=f"{MOD}:{baseline}", candidate_id="a"),
        candidate=ArmSpec(label="B", agent=f"{MOD}:{candidate}", candidate_id="b"),
        conditions=conditions,
        n_per_arm=n_per_arm,
        alpha=alpha,
        base_seed=7,
        budgets=Budgets(max_tool_calls=20, max_seconds=max_seconds),
        prior_runs=prior_runs,
    )


def spec(
    agent: str,
    *,
    condition: Condition = COND_TIMEOUT,
    arm: Literal["baseline", "candidate"] = "candidate",
    seed: int = 11,
    max_seconds: float = 10.0,
    max_tool_calls: int = 20,
    toolset: str = "make_world",
    task: dict[str, JsonValue] | None = None,
    grader_seconds: float = 20.0,
) -> TrialSpec:
    return TrialSpec(
        experiment_id="exp-acceptance",
        trial_id=f"{condition.condition_id}:00000:{arm}",
        pair_id=f"{condition.condition_id}:00000",
        arm=arm,
        variant=agent,
        agent=f"{MOD}:{agent}",
        toolset=f"{MOD}:{toolset}",
        task_id="store-the-answer",
        task={"goal": "store 42"} if task is None else task,
        condition=condition,
        seed=seed,
        budgets=Budgets(
            max_tool_calls=max_tool_calls, max_seconds=max_seconds, grader_seconds=grader_seconds
        ),
    )


def synthetic_trials(
    m: Manifest,
    *,
    condition_id: str,
    baseline_successes: int,
    candidate_successes: int,
    n: int | None = None,
    candidate_errors: int = 0,
    candidate_hard_violations: int = 0,
) -> list[TrialEnvelope]:
    """Envelopes with chosen outcomes, for testing `decide` without running agents."""
    count = m.n_per_arm if n is None else n
    out: list[TrialEnvelope] = []
    for s in build_schedule(m):
        i = int(s.pair_id.rsplit(":", 1)[1])
        if s.condition.condition_id != condition_id or i >= count:
            continue
        candidate = s.arm == "candidate"
        ok = i < (candidate_successes if candidate else baseline_successes)
        is_error = candidate and i >= count - candidate_errors
        hard = candidate and i < candidate_hard_violations
        violations = (
            (Violation(invariant="forbidden_tools", severity="hard", detail="used rm"),)
            if hard
            else ()
        )
        # A hard violation makes the trial FAIL even when the oracle is satisfied.
        passed = ok and not hard
        outcome = Outcome.ERROR if is_error else (Outcome.PASS if passed else Outcome.FAIL)
        out.append(
            TrialEnvelope.create(
                spec_sha256=spec_sha256(s),
                experiment_id=s.experiment_id,
                trial_id=s.trial_id,
                pair_id=s.pair_id,
                arm=s.arm,
                variant=s.variant,
                task_id=s.task_id,
                condition_id=condition_id,
                seed=s.seed,
                outcome=outcome,
                termination=Termination.HARNESS_ERROR if is_error else Termination.COMPLETED,
                contract=None if is_error else ContractResult(success=ok, violations=violations),
                failure_fingerprint=None if outcome is Outcome.PASS else "f" * 64,
            )
        )
    return out


def reseal(trial: TrialEnvelope, **update: object) -> TrialEnvelope:
    """A validly sealed copy with some fields changed (a well-formed impostor)."""
    return TrialEnvelope.create(**{**trial.model_dump(exclude={"record_sha256"}), **update})
