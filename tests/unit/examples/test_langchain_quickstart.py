"""Exercise the documented offline run and independently recompute its gate."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from fractions import Fraction
from pathlib import Path

import pytest

from arci.descriptor import loads_suite_descriptor
from arci.suite_stats import operating_characteristics, rule_of

if importlib.util.find_spec("langchain") is None:
    if os.environ.get("ARCI_REQUIRE_ADAPTERS") == "1":
        raise ImportError("ARCI_REQUIRE_ADAPTERS=1 requires LangChain")
    pytest.skip("optional LangChain extra is absent", allow_module_level=True)

EXAMPLE = Path(__file__).resolve().parents[3] / "examples" / "langchain_quickstart"


def offline_env() -> dict[str, str]:
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in {"PYTHONPATH", "ARCI_QUICKSTART_BASELINE", "ARCI_QUICKSTART_CANDIDATE"}
    }
    env["LANGSMITH_TRACING"] = "false"
    env["LANGSMITH_TRACING_V2"] = "false"
    return env


def arci(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-P", "-m", "arci.cli", *args],
        cwd=cwd,
        env=offline_env(),
        capture_output=True,
        text=True,
        timeout=115,
    )


def run_and_gate(project: Path) -> float:
    started = time.monotonic()
    run = arci(project, "run", "arci.yaml", "--workers", "4")
    elapsed = time.monotonic() - started
    assert run.returncode == 1, run.stdout + run.stderr
    stores = list((project / "runs").iterdir())
    assert len(stores) == 1
    decision = json.loads((stores[0] / "decision.json").read_text())
    assert decision["verdict"] == "BLOCK"
    assert decision["stopped_at_round"] == 1
    trials = [json.loads(line) for line in (stores[0] / "trials.jsonl").read_text().splitlines()]
    assert len(trials) == 192
    assert sum(t["outcome"] == "PASS" for t in trials if t["arm"] == "baseline") == 96
    assert sum(t["outcome"] == "PASS" for t in trials if t["arm"] == "candidate") == 48
    gate = arci(project, "gate", str(stores[0]))
    assert gate.returncode == 1, gate.stdout + gate.stderr
    assert "BLOCK" in gate.stdout
    assert elapsed < 120
    return elapsed


def test_quickstart_run_and_gate(tmp_path: Path) -> None:
    assert EXAMPLE.is_dir(), "quickstart example has not been implemented"
    project = tmp_path / "order-desk"
    shutil.copytree(EXAMPLE, project, ignore=shutil.ignore_patterns("__pycache__", "runs"))
    elapsed = run_and_gate(project)
    print(f"offline quickstart: BLOCK, round 1, 192 trials, {elapsed:.2f} seconds")


def test_offline_design_decides_with_certainty() -> None:
    assert (EXAMPLE / "arci.yaml").is_file()
    manifest = loads_suite_descriptor(
        (EXAMPLE / "arci.yaml").read_text(), str(EXAMPLE / "arci.yaml")
    )
    assert manifest.n_cells == 96
    # Both arms succeed in clean/empty; only baseline succeeds on timeout/error.
    zero, one = Fraction(0), Fraction(1)
    laws = [(one, zero, zero)] * 48 + [(zero, one, zero)] * 48
    oc = operating_characteristics(laws, rule_of(manifest))
    assert oc.p_block == 1
    assert oc.expected_pairs == 96
