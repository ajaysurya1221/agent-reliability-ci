from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

import arci.cli as cli_module
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


@pytest.mark.parametrize(("flag", "expected"), [((), False), (("--all-steps",), True)])
def test_diff_all_steps_flag_is_dispatched(
    monkeypatch: pytest.MonkeyPatch, flag: tuple[str, ...], expected: bool
) -> None:
    observed: list[bool] = []

    def fake_diff(run_dir: str, trial_a: str, trial_b: str, all_steps: bool) -> int:
        assert (run_dir, trial_a, trial_b) == ("run", "left", "right")
        observed.append(all_steps)
        return 0

    monkeypatch.setattr(cli_module, "_cmd_diff", fake_diff)

    assert main(["diff", "run", "left", "right", *flag]) == 0
    assert observed == [expected]
