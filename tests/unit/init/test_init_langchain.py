"""The generated order desk works without the repository's example files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tests.unit.examples.test_langchain_quickstart import arci, require_langchain, run_and_gate


def available(_name: str) -> object:
    return object()


def skip_references(*args: Any, **kwargs: Any) -> None:
    pass


def test_scaffold_and_run(tmp_path: Path) -> None:
    require_langchain()
    result = arci(tmp_path, "init", "--langchain")
    assert result.returncode == 0, result.stderr
    assert (
        result.stdout == "LANGSMITH_TRACING=false LANGSMITH_TRACING_V2=false arci run arci.yaml\n"
    )
    assert result.stderr == ""
    assert {p.name for p in tmp_path.iterdir()} == {
        "tools.py",
        "agent.py",
        "offline_model.py",
        "configuration.py",
        "register.py",
        "check.py",
        "tasks.jsonl",
        "arci.yaml",
    }
    elapsed = run_and_gate(tmp_path)
    print(f"scaffold: BLOCK, round 1, 192 trials, {elapsed:.2f} seconds")


@pytest.mark.parametrize(
    "name",
    [
        "tools.py",
        "agent.py",
        "offline_model.py",
        "configuration.py",
        "register.py",
        "check.py",
        "tasks.jsonl",
        "arci.yaml",
    ],
)
def test_scaffold_never_overwrites(
    tmp_path: Path, name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from arci.init import InitError, run_langchain_init

    monkeypatch.setattr("importlib.util.find_spec", available)
    monkeypatch.chdir(tmp_path)
    (tmp_path / name).write_text("keep me")
    with pytest.raises(InitError) as error:
        run_langchain_init()
    assert (
        str(error.value) == f"output {name} exists; run arci init --langchain in an empty directory"
    )
    assert {p.name for p in tmp_path.iterdir()} == {name}
    assert (tmp_path / name).read_text() == "keep me"


def test_packaged_templates_match_example(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from arci.init import run_langchain_init
    from tests.unit.examples.test_langchain_quickstart import EXAMPLE

    monkeypatch.chdir(tmp_path)
    require_langchain()
    assert (
        run_langchain_init()
        == "LANGSMITH_TRACING=false LANGSMITH_TRACING_V2=false arci run arci.yaml"
    )
    for path in tmp_path.iterdir():
        assert path.read_bytes() == (EXAMPLE / path.name).read_bytes()


def test_missing_extra_writes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib.util

    from arci.init import InitError, run_langchain_init

    monkeypatch.chdir(tmp_path)

    def missing(_name: str) -> None:
        return None

    monkeypatch.setattr(importlib.util, "find_spec", missing)
    with pytest.raises(
        InitError, match=r"^pip install 'agent-reliability-ci\[langchain\]>=2.0.0'$"
    ):
        run_langchain_init()
    assert list(tmp_path.iterdir()) == []


def test_cli_missing_extra_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import importlib.util

    from arci.cli import main

    def missing(_name: str) -> None:
        return None

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(importlib.util, "find_spec", missing)
    assert main(["init", "--langchain"]) == 3
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == (
        "error: CliError: init: pip install 'agent-reliability-ci[langchain]>=2.0.0'\n"
    )
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "extra",
    [
        ["my-experiment"],
        ["--baseline", "agent:baseline"],
        ["--candidate", "agent:candidate"],
        ["--toolset", "agent:toolset"],
        ["--oracle", "check:check"],
        ["--task", "{}"],
        ["--task-file", "task.json"],
        ["--fault", "tool_timeout"],
        ["--n", "8"],
        ["--out", "arci.yaml"],
        ["--force"],
    ],
)
def test_cli_refuses_mixed_scaffold_options(tmp_path: Path, extra: list[str]) -> None:
    result = arci(tmp_path, "init", "--langchain", *extra)
    assert result.returncode == 3
    assert result.stdout == ""
    assert "--langchain cannot be combined" in result.stderr
    assert list(tmp_path.iterdir()) == []


def test_publish_failure_rolls_back_only_our_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import errno
    import os

    from arci.init import InitError, run_langchain_init

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("importlib.util.find_spec", available)
    monkeypatch.setattr("arci.init.check_references", skip_references)
    real_link = os.link

    def fail_second(source: Path, destination: Path) -> None:
        if destination.name == "agent.py":
            destination.write_text("racing writer")
            raise FileExistsError(errno.EEXIST, "exists")
        real_link(source, destination)

    monkeypatch.setattr(os, "link", fail_second)
    with pytest.raises(InitError, match=r"output agent\.py exists"):
        run_langchain_init()
    assert {p.name for p in tmp_path.iterdir()} == {"agent.py"}
    assert (tmp_path / "agent.py").read_text() == "racing writer"


def test_unwritable_staging_uses_init_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import errno
    import tempfile

    from arci.init import InitError, run_langchain_init

    def denied(*args: Any, **kwargs: Any) -> None:
        raise PermissionError(errno.EACCES, "Permission denied")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("importlib.util.find_spec", available)
    monkeypatch.setattr(tempfile, "TemporaryDirectory", denied)
    with pytest.raises(InitError, match="cannot write scaffold: Permission denied"):
        run_langchain_init()
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("name", ["tools", "agent", "configuration", "README.md"])
def test_nonempty_directory_is_refused(
    tmp_path: Path, name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from arci.init import InitError, run_langchain_init

    monkeypatch.setattr("importlib.util.find_spec", available)
    monkeypatch.chdir(tmp_path)
    (tmp_path / name).mkdir()
    with pytest.raises(InitError, match="run arci init --langchain in an empty directory") as error:
        run_langchain_init()
    assert "--force" not in str(error.value)
    assert list(tmp_path.iterdir()) == [tmp_path / name]
