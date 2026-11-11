"""Independent count/wealth checks and deterministic suite rendering."""

from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path

import pytest

from arci.cli import main
from arci.schema import Event, EventKind, TrialEnvelope
from arci.suite_gate import decide_suite
from arci.suite_schema import SuiteManifest
from arci.suite_storage import SuiteStore
from tests.acceptance.suite_helpers import reference_wealth, round_trials, suite_manifest


def evidence(verdict: str) -> tuple[SuiteManifest, tuple[TrialEnvelope, ...]]:
    manifest = suite_manifest(max_rounds=4, max_errored_pairs=0, prior_runs=("earlier",))
    differences = {
        "PASS": [0] * 20,
        "BLOCK": [-1] * 20,
        "INCONCLUSIVE": [-1] * 2 + [0] * 18,
        "ERROR": [0] * 20,
    }[verdict]
    rounds = 4 if verdict in {"PASS", "INCONCLUSIVE"} else 1
    trials = tuple(
        t
        for r in range(1, rounds + 1)
        for t in round_trials(manifest, r, differences, errored=(0,) if verdict == "ERROR" else ())
    )
    return manifest, trials


def store_at(root: Path, verdict: str) -> SuiteStore:
    manifest, trials = evidence(verdict)
    store = SuiteStore(root, manifest)
    for trial in trials:
        store.append_trial(trial)
    return store


@pytest.mark.parametrize(
    "verdict,exit_code", [("PASS", 0), ("BLOCK", 1), ("INCONCLUSIVE", 2), ("ERROR", 3)]
)
def test_suite_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], verdict: str, exit_code: int
) -> None:
    from arci.suite_report import render_suite_json, render_suite_markdown

    manifest, trials = evidence(verdict)
    decision = decide_suite(manifest, trials)
    assert decision.verdict.value == verdict
    report = render_suite_markdown(manifest, decision, trials)
    document = json.loads(render_suite_json(manifest, decision, trials))
    assert document["decision"] == decision.model_dump(mode="json")
    assert document["observed_trials"] == len(trials)
    # Reconstruct cell counts directly from paired outcomes, independently of the gate.
    by_pair: dict[str, list[TrialEnvelope]] = {}
    for trial in trials:
        by_pair.setdefault(trial.pair_id, []).append(trial)
    for cell in decision.cells:
        pairs = [
            pair
            for pair in by_pair.values()
            if pair[0].task_id == cell.task_id and pair[0].condition_id == cell.condition_id
        ]
        baselines = [next(t for t in pair if t.arm == "baseline") for pair in pairs]
        candidates = [next(t for t in pair if t.arm == "candidate") for pair in pairs]
        assert cell.pairs == len(pairs)
        assert cell.baseline_successes == sum(t.outcome.value == "PASS" for t in baselines)
        assert cell.candidate_successes == sum(t.outcome.value == "PASS" for t in candidates)
        counts = {"minus": 0, "zero": 0, "plus": 0, "errored": 0}
        for a, b in zip(baselines, candidates, strict=True):
            if "ERROR" in (a.outcome.value, b.outcome.value):
                counts["errored"] += 1
            else:
                d = int(b.outcome.value == "PASS") - int(a.outcome.value == "PASS")
                counts[{-1: "minus", 0: "zero", 1: "plus"}[d]] += 1
        assert cell.counts.model_dump() == counts
        assert cell.candidate_hard_violations == sum(
            v.severity == "hard" for t in candidates if t.contract for v in t.contract.violations
        )
    assert report == render_suite_markdown(manifest, decision, tuple(reversed(trials)))
    assert report == Path(__file__).with_name(f"{verdict.lower()}.md").read_text()
    assert "descriptive" in report and "suite-mean PASS can hide a regression in one cell" in report
    assert "earlier" in report
    for row in decision.history:
        counts = row.counts
        wp = reference_wealth(
            counts.minus + counts.errored,
            counts.zero,
            counts.plus,
            Fraction(1, 20),
            Fraction(1, 10),
            (Fraction(1, 4), Fraction(1, 2)),
        )[0]
        wb = reference_wealth(
            counts.minus,
            counts.zero,
            counts.plus + counts.errored,
            Fraction(1, 20),
            Fraction(1, 10),
            (Fraction(1, 4), Fraction(1, 2)),
        )[1]
        assert row.pass_crossed == (wp >= 40)
        assert row.block_crossed == (wb >= 40)
        assert float(row.pass_wealth) == pytest.approx(float(wp), rel=0.00001)
        assert float(row.block_wealth) == pytest.approx(float(wb), rel=0.00001)
        assert row.pairs == sum((counts.minus, counts.zero, counts.plus, counts.errored))
    store = store_at(tmp_path, verdict)
    before = {p.name: p.read_bytes() for p in store.run_dir.iterdir()}
    assert main(["report", str(store.run_dir), "--format", "json"]) == exit_code
    assert json.loads(capsys.readouterr().out) == document
    assert main(["report", str(store.run_dir)]) == exit_code
    assert capsys.readouterr().out == report
    assert {p.name: p.read_bytes() for p in store.run_dir.iterdir()} == before


def test_seed_guarantee_and_invalid_history() -> None:
    from arci.suite_report import guarantee, render_suite_markdown

    statistics = " ".join(Path("docs/STATISTICS_SUITE.md").read_text().replace("**", "").split())
    for mode in ("fixed", "per_round"):
        assert guarantee(mode) in statistics
        m = suite_manifest(max_rounds=4, scenario_seeds=mode)
        trials = round_trials(m, 1, [0] * 20)[:1]
        report = render_suite_markdown(m, decide_suite(m, trials), trials)
        assert "VERDICT: ERROR (exit 3)" in report
        assert "No validated complete-round history" in report
        assert guarantee(mode) in report


def test_fault_accounting() -> None:
    from arci.report import fault_accounting, fault_markdown

    manifest, trials = evidence("BLOCK")
    selected = next(t for t in trials if t.condition_id == "fetch_timeout" and t.arm == "candidate")
    injected: list[tuple[EventKind, str]] = [
        ("tool_finish", "tool_timeout"),
        ("tool_finish", "tool_timeout"),
        ("model_step", "tool_timeout"),
        ("tool_finish", "unknown"),
    ]
    events = tuple(
        Event(trial_id=selected.trial_id, seq=i, kind=kind, payload={"injected_by": injection})
        for i, (kind, injection) in enumerate(injected)
    )
    changed = TrialEnvelope.create(
        **(selected.model_dump(exclude={"record_sha256"}) | {"events": events})
    )
    trials = tuple(changed if t == selected else t for t in trials)
    rows = fault_accounting(manifest.conditions, trials)
    row = next(r for r in rows if r["condition_id"] == "fetch_timeout" and r["arm"] == "candidate")
    assert row["injections"] == 2 and row["trials_fired"] == 1 and row["trials"] == 5
    assert row["status"] == "observed"
    baseline = next(
        r for r in rows if r["condition_id"] == "fetch_timeout" and r["arm"] == "baseline"
    )
    assert baseline["injections"] == baseline["trials_fired"] == 0
    assert baseline["status"] == "declared, never fired"
    assert "declared, never fired" in "\n".join(fault_markdown(manifest.conditions, trials))
