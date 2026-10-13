"""The retry story in six steps, through the real CLI, from an installed wheel.

1. One illustrative run cannot tell agent A from agent B.
2. The frozen experiment BLOCKs B (exit 1) and PASSes A against itself (exit 0).
3. The paired trace diff names the first divergent step after the injected fault.
4. Fault minimisation shrinks the failing condition to the one fault that matters.
5. The exported bundle replays the failure offline.
6. The repaired agent C passes the reproducer and its own frozen experiment.

Every count is computed fresh by running the agents; nothing is read from recorded evidence.
CLI steps call ``arci.cli.main`` in-process, so no ``PYTHONPATH``, repository checkout or
``__file__`` lookup is involved: the agents are referenced as ``arci.demo.*``.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn

from arci.demo.experiment import build_manifest, clean_manifest
from arci.replay import replay
from arci.runner import run_trial
from arci.schedule import build_schedule
from arci.schema import (
    Bucket,
    Condition,
    FaultSpec,
    Manifest,
    Outcome,
    ReplayBundle,
    ReplayStatus,
    ToolMode,
)

N_PER_ARM = 200
NOISY_N_PER_ARM = 12
RECORDED_COUNTS = "A 192/200, B 132/200"
# Passes under the fault in the recorded N=200 run: (A, candidate) per step-2 experiment.
RECORDED_PASSES: dict[str, tuple[int, int]] = {"agent_b": (192, 132), "agent_a": (192, 192)}


class StepFailed(Exception):
    """A demo expectation did not hold; the message is the failed expectation."""


@dataclass(frozen=True)
class CliResult:
    code: int
    stdout: str
    stderr: str

    @property
    def last_line(self) -> str:
        lines = [line for line in self.stdout.splitlines() if line.strip()]
        if lines:
            return lines[-1].strip()
        detail = self.stderr.strip().splitlines()
        return detail[-1] if detail else f"(no output, exit {self.code})"


def default_workers() -> int:
    return min(8, os.cpu_count() or 4)


def arci(*args: str) -> CliResult:
    """Run one ``arci`` command in-process and capture what it prints."""
    # Deferred: arci.cli imports this module to register the demo subcommand.
    from arci.cli import main

    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = main(list(args))
    return CliResult(code=code, stdout=stdout.getvalue(), stderr=stderr.getvalue())


def step(number: int, title: str) -> None:
    print(f"\n=== {number}. {title}", flush=True)


def expect(condition: bool, message: str) -> None:
    print(("  ok   " if condition else "  FAIL ") + message, flush=True)
    if not condition:
        raise StepFailed(message)


def fail(message: str) -> NoReturn:
    expect(False, message)
    raise StepFailed(message)


def indented(text: str) -> str:
    return "  " + text.strip().replace("\n", "\n  ")


def check_keep(keep: Path) -> None:
    """Refuse a ``--keep`` path that is a file or a non-empty directory."""
    if keep.exists() and (not keep.is_dir() or any(keep.iterdir())):
        raise ValueError(f"--keep must name an empty or new directory: {keep}")


def with_noise(manifest: Manifest) -> Manifest:
    """The same experiment plus two irrelevant injected faults, for the minimiser to remove."""
    (condition,) = manifest.conditions
    noise = (
        FaultSpec(name="empty_result", bucket=Bucket.BENIGN, tool="get_stock", at_occurrence=6),
        FaultSpec(name="tool_error_once", bucket=Bucket.FALSIFY, tool="confirm", at_occurrence=9),
    )
    noisy = Condition(condition_id=condition.condition_id, faults=(*noise, *condition.faults))
    data = manifest.model_dump(exclude={"record_sha256"})
    return Manifest.create(
        **{
            **data,
            "experiment_id": f"{manifest.experiment_id}-noisy",
            "conditions": (noisy,),
            "n_per_arm": NOISY_N_PER_ARM,
        }
    )


def _write_manifest(work: Path, name: str, manifest: Manifest) -> Path:
    path = work / f"manifest-{name}.json"
    path.write_text(manifest.model_dump_json(), encoding="utf-8")
    return path


def _run(work: Path, manifest_path: Path, workers: int) -> CliResult:
    return arci("run", str(manifest_path), "--out", str(work / "runs"), "--workers", str(workers))


def _trials(run_dir: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in (run_dir / "trials.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _candidate_passes(run_dir: Path) -> tuple[int, int]:
    counts = {"baseline": 0, "candidate": 0}
    for trial in _trials(run_dir):
        if trial["outcome"] == "PASS":
            counts[trial["arm"]] += 1
    return counts["baseline"], counts["candidate"]


def illustrative_run() -> None:
    """Step 1: one clean pair passes on both arms."""
    step(1, "One illustrative run: A and B look the same")
    clean = clean_manifest(candidate="agent_b")
    outcomes = [
        run_trial(spec, lambda _event: None, clean.contract).outcome
        for spec in build_schedule(clean)
    ]
    expect(
        outcomes == [Outcome.PASS, Outcome.PASS],
        f"pass@1, no fault: A={outcomes[0]} B={outcomes[1]}",
    )


def recorded_comparison(candidate: str, counts: tuple[int, int] | None) -> tuple[bool, str]:
    """Compare fresh step-2 passes with the recorded run; the line says which, never fails."""
    baseline, passed = RECORDED_PASSES[candidate]
    recorded = f"A {baseline}/{N_PER_ARM}, {candidate} {passed}/{N_PER_ARM}"
    if counts == (baseline, passed):
        return True, f"  matches the recorded run ({recorded})"
    return False, f"  differs from the recorded run (recorded {recorded})"


def frozen_experiment(work: Path, workers: int, n_per_arm: int = N_PER_ARM) -> bool:
    """Step 2: A vs B BLOCKs, A vs A PASSes; True when both counts match the recorded run.

    A count that differs from the recorded run is reported, not failed: the verdict
    expectations decide whether the step holds.
    """
    step(2, f"The frozen experiment, N={n_per_arm} per arm, fault: tool_timeout on reserve")
    verdicts: dict[str, int] = {}
    matched = True
    for candidate in ("agent_b", "agent_a"):
        manifest = build_manifest(n_per_arm=n_per_arm, candidate=candidate)
        done = _run(work, _write_manifest(work, candidate, manifest), workers)
        verdicts[candidate] = done.code
        print(f"  {done.last_line}   [A vs {candidate}]", flush=True)
        counts: tuple[int, int] | None = None
        if done.code in (0, 1):
            counts = _candidate_passes(work / "runs" / manifest.experiment_id)
            print(
                f"  passed under the fault: A {counts[0]}/{n_per_arm}, "
                f"{candidate} {counts[1]}/{n_per_arm}",
                flush=True,
            )
        same, line = recorded_comparison(candidate, counts)
        matched = matched and same
        print(line, flush=True)
    expect(verdicts["agent_b"] == 1, "A vs B is BLOCKED (exit 1)")
    expect(verdicts["agent_a"] == 0, "A vs A PASSES (exit 0)")
    return matched


def _pair_index(pair_id: str) -> int:
    return int(pair_id.rsplit(":", 1)[1])


def failing_trial(run_dir: Path) -> str | None:
    """The candidate FAIL whose paired baseline PASSes, with the smallest pair index.

    Chosen by pair index, not by row order: trials.jsonl is written in completion order,
    which varies with the worker count and the scheduler.
    """
    trials = _trials(run_dir)
    by_id = {trial["trial_id"]: trial for trial in trials}
    candidates = [
        trial
        for trial in trials
        if trial["arm"] == "candidate"
        and trial["outcome"] == "FAIL"
        and by_id.get(trial["pair_id"] + ":baseline", {}).get("outcome") == "PASS"
    ]
    if not candidates:
        return None
    return str(min(candidates, key=lambda trial: _pair_index(trial["pair_id"]))["trial_id"])


def first_divergence(work: Path, workers: int) -> tuple[Path, str]:
    """Step 3: run the noisy 12-pair experiment and diff a passing and a failing trial."""
    step(3, "Where do a passing and a failing run part ways?")
    noisy = with_noise(build_manifest(n_per_arm=N_PER_ARM, candidate="agent_b"))
    done = _run(work, _write_manifest(work, "noisy", noisy), workers)
    if done.code not in (0, 1, 2):
        fail(f"the noisy run did not complete: {done.last_line}")
    run_dir = work / "runs" / noisy.experiment_id
    failing = failing_trial(run_dir)
    if failing is None:
        fail("no pair where A passes and B fails")
    passing = failing.rsplit(":", 1)[0] + ":baseline"
    diffed = arci("diff", str(run_dir), passing, failing)
    print(indented(diffed.stdout or diffed.stderr), flush=True)
    expect(
        diffed.code == 0 and "tool_timeout" in diffed.stdout,
        "the divergence sits right after the injected tool_timeout",
    )
    return run_dir, failing


def shrink(work: Path, run_dir: Path, failing: str) -> ReplayBundle:
    """Step 4: minimise the failing trial's three faults to the one that matters."""
    step(4, "Shrink the failing condition (3 injected faults)")
    bundle_path = work / "min.json"
    shrunk = arci("minimize", str(run_dir), failing, "--out", str(bundle_path))
    print(indented(shrunk.stdout or shrunk.stderr), flush=True)
    if shrunk.code != 0 or not bundle_path.exists():
        fail(f"the minimiser wrote no bundle (exit {shrunk.code})")
    reduced = ReplayBundle.model_validate_json(bundle_path.read_text(encoding="utf-8"))
    kept = [fault.name for fault in reduced.spec.condition.faults]
    expect(
        kept == ["tool_timeout"] and reduced.minimality == "1-minimal",
        f"1-minimal reproducer keeps only {kept}",
    )
    return reduced


