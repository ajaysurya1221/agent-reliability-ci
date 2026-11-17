"""The bridge's `state.json` is replaced whole: a reader never sees a half-written file.

When the trial ends the boundary closes the tool server's input and, if it is still running,
stops it with SIGKILL; the grader reads `state.json` afterwards. Whatever a reader could see
at an instant of a write is what a kill at that instant leaves on disk, so the first two
tests read the file through a profile function while a write runs.

The probe sees only Python call and return boundaries, not every instant. The guarantee
itself comes from `os.replace` being an atomic rename inside one folder.
"""

from __future__ import annotations

import errno
import json
import stat
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from types import FrameType

import pytest
from pydantic import JsonValue

from arci.mcp_toolset_server import ToolSetServer, snapshot

# A lone surrogate passes `json.dumps(..., ensure_ascii=False)` and cannot be encoded as UTF-8,
# so the snapshot cannot be written. The new code fails at the encoding, before any file is
# touched; the old code had emptied `state.json` by then.
UNENCODABLE = "\ud800"


class StateToolSet:
    def __init__(self, value: JsonValue) -> None:
        self.value = value
        self.tools: Mapping[str, Callable[..., JsonValue]] = {"store": self.store}

    def store(self, value: JsonValue) -> JsonValue:
        self.value = value
        return {"stored": True}

    def snapshot(self) -> dict[str, JsonValue]:
        return {"value": self.value, "names": ["zoë", "日本"], "count": 3}


def _state(value: JsonValue) -> dict[str, JsonValue]:
    return {"value": value, "names": ["zoë", "日本"], "count": 3}


def _reads_during(action: Callable[[], object], workdir: Path) -> list[object]:
    """What the grader's reader returns at every call and return made while `action` runs."""
    seen: list[object] = []

    def probe(frame: FrameType, event: str, arg: object) -> None:
        del frame, event, arg
        try:
            seen.append(snapshot({}, str(workdir)))
        except Exception as exc:
            seen.append(f"reader raised {type(exc).__name__}")

    previous = sys.getprofile()
    sys.setprofile(probe)
    try:
        action()
    finally:
        sys.setprofile(previous)
    return seen


def _distinct(values: list[object]) -> list[object]:
    result: list[object] = []
    for value in values:
        if value not in result:
            result.append(value)
    return result


def test_a_reader_sees_no_file_or_a_complete_file_during_the_first_write(tmp_path: Path) -> None:
    toolset = StateToolSet("first")

    seen = _reads_during(lambda: ToolSetServer(toolset, tmp_path, None), tmp_path)

    assert _distinct(seen) == [{}, _state("first")]


def test_a_reader_sees_the_old_or_the_new_state_during_a_later_write(tmp_path: Path) -> None:
    toolset = StateToolSet("old")
    server = ToolSetServer(toolset, tmp_path, None)
    toolset.value = "new"

    seen = _reads_during(server.save_snapshot, tmp_path)

    assert _distinct(seen) == [_state("old"), _state("new")]


def test_a_failed_first_write_leaves_no_file(tmp_path: Path) -> None:
    with pytest.raises(UnicodeEncodeError):
        ToolSetServer(StateToolSet(UNENCODABLE), tmp_path, None)

    assert list(tmp_path.iterdir()) == []
    assert snapshot({}, str(tmp_path)) == {}


def test_a_failed_write_keeps_the_last_complete_state(tmp_path: Path) -> None:
    server = ToolSetServer(StateToolSet("kept"), tmp_path, None)

    response = server.handle(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "store", "arguments": {"value": UNENCODABLE}},
        }
    )

    assert response is not None
    assert response["error"] == {"code": -32603, "message": "snapshot failed"}
    assert [path.name for path in tmp_path.iterdir()] == ["state.json"]
    assert snapshot({}, str(tmp_path)) == _state("kept")


def test_a_temporary_write_that_fails_part_way_is_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    toolset = StateToolSet("kept")
    server = ToolSetServer(toolset, tmp_path, None)
    toolset.value = "lost"
    plain_write = Path.write_bytes
    partly_written: list[Path] = []

    def write_half_then_fail(self: Path, data: bytes) -> int:
        plain_write(self, data[: len(data) // 2])
        partly_written.append(self)
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(Path, "write_bytes", write_half_then_fail)
    with pytest.raises(OSError):
        server.save_snapshot()
    monkeypatch.undo()

    assert partly_written == [tmp_path / "state.json.tmp"]
    assert [path.name for path in tmp_path.iterdir()] == ["state.json"]
    assert snapshot({}, str(tmp_path)) == _state("kept")


def test_a_move_that_fails_leaves_no_temporary_file(tmp_path: Path) -> None:
    (tmp_path / "state.json").mkdir()

    with pytest.raises(OSError):
        ToolSetServer(StateToolSet("blocked"), tmp_path, None)

    assert [path.name for path in tmp_path.iterdir()] == ["state.json"]
    assert list((tmp_path / "state.json").iterdir()) == []


def test_the_file_has_the_same_bytes_and_mode_as_a_plain_text_write(tmp_path: Path) -> None:
    workdir = tmp_path / "trial"
    ToolSetServer(StateToolSet("bytes"), workdir, None)
    reference = tmp_path / "reference.json"
    payload = json.dumps(_state("bytes"), sort_keys=True, ensure_ascii=False, allow_nan=False)
    reference.write_text(payload, encoding="utf-8")

    written = workdir / "state.json"
    assert [path.name for path in workdir.iterdir()] == ["state.json"]
    assert written.read_bytes() == payload.encode("utf-8")
    assert stat.S_IMODE(written.stat().st_mode) == stat.S_IMODE(reference.stat().st_mode)
