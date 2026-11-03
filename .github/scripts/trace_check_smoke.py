"""Exercise installed trace-check using the packaged demo's preserved native stores.

Run with the installed Python -P, outside the checkout and with PYTHONPATH cleared.
Only the standard library and the installed arci package are imported; no checkout
tests, helpers, agents, or fixture modules participate.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import arci

TOP_KEYS = {
    "schema_version",
    "status",
    "reason",
    "baseline",
    "candidate",
    "first_difference",
    "limitations",
}
SOURCE_KEYS = {
    "experiment_id",
    "trial_id",
    "manifest_sha256",
    "trial_sha256",
    "decision_sha256",
    "trial_outcome",
    "gate_verdict",
    "gate_exit_code",
}
DIFFERENCE_KEYS = {
    "step",
    "path",
    "baseline_kind",
    "candidate_kind",
    "baseline_sha256",
    "candidate_sha256",
}


def _read_object(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _trials(run: Path) -> list[dict[str, Any]]:
    return [
        cast(dict[str, Any], json.loads(line))
        for line in (run / "trials.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _snapshot(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*")
        if path.is_file()
    }


def _sha256(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _check(
    baseline_run: Path,
    baseline: dict[str, Any],
    candidate_run: Path,
    candidate: dict[str, Any],
    *,
    status: str,
    exit_code: int,
    env: dict[str, str],
    candidate_id: str | None = None,
) -> dict[str, Any]:
    done = subprocess.run(
        [
            sys.executable,
            "-P",
            "-m",
            "arci",
            "trace-check",
            str(baseline_run),
            baseline["trial_id"],
            str(candidate_run),
            candidate["trial_id"] if candidate_id is None else candidate_id,
            "--format",
            "json",
        ],
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert done.returncode == exit_code, (status, done.returncode, done.stderr, done.stdout)
    assert done.stderr == "", done.stderr
    document = cast(dict[str, Any], json.loads(done.stdout))
    assert set(document) == TOP_KEYS, document
    assert document["schema_version"] == "arci-trace-check/1"
    assert document["status"] == status, document
    assert isinstance(document["reason"], str)
    assert isinstance(document["limitations"], list)
    # The exact allowlists prohibit serialized events, arguments, tool values,
    # recordings, final state, raw exceptions, and other unbounded payload dumps.
    for name, trial, run in (
        ("baseline", baseline, baseline_run),
        ("candidate", candidate, candidate_run),
    ):
        source = document[name]
        if source is None:
            assert status == "INVALID"
            continue
        assert set(source) == SOURCE_KEYS, source
        assert source["trial_id"] == trial["trial_id"]
        assert source["trial_sha256"] == trial["record_sha256"]
        assert source["manifest_sha256"] == _read_object(run / "manifest.json")["record_sha256"]
        decision = _read_object(run / "decision.json")
        assert source["decision_sha256"] == decision["record_sha256"]
        assert source["gate_verdict"] == decision["verdict"]
        assert source["gate_exit_code"] == decision["exit_code"]
        for key in ("manifest_sha256", "trial_sha256", "decision_sha256"):
            assert _sha256(source[key])
        assert source["trial_outcome"] == trial["outcome"]
    difference = document["first_difference"]
    if status == "DRIFT":
        assert set(difference) == DIFFERENCE_KEYS, difference
        assert isinstance(difference["step"], int) and difference["step"] >= 0
        assert isinstance(difference["path"], str)
        for key in ("baseline_sha256", "candidate_sha256"):
            assert difference[key] is None or _sha256(difference[key])
        for key in ("baseline_kind", "candidate_kind"):
            assert difference[key] in (
                None,
                "tool_start",
                "tool_finish",
                "agent_result",
                "terminal",
            )
    else:
        assert difference is None
    # These concrete demo values must never be rendered in diagnostic output.
    for raw_value in ("order-7", "widget", "missing-sensitive-trial"):
        assert raw_value not in done.stdout
    print(f"trace_check_smoke: {status}/{exit_code}")
    return document


def main() -> None:
    assert len(sys.argv) == 2, "usage: python -P trace_check_smoke.py DEMO_DIR"
    assert sys.flags.safe_path, "the smoke helper must run with -P"
    assert not os.environ.get("PYTHONPATH"), "PYTHONPATH must be cleared"
    package = Path(arci.__file__).resolve()
    assert package.is_relative_to(Path(sys.prefix).resolve()), package
    checkout = Path(__file__).resolve().parents[2]
    assert not Path.cwd().resolve().is_relative_to(checkout), "run outside the source checkout"
    demo = Path(sys.argv[1]).resolve()
    assert not demo.is_relative_to(checkout), "demo stores must be outside the checkout"
    runs: dict[str, Path] = {}
    for path in (demo / "runs").glob("*/manifest.json"):
        manifest = _read_object(path)
        if manifest["n_per_arm"] != 200 or len(manifest["conditions"][0]["faults"]) != 1:
            continue
        candidate_agent = manifest["candidate"]["agent"]
        for agent in ("agent_a", "agent_b"):
            if candidate_agent == f"arci.demo.agents:{agent}":
                assert agent not in runs, f"ambiguous demo store for {agent}"
                runs[agent] = path.parent
    assert set(runs) == {"agent_a", "agent_b"}, "missing packaged A-vs-A or A-vs-B run"
    a_trials, b_trials = _trials(runs["agent_a"]), _trials(runs["agent_b"])
    b_baselines = {trial["pair_id"]: trial for trial in b_trials if trial["arm"] == "baseline"}
    failures = sorted(
        (
            trial
            for trial in b_trials
            if trial["arm"] == "candidate"
            and trial["outcome"] == "FAIL"
            and b_baselines[trial["pair_id"]]["outcome"] == "PASS"
        ),
        key=lambda trial: trial["pair_id"],
    )
    assert failures, "demo has no passing A / failing B pair"
    b_candidate = failures[0]
    b_baseline = b_baselines[b_candidate["pair_id"]]
    a_baseline = next(
        trial
        for trial in a_trials
        if trial["arm"] == "baseline" and trial["seed"] == b_baseline["seed"]
    )
    summary = demo / "trace-check-summary-must-not-exist.md"
    assert not summary.exists()
    env = {**os.environ, "GITHUB_STEP_SUMMARY": str(summary)}
    before = _snapshot(demo)
    match = _check(
        runs["agent_a"],
        a_baseline,
        runs["agent_b"],
        b_baseline,
        status="MATCH",
        exit_code=0,
        env=env,
    )
    assert match["baseline"]["gate_verdict"] == "PASS"
    assert match["baseline"]["gate_exit_code"] == 0
    assert match["candidate"]["gate_verdict"] == "BLOCK"
    assert match["candidate"]["gate_exit_code"] == 1
    _check(
        runs["agent_a"],
        a_baseline,
        runs["agent_b"],
        b_candidate,
        status="DRIFT",
        exit_code=1,
        env=env,
    )
    _check(
        runs["agent_a"],
        a_baseline,
        runs["agent_b"],
        b_candidate,
        status="INVALID",
        exit_code=3,
        env=env,
        candidate_id="missing-sensitive-trial",
    )
    assert _snapshot(demo) == before, "trace-check modified source stores or created files"
    assert not summary.exists(), "trace-check wrote GITHUB_STEP_SUMMARY"
    print("trace_check_smoke: installed JSON contract and unchanged source hashes verified")


if __name__ == "__main__":
    main()
