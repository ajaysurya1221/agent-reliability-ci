"""P4c metadata, fail-soft comments and bounded Markdown regressions."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from tests.unit.examples.test_pr_comment import MARKER_FOR, POST, FakeAPI, environment


def test_all_action_descriptions_are_literal() -> None:
    action = yaml.safe_load(Path("action.yml").read_text())
    descriptions = [action["description"]]
    descriptions += [
        item["description"] for group in ("inputs", "outputs") for item in action[group].values()
    ]
    assert all("${{" not in description for description in descriptions)


def test_readme_documents_comment_setup() -> None:
    readme = Path("README.md").read_text()
    action = readme.split("### GitHub Actions\n", 1)[1].split("\n##", 1)[0]
    for text in (
        "pr-comment",
        "comment-id",
        "pull-requests: write",
        "concurrency:",
        "${{ github.workflow }}",
        "cancel-in-progress: false",
        "matrix",
    ):
        assert text in action
    assert "no HTML report yet" not in readme


def test_explicit_comment_id_still_scopes_to_job(tmp_path: Path) -> None:
    env = environment(tmp_path) | {"ARCI_COMMENT_ID": "stable"}
    assert MARKER_FOR(env) != MARKER_FOR(env | {"GITHUB_JOB": "another-job"})


def test_explicit_and_default_identity_cannot_collide(tmp_path: Path) -> None:
    env = environment(tmp_path) | {"GITHUB_WORKFLOW": "explicit"}
    assert MARKER_FOR(env) != MARKER_FOR(env | {"ARCI_COMMENT_ID": env["ARCI_MANIFEST"]})


def test_unexpected_exception_is_one_line_exit_zero(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import runpy, subprocess\n"
            "def fail(*a, **kw): raise RuntimeError('secret-error')\n"
            "subprocess.run = fail\n"
            "runpy.run_path('.github/scripts/pr_comment.py', run_name='__main__')",
        ],
        env=os.environ | environment(tmp_path),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert (
        result.stdout == "ARCI comment skipped: API or report unavailable; gate result unchanged.\n"
    )
    assert result.stderr == ""


@pytest.mark.parametrize("table", [False, True])
def test_truncation_preserves_sections_and_table_headers(tmp_path: Path, table: bool) -> None:
    env, api = environment(tmp_path), FakeAPI()
    header = "| Condition | Count |\n|---|---:|\n"
    content = (
        header + "| `é-condition` | 1 |\n" * 10000 if table else "label: `" + "x" * 66000 + "`"
    )
    Path(env["ARCI_SUMMARY"]).write_text("VERDICT: BLOCK (exit 1)\n\n## Evidence\n\n" + content)
    POST(env, api)
    body = str(api.comments[-1]["body"])
    assert len(body.encode()) <= 65000
    assert "Summary truncated" in body and env["ARCI_ARTIFACT_URL"] in body
    assert "VERDICT: BLOCK" in body
    if table:
        assert "## Evidence\n\n" + header in body
        assert "| `é-condition` | 1 |" in body
        assert all(
            line == "| `é-condition` | 1 |" for line in body.splitlines() if line.startswith("| `")
        )
    else:
        assert "## Evidence" not in body
