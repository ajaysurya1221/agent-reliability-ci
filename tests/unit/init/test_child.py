"""The reference check's child: deadline, process-group kill, captured output, crashes.

These call `arci.init` in-process with modules written to a temporary working directory, so the
child resolves them only through the ADR 0006 rule (the cwd appended to its PYTHONPATH).
"""

from __future__ import annotations

import os
import sys
import textwrap
import time
from pathlib import Path

import pytest

from arci.init import InitError, InitRequest, check_references, parse_request

AGENT = (
    "def agent(task, tools, rng):\n    return {}\n\n\ndef oracle(task, state):\n    return True\n"
)


def _write(directory: Path, name: str, body: str) -> None:
    (directory / f"{name}.py").write_text(AGENT + textwrap.dedent(body), encoding="utf-8")


def _request(module: str, *, faults: tuple[str, ...] = ()) -> InitRequest:
    return parse_request(
        experiment_id="child-check",
        baseline=f"{module}:agent",
        candidate=f"{module}:agent",
        toolset=f"{module}:make_world",
        oracle=f"{module}:oracle",
        task='{"k": "v"}',
        task_file=None,
        faults=faults,
        n="8",
        out="arci.yaml",
        force=False,
    )


def _gone(pid: int, within: float = 10.0) -> bool:
    end = time.monotonic() + within
    while time.monotonic() < end:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.05)
    return False


@pytest.fixture
def workdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PYTHONPATH", raising=False)
    return tmp_path


SPAWNS_AND_HANGS = """
import os, subprocess, time

def make_world(task, seed):
    sleeper = subprocess.Popen(["sleep", "120"])
    with open("pids.txt", "w") as handle:
        handle.write(f"{os.getpid()} {sleeper.pid}")
    time.sleep(120)
"""


def test_a_hanging_toolset_is_killed_with_its_process_group(workdir: Path) -> None:
    _write(workdir, "init_hang_world", SPAWNS_AND_HANGS)
    started = time.monotonic()
    with pytest.raises(InitError) as caught:
        check_references(_request("init_hang_world"), deadline=3.0)
    assert time.monotonic() - started < 60
    assert str(caught.value) == (
        "reference check did not finish within 3 s (an import or the --toolset call hangs); "
        "nothing written"
    )
    child, grandchild = (int(pid) for pid in (workdir / "pids.txt").read_text().split())
    assert _gone(child)
    assert _gone(grandchild)
    assert not (workdir / "arci.yaml").exists()


SPAWNS_AND_RETURNS = """
import os, subprocess

class World:
    tools = {"reserve": len}

    def snapshot(self):
        return {}

def make_world(task, seed):
    sleeper = subprocess.Popen(["sleep", "120"])
    with open("pids.txt", "w") as handle:
        handle.write(str(sleeper.pid))
    return World()
"""


def test_no_descendant_outlives_a_successful_check(workdir: Path) -> None:
    _write(workdir, "init_spawn_world", SPAWNS_AND_RETURNS)
    assert check_references(_request("init_spawn_world")) == ("reserve",)
    assert _gone(int((workdir / "pids.txt").read_text()))


NOISY = """
import os, sys
print("import-time print")
os.write(1, b"raw fd write\\n")

class World:
    def __init__(self, task, seed):
        assert task == {"k": "v"} and seed == 0
        print("factory print", file=sys.stdout)
        self.tools = {"b_tool": len, "a_tool": len}

    def snapshot(self):
        raise AssertionError("snapshot is never called")

def make_world(task, seed):
    return World(task, seed)

def agent(task, tools, rng):
    raise AssertionError("agents are never called")

def oracle(task, state):
    raise AssertionError("the oracle is never called")
"""


def test_user_output_never_mixes_with_the_result_and_nothing_else_is_called(
    workdir: Path,
) -> None:
    _write(workdir, "init_noisy_world", NOISY)
    assert check_references(_request("init_noisy_world", faults=("empty_result:a_tool",))) == (
        "a_tool",
        "b_tool",
    )
    # The parent never imports a reference.
    assert "init_noisy_world" not in sys.modules


