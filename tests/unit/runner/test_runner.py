from __future__ import annotations

import contextlib
import os
import queue
import random
import signal
import threading
import time
from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic import JsonValue

import arci.runner as runner_module
from arci.interfaces import BudgetExceeded, ToolBoxProtocol
from arci.runner import run_experiment, run_trial
from arci.schedule import spec_sha256
from arci.schema import (
    Budgets,
    ContractSpec,
    Event,
    Manifest,
    Outcome,
    Termination,
    TrialEnvelope,
    TrialSpec,
)
from tests.acceptance.helpers import COND_CLEAN, contract, manifest, spec


def model_budget_agent(
    task: dict[str, JsonValue], tools: ToolBoxProtocol, rng: random.Random
) -> dict[str, JsonValue]:
    del task, rng
    tools.note_model_step("first")
    with contextlib.suppress(BudgetExceeded):
        tools.note_model_step("over")
    tools.call("store", value=42)
    return {"success": True}


def test_same_spec_has_stable_seal() -> None:
    trial_spec = spec("fragile_agent")
    left = run_trial(trial_spec, lambda _event: None, contract())
    right = run_trial(trial_spec, lambda _event: None, contract())
    assert left.record_sha256 == right.record_sha256


def test_oracle_not_agent_claim_decides_outcome() -> None:
    trial = run_trial(spec("liar_agent", condition=COND_CLEAN), lambda _event: None, contract())
    assert trial.agent_claimed_success is True
    assert trial.outcome is Outcome.FAIL
    assert trial.termination is Termination.COMPLETED


def test_caught_model_step_budget_is_still_a_budget_failure() -> None:
    trial_spec = spec("good_agent", condition=COND_CLEAN).model_copy(
        update={
            "agent": "tests.unit.runner.test_runner:model_budget_agent",
            "budgets": Budgets(max_model_steps=1),
        }
    )
    trial = run_trial(trial_spec, lambda _event: None, contract())
    assert trial.final_state is not None and trial.final_state["stored"] == 42
    assert trial.outcome is Outcome.FAIL
    assert trial.termination is Termination.BUDGET


def test_large_grader_result_is_drained_while_process_runs() -> None:
    many = tuple(f"missing_tool_{index:04d}" for index in range(2000))
    trial = run_trial(
        spec("good_agent", condition=COND_CLEAN),
        lambda _event: None,
        contract(required_tools=many),
    )

    assert trial.contract is not None
    assert len(trial.contract.violations) == 2000
    assert trial.outcome is Outcome.FAIL
    assert trial.termination is Termination.COMPLETED


def test_protocol_reader_drains_frames_already_in_the_pipe_after_exit() -> None:
    read_fd, write_fd = os.pipe()
    stdout = os.fdopen(read_fd, "rb", buffering=0)

    class FakeProcess:
        def __init__(self) -> None:
            self.stdout = stdout

    messages: queue.Queue[tuple[str, object]] = queue.Queue(maxsize=1)
    stop = threading.Event()
    abandon = threading.Event()
    os.write(write_fd, b"first\nsecond\n")
    os.close(write_fd)
    reader = threading.Thread(
        target=vars(runner_module)["_protocol_reader"],
        args=(FakeProcess(), messages, stop, abandon),
    )
    reader.start()
    stop.set()
    seen: list[tuple[str, object]] = []

    def consume(kind: str, value: object) -> None:
        seen.append((kind, value))

    drain = vars(runner_module)["_drain_after_exit"]
    drain(reader, messages, consume)
    stdout.close()

    assert [value for kind, value in seen if kind == "line"] == [b"first", b"second"]
    assert seen[-1] == ("reader_done", None)


