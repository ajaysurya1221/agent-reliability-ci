"""Pair scheduling, complete-round looks and append-only suite stores."""

from __future__ import annotations

import importlib
import importlib.util
import threading
from pathlib import Path
from typing import Any

import pytest

from arci.interfaces import EmitEvent
from arci.schedule import spec_sha256
from arci.schema import (
    ArmSpec,
    Condition,
    ContractSpec,
    Event,
    Outcome,
    Termination,
    TrialEnvelope,
    TrialSpec,
    Verdict,
    digest_payload,
)
from arci.suite_gate import decide_suite
from arci.suite_schedule import (
    arm_order,
    build_suite_schedule,
    create_suite_manifest,
    pair_round,
    suite_rule_sha256,
)
from arci.suite_schema import SuiteDecision, SuiteManifest, SuiteTask


def manifest(**updates: Any) -> SuiteManifest:
    fields: dict[str, Any] = dict(
        suite_id="runner-test",
        tasks=tuple(SuiteTask(task_id=f"t{i}") for i in range(5)),
        conditions=tuple(Condition(condition_id=f"c{i}") for i in range(4)),
        baseline=ArmSpec(label="a", agent="arci.demo.suite:control"),
        candidate=ArmSpec(label="b", agent="arci.demo.suite:control"),
        toolset="arci.demo.suite:make_world",
        contract=ContractSpec(oracle="arci.demo.suite:oracle"),
        max_rounds=4,
        max_errored_pairs=1,
        scenario_seeds="per_round",
    )
    fields.update(updates)
    return create_suite_manifest(**fields)


def envelope(spec: TrialSpec, outcome: Outcome = Outcome.PASS) -> TrialEnvelope:
    return TrialEnvelope.create(
        experiment_id=spec.experiment_id,
        spec_sha256=spec_sha256(spec),
        trial_id=spec.trial_id,
        pair_id=spec.pair_id,
        arm=spec.arm,
        variant=spec.variant,
        task_id=spec.task_id,
        condition_id=spec.condition.condition_id,
        seed=spec.seed,
        outcome=outcome,
        termination=Termination.HARNESS_ERROR
        if outcome is Outcome.ERROR
        else Termination.COMPLETED,
        events=(
            Event(trial_id=spec.trial_id, seq=0, kind="trial_start"),
            Event(trial_id=spec.trial_id, seq=1, kind="trial_end"),
        ),
    )


def module(name: str) -> Any:
    # Test the absent API as an assertion during the first red run.
    assert importlib.util.find_spec(f"arci.{name}") is not None, f"missing arci.{name}"
    return importlib.import_module(f"arci.{name}")


@pytest.mark.parametrize("change", ["seal", "wrong_id", "traversal", "absolute", "plan"])
def test_store_refuses_before_mkdir(tmp_path: Path, change: str) -> None:
    store = module("suite_storage")
    m = manifest()
    if change == "seal":
        m = m.model_copy(update={"record_sha256": "broken"})
    elif change == "plan":
        m = manifest(max_rounds=3)
    else:
        bad_id = {
            "wrong_id": "wrong@" + "0" * 64,
            "traversal": "../escape",
            "absolute": str(tmp_path.parent / "escape"),
        }[change]
        m = m.model_copy(update={"experiment_id": bad_id})
    out = tmp_path / "runs"
    with pytest.raises(ValueError):
        store.SuiteStore(out, m)
    assert not out.exists()


def test_store_layout_and_symlink_refusal(tmp_path: Path) -> None:
    api = module("suite_storage")
    m = manifest()
    store = api.SuiteStore(tmp_path / "runs", m)
    assert {p.name for p in store.run_dir.iterdir()} == {
        "manifest.json",
        "events.jsonl",
        "trials.jsonl",
    }
    assert api.load_suite_run(store.run_dir) == (m, ())
    assert api.manifest_schema_version(store.run_dir) == "arci-suite/1"
    with pytest.raises(FileExistsError):
        api.SuiteStore(tmp_path / "runs", m)
    outside = tmp_path / "outside"
    outside.mkdir()
    linked = tmp_path / "linked"
    linked.mkdir()
    (linked / m.experiment_id).symlink_to(outside, target_is_directory=True)
    with pytest.raises((ValueError, FileExistsError)):
        api.SuiteStore(linked, m)
    assert list(outside.iterdir()) == []


