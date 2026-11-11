"""Persistence and interruption checks with deterministic thread synchronization."""

from __future__ import annotations

import random
import threading
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest
from pydantic import JsonValue

from arci import suite_runner, suite_storage
from arci.demo import suite
from arci.interfaces import EmitEvent
from arci.schema import ContractSpec, Event, TrialEnvelope, TrialSpec, Verdict
from arci.suite_gate import decide_suite
from arci.suite_schedule import build_suite_round
from arci.suite_stats import operating_characteristics, rule_of
from tests.unit.suite_runner.test_runner import envelope, manifest


def events_at(path: Path) -> tuple[Event, ...]:
    return tuple(Event.model_validate_json(line) for line in path.read_text().split("\n") if line)


def test_unicode_trial_roundtrip_and_events(tmp_path: Path) -> None:
    m = manifest()
    store = suite_storage.SuiteStore(tmp_path, m)
    base = envelope(build_suite_round(m, 1)[0])
    event = base.events[0].model_copy(update={"payload": {"text": "a\u2028b\u2029c\u0085d"}})
    trial = TrialEnvelope.create(
        **{**base.model_dump(exclude={"record_sha256"}), "events": (event, *base.events[1:])}
    )
    store.write_round(1, [trial], trial.events)
    assert suite_storage.load_suite_run(store.run_dir) == (m, (trial,))
    assert events_at(store.run_dir / "events.jsonl") == trial.events


def test_runner_validates_contract_before_creating_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    m = manifest(contract=ContractSpec(oracle="arci.demo.suite:oracle", unobservable=("thought",)))

    def forbidden(*args: Any, **kwargs: Any) -> TrialEnvelope:
        raise AssertionError("trial started")

    monkeypatch.setattr(suite_runner, "run_trial", forbidden)
    out = tmp_path / "runs"
    with pytest.raises(ValueError, match="outside the tool boundary"):
        suite_runner.run_suite(m, out)
    assert not out.exists()


@pytest.mark.parametrize("interruption", [KeyboardInterrupt, RuntimeError])
def test_interruption_drains_active_pairs_and_cancels_queue(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    interruption: type[BaseException],
) -> None:
    m = manifest()
    second_started = threading.Event()
    draining = threading.Event()
    seen: list[TrialSpec] = []
    lock = threading.Lock()
    schedule = build_suite_round(m, 1)
    first_pair, second_pair = schedule[0].pair_id, schedule[2].pair_id
    shutdown = suite_runner.ThreadPoolExecutor.shutdown

    def drain(self: Any, *args: Any, **kwargs: Any) -> None:
        draining.set()
        shutdown(self, *args, **kwargs)

    monkeypatch.setattr(suite_runner.ThreadPoolExecutor, "shutdown", drain)

    def run(
        spec: TrialSpec, emit: EmitEvent, contract: ContractSpec, **kwargs: Any
    ) -> TrialEnvelope:
        del contract, kwargs
        with lock:
            seen.append(spec)
        assert spec.pair_id in {first_pair, second_pair}, "queued pair started after interruption"
        if spec.pair_id == first_pair:
            assert second_started.wait(5)
            emit(Event(trial_id=spec.trial_id, seq=0, kind="trial_start"))
            raise interruption("interrupt")
        second_started.set()
        assert draining.wait(5)
        result = envelope(spec)
        for event in result.events:
            emit(event)
        return result

    monkeypatch.setattr(suite_runner, "run_trial", run)
    with pytest.raises(interruption):
        suite_runner.run_suite(m, tmp_path, workers=2)
    path = tmp_path / m.experiment_id
    _, saved = suite_storage.load_suite_run(path)
    # Both arms of the already active pair finish, even after the parent's interruption.
    assert {t.trial_id for t in saved} == {s.trial_id for s in schedule[2:4]}
    assert len(seen) == 3
    failed_id = next(s.trial_id for s in seen if s.pair_id == first_pair)
    assert events_at(path / "events.jsonl") == (
        Event(trial_id=failed_id, seq=0, kind="trial_start"),
        *(event for trial in saved for event in trial.events),
    )
    assert decide_suite(m, saved).verdict is Verdict.ERROR
    assert not (path / "decision.json").exists()


