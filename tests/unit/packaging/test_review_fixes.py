"""Checks run on built artifacts by CI and the release smoke script."""

import ast
import json
import re
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path

import pytest
import yaml

from arci import __version__

ROOT = Path(__file__).resolve().parents[3]


def test_every_release_version_matches() -> None:
    versions: dict[str, str] = {}
    for relative in ("pyproject.toml", "packages/realornoise/pyproject.toml"):
        data = tomllib.loads((ROOT / relative).read_text())["project"]
        versions[relative] = data["version"]
        if relative.startswith("packages/"):
            versions[relative + " dependency"] = data["dependencies"][0].removeprefix(
                "agent-reliability-ci=="
            )
    versions["src/arci/__init__.py"] = __version__
    module = ast.parse((ROOT / "packages/realornoise/src/realornoise/__init__.py").read_text())
    versions["packages/realornoise/src/realornoise/__init__.py"] = next(
        ast.literal_eval(n.value) for n in module.body if isinstance(n, ast.Assign)
    )
    versions["plugins/realornoise/.claude-plugin/plugin.json"] = json.loads(
        (ROOT / "plugins/realornoise/.claude-plugin/plugin.json").read_text()
    )["version"]
    versions["CITATION.cff"] = yaml.safe_load((ROOT / "CITATION.cff").read_text())["version"]
    versions["uv.lock"] = next(
        p["version"]
        for p in tomllib.loads((ROOT / "uv.lock").read_text())["package"]
        if p["name"] == "agent-reliability-ci"
    )
    for relative in (
        "plugins/realornoise/skills/realornoise/SKILL.md",
        "plugins/realornoise/README.md",
        "integrations/codex/skills/realornoise/SKILL.md",
    ):
        pins = re.findall(
            r"uvx --python 3\.14 realornoise==([0-9.]+)", (ROOT / relative).read_text()
        )
        assert pins, relative
        assert all(pin == __version__ for pin in pins), relative
        versions[relative] = pins[0]
    readme = (ROOT / "README.md").read_text()
    for pattern in (
        r"v([0-9.]+) is the current release",
        r"pins `v([0-9.]+)`, the current release",
        r"agent-reliability-ci@v([0-9.]+)",
        r"agent-reliability-ci(?:\[[^\]]+\])?==([0-9.]+)",
    ):
        found = re.findall(pattern, readme)
        assert found and all(version == __version__ for version in found), pattern
    versions["README.md"] = __version__
    assert {path: value for path, value in versions.items() if value != __version__} == {}
    documented = (ROOT / "docs/RELEASING.md").read_text()
    assert all(path.removesuffix(" dependency") in documented for path in versions)


@pytest.mark.parametrize(
    "fault",
    ["none", "missing_example", "extra_package", "wrong_pin", "wrong_entry", "extra_metadata"],
)
def test_smoke_checks_built_wheel_contents(tmp_path: Path, fault: str) -> None:
    script = (ROOT / ".github/scripts/wheel_smoke.sh").read_text()
    match = re.search(r"<<'WHEEL_CHECK'\n(.*?)\nWHEEL_CHECK", script, re.S)
    assert match is not None, "wheel smoke must validate built wheel contents"
    main, second = tmp_path / "main.whl", tmp_path / "second.whl"
    meta = "realornoise-2.2.0.dist-info/"
    with zipfile.ZipFile(main, "w") as wheel:
        wheel.writestr("agent_reliability_ci-2.2.0.dist-info/METADATA", "Version: 2.2.0\n")
        for name in (
            "now.txt",
            "claude/history.jsonl",
            "codex/sessions/rollout-example.jsonl",
            "codex/archived_sessions/rollout-subagent.jsonl",
        ):
            if fault != "missing_example" or name != "now.txt":
                wheel.writestr("arci/logs/example/" + name, "example")
    with zipfile.ZipFile(second, "w") as wheel:
        wheel.writestr("realornoise/__init__.py", "")
        wheel.writestr("realornoise/py.typed", "")
        pin = "0.0.0" if fault == "wrong_pin" else "2.2.0"
        wheel.writestr(
            meta + "METADATA",
            f"Version: 2.2.0\nRequires-Dist: agent-reliability-ci=={pin}\n"
            "Requires-Python: >=3.11\n",
        )
        wheel.writestr(
            meta + "entry_points.txt",
            "[console_scripts]\nrealornoise = "
            + ("other:main" if fault == "wrong_entry" else "arci.logs.cli:main")
            + "\n",
        )
        wheel.writestr(meta + "licenses/LICENSE", "license")
        if fault == "extra_package":
            wheel.writestr("arci/__init__.py", "")
        if fault == "extra_metadata":
            wheel.writestr(meta + "unexpected.py", "")
    result = subprocess.run(
        [sys.executable, "-c", match.group(1), str(main), str(second)],
        capture_output=True,
        text=True,
    )
    assert (result.returncode == 0) == (fault == "none"), result.stderr
