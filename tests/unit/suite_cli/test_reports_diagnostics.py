"""Suite diagnostics preserve paired identity, gate exits and read-only stores."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from arci.cli import main
from arci.diff import first_divergence
from arci.schema import Event, TrialEnvelope
from tests.unit.suite_report.test_reports import store_at


def add_events(store: Path) -> tuple[TrialEnvelope, ...]:
    trials = tuple(
        TrialEnvelope.model_validate_json(line)
        for line in (store / "trials.jsonl").read_text().splitlines()
    )
    result: list[TrialEnvelope] = []
    for trial in trials:
        events = (
            Event(
                trial_id=trial.trial_id,
                seq=0,
                kind="trial_start",
                payload={"seed": trial.seed, "arm": trial.arm, "variant": trial.variant},
            ),
            Event(
                trial_id=trial.trial_id,
                seq=1,
                kind="agent_result",
                payload={"result": {"ok": trial.arm == "baseline"}},
            ),
            Event(trial_id=trial.trial_id, seq=2, kind="trial_end"),
        )
        result.append(
            TrialEnvelope.create(
                **(trial.model_dump(exclude={"record_sha256"}) | {"events": events})
            )
        )
    (store / "trials.jsonl").write_text("".join(t.model_dump_json() + "\n" for t in result))
    return tuple(result)


def test_suite_triage_and_diff(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    store = store_at(tmp_path / "left", "BLOCK")
    trials = add_events(store.run_dir)
    other = store_at(tmp_path / "right", "BLOCK")
    add_events(other.run_dir)
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    candidate = trials[-1]
    baseline = next(t for t in trials if t.pair_id == candidate.pair_id and t.arm == "baseline")
    assert (
        main(["triage", str(store.run_dir), "--trial", candidate.trial_id, "--format", "json"]) == 1
    )
    doc = json.loads(capsys.readouterr().out)
    pair = doc["selected_pairs"][0]
    assert pair["baseline_trial_id"] == baseline.trial_id
    assert pair["comparison"]["status"] == "DRIFT"
    assert pair["comparison"]["first_difference"]["path"] == "/payload/result/ok"
    assert pair["first_difference_context"]["candidate"]["seq"] == 1
    for extra in ([], ["--other-run", str(other.run_dir)]):
        assert (
            main(["diff", str(store.run_dir), baseline.trial_id, candidate.trial_id, *extra]) == 0
        )
        assert (
            f"common_prefix: {first_divergence(baseline, candidate).common_prefix}"
            in capsys.readouterr().out
        )
    assert {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()} == before


def test_suite_junit_refused(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    store = store_at(tmp_path, "PASS")
    assert main(["report", str(store.run_dir), "--format", "junit"]) == 3
    output = capsys.readouterr()
    assert output.out + output.err == "suite support for report is not built yet\n"


def test_suite_diagnostic_invalid_events_and_error_gate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store = store_at(tmp_path / "block", "BLOCK")
    # Synthetic records have no valid event frame; a statistical BLOCK cannot
    # make a malformed trace diagnosable.
    assert main(["triage", str(store.run_dir), "--for", "json"]) == 3
    doc = json.loads(capsys.readouterr().out)
    assert doc["status"] == "INVALID" and doc["selected_pairs"] == []
    store = store_at(tmp_path / "error", "ERROR")
    assert main(["triage", str(store.run_dir)]) == 3
    assert "gate is ERROR" in capsys.readouterr().out
    trials = add_events(store.run_dir)
    # Like v1 diff, this diagnostic can inspect sealed traces from an ERROR run.
    assert main(["diff", str(store.run_dir), trials[0].trial_id, trials[1].trial_id]) == 0
    assert "common_prefix:" in capsys.readouterr().out


def test_suite_triage_snapshot_change(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import arci.triage as module

    store = store_at(tmp_path, "BLOCK")
    trials = add_events(store.run_dir)
    candidate = trials[1]
    load = module.load_suite_run
    reads = 0

    def changed(path: Path | str):
        nonlocal reads
        reads += 1
        manifest, records = load(path)
        if reads == 2:
            records = tuple(
                TrialEnvelope.create(
                    **(t.model_dump(exclude={"record_sha256"}) | {"failure_detail": "changed"})
                )
                if t == candidate
                else t
                for t in records
            )
        return manifest, records

    monkeypatch.setattr(module, "load_suite_run", changed)
    result = module.triage_run(store.run_dir, trial_id=candidate.trial_id)
    assert result.status == "INVALID" and not result.selected_pairs
    assert "snapshot changed" in result.reason


def test_v1_triage_preserves_default_schema_loading(tmp_path: Path) -> None:
    from arci.schedule import build_schedule
    from arci.storage import ExperimentStore
    from arci.triage import triage_run
    from tests.unit.triage.test_triage_core import envelope, manifest

    m = manifest()
    store = ExperimentStore(tmp_path, m)
    for spec in build_schedule(m):
        store.append_trial(envelope(spec))
    before = triage_run(store.run_dir)
    assert before.status == "OK"
    # The v1 loader has always restored schema_version from its model default.
    path = store.run_dir / "manifest.json"
    data = json.loads(path.read_text())
    del data["schema_version"]
    path.write_text(json.dumps(data))
    assert triage_run(store.run_dir) == before