@pytest.mark.parametrize(
    "kind,verdict,rounds",
    [
        ("control", Verdict.PASS, 4),
        ("regression", Verdict.BLOCK, 1),
        ("uncertain", Verdict.INCONCLUSIVE, 4),
        ("one_error", Verdict.INCONCLUSIVE, 4),
        ("two_errors", Verdict.ERROR, 1),
    ],
)
def test_round_stopping_and_replay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
    verdict: Verdict,
    rounds: int,
) -> None:
    runner = module("suite_runner")
    storage = module("suite_storage")
    m = manifest()
    calls: list[str] = []
    lock = threading.Lock()

    def run(
        spec: TrialSpec, emit: EmitEvent, contract: ContractSpec, **kwargs: Any
    ) -> TrialEnvelope:
        del contract, kwargs
        outcome = Outcome.PASS
        if spec.arm == "candidate":
            if kind == "regression" or (kind == "uncertain" and spec.task_id == "t0"):
                outcome = Outcome.FAIL
            if (
                kind in {"one_error", "two_errors"}
                and pair_round(spec.pair_id) == 1
                and spec.task_id == "t0"
                and spec.condition.condition_id
                in ({"c0", "c1"} if kind == "two_errors" else {"c0"})
            ):
                outcome = Outcome.ERROR
        trial = envelope(spec, outcome)
        for event in trial.events:
            emit(event)
        with lock:
            calls.append(spec.trial_id)
        return trial

    monkeypatch.setattr(runner, "run_trial", run)
    trials = runner.run_suite(m, tmp_path, workers=2)
    stored_m, stored = storage.load_suite_run(tmp_path / m.experiment_id)
    decision = SuiteDecision.model_validate_json(
        (tmp_path / m.experiment_id / "decision.json").read_text()
    )
    from tests.unit.suite_runner.test_review_fixes import events_at

    assert events_at(tmp_path / m.experiment_id / "events.jsonl") == tuple(
        event for trial in trials for event in trial.events
    )
    assert stored_m == m and stored == trials
    assert decision == decide_suite(m, stored)
    assert decision.verdict is verdict
    assert len(trials) == 40 * rounds
    assert len(calls) == len(set(calls)) == len(trials)
    assert [t.trial_id for t in trials] == [
        s.trial_id for s in build_suite_schedule(m)[: len(trials)]
    ]
    assert all(h.verdict is Verdict.INCONCLUSIVE for h in decision.history[:-1])
    assert decision.stopped_at_round == (0 if verdict is Verdict.ERROR else rounds)


