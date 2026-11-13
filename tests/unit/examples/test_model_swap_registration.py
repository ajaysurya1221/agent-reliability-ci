"""Registration names the actual comparison before identity and seeds are derived."""

from __future__ import annotations

import importlib
import shutil
from pathlib import Path

import pytest

from arci.descriptor import loads_suite_descriptor
from arci.suite_schedule import build_suite_round, suite_rule_sha256
from arci.suite_schema import SuiteManifest
from examples.langchain_quickstart.configuration import validate_registration
from tests.unit.examples.test_langchain_quickstart import EXAMPLE


def test_labels_restore_and_mode_changes_require_registration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("BASELINE", "CANDIDATE", "TEMPERATURE"):
        monkeypatch.delenv(f"ARCI_QUICKSTART_{name}", raising=False)
    shutil.copytree(EXAMPLE, tmp_path, dirs_exist_ok=True)
    monkeypatch.syspath_prepend(str(EXAMPLE))
    register = importlib.import_module("register").register
    descriptor = tmp_path / "arci.yaml"

    def manifest() -> SuiteManifest:
        return loads_suite_descriptor(descriptor.read_text(), str(descriptor))

    offline = manifest()
    # Exercise swap -> same real model -> offline, including restoration of labels.
    for baseline, candidate, labels in (
        (
            "ollama:base/model:tag",
            "other:candidate/v2",
            ("ollama:base/model:tag", "other:candidate/v2"),
        ),
        ("ollama:base/model:tag", "ollama:base/model:tag", ("retry", "no-retry")),
        (None, None, ("retry", "no-retry")),
    ):
        previous = manifest()
        for arm, identifier in (("BASELINE", baseline), ("CANDIDATE", candidate)):
            if identifier is None:
                monkeypatch.delenv(f"ARCI_QUICKSTART_{arm}", raising=False)
            else:
                monkeypatch.setenv(f"ARCI_QUICKSTART_{arm}", identifier)
        with pytest.raises(ValueError, match="disagrees with registered settings"):
            validate_registration(previous.tasks[0].task)
        register(tmp_path)
        registered = manifest()
        assert (registered.baseline.label, registered.candidate.label) == labels
        assert registered.experiment_id != previous.experiment_id
        assert suite_rule_sha256(registered) != suite_rule_sha256(previous)
        specs = build_suite_round(registered, 1)
        assert {spec.variant for spec in specs} == set(labels)
        assert [spec.seed for spec in specs] != [
            spec.seed for spec in build_suite_round(previous, 1)
        ]
        assert validate_registration(registered.tasks[0].task)
    assert manifest().experiment_id == offline.experiment_id


def test_all_static_templates_match_without_optional_framework() -> None:
    from arci.init import LANGCHAIN_FILES

    for name, content in LANGCHAIN_FILES.items():
        assert content.encode() == (EXAMPLE / name).read_bytes(), name


def test_register_accepts_bare_string_arms(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A descriptor may name an arm as a bare `module:function`; registration keeps working."""
    shutil.copytree(EXAMPLE, tmp_path, dirs_exist_ok=True)
    descriptor = tmp_path / "arci.yaml"
    text = descriptor.read_text()
    old_arms = (
        "baseline: {label: retry, agent: 'agent:baseline'}\n"
        "candidate: {label: no-retry, agent: 'agent:candidate'}\n"
    )
    assert old_arms in text
    descriptor.write_text(
        text.replace(old_arms, "baseline: 'agent:baseline'\ncandidate: 'agent:candidate'\n")
    )
    monkeypatch.syspath_prepend(str(EXAMPLE))
    monkeypatch.setenv("ARCI_QUICKSTART_BASELINE", "fake:first")
    monkeypatch.setenv("ARCI_QUICKSTART_CANDIDATE", "fake:second")
    monkeypatch.delenv("ARCI_QUICKSTART_TEMPERATURE", raising=False)
    importlib.import_module("register").register(tmp_path)
    manifest = loads_suite_descriptor(descriptor.read_text(), str(descriptor))
    assert (manifest.baseline.label, manifest.candidate.label) == ("fake:first", "fake:second")
