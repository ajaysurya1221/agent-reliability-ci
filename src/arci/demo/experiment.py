"""Frozen-manifest builders for the packaged retry demo (``arci demo``).

The same experiment as ``examples/retry_agent/experiment.py``: the same task, condition,
budgets and base seed, so the same trial seeds and the same counts. Only the references
(``arci.demo.*``, importable from an installed wheel) and the ``arci-demo-`` experiment id
prefix differ, which gives these manifests their own seals.
"""

from __future__ import annotations

from arci.schema import (
    ArmSpec,
    Bucket,
    Budgets,
    Condition,
    ContractSpec,
    FaultSpec,
    Manifest,
)

BASE = "arci.demo"
CANDIDATES = ("agent_a", "agent_b", "agent_c")


def _manifest(*, candidate: str, condition: Condition, n_per_arm: int) -> Manifest:
    if candidate not in CANDIDATES:
        raise ValueError(f"unknown candidate: {candidate}")
    return Manifest.create(
        experiment_id=f"arci-demo-{candidate}-{condition.condition_id}-{n_per_arm}",
        task_id="confirm-inventory-order",
        task={
            "order_id": "order-7",
            "sku": "widget",
            "quantity": 2,
            "stock": 10,
        },
        toolset=f"{BASE}.world:make_world",
        contract=ContractSpec(oracle=f"{BASE}.world:oracle"),
        baseline=ArmSpec(
            label="agent_a", agent=f"{BASE}.agents:agent_a", candidate_id="baseline-a"
        ),
        candidate=ArmSpec(
            label=candidate,
            agent=f"{BASE}.agents:{candidate}",
            candidate_id=f"candidate-{candidate}",
        ),
        conditions=(condition,),
        n_per_arm=n_per_arm,
        base_seed=12_000,
        budgets=Budgets(max_tool_calls=10, max_model_steps=10, max_seconds=15.0),
    )


def build_manifest(n_per_arm: int = 200, candidate: str = "agent_b") -> Manifest:
    """The frozen experiment: ``tool_timeout`` on the first ``reserve`` call."""
    condition = Condition(
        condition_id="reserve-timeout",
        faults=(
            FaultSpec(
                name="tool_timeout",
                bucket=Bucket.FALSIFY,
                tool="reserve",
                at_occurrence=0,
            ),
        ),
    )
    return _manifest(candidate=candidate, condition=condition, n_per_arm=n_per_arm)


def clean_manifest(candidate: str = "agent_b") -> Manifest:
    """One fault-free pair: the illustrative run that cannot tell A from B."""
    return _manifest(
        candidate=candidate,
        condition=Condition(condition_id="clean"),
        n_per_arm=1,
    )
