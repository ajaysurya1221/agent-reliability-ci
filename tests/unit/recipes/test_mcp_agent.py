"""The MCP command-agent recipe (examples/recipes/mcp_agent) and docs/recipes/mcp-inspector.md.

Everything runs from a tmp copy of the tree with the copy as the working directory, never from this
repository (the recipe's `world` and `agent` modules resolve through the current directory).
The committed `arci.yaml` says `python`, resolved on PATH; the copy's three argv lists are rewritten
to start with `sys.executable` instead, so the trials use this environment's interpreter, which has
arci installed. No network and no npx: the Inspector step itself is the orchestrator's.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from arci.cli import smoke_notice
from arci.descriptor import compile_descriptor
from arci.schema import GateDecision, Manifest, Outcome, TrialEnvelope, Verdict

ROOT = Path(__file__).resolve().parents[3]
RECIPE = ROOT / "examples" / "recipes" / "mcp_agent"
DOC = ROOT / "docs" / "recipes" / "mcp-inspector.md"
PYTHON_ARGV = 'argv: ["python",'
RUN = "arci run arci.yaml"
DIAGNOSE = (
    "arci diff runs/mcp-fetch-retry fetch-error:00000:baseline fetch-error:00000:candidate",
    "arci minimize runs/mcp-fetch-retry fetch-error:00000:candidate --out min.json",
    "arci bundle runs/mcp-fetch-retry fetch-error:00000:candidate --out bundle.json --root ."
    " --include agent.py --include world.py",
    "arci replay bundle.json",
)
INSPECTOR = (
    "npx @modelcontextprotocol/inspector --cli --config mcp.inspector.json --server env"
    " --method tools/list"
)
DOC_COMMANDS = (
    "cp -R examples/recipes/mcp_agent mcp-recipe",
    "cd mcp-recipe",
    "python -m venv .venv",
    ". .venv/bin/activate",
    "pip install agent-reliability-ci",
    INSPECTOR,
    "python - <<'EOF'",
    RUN,
    *DIAGNOSE,
)


def _doc() -> str:
    return DOC.read_text(encoding="utf-8")


def doc_commands() -> tuple[str, ...]:
    """The first line of every command in the doc's bash blocks, split on `&&`."""
    commands: list[str] = []
    for block in re.findall(r"^```bash\n(.*?)^```$", _doc(), flags=re.MULTILINE | re.DOTALL):
        heredoc = False
        for line in block.splitlines():
            if heredoc:
                heredoc = line != "EOF"
                continue
            heredoc = line.endswith("<<'EOF'")
            commands += [part.strip() for part in line.split(" && ") if part.strip()]
    return tuple(commands)


def preflight_script() -> str:
    (script,) = re.findall(r"^python - <<'EOF'\n(.*?)^EOF$", _doc(), flags=re.MULTILINE | re.DOTALL)
    return script


def _env(**extra: str) -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    return {**env, **extra}


