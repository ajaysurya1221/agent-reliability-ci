"""Verify installed triage against the demo stores, outside the checkout.

Only stdlib and installed ARCI participate. No recorded agent/oracle is imported.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, cast

import arci
from arci.gate import decide
from arci.schema import Outcome, Termination, TrialEnvelope
from arci.storage import ExperimentStore, load_run

TOP_KEYS = {
    "schema_version",
    "status",
    "reason",
    "exit_code",
    "gate",
    "group_counts",
    "groups",
    "selected_pairs",
    "limitations",
}
GROUP_KEYS = {
    "condition_id",
    "failure_fingerprint",
    "count",
    "hard_violation_trials",
    "is_gating",
    "condition_verdict",
    "selected_candidate_id",
}
PAIR_KEYS = {
    "candidate_trial_id",
    "baseline_trial_id",
    "candidate_outcome",
    "baseline_outcome",
    "comparison",
    "first_difference_context",
}
COMPARISON_KEYS = {
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
CONTEXT_KEYS = {"location", "event_kind", "seq", "tool", "occurrence", "value_present"}


def _snapshot(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*")
        if path.is_file()
    }


def _check(
    run: Path,
    *,
    exit_code: int,
    status: str = "OK",
    trial: str | None = None,
    env: dict[str, str],
) -> dict[str, Any]:
    args = [sys.executable, "-P", "-m", "arci", "triage", str(run), "--format", "json"]
    if trial is not None:
        args.extend(("--trial", trial))
    done = subprocess.run(args, env=env, capture_output=True, text=True, check=False, timeout=60)
    assert done.returncode == exit_code, (done.returncode, done.stderr, done.stdout)
    assert done.stderr == "", done.stderr
    document = cast(dict[str, Any], json.loads(done.stdout))
    assert set(document) == TOP_KEYS, document
    assert document["schema_version"] == "arci-triage/1"
    assert document["status"] == status
    assert document["exit_code"] == exit_code
    assert isinstance(document["reason"], str)
    assert document["limitations"] and all(
        isinstance(item, str) for item in document["limitations"]
    )
    # Concrete values in the real demo and the invalid selector must not be dumped.
    for raw in ("order-7", "widget", "missing-sensitive-trial"):
        assert raw not in done.stdout
    gate = document["gate"]
    if not run.exists():
        assert gate is None
        assert document["selected_pairs"] == []
        return document
    manifest, trials = load_run(run)
    original = decide(manifest, trials).model_dump(mode="json")
    assert gate == {**original, "decision_sha256": original["record_sha256"]}
    assert gate["manifest_sha256"] == manifest.record_sha256
    if status == "OK":
        assert gate["exit_code"] == exit_code
    else:
        assert exit_code == 3
        assert document["selected_pairs"] == []
    counts = document["group_counts"]
    assert set(counts) == {"total", "shown", "omitted"}
    assert counts["shown"] == len(document["groups"]) <= 3
    assert counts["total"] == counts["shown"] + counts["omitted"]
    by_id = {item.trial_id: item for item in trials}
    failures = Counter(
        (item.condition_id, item.failure_fingerprint)
        for item in trials
        if item.arm == "candidate" and item.outcome is Outcome.FAIL
    )
    if status == "OK" and gate["verdict"] != "ERROR":
        assert counts["total"] == len(failures)
    for group in document["groups"]:
        assert set(group) == GROUP_KEYS, group
        key = (group["condition_id"], group["failure_fingerprint"])
        assert group["count"] == failures[key]
        selected = by_id[group["selected_candidate_id"]]
        assert selected.arm == "candidate" and selected.outcome is Outcome.FAIL
        assert (selected.condition_id, selected.failure_fingerprint) == key
    for pair in document["selected_pairs"]:
        assert set(pair) == PAIR_KEYS, pair
        candidate = by_id[pair["candidate_trial_id"]]
        baseline = by_id[pair["baseline_trial_id"]]
        assert candidate.arm == "candidate" and baseline.arm == "baseline"
        assert candidate.pair_id == baseline.pair_id
        assert pair["candidate_outcome"] == candidate.outcome
        assert pair["baseline_outcome"] == baseline.outcome
        comparison = pair["comparison"]
        assert set(comparison) == COMPARISON_KEYS
        assert comparison["schema_version"] == "arci-trace-check/1"
        assert comparison["status"] in ("MATCH", "DRIFT")
        for side, record in (("baseline", baseline), ("candidate", candidate)):
            source = comparison[side]
            assert set(source) == SOURCE_KEYS
            assert source["trial_id"] == record.trial_id
            assert source["trial_sha256"] == record.record_sha256
            assert source["manifest_sha256"] == manifest.record_sha256
            assert source["decision_sha256"] == gate["decision_sha256"]
            assert source["gate_verdict"] == gate["verdict"]
            assert source["gate_exit_code"] == gate["exit_code"]
            assert source["trial_outcome"] == record.outcome
        difference = comparison["first_difference"]
        context = pair["first_difference_context"]
        if comparison["status"] == "MATCH":
            assert difference is None and context is None
        else:
            assert set(difference) == DIFFERENCE_KEYS
            assert set(context) == {"baseline", "candidate"}
            for side in ("baseline", "candidate"):
                location = context[side]
                assert set(location) == CONTEXT_KEYS
                assert location["location"] in ("event", "terminal", "absent")
                assert location["value_present"] == (difference[f"{side}_sha256"] is not None)
                if location["location"] == "event":
                    assert isinstance(location["seq"], int)
                if location["tool"] is not None:
                    assert isinstance(location["tool"], str)
    print(f"triage_smoke: {gate['verdict']}/{gate['exit_code']} diagnostic {status}/{exit_code}")
    return document


def main() -> None:
    assert len(sys.argv) == 2, "usage: python -P triage_smoke.py DEMO_DIR"
    assert sys.flags.safe_path, "the smoke helper must run with -P"
    assert not os.environ.get("PYTHONPATH"), "PYTHONPATH must be cleared"
    package = Path(arci.__file__).resolve()
    assert package.is_relative_to(Path(sys.prefix).resolve()), package
    checkout = Path(__file__).resolve().parents[2]
    assert not Path.cwd().resolve().is_relative_to(checkout), "run outside checkout"
    demo = Path(sys.argv[1]).resolve()
    assert not demo.is_relative_to(checkout), "demo stores must be outside checkout"
    runs: dict[str, Path] = {}
    for path in (demo / "runs").glob("*/manifest.json"):
        decision = cast(dict[str, Any], json.loads((path.parent / "decision.json").read_text()))
        runs.setdefault(decision["verdict"], path.parent)
    assert {"PASS", "BLOCK", "INCONCLUSIVE"} <= set(runs), runs
    summary = demo / "triage-summary-must-not-exist.md"
    assert not summary.exists()
    env = {**os.environ, "GITHUB_STEP_SUMMARY": str(summary)}
    before = _snapshot(demo)
    _check(runs["PASS"], exit_code=0, env=env)
    block = _check(runs["BLOCK"], exit_code=1, env=env)
    assert any(pair["comparison"]["status"] == "DRIFT" for pair in block["selected_pairs"])
    _check(runs["INCONCLUSIVE"], exit_code=2, env=env)
    manifest, trials = load_run(runs["BLOCK"])
    baseline_id = next(item.trial_id for item in trials if item.arm == "baseline")
    _check(runs["BLOCK"], trial=baseline_id, exit_code=3, status="INVALID", env=env)
    _check(runs["BLOCK"], trial="missing-sensitive-trial", exit_code=3, status="INVALID", env=env)
    # Explicit PASS selection produces a comparison but does not alter the gate.
    pass_id = next(
        item.trial_id for item in trials if item.arm == "candidate" and item.outcome is Outcome.PASS
    )
    explicit = _check(runs["BLOCK"], trial=pass_id, exit_code=1, env=env)
    assert len(explicit["selected_pairs"]) == 1
    assert explicit["selected_pairs"][0]["candidate_trial_id"] == pass_id
    # Derive a sealed harness-ERROR store from the existing demo records without execution.
    # Its original statistical ERROR/3 is distinct from an INVALID diagnostic override.
    with tempfile.TemporaryDirectory(prefix="arci-triage-smoke-") as temporary:
        root = Path(temporary)
        store = ExperimentStore(root, manifest)
        changed = False
        for item in trials:
            if not changed and item.arm == "candidate":
                payload = item.model_dump(exclude={"record_sha256"})
                payload.update(outcome=Outcome.ERROR, termination=Termination.HARNESS_ERROR)
                item = TrialEnvelope.create(**payload)
                changed = True
            store.append_trial(item)
            for event in item.events:
                store.append_event(event)
        error_before = _snapshot(root)
        error = _check(store.run_dir, exit_code=3, status="INVALID", env=env)
        assert error["gate"]["verdict"] == "ERROR"
        assert error["selected_pairs"] == []
        _check(root / "missing", exit_code=3, status="INVALID", env=env)
        assert _snapshot(root) == error_before
        # A synthetic trace difference in a passing observed candidate must retain
        # PASS/0. Keep all outcomes, specifications and statistical settings intact.
        pass_manifest, pass_trials = load_run(runs["PASS"])
        drift_store = ExperimentStore(root / "drift", pass_manifest)
        changed_id: str | None = None
        for item in pass_trials:
            if changed_id is None and item.arm == "candidate" and item.outcome is Outcome.PASS:
                events = list(item.events)
                index = next(i for i, event in enumerate(events) if event.kind == "tool_finish")
                event = events[index]
                assert event.payload["value"] is not None
                events[index] = event.model_copy(
                    update={"payload": {**event.payload, "value": None}}
                )
                payload = item.model_dump(exclude={"record_sha256"})
                payload["events"] = events
                item = TrialEnvelope.create(**payload)
                changed_id = item.trial_id
            drift_store.append_trial(item)
            for event in item.events:
                drift_store.append_event(event)
        assert changed_id is not None
        drift_before = _snapshot(root)
        drift = _check(drift_store.run_dir, trial=changed_id, exit_code=0, env=env)
        assert drift["selected_pairs"][0]["comparison"]["status"] == "DRIFT"
        assert drift["selected_pairs"][0]["candidate_outcome"] == "PASS"
        assert _snapshot(root) == drift_before
    assert _snapshot(demo) == before, "triage modified source stores or created files"
    assert not summary.exists(), "triage wrote GITHUB_STEP_SUMMARY"
    print("triage_smoke: installed JSON contract and unchanged source hashes verified")


if __name__ == "__main__":
    main()