def replay_offline(work: Path) -> None:
    """Step 5: replay the reduced bundle from its recording."""
    step(5, "Replay the reduced bundle offline")
    replayed = arci("replay", str(work / "min.json"))
    print(f"  {replayed.last_line}", flush=True)
    expect(replayed.code == 0, "REPRODUCED from the recording, no live tools")


def repaired_reproducer(reduced: ReplayBundle) -> None:
    """Step 6, first half: agent C runs the exact reproducer live and passes."""
    repaired_agent = build_manifest(n_per_arm=N_PER_ARM, candidate="agent_c").candidate.agent
    data = reduced.model_dump(exclude={"record_sha256"})
    live = reduced.spec.model_copy(
        update={
            "agent": repaired_agent,
            "tool_mode": ToolMode.RECORD,
            "recording": (),
            "replay_final_state": None,
        }
    )
    result = replay(ReplayBundle.create(**{**data, "spec": live}))
    expect(
        result.status is ReplayStatus.NOT_REPRODUCED and result.observed_outcome is Outcome.PASS,
        "C passes the exact reproducer that B fails",
    )


def repaired_experiment(work: Path, workers: int, n_per_arm: int = N_PER_ARM) -> None:
    """Step 6, second half: A vs C PASSes its own frozen experiment."""
    manifest_c = build_manifest(n_per_arm=n_per_arm, candidate="agent_c")
    done = _run(work, _write_manifest(work, "agent_c", manifest_c), workers)
    print(f"  {done.last_line}   [A vs agent_c]", flush=True)
    expect(done.code == 0, "A vs C PASSES its own separately frozen experiment (exit 0)")


