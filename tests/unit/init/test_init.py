"""`arci init` (ADR 0008) through the command line, from a copy of a small sample project.

Every command that reaches the reference check runs as `python -P -m arci.cli` with the copy as
its working directory and no PYTHONPATH: the console script's situation, in which the parent's
sys.path lacks the current directory and only the ADR 0006 rule lets `app` and `tests` resolve.
(The copy's own `tests` package would collide with this repository's if the parent's path were
used, which is why nothing here imports the sample project in-process.)
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from arci.cli import main, smoke_followup, smoke_notice
from arci.descriptor import compile_descriptor
from arci.init import HEADER
from arci.schema import Bucket, FaultSpec, Manifest

SAMPLE = Path(__file__).resolve().parent / "fixtures" / "sample_project"
REFS: tuple[str, ...] = (
    "--baseline",
    "app.v1:run",
    "--candidate",
    "app.v2:run",
    "--toolset",
    "tests.world:make_world",
    "--oracle",
    "tests.world:passed",
)
INIT: tuple[str, ...] = ("init", "checkout-retry", *REFS)
PREFIX = "error: CliError: init: "

EXPECTED_CLEAN = (
    HEADER
    + """\
experiment_id: "checkout-retry"
task: {}
toolset: "tests.world:make_world"
oracle: "tests.world:passed"
baseline:
  label: "baseline"
  agent: "app.v1:run"
candidate:
  label: "candidate"
  agent: "app.v2:run"
conditions:
  - id: "clean"
n_per_arm: 8
"""
)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    copy = tmp_path / "project"
    shutil.copytree(SAMPLE, copy, ignore=shutil.ignore_patterns("__pycache__"))
    return copy


def arci(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    env = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    return subprocess.run(
        [sys.executable, "-P", "-m", "arci.cli", *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )


def _refused(done: subprocess.CompletedProcess[str], detail: str) -> None:
    assert done.returncode == 3, done.stderr
    assert done.stdout == ""
    assert done.stderr == f"{PREFIX}{detail}\n"


def _files(directory: Path) -> set[str]:
    return {path.name for path in directory.iterdir()}


# --- success ------------------------------------------------------------------------------------


def test_init_writes_the_descriptor_and_prints_only_the_next_command(project: Path) -> None:
    before = _files(project)
    done = arci(*INIT, cwd=project)
    assert done.returncode == 0, done.stderr
    assert done.stdout == "arci run arci.yaml\n"
    assert done.stderr == ""
    assert _files(project) - before == {"arci.yaml"}  # nothing staged is left behind
    text = (project / "arci.yaml").read_text(encoding="utf-8")
    assert text == EXPECTED_CLEAN
    assert text.splitlines()[:5] == HEADER.splitlines()

    manifest = compile_descriptor(project / "arci.yaml")
    assert manifest.validate_seal()
    assert manifest.n_per_arm == 8
    assert manifest.task_id == manifest.experiment_id == "checkout-retry"
    assert manifest.task == {}
    assert (manifest.baseline.label, manifest.candidate.label) == ("baseline", "candidate")
    assert (manifest.baseline.agent, manifest.candidate.agent) == ("app.v1:run", "app.v2:run")
    assert manifest.baseline.candidate_id == manifest.candidate.candidate_id == ""
    assert [c.condition_id for c in manifest.conditions] == ["clean"]
    assert manifest.conditions[0].faults == ()
    assert (manifest.alpha, manifest.delta, manifest.base_seed) == (0.05, 0.10, 0)
    assert (manifest.interval_method, manifest.looks) == ("clopper_pearson", ())
    mode = stat.S_IMODE((project / "arci.yaml").stat().st_mode)
    umask = os.umask(0o022)
    os.umask(umask)
    assert mode == 0o666 & ~umask  # an ordinary new file, not mkstemp's 0600


def test_faults_compose_one_condition_in_order(project: Path) -> None:
    done = arci(
        *INIT,
        "--fault",
        "tool_timeout:reserve",
        "--fault",
        "empty_result",
        "--fault",
        "tool_error_once:reserve:2",
        "--n",
        "12",
        cwd=project,
    )
    assert done.returncode == 0, done.stderr
    text = (project / "arci.yaml").read_text(encoding="utf-8")
    assert (
        """\
conditions:
  - id: "faults"
    faults:
      - name: "tool_timeout"
        bucket: "falsify"
        tool: "reserve"
        occurrence: 0
      - name: "empty_result"
        bucket: "falsify"
        occurrence: 0
      - name: "tool_error_once"
        bucket: "falsify"
        tool: "reserve"
        occurrence: 2
