"""Offline metadata, artifact and release guards for the second distribution."""

from __future__ import annotations

import ast
import configparser
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
SECOND = ROOT / "packages/realornoise"


def _toml(path: Path) -> dict[str, Any]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _workflow(name: str) -> dict[str, Any]:
    # BaseLoader preserves GitHub's `on` key instead of treating it as YAML 1.1 True.
    return cast(
        dict[str, Any],
        yaml.load(
            (ROOT / ".github/workflows" / name).read_text(encoding="utf-8"), Loader=yaml.BaseLoader
        ),
    )


def _step(job: dict[str, Any], name: str) -> dict[str, Any]:
    return next(step for step in job["steps"] if step["name"] == name)


def test_realornoise_metadata_and_license() -> None:
    main = _toml(ROOT / "pyproject.toml")
    second = _toml(SECOND / "pyproject.toml")
    project = second["project"]
    version = main["project"]["version"]
    assert project["name"] == "realornoise"
    assert project["version"] == version
    assert project["dependencies"] == [f"agent-reliability-ci=={version}"]
    assert project["requires-python"] == ">=3.11"
    assert project["scripts"] == {"realornoise": "arci.logs.cli:main"}
    assert project["classifiers"] == [
        value
        for value in main["project"]["classifiers"]
        if value.startswith("Programming Language :: Python ::")
    ]
    assert second["build-system"] == main["build-system"]
    for field in ("license", "license-files"):
        assert project[field] == main["project"][field]
    for name in project["license-files"]:
        assert (SECOND / name).read_bytes() == (ROOT / name).read_bytes()
    module = ast.parse((SECOND / "src/realornoise/__init__.py").read_text(encoding="utf-8"))
    assert len(module.body) == 2 and ast.get_docstring(module)
    assignment = module.body[1]
    assert isinstance(assignment, ast.Assign)
    assert len(assignment.targets) == 1
    target = assignment.targets[0]
    assert isinstance(target, ast.Name) and target.id == "__version__"
    assert ast.literal_eval(assignment.value) == version
    assert (SECOND / "src/realornoise/py.typed").is_file()
    assert "workspace" not in main.get("tool", {}).get("uv", {})


def test_realornoise_requires_python_matches_main() -> None:
    assert (
        _toml(SECOND / "pyproject.toml")["project"]["requires-python"]
        == _toml(ROOT / "pyproject.toml")["project"]["requires-python"]
    )


def test_realornoise_and_main_wheel_file_lists(tmp_path: Path) -> None:
    if importlib.util.find_spec("hatchling") is None:
        pytest.skip(
            "Hatchling unavailable offline; built-wheel checks run in "
            ".github/scripts/wheel_smoke.sh in CI and release smoke jobs"
        )
    wheels: list[Path] = []
    for index, source in enumerate((ROOT, SECOND)):
        output = tmp_path / str(index)
        output.mkdir()
        subprocess.run(
            [
                sys.executable,
                "-c",
                "from hatchling.build import build_wheel; import sys; build_wheel(sys.argv[1])",
                str(output),
            ],
            cwd=source,
            check=True,
            capture_output=True,
            text=True,
        )
        built = list(output.glob("*.whl"))
        assert len(built) == 1
        wheels.append(built[0])
    with zipfile.ZipFile(wheels[0]) as wheel:
        example = ROOT / "src/arci/logs/example"
        expected = {
            path.relative_to(ROOT / "src").as_posix(): path.read_bytes()
            for path in example.rglob("*")
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
        }
        assert {
            "arci/logs/example/now.txt",
            "arci/logs/example/claude/history.jsonl",
            "arci/logs/example/codex/sessions/rollout-example.jsonl",
            "arci/logs/example/codex/archived_sessions/rollout-subagent.jsonl",
        } <= expected.keys()
        for name, content in expected.items():
            assert wheel.read(name) == content
    with zipfile.ZipFile(wheels[1]) as wheel:
        names = set(wheel.namelist())
        version = _toml(SECOND / "pyproject.toml")["project"]["version"]
        metadata = f"realornoise-{version}.dist-info/"
        assert {name for name in names if not name.startswith(metadata)} == {
            "realornoise/__init__.py",
            "realornoise/py.typed",
        }
        entry = configparser.ConfigParser()
        entry.read_string(wheel.read(metadata + "entry_points.txt").decode())
        assert dict(entry["console_scripts"]) == {"realornoise": "arci.logs.cli:main"}
        content = wheel.read(metadata + "METADATA").decode()
        assert f"Requires-Dist: agent-reliability-ci=={version}\n" in content
        assert "Requires-Python: >=3.11\n" in content