def arci(command: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    argv = shlex.split(command)
    assert argv[0] == "arci", command
    return subprocess.run(
        [sys.executable, "-P", "-m", "arci.cli", *argv[1:]],
        cwd=cwd,
        env=_env(),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def _copy(parent: Path) -> Path:
    copy = parent / "mcp-recipe"
    shutil.copytree(RECIPE, copy, ignore=shutil.ignore_patterns("__pycache__", "runs"))
    descriptor = copy / "arci.yaml"
    text = descriptor.read_text(encoding="utf-8")
    assert text.count(PYTHON_ARGV) == 3  # baseline, candidate and mcp_server
    descriptor.write_text(
        text.replace(PYTHON_ARGV, f"argv: [{json.dumps(sys.executable)},"), encoding="utf-8"
    )
    return copy


@dataclass(frozen=True)
class Run:
    copy: Path
    done: subprocess.CompletedProcess[str]


@pytest.fixture(scope="module")
def run(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Run]:
    copy = _copy(tmp_path_factory.mktemp("mcp"))
    yield Run(copy=copy, done=arci(RUN, copy))


def test_the_doc_commands_are_the_ones_these_tests_run() -> None:
    assert doc_commands() == DOC_COMMANDS
    assert "Server's protocol version is not supported: 2026-07-28" in _doc()
    readme = (RECIPE / "README.md").read_text(encoding="utf-8")
    for command in (INSPECTOR, RUN, DIAGNOSE[0]):
        assert command in readme.splitlines()


def test_the_manual_preflight_drives_the_raw_bridge(tmp_path: Path) -> None:
    copy = _copy(tmp_path)
    config: Any = json.loads((copy / "mcp.inspector.json").read_text(encoding="utf-8"))
    assert config["mcpServers"]["env"]["env"] == {"PYTHONPATH": "."}
    done = subprocess.run(
        [sys.executable, "-"],
        input=preflight_script(),
        cwd=copy,
        env=_env(),
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    *replies, last = done.stdout.splitlines()
    assert last == "server exit 0 "
    initialize, listed, called = (json.loads(line) for line in replies)
    assert initialize["result"]["protocolVersion"] == "2026-07-28"
    assert [tool["name"] for tool in listed["result"]["tools"]] == ["fetch", "store"]
    assert listed["result"]["tools"][0]["inputSchema"]["required"] == ["key"]
    # Seed 0 is a flaky upstream: the environment's own error, not an injected one.
    assert called["id"] == 3
    assert called["result"] == {
        "resultType": "complete",
        "content": [{"type": "text", "text": "TimeoutError: upstream transient timeout"}],
        "isError": True,
    }
    state = json.loads((copy / "preflight-state" / "state.json").read_text(encoding="utf-8"))
    assert state["stored"] == {}


def test_the_faulted_run_blocks_with_a_sealed_store(run: Run) -> None:
    done = run.done
    # fragile fails all 8 trials under the injected error and retry passes all 8: a total
    # collapse, the one result a smoke design of 8 per arm can decide.
    assert done.returncode == 1, done.stderr[-2000:]
    assert done.stdout.strip().splitlines()[-1] == "VERDICT: BLOCK (exit 1)"
    manifest = compile_descriptor(run.copy / "arci.yaml")
    assert done.stderr == f"{smoke_notice(manifest)}\n"
    run_dir = run.copy / "runs" / "mcp-fetch-retry"
    stored = Manifest.model_validate_json((run_dir / "manifest.json").read_text("utf-8"))
    assert stored.validate_seal() and stored == manifest
    trials = [
        TrialEnvelope.model_validate_json(line)
        for line in (run_dir / "trials.jsonl").read_text("utf-8").splitlines()
    ]
    assert len(trials) == 16 and all(trial.validate_seal() for trial in trials)
    for arm, passes in (("baseline", 8), ("candidate", 0)):
        mine = [trial for trial in trials if trial.arm == arm]
        assert sum(trial.outcome is Outcome.PASS for trial in mine) == passes
        assert all(trial.outcome is not Outcome.ERROR for trial in mine)
        assert all(trial.recording for trial in mine)
        fetches = [r for trial in mine for r in trial.recording if r.tool == "fetch"]
        assert fetches, arm
    decision = GateDecision.model_validate_json((run_dir / "decision.json").read_text("utf-8"))
    assert decision.validate_seal() and decision.verdict is Verdict.BLOCK


def test_diff_minimize_bundle_and_replay(run: Run) -> None:
    assert run.done.returncode == 1
    diff, minimize, bundle, replay = (arci(command, run.copy) for command in DIAGNOSE)
    for done in (diff, minimize, bundle, replay):
        assert done.returncode == 0, done.stderr[-2000:]
    assert "after_injection: tool_error_once" in diff.stdout
    assert 'left: tool_start tool="fetch"' in diff.stdout
    assert "kept: tool_error_once" in minimize.stdout
    assert replay.stdout.startswith("REPRODUCED")
