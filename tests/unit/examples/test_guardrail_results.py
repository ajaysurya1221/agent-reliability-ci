"""Every committed guardrail decision re-derives byte for byte from its sealed records.

For each store under `docs/results/guardrail/`, including any invalid attempt, only
`manifest.json` and `trials.jsonl` are copied to a temporary directory; `arci gate` runs there in
a child process without a key, and the `decision.json` it writes must equal the committed bytes.
Offline: no trial, minimisation, replay or network call.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from arci.schema import GateDecision, Manifest, TrialEnvelope

RESULTS = Path(__file__).resolve().parents[3] / "docs" / "results" / "guardrail"
# The committed stores, listed so that deleting one (or its decision) fails here instead of
# silently removing a test case.
STORES = (
    "2026-10-05/guardrail-live-b-all-provider_down-200",
    "2026-10-05/guardrail-live-b-ask-clean-1",
    "2026-10-05/guardrail-live-b-ask-low_confidence-50",
    "2026-10-05/guardrail-live-b-ask-provider_down-200",
    "2026-10-05/guardrail-live-b-ask-provider_down-50",
    "2026-10-05/guardrail-live-c-ask-clean-50",
)
SCRUBBED = ("TYPESAFE_API_KEY", "jev_key", "GITHUB_STEP_SUMMARY")


def test_the_store_inventory_is_complete() -> None:
    decisions = sorted(
        p.parent.relative_to(RESULTS).as_posix() for p in RESULTS.rglob("decision.json")
    )
    assert decisions, "no committed guardrail decisions"
    assert decisions == sorted(STORES)
    # A store whose decision.json went missing still has its records: catch that too.
    records = {
        p.parent.relative_to(RESULTS).as_posix()
        for name in ("manifest.json", "trials.jsonl")
        for p in RESULTS.rglob(name)
    }
    assert records == set(STORES)


@pytest.mark.parametrize("store", STORES)
def test_committed_decision_re_derives_byte_for_byte(store: str, tmp_path: Path) -> None:
    source = RESULTS / store
    names = ("manifest.json", "trials.jsonl", "decision.json")
    before = {name: (source / name).read_bytes() for name in names}

    manifest = Manifest.model_validate_json(before["manifest.json"])
    assert manifest.validate_seal()
    lines = [line for line in before["trials.jsonl"].decode("utf-8").splitlines() if line]
    assert lines
    assert all(TrialEnvelope.model_validate_json(line).validate_seal() for line in lines)
    committed = GateDecision.model_validate_json(before["decision.json"])
    assert committed.validate_seal()
    assert committed.experiment_id == manifest.experiment_id == source.name

    target = tmp_path / source.name
    target.mkdir()
    for name in ("manifest.json", "trials.jsonl"):
        shutil.copy2(source / name, target / name)
    env = {key: value for key, value in os.environ.items() if key not in SCRUBBED}
    result = subprocess.run(
        [sys.executable, "-m", "arci.cli", "gate", str(target)],
        env=env,
        capture_output=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == json.loads(before["decision.json"])["exit_code"]
    assert result.returncode == committed.exit_code
    regenerated = target / "decision.json"
    assert regenerated.is_file()
    assert regenerated.read_bytes() == before["decision.json"]
    assert {name: (source / name).read_bytes() for name in names} == before
