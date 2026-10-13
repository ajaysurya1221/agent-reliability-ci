"""The committed Action fixture is current, sealed, and built only from packaged refs."""

from __future__ import annotations

from pathlib import Path

from arci.demo.experiment import build_manifest
from arci.schema import Manifest
from examples.action_fixture.build_manifest import MANIFEST, render, write


def test_regenerating_the_fixture_is_byte_identical(tmp_path: Path) -> None:
    regenerated = write(tmp_path / "manifest.json")
    assert regenerated.read_bytes() == MANIFEST.read_bytes(), (
        "examples/action_fixture/manifest.json is stale: "
        "run python examples/action_fixture/build_manifest.py"
    )
    assert render().encode("utf-8") == MANIFEST.read_bytes()


def test_the_fixture_seal_validates() -> None:
    manifest = Manifest.model_validate_json(MANIFEST.read_text(encoding="utf-8"))
    assert manifest.validate_seal()
    assert manifest.created_at == ""
    assert manifest == build_manifest(n_per_arm=200, candidate="agent_b")


def test_the_fixture_is_the_demo_a_vs_b_experiment_with_packaged_refs() -> None:
    manifest = Manifest.model_validate_json(MANIFEST.read_text(encoding="utf-8"))
    assert manifest.n_per_arm == 200
    assert manifest.baseline.label == "agent_a"
    assert manifest.candidate.label == "agent_b"
    refs = [
        manifest.toolset,
        manifest.contract.oracle,
        manifest.baseline.agent,
        manifest.candidate.agent,
    ]
    assert all(ref is not None and ref.startswith("arci.demo.") for ref in refs), refs
    assert manifest.mcp_server is None
    assert manifest.decisions is None
