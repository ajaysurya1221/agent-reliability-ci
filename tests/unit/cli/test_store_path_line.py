"""Task 16: `arci run` names its run store on stderr; stdout and other commands are unchanged."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from arci.gate import decide
from arci.report import render_markdown
from arci.storage import load_run
from tests.acceptance.helpers import manifest

REPO = Path(__file__).resolve().parents[3]


def arci(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": str(REPO)}
    env.pop("GITHUB_STEP_SUMMARY", None)
    return subprocess.run(
        [sys.executable, "-m", "arci.cli", *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )


def test_run_prints_the_store_path_on_stderr_only(tmp_path: Path) -> None:
    built = manifest(n_per_arm=6)  # 6/6 vs 0/6 under a timeout: INCONCLUSIVE
    (tmp_path / "manifest.json").write_text(built.model_dump_json(), encoding="utf-8")

    done = arci("run", "manifest.json", "--out", "runs", "--workers", "8", cwd=tmp_path)
    assert done.returncode == 2, done.stderr[-2000:]
    run_dir = tmp_path / "runs" / built.experiment_id
    store_line = f"run store: {run_dir.resolve()}"
    assert Path(store_line.removeprefix("run store: ")).is_absolute()
    # The line is stderr's last, and appears exactly once; stdout never carries it.
    assert done.stderr.endswith(f"\n{store_line}\n")
    assert done.stderr.count("run store:") == 1
    assert "run store:" not in done.stdout
    assert done.stdout.strip().splitlines()[-1] == "VERDICT: INCONCLUSIVE (exit 2)"
    stored, trials = load_run(run_dir)
    markdown = render_markdown(stored, decide(stored, trials), trials)
    assert done.stdout == markdown + ("" if markdown.endswith("\n") else "\n")

    report = arci("report", str(run_dir), cwd=tmp_path)
    assert (report.returncode, report.stdout, report.stderr) == (0, done.stdout, "")
    gate = arci("gate", str(run_dir), cwd=tmp_path)
    assert (gate.returncode, gate.stdout, gate.stderr) == (2, done.stdout, "")
