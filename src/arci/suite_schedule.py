"""Content-bound suite identities and balanced schedules; no outcome-dependent choices."""

from __future__ import annotations

import re
from hashlib import sha256
from typing import Any, Literal

from arci.hashing import hash_record
from arci.schema import ArmSpec, Condition, TrialSpec, digest_payload
from arci.suite_schema import SuiteManifest, SuiteTask, parse_rational

Arm = Literal["baseline", "candidate"]


def suite_cells(manifest: SuiteManifest) -> tuple[tuple[SuiteTask, Condition], ...]:
    return tuple(
        (task, condition)
        for task in sorted(manifest.tasks, key=lambda task: task.task_id)
        for condition in sorted(manifest.conditions, key=lambda condition: condition.condition_id)
    )


def suite_rule_sha256(manifest: SuiteManifest) -> str:
    payload = digest_payload(manifest)
    del payload["experiment_id"]
    payload["tasks"] = sorted(payload["tasks"], key=lambda task: task["task_id"])
    payload["conditions"] = sorted(payload["conditions"], key=lambda c: c["condition_id"])
    return hash_record({"domain": "arci-suite/1 rule", "content": payload})


def suite_experiment_id(manifest: SuiteManifest) -> str:
    return f"{manifest.suite_id}@{suite_rule_sha256(manifest)}"


def create_suite_manifest(**fields: Any) -> SuiteManifest:
    if "experiment_id" in fields or "record_sha256" in fields:
        raise TypeError("experiment_id and record_sha256 are generated")
    draft = SuiteManifest(experiment_id="", **fields)
    return SuiteManifest.create(experiment_id=suite_experiment_id(draft), **fields)


def _key(rule_sha256: object, cell_index: int, round: int) -> bytes:
    if not isinstance(rule_sha256, str) or re.fullmatch(r"[0-9a-f]{64}", rule_sha256) is None:
        raise ValueError("rule_sha256 must be 64 lowercase hex characters")
    if type(cell_index) is not int or not 0 <= cell_index < 2**32:
        raise ValueError("cell_index must be an integer in [0, 2**32)")
    if type(round) is not int or not 1 <= round < 2**32:
        raise ValueError("round must be an integer in [1, 2**32)")
    return bytes.fromhex(rule_sha256) + cell_index.to_bytes(4, "big")


def cell_seed(rule_sha256: str, cell_index: int, round: int, scenario_seeds: str) -> int:
    key = _key(rule_sha256, cell_index, round)
    if scenario_seeds not in ("fixed", "per_round"):
        raise ValueError("unknown scenario_seeds mode")
    r = 0 if scenario_seeds == "fixed" else round
    digest = sha256(b"arci-suite/1 seed" + key + r.to_bytes(4, "big")).digest()
    return int.from_bytes(digest[:8], "big") & (2**53 - 1)


def arm_order(rule_sha256: str, cell_index: int, round: int) -> tuple[Arm, Arm]:
    key = _key(rule_sha256, cell_index, round)
    bit = sha256(b"arci-suite/1 order" + key + round.to_bytes(4, "big")).digest()[0] & 1
    return ("baseline", "candidate") if bit == 0 else ("candidate", "baseline")


def suite_pair_id(round: int, task_id: str, condition_id: str) -> str:
    return f"r{round:06d}:{task_id}:{condition_id}"


def pair_round(pair_id: str) -> int:
    match = re.fullmatch(r"r([0-9]{6}):[^:]+:[^:]+", pair_id)
    if match is None or int(match[1]) < 1:
        raise ValueError("invalid suite pair id")
    return int(match[1])


def build_suite_round(manifest: SuiteManifest, round: int) -> tuple[TrialSpec, ...]:
    if type(round) is not int or not 1 <= round <= manifest.max_rounds:
        raise ValueError("round must be within the registered plan")
    rule_sha256 = suite_rule_sha256(manifest)
    arms: tuple[tuple[Arm, ArmSpec], ...] = (
        ("baseline", manifest.baseline),
        ("candidate", manifest.candidate),
    )
    seeds: set[int] = set()
    specs: list[TrialSpec] = []
    for index, (task, condition) in enumerate(suite_cells(manifest)):
        seed = cell_seed(rule_sha256, index, round, manifest.scenario_seeds)
        if seed in seeds:
            raise ValueError("seed collision")
        seeds.add(seed)
        pair_id = suite_pair_id(round, task.task_id, condition.condition_id)
        for arm, arm_spec in arms:
            specs.append(
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
                    decisions=None,
                    task_id=task.task_id,
                    task=task.task,
                    condition=condition,
                    seed=seed,
                    budgets=manifest.budgets,
                    alpha=float(parse_rational(manifest.alpha)),
                    delta=float(parse_rational(manifest.delta)),
                )
            )
    return tuple(specs)


def build_suite_schedule(manifest: SuiteManifest) -> tuple[TrialSpec, ...]:
    return tuple(
        spec
        for round in range(1, manifest.max_rounds + 1)
        for spec in build_suite_round(manifest, round)
    )
