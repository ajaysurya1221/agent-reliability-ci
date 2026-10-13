"""`arci init` publication and the descriptor's header and next command, in-process.

The reference check is replaced by a stub (its child is covered by test_child.py and test_init.py),
so these tests reach `publish` with references that need not import.
"""

from __future__ import annotations

import argparse
import errno
import os
import shlex
import stat
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

import arci.cli as cli_module
import arci.init as init_module
from arci.cli import main
from arci.descriptor import compile_descriptor, compile_descriptor_text
from arci.init import HEADER, NON_SMOKE_N, InitRequest, parse_request, render_descriptor

REFS: tuple[str, ...] = (
    "--baseline",
    "app.v1:run",
    "--candidate",
    "app.v2:run",
    "--toolset",
    "tests.world:make_world",
    "--oracle",
    "tests.world:passed",
)
PREFIX = "error: CliError: init: "
# The units under test, taken by name so that no private-usage suppression is needed.
REAL_CHECK_OUTPUT = cast(Callable[[Path, str, bool], None], vars(init_module)["_check_output"])
REAL_PARSER = cast(Callable[[], argparse.ArgumentParser], vars(cli_module)["_parser"])


@pytest.fixture
def workdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    def no_child(request: InitRequest, *, deadline: float) -> tuple[str, ...]:
        del request, deadline
        return ()

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(init_module, "check_references", no_child)
    return tmp_path


def _init(capsys: pytest.CaptureFixture[str], *extra: str) -> tuple[int, str, str]:
    code = main(["init", "exp", *REFS, *extra])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def _no_links(source: object, dest: object) -> None:
    del source, dest
    raise OSError(errno.EOPNOTSUPP, os.strerror(errno.EOPNOTSUPP))


def _ordinary_mode() -> int:
    umask = os.umask(0o022)
    os.umask(umask)
    return 0o666 & ~umask


# --- 1b: without --force, publication fails closed --------------------------------------------


NO_LINKS_LINE = (
    f"{PREFIX}output arci.yaml: cannot publish atomically here (hard links unsupported); "
    "choose another directory or pass --force\n"
)


