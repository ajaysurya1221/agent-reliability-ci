"""JSONL framing must preserve Unicode separators inside stored strings."""

from pathlib import Path

import pytest

from arci.gate import decide
from arci.schema import Condition, Manifest, TrialEnvelope, Verdict
from arci.storage import ExperimentStore, load_run
from tests.acceptance.helpers import synthetic_trials
from tests.unit.html_report.test_html_report import v1_evidence


@pytest.mark.parametrize("separator", ["", "\u0085", "\u2028", "\u2029"])
def test_v1_unicode_separator_round_trip(tmp_path: Path, separator: str) -> None:
    original, _ = v1_evidence()
    label, condition, detail = (f"{name}a{separator}b" for name in ("label", "condition", "detail"))
    manifest = Manifest.create(
        **(
            original.model_dump(exclude={"record_sha256"})
            | {
                "baseline": original.baseline.model_copy(update={"label": label}),
                "conditions": (Condition(condition_id=condition),),
            }
        )
    )
    trials = tuple(
        TrialEnvelope.create(
            **(t.model_dump(exclude={"record_sha256"}) | {"failure_detail": detail})
        )
        for t in synthetic_trials(
            manifest, condition_id=condition, baseline_successes=12, candidate_successes=0
        )
    )
    store = ExperimentStore(tmp_path, manifest)
    for trial in trials:
        store.append_trial(trial)
    before = {p.name: p.read_bytes() for p in store.run_dir.iterdir()}
    loaded, observed = load_run(store.run_dir)
    assert (loaded, observed) == (manifest, trials)
    assert tuple(t.model_dump_json() for t in observed) == tuple(
        t.model_dump_json() for t in trials
    )
    assert decide(loaded, observed) == decide(manifest, trials)
    assert decide(loaded, observed).verdict is not Verdict.ERROR
    assert {p.name: p.read_bytes() for p in store.run_dir.iterdir()} == before
