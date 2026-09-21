"""v0.2: command agents behind the harness-owned MCP boundary. FROZEN. Offline, no model calls.

The acceptance story: removed retry -> reproduced failure -> repaired retry, for an agent that is
an arbitrary subprocess speaking MCP over stdio.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
from pydantic import ValidationError

from arci.schema import (
    ArmSpec,
    Event,
    Outcome,
    ReplayBundle,
    ReplayStatus,
    Termination,
    ToolMode,
    TrialEnvelope,
    Verdict,
)
from tests.acceptance.helpers import COND_CLEAN
from tests.acceptance.mcp_fixtures import client, mcp_contract, mcp_manifest, mcp_spec, server

pytestmark = pytest.mark.acceptance
REPO = Path(__file__).resolve().parents[2]


def _run(variant: str, **kw: object) -> tuple[TrialEnvelope, list[Event]]:
    from arci.runner import run_trial

    seen: list[Event] = []
    env = run_trial(mcp_spec(variant, **kw), seen.append, mcp_contract())  # pyright: ignore[reportArgumentType]
    return env, seen


def _kinds(env: TrialEnvelope) -> list[str]:
    return [e.kind for e in env.events]


def _terminated(pid: int) -> bool:
    stat = subprocess.run(
        ["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True, check=False
    ).stdout.strip()
    return stat == "" or stat.startswith("Z")


def _rebundle(bundle: ReplayBundle, **spec_update: object) -> ReplayBundle:
    data = bundle.model_dump(exclude={"record_sha256"})
    return ReplayBundle.create(**{**data, "spec": bundle.spec.model_copy(update=spec_update)})


# --- schema ---------------------------------------------------------------------------


def test_an_arm_is_a_python_agent_or_a_command_never_both() -> None:
    with pytest.raises(ValidationError):
        ArmSpec(label="x")
    with pytest.raises(ValidationError):
        ArmSpec(label="x", agent="a.b:c", command=client("good"))
    data = mcp_manifest().model_dump(exclude={"record_sha256"})
    with pytest.raises(ValidationError):  # command agents need an MCP server, not a toolset
        type(mcp_manifest()).create(**{**data, "mcp_server": None})


# --- the boundary -----------------------------------------------------------------------


def test_both_clients_pass_without_injection() -> None:
    for variant in ("good", "fragile"):
        env, _ = _run(variant, condition=COND_CLEAN)
        assert env.outcome is Outcome.PASS, variant
        assert env.final_state == {"stored": 42, "log": ["start"]}


def test_injected_timeout_separates_the_retrying_client_from_the_broken_one() -> None:
    good, seen = _run("good")
    assert good.outcome is Outcome.PASS and good.termination is Termination.COMPLETED
    assert good.validate_seal() and good.usage.tool_calls == 4  # log, fetch(injected), fetch, store
    injected = [
        e
        for e in good.events
        if e.kind == "tool_finish" and e.payload.get("injected_by") == "tool_timeout"
    ]
    assert len(injected) == 1 and injected[0].payload.get("ok") is False
    assert [e.seq for e in good.events] == list(range(len(good.events)))
    assert _kinds(good)[0] == "trial_start" and _kinds(good).count("trial_end") == 1
    assert _kinds(good)[-1] == "trial_end" and [e.kind for e in seen] == _kinds(good)
    starts = [e.payload.get("tool") for e in good.events if e.kind == "tool_start"]
    assert starts == ["log", "fetch", "fetch", "store"]  # only tools/call is a tool event

    broken, _ = _run("fragile")
    assert broken.outcome is Outcome.FAIL and broken.termination is Termination.COMPLETED
    assert broken.agent_claimed_success is True  # it exited 0
    assert broken.final_state == {"stored": None, "log": ["start"]}
    assert broken.failure_fingerprint is not None


def test_a_scripted_client_gives_a_deterministic_sealed_record() -> None:
    a, _ = _run("fragile")
    b, _ = _run("fragile")
    assert a.record_sha256 == b.record_sha256
    assert "/" not in " ".join(str(e.payload) for e in a.events if e.kind != "tool_start")


def test_a_client_that_never_touches_its_tools_is_failed_by_the_snapshot_oracle() -> None:
    env, _ = _run("liar", condition=COND_CLEAN)
    assert env.outcome is Outcome.FAIL and env.agent_claimed_success is True


def test_timeout_budget_and_cleanup(tmp_path: Path) -> None:
    pids = ("--pid-dir", str(tmp_path))
    hung, _ = _run(
        "hang", condition=COND_CLEAN, max_seconds=4.0, server_args=pids, client_args=pids
    )
    assert hung.outcome is Outcome.FAIL and hung.termination is Termination.TIMEOUT
    assert "tool_finish" in _kinds(hung) and hung.validate_seal()
    for name in ("server.pid", "client.pid"):
        pid = int((tmp_path / name).read_text())
        deadline = time.monotonic() + 10
        while not _terminated(pid) and time.monotonic() < deadline:
            time.sleep(0.1)
        assert _terminated(pid), f"{name} survived the trial"

    chatty, _ = _run("chatty", condition=COND_CLEAN, max_tool_calls=5)
    assert chatty.outcome is Outcome.FAIL and chatty.termination is Termination.BUDGET
    assert chatty.usage.tool_calls == 5


def test_unsupported_mcp_features_are_a_harness_error_not_a_silent_pass_through() -> None:
    env, _ = _run("direct", condition=COND_CLEAN, server_args=("--task-results",))
    assert env.outcome is Outcome.ERROR and env.termination is Termination.HARNESS_ERROR


def test_a_server_that_will_not_start_is_a_harness_error() -> None:
    from arci.runner import run_trial

    spec = mcp_spec("good", condition=COND_CLEAN)
    dead = spec.model_copy(
        update={"mcp_server": server().model_copy(update={"argv": ("/nonexistent/mcp-server",)})}
    )
    sink: list[Event] = []
    env = run_trial(dead, sink.append, mcp_contract())
    assert env.validate_seal()
    assert env.outcome is Outcome.ERROR and env.termination is Termination.HARNESS_ERROR


# --- replay -----------------------------------------------------------------------------


def test_replay_reproduces_the_failure_without_ever_starting_the_server(tmp_path: Path) -> None:
    from arci.replay import make_bundle, replay

    env, _ = _run("fragile")
    bundle = make_bundle(mcp_manifest(), env, mcp_spec("fragile"))
    assert bundle.validate_seal() and bundle.spec.tool_mode is ToolMode.REPLAY
    assert bundle.spec.replay_final_state == env.final_state
    marker = tmp_path / "server-started"
    forbidden = _rebundle(bundle, mcp_server=server("--marker", str(marker)))
    assert replay(forbidden).status is ReplayStatus.REPRODUCED
    assert not marker.exists(), "replay launched the live server"


def test_replay_mismatch_is_invalid() -> None:
    from arci.replay import make_bundle, replay

    env, _ = _run("fragile")
    bundle = make_bundle(mcp_manifest(), env, mcp_spec("fragile"))
    calls = [r for r in bundle.spec.recording if r.tool == "fetch"]
    assert calls, "tools/call exchanges must be in the recording"
    tampered = tuple(
        r.model_copy(update={"arguments_sha256": "0" * 64}) if r is calls[0] else r
        for r in bundle.spec.recording
    )
    assert replay(_rebundle(bundle, recording=tampered)).status is ReplayStatus.INVALID
    padded = (*bundle.spec.recording, bundle.spec.recording[-1])
    assert replay(_rebundle(bundle, recording=padded)).status is ReplayStatus.INVALID


def test_the_repaired_client_passes_the_same_fault_live() -> None:
    from arci.replay import make_bundle, replay

    env, _ = _run("fragile")
    bundle = make_bundle(mcp_manifest(), env, mcp_spec("fragile"))
    live = _rebundle(
        bundle,
        command=client("good"),
        tool_mode=ToolMode.RECORD,
        recording=(),
        replay_final_state=None,
    )
    result = replay(live)
    assert result.status is ReplayStatus.NOT_REPRODUCED
    assert result.observed_outcome is Outcome.PASS


# --- the whole loop through the gate and the CLI ------------------------------------------


def test_experiment_gate_and_cli_for_command_agents(tmp_path: Path) -> None:
    from arci.gate import decide
    from arci.runner import run_experiment

    m = mcp_manifest(n_per_arm=12)
    trials = run_experiment(m, tmp_path / "api", max_workers=6)
    d = decide(m, trials)
    assert (d.conditions[0].baseline.successes, d.conditions[0].candidate.successes) == (12, 0)
    assert d.verdict is Verdict.BLOCK

    path = tmp_path / "manifest.json"
    path.write_text(mcp_manifest(n_per_arm=6).model_dump_json())
    env = {**os.environ, "PYTHONPATH": str(REPO)}
    done = subprocess.run(
        [sys.executable, "-m", "arci.cli", "run", str(path), "--out", "runs", "--workers", "6"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert done.returncode == 2, done.stderr[-2000:]  # 6/6 vs 0/6 is INCONCLUSIVE
    assert done.stdout.strip().splitlines()[-1].startswith("VERDICT: INCONCLUSIVE")


def test_diff_and_minimise_work_on_command_trials() -> None:
    from arci.diff import first_divergence
    from arci.minimize import minimize_faults
    from tests.acceptance.helpers import COND_NOISY

    good, _ = _run("good", arm="baseline")
    broken, _ = _run("fragile")
    d = first_divergence(good, broken)
    assert d.after_injection == "tool_timeout" and d.left is not None and "fetch" in d.left

    noisy, _ = _run("fragile", condition=COND_NOISY)
    assert noisy.outcome is Outcome.FAIL
    result = minimize_faults(
        mcp_manifest(conditions=(COND_NOISY,)), noisy, mcp_spec("fragile", condition=COND_NOISY)
    )
    assert result.kept == ("tool_timeout",) and result.minimality == "1-minimal"
