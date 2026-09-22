"""Run the six-step Jev triage regression story through the real CLI."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from arci.replay import replay  # noqa: E402
from arci.runner import run_trial  # noqa: E402
from arci.schedule import build_schedule  # noqa: E402
from arci.schema import Outcome, ReplayBundle, ReplayStatus, ToolMode  # noqa: E402
from examples.jev_triage_agent.experiment import (  # noqa: E402
    build_manifest,
    clean_manifest,
    noisy_manifest,
)

ENV = {**os.environ, "PYTHONPATH": str(REPO)}


def arci(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "arci.cli", *args],
        cwd=cwd,
        env=ENV,
        capture_output=True,
        text=True,
        check=False,
    )


def step(number: int, title: str) -> None:
    print(f"\n=== {number}. {title}")


def expect(condition: bool, message: str) -> None:
    print(("  ok   " if condition else "  FAIL ") + message)
    if not condition:
        raise SystemExit(1)


def _last_line(result: subprocess.CompletedProcess[str]) -> str:
    lines = result.stdout.strip().splitlines()
    return lines[-1] if lines else result.stderr.strip().splitlines()[-1]


def main() -> int:
    parser = argparse.ArgumentParser(description="The Jev triage reliability story.")
    parser.add_argument("--n", type=int, default=50, help="trials per arm (default 50)")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--keep", type=Path, default=None)
    args = parser.parse_args()
    work = args.keep or Path(tempfile.mkdtemp(prefix="arci-jev-hero-"))
    work.mkdir(parents=True, exist_ok=True)

    step(1, "One clean pair: A and B both act correctly")
    clean = clean_manifest("b")
    clean_outcomes = [
        run_trial(spec, lambda _event: None, clean.contract).outcome
        for spec in build_schedule(clean)
    ]
    expect(clean_outcomes == [Outcome.PASS, Outcome.PASS], "clean A and B both PASS")

    step(2, f"Frozen low-confidence experiment, N={args.n} per arm")
    results: dict[str, subprocess.CompletedProcess[str]] = {}
    for candidate in ("b", "a"):
        manifest = build_manifest(n_per_arm=args.n, candidate=candidate)
        path = work / f"manifest-{candidate}.json"
        path.write_text(manifest.model_dump_json(), encoding="utf-8")
        result = arci(
            "run",
            str(path),
            "--out",
            str(work / "runs"),
            "--workers",
            str(args.workers),
            cwd=work,
        )
        results[candidate] = result
        print(f"  {_last_line(result)}   [A vs {candidate.upper()}]")
    expect(results["b"].returncode == 1, "A vs B BLOCKS (exit 1)")
    expect(results["a"].returncode == 0, "A vs A PASSES (exit 0)")

    step(3, "Diff a passing A trial against its failing B pair")
    manifest_b = build_manifest(n_per_arm=args.n, candidate="b")
    run_dir = work / "runs" / manifest_b.experiment_id
    trials = [json.loads(line) for line in (run_dir / "trials.jsonl").read_text().splitlines()]
    by_id = {trial["trial_id"]: trial for trial in trials}
    failing = next(
        trial["trial_id"]
        for trial in trials
        if trial["arm"] == "candidate"
        and trial["outcome"] == "FAIL"
        and by_id[trial["pair_id"] + ":baseline"]["outcome"] == "PASS"
    )
    passing = failing.rsplit(":", 1)[0] + ":baseline"
    diffed = arci("diff", str(run_dir), passing, failing, cwd=work)
    print("  " + diffed.stdout.strip().replace("\n", "\n  "))
    expect(
        diffed.returncode == 0 and "decision_low_confidence" in diffed.stdout,
        "the divergence follows the injected low-confidence decision",
    )

    step(4, "Minimise a noisy failing condition")
    noisy = noisy_manifest("b")
    noisy_path = work / "manifest-noisy.json"
    noisy_path.write_text(noisy.model_dump_json(), encoding="utf-8")
    noisy_run = arci(
        "run",
        str(noisy_path),
        "--out",
        str(work / "runs"),
        "--workers",
        str(args.workers),
        cwd=work,
    )
    expect(noisy_run.returncode == 2, "single-pair noisy experiment is INCONCLUSIVE (exit 2)")
    noisy_dir = work / "runs" / noisy.experiment_id
    noisy_trials = [
        json.loads(line) for line in (noisy_dir / "trials.jsonl").read_text().splitlines()
    ]
    noisy_failing = next(
        trial["trial_id"]
        for trial in noisy_trials
        if trial["arm"] == "candidate" and trial["outcome"] == "FAIL"
    )
    minimised = arci(
        "minimize",
        str(noisy_dir),
        noisy_failing,
        "--out",
        str(work / "min.json"),
        cwd=work,
    )
    print("  " + minimised.stdout.strip().replace("\n", "\n  "))
    expect(minimised.returncode == 0, "minimise exits 0")
    reduced = ReplayBundle.model_validate_json((work / "min.json").read_text(encoding="utf-8"))
    kept = [fault.name for fault in reduced.spec.condition.faults]
    expect(
        kept == ["decision_low_confidence"] and reduced.minimality == "1-minimal",
        "1-minimal reproducer removes the benign reply fault",
    )

    step(5, "Replay the reduced failure offline")
    replayed = arci("replay", str(work / "min.json"), cwd=work)
    print("  " + _last_line(replayed))
    expect(replayed.returncode == 0, "B is REPRODUCED without a live decision provider")

    step(6, "Repair C restores escalation")
    repaired_command = build_manifest(n_per_arm=1, candidate="c").candidate.command
    live_spec = reduced.spec.model_copy(
        update={
            "variant": "c",
            "command": repaired_command,
            "tool_mode": ToolMode.RECORD,
            "recording": (),
            "replay_final_state": None,
        }
    )
    bundle_data = reduced.model_dump(exclude={"record_sha256"})
    live_result = replay(ReplayBundle.create(**{**bundle_data, "spec": live_spec}))
    expect(
        live_result.status is ReplayStatus.NOT_REPRODUCED
        and live_result.observed_outcome is Outcome.PASS,
        "C passes B's exact low-confidence reproducer live",
    )
    manifest_c = build_manifest(n_per_arm=args.n, candidate="c")
    path_c = work / "manifest-c.json"
    path_c.write_text(manifest_c.model_dump_json(), encoding="utf-8")
    c_run = arci(
        "run",
        str(path_c),
        "--out",
        str(work / "runs"),
        "--workers",
        str(args.workers),
        cwd=work,
    )
    print(f"  {_last_line(c_run)}   [A vs C]")
    expect(c_run.returncode == 0, "A vs C PASSES (exit 0)")

    print(
        '\nReal Jev: set DecisionSpec(upstream="http") and put TYPESAFE_API_KEY '
        "in the harness environment."
    )
    print(f"Run stores: {work}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
