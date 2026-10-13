"""Task 05: `arci run` names a smoke design on stderr, and nothing else changes."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

import arci.cli as cli_module
from arci.cli import main, smoke_followup, smoke_notice
from arci.gate import decide
from arci.planning import verdict_table
from arci.report import render_markdown
from arci.schema import Condition, Manifest, Verdict
from arci.storage import load_run
from tests.acceptance.helpers import COND_CEILING, COND_CLEAN, COND_TIMEOUT, manifest

REPO = Path(__file__).resolve().parents[3]
DEFAULT_LINE = (
    "SMOKE DESIGN: n_per_arm=6 (alpha 0.05, delta 0.1, K=1): under the default rule two "
    "perfect arms cannot PASS below N=42 and a total collapse cannot BLOCK below N=8; expect "
    "INCONCLUSIVE. Plan a confirmatory N: arci plan --baseline-rate P --candidate-rate P "
    "--target-verdict BLOCK"
)
FOLLOWUP_6 = (
    "INCONCLUSIVE at n_per_arm=6 is the expected smoke result; choose a confirmatory N with "
    "arci plan before re-running."
)
THRESHOLDS = re.compile(
    r"cannot PASS below N=(\d+) and a total collapse cannot BLOCK below N=(\d+)"
)


def arci(
    *args: str, cwd: Path, extra_env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": str(REPO), **(extra_env or {})}
    return subprocess.run(
        [sys.executable, "-m", "arci.cli", *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )


def _with(base: Manifest, **changes: object) -> Manifest:
    data = base.model_dump(exclude={"record_sha256", "schema_version"})
    data.update(changes)
    return Manifest.create(**data)


# --- the real run -------------------------------------------------------------------------------


def test_n6_prints_two_stderr_lines_and_leaves_stdout_and_reports_alone(tmp_path: Path) -> None:
    built = manifest(n_per_arm=6)  # 6/6 vs 0/6 under a timeout: INCONCLUSIVE
    path = tmp_path / "manifest.json"
    path.write_text(built.model_dump_json(), encoding="utf-8")
    summary = tmp_path / "summary.md"

    done = arci("run", "manifest.json", "--out", "runs", "--workers", "8", cwd=tmp_path)
    assert done.returncode == 2, done.stderr[-2000:]
    assert done.stderr == f"{DEFAULT_LINE}\n{FOLLOWUP_6}\n"
    assert done.stdout.strip().splitlines()[-1] == "VERDICT: INCONCLUSIVE (exit 2)"
    assert "SMOKE" not in done.stdout

    # The Markdown report is byte-for-byte the renderer's, and so is what the Action summarises
    # (it tees `arci run` stdout; `arci gate` writes GITHUB_STEP_SUMMARY).
    run_dir = tmp_path / "runs" / built.experiment_id
    stored, trials = load_run(run_dir)
    markdown = render_markdown(stored, decide(stored, trials), trials)
    assert done.stdout == markdown + ("" if markdown.endswith("\n") else "\n")
    report = arci("report", str(run_dir), cwd=tmp_path)
    assert (report.returncode, report.stdout, report.stderr) == (0, done.stdout, "")
    gate = arci("gate", str(run_dir), cwd=tmp_path, extra_env={"GITHUB_STEP_SUMMARY": str(summary)})
    assert (gate.returncode, gate.stdout) == (2, done.stdout)
    assert summary.read_text(encoding="utf-8") == markdown
    assert "SMOKE" not in (run_dir / "decision.json").read_text(encoding="utf-8")


# --- before the run: in-process, with the run itself stubbed ------------------------------------


class _Stop(RuntimeError):
    pass


def _stderr_before_the_run(
    built: Manifest,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> str:
    def stop(*_args: object, **_kwargs: object) -> None:
        raise _Stop("the run started")

    path = tmp_path / "manifest.json"
    path.write_text(built.model_dump_json(), encoding="utf-8")
    monkeypatch.setattr(cli_module, "run_experiment", stop)
    assert main(["run", str(path), "--out", str(tmp_path / "runs")]) == 3
    captured = capsys.readouterr()
    assert captured.out == ""
    lines = captured.err.splitlines()
    assert lines[-1] == "error: _Stop: the run started"
    return "\n".join(lines[:-1])


@pytest.mark.parametrize(
    ("n", "conditions", "expected"),
    [
        (6, (COND_TIMEOUT,), DEFAULT_LINE),
        (99, (COND_TIMEOUT,), DEFAULT_LINE.replace("n_per_arm=6", "n_per_arm=99")),
        (100, (COND_TIMEOUT,), ""),
        (200, (COND_TIMEOUT,), ""),
        (6, (COND_CEILING,), ""),  # no gating condition: nothing is gated, nothing to say
        (6, (COND_TIMEOUT, COND_CEILING), DEFAULT_LINE),  # K counts gating conditions only
    ],
)
def test_the_notice_comes_before_the_run_only_below_100(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    n: int,
    conditions: tuple[Condition, ...],
    expected: str,
) -> None:
    built = manifest(n_per_arm=n, conditions=conditions)
    assert _stderr_before_the_run(built, tmp_path, monkeypatch, capsys) == expected


def test_a_design_outside_the_planner_uses_the_default_rule_and_says_so() -> None:
    two = manifest(n_per_arm=6, conditions=(COND_TIMEOUT, COND_CLEAN))
    newcombe = _with(manifest(n_per_arm=6), interval_method="newcombe")
    looks = _with(manifest(n_per_arm=6), looks=(3, 6))
    default_rule = (
        "under the default rule (default rule: alpha 0.05, delta 0.1, K=1, one look; this "
        "design is outside the planner's domain) two perfect arms cannot PASS below N=42 and a "
        "total collapse cannot BLOCK below N=8; expect INCONCLUSIVE."
    )
    assert smoke_notice(two) == (
        f"SMOKE DESIGN: n_per_arm=6 (alpha 0.05, delta 0.1, K=2): {default_rule} Plan a "
        "confirmatory N: arci plan --baseline-rate P --candidate-rate P --target-verdict BLOCK"
    )
    for design in (two, newcombe, looks):
        notice = smoke_notice(design)
        assert notice is not None
        assert default_rule in notice
    one_look = _with(manifest(n_per_arm=6), looks=(6,))
    assert smoke_notice(one_look) == DEFAULT_LINE


def test_the_followup_line() -> None:
    assert smoke_followup(manifest(n_per_arm=6)) == FOLLOWUP_6


# --- the thresholds are the gate's --------------------------------------------------------------


@pytest.mark.parametrize(("alpha", "delta"), [(0.05, 0.10), (0.01, 0.2), (0.1, 0.2), (0.2, 0.3)])
def test_printed_thresholds_agree_with_the_gate(alpha: float, delta: float) -> None:
    built = _with(manifest(n_per_arm=6, alpha=alpha), delta=delta)
    notice = smoke_notice(built)
    assert notice is not None
    assert f"(alpha {alpha:g}, delta {delta:g}, K=1)" in notice
    match = THRESHOLDS.search(notice)
    assert match is not None
    n_pass, n_block = int(match.group(1)), int(match.group(2))
    # At the printed N the outcome decides; at every smaller N it does not.
    assert verdict_table(n_pass, alpha=alpha, delta=delta)[n_pass][n_pass] is Verdict.PASS
    assert verdict_table(n_block, alpha=alpha, delta=delta)[n_block][0] is Verdict.BLOCK
    for n in range(1, n_pass):
        assert verdict_table(n, alpha=alpha, delta=delta)[n][n] is not Verdict.PASS
    for n in range(1, n_block):
        assert verdict_table(n, alpha=alpha, delta=delta)[n][0] is not Verdict.BLOCK


def test_unreachable_pass_is_stated_up_to_the_planner_bound() -> None:
    notice = smoke_notice(_with(manifest(n_per_arm=6), delta=0.01))
    assert notice is not None
    assert "two perfect arms cannot PASS at any N up to 400 and" in notice
