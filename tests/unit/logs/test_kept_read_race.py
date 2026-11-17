"""Record 0017: the kept table read while another run installs the table.

The writer makes the table path go from absent to an empty placeholder, back to absent, and
then to the finished table. A reader without the directory lock can make two calls on either
side of one of those steps. Every test here places the step between two calls by hand: there
is no second process, no thread and no sleep.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import IO, Any

import pytest

from arci.logs import kept
from tests.unit.logs.test_logs2 import history, invoke, row

Step = Callable[[], object]


def table(*models: str) -> str:
    return kept.serialize(tuple(row(model=model) for model in sorted(models)))


def after_first_missing_stat(monkeypatch: pytest.MonkeyPatch, path: Path, step: Step) -> list[int]:
    """Run `step` once, right after the first `path.stat()` that finds nothing there.

    Returns a one-item list that counts the `stat()` calls on `path` that follow links.
    `Path.lstat` is `stat(follow_symlinks=False)` on Python 3.11, so those calls pass through.
    """
    original = Path.stat
    calls = [0]
    pending = [True]

    def stat(self: Path, *, follow_symlinks: bool = True) -> os.stat_result:
        if self != path or not follow_symlinks:
            return original(self, follow_symlinks=follow_symlinks)
        calls[0] += 1
        try:
            return original(self)
        except FileNotFoundError:
            if pending[0]:
                pending[0] = False
                step()
            raise

    monkeypatch.setattr(Path, "stat", stat)
    return calls


def before_first_open(monkeypatch: pytest.MonkeyPatch, path: Path, step: Step) -> None:
    """Run `step` once, after `path.stat()` has answered and before `path.open()` runs."""
    original = Path.open
    pending = [True]

    def open_(self: Path, *args: Any, **kwargs: Any) -> IO[Any]:
        if self == path and pending[0]:
            pending[0] = False
            step()
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", open_)


def placeholder_goes_at_first_open(
    monkeypatch: pytest.MonkeyPatch, path: Path, content: str
) -> list[bool]:
    """At the first `path.open()` the placeholder is gone; right after it `content` is there.

    Returns a one-item list that turns false once that `open()` has run.
    """
    original = Path.open
    pending = [True]

    def open_(self: Path, *args: Any, **kwargs: Any) -> IO[Any]:
        if self != path or not pending[0]:
            return original(self, *args, **kwargs)
        pending[0] = False
        path.unlink()
        try:
            return original(self, *args, **kwargs)
        finally:
            path.write_text(content)

    monkeypatch.setattr(Path, "open", open_)
    return pending


def test_a_table_installed_between_stat_and_lstat_is_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / kept.FILENAME
    calls = after_first_missing_stat(monkeypatch, path, lambda: path.write_text(table("gpt-5")))
    assert kept.read(path) == ("read", (row(model="gpt-5"),))
    assert calls == [2]
    assert kept.read(path) == ("read", (row(model="gpt-5"),))


def test_a_table_installed_after_the_placeholder_went_is_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`stat()` sees the writer's empty placeholder, `open()` misses it, then the table lands."""
    path = tmp_path / kept.FILENAME
    path.write_bytes(b"")
    pending = placeholder_goes_at_first_open(monkeypatch, path, table("gpt-5"))
    assert kept.read(path) == ("read", (row(model="gpt-5"),))
    assert not pending[0]


def test_one_writer_can_cost_three_attempts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every step of one writer falls between two calls of the reader.

    First attempt: `stat()` finds nothing, `lstat()` finds the empty placeholder. Second:
    `stat()` finds the placeholder, `open()` misses it, `lstat()` finds the finished table.
    The third attempt reads the table.
    """
    path = tmp_path / kept.FILENAME

    def placeholder() -> None:
        # As the writer makes it, and without `Path.open`, which is patched below.
        os.close(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600))

    calls = after_first_missing_stat(monkeypatch, path, placeholder)
    pending = placeholder_goes_at_first_open(monkeypatch, path, table("gpt-5"))
    assert kept.read(path) == ("read", (row(model="gpt-5"),))
    assert calls == [3] and not pending[0]


def test_a_path_that_cannot_be_asked_is_unreadable_after_one_attempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only a path that is present at the follow-up call is read again."""
    path = tmp_path / kept.FILENAME
    original = Path.stat
    calls = [0]

    def stat(self: Path, *, follow_symlinks: bool = True) -> os.stat_result:
        if self != path:
            return original(self, follow_symlinks=follow_symlinks)
        if not follow_symlinks:
            raise PermissionError("private text")
        calls[0] += 1
        raise FileNotFoundError

    def lstat(self: Path) -> os.stat_result:
        return stat(self, follow_symlinks=False)

    monkeypatch.setattr(Path, "stat", stat)
    monkeypatch.setattr(Path, "lstat", lstat)
    assert kept.read(path) == ("unreadable", ())
    assert calls == [1]


