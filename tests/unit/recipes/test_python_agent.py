"""The Python-agent recipe (examples/recipes/python_agent), driven by its own README.

Every command comes out of the README's ```bash blocks: the list is pinned below, so a README
edit that adds, drops or changes a command fails here, and each `arci` command is run as
`python -P -m arci.cli` with a tmp copy of the tree as its working directory and no PYTHONPATH (the
console script's situation; ADR 0006 puts the copy on the child's import path). Nothing here imports
the recipe in-process: its `tests` package would collide with this repository's.

Not run here: `uv tool install` (network; the test uses this environment's arci) and
`arci run confirm.yaml` (800 trials; the orchestrator records that run). The confirmatory
descriptor is still written by the README's command and compiled.
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

import pytest

from arci.cli import smoke_followup, smoke_notice
from arci.descriptor import compile_descriptor
from arci.schema import GateDecision, Manifest, Outcome, TrialEnvelope, Verdict

ROOT = Path(__file__).resolve().parents[3]
RECIPE = ROOT / "examples" / "recipes" / "python_agent"
README = RECIPE / "README.md"
COMMITTED = RECIPE / "arci.yaml"

INIT = (
    "arci init checkout-retry --baseline app.v1:run --candidate app.v2:run"
    " --toolset tests.world:make_world --oracle tests.world:passed"
    ' --task \'{"order_id": "order-7"}\' --fault tool_timeout:reserve:0'
)
CONFIRM_INIT = (
    "arci init checkout-retry-n400 --baseline app.v1:run --candidate app.v2:run"
    " --toolset tests.world:make_world --oracle tests.world:passed"
    ' --task \'{"order_id": "order-7"}\' --fault tool_timeout:reserve:0'
    " --n 400 --out confirm.yaml"
)
SMOKE_RUN = "arci run arci.yaml"
PLAN = "arci plan --baseline-rate 0.95 --candidate-rate 0.75 --target-verdict BLOCK"
CONFIRM_RUN = "arci run confirm.yaml"
FAILING = "faults:00000:candidate"
DIAGNOSE = (
    f"arci diff runs/checkout-retry faults:00000:baseline {FAILING}",
    f"arci minimize runs/checkout-retry {FAILING} --out min.json",
    f"arci bundle runs/checkout-retry {FAILING} --out bundle.json --root ."
    " --include app/v2.py --include tests/world.py",
    "arci replay bundle.json",
)
SETUP = (
    "cp -R examples/recipes/python_agent checkout",
    "cd checkout",
    "rm arci.yaml",
)
INSTALL = "uv tool install agent-reliability-ci"
README_COMMANDS = (
    *SETUP,
    INSTALL,
    INIT,
    SMOKE_RUN,
    PLAN,
    CONFIRM_INIT,
    CONFIRM_RUN,
    *DIAGNOSE,
)


def _blocks(language: str) -> list[str]:
    text = README.read_text(encoding="utf-8")
    return re.findall(rf"^```{language}\n(.*?)^```$", text, flags=re.MULTILINE | re.DOTALL)


def readme_commands() -> tuple[str, ...]:
    """Every command in the README's bash blocks, in order, split on `&&`."""
    commands: list[str] = []
    for block in _blocks("bash"):
        for line in block.splitlines():
            if line.strip() and not line.lstrip().startswith("#"):
                commands += [part.strip() for part in line.split(" && ")]
    return tuple(commands)