def test_pair_is_one_slot_and_store_order_is_deterministic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = module("suite_runner")
    m = manifest()
    slots: dict[int, list[str]] = {}
    lock = threading.Lock()
    # Two simultaneous pairs must reach this barrier; single-trial scheduling deadlocks
    # or interleaves the paired arms. No sleep or wall-clock assertion.
    barrier = threading.Barrier(2, timeout=10)
    count: dict[int, int] = {}

    def run(
        spec: TrialSpec, emit: EmitEvent, contract: ContractSpec, **kwargs: Any
    ) -> TrialEnvelope:
        del contract, kwargs
        slot = threading.get_ident()
        with lock:
            slots.setdefault(slot, []).append(spec.trial_id)
            count[slot] = count.get(slot, 0) + 1
            first = count[slot] % 2 == 1
        if first:
            barrier.wait()
        result = envelope(spec)
        for event in result.events:
            emit(event)
        return result

    monkeypatch.setattr(runner, "run_trial", run)
    left = runner.run_suite(m, tmp_path / "left", workers=2)
    for ids in slots.values():
        for i in range(0, len(ids), 2):
            a, b = ids[i : i + 2]
            assert a.rsplit(":", 1)[0] == b.rsplit(":", 1)[0]
            r = pair_round(a.rsplit(":", 1)[0])
            specs = build_suite_schedule(m)
            cell = next(j // 2 % 20 for j, s in enumerate(specs) if s.trial_id == a)
            assert (a.rsplit(":", 1)[1], b.rsplit(":", 1)[1]) == arm_order(
                suite_rule_sha256(m), cell, r
            )
    slots.clear()
    count.clear()
    right = runner.run_suite(m, tmp_path / "right", workers=2)
    assert [digest_payload(t) for t in left] == [digest_payload(t) for t in right]
    for name in ("trials.jsonl", "events.jsonl", "decision.json", "manifest.json"):
        assert (tmp_path / "left" / m.experiment_id / name).read_bytes() == (
            tmp_path / "right" / m.experiment_id / name
        ).read_bytes()


def test_interruption_preserves_partial_round(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = module("suite_runner")
    storage = module("suite_storage")
    m = manifest()
    completed = 0

    def run(
        spec: TrialSpec, emit: EmitEvent, contract: ContractSpec, **kwargs: Any
    ) -> TrialEnvelope:
        nonlocal completed
        del contract, kwargs
        if completed == 3:
            raise KeyboardInterrupt
        completed += 1
        result = envelope(spec)
        for event in result.events:
            emit(event)
        return result

    monkeypatch.setattr(runner, "run_trial", run)
    with pytest.raises(KeyboardInterrupt):
        runner.run_suite(m, tmp_path, workers=1)
    _, trials = storage.load_suite_run(tmp_path / m.experiment_id)
    assert len(trials) == 3
    assert decide_suite(m, trials).verdict is Verdict.ERROR
    assert not (tmp_path / m.experiment_id / "decision.json").exists()


def test_resealed_wrong_id_is_rejected(tmp_path: Path) -> None:
    store = module("suite_storage")
    m = manifest()
    wrong = SuiteManifest.create(
        **{
            **m.model_dump(exclude={"record_sha256"}),
            "experiment_id": "wrong@" + "0" * 64,
        }
    )
    assert wrong.validate_seal()
    with pytest.raises(ValueError, match="experiment_id"):
        store.SuiteStore(tmp_path / "runs", wrong)
    assert not (tmp_path / "runs").exists()


def test_invalid_plan_runs_no_trial(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runner = module("suite_runner")

    def forbidden(*args: object, **kwargs: object) -> TrialEnvelope:
        raise AssertionError("a trial started before plan validation")

    monkeypatch.setattr(runner, "run_trial", forbidden)
    with pytest.raises(ValueError):
        runner.run_suite(manifest(max_rounds=3), tmp_path / "runs", workers=2)
    assert not (tmp_path / "runs").exists()


def test_warning_is_printed_before_trials(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    runner = module("suite_runner")
    m = manifest(
        tasks=tuple(SuiteTask(task_id=f"t{i}") for i in range(20)),
        max_rounds=1,
        acknowledge_single_round=True,
    )
    warned = False

    def run(
        spec: TrialSpec, emit: EmitEvent, contract: ContractSpec, **kwargs: Any
    ) -> TrialEnvelope:
        nonlocal warned
        del contract, kwargs
        if not warned:
            assert capsys.readouterr().err == "max_rounds below 3: few looks\n"
            warned = True
        result = envelope(spec)
        for event in result.events:
            emit(event)
        return result

    monkeypatch.setattr(runner, "run_trial", run)
    runner.run_suite(m, tmp_path, workers=1)
    assert warned


def test_real_fixture_manifest_and_seed_repeatability(tmp_path: Path) -> None:
    from arci.demo.suite import build_manifest
    from arci.runner import run_trial
    from arci.schema import digest_payload
    from arci.suite_schedule import build_suite_round

    m = build_manifest()
    assert m.n_cells == 20 and m.scenario_seeds == "per_round"
    spec = build_suite_round(m, 1)[0]
    first = run_trial(spec, lambda event: None, m.contract)
    second = run_trial(spec, lambda event: None, m.contract)
    assert first.outcome is second.outcome
    assert first.outcome in {Outcome.PASS, Outcome.FAIL}
    assert digest_payload(first) == digest_payload(second)