@pytest.mark.parametrize("change", ["none", "tag", "branch", "version", "pin", "module"])
def test_release_guard_rejects_mismatched_second_distribution(tmp_path: Path, change: str) -> None:
    for name in (
        "pyproject.toml",
        "src/arci/__init__.py",
        "packages/realornoise/pyproject.toml",
        "packages/realornoise/src/realornoise/__init__.py",
    ):
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    version = _toml(ROOT / "pyproject.toml")["project"]["version"]
    project = tmp_path / "packages/realornoise/pyproject.toml"
    if change in {"version", "pin"}:
        old = (
            f'version = "{version}"' if change == "version" else f"agent-reliability-ci=={version}"
        )
        project.write_text(project.read_text().replace(old, old.replace(version, "0.0.0")))
    if change == "module":
        (tmp_path / "packages/realornoise/src/realornoise/__init__.py").write_text(
            '__version__ = "0.0.0"\n'
        )
    build = _workflow("release.yml")["jobs"]["build"]
    script = _step(build, "Refuse to build unless the tag is v plus the package version")["run"]
    python = script.split("<<'PY'\n", 1)[1].rsplit("\nPY", 1)[0]
    result = subprocess.run(
        [sys.executable, "-c", python],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "REF_TYPE": "branch" if change == "branch" else "tag",
            "REF_NAME": "v0.0.0" if change == "tag" else f"v{version}",
        },
    )
    assert result.returncode == (0 if change == "none" else 1), result.stdout + result.stderr
    assert ("::error title=release guard::" in result.stdout) == (change != "none")


def test_release_workflow_keeps_publish_order_and_artifacts_separate() -> None:
    jobs = _workflow("release.yml")["jobs"]
    main, second = jobs["publish"], jobs["publish-realornoise"]
    assert {"build", "smoke", "publish"} <= set(second["needs"])
    assert main["environment"]["name"] == second["environment"]["name"] == "pypi"
    assert main["permissions"] == second["permissions"] == {"id-token": "write"}
    for job, artifact in ((main, "dist"), (second, "dist-realornoise")):
        download = job["steps"][0]
        assert download["with"] == {"name": artifact, "path": artifact}
        check = _step(job, "Verify the checksums and keep only the wheel and the sdist")["run"]
        assert f"cd {artifact}\n" in check and "sha256sum -c SHA256SUMS" in check
        publish = _step(job, "Publish to PyPI with attestations")
        assert publish["with"]["attestations"] == "true"
        assert publish["with"]["skip-existing"] == "false"
    assert second["steps"][-1]["uses"] == main["steps"][-1]["uses"]
    assert second["steps"][-1]["with"]["packages-dir"] == "dist-realornoise/"
    build_steps = jobs["build"]["steps"]
    for artifact in ("dist", "dist-realornoise"):
        assert any(step.get("with", {}).get("name") == artifact for step in build_steps)
        assert any(
            f"cd {artifact}\n" in step.get("run", "") and "sha256sum -- *" in step["run"]
            for step in build_steps
        )
    assert (
        'packages/realornoise --out-dir "$PWD/dist-realornoise"'
        in _step(jobs["build"], "Build the realornoise wheel and sdist separately")["run"]
    )


def test_ci_and_release_workflow_smoke_both_wheels_on_every_python() -> None:
    ci = _workflow("ci.yml")["jobs"]
    release = _workflow("release.yml")["jobs"]
    assert {"3.11", "3.14"} <= set(ci["check"]["strategy"]["matrix"]["python-version"])
    assert _step(ci["check"], "Tests")["run"] == ".venv/bin/pytest -p no:cacheprovider"
    for job in (ci["wheel-smoke"], release["smoke"]):
        assert {"3.11", "3.14"} <= set(job["strategy"]["matrix"]["python-version"])
        smoke = _step(job, "Smoke-test the built wheel from an empty directory")
        assert "if" not in smoke
        assert smoke["run"].strip() == (
            "bash .github/scripts/wheel_smoke.sh dist/*.whl dist-realornoise/*.whl"
        )
        download = _step(job, "Download realornoise dist")
        assert "if" not in download
        assert download["with"] == {"name": "dist-realornoise", "path": "dist-realornoise"}
    assert ci["wheel-smoke"]["needs"] == "build-realornoise"
    for jobs, build_name in ((ci, "build-realornoise"), (release, "build")):
        build = jobs[build_name]
        assert "strategy" not in build and "if" not in build
        builds = [
            (name, step)
            for name, job in jobs.items()
            for step in job["steps"]
            if step.get("name") == "Build the realornoise wheel and sdist separately"
        ]
        assert len(builds) == 1 and builds[0][0] == build_name
        assert "if" not in builds[0][1]
        upload = _step(build, "Upload realornoise dist")
        assert upload["with"]["name"] == "dist-realornoise"


