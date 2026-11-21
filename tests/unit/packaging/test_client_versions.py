"""F6: the client-versions guard script and its workflow.

`.github/scripts/client_versions.py` compares the newest published Claude Code and Codex
CLI versions against the ones `docs/LOG_FORMATS.md` says the session-log readers were
checked against, and prints the body for a tracking issue (or nothing). It takes no
network access itself, so it is tested by calling its functions directly, loaded the way
`tests/unit/examples/test_pr_comment.py` loads `.github/scripts/pr_comment.py`.
"""

from __future__ import annotations

import runpy
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / ".github" / "scripts" / "client_versions.py"
WORKFLOW = ROOT / ".github" / "workflows" / "client-versions.yml"
LOG_FORMATS = ROOT / "docs" / "LOG_FORMATS.md"

_MODULE = runpy.run_path(str(SCRIPT))
VERSION_TUPLE = cast(Callable[[str], tuple[int, ...]], _MODULE["version_tuple"])
HIGHEST_CHECKED = cast(Callable[[str], tuple[str, str]], _MODULE["highest_checked"])
COMPARE = cast(Callable[[str, str, str], str], _MODULE["compare"])


def test_version_tuple_compares_numerically() -> None:
    assert VERSION_TUPLE("2.1.325") > VERSION_TUPLE("2.1.40")
    assert VERSION_TUPLE("0.167.0") > VERSION_TUPLE("0.154.0")
    assert VERSION_TUPLE("2.1.40") < VERSION_TUPLE("2.1.325")


def test_highest_checked_parses_the_real_log_formats_doc() -> None:
    text = LOG_FORMATS.read_text(encoding="utf-8")
    checked_claude_code, checked_codex = HIGHEST_CHECKED(text)
    # docs/LOG_FORMATS.md names 2.1.309, 2.1.321, 2.1.325, 2.1.326, 2.1.330 and 0.154.0,
    # 0.167.0, 0.169.0, 0.171.0 (0.169.0 added on 16 Nov 2026; 2.1.326, 2.1.330 and 0.171.0
    # on 21 Nov 2026, each after sessions of that client were read).
    assert checked_claude_code == "2.1.330"
    assert checked_codex == "0.171.0"


def test_prints_nothing_when_nothing_is_newer() -> None:
    text = LOG_FORMATS.read_text(encoding="utf-8")
    checked_claude_code, checked_codex = HIGHEST_CHECKED(text)
    assert COMPARE(checked_claude_code, checked_codex, text) == ""
    assert COMPARE("2.1.40", "0.100.0", text) == ""


def test_prints_a_body_naming_both_clients_when_one_is_newer() -> None:
    text = LOG_FORMATS.read_text(encoding="utf-8")
    checked_claude_code, checked_codex = HIGHEST_CHECKED(text)
    body = COMPARE("99.0.0", checked_codex, text)
    assert "Claude Code" in body
    assert "Codex CLI" in body
    assert checked_claude_code in body
    assert "99.0.0" in body
    assert checked_codex in body

    body = COMPARE(checked_claude_code, "99.0.0", text)
    assert "Claude Code" in body
    assert "Codex CLI" in body
    assert "99.0.0" in body


def test_highest_checked_rejects_a_log_formats_doc_with_no_sentence() -> None:
    with pytest.raises(ValueError):
        HIGHEST_CHECKED("CANARY-no-such-sentence-here")


def _workflow() -> dict[Any, Any]:
    return cast(dict[Any, Any], yaml.safe_load(WORKFLOW.read_text(encoding="utf-8")))


def test_workflow_has_a_daily_schedule() -> None:
    doc = _workflow()
    # YAML parses the bare key `on:` as the boolean True.
    triggers = doc.get("on") or doc.get(True)
    assert triggers is not None
    schedules = triggers.get("schedule") or []
    assert any("cron" in entry for entry in schedules)
    assert "workflow_dispatch" in triggers


def test_workflow_has_the_two_permissions() -> None:
    doc = _workflow()
    assert doc["permissions"] == {"contents": "read"}
    job = doc["jobs"]["check"]
    assert job["permissions"] == {"contents": "read", "issues": "write"}


def test_workflow_has_no_unpinned_action() -> None:
    # test_trust_files.py already checks every workflow's actions are pinned; this test
    # checks only that this workflow uses `uses:` at all, so that guard is not vacuous.
    doc = _workflow()
    uses = [step.get("uses") for step in doc["jobs"]["check"]["steps"] if step.get("uses")]
    assert uses
    for reference in uses:
        assert "@" in reference
        ref = reference.rsplit("@", 1)[-1]
        assert len(ref) == 40 and all(c in "0123456789abcdef" for c in ref)


@pytest.mark.parametrize("bad", ["2.1.330; echo x", "$(id)", "2.1.330\n- injected", "", "latest"])
def test_main_refuses_anything_but_a_plain_version(
    bad: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """A registry value that is not a plain version never reaches the issue body."""
    import subprocess
    import sys

    script = Path(__file__).resolve().parents[3] / ".github" / "scripts" / "client_versions.py"
    done = subprocess.run(
        [sys.executable, str(script), bad, "0.167.0"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert done.returncode == 2
    assert done.stdout == ""


def test_workflow_passes_outside_values_through_the_environment() -> None:
    text = (
        Path(__file__).resolve().parents[3] / ".github" / "workflows" / "client-versions.yml"
    ).read_text("utf-8")
    for line in text.splitlines():
        stripped = line.strip()
        if "${{" in stripped and not stripped.startswith(("if:", "#")):
            # An expression may set an env value or a `with:` value, never sit in a script line.
            assert ":" in stripped.split("${{")[0], line
