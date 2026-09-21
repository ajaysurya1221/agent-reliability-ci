"""Recorder, runner and replay semantics. FROZEN. No network, no model calls."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from arci.schema import (
    Event,
    Outcome,
    ReplayStatus,
    Termination,
    ToolMode,
    TrialEnvelope,
)
from tests.acceptance.helpers import COND_CLEAN, COND_TIMEOUT, contract, manifest, spec

pytestmark = pytest.mark.acceptance


def _run(agent: str, **kw: object) -> tuple[TrialEnvelope, list[Event]]:
    from arci.runner import run_trial

    seen: list[Event] = []
    oracle = str(kw.pop("oracle", "oracle"))
    env = run_trial(spec(agent, **kw), seen.append, contract(oracle))  # pyright: ignore[reportArgumentType]
    return env, seen


def _kinds(events: tuple[Event, ...] | list[Event]) -> list[str]:
    return [e.kind for e in events]


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
    assert [e.seq for e in env.events] == list(range(len(env.events)))
    assert _kinds(seen) == _kinds(env.events)  # parent saw every event
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


def test_timeout_kills_the_worker_and_keeps_the_partial_trace() -> None:
    started = time.monotonic()
    env, seen = _run("hang_agent", condition=COND_CLEAN, max_seconds=1.0)
    assert time.monotonic() - started < 15
    assert env.outcome is Outcome.FAIL and env.termination is Termination.TIMEOUT
    assert "tool_finish" in _kinds(env.events) and "tool_finish" in _kinds(seen)
    assert env.validate_seal()


def test_hard_exit_still_yields_a_terminal_envelope() -> None:
    env, _ = _run("exit_agent", condition=COND_CLEAN)
    assert env.outcome is Outcome.FAIL and env.termination is Termination.CRASH
    assert "tool_finish" in _kinds(env.events)


def test_budget_exhaustion_is_a_failure() -> None:
    env, _ = _run("chatty_agent", condition=COND_CLEAN, max_tool_calls=5)
    assert env.outcome is Outcome.FAIL and env.termination is Termination.BUDGET
    assert env.usage.tool_calls == 5


def test_grader_error_is_error_not_fail() -> None:
    env, _ = _run("good_agent", oracle="raising_oracle")
    assert env.outcome is Outcome.ERROR and env.termination is Termination.GRADER_ERROR


def test_same_spec_gives_the_same_sealed_record() -> None:
    a, _ = _run("fragile_agent")
    b, _ = _run("fragile_agent")
    assert a.record_sha256 == b.record_sha256


def test_schedule_is_deterministic_paired_and_complete() -> None:
    from arci.runner import build_schedule

    m = manifest(n_per_arm=5, conditions=(COND_CLEAN, COND_TIMEOUT))
    schedule = build_schedule(m)
    assert schedule == build_schedule(m)
    assert len(schedule) == 2 * 2 * 5
    assert len({s.trial_id for s in schedule}) == len(schedule)
    by_pair: dict[str, list[int]] = {}
    for s in schedule:
        by_pair.setdefault(s.pair_id, []).append(s.seed)
    assert all(len(v) == 2 and v[0] == v[1] for v in by_pair.values())  # arms share the seed
    assert len({v[0] for v in by_pair.values()}) == len(by_pair)  # pairs do not


def test_experiment_writes_one_store_and_gates_end_to_end(tmp_path: Path) -> None:
    from arci.gate import decide
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
    d = decide(m, trials)
    base, cand = d.conditions[0].baseline, d.conditions[0].candidate
    assert (base.successes, cand.successes) == (6, 0)


def test_failing_trial_replays_offline_from_its_bundle() -> None:
    from arci.replay import make_bundle, replay

    env, _ = _run("fragile_agent")
    bundle = make_bundle(manifest(), env, spec("fragile_agent"))
    assert bundle.validate_seal() and bundle.spec.tool_mode is ToolMode.REPLAY
    assert bundle.expected_fingerprint == env.failure_fingerprint
    result = replay(bundle)
    assert result.status is ReplayStatus.REPRODUCED


def test_replay_miss_is_invalid_never_reproduced() -> None:
    from arci.replay import make_bundle, replay

    from arci.schema import ReplayBundle

    env, _ = _run("fragile_agent")
    bundle = make_bundle(manifest(), env, spec("fragile_agent"))
    clipped = bundle.spec.model_copy(update={"recording": bundle.spec.recording[:1]})
    data = bundle.model_dump(exclude={"record_sha256"})
    broken = ReplayBundle.create(**{**data, "spec": clipped})
    assert replay(broken).status is ReplayStatus.INVALID


def test_tampered_bundle_is_invalid() -> None:
    from arci.replay import make_bundle, replay

    env, _ = _run("fragile_agent")
    bundle = make_bundle(manifest(), env, spec("fragile_agent"))
    forged = bundle.model_copy(update={"expected_outcome": Outcome.PASS})
    assert replay(forged).status is ReplayStatus.INVALID


def test_repaired_agent_does_not_reproduce_the_failure() -> None:
    from arci.replay import make_bundle, replay

    from arci.schema import ReplayBundle

    env, _ = _run("fragile_agent")
    bundle = make_bundle(manifest(), env, spec("fragile_agent"))
    # The repaired agent retries, so it needs a second fetch the recording lacks;
    # run it live against the same seeded condition instead of the recording.
    repaired = bundle.spec.model_copy(
        update={
            "agent": "tests.acceptance.fixture_agents:good_agent",
            "tool_mode": ToolMode.RECORD,
            "recording": (),
        }
    )
    data = bundle.model_dump(exclude={"record_sha256"})
    result = replay(ReplayBundle.create(**{**data, "spec": repaired}))
    assert result.status is ReplayStatus.NOT_REPRODUCED
    assert result.observed_outcome is Outcome.PASS