@pytest.mark.parametrize(
    ("status", "line", "passes"),
    [
        (1, "RESULT: REAL DROP", True),
        (0, "RESULT: REAL DROP", False),
        (2, "RESULT: REAL DROP", False),
        (3, "RESULT: REAL DROP", False),
        (1, "RESULT: CANNOT TELL", False),
    ],
)
def test_wheel_smoke_example_checks_status_and_result(
    tmp_path: Path,
    status: int,
    line: str,
    passes: bool,
) -> None:
    source = (ROOT / ".github/scripts/wheel_smoke.sh").read_text()
    function = "example() {" + source.split("example() {", 1)[1].split("\n}", 1)[0] + "\n}\n"
    script = (
        "set -euo pipefail\nroot=$1\nnow() { echo 0; }\n"
        "record() { :; }\nfail() { exit 1; }\n"
        + function
        + 'example test bash -c \'echo "$1"; exit "$2"\' -- "$2" "$3"\n'
    )
    result = subprocess.run(
        ["bash", "-c", script, "--", str(tmp_path), line, str(status)],
        capture_output=True,
        text=True,
    )
    assert (result.returncode == 0) == passes, result.stderr
    assert 'example "arci logs --example" arci logs --example' in source
    assert 'example "realornoise --example" realornoise --example' in source


@pytest.mark.parametrize("command", ["arci demo", "realornoise --example"])
@pytest.mark.parametrize("fault", ["none", "exit", "marker", "timeout", "missing"])
def test_ttfv_workflow_accepts_expected_result_only(
    tmp_path: Path, command: str, fault: str
) -> None:
    workflow = _workflow("ttfv-reference.yml")
    assert set(workflow["on"]) == {"workflow_dispatch"}
    inputs = workflow["on"]["workflow_dispatch"]["inputs"]
    assert inputs["package"]["default"] == "agent-reliability-ci"
    assert inputs["command"]["default"] == "arci demo"
    assert command in inputs["command"]["options"]
    assert "sprint/t18-" not in (ROOT / ".github/workflows/ttfv-reference.yml").read_text()
    example = command != "arci demo"
    marker = "RESULT: REAL DROP" if example else "All six steps held."
    status = 1 if example else 0
    env = {
        **os.environ,
        "OUT_DIR": str(tmp_path),
        "OUT_JSON": str(tmp_path / "result.json"),
        "PACKAGE": "realornoise" if example else "agent-reliability-ci",
        "COMMAND": command,
        "EXPECTED_EXIT_CODE": str(status),
        "SUCCESS_MARKER": marker,
        "COLD_SAMPLES": "1",
        "WARM_SAMPLES": "0",
    }
    (tmp_path / "sample-1.log").write_text(
        "2026-11-15T00:00:00Z " + ("wrong output" if fault == "marker" else marker) + "\n"
    )
    row = {
        "sample": 1,
        "started": True,
        "timed_out": fault == "timeout",
        "exit_code": 3 if fault == "exit" else status,
    }
    (tmp_path / "samples.jsonl").write_text("" if fault == "missing" else json.dumps(row) + "\n")
    job = workflow["jobs"]["reference"]
    for name, expected in (
        ("Parse the logs into reference-${{ matrix.os }}.json", 0),
        ("Fail if any sample did not hold", 0 if fault == "none" else 1),
    ):
        result = subprocess.run(
            [sys.executable, "-c", _step(job, name)["run"]], env=env, capture_output=True, text=True
        )
        assert result.returncode == expected, result.stdout + result.stderr
    doc = json.loads((tmp_path / "result.json").read_text())
    assert doc["command"] == f"uvx --from {env['PACKAGE']} {command}"
