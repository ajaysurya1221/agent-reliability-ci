"""v0.2 bridge: serve any v0.1 python toolset as a stdio MCP server. FROZEN."""

from __future__ import annotations

import sys

import pytest

from arci.schema import Event, McpServerSpec, Outcome, TrialEnvelope
from tests.acceptance.helpers import COND_CLEAN, MOD
from tests.acceptance.mcp_fixtures import mcp_contract, mcp_spec

pytestmark = pytest.mark.acceptance

BRIDGE = McpServerSpec(
    argv=(
        sys.executable,
        "-P",
        "-m",
        "arci.mcp_toolset_server",
        "--toolset",
        f"{MOD}:make_world",
        "--tools",
        "fetch,store,log",
        "--workdir",
        "{workdir}",
        "--seed",
        "{seed}",
    ),
    snapshot="arci.mcp_toolset_server:snapshot",
)


def _run(variant: str, **kw: object) -> TrialEnvelope:
    from arci.runner import run_trial

    sink: list[Event] = []
    spec = mcp_spec(variant, **kw).model_copy(update={"mcp_server": BRIDGE})  # pyright: ignore[reportArgumentType]
    return run_trial(spec, sink.append, mcp_contract())


def test_a_python_toolset_becomes_an_mcp_environment() -> None:
    env = _run("good", condition=COND_CLEAN)
    assert env.outcome is Outcome.PASS
    assert env.final_state == {"stored": 42, "log": ["start"]}  # World.snapshot(), via the bridge


def test_fault_injection_and_the_oracle_work_through_the_bridge() -> None:
    assert _run("good").outcome is Outcome.PASS
    broken = _run("fragile")
    assert broken.outcome is Outcome.FAIL
    assert broken.final_state == {"stored": None, "log": ["start"]}


def test_the_bridge_is_deterministic() -> None:
    assert _run("fragile").record_sha256 == _run("fragile").record_sha256
