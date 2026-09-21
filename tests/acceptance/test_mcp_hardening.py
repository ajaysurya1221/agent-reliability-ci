"""v0.2 hardening: findings from the pre-release review of the MCP boundary. FROZEN."""

from __future__ import annotations

import sys

import pytest

from arci.schema import (
    Event,
    McpServerSpec,
    Outcome,
    ReplayBundle,
    ReplayStatus,
    Termination,
    TrialEnvelope,
)
from tests.acceptance.helpers import COND_CLEAN, MOD
from tests.acceptance.mcp_fixtures import mcp_contract, mcp_manifest, mcp_spec

pytestmark = pytest.mark.acceptance


def _bridge(factory: str) -> McpServerSpec:
    return McpServerSpec(
        argv=(
            sys.executable,
            "-P",
            "-m",
            "arci.mcp_toolset_server",
            "--toolset",
            f"{MOD}:{factory}",
            "--tools",
            "fetch,store,log",
            "--workdir",
            "{workdir}",
            "--seed",
            "{seed}",
        ),
        snapshot="arci.mcp_toolset_server:snapshot",
    )


def _run(variant: str, *, bridge: str | None = None, **kw: object) -> TrialEnvelope:
    from arci.runner import run_trial

    sink: list[Event] = []
    spec = mcp_spec(variant, **kw)  # pyright: ignore[reportArgumentType]
    if bridge is not None:
        spec = spec.model_copy(update={"mcp_server": _bridge(bridge)})
    return run_trial(spec, sink.append, mcp_contract())


def test_leftover_recording_is_invalid_even_when_the_agent_hangs_to_the_deadline() -> None:
    from arci.replay import make_bundle, replay

    hung = _run("hang", condition=COND_CLEAN, max_seconds=4.0)
    assert hung.outcome is Outcome.FAIL and hung.termination is Termination.TIMEOUT
    spec = mcp_spec("hang", condition=COND_CLEAN, max_seconds=4.0)
    bundle = make_bundle(mcp_manifest(candidate="hang", conditions=(COND_CLEAN,)), hung, spec)
    assert replay(bundle).status is ReplayStatus.REPRODUCED
    padded = bundle.spec.model_copy(
        update={"recording": (*bundle.spec.recording, bundle.spec.recording[-1])}
    )
    data = bundle.model_dump(exclude={"record_sha256"})
    assert replay(ReplayBundle.create(**{**data, "spec": padded})).status is ReplayStatus.INVALID


def test_a_client_protocol_mistake_is_the_agents_problem_not_a_harness_error() -> None:
    env = _run("badargs", condition=COND_CLEAN)
    assert env.outcome is Outcome.PASS, env.failure_detail  # it recovered and did the work
    assert env.usage.tool_calls == 3  # the malformed call never reached the tool boundary


def test_a_malformed_server_result_is_a_harness_error() -> None:
    env = _run("good", condition=COND_CLEAN, server_args=("--malformed",))
    assert env.outcome is Outcome.ERROR and env.termination is Termination.HARNESS_ERROR


def test_an_environment_returning_non_json_is_a_harness_error_not_a_tool_error() -> None:
    env = _run("good", condition=COND_CLEAN, bridge="make_setty_world")
    assert env.outcome is Outcome.ERROR and env.termination is Termination.HARNESS_ERROR


def test_tool_error_text_from_the_bridge_does_not_leak_run_specific_paths() -> None:
    a = _run("fragile", condition=COND_CLEAN, bridge="make_pathy_world")
    b = _run("fragile", condition=COND_CLEAN, bridge="make_pathy_world")
    assert a.outcome is Outcome.FAIL and a.termination is Termination.COMPLETED
    assert a.record_sha256 == b.record_sha256
    assert "arci-pathy-" not in a.model_dump_json()


def test_large_recordings_are_streamed_not_squeezed_into_one_frame() -> None:
    env = _run("double", condition=COND_CLEAN, server_args=("--big",), max_seconds=40.0)
    assert env.outcome is Outcome.PASS, env.failure_detail
    fetched = [r for r in env.recording if r.tool == "fetch"]
    assert len(fetched) == 2 and len(env.model_dump_json()) > 1_400_000
    assert env.validate_seal()


def test_pipelined_large_messages_do_not_deadlock_the_boundary() -> None:
    env = _run("pipeline", condition=COND_CLEAN, server_args=("--big",), max_seconds=40.0)
    assert env.outcome is Outcome.PASS, env.failure_detail
    assert env.usage.wall_seconds < 30


def test_an_infrastructure_exit_code_invalidates_the_trial_instead_of_blaming_the_agent() -> None:
    """Found the hard way: a local model server died mid-experiment and 435 trials "crashed"."""
    infra = _run("infra", condition=COND_CLEAN)
    assert infra.outcome is Outcome.ERROR and infra.termination is Termination.HARNESS_ERROR
    assert infra.failure_detail is not None and "infrastructure" in infra.failure_detail
    crashed = _run("boom", condition=COND_CLEAN)
    assert crashed.outcome is Outcome.FAIL and crashed.termination is Termination.CRASH
