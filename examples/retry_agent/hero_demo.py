"""The whole story in one script, through the real CLI.

    .venv/bin/python examples/retry_agent/hero_demo.py [--n 200] [--keep DIR]

1. One illustrative run cannot tell agent A from agent B.
2. The frozen experiment BLOCKs B (exit 1) and PASSes A against itself (exit 0).
3. The paired trace diff names the first divergent step after the injected fault.
4. Fault minimisation shrinks the failing condition to the one fault that matters.
5. The exported bundle replays the failure offline.
6. The repaired agent C passes the reproducer and its own frozen experiment.
"""

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
from arci.schema import (  # noqa: E402
    Bucket,
    Condition,
    FaultSpec,
    Manifest,
    Outcome,
    ReplayBundle,
    ReplayStatus,
    ToolMode,
)
from examples.retry_agent.experiment import build_manifest, clean_manifest  # noqa: E402

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
            "n_per_arm": 12,
        }
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="The agent-reliability-ci story, end to end.")
    parser.add_argument("--n", type=int, default=200, help="trials per arm (default 200)")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--keep", type=Path, default=None, help="keep run stores in this directory")
    args = parser.parse_args()
    work = args.keep or Path(tempfile.mkdtemp(prefix="arci-hero-"))
    work.mkdir(parents=True, exist_ok=True)

    step(1, "One illustrative run: A and B look the same")
    clean = clean_manifest(candidate="agent_b")
    outcomes = [
        run_trial(s, lambda _e: None, clean.contract).outcome for s in build_schedule(clean)
    ]
    expect(
        outcomes == [Outcome.PASS, Outcome.PASS],
        f"pass@1, no fault: A={outcomes[0]} B={outcomes[1]}",
    )

    step(2, f"The frozen experiment, N={args.n} per arm, fault: tool_timeout on reserve")
    verdicts: dict[str, int] = {}
    for candidate in ("agent_b", "agent_a"):
        manifest = build_manifest(n_per_arm=args.n, candidate=candidate)
        path = work / f"manifest-{candidate}.json"
        path.write_text(manifest.model_dump_json())
        done = arci(
            "run", str(path), "--out", str(work / "runs"), "--workers", str(args.workers), cwd=work
        )
        verdicts[candidate] = done.returncode
        print("  " + done.stdout.strip().splitlines()[-1] + f"   [A vs {candidate}]")
    expect(verdicts["agent_b"] == 1, "A vs B is BLOCKED (exit 1)")
    expect(verdicts["agent_a"] == 0, "A vs A PASSES (exit 0)")

    step(3, "Where do a passing and a failing run part ways?")
    noisy = with_noise(build_manifest(n_per_arm=args.n, candidate="agent_b"))
    noisy_path = work / "manifest-noisy.json"
    noisy_path.write_text(noisy.model_dump_json())
    arci(
        "run",
        str(noisy_path),
        "--out",
        str(work / "runs"),
        "--workers",
        str(args.workers),
        cwd=work,
    )
    run_dir = work / "runs" / noisy.experiment_id
    trials = [json.loads(line) for line in (run_dir / "trials.jsonl").read_text().splitlines()]
    by_id = {t["trial_id"]: t for t in trials}
    failing = next(
        t["trial_id"]
        for t in trials
        if t["arm"] == "candidate"
        and t["outcome"] == "FAIL"
        and by_id[t["pair_id"] + ":baseline"]["outcome"] == "PASS"
    )
    passing = failing.rsplit(":", 1)[0] + ":baseline"
    diffed = arci("diff", str(run_dir), passing, failing, cwd=work)
    print("  " + diffed.stdout.strip().replace("\n", "\n  "))
    expect(
        diffed.returncode == 0 and "tool_timeout" in diffed.stdout,
        "the divergence sits right after the injected tool_timeout",
    )

    step(4, "Shrink the failing condition (3 injected faults)")
    shrunk = arci("minimize", str(run_dir), failing, "--out", str(work / "min.json"), cwd=work)
    print("  " + shrunk.stdout.strip().replace("\n", "\n  "))
    reduced = ReplayBundle.model_validate_json((work / "min.json").read_text())
    kept = [f.name for f in reduced.spec.condition.faults]
    expect(
        kept == ["tool_timeout"] and reduced.minimality == "1-minimal",
        f"1-minimal reproducer keeps only {kept}",
    )

    step(5, "Replay the reduced bundle offline")
    replayed = arci("replay", str(work / "min.json"), cwd=work)
    print("  " + replayed.stdout.strip().splitlines()[-1])
    expect(replayed.returncode == 0, "REPRODUCED from the recording, no live tools")

    step(6, "The repair: agent C")
    repaired_agent = build_manifest(n_per_arm=args.n, candidate="agent_c").candidate.agent
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
    manifest_c = build_manifest(n_per_arm=args.n, candidate="agent_c")
    path_c = work / "manifest-agent_c.json"
    path_c.write_text(manifest_c.model_dump_json())
    done = arci(
        "run", str(path_c), "--out", str(work / "runs"), "--workers", str(args.workers), cwd=work
    )
    print("  " + done.stdout.strip().splitlines()[-1] + "   [A vs agent_c]")
    expect(done.returncode == 0, "A vs C PASSES its own separately frozen experiment (exit 0)")

    print(f"\nAll six steps held. Run stores: {work}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
