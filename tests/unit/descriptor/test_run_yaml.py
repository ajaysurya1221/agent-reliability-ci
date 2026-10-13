"""`arci run x.yaml` compiles, seals and runs; the run store and verdict match the JSON path."""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

from arci.cli import smoke_followup, smoke_notice
from arci.descriptor import compile_descriptor_text
from arci.schema import GateDecision, Manifest

REPO = Path(__file__).resolve().parents[3]
MOD = "tests.acceptance.fixture_agents"

DESCRIPTOR = f"""\
experiment_id: exp-yaml
task_id: store-the-answer
task: {{goal: store 42}}
toolset: {MOD}:make_world
oracle: {MOD}:oracle
baseline: {{label: A, agent: "{MOD}:good_agent", candidate_id: a}}
candidate: {{label: B, agent: "{MOD}:fragile_agent", candidate_id: b}}
conditions:
  - id: fetch_timeout
    fault: {{name: tool_timeout, tool: fetch, occurrence: 0}}
n_per_arm: 6
base_seed: 7
budgets: {{max_tool_calls: 20, max_seconds: 10.0}}
"""


def arci(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": str(REPO)}
    return subprocess.run(
        [sys.executable, "-m", "arci.cli", *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )


def test_run_yaml_matches_the_json_path(tmp_path: Path) -> None:
    compiled = compile_descriptor_text(DESCRIPTOR)
    yaml_dir, json_dir = tmp_path / "yaml", tmp_path / "json"
    yaml_dir.mkdir()
    json_dir.mkdir()
    (yaml_dir / "arci.yaml").write_text(DESCRIPTOR, encoding="utf-8")
    (json_dir / "manifest.json").write_text(compiled.model_dump_json(), encoding="utf-8")

    from_yaml = arci("run", "arci.yaml", "--out", "runs", "--workers", "8", cwd=yaml_dir)
    from_json = arci("run", "manifest.json", "--out", "runs", "--workers", "8", cwd=json_dir)

    assert from_yaml.returncode == 2, from_yaml.stderr[-2000:]  # 6/6 vs 0/6: INCONCLUSIVE
    assert from_json.returncode == 2, from_json.stderr[-2000:]
    # stderr carries the smoke-design notice (task 05), identical for both paths, then the line
    # naming each run's own store (task 16).
    notice = f"{smoke_notice(compiled)}\n{smoke_followup(compiled)}\n"
    for done, workdir in ((from_yaml, yaml_dir), (from_json, json_dir)):
        store_line = f"run store: {(workdir / 'runs' / compiled.experiment_id).resolve()}\n"
        assert done.stderr == notice + store_line
    last = from_yaml.stdout.strip().splitlines()[-1]
    assert last.startswith("VERDICT: INCONCLUSIVE")
    assert last == from_json.stdout.strip().splitlines()[-1]

    run_dir = yaml_dir / "runs" / "exp-yaml"
    stored = Manifest.model_validate_json((run_dir / "manifest.json").read_text())
    assert stored.validate_seal()
    assert stored == compiled
    assert (run_dir / "manifest.json").read_text() == compiled.model_dump_json(indent=2) + "\n"
    yaml_decision = GateDecision.model_validate_json((run_dir / "decision.json").read_text())
    json_decision = GateDecision.model_validate_json(
        (json_dir / "runs" / "exp-yaml" / "decision.json").read_text()
    )
    assert yaml_decision.record_sha256 == json_decision.record_sha256


def test_out_defaults_to_runs(tmp_path: Path) -> None:
    (tmp_path / "arci.yml").write_text(
        DESCRIPTOR.replace("n_per_arm: 6", "n_per_arm: 1"), encoding="utf-8"
    )
    done = arci("run", "arci.yml", cwd=tmp_path)
    assert done.returncode == 2, done.stderr[-2000:]
    assert done.stdout.strip().splitlines()[-1].startswith("VERDICT: ")
    assert (tmp_path / "runs" / "exp-yaml" / "manifest.json").is_file()
    assert (tmp_path / "runs" / "exp-yaml" / "decision.json").is_file()


def test_a_broken_descriptor_fails_before_any_trial(tmp_path: Path) -> None:
    (tmp_path / "arci.yaml").write_text(DESCRIPTOR + "n_per_arn: 3\n", encoding="utf-8")
    done = arci("run", "arci.yaml", cwd=tmp_path)
    assert done.returncode == 3
    assert done.stdout == ""
    assert done.stderr == (
        'error: CliError: descriptor arci.yaml:n_per_arn: unknown key "n_per_arn"\n'
    )
    assert not (tmp_path / "runs").exists()


def test_a_json_manifest_is_still_seal_checked(tmp_path: Path) -> None:
    compiled = compile_descriptor_text(DESCRIPTOR)
    tampered = compiled.model_copy(update={"n_per_arm": 5})
    (tmp_path / "manifest.json").write_text(tampered.model_dump_json(), encoding="utf-8")
    done = arci("run", "manifest.json", cwd=tmp_path)
    assert done.returncode == 3
    assert done.stderr == "error: CliError: manifest seal is invalid\n"


def test_the_cli_with_the_descriptor_never_imports_bench() -> None:
    script = textwrap.dedent(
        """
        import contextlib, io, sys
        from arci.cli import main
        with contextlib.redirect_stdout(io.StringIO()):
            code = main(["schema"])
        assert code == 0, code
        assert "arci.descriptor" in sys.modules
        loaded = sorted(m for m in sys.modules if m == "bench" or m.startswith("bench."))
        assert not loaded, loaded
        print("ok")
        """
    )
    completed = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=False
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == "ok\n"