def run_demo(*, workers: int | None = None, keep: Path | None = None) -> int:
    """Run all six steps; 0 when every step holds, 1 when one fails."""
    workers = default_workers() if workers is None else workers
    if workers < 1:
        raise ValueError("workers must be at least 1")
    if keep is None:
        work = Path(tempfile.mkdtemp(prefix="arci-demo-"))
    else:
        check_keep(keep)
        keep.mkdir(parents=True, exist_ok=True)
        work = keep.resolve()
    print(f"arci demo: the retry story, {workers} workers, run stores in {work}", flush=True)
    try:
        illustrative_run()
        matched = frozen_experiment(work, workers)
        run_dir, failing = first_divergence(work, workers)
        reduced = shrink(work, run_dir, failing)
        replay_offline(work)
        step(6, "The repair: agent C")
        repaired_reproducer(reduced)
        repaired_experiment(work, workers)
    except StepFailed as failed:
        print(f"\nA step did not hold: {failed}. Run stores: {work}", flush=True)
        return 1
    print("\nAll six steps held.", flush=True)
    print(final_line(work, matched=matched), flush=True)
    return 0


def final_line(work: Path, *, matched: bool) -> str:
    comparison = (
        f"they matched the recorded run ({RECORDED_COUNTS})"
        if matched
        else "they did not all match the recorded run (see step 2)"
    )
    return (
        f"Run stores: {work}. Every count above was computed fresh on this machine, "
        f"not replayed from evidence; {comparison}."
    )
