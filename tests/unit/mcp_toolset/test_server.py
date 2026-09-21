from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import JsonValue

from arci.mcp_toolset_server import ToolSetServer, snapshot


class FixtureToolSet:
    def __init__(self) -> None:
        self.calls = 0
        self.value: JsonValue = None
        self.tools: Mapping[str, Callable[..., JsonValue]] = {
            "store": self.store,
            "boom": self.boom,
            "hidden": self.hidden,
            "setty": self.setty,
            "nan": self.nan,
            "pathy": self.pathy,
        }

    def store(self, value: JsonValue) -> JsonValue:
        print("tool noise")
        self.calls += 1
        self.value = value
        return {"stored": True}

    def boom(self) -> JsonValue:
        self.calls += 1
        raise TimeoutError("temporary\nproblem")

    def hidden(self) -> JsonValue:
        raise AssertionError("hidden tool was called")

    def setty(self) -> JsonValue:
        return {1, 2}  # pyright: ignore[reportReturnType]

    def nan(self) -> JsonValue:
        return float("nan")

    def pathy(self) -> JsonValue:
        raise FileNotFoundError("/tmp/arci-pathy-12345/cache/item.json")

    def snapshot(self) -> dict[str, JsonValue]:
        print("snapshot noise")
        return {"calls": self.calls, "value": self.value}


def make_toolset(task: dict[str, JsonValue], seed: int) -> FixtureToolSet:
    del task, seed
    print("factory noise")
    return FixtureToolSet()


def _request(request_id: int, method: str, params: dict[str, JsonValue] | None = None) -> str:
    return json.dumps(
        {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}}
    )


def test_subset_exception_mapping_and_snapshot_file(tmp_path: Path) -> None:
    task_file = tmp_path / "task.json"
    task_file.write_text('{"goal": "test"}', encoding="utf-8")
    requests = "\n".join(
        (
            _request(1, "initialize"),
            _request(2, "tools/list"),
            _request(3, "tools/call", {"name": "store", "arguments": {"value": 7}}),
            _request(4, "tools/call", {"name": "boom", "arguments": {}}),
        )
    )
    process = subprocess.run(
        (
            sys.executable,
            "-P",
            "-m",
            "arci.mcp_toolset_server",
            "--toolset",
            f"{__name__}:make_toolset",
            "--workdir",
            str(tmp_path),
            "--seed",
            "9",
            "--tools",
            "store,boom",
            "--task-file",
            str(task_file),
        ),
        input=requests + "\n",
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, "PYTHONPATH": os.pathsep.join(sys.path)},
    )
    replies: list[dict[str, Any]] = [json.loads(line) for line in process.stdout.splitlines()]
    assert "factory noise" in process.stderr
    assert "tool noise" in process.stderr
    assert "snapshot noise" in process.stderr
    assert replies[0]["result"]["protocolVersion"] == "2026-07-28"
    assert [tool["name"] for tool in replies[1]["result"]["tools"]] == ["store", "boom"]
    assert json.loads(replies[2]["result"]["content"][0]["text"]) == {"stored": True}
    assert replies[3]["result"] == {
        "resultType": "complete",
        "content": [{"type": "text", "text": "TimeoutError: temporary problem"}],
        "isError": True,
    }
    assert snapshot({}, str(tmp_path)) == {"calls": 2, "value": 7}


def test_snapshot_missing_file_is_empty(tmp_path: Path) -> None:
    assert snapshot({}, str(tmp_path)) == {}


def test_snapshot_is_written_at_startup(tmp_path: Path) -> None:
    process = subprocess.run(
        (
            sys.executable,
            "-P",
            "-m",
            "arci.mcp_toolset_server",
            "--toolset",
            f"{__name__}:make_toolset",
            "--workdir",
            str(tmp_path),
            "--seed",
            "4",
        ),
        input="",
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, "PYTHONPATH": os.pathsep.join(sys.path)},
    )
    assert process.stdout == ""
    assert snapshot({}, str(tmp_path)) == {"calls": 0, "value": None}


def test_non_json_tool_returns_are_internal_environment_errors(tmp_path: Path) -> None:
    server = ToolSetServer(FixtureToolSet(), tmp_path, None)
    for name in ("setty", "nan"):
        response = server.handle(
            {
                "jsonrpc": "2.0",
                "id": name,
                "method": "tools/call",
                "params": {"name": name, "arguments": {}},
            }
        )
        assert response is not None
        assert response["error"] == {
            "code": -32603,
            "message": "tool returned invalid JSON",
        }


def test_snapshot_write_failure_is_an_internal_environment_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    server = ToolSetServer(FixtureToolSet(), tmp_path, None)

    def fail_snapshot() -> None:
        raise OSError("disk failed")

    monkeypatch.setattr(server, "save_snapshot", fail_snapshot)
    response = server.handle(
        {
            "jsonrpc": "2.0",
            "id": "store",
            "method": "tools/call",
            "params": {"name": "store", "arguments": {"value": 3}},
        }
    )
    assert response is not None
    assert response["error"] == {"code": -32603, "message": "snapshot failed"}


def test_tool_exception_diagnostic_scrubs_run_specific_paths(tmp_path: Path) -> None:
    server = ToolSetServer(FixtureToolSet(), tmp_path, None)
    response = server.handle(
        {
            "jsonrpc": "2.0",
            "id": "path",
            "method": "tools/call",
            "params": {"name": "pathy", "arguments": {}},
        }
    )
    assert response is not None
    data = cast(dict[str, Any], response)
    text = data["result"]["content"][0]["text"]
    assert "arci-pathy" not in str(text)
    assert "<path>" in str(text)
