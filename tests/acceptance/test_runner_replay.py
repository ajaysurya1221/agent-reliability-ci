"""Recorder, runner and replay semantics. FROZEN. No network, no model calls."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from arci.hashing import hash_bytes
from arci.schema import (
    Event,
    Outcome,
    ReplayBundle,
    ReplayStatus,
    Termination,
    ToolMode,
    TrialEnvelope,
)
from tests.acceptance.helpers import (
    COND_CLEAN,
    MOD,
    contract,
    manifest,
    spec,
)

pytestmark = pytest.mark.acceptance
REPO = Path(__file__).resolve().parents[2]
PAYLOAD = (
    "tests/__init__.py",
    "tests/acceptance/__init__.py",
    "tests/acceptance/fixture_agents.py",
)


def _run(agent: str, **kw: object) -> tuple[TrialEnvelope, list[Event]]:
    from arci.runner import run_trial

    seen: list[Event] = []
    oracle = str(kw.pop("oracle", "oracle"))
    env = run_trial(spec(agent, **kw), seen.append, contract(oracle))  # pyright: ignore[reportArgumentType]
    return env, seen


def _kinds(events: tuple[Event, ...] | list[Event]) -> list[str]:
    return [e.kind for e in events]


def _steps(env: TrialEnvelope) -> list[tuple[str, object]]:
    return [(e.kind, e.payload) for e in env.events]


def _rebundle(bundle: ReplayBundle, **spec_update: object) -> ReplayBundle:
    data = bundle.model_dump(exclude={"record_sha256"})
    return ReplayBundle.create(**{**data, "spec": bundle.spec.model_copy(update=spec_update)})


# --- recorder and outcome taxonomy -------------------------------------------


def test_robust_agent_passes_under_injected_timeout() -> None:
    env, seen = _run("good_agent")
    assert env.outcome is Outcome.PASS and env.termination is Termination.COMPLETED
    assert env.validate_seal() and env.failure_fingerprint is None
    injected = [
        e
        for e in env.events
        if e.kind == "tool_finish" and e.payload.get("injected_by") == "tool_timeout"
    ]
    assert len(injected) == 1 and injected[0].payload.get("ok") is False
    assert _kinds(env.events)[0] == "trial_start" and _kinds(env.events)[-1] == "trial_end"
    assert _kinds(env.events).count("trial_end") == 1
    assert [e.seq for e in env.events] == list(range(len(env.events)))
    assert _kinds(seen) == _kinds(env.events)  # the parent saw every event
    assert env.usage.tool_calls == 4  # log, fetch(injected), fetch, store
    assert env.final_state == {"stored": 42, "log": ["start"]}


def test_fragile_agent_fails_by_the_oracle_despite_claiming_success() -> None:
    env, _ = _run("fragile_agent")
    assert env.outcome is Outcome.FAIL and env.termination is Termination.COMPLETED
    assert env.agent_claimed_success is True
    assert env.contract is not None and env.contract.success is False
    assert env.failure_fingerprint is not None


def test_fragile_agent_passes_without_the_fault() -> None:
    env, _ = _run("fragile_agent", condition=COND_CLEAN)
    assert env.outcome is Outcome.PASS


def test_liar_is_failed_by_the_independent_oracle() -> None:
    env, _ = _run("liar_agent", condition=COND_CLEAN)
    assert env.outcome is Outcome.FAIL and env.agent_claimed_success is True


def test_uncaught_tool_fault_is_an_agent_failure_not_a_harness_error() -> None:
    env, _ = _run("uncaught_agent")
    assert env.outcome is Outcome.FAIL and env.termination is Termination.CRASH


def _terminated(pid: int) -> bool:
    """Gone, or a zombie awaiting reaping. Either way it is no longer running."""
    stat = subprocess.run(
        ["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True, check=False
    ).stdout.strip()
    return stat == "" or stat.startswith("Z")


def test_timeout_mid_call_keeps_the_trace_and_kills_the_whole_process_tree(
    tmp_path: Path,
) -> None:
    from arci.runner import run_trial

    pid_file, ack_file, acked_file = (tmp_path / n for n in ("pid", "ack", "acked"))

    def acknowledge(event: Event) -> None:
        # Runs in the parent. The blocked tool proceeds only once this file exists, so
        # `acked_file` can only appear if the event was delivered while the worker lived.
        if event.kind == "tool_start":
            ack_file.write_text("seen")

    blocked = spec(
        "block_agent",
        condition=COND_CLEAN,
        max_seconds=10.0,
        task={"pid_file": str(pid_file), "ack_file": str(ack_file), "acked_file": str(acked_file)},
    )
    env = run_trial(blocked, acknowledge, contract())

    assert env.outcome is Outcome.FAIL and env.termination is Termination.TIMEOUT
    assert env.validate_seal()
    assert acked_file.exists(), "tool_start was not delivered before the worker was killed"
    assert [c.tool for c in env.incomplete_calls] == ["block"]
    kinds = _kinds(env.events)
    assert "tool_start" in kinds and "tool_finish" not in kinds
    assert kinds.count("trial_end") == 1 and kinds[-1] == "trial_end"

    descendant = int(pid_file.read_text())
    deadline = time.monotonic() + 10
    while not _terminated(descendant) and time.monotonic() < deadline:
        time.sleep(0.1)
    assert _terminated(descendant), "descendant process survived the timeout"


def test_hard_exit_still_yields_a_terminal_envelope() -> None:
    env, _ = _run("exit_agent", condition=COND_CLEAN)
    assert env.outcome is Outcome.FAIL and env.termination is Termination.CRASH
    assert "tool_finish" in _kinds(env.events) and _kinds(env.events)[-1] == "trial_end"


def test_budget_exhaustion_is_a_failure() -> None:
    env, _ = _run("chatty_agent", condition=COND_CLEAN, max_tool_calls=5)
    assert env.outcome is Outcome.FAIL and env.termination is Termination.BUDGET
    assert env.usage.tool_calls == 5


@pytest.mark.parametrize("oracle", ["raising_oracle", "no_such_function"])
def test_grader_faults_are_errors_not_failures(oracle: str) -> None:
    env, _ = _run("good_agent", oracle=oracle)
    assert env.outcome is Outcome.ERROR and env.termination is Termination.GRADER_ERROR


def test_a_broken_environment_is_a_harness_error() -> None:
    env, _ = _run("good_agent", toolset="make_broken_world")
    assert env.outcome is Outcome.ERROR and env.termination is Termination.HARNESS_ERROR
    assert env.validate_seal()


def test_same_spec_gives_the_same_sealed_record() -> None:
    a, _ = _run("fragile_agent")
    b, _ = _run("fragile_agent")
    assert a.record_sha256 == b.record_sha256


def test_experiment_writes_one_store_and_gates_end_to_end(tmp_path: Path) -> None:
    from arci.runner import run_experiment

    m = manifest(n_per_arm=6)
    trials = run_experiment(m, tmp_path, max_workers=3)
    assert len(trials) == 12
    run_dir = tmp_path / m.experiment_id
    assert json.loads((run_dir / "manifest.json").read_text())["record_sha256"] == m.record_sha256
    lines = (run_dir / "trials.jsonl").read_text().splitlines()
    assert len(lines) == 12
    assert all(TrialEnvelope.model_validate_json(x).validate_seal() for x in lines)
    assert (run_dir / "events.jsonl").read_text().count("\n") >= 12 * 4
    with pytest.raises(FileExistsError):
        run_experiment(m, tmp_path, max_workers=1)  # a run directory is never reused

    from arci.gate import decide

    d = decide(m, trials)
    base, cand = d.conditions[0].baseline, d.conditions[0].candidate
    assert (base.successes, cand.successes) == (6, 0)


# --- replay ------------------------------------------------------------------


def test_replay_reproduces_a_passing_trial_without_touching_live_tools() -> None:
    from arci.runner import run_trial

    live, _ = _run("good_agent")
    sink: list[Event] = []
    replayed = run_trial(
        spec("good_agent", toolset="make_untouchable_world").model_copy(
            update={
                "tool_mode": ToolMode.REPLAY,
                "recording": live.recording,
                "replay_final_state": live.final_state,
            }
        ),
        sink.append,
        contract(),
    )
    assert replayed.outcome is Outcome.PASS
    assert replayed.final_state == live.final_state
    assert _steps(replayed) == _steps(live)


def test_unconsumed_recording_is_a_replay_mismatch() -> None:
    from arci.runner import run_trial

    live, _ = _run("good_agent")
    sink: list[Event] = []
    env = run_trial(
        spec("good_agent", toolset="make_untouchable_world").model_copy(
            update={
                "tool_mode": ToolMode.REPLAY,
                "recording": (*live.recording, live.recording[-1]),
                "replay_final_state": live.final_state,
            }
        ),
        sink.append,
        contract(),
    )
    assert env.outcome is Outcome.ERROR and env.termination is Termination.REPLAY_MISS


def test_failing_trial_replays_offline_from_its_bundle() -> None:
    from arci.replay import make_bundle, replay

    env, _ = _run("fragile_agent")
    bundle = make_bundle(manifest(), env, spec("fragile_agent"))
    assert bundle.validate_seal() and bundle.spec.tool_mode is ToolMode.REPLAY
    assert bundle.expected_fingerprint == env.failure_fingerprint
    assert bundle.spec.replay_final_state == env.final_state
    assert replay(bundle).status is ReplayStatus.REPRODUCED
    passing, _ = _run("good_agent")
    with pytest.raises(ValueError):
        make_bundle(manifest(), passing, spec("good_agent"))


@pytest.mark.parametrize("mutation", ["dropped", "tool", "arguments", "occurrence"])
def test_replay_miss_is_invalid_even_when_the_agent_swallows_it(mutation: str) -> None:
    from arci.replay import make_bundle, replay

    env, _ = _run("catchall_agent")
    assert env.outcome is Outcome.FAIL
    bundle = make_bundle(manifest(candidate="catchall_agent"), env, spec("catchall_agent"))
    assert replay(bundle).status is ReplayStatus.REPRODUCED
    first, *rest = bundle.spec.recording
    broken = {
        "dropped": (),
        "tool": (first.model_copy(update={"tool": "fetch_v2"}), *rest),
        "arguments": (first.model_copy(update={"arguments_sha256": "0" * 64}), *rest),
        "occurrence": (first.model_copy(update={"occurrence": 5}), *rest),
    }[mutation]
    assert replay(_rebundle(bundle, recording=broken)).status is ReplayStatus.INVALID


def test_tampered_bundle_is_invalid() -> None:
    from arci.replay import make_bundle, replay

    env, _ = _run("fragile_agent")
    bundle = make_bundle(manifest(), env, spec("fragile_agent"))
    forged = bundle.model_copy(update={"expected_outcome": Outcome.PASS})
    assert replay(forged).status is ReplayStatus.INVALID


def test_repaired_agent_does_not_reproduce_the_failure() -> None:
    from arci.replay import make_bundle, replay

    env, _ = _run("fragile_agent")
    bundle = make_bundle(manifest(), env, spec("fragile_agent"))
    # The repaired agent retries, so it needs calls the recording lacks: run it live
    # against the same seeded condition instead.
    live = _rebundle(
        bundle,
        agent=f"{MOD}:good_agent",
        tool_mode=ToolMode.RECORD,
        recording=(),
        replay_final_state=None,
    )
    result = replay(live)
    assert result.status is ReplayStatus.NOT_REPRODUCED
    assert result.observed_outcome is Outcome.PASS


def test_bundle_is_portable_and_runs_without_the_checkout(tmp_path: Path) -> None:
    from arci.replay import make_bundle

    env, _ = _run("fragile_agent")
    bundle = make_bundle(manifest(), env, spec("fragile_agent"), root=REPO, include=PAYLOAD)
    assert set(bundle.files) == set(PAYLOAD)
    assert bundle.fixtures == {p: hash_bytes((REPO / p).read_bytes()) for p in PAYLOAD}
    (tmp_path / "bundle.json").write_text(bundle.model_dump_json())
    code = (
        "from arci.replay import replay\n"
        "from arci.schema import ReplayBundle\n"
        "b = ReplayBundle.model_validate_json(open('bundle.json').read())\n"
        "print(replay(b).status.value)\n"
    )
    clean_env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    done = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        env=clean_env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert done.stdout.strip().splitlines()[-1:] == ["REPRODUCED"], done.stderr[-2000:]


def test_bundle_payload_is_verified_before_execution() -> None:
    import base64

    from arci.replay import make_bundle, replay

    env, _ = _run("fragile_agent")
    bundle = make_bundle(manifest(), env, spec("fragile_agent"), root=REPO, include=PAYLOAD)
    evil = base64.b64encode(b"raise SystemExit('payload swapped')\n").decode()
    data = bundle.model_dump(exclude={"record_sha256"})
    swapped = ReplayBundle.create(**{**data, "files": {**bundle.files, PAYLOAD[2]: evil}})
    assert swapped.validate_seal()  # well sealed, but the content no longer matches `fixtures`
    assert replay(swapped).status is ReplayStatus.INVALID