def arci(command: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run one README `arci ...` command as the console script would, from `cwd`."""
    argv = shlex.split(command)
    assert argv[0] == "arci", command
    env = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    return subprocess.run(
        [sys.executable, "-P", "-m", "arci.cli", *argv[1:]],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


@dataclass(frozen=True)
class Smoke:
    copy: Path
    init: subprocess.CompletedProcess[str]
    run: subprocess.CompletedProcess[str]


@pytest.fixture(scope="module")
def smoke(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Smoke]:
    """The README's setup, then its first-screen command, once for the module."""
    commands = readme_commands()
    assert commands[: len(SETUP)] == SETUP
    copy = tmp_path_factory.mktemp("recipe") / "checkout"  # cp -R ... checkout && cd checkout
    shutil.copytree(RECIPE, copy, ignore=shutil.ignore_patterns("__pycache__", "runs"))
    (copy / "arci.yaml").unlink()  # rm arci.yaml
    init = arci(INIT, copy)
    run = arci(SMOKE_RUN, copy)
    yield Smoke(copy=copy, init=init, run=run)


def test_the_readme_commands_are_the_ones_these_tests_run() -> None:
    assert readme_commands() == README_COMMANDS
    first_screen = f"{INSTALL} && {INIT} && {SMOKE_RUN}"
    assert first_screen in README.read_text(encoding="utf-8").splitlines()
    assert "<<recorded run>>" in README.read_text(encoding="utf-8")


def test_init_writes_the_committed_descriptor_byte_for_byte(smoke: Smoke) -> None:
    assert smoke.init.returncode == 0, smoke.init.stderr
    assert smoke.init.stdout == f"{SMOKE_RUN}\n"
    assert smoke.init.stderr == ""
    assert (smoke.copy / "arci.yaml").read_bytes() == COMMITTED.read_bytes()


def test_the_smoke_run_is_inconclusive_with_a_sealed_store(smoke: Smoke) -> None:
    done = smoke.run
    # v1 survives the injected timeout; v2 loses every order that was not already held, but at
    # N=8 the interval on the difference still crosses the margin.
    assert done.returncode == 2, done.stderr[-2000:]
    assert done.stdout.strip().splitlines()[-1] == "VERDICT: INCONCLUSIVE (exit 2)"
    manifest = compile_descriptor(COMMITTED)
    assert done.stderr == f"{smoke_notice(manifest)}\n{smoke_followup(manifest)}\n"
    run_dir = smoke.copy / "runs" / "checkout-retry"
    stored = Manifest.model_validate_json((run_dir / "manifest.json").read_text("utf-8"))
    assert stored.validate_seal()
    assert stored == manifest
    trials = [
        TrialEnvelope.model_validate_json(line)
        for line in (run_dir / "trials.jsonl").read_text("utf-8").splitlines()
    ]
    assert len(trials) == 16 and all(trial.validate_seal() for trial in trials)
    by_arm = {
        arm: sum(t.outcome is Outcome.PASS for t in trials if t.arm == arm)
        for arm in ("baseline", "candidate")
    }
    assert (by_arm["baseline"], by_arm["candidate"]) == (8, 2)  # a drop, not a total collapse
    decision = GateDecision.model_validate_json((run_dir / "decision.json").read_text("utf-8"))
    assert decision.validate_seal()
    assert decision.verdict is Verdict.INCONCLUSIVE


def test_plan_then_the_confirmatory_descriptor(smoke: Smoke) -> None:
    planned = arci(PLAN, smoke.copy)
    assert planned.returncode == 0, planned.stderr
    assert "smallest tested N per arm meeting P(BLOCK) >= 0.8: 400 " in planned.stdout
    written = arci(CONFIRM_INIT, smoke.copy)
    assert written.returncode == 0, written.stderr
    assert written.stdout == f"{CONFIRM_RUN}\n"
    (addition,) = _blocks("yaml")
    with (smoke.copy / "confirm.yaml").open("a", encoding="utf-8") as handle:
        handle.write(addition)
    manifest = compile_descriptor(smoke.copy / "confirm.yaml")
    assert manifest.validate_seal()
    assert (manifest.experiment_id, manifest.n_per_arm) == ("checkout-retry-n400", 400)
    assert (manifest.base_seed, manifest.prior_runs) == (1000, ("checkout-retry",))
    smoke_manifest = compile_descriptor(COMMITTED)
    assert manifest.conditions == smoke_manifest.conditions
    assert (manifest.baseline, manifest.candidate) == (
        smoke_manifest.baseline,
        smoke_manifest.candidate,
    )


def test_diff_minimize_bundle_and_replay_a_failing_trial(smoke: Smoke) -> None:
    assert smoke.run.returncode == 2
    diff, minimize, bundle, replay = (arci(command, smoke.copy) for command in DIAGNOSE)
    for done in (diff, minimize, bundle, replay):
        assert done.returncode == 0, done.stderr[-2000:]
    assert "after_injection: tool_timeout" in diff.stdout
    assert 'left: tool_start tool="reserve"' in diff.stdout
    assert "kept: tool_timeout" in minimize.stdout
    assert json.loads((smoke.copy / "min.json").read_text("utf-8"))
    assert replay.stdout.startswith("REPRODUCED")
