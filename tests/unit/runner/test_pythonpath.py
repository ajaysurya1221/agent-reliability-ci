"""ADR 0006: the current directory is on the child import path, appended, never first."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from arci.runner import child_pythonpath

SITE = "/opt/python/site-packages"
STDLIB = "/opt/python/lib"


def _entries(value: str) -> list[str]:
    return value.split(os.pathsep)


@pytest.fixture
def cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PYTHONPATH", raising=False)
    return os.getcwd()


def test_console_script_path_gains_the_cwd_once_and_last(
    cwd: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The `arci` console script: sys.path starts with the script's bin directory, no "" or cwd.
    monkeypatch.setattr(sys, "path", ["/opt/venv/bin", STDLIB, SITE])
    entries = _entries(child_pythonpath(()))
    assert entries.count(cwd) == 1
    assert entries[0] != cwd
    assert entries == ["/opt/venv/bin", STDLIB, SITE, cwd]


def test_the_cwd_is_appended_after_an_inherited_pythonpath(
    cwd: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "path", [STDLIB, SITE])
    monkeypatch.setenv("PYTHONPATH", "/extra/one")
    assert _entries(child_pythonpath(())) == [STDLIB, SITE, "/extra/one", cwd]


@pytest.mark.parametrize("first", ["", "cwd"])
def test_nothing_changes_when_sys_path_already_has_the_cwd(
    cwd: str, monkeypatch: pytest.MonkeyPatch, first: str
) -> None:
    # `python -m arci.cli` puts "" first; the cwd keeps that position and is not repeated.
    monkeypatch.setattr(sys, "path", [cwd if first == "cwd" else "", STDLIB, SITE])
    assert _entries(child_pythonpath(())) == [cwd, STDLIB, SITE]


def test_nothing_changes_when_the_inherited_pythonpath_has_the_cwd(
    cwd: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "path", [STDLIB, SITE])
    monkeypatch.setenv("PYTHONPATH", cwd)
    assert _entries(child_pythonpath(())) == [STDLIB, SITE, cwd]


def test_replay_bundle_directory_still_comes_first(
    cwd: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    bundle = str(tmp_path / "bundle")
    monkeypatch.setattr(sys, "path", ["/opt/venv/bin", STDLIB, SITE])
    entries = _entries(child_pythonpath((bundle,)))
    assert entries[0] == bundle
    assert entries[-1] == cwd
    assert entries.count(cwd) == 1


def test_a_removed_cwd_is_skipped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    gone = tmp_path / "gone"
    gone.mkdir()
    monkeypatch.chdir(gone)
    gone.rmdir()
    monkeypatch.delenv("PYTHONPATH", raising=False)
    monkeypatch.setattr(sys, "path", [STDLIB, SITE])
    assert _entries(child_pythonpath(())) == [STDLIB, SITE]
