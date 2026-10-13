"""The Python-agent recipe (examples/recipes/python_agent), driven by its own README.

Every command comes out of the README's ```bash blocks: the list is pinned below, so a README
edit that adds, drops or changes a command fails here, and each `arci` command is run as
`python -P -m arci.cli` with a tmp copy of the tree as its working directory and no PYTHONPATH (the
console script's situation; ADR 0006 puts the copy on the child's import path). Nothing here imports
the recipe in-process: its `tests` package would collide with this repository's.

Not run here: `uv tool install` (network; the test uses this environment's arci) and
`arci run confirm.yaml` (800 trials, about 80 s; the README's recorded run shows it). The
confirmatory descriptor is still written by the README's command and compiled.

The bundle names `app/__init__.py` and `tests/__init__.py` so that its `app` and `tests` are
regular packages: replay puts the bundle directory first on the import path, and a regular package
there shadows the working tree's. Without the two `__init__.py` files the bundled directories are
only namespace portions, the working tree's regular packages win, and replay runs the tree's
current sources instead of the bundled ones; two tests below show both cases.
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
DOC = ROOT / "docs" / "recipes" / "python-agent.md"
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
    " --include app/__init__.py --include app/v2.py --include tests/__init__.py"
    " --include tests/world.py",
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


RECORDED_LABEL = (
    "Recorded on the maintainer's machine during the v0.8.0 sprint (2026-10-13; 15-core Apple"
    " Silicon Mac; ARCI at the sprint's descriptor lane)"
)


def _recorded_blocks(path: Path) -> list[str]:
    """The ```text blocks of the "Recorded run" section, in order."""
    text = path.read_text(encoding="utf-8")
    section = text.split("\n## Recorded run\n", 1)[1].split("\n## What this does not show", 1)[0]
    assert " ".join(section.split()).count(RECORDED_LABEL) == 1, path
    return re.findall(r"^```text\n(.*?)^```$", section, flags=re.MULTILINE | re.DOTALL)


@pytest.mark.parametrize("path", [README, DOC], ids=["readme", "doc"])
def test_the_recorded_run_sections(path: Path) -> None:
    init, smoke_run, plan, confirm = _recorded_blocks(path)
    assert init.splitlines() == [f"$ {INIT}", SMOKE_RUN]
    assert smoke_run.startswith(f"$ /usr/bin/time -p {SMOKE_RUN}\n")
    manifest = compile_descriptor(COMMITTED)  # the notices as this ARCI prints them, verbatim
    assert smoke_notice(manifest) in smoke_run.splitlines()
    assert smoke_followup(manifest) in smoke_run.splitlines()
    assert "## Condition: faults" in smoke_run
    assert "| Successes | 8 | 2 |" in smoke_run
    assert any(line.startswith("real ") for line in smoke_run.splitlines())  # wall time
    assert "VERDICT: INCONCLUSIVE (exit 2)" in smoke_run
    assert plan.startswith(f"$ {PLAN}\n")
    assert "smallest tested N per arm meeting P(BLOCK) >= 0.8: 400 " in plan
    assert "| 400 | 800 | 0.000 | 0.828 | 0.172 | yes |" in plan
    assert "No pairing:" in plan
    assert confirm.startswith(f"$ {CONFIRM_INIT}\n")
    assert "base_seed: 1000" in confirm and 'prior_runs: ["checkout-retry"]' in confirm
    assert "## Condition: faults" in confirm and "| n | 400 | 400 |" in confirm
    assert "VERDICT: BLOCK (exit 1)" in confirm
    earlier = confirm.split("## Earlier runs on this candidate", 1)[1].split("\n[...]", 1)[0]
    assert "- `checkout-retry`" in earlier.splitlines()
    assert any(line.startswith("real ") for line in confirm.splitlines())


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
    run_dir = smoke.copy / "runs" / "checkout-retry"
    assert done.stderr == (
        f"{smoke_notice(manifest)}\n{smoke_followup(manifest)}\nrun store: {run_dir.resolve()}\n"
    )
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


GIVE_UP = 'return {"confirmed": False}  # gives up on the first fault'
BARE_BUNDLE = (
    f"arci bundle runs/checkout-retry {FAILING} --out bare.json --root ."
    " --include app/v2.py --include tests/world.py"
)


@dataclass(frozen=True)
class Edited:
    copy: Path
    bundled: subprocess.CompletedProcess[str]
    bare: subprocess.CompletedProcess[str]


@pytest.fixture(scope="module")
def edited(smoke: Smoke, tmp_path_factory: pytest.TempPathFactory) -> Iterator[Edited]:
    """Bundle the failing trial twice, then change the working tree under both bundles.

    `bundle.json` is the README's bundle (with both `__init__.py`); `bare.json` omits them. Before
    any edit, `bare.json` reproduces on the unedited tree, so its later NOT_REPRODUCED comes from
    the edits and not from the bundle itself. The edits would each turn the failure into something
    else if they ran: v2 raises instead of returning after the fault (same tool calls, so no
    recording miss, but a crash), and the oracle passes every final state. (v1's body is not used
    as the edit: if the tree's v1 ran, its second `reserve` call would not be in the recording, so
    replay would report INVALID, exit 3, a recording miss rather than a changed outcome.)
    """
    copy = tmp_path_factory.mktemp("edited") / "checkout"
    shutil.copytree(smoke.copy, copy, ignore=shutil.ignore_patterns("__pycache__"))
    for command in (DIAGNOSE[2], BARE_BUNDLE):
        done = arci(command, copy)
        assert done.returncode == 0, done.stderr[-2000:]
    unedited = arci("arci replay bare.json", copy)
    assert unedited.returncode == 0, unedited.stdout + unedited.stderr[-2000:]
    assert unedited.stdout.startswith("REPRODUCED")
    v2 = copy / "app" / "v2.py"
    source = v2.read_text(encoding="utf-8")
    assert source.count(GIVE_UP) == 1
    v2.write_text(source.replace(GIVE_UP, 'raise RuntimeError("the working tree")'), "utf-8")
    with (copy / "tests" / "world.py").open("a", encoding="utf-8") as handle:
        handle.write(
            "\n\ndef passed(task: object, final_state: object) -> bool:\n    return True\n"
        )
    yield Edited(
        copy=copy,
        bundled=arci("arci replay bundle.json", copy),
        bare=arci("arci replay bare.json", copy),
    )


def test_replay_runs_the_bundled_sources_not_the_working_tree(edited: Edited) -> None:
    assert edited.bundled.returncode == 0, edited.bundled.stdout + edited.bundled.stderr[-2000:]
    assert edited.bundled.stdout.startswith("REPRODUCED")


def test_without_the_init_files_replay_runs_the_edited_tree(edited: Edited) -> None:
    # The control: the bundle's bare `app/` and `tests/` are namespace portions, so the working
    # tree's regular packages win and the edited sources run; the failure does not reproduce.
    assert edited.bare.returncode == 1, edited.bare.stdout + edited.bare.stderr[-2000:]
    assert edited.bare.stdout.startswith("NOT_REPRODUCED")