n_per_arm: 12
"""
        in text
    )
    manifest = compile_descriptor(project / "arci.yaml")
    assert len(manifest.conditions) == 1
    assert manifest.conditions[0].condition_id == "faults"
    assert manifest.conditions[0].faults == (
        FaultSpec(name="tool_timeout", bucket=Bucket.FALSIFY, tool="reserve", at_occurrence=0),
        FaultSpec(name="empty_result", bucket=Bucket.FALSIFY, tool=None, at_occurrence=0),
        FaultSpec(name="tool_error_once", bucket=Bucket.FALSIFY, tool="reserve", at_occurrence=2),
    )


def test_task_strings_are_quoted_so_yaml_cannot_coerce_them(project: Path) -> None:
    task = '{"flag": "yes", "none": "null", "octal": "010", "date": "2026-10-13", "n": 3}'
    done = arci(*INIT, "--task", task, cwd=project)
    assert done.returncode == 0, done.stderr
    text = (project / "arci.yaml").read_text(encoding="utf-8")
    assert (
        'task: {"flag": "yes", "none": "null", "octal": "010", "date": "2026-10-13", "n": 3}\n'
        in text
    )
    for line in text.splitlines()[5:]:
        key, _, value = line.strip().removeprefix("- ").partition(": ")
        assert value == "" or value[0] in '"{' or value.isdecimal(), (key, value)
    assert compile_descriptor(project / "arci.yaml").task == {
        "flag": "yes",
        "none": "null",
        "octal": "010",
        "date": "2026-10-13",
        "n": 3,
    }


def test_task_file_is_read_as_utf8_json(project: Path) -> None:
    (project / "task.json").write_text('{"order_id": "ordre-é"}', encoding="utf-8")
    done = arci(*INIT, "--task-file", "task.json", cwd=project)
    assert done.returncode == 0, done.stderr
    assert compile_descriptor(project / "arci.yaml").task == {"order_id": "ordre-é"}


def test_the_next_command_is_shell_quoted(project: Path) -> None:
    (project / "my dir").mkdir()
    done = arci(*INIT, "--out", "my dir/exp.yml", cwd=project)
    assert done.returncode == 0, done.stderr
    assert done.stdout == "arci run 'my dir/exp.yml'\n"
    assert (project / "my dir" / "exp.yml").is_file()


def test_force_replaces_an_existing_regular_file(project: Path) -> None:
    (project / "arci.yaml").write_text("old\n", encoding="utf-8")
    done = arci(*INIT, "--force", cwd=project)
    assert done.returncode == 0, done.stderr
    assert (project / "arci.yaml").read_text(encoding="utf-8") == EXPECTED_CLEAN


# --- the reference check, in a child ------------------------------------------------------------


@pytest.mark.parametrize(
    ("change", "detail"),
    [
        (
            ("--baseline", "app.v9:run"),
            "--baseline app.v9:run: module not importable; importing app.v9 raised "
            "ModuleNotFoundError: No module named 'app.v9'; check module and dependencies",
        ),
        (
            ("--candidate", "app.v2:runn"),
            "--candidate app.v2:runn: module app.v2 has no attribute runn; check the function name",
        ),
        (
            ("--baseline", "app.v1:NAME"),
            "--baseline app.v1:NAME: NAME is not callable; reference a function",
        ),
        (
            ("--oracle", "tests.world:TRANSIENT_SHARE"),
            "--oracle tests.world:TRANSIENT_SHARE: TRANSIENT_SHARE is not callable; "
            "reference a function",
        ),
        (
            ("--toolset", "tests.nowhere:make_world"),
            "--toolset tests.nowhere:make_world: module not importable; importing tests.nowhere "
            "raised ModuleNotFoundError: No module named 'tests.nowhere'; check module and "
            "dependencies",
        ),
    ],
)
def test_the_reference_error_classes(project: Path, change: tuple[str, str], detail: str) -> None:
    args: list[str] = list(INIT)
    args[args.index(change[0]) + 1] = change[1]
    _refused(arci(*args, cwd=project), detail)
    assert not (project / "arci.yaml").exists()


def test_a_fault_tool_the_toolset_does_not_advertise(project: Path) -> None:
    done = arci(*INIT, "--fault", "tool_timeout:charge:0", cwd=project)
    _refused(
        done,
        "--fault tool_timeout:charge:0: tool charge absent from --toolset tests.world:make_world; "
        "choose an advertised tool (reserve)",
    )
    assert not (project / "arci.yaml").exists()


def test_references_are_checked_in_order(project: Path) -> None:
    args: list[str] = list(INIT)
    args[args.index("--toolset") + 1] = "tests.nowhere:make_world"
    args[args.index("--candidate") + 1] = "app.v2:gone"
    _refused(
        arci(*args, cwd=project),
        "--candidate app.v2:gone: module app.v2 has no attribute gone; check the function name",
    )


# --- end to end ---------------------------------------------------------------------------------


def test_the_console_script_parent_lacks_the_cwd(project: Path) -> None:
    # The premise of ADR 0006: under -P and no PYTHONPATH, the parent's sys.path has no cwd.
    probe = "import os, sys; print(os.getcwd() in sys.path or '' in sys.path)"
    env = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    done = subprocess.run(
        [sys.executable, "-P", "-c", probe],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert done.stdout == "False\n"


def test_init_then_run_from_the_sample_project(project: Path) -> None:
    assert arci(*INIT, cwd=project).returncode == 0
    done = arci("run", "arci.yaml", cwd=project)
    # 8/8 against a candidate that loses about a third of its orders: INCONCLUSIVE at N=8.
    assert done.returncode == 2, done.stderr[-2000:]
    assert done.stdout.strip().splitlines()[-1] == "VERDICT: INCONCLUSIVE (exit 2)"
    manifest = compile_descriptor(project / "arci.yaml")
    assert done.stderr == f"{smoke_notice(manifest)}\n{smoke_followup(manifest)}\n"
    run_dir = project / "runs" / "checkout-retry"
    stored = Manifest.model_validate_json((run_dir / "manifest.json").read_text())
    assert stored.validate_seal()
    assert stored == manifest
    assert (run_dir / "decision.json").is_file()
    # The trials ran: the candidate lost some orders, so the store is not all errors.
    report = arci("report", str(run_dir), cwd=project)
    assert report.returncode == 0, report.stderr
    assert report.stderr == ""


# --- in-process checks: nothing reaches a child ---------------------------------------------------


def _main(
    args: list[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> tuple[int, str, str]:
    monkeypatch.chdir(tmp_path)
    code = main(args)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


@pytest.mark.parametrize(
    ("args", "detail"),
    [
        (
            [*INIT, "--task", "{}", "--task-file", "t.json"],
            "--task and --task-file are mutually exclusive; give one",
        ),
        ([*INIT, "--n", "0"], "--n must be an integer from 1 to 10000, got 0"),
        ([*INIT, "--n", "10001"], "--n must be an integer from 1 to 10000, got 10001"),
        ([*INIT, "--n", "eight"], "--n must be an integer from 1 to 10000, got eight"),
        (
            [*INIT, "--out", "arci.json"],
            "--out arci.json: must end in .yaml or .yml "
            "(arci run reads any other path as a manifest JSON)",
        ),
        (
            ["init", "_bad", *REFS],
            "experiment id _bad must match [A-Za-z0-9][A-Za-z0-9._-]* (it names the run directory)",
        ),
        (
            ["init", "has space", *REFS],
            'experiment id "has space" must match [A-Za-z0-9][A-Za-z0-9._-]* (it names the run '
            "directory)",
        ),
        (
            ["init", "e", *REFS[:7], "tests.world"],
            "--oracle tests.world: invalid reference; expected module:function",
        ),
        (
            ["init", "e", "--baseline", "app/v1.py:run", *REFS[2:]],
            "--baseline app/v1.py:run: invalid reference; expected module:function",
        ),
        ([*INIT, "--task", "[1]"], "--task: must be a JSON object, got an array"),
        (
            [*INIT, "--task", "{"],
            "--task: invalid JSON (Expecting property name enclosed in "
            "double quotes: line 1 column 2 (char 1))",
        ),
        ([*INIT, "--task", '{"x": NaN}'], "--task: invalid JSON (NaN is not a JSON number)"),
        ([*INIT, "--task", '{"x": 1e999}'], "--task: invalid JSON (1e999 is out of range)"),
        (
            [*INIT, "--task-file", "missing.json"],
            "--task-file missing.json: cannot read: No such file or directory",
        ),
        (
            [*INIT, "--fault", "tool_crash"],
            "--fault tool_crash: unknown fault tool_crash; expected one of tool_timeout, "
            "tool_error_once, empty_result (a custom module:function fault is written by hand "
            "in the descriptor)",
        ),
        (
            [*INIT, "--fault", "faults.custom:make"],
            "--fault faults.custom:make: unknown fault faults.custom; expected one of "
            "tool_timeout, tool_error_once, empty_result (a custom module:function fault is "
            "written by hand in the descriptor)",
        ),
        (
            [*INIT, "--fault", "tool_timeout:reserve:0:1"],
            "--fault tool_timeout:reserve:0:1: expected NAME[:TOOL[:OCC]]",
        ),
        (
            [*INIT, "--fault", "tool_timeout:reserve:-1"],
            "--fault tool_timeout:reserve:-1: occurrence -1 must be an integer from 0 to "
            "1000000000",
        ),
        (
            [*INIT, "--fault", "tool_timeout:reserve:1000000001"],
            "--fault tool_timeout:reserve:1000000001: occurrence 1000000001 must be an integer "
            "from 0 to 1000000000",
        ),
        (
            [*INIT, "--fault", "tool_timeout:reserve:" + "9" * 5000],
            f"--fault tool_timeout:reserve:{'9' * 5000}: occurrence {'9' * 5000} must be an "
            "integer from 0 to 1000000000",
        ),
        ([*INIT, "--n", "9" * 5000], f"--n must be an integer from 1 to 10000, got {'9' * 5000}"),
        (
            ["init", "e" * 201, *REFS],
            "experiment id has 201 characters; at most 200 (it names the run directory)",
        ),
        (
            [*INIT, "--out", "no/such/dir/arci.yaml"],
            "output directory no/such/dir does not exist",
        ),
    ],
)
def test_syntax_errors_are_one_line_before_any_child(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    args: list[str],
    detail: str,
) -> None:
    # The references point nowhere importable from tmp_path: reaching the child would fail with
    # a different message, so each expected line proves the in-process check came first.
    code, out, err = _main(args, tmp_path, monkeypatch, capsys)
    assert (code, out, err) == (3, "", f"{PREFIX}{detail}\n")
    assert _files(tmp_path) == set()


def test_the_in_process_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "arci.yaml").write_text("keep\n", encoding="utf-8")
    bad_everything = [
        "init",
        "bad id",
        "--baseline",
        "nope",
        *REFS[2:],
        "--task",
        "[",
        "--fault",
        "x",
    ]
    _, _, err = _main(bad_everything, tmp_path, monkeypatch, capsys)
    assert err.startswith(f"{PREFIX}experiment id ")
    _, _, err = _main(["init", "ok", *bad_everything[2:]], tmp_path, monkeypatch, capsys)
    assert err.startswith(f"{PREFIX}--baseline nope: invalid reference")
    _, _, err = _main(["init", "ok", *REFS, *bad_everything[-4:]], tmp_path, monkeypatch, capsys)
    assert err.startswith(f"{PREFIX}--task: invalid JSON")
    _, _, err = _main(["init", "ok", *REFS, "--fault", "x"], tmp_path, monkeypatch, capsys)
    assert err.startswith(f"{PREFIX}--fault x: unknown fault")
    _, _, err = _main(["init", "ok", *REFS], tmp_path, monkeypatch, capsys)
    assert err == f"{PREFIX}output arci.yaml exists; use --force to replace it\n"
    assert (tmp_path / "arci.yaml").read_text(encoding="utf-8") == "keep\n"


@pytest.mark.parametrize("force", [False, True])
def test_a_directory_or_symlink_is_never_replaced(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    force: bool,
) -> None:
    flags = ["--force"] if force else []
    (tmp_path / "dir.yaml").mkdir()
    target = tmp_path / "target.yaml"
    target.write_text("target\n", encoding="utf-8")
    (tmp_path / "link.yaml").symlink_to(target)
    (tmp_path / "dangling.yaml").symlink_to(tmp_path / "missing.yaml")

    _, _, err = _main([*INIT, "--out", "dir.yaml", *flags], tmp_path, monkeypatch, capsys)
    assert err == f"{PREFIX}output dir.yaml is a directory; it is never replaced\n"
    _, _, err = _main([*INIT, "--out", "link.yaml", *flags], tmp_path, monkeypatch, capsys)
    assert err == f"{PREFIX}output link.yaml is a symlink; it is never replaced\n"
    _, _, err = _main([*INIT, "--out", "dangling.yaml", *flags], tmp_path, monkeypatch, capsys)
    assert err == f"{PREFIX}output dangling.yaml is a symlink; it is never replaced\n"
    assert target.read_text(encoding="utf-8") == "target\n"
    assert (tmp_path / "dir.yaml").is_dir()
    assert not (tmp_path / "missing.yaml").exists()


def test_init_help_names_the_contract() -> None:
    done = subprocess.run(
        [sys.executable, "-m", "arci.cli", "init", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0
    assert done.stderr == ""
    for flag in ("--baseline", "--candidate", "--toolset", "--oracle", "--task-file", "--force"):
        assert flag in done.stdout