def test_without_links_nothing_is_published(
    workdir: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(os, "link", _no_links)
    assert _init(capsys) == (3, "", NO_LINKS_LINE)
    assert set(workdir.iterdir()) == set()  # no destination, no staged file


def test_without_links_a_destination_that_appears_before_publication_survives(
    workdir: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    real_check = REAL_CHECK_OUTPUT
    competitor = b"a competitor's bytes\n"
    calls: list[Path] = []

    def check_then_race(out: Path, out_text: str, force: bool) -> None:
        real_check(out, out_text, force)
        calls.append(out)
        if len(calls) == 2:  # the re-check in publish: the competitor lands right after it
            out.write_bytes(competitor)

    monkeypatch.setattr(init_module, "_check_output", check_then_race)
    monkeypatch.setattr(os, "link", _no_links)
    assert _init(capsys) == (3, "", NO_LINKS_LINE)
    assert len(calls) == 2
    assert (workdir / "arci.yaml").read_bytes() == competitor
    assert {path.name for path in workdir.iterdir()} == {"arci.yaml"}  # nothing staged is left


def test_with_force_and_no_links_the_rename_still_publishes(
    workdir: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (workdir / "arci.yaml").write_bytes(b"old\n")
    monkeypatch.setattr(os, "link", _no_links)
    assert _init(capsys, "--force") == (0, "arci run arci.yaml\n", "")
    assert {path.name for path in workdir.iterdir()} == {"arci.yaml"}
    assert compile_descriptor(workdir / "arci.yaml").experiment_id == "exp"


def test_with_links_a_destination_that_appears_before_publication_survives(
    workdir: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    real_check = REAL_CHECK_OUTPUT
    calls: list[Path] = []

    def check_then_race(out: Path, out_text: str, force: bool) -> None:
        real_check(out, out_text, force)
        calls.append(out)
        if len(calls) == 2:
            out.write_bytes(b"competitor\n")

    monkeypatch.setattr(init_module, "_check_output", check_then_race)
    code, _, err = _init(capsys)
    assert code == 3
    assert err == f"{PREFIX}output arci.yaml exists; use --force to replace it\n"
    assert (workdir / "arci.yaml").read_bytes() == b"competitor\n"
    assert {path.name for path in workdir.iterdir()} == {"arci.yaml"}


# --- 2b: durability ---------------------------------------------------------------------------


def _is_directory(fd: int) -> bool:
    return stat.S_ISDIR(os.fstat(fd).st_mode)


def test_the_staged_file_and_the_directory_are_fsynced(
    workdir: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    real_fsync = os.fsync
    synced: list[str] = []

    def recording_fsync(fd: int) -> None:
        synced.append("dir" if _is_directory(fd) else "file")
        real_fsync(fd)

    monkeypatch.setattr(os, "fsync", recording_fsync)
    assert _init(capsys) == (0, "arci run arci.yaml\n", "")
    assert synced == ["file", "dir"]
    published = workdir / "arci.yaml"
    assert stat.S_IMODE(published.stat().st_mode) == _ordinary_mode()


def test_a_failed_staged_fsync_writes_nothing(
    workdir: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def failing_fsync(fd: int) -> None:
        del fd
        raise OSError(errno.EIO, os.strerror(errno.EIO))

    monkeypatch.setattr(os, "fsync", failing_fsync)
    code, out, err = _init(capsys)
    assert (code, out) == (3, "")
    assert err == f"{PREFIX}output arci.yaml: cannot write: {os.strerror(errno.EIO)}\n"
    assert set(workdir.iterdir()) == set()  # no destination, no staged file


def test_a_failed_directory_fsync_is_ignored(
    workdir: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    real_fsync = os.fsync

    def directory_fsync_fails(fd: int) -> None:
        if _is_directory(fd):
            raise OSError(errno.EINVAL, os.strerror(errno.EINVAL))
        real_fsync(fd)

    monkeypatch.setattr(os, "fsync", directory_fsync_fails)
    assert _init(capsys) == (0, "arci run arci.yaml\n", "")
    assert {path.name for path in workdir.iterdir()} == {"arci.yaml"}
    assert compile_descriptor(workdir / "arci.yaml").experiment_id == "exp"


# --- 1c: an unwritable output directory -----------------------------------------------------------


@pytest.mark.skipif(os.geteuid() == 0, reason="root writes into a read-only directory")
def test_an_unwritable_output_directory_is_one_line_and_writes_nothing(
    workdir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    locked = workdir / "locked"
    locked.mkdir()
    locked.chmod(0o555)
    try:
        code, out, err = _init(capsys, "--out", "locked/arci.yaml")
        assert (code, out) == (3, "")
        assert err == (
            f"{PREFIX}output locked/arci.yaml: cannot write: {os.strerror(errno.EACCES)}\n"
        )
        assert list(locked.iterdir()) == []
    finally:
        locked.chmod(0o755)


# --- 1e: the next command parses with the real parser ---------------------------------------------


@pytest.mark.parametrize(
    ("out", "line"),
    [
        ("arci.yaml", "arci run arci.yaml"),
        ("-x.yaml", "arci run -- -x.yaml"),
        ("--help.yml", "arci run -- --help.yml"),
        ("-my file.yaml", "arci run -- '-my file.yaml'"),
    ],
)
def test_the_printed_command_parses_back_to_the_written_path(
    workdir: Path, capsys: pytest.CaptureFixture[str], out: str, line: str
) -> None:
    code, printed, err = _init(capsys, f"--out={out}")
    assert (code, printed, err) == (0, f"{line}\n", "")
    assert (workdir / out).is_file()
    words = shlex.split(printed)
    assert words[0] == "arci"
    values = vars(REAL_PARSER().parse_args(words[1:]))
    assert values["command"] == "run"
    assert values["manifest_json"] == out


# --- 1f: the header names a chosen design from N = 100 ----------------------------------------


def _request(n: int) -> InitRequest:
    return parse_request(
        experiment_id="exp",
        baseline="app.v1:run",
        candidate="app.v2:run",
        toolset="tests.world:make_world",
        oracle="tests.world:passed",
        task=None,
        task_file=None,
        faults=(),
        n=str(n),
        out="arci.yaml",
        force=False,
    )


def test_the_non_smoke_bound_is_the_run_notices() -> None:
    assert NON_SMOKE_N == cli_module.SMOKE_N_BELOW == 100


@pytest.mark.parametrize("n", [1, 8, 99])
def test_a_smoke_design_keeps_the_smoke_header(workdir: Path, n: int) -> None:
    del workdir
    text = render_descriptor(_request(n))
    assert text.startswith(HEADER)
    assert compile_descriptor_text(text).n_per_arm == n


@pytest.mark.parametrize("n", [100, 250, 10000])
def test_a_design_from_100_names_the_chosen_n(workdir: Path, n: int) -> None:
    del workdir
    text = render_descriptor(_request(n))
    assert text.splitlines()[:5] == [
        "# arci experiment descriptor. Schema: `arci schema`.",
        f"# design: {n} trials per arm, chosen by you; plan it with arci plan",
        "# This file was written by arci init; re-run init or edit to change the design.",
        "# Plan before trials: arci plan --help",
        "# Never extend this experiment based on its verdict.",
    ]
    assert "smoke" not in text.lower()
    assert compile_descriptor_text(text).n_per_arm == n


def test_init_writes_the_chosen_design_header(
    workdir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _init(capsys, "--n", "120") == (0, "arci run arci.yaml\n", "")
    lines = (workdir / "arci.yaml").read_text(encoding="utf-8").splitlines()
    assert lines[1] == "# design: 120 trials per arm, chosen by you; plan it with arci plan"
    assert "n_per_arm: 120" in lines
