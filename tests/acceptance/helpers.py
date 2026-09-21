"""Builders shared by the acceptance suite. FROZEN."""

from __future__ import annotations

from typing import Literal

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
) -> TrialSpec:
    return TrialSpec(
        experiment_id="exp-acceptance",
        trial_id=f"{condition.condition_id}:00000:{arm}",
        pair_id=f"{condition.condition_id}:00000",
        arm=arm,
        variant=agent,
        agent=f"{MOD}:{agent}",
        toolset=f"{MOD}:make_world",
        task_id="store-the-answer",
        task={"goal": "store 42"},
        condition=condition,
        seed=seed,
        budgets=Budgets(max_tool_calls=max_tool_calls, max_seconds=max_seconds),
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
    for arm, successes in (("baseline", baseline_successes), ("candidate", candidate_successes)):
        for i in range(count):
            ok = i < successes
            is_error = arm == "candidate" and i >= count - candidate_errors
            hard = arm == "candidate" and i < candidate_hard_violations
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
                    spec_sha256="0" * 64,
                    experiment_id=m.experiment_id,
                    trial_id=f"{condition_id}:{i:05d}:{arm}",
                    pair_id=f"{condition_id}:{i:05d}",
                    arm=arm,
                    variant=arm,
                    task_id=m.task_id,
                    condition_id=condition_id,
                    seed=i,
                    outcome=outcome,
                    termination=(Termination.HARNESS_ERROR if is_error else Termination.COMPLETED),
                    contract=None
                    if is_error
                    else ContractResult(success=ok, violations=violations),
                    failure_fingerprint=None if outcome is Outcome.PASS else "f" * 64,
                )
            )
    return out
