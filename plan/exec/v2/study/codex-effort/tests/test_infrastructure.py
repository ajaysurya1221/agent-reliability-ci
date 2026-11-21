"""Exercise process limits and executable provenance using local stand-ins."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import driver
import grade
from run_trial import executable_identity, run_trial
from test_study import ITEMS, STANDIN, script


def test_helper_timeout_and_git_prompts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_TERMINAL_PROMPT", "1")
    cmd = [str(grade.PYTHON), "-c", "import os; print(os.environ['GIT_TERMINAL_PROMPT'])"]
    assert grade.bounded(cmd, tmp_path).stdout == b"0\n"
    monkeypatch.setattr(grade, "INFRA_SECONDS", 0.1)
    with pytest.raises(subprocess.TimeoutExpired):
        grade.bounded([str(grade.PYTHON), "-c", "import time; time.sleep(30)"], tmp_path)


@pytest.mark.parametrize("stage", ["archive", "tar", "diff", "apply"])
def test_trial_infrastructure_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stage: str
) -> None:
    ticket = ITEMS[0]
    monkeypatch.setenv("CODEX_BIN", str(STANDIN))
    script(tmp_path, monkeypatch, [ticket], "correct")
    bounded = grade.bounded

    def delayed(argv: list[str], cwd: Path, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        if stage in argv or (stage == "tar" and Path(argv[0]).name == "tar"):
            raise subprocess.TimeoutExpired(argv, grade.INFRA_SECONDS)
        data = kwargs.get("data")
        assert data is None or isinstance(data, bytes)
        return bounded(argv, cwd, data=data)

    monkeypatch.setattr(grade, "bounded", delayed)
    row = run_trial(ticket, "baseline", 1, 1, tmp_path / "private", tmp_path)
    assert row.outcome == "error" and "timed out" in row.grader_evidence
    record = tmp_path / f"r01-{ticket['id']}-baseline" / "grade.json"
    assert json.loads(record.read_bytes())["outcome"] == "error"


@pytest.mark.parametrize("stage", ["ls-remote", "preflight", "verdict"])
def test_driver_infrastructure_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stage: str
) -> None:
    work = tmp_path / "private"
    registration = tmp_path / "registration"
    registration.touch()
    monkeypatch.setattr(driver, "REGISTER", registration)
    monkeypatch.setattr(driver, "MARKER", tmp_path / "local")
    monkeypatch.setattr(driver, "SHARED_MARKER", tmp_path / "shared")
    monkeypatch.setattr(driver, "OUTPUT", tmp_path / "out")
    monkeypatch.setattr(driver, "PRIVATE_WORK", work)

    def registration_digest(tip: str) -> str:
        assert tip == "abc"
        return "test digest"

    monkeypatch.setattr(driver, "check_registration", registration_digest)
    monkeypatch.setenv("CODEX_BIN", str(STANDIN))
    bounded = grade.bounded
    delayed_calls: list[str] = []

    def delayed(
        argv: list[str],
        cwd: Path,
        *,
        seconds: float | None = None,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[bytes]:
        if "ls-remote" in argv:
            which = "ls-remote"
        elif "pytest" in argv:
            which = "preflight"
            assert seconds == driver.PREFLIGHT_SECONDS
            assert env and env["RUN5_CHECK_CONFINEMENT"] == "1" and not env["PYTEST_ADDOPTS"]
        elif "verdict" in argv:
            which = "verdict"
        else:
            return bounded(argv, cwd, seconds=seconds, env=env)
        if which == stage:
            delayed_calls.append(which)
            raise subprocess.TimeoutExpired(argv, seconds or grade.INFRA_SECONDS)
        return subprocess.CompletedProcess(argv, 0, b"abc\trefs/heads/v2/phase0\n", b"")

    def verdict_only(*args: object, **kwargs: object) -> None:
        driver.verdict(driver.OUTPUT, 1)
        pytest.fail("timed-out verdict returned")

    monkeypatch.setattr(driver, "bounded", delayed)
    monkeypatch.setattr(grade, "bounded", delayed)
    monkeypatch.setattr(driver, "campaign", verdict_only)
    with pytest.raises(SystemExit) as caught:
        driver.live(work, 1)
    assert caught.value.code == 3 and delayed_calls == [stage]
    if stage == "verdict":
        stop = json.loads((driver.OUTPUT / "stop.json").read_bytes())
        assert stop["status"] == "ERROR" and "timed out" in stop["reason"]
    else:
        assert not driver.SHARED_MARKER.exists()


@pytest.mark.parametrize("optional_package", [False, True])
def test_npm_native_executable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, optional_package: bool
) -> None:
    pkg = tmp_path / "node_modules/@openai/codex"
    launcher = pkg / "bin/codex.js"
    launcher.parent.mkdir(parents=True)
    launcher.write_text("#!/usr/bin/env node\n")
    launcher.chmod(0o755)
    cpu, npm_arch = ("aarch64", "arm64") if platform.machine() == "arm64" else ("x86_64", "x64")
    root = pkg
    if optional_package:
        root = pkg.parent / ("codex-darwin-" + npm_arch)
        root.mkdir()
        (root / "package.json").write_text("{}")
    native = root / "vendor" / (cpu + "-apple-darwin") / "bin/codex"
    native.parent.mkdir(parents=True)
    native.write_bytes(b"native stand-in")
    monkeypatch.setenv("CODEX_BIN", str(launcher))
    identity = executable_identity(dict(os.environ))
    assert identity.native == str(native)
    assert identity.executable_sha256 == hashlib.sha256(launcher.read_bytes()).hexdigest()
    assert identity.native_executable_sha256 == hashlib.sha256(native.read_bytes()).hexdigest()
    assert identity.native_executable_sha256 != identity.executable_sha256
