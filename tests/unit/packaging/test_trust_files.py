"""The trust items added for 2.4.0: CI security workflows and contributor files.

Checks that the files exist, that every YAML file under `.github/` parses, that every
workflow action is pinned by commit (or is a local `./` action), that no workflow installs
uv without `--require-hashes` once it has already checked the repository out, that the uv
version is the same everywhere it is named, that Dependabot watches GitHub Actions, and that
both issue forms carry the required privacy checkbox.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]
GITHUB = ROOT / ".github"
WORKFLOWS = GITHUB / "workflows"

REQUIRED_FILES = (
    GITHUB / "dependabot.yml",
    WORKFLOWS / "codeql.yml",
    WORKFLOWS / "workflow-audit.yml",
    GITHUB / "requirements" / "uv.txt",
    ROOT / "constraints" / "oracle.txt",
    ROOT / "CONTRIBUTING.md",
    ROOT / "CODE_OF_CONDUCT.md",
    GITHUB / "ISSUE_TEMPLATE" / "config.yml",
    GITHUB / "ISSUE_TEMPLATE" / "log-format-changed.yml",
    GITHUB / "ISSUE_TEMPLATE" / "bug.yml",
    GITHUB / "PULL_REQUEST_TEMPLATE.md",
)

_YAML_GLOBS = ("*.yml", "*.yaml")


def _all_yaml_files() -> list[Path]:
    files: list[Path] = []
    for pattern in _YAML_GLOBS:
        files.extend(GITHUB.glob(pattern))
        files.extend(WORKFLOWS.glob(pattern))
        files.extend((GITHUB / "ISSUE_TEMPLATE").glob(pattern))
    return sorted(set(files))


def test_required_files_exist() -> None:
    missing = [str(path.relative_to(ROOT)) for path in REQUIRED_FILES if not path.is_file()]
    assert missing == []


def test_every_yaml_file_parses() -> None:
    files = _all_yaml_files()
    assert files, "expected at least one YAML file under .github/"
    for path in files:
        yaml.safe_load(path.read_text())  # raises on invalid YAML


def _iter_uses(node: Any) -> Iterator[str]:
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "uses" and isinstance(value, str):
                yield value
            else:
                yield from _iter_uses(value)
    elif isinstance(node, list):
        for item in node:
            yield from _iter_uses(item)


_FULL_SHA = re.compile(r"[0-9a-f]{40}")


def test_every_workflow_action_is_pinned_to_a_commit_or_local() -> None:
    offenders: list[str] = []
    for path in sorted(WORKFLOWS.glob("*.yml")):
        doc = yaml.safe_load(path.read_text())
        for uses in _iter_uses(doc):
            if uses.startswith("./"):
                continue
            ref = uses.rsplit("@", 1)[-1] if "@" in uses else ""
            if not _FULL_SHA.fullmatch(ref):
                offenders.append(f"{path.name}: {uses}")
    assert offenders == []


def _job_steps(doc: dict[str, Any]) -> Iterator[list[dict[str, Any]]]:
    for job in (doc.get("jobs") or {}).values():
        steps = job.get("steps")
        if isinstance(steps, list):
            yield steps


def test_no_workflow_installs_uv_without_require_hashes_after_a_checkout() -> None:
    # A step that installs uv without --require-hashes is only acceptable in a job that
    # never checked the repository out first (so .github/requirements/uv.txt is not on
    # disk to point at). That is the one known, reported exception: the "reference" job in
    # ttfv-reference.yml, which deliberately has no checkout step at all.
    offenders: list[str] = []
    for path in sorted(WORKFLOWS.glob("*.yml")):
        doc = yaml.safe_load(path.read_text())
        for steps in _job_steps(doc):
            checked_out = False
            for step in steps:
                uses = step.get("uses")
                if isinstance(uses, str) and uses.startswith("actions/checkout@"):
                    checked_out = True
                run = step.get("run")
                if not isinstance(run, str):
                    continue
                if "uv==" not in run and "uv.txt" not in run:
                    continue
                if "pip install" not in run:
                    continue
                if checked_out and "--require-hashes" not in run:
                    offenders.append(f"{path.name}: {step.get('name')}")
    assert offenders == []


def test_uv_requirements_version_matches_every_uv_version() -> None:
    uv_txt = (GITHUB / "requirements" / "uv.txt").read_text()
    pinned = re.search(r"^uv==(\S+?)\s*\\?\s*$", uv_txt, re.MULTILINE)
    assert pinned is not None, "could not find a pinned uv== line in uv.txt"
    version = pinned.group(1)

    found_any = False
    for path in sorted(WORKFLOWS.glob("*.yml")):
        for match in re.finditer(r"UV_VERSION:\s*[\"']?([^\"'\s]+)", path.read_text()):
            found_any = True
            assert match.group(1) == version, f"{path.name} UV_VERSION != {version}"
    assert found_any, "expected at least one UV_VERSION declaration to check against"


def test_dependabot_watches_github_actions() -> None:
    doc = yaml.safe_load((GITHUB / "dependabot.yml").read_text())
    ecosystems = {update.get("package-ecosystem") for update in doc.get("updates", [])}
    assert "github-actions" in ecosystems


def _checkbox_options(doc: dict[str, Any]) -> Iterator[dict[str, Any]]:
    for item in doc.get("body", []):
        if item.get("type") == "checkboxes":
            yield from item.get("attributes", {}).get("options", [])


def test_both_issue_forms_carry_the_required_privacy_checkbox() -> None:
    for name in ("log-format-changed.yml", "bug.yml"):
        doc = yaml.safe_load((GITHUB / "ISSUE_TEMPLATE" / name).read_text())
        options = list(_checkbox_options(doc))
        matching = [
            option
            for option in options
            if option.get("required") is True
            and "I pasted no log line and no file path" in option.get("label", "")
        ]
        assert matching, f"{name} is missing the required 'no log line, no file path' checkbox"
