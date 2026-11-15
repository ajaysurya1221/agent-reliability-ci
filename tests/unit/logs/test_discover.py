"""Discovery uses names only; missing roots and failures do not expose paths."""

from pathlib import Path

import pytest

from arci.logs.discover import claude_files, claude_root, codex_files, codex_root
from tests.unit.logs.synth_logs import generate


def test_roots_are_pure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("filesystem access")

    monkeypatch.setattr(Path, "stat", forbidden)
    assert claude_root({}, tmp_path) == tmp_path / ".claude/projects"
    assert codex_root({}, tmp_path) == tmp_path / ".codex"
    assert claude_root({"CLAUDE_CONFIG_DIR": "/synthetic"}, tmp_path) == Path("/synthetic/projects")
    assert codex_root({"CODEX_HOME": "/synthetic"}, tmp_path) == Path("/synthetic")


def test_all_nested_files_sorted(tmp_path: Path) -> None:
    fixture = generate(tmp_path)
    assert claude_files(fixture.claude_root) == sorted(fixture.paths["claude-code"])
    assert codex_files(fixture.codex_root) == sorted(fixture.paths["codex"])
    extra = fixture.claude_root / "arbitrary/deep/other.jsonl"
    extra.parent.mkdir(parents=True)
    extra.touch()
    (extra.parent / "journal.jsonl").touch()
    (extra.parent / "noise.json").touch()
    (fixture.codex_root / "sessions/ignored.jsonl").touch()
    (fixture.codex_root / "rollout-outside.jsonl").touch()
    (fixture.codex_root / "archived_sessions/rollout-noise.jsonl.gz").touch()
    assert claude_files(fixture.claude_root) == sorted([*fixture.paths["claude-code"], extra])
    assert codex_files(fixture.codex_root) == sorted(fixture.paths["codex"])


def test_missing_or_non_directory_roots(tmp_path: Path) -> None:
    assert claude_files(tmp_path / "absent") == codex_files(tmp_path / "absent") == []
    file = tmp_path / "file"
    file.touch()
    assert claude_files(file) == codex_files(file) == []


def test_discovery_failure_has_no_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise PermissionError("CANARY-1 /private/canary-payroll-1")

    monkeypatch.setattr("arci.logs.discover.os.walk", fail)
    assert claude_files(tmp_path) == codex_files(tmp_path) == []
    assert capsys.readouterr() == ("", "")
