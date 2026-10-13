"""`arci demo`: the packaged retry story, its manifests, its isolation and its CLI edges.

The full N=200 demo is not run here (CI time); the step logic is exercised with the
12-pair noisy run, and the orchestrator runs the whole demo from a built wheel.
"""

from __future__ import annotations

import json
import random
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

import arci.demo.agents as demo_agents
import arci.demo.run as demo_run
import arci.demo.world as demo_world
import examples.retry_agent.agents as example_agents
import examples.retry_agent.world as example_world
from arci.cli import main
from arci.demo.experiment import build_manifest, clean_manifest
from arci.schedule import build_schedule
from examples.retry_agent import experiment as example_experiment

CANDIDATES = ("agent_a", "agent_b", "agent_c")


@pytest.mark.parametrize("candidate", CANDIDATES)
def test_demo_manifest_is_the_example_experiment_with_its_own_refs_and_seal(
    candidate: str,
) -> None:
    demo = build_manifest(n_per_arm=200, candidate=candidate)
    example = example_experiment.build_manifest(n_per_arm=200, candidate=candidate)

    assert demo.validate_seal()
    assert demo.experiment_id == f"arci-demo-{candidate}-reserve-timeout-200"
    assert demo.toolset == "arci.demo.world:make_world"
    assert demo.contract.oracle == "arci.demo.world:oracle"
    assert demo.baseline.agent == "arci.demo.agents:agent_a"
    assert demo.baseline.candidate_id == "baseline-a"
    assert demo.candidate.agent == f"arci.demo.agents:{candidate}"
    assert demo.candidate.candidate_id == f"candidate-{candidate}"
    assert demo.baseline.label == example.baseline.label
    assert demo.candidate.label == example.candidate.label
    assert demo.task_id == example.task_id
    assert demo.task == example.task
    assert demo.conditions == example.conditions
    assert demo.budgets == example.budgets
    assert (
        (demo.base_seed, demo.n_per_arm) == (example.base_seed, example.n_per_arm) == (12_000, 200)
    )
    assert [spec.seed for spec in build_schedule(demo)] == [
        spec.seed for spec in build_schedule(example)
    ]
    assert demo.record_sha256 != example.record_sha256


def test_demo_clean_manifest_matches_the_example_clean_pair() -> None:
    demo = clean_manifest(candidate="agent_b")
    example = example_experiment.clean_manifest(candidate="agent_b")

    assert demo.validate_seal()
    assert demo.experiment_id == "arci-demo-agent_b-clean-1"
    assert demo.conditions == example.conditions
    assert demo.task == example.task
    assert demo.n_per_arm == 1
    assert demo.record_sha256 != example.record_sha256


def test_unknown_candidate_is_refused() -> None:
    with pytest.raises(ValueError, match="unknown candidate"):
        build_manifest(candidate="agent_z")


def test_example_modules_reexport_the_packaged_objects() -> None:
    assert example_world.make_world is demo_world.make_world
    assert example_world.oracle is demo_world.oracle
    assert example_world.scenario_for_seed is demo_world.scenario_for_seed
    assert example_world.InventoryWorld is demo_world.InventoryWorld
    assert example_world.Scenario is demo_world.Scenario
    assert example_world.PREEXISTING_RESERVATION_SHARE == demo_world.PREEXISTING_RESERVATION_SHARE
    assert example_world.FLAKY_CONFIRM_SHARE == demo_world.FLAKY_CONFIRM_SHARE
    assert example_world.CONFIRM_TRANSIENT_FAILURES == demo_world.CONFIRM_TRANSIENT_FAILURES
    assert example_agents.agent_a is demo_agents.agent_a
    assert example_agents.agent_b is demo_agents.agent_b
    assert example_agents.agent_c is demo_agents.agent_c


