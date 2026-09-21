"""Builders for the MCP / command-agent acceptance tests. FROZEN."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Literal

from pydantic import JsonValue

from arci.schema import (
    ArmSpec,
    Budgets,
    CommandSpec,
    Condition,
    ContractSpec,
    Manifest,
    McpServerSpec,
    TrialSpec,
)
from tests.acceptance.helpers import COND_TIMEOUT, MOD

HERE = Path(__file__).resolve().parent
SERVER = str(HERE / "mcp_fixture_server.py")
CLIENT = str(HERE / "mcp_fixture_client.py")
ME = "tests.acceptance.mcp_fixtures"


def snapshot(task: dict[str, JsonValue], workdir: str) -> dict[str, JsonValue]:
    """Trusted: read the environment's state after the agent has gone."""
    path = Path(workdir) / "state.json"
    return json.loads(path.read_text()) if path.exists() else {}


def server(*extra: str) -> McpServerSpec:
    return McpServerSpec(
        argv=(sys.executable, SERVER, "--workdir", "{workdir}", *extra), snapshot=f"{ME}:snapshot"
    )


def client(variant: str, *extra: str) -> CommandSpec:
    return CommandSpec(
        argv=(sys.executable, CLIENT, "--mcp-config", "{mcp_config}", "--variant", variant, *extra)
    )


def mcp_contract(oracle: str = "oracle") -> ContractSpec:
    return ContractSpec(oracle=f"{MOD}:{oracle}")


def mcp_spec(
    variant: str,
    *,
    condition: Condition = COND_TIMEOUT,
    arm: Literal["baseline", "candidate"] = "candidate",
    max_seconds: float = 20.0,
    max_tool_calls: int = 20,
    server_args: tuple[str, ...] = (),
    client_args: tuple[str, ...] = (),
) -> TrialSpec:
    return TrialSpec(
        experiment_id="exp-mcp",
        trial_id=f"{condition.condition_id}:00000:{arm}",
        pair_id=f"{condition.condition_id}:00000",
        arm=arm,
        variant=variant,
        command=client(variant, *client_args),
        mcp_server=server(*server_args),
        task_id="store-the-answer",
        task={"goal": "store 42"},
        condition=condition,
        seed=11,
        budgets=Budgets(max_tool_calls=max_tool_calls, max_seconds=max_seconds),
    )


def mcp_manifest(
    *,
    candidate: str = "fragile",
    n_per_arm: int = 12,
    conditions: tuple[Condition, ...] = (COND_TIMEOUT,),
) -> Manifest:
    return Manifest.create(
        experiment_id="exp-mcp",
        task_id="store-the-answer",
        task={"goal": "store 42"},
        mcp_server=server(),
        contract=mcp_contract(),
        baseline=ArmSpec(label="A", command=client("good"), candidate_id="a"),
        candidate=ArmSpec(label="B", command=client(candidate), candidate_id="b"),
        conditions=conditions,
        n_per_arm=n_per_arm,
        base_seed=7,
        budgets=Budgets(max_tool_calls=20, max_seconds=20.0),
    )
