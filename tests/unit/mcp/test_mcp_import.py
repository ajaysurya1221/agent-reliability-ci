"""`arci.mcp_boundary` imports without a binary stdout; frames go to the original stdout."""

from __future__ import annotations

import contextlib
import importlib
import io
import subprocess
import sys
from pathlib import Path

import pytest

import arci
import arci.mcp_boundary as original


def test_import_succeeds_when_stdout_has_no_buffer(monkeypatch: pytest.MonkeyPatch) -> None:
    replaced = io.StringIO()
    assert not hasattr(replaced, "buffer")
    # monkeypatch restores sys.stdout, the sys.modules entry and the package attribute afterwards.
    monkeypatch.setattr(sys, "stdout", replaced)
    monkeypatch.delitem(sys.modules, "arci.mcp_boundary")
    monkeypatch.setattr(arci, "mcp_boundary", original)
    fresh = importlib.import_module("arci.mcp_boundary")
    assert fresh is not original
    assert vars(fresh)["_PROTOCOL"] is None
    assert replaced.getvalue() == ""


def test_frames_go_to_the_original_stdout_even_under_redirect_stdout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binary, diverted = io.BytesIO(), io.StringIO()
    monkeypatch.setattr(sys, "__stdout__", io.TextIOWrapper(binary, encoding="utf-8"))
    monkeypatch.setattr(original, "_PROTOCOL", None)
    with contextlib.redirect_stdout(diverted):
        vars(original)["_frame"]("nonce", "ready", ok=True)
    assert binary.getvalue() == b'{"kind":"ready","nonce":"nonce","ok":true}\n'
    assert diverted.getvalue() == ""
    assert vars(original)["_PROTOCOL"] is None


def test_a_fresh_interpreter_writes_frames_to_its_stdout_pipe(tmp_path: Path) -> None:
    # As the runner starts the boundary: a new interpreter (`-P`) whose stdout is a pipe.
    done = subprocess.run(
        [sys.executable, "-P", "-c", "from arci.mcp_boundary import _frame; _frame('n', 'ready')"],
        cwd=tmp_path,
        capture_output=True,
        timeout=60,
        check=False,
    )
    assert (done.returncode, done.stdout) == (0, b'{"kind":"ready","nonce":"n"}\n'), done.stderr