def test_a_table_replaced_between_stat_and_open_is_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / kept.FILENAME
    path.write_text(table("gpt-5"))
    staged = tmp_path / "staged"
    staged.write_text(table("gpt-5", "gpt-6"))
    before_first_open(monkeypatch, path, lambda: os.replace(staged, path))
    assert kept.read(path) == ("read", (row(model="gpt-5"), row(model="gpt-6")))


def test_a_table_that_replaces_the_placeholder_before_open_is_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / kept.FILENAME
    path.write_bytes(b"")
    staged = tmp_path / "staged"
    staged.write_text(table("gpt-5"))
    before_first_open(monkeypatch, path, lambda: os.replace(staged, path))
    assert kept.read(path) == ("read", (row(model="gpt-5"),))


def test_a_placeholder_that_went_before_open_is_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / kept.FILENAME
    path.write_bytes(b"")
    before_first_open(monkeypatch, path, path.unlink)
    assert kept.read(path) == ("absent", ())


def test_an_absent_path_is_asked_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / kept.FILENAME
    calls = after_first_missing_stat(monkeypatch, path, lambda: None)
    assert kept.read(path) == ("absent", ())
    assert calls == [1]


def test_a_dangling_link_is_unreadable_after_a_fixed_number_of_attempts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / kept.FILENAME
    path.symlink_to(tmp_path / "missing")
    calls = after_first_missing_stat(monkeypatch, path, lambda: None)
    assert kept.read(path) == ("unreadable", ())
    # One writer alone can cost three attempts; the count stays small and fixed.
    assert calls == [kept.READ_ATTEMPTS] and 3 <= kept.READ_ATTEMPTS <= 8


def test_a_dangling_link_that_appears_is_unreadable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / kept.FILENAME
    after_first_missing_stat(monkeypatch, path, lambda: path.symlink_to(tmp_path / "missing"))
    assert kept.read(path) == ("unreadable", ())


def test_a_path_that_changes_at_every_attempt_is_unreadable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The reader gives up after its fixed number of attempts, however the path goes on changing."""
    path = tmp_path / kept.FILENAME
    original = Path.stat
    calls = [0]

    def stat(self: Path, *, follow_symlinks: bool = True) -> os.stat_result:
        if self != path:
            return original(self, follow_symlinks=follow_symlinks)
        if not follow_symlinks:
            # The follow-up call finds a file that the next first call misses again.
            return original(tmp_path, follow_symlinks=False)
        calls[0] += 1
        raise FileNotFoundError

    monkeypatch.setattr(Path, "stat", stat)

    def lstat(self: Path) -> os.stat_result:
        return stat(self, follow_symlinks=False)

    monkeypatch.setattr(Path, "lstat", lstat)
    assert kept.read(path) == ("unreadable", ())
    assert calls == [kept.READ_ATTEMPTS]


@pytest.mark.parametrize(
    ("content", "state"),
    (
        (b"{not json", "unreadable"),
        (b'{"schema":"realornoise-days/1","rows":[],"other":1}\n', "unreadable"),
        (b"\xff\xfe", "unreadable"),
        (b"", "absent"),
    ),
)
def test_what_appears_is_judged_as_any_other_file(
    content: bytes, state: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / kept.FILENAME
    after_first_missing_stat(monkeypatch, path, lambda: path.write_bytes(content))
    assert kept.read(path) == (state, ())


def test_a_directory_that_appears_is_unreadable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / kept.FILENAME
    after_first_missing_stat(monkeypatch, path, path.mkdir)
    assert kept.read(path) == ("unreadable", ())


@pytest.mark.parametrize("difference", (0, 1))
def test_the_size_limit_holds_for_a_table_that_appears(
    difference: int, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / kept.FILENAME
    content = table("gpt-5")
    monkeypatch.setattr(kept, "MAX_BYTES", len(content.encode()) - difference)
    after_first_missing_stat(monkeypatch, path, lambda: path.write_text(content))
    assert kept.read(path)[0] == ("unreadable" if difference else "read")


def test_a_run_that_starts_while_another_installs_the_table_keeps_its_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two runs on a new keep directory: the second one's first read meets the first one's table."""
    history(tmp_path)
    other_root = tmp_path / "other-run"
    history(other_root, model="gpt-6")
    path = tmp_path / ".realornoise" / kept.FILENAME
    read = kept.read
    started = False

    def first_read_races(target: Path) -> tuple[kept.KeptState, tuple[kept.KeptRow, ...]]:
        nonlocal started
        if not started:
            started = True
            # A complete second CLI run writes between this read's first and second call.
            after_first_missing_stat(
                monkeypatch, path, lambda: invoke(other_root, "--keep-dir", str(path.parent))
            )
        return read(target)

    monkeypatch.setattr(kept, "read", first_read_races)
    record, output = invoke(tmp_path, "--keep")
    assert record.kept_table == "read"
    assert "The kept day table could not be read" not in output
    state, rows = read(path)
    assert state == "read"
    assert {r.model for r in rows} == {"gpt-5-sol", "gpt-6"}
