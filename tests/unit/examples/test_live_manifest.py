"""Live (http upstream) manifests for the Jev triage example. Offline: nothing is called."""

from __future__ import annotations

from pathlib import Path

import pytest

from arci.schema import DECISION_TOOL, Manifest
from examples.jev_triage_agent.experiment import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    DEFAULT_RPM,
    build_manifest,
    live_manifest,
    main,
)


def test_live_manifest_targets_the_http_upstream_and_seals() -> None:
    m = live_manifest("b")
    assert m.validate_seal()
    assert m.decisions is not None
    assert m.decisions.upstream == "http"
    assert m.decisions.fixture is None
    assert m.decisions.base_url == DEFAULT_BASE_URL
    assert m.decisions.model == DEFAULT_MODEL
    assert m.decisions.max_requests_per_minute == DEFAULT_RPM
    assert m.experiment_id == "jev-live-b-low_confidence-50"
    assert m.n_per_arm == 50


def test_live_manifest_only_changes_the_decision_upstream() -> None:
    live = live_manifest("b", n_per_arm=200)
    fixture = build_manifest(n_per_arm=200, candidate="b")
    for field in (
        "task",
        "mcp_server",
        "contract",
        "baseline",
        "candidate",
        "conditions",
        "budgets",
        "base_seed",
    ):
        assert getattr(live, field) == getattr(fixture, field), field


@pytest.mark.parametrize(
    ("condition", "condition_id", "fault"),
    [
        ("clean", "clean", None),
        ("low_confidence", "low_confidence", "decision_low_confidence"),
        ("unavailable", "provider_down", "decision_unavailable"),
    ],
)
def test_live_conditions(condition: str, condition_id: str, fault: str | None) -> None:
    m = live_manifest("b", condition=condition)
    (c,) = m.conditions
    assert c.condition_id == condition_id
    if fault is None:
        assert c.faults == ()
    else:
        (f,) = c.faults
        assert f.name == fault and f.tool == DECISION_TOOL


def test_live_manifest_ids_are_distinct_per_axis() -> None:
    ids = {
        live_manifest("a").experiment_id,
        live_manifest("b").experiment_id,
        live_manifest("b", n_per_arm=200).experiment_id,
        live_manifest("b", condition="clean", n_per_arm=1).experiment_id,
        live_manifest("b", runtime="node").experiment_id,
    }
    assert len(ids) == 5
    assert live_manifest("b", runtime="node").experiment_id == "jev-live-b-low_confidence-50-node"


def test_prior_runs_and_overrides_are_threaded_into_the_seal() -> None:
    m = live_manifest(
        "b",
        n_per_arm=200,
        base_url="https://ai-gateway.vercel.sh/typesafe",
        model="typesafe-ai/jev",
        max_requests_per_minute=120,
        prior_runs=("jev-live-b-low_confidence-50", "jev-live-a-low_confidence-50"),
    )
    assert m.validate_seal()
    assert m.prior_runs == ("jev-live-b-low_confidence-50", "jev-live-a-low_confidence-50")
    assert m.decisions is not None
    assert m.decisions.base_url == "https://ai-gateway.vercel.sh/typesafe"
    assert m.decisions.model == "typesafe-ai/jev"
    assert m.decisions.max_requests_per_minute == 120
    assert m.record_sha256 != live_manifest("b", n_per_arm=200).record_sha256


def test_invalid_condition_is_rejected() -> None:
    with pytest.raises(ValueError, match="condition must be"):
        live_manifest("b", condition="storm")


def test_main_writes_a_round_trippable_sealed_manifest(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "m" / "manifest.json"
    code = main(
        [
            "--candidate",
            "a",
            "--n-per-arm",
            "7",
            "--condition",
            "unavailable",
            "--prior-run",
            "jev-live-b-clean-1",
            "--prior-run",
            "jev-live-b-low_confidence-50",
            "--rpm",
            "60",
            "--out",
            str(out),
        ]
    )
    assert code == 0
    loaded = Manifest.model_validate_json(out.read_text(encoding="utf-8"))
    assert loaded.validate_seal()
    assert loaded == live_manifest(
        "a",
        n_per_arm=7,
        condition="unavailable",
        max_requests_per_minute=60,
        prior_runs=("jev-live-b-clean-1", "jev-live-b-low_confidence-50"),
    )
    assert "jev-live-a-provider_down-7" in capsys.readouterr().out


def test_main_fixture_flag_keeps_the_seeded_upstream(tmp_path: Path) -> None:
    out = tmp_path / "fixture.json"
    assert main(["--fixture", "--n-per-arm", "50", "--out", str(out)]) == 0
    loaded = Manifest.model_validate_json(out.read_text(encoding="utf-8"))
    assert loaded == build_manifest(n_per_arm=50, candidate="b")