@pytest.mark.parametrize("filename", ["events.jsonl", "trials.jsonl"])
@pytest.mark.parametrize("round_number", [1, 2])
def test_interruption_while_publishing_round_keeps_every_trial(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    filename: str,
    round_number: int,
) -> None:
    m = manifest()

    def run(
        spec: TrialSpec, emit: EmitEvent, contract: ContractSpec, **kwargs: Any
    ) -> TrialEnvelope:
        del contract, kwargs
        result = envelope(spec)
        for event in result.events:
            emit(event)
        return result

    monkeypatch.setattr(suite_runner, "run_trial", run)
    replace = suite_storage.os.replace
    interrupted = False

    def interrupt(source: Any, destination: Any) -> None:
        nonlocal interrupted
        replace(source, destination)
        line_count = len(Path(destination).read_bytes().split(b"\n")) - 1
        expected_lines = 40 * round_number * (2 if filename == "events.jsonl" else 1)
        if Path(destination).name == filename and line_count == expected_lines and not interrupted:
            interrupted = True
            raise KeyboardInterrupt

    monkeypatch.setattr(suite_storage.os, "replace", interrupt)
    with pytest.raises(KeyboardInterrupt):
        suite_runner.run_suite(m, tmp_path, workers=2)
    path = tmp_path / m.experiment_id
    _, trials = suite_storage.load_suite_run(path)
    assert [t.trial_id for t in trials] == [
        s.trial_id for r in range(1, round_number + 1) for s in build_suite_round(m, r)
    ]
    assert events_at(path / "events.jsonl") == tuple(e for t in trials for e in t.events)
    assert not (path / "decision.json").exists()
    assert decide_suite(m, trials).verdict is Verdict.ERROR  # full but early inconclusive stop


@pytest.mark.parametrize(
    "candidate,minus,verdict",
    [
        ("control", Fraction(0), "p_pass"),
        ("regression", Fraction(3, 4), "p_block"),
        ("uncertain", Fraction(1, 8), "p_inconclusive"),
    ],
)
def test_fixture_exact_verdict_probability(candidate: str, minus: Fraction, verdict: str) -> None:
    m = suite.build_manifest(candidate)
    result = operating_characteristics([(minus, 1 - minus, Fraction(0))] * m.n_cells, rule_of(m))
    assert getattr(result, verdict) >= Fraction(999, 1000)


@pytest.mark.parametrize("name,successes", [("control", 7), ("regression", 1), ("uncertain", 6)])
def test_fixture_seed_controls_success(name: str, successes: int) -> None:
    class Tools:
        def __init__(self) -> None:
            self.value: JsonValue = None

        def call(self, tool: str, **arguments: JsonValue) -> JsonValue:
            assert tool == "finish"
            self.value = arguments["value"]
            return None

        def note_model_step(self, summary: str, **payload: JsonValue) -> None:
            pass

    agent = {
        "control": suite.control,
        "regression": suite.regression,
        "uncertain": suite.uncertain,
    }[name]
    outcomes: set[bool] = set()
    for seed in range(64):
        tools = Tools()
        agent({"target": 1}, tools, random.Random(seed))
        success = tools.value == 1
        assert success == (random.Random(seed).randrange(8) < successes)
        outcomes.add(success)
    assert outcomes == {False, True}


def test_store_refuses_unsealed_decision(tmp_path: Path) -> None:
    m = manifest()
    store = suite_storage.SuiteStore(tmp_path, m)
    decision = decide_suite(m, ())
    with pytest.raises(ValueError, match="seal"):
        store.write_decision(decision.model_copy(update={"record_sha256": ""}))
    assert not (store.run_dir / "decision.json").exists()