def test_importing_the_demo_and_cli_loads_no_examples_bench_or_tests() -> None:
    script = textwrap.dedent(
        """
        import sys
        import arci.cli
        import arci.demo
        import arci.demo.agents
        import arci.demo.experiment
        import arci.demo.run
        import arci.demo.world
        roots = ("examples", "bench", "tests")
        loaded = sorted(
            m for m in sys.modules if any(m == r or m.startswith(r + ".") for r in roots)
        )
        assert not loaded, loaded
        print("ok")
        """
    )
    completed = subprocess.run(
        [sys.executable, "-I", "-c", script], capture_output=True, text=True, check=False
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == "ok\n"


def test_demo_help_exits_zero_with_empty_stderr() -> None:
    completed = subprocess.run(
        [sys.executable, "-I", "-m", "arci", "demo", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0
    assert completed.stderr == ""
    assert completed.stdout.startswith("usage: arci demo")


def test_the_step_logic_holds_on_the_noisy_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Steps 1, 3, 4, 5 and the reproducer half of 6, without the N=200 runs."""
    demo_run.illustrative_run()
    run_dir, failing = demo_run.first_divergence(tmp_path, workers=4)
    assert run_dir == tmp_path / "runs" / "arci-demo-agent_b-reserve-timeout-200-noisy"
    assert failing.endswith(":candidate")
    reduced = demo_run.shrink(tmp_path, run_dir, failing)
    assert [fault.name for fault in reduced.spec.condition.faults] == ["tool_timeout"]
    assert reduced.spec.agent == "arci.demo.agents:agent_b"
    demo_run.replay_offline(tmp_path)
    demo_run.repaired_reproducer(reduced)

    out = capsys.readouterr().out
    assert "FAIL" not in out
    assert out.count("  ok   ") == 5
    assert "after_injection: tool_timeout" in out
    assert "  kept: tool_timeout\n" in out
    assert "minimality: 1-minimal" in out
    assert "REPRODUCED: failure reproduced" in out

    baseline, candidate = demo_run._candidate_passes(run_dir)  # pyright: ignore[reportPrivateUsage]
    rows = [
        json.loads(line)
        for line in (run_dir / "trials.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == 2 * demo_run.NOISY_N_PER_ARM
    assert baseline == sum(r["arm"] == "baseline" and r["outcome"] == "PASS" for r in rows)
    assert candidate == sum(r["arm"] == "candidate" and r["outcome"] == "PASS" for r in rows)
    assert 0 <= candidate < baseline <= demo_run.NOISY_N_PER_ARM


def _write_trials(run_dir: Path, rows: list[dict[str, str]]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(row) + "\n" for row in rows)
    (run_dir / "trials.jsonl").write_text(text, encoding="utf-8")


def _pair(index: int, baseline: str, candidate: str) -> list[dict[str, str]]:
    pair_id = f"reserve-timeout:{index:05d}"
    return [
        {
            "trial_id": f"{pair_id}:baseline",
            "pair_id": pair_id,
            "arm": "baseline",
            "outcome": baseline,
        },
        {
            "trial_id": f"{pair_id}:candidate",
            "pair_id": pair_id,
            "arm": "candidate",
            "outcome": candidate,
        },
    ]


def test_candidate_passes_counts_each_arm(tmp_path: Path) -> None:
    rows = [
        *_pair(0, "PASS", "PASS"),
        *_pair(1, "PASS", "FAIL"),
        *_pair(2, "FAIL", "PASS"),
        *_pair(3, "PASS", "ERROR"),
    ]
    _write_trials(tmp_path, rows)
    assert demo_run._candidate_passes(tmp_path) == (3, 2)  # pyright: ignore[reportPrivateUsage]


@pytest.mark.parametrize("seed", range(5))
def test_failing_trial_is_the_smallest_pair_index_in_any_row_order(
    tmp_path: Path, seed: int
) -> None:
    rows = [
        *_pair(0, "PASS", "PASS"),
        *_pair(1, "FAIL", "FAIL"),  # baseline fails too: not a usable pair
        *_pair(2, "PASS", "ERROR"),  # candidate errored, not FAIL
        *_pair(3, "PASS", "FAIL"),
        *_pair(7, "PASS", "FAIL"),
        *_pair(11, "PASS", "FAIL"),
    ]
    random.Random(seed).shuffle(rows)
    _write_trials(tmp_path, rows)
    assert demo_run.failing_trial(tmp_path) == "reserve-timeout:00003:candidate"


def test_failing_trial_is_none_without_an_a_pass_b_fail_pair(tmp_path: Path) -> None:
    _write_trials(tmp_path, [*_pair(0, "PASS", "PASS"), *_pair(1, "FAIL", "FAIL")])
    assert demo_run.failing_trial(tmp_path) is None


@pytest.mark.parametrize("matched", [True, False])
def test_the_last_line_names_the_store_and_the_recorded_comparison(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    matched: bool,
) -> None:
    def frozen(work: Path, workers: int) -> bool:
        return matched

    def divergence(work: Path, workers: int) -> tuple[Path, str]:
        return work / "runs" / "noisy", "reserve-timeout:00003:candidate"

    def shrunk(work: Path, run_dir: Path, failing: str) -> object:
        return object()

    def nothing(*_args: object) -> None:
        return None

    monkeypatch.setattr(demo_run, "illustrative_run", nothing)
    monkeypatch.setattr(demo_run, "frozen_experiment", frozen)
    monkeypatch.setattr(demo_run, "first_divergence", divergence)
    monkeypatch.setattr(demo_run, "shrink", shrunk)
    monkeypatch.setattr(demo_run, "replay_offline", nothing)
    monkeypatch.setattr(demo_run, "repaired_reproducer", nothing)
    monkeypatch.setattr(demo_run, "repaired_experiment", nothing)
    keep = tmp_path / "stores"

    assert demo_run.run_demo(workers=1, keep=keep) == 0
    lines = capsys.readouterr().out.splitlines()
    comparison = (
        "they matched the recorded run (A 192/200, B 132/200)."
        if matched
        else "they did not all match the recorded run (see step 2)."
    )
    assert lines[-2] == "All six steps held."
    assert lines[-1] == (
        f"Run stores: {keep.resolve()}. Every count above was computed fresh on this machine, "
        f"not replayed from evidence; {comparison}"
    )


@pytest.mark.parametrize(
    ("candidate", "counts", "line"),
    [
        ("agent_b", (192, 132), "  matches the recorded run (A 192/200, agent_b 132/200)"),
        ("agent_a", (192, 192), "  matches the recorded run (A 192/200, agent_a 192/200)"),
        (
            "agent_b",
            (191, 132),
            "  differs from the recorded run (recorded A 192/200, agent_b 132/200)",
        ),
        (
            "agent_a",
            None,
            "  differs from the recorded run (recorded A 192/200, agent_a 192/200)",
        ),
    ],
)
def test_step_two_compares_with_the_recorded_run(
    candidate: str, counts: tuple[int, int] | None, line: str
) -> None:
    assert demo_run.recorded_comparison(candidate, counts) == (line.startswith("  matches"), line)


def test_a_failed_step_exits_one_and_names_the_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def broken() -> None:
        demo_run.fail("injected for the test")

    monkeypatch.setattr(demo_run, "illustrative_run", broken)
    keep = tmp_path / "stores"

    assert main(["demo", "--keep", str(keep), "--workers", "1"]) == 1
    out = capsys.readouterr().out
    assert "  FAIL injected for the test" in out
    assert f"A step did not hold: injected for the test. Run stores: {keep.resolve()}" in out
    assert "All six steps held" not in out
    assert keep.is_dir()


@pytest.mark.parametrize("kind", ["non-empty directory", "file"])
def test_keep_refuses_an_occupied_path_with_exit_three(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], kind: str
) -> None:
    if kind == "file":
        keep = tmp_path / "taken"
        keep.write_text("mine\n", encoding="utf-8")
    else:
        keep = tmp_path / "stores"
        keep.mkdir()
        (keep / "mine.txt").write_text("mine\n", encoding="utf-8")

    assert main(["demo", "--keep", str(keep)]) == 3
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.count("\n") == 1
    assert captured.err.startswith("error: CliError: --keep must name an empty or new directory")
    assert sorted(path.name for path in tmp_path.rglob("*")) == sorted(
        ["taken"] if kind == "file" else ["stores", "mine.txt"]
    )


def test_bad_workers_is_a_cli_error() -> None:
    assert main(["demo", "--workers", "0"]) == 3
