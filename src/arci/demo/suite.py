"""Twenty-cell offline suite: equal control, planted regression and short-cap uncertainty.

All randomness comes from the trial seed. Under a uniform draw from 0..7, every
cell has success probabilities control=7/8, regression=1/8, uncertain=6/8.
Both arms share that draw: paired regression is -3/4, uncertain is -1/8,
and the control is identical to baseline in law and outcome. These stochastic
models do not certify a sampling distribution for deterministic hash-derived seeds.
"""

from __future__ import annotations

import random
from collections.abc import Callable, Mapping

from pydantic import JsonValue

from arci.interfaces import ToolBoxProtocol, ToolFault
from arci.schema import ArmSpec, Bucket, Budgets, Condition, ContractSpec, FaultSpec
from arci.suite_schedule import create_suite_manifest
from arci.suite_schema import SuiteManifest, SuiteTask


class World:
    def __init__(self) -> None:
        self.value: JsonValue = None
        self.token: JsonValue = None
        self.tools: Mapping[str, Callable[..., JsonValue]] = {"finish": self.finish}

    def finish(self, value: JsonValue, token: int) -> JsonValue:
        self.value, self.token = value, token
        return {"done": True}

    def snapshot(self) -> dict[str, JsonValue]:
        return {"value": self.value, "token": self.token}


def make_world(task: dict[str, JsonValue], seed: int) -> World:
    del task, seed
    return World()


def oracle(task: dict[str, JsonValue], state: dict[str, JsonValue]) -> bool:
    return state.get("value") == task["target"]


def _finish(value: JsonValue, tools: ToolBoxProtocol, rng: random.Random) -> dict[str, JsonValue]:
    token = rng.randrange(1_000_000)
    for _ in range(2):
        try:
            tools.call("finish", value=value, token=token)
            break
        except ToolFault:
            continue
    return {"claimed": True}


def control(
    task: dict[str, JsonValue], tools: ToolBoxProtocol, rng: random.Random
) -> dict[str, JsonValue]:
    return _finish(task["target"] if rng.randrange(8) < 7 else "wrong", tools, rng)


def regression(
    task: dict[str, JsonValue], tools: ToolBoxProtocol, rng: random.Random
) -> dict[str, JsonValue]:
    return _finish(task["target"] if rng.randrange(8) < 1 else "wrong", tools, rng)


def uncertain(
    task: dict[str, JsonValue], tools: ToolBoxProtocol, rng: random.Random
) -> dict[str, JsonValue]:
    return _finish(task["target"] if rng.randrange(8) < 6 else "wrong", tools, rng)


def build_manifest(candidate: str = "control", *, max_rounds: int = 4) -> SuiteManifest:
    if candidate not in {"control", "regression", "uncertain"}:
        raise ValueError("candidate must be control, regression or uncertain")
    return create_suite_manifest(
        suite_id="offline-suite",
        tasks=tuple(SuiteTask(task_id=f"task{i}", task={"target": i}) for i in range(1, 6)),
        conditions=(
            Condition(condition_id="clean"),
            *(
                Condition(
                    condition_id=name,
                    faults=(
                        FaultSpec(name=name, bucket=Bucket.FALSIFY, tool="finish", at_occurrence=0),
                    ),
                )
                for name in ("tool_timeout", "tool_error_once", "empty_result")
            ),
        ),
        baseline=ArmSpec(label="control", agent="arci.demo.suite:control"),
        candidate=ArmSpec(label=candidate, agent=f"arci.demo.suite:{candidate}"),
        toolset="arci.demo.suite:make_world",
        contract=ContractSpec(oracle="arci.demo.suite:oracle"),
        max_rounds=max_rounds,
        max_errored_pairs=1,
        scenario_seeds="per_round",
        budgets=Budgets(max_tool_calls=3, max_model_steps=2, max_seconds=10, grader_seconds=10),
    )
