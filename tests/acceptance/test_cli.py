"""The command line: exit codes are the CI contract. FROZEN."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from arci.schema import GateDecision, ReplayBundle
from tests.acceptance.helpers import COND_NOISY, manifest

pytestmark = pytest.mark.acceptance
REPO = Path(__file__).resolve().parents[2]


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


def _write_manifest(tmp_path: Path, **kw: object) -> Path:
    path = tmp_path / "manifest.json"
    path.write_text(manifest(**kw).model_dump_json())  # pyright: ignore[reportArgumentType]
    return path


@pytest.mark.parametrize(
    ("kw", "code", "verdict"),
    [
        ({"n_per_arm": 12}, 1, "BLOCK"),  # 12/12 vs 0/12
        ({"n_per_arm": 45, "candidate": "good_agent"}, 0, "PASS"),  # 45/45 vs 45/45
        ({"n_per_arm": 6}, 2, "INCONCLUSIVE"),  # 6/6 vs 0/6 is not enough evidence
        ({"n_per_arm": 2, "oracle": "raising_oracle"}, 3, "ERROR"),
    ],
)
def test_run_exit_code_is_the_verdict(
    tmp_path: Path, kw: dict[str, object], code: int, verdict: str
) -> None:
    done = arci(
        "run", str(_write_manifest(tmp_path, **kw)), "--out", "runs", "--workers", "8", cwd=tmp_path
    )
    assert done.returncode == code, done.stderr[-2000:]
    assert done.stdout.strip().splitlines()[-1].startswith(f"VERDICT: {verdict}")
    run_dir = tmp_path / "runs" / "exp-acceptance"
    decision = GateDecision.model_validate_json((run_dir / "decision.json").read_text())
    assert decision.validate_seal() and decision.verdict.value == verdict


def test_gate_recomputes_from_the_store_and_writes_reports(tmp_path: Path) -> None:
    arci(
        "run",
        str(_write_manifest(tmp_path, n_per_arm=12, prior_runs=("exp-earlier",))),
        "--out",
        "runs",
        "--workers",
        "8",
        cwd=tmp_path,
    )
    run_dir = tmp_path / "runs" / "exp-acceptance"
    summary = tmp_path / "step-summary.md"
    done = arci(
        "gate",
        str(run_dir),
        "--junit",
        "junit.xml",
        "--markdown",
        "report.md",
        cwd=tmp_path,
        extra_env={"GITHUB_STEP_SUMMARY": str(summary)},
    )
    assert done.returncode == 1
    report = (tmp_path / "report.md").read_text()
    assert report.strip().splitlines()[-1].startswith("VERDICT: BLOCK")
    assert "exp-earlier" in report  # earlier runs on this candidate are never hidden
    assert "fetch_timeout" in report and "Clopper" in report
    assert summary.read_text() == report
    suite = ET.parse(tmp_path / "junit.xml").getroot()
    assert suite.tag in {"testsuite", "testsuites"}
    assert int(next(suite.iter("testsuite")).attrib["failures"]) >= 1


def test_gate_refuses_a_tampered_store(tmp_path: Path) -> None:
    arci(
        "run",
        str(_write_manifest(tmp_path, n_per_arm=12)),
        "--out",
        "runs",
        "--workers",
        "8",
        cwd=tmp_path,
    )
    trials = tmp_path / "runs" / "exp-acceptance" / "trials.jsonl"
    lines = trials.read_text().splitlines()
    first = json.loads(lines[0])
    first["outcome"] = "PASS" if first["outcome"] != "PASS" else "FAIL"
    trials.write_text("\n".join([json.dumps(first), *lines[1:]]) + "\n")
    done = arci("gate", str(tmp_path / "runs" / "exp-acceptance"), cwd=tmp_path)
    assert done.returncode == 3
    assert done.stdout.strip().splitlines()[-1].startswith("VERDICT: ERROR")


def test_bundle_replay_diff_and_minimize_commands(tmp_path: Path) -> None:
    arci(
        "run",
        str(_write_manifest(tmp_path, n_per_arm=3, conditions=(COND_NOISY,))),
        "--out",
        "runs",
        "--workers",
        "6",
        cwd=tmp_path,
    )
    run_dir = str(tmp_path / "runs" / "exp-acceptance")
    failing, passing = "noisy:00000:candidate", "noisy:00000:baseline"

    made = arci(
        "bundle",
        run_dir,
        failing,
        "--out",
        "bundle.json",
        "--root",
        str(REPO),
        "--include",
        "tests/__init__.py",
        "--include",
        "tests/acceptance/__init__.py",
        "--include",
        "tests/acceptance/fixture_agents.py",
        cwd=tmp_path,
    )
    assert made.returncode == 0, made.stderr[-2000:]
    bundle = ReplayBundle.model_validate_json((tmp_path / "bundle.json").read_text())
    assert bundle.validate_seal() and len(bundle.files) == 3

    replayed = arci("replay", "bundle.json", cwd=tmp_path)
    assert replayed.returncode == 0 and "REPRODUCED" in replayed.stdout
    assert arci("bundle", run_dir, passing, "--out", "nope.json", cwd=tmp_path).returncode != 0

    diffed = arci("diff", run_dir, passing, failing, cwd=tmp_path)
    assert diffed.returncode == 0 and "tool_timeout" in diffed.stdout

    shrunk = arci("minimize", run_dir, failing, "--out", "min.json", cwd=tmp_path)
    assert shrunk.returncode == 0, shrunk.stderr[-2000:]
    assert "1-minimal" in shrunk.stdout and "tool_timeout" in shrunk.stdout
    small = ReplayBundle.model_validate_json((tmp_path / "min.json").read_text())
    assert [f.name for f in small.spec.condition.faults] == ["tool_timeout"]
    assert arci("replay", "min.json", cwd=tmp_path).returncode == 0


def test_replay_exit_codes(tmp_path: Path) -> None:
    (tmp_path / "garbage.json").write_text("{}")
    assert arci("replay", "garbage.json", cwd=tmp_path).returncode == 3