def test_protocol_reader_keeps_frames_when_the_queue_backs_up_during_a_drain() -> None:
    read_fd, write_fd = os.pipe()
    stdout = os.fdopen(read_fd, "rb", buffering=0)

    class FakeProcess:
        def __init__(self) -> None:
            self.stdout = stdout

    # A one-slot queue plus a consumer that starts late: the reader must block rather than
    # drop the frames it has already parsed, or a final result frame can vanish.
    messages: queue.Queue[tuple[str, object]] = queue.Queue(maxsize=1)
    stop = threading.Event()
    abandon = threading.Event()
    lines = [f"line-{index}".encode() for index in range(64)]
    os.write(write_fd, b"".join(line + b"\n" for line in lines))
    os.close(write_fd)
    reader = threading.Thread(
        target=vars(runner_module)["_protocol_reader"],
        args=(FakeProcess(), messages, stop, abandon),
    )
    reader.start()
    stop.set()
    time.sleep(0.3)
    seen: list[tuple[str, object]] = []

    def consume(kind: str, value: object) -> None:
        seen.append((kind, value))

    drain = vars(runner_module)["_drain_after_exit"]
    drain(reader, messages, consume)
    stdout.close()

    assert [value for kind, value in seen if kind == "line"] == lines


def test_boundary_exit_is_abnormal_only_when_it_was_not_the_parents_own_stop() -> None:
    abnormal = vars(runner_module)["_boundary_exit_abnormal"]

    # Clean exit with the final frame in hand.
    assert not abnormal(alive_at_deadline=False, exit_code=0, stop_signal=None, has_result=True)
    # Killed by the stop signal the parent itself sent, AFTER the final frame was written
    # and drained: the parent's own doing, not an abnormal boundary exit.
    assert not abnormal(
        alive_at_deadline=False,
        exit_code=-signal.SIGTERM,
        stop_signal=int(signal.SIGTERM),
        has_result=True,
    )
    # Same status, but the parent never asked it to stop: a real fault.
    assert abnormal(
        alive_at_deadline=False, exit_code=-signal.SIGTERM, stop_signal=None, has_result=True
    )
    # Stopped by the parent but no final frame ever arrived: still a fault.
    assert abnormal(
        alive_at_deadline=False,
        exit_code=-signal.SIGTERM,
        stop_signal=int(signal.SIGTERM),
        has_result=False,
    )
    # Some other non-zero status is a fault even when a stop was requested.
    assert abnormal(
        alive_at_deadline=False, exit_code=3, stop_signal=int(signal.SIGTERM), has_result=True
    )
    # Still running when the deadline passed: the timeout path owns this, not the fault path.
    assert not abnormal(alive_at_deadline=True, exit_code=-9, stop_signal=None, has_result=False)
    assert not abnormal(alive_at_deadline=False, exit_code=None, stop_signal=None, has_result=False)


def test_run_experiment_submits_only_the_first_decisive_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = manifest(n_per_arm=48).model_dump(exclude={"record_sha256"})
    experiment = Manifest.create(**{**data, "looks": (12, 24, 48)})
    seen: list[int] = []

    def fake_run_trial(
        trial_spec: TrialSpec,
        _emit: Callable[[Event], None],
        _contract: ContractSpec,
    ) -> TrialEnvelope:
        seen.append(int(trial_spec.pair_id.rsplit(":", 1)[1]))
        passed = trial_spec.arm == "baseline"
        return TrialEnvelope.create(
            spec_sha256=spec_sha256(trial_spec),
            experiment_id=trial_spec.experiment_id,
            trial_id=trial_spec.trial_id,
            pair_id=trial_spec.pair_id,
            arm=trial_spec.arm,
            variant=trial_spec.variant,
            task_id=trial_spec.task_id,
            condition_id=trial_spec.condition.condition_id,
            seed=trial_spec.seed,
            outcome=Outcome.PASS if passed else Outcome.FAIL,
            termination=Termination.COMPLETED,
            failure_fingerprint=None if passed else "f" * 64,
        )

    monkeypatch.setattr(runner_module, "run_trial", fake_run_trial)
    trials = run_experiment(experiment, tmp_path, max_workers=4)

    assert len(trials) == 24
    assert set(seen) == set(range(12))
