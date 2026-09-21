from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from arci.cli import main


@pytest.mark.parametrize(
    "command", ("run", "gate", "report", "bundle", "replay", "diff", "minimize")
)
def test_subcommand_help_works(command: str) -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "arci.cli", command, "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0
    assert completed.stderr == ""
    assert completed.stdout.startswith(f"usage: arci {command}")


def test_user_error_returns_three_without_a_traceback(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["not-a-command"]) == 3
    captured = capsys.readouterr()
    assert "invalid choice" in captured.err
    assert "Traceback" not in captured.err


def test_malformed_replay_is_invalid(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bundle = tmp_path / "bundle.json"
    bundle.write_text("{}", encoding="utf-8")

    assert main(["replay", str(bundle)]) == 3
    captured = capsys.readouterr()
    assert captured.out.startswith("INVALID:")
    assert "Traceback" not in captured.err