@pytest.mark.parametrize(
    ("body", "detail"),
    [
        (
            "def make_world(task, seed):\n    raise KeyError('stock')\n",
            "--toolset init_bad_world:make_world: calling it with the task and seed 0 raised "
            "KeyError: 'stock'; check the toolset factory and --task",
        ),
        (
            "def make_world(task, seed):\n    return object()\n",
            "--toolset init_bad_world:make_world: its result has no .tools mapping of tool "
            "names; return an object with .tools and .snapshot()",
        ),
        (
            "class W:\n    tools = {1: len}\n    def snapshot(self):\n        return {}\n"
            "def make_world(task, seed):\n    return W()\n",
            "--toolset init_bad_world:make_world: its result has no .tools mapping of tool "
            "names; return an object with .tools and .snapshot()",
        ),
        (
            "class W:\n    tools = {'t': len}\n    snapshot = None\n"
            "def make_world(task, seed):\n    return W()\n",
            "--toolset init_bad_world:make_world: its result has no callable .snapshot; return "
            "an object with .tools and .snapshot()",
        ),
        (
            "import os\nos._exit(5)\n",
            "reference check process exited with code 5 before reporting; nothing written",
        ),
        (
            "raise SystemExit(4)\n",
            "--baseline init_bad_world:agent: module not importable; importing init_bad_world "
            "raised SystemExit: 4; check module and dependencies",
        ),
    ],
)
def test_toolset_and_child_failures_are_one_line(workdir: Path, body: str, detail: str) -> None:
    _write(workdir, "init_bad_world", body)
    with pytest.raises(InitError) as caught:
        check_references(_request("init_bad_world"))
    assert str(caught.value) == detail
    assert "init_bad_world" not in sys.modules


def test_a_resolve_error_other_than_a_missing_attribute_names_its_type(workdir: Path) -> None:
    _write(
        workdir,
        "init_lazy_world",
        "def __getattr__(name):\n    raise ValueError('lazy attributes fail')\n",
    )
    request = parse_request(
        experiment_id="child-check",
        baseline="init_lazy_world:lazy",
        candidate="init_lazy_world:agent",
        toolset="init_lazy_world:make_world",
        oracle="init_lazy_world:oracle",
        task=None,
        task_file=None,
        faults=(),
        n="8",
        out="arci.yaml",
        force=False,
    )
    with pytest.raises(InitError) as caught:
        check_references(request)
    assert str(caught.value) == (
        "--baseline init_lazy_world:lazy: importable but resolving lazy raised ValueError"
    )


def test_a_failing_import_names_the_module_and_the_exception_in_one_bounded_line(
    workdir: Path,
) -> None:
    _write(workdir, "init_dep_world", "import init_missing_dependency\n")
    with pytest.raises(InitError) as caught:
        check_references(_request("init_dep_world"))
    assert str(caught.value) == (
        "--baseline init_dep_world:agent: module not importable; importing init_dep_world raised "
        "ModuleNotFoundError: No module named 'init_missing_dependency'; check module and "
        "dependencies"
    )
    _write(workdir, "init_long_world", "raise RuntimeError('x' * 5000 + '\\nsecond line')\n")
    with pytest.raises(InitError) as caught:
        check_references(_request("init_long_world"))
    message = str(caught.value)
    assert "\n" not in message
    detail = message.split(" raised ", 1)[1].removesuffix("; check module and dependencies")
    assert len(detail) == 200
    assert detail.startswith("RuntimeError: xxx")
    assert detail.endswith("...")


MANY_TOOLS = """
class World:
    tools = {f"t{i:02d}": len for i in range(25)}

    def snapshot(self):
        return {}

def make_world(task, seed):
    return World()
"""


def test_the_advertised_tools_suffix_names_at_most_twenty(workdir: Path) -> None:
    _write(workdir, "init_many_world", MANY_TOOLS)
    with pytest.raises(InitError) as caught:
        check_references(_request("init_many_world", faults=("tool_timeout:charge",)))
    names = ", ".join(f"t{i:02d}" for i in range(20))
    assert str(caught.value) == (
        "--fault tool_timeout:charge: tool charge absent from --toolset "
        f"init_many_world:make_world; choose an advertised tool ({names}, and 5 more)"
    )
