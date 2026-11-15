"""Regressions for the final L10 counter and compatibility clarifications."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from arci import html_base, html_report
from arci.logs import claude_code, codex, report
from arci.logs.report import wrap_text
from tests.unit.logs.synth_logs import assistant, context, meta, result, token, write_rows
from tests.unit.logs.test_cli import invoke

NOW = datetime(2026, 2, 1, tzinfo=UTC)


@pytest.mark.parametrize(
    "name", ["_CSS", "_heading", "_p", "_table", "_text", "_wrap_class", "visible_text"]
)
def test_moved_html_helpers_remain_available(name: str) -> None:
    assert getattr(html_report, name) is getattr(html_base, name)


def test_report_exports_only_public_renderers() -> None:
    assert report.__all__ == sorted(report.__all__)
    assert all(not name.startswith("_") for name in report.__all__)
    assert {"render_markdown", "render_text"} <= set(report.__all__)


def test_wrap_allows_exactly_one_hundred_characters() -> None:
    line = "a" * 49 + " " + "b" * 50
    assert len(line) == 100
    assert wrap_text(line) == line
    assert wrap_text(line + " next word") == line + "\nnext word"


@pytest.mark.parametrize("flag", [True, False, None])
def test_api_error_marker_counts_as_unused_type(tmp_path: Path, flag: object) -> None:
    path = tmp_path / "session.jsonl"
    write_rows(
        path,
        [
            assistant("error", isApiErrorMessage=flag),
            result("missing", isApiErrorMessage=flag),
            assistant("kept"),
        ],
    )
    data = claude_code.read([path], project=None, now=NOW)
    assert data.counters.lines == 3
    assert data.counters.lines_unknown_type == 2
    assert data.counters.responses == 1
    assert data.counters.edits_unmatched == 0


@pytest.mark.parametrize("tool", ["claude-code", "codex"])
def test_files_read_counts_opened_files_even_if_decode_fails(tmp_path: Path, tool: str) -> None:
    path = tmp_path / "undecodable.jsonl"
    path.write_bytes(b"\xff\n")
    reader = claude_code.read if tool == "claude-code" else codex.read
    data = reader([path, tmp_path / "absent.jsonl"], project=None, now=NOW)
    assert data.counters.files_read == 1
    assert data.counters.files_unreadable == 2
    assert data.counters.responses == 0


@pytest.mark.parametrize("tool", ["claude-code", "codex"])
def test_decode_failure_still_reports_read_error(tmp_path: Path, tool: str) -> None:
    root = tmp_path / "logs"
    path = root / (
        "project/session.jsonl" if tool == "claude-code" else "sessions/rollout-example.jsonl"
    )
    path.parent.mkdir(parents=True)
    path.write_bytes(b"\xff\n")
    flag = "--claude-dir" if tool == "claude-code" else "--codex-dir"
    code, out, err = invoke(tmp_path, ["--tool", tool, flag, str(root)])
    assert code == 3 and not err
    assert "Session log files could not be read." in out


@pytest.mark.parametrize("tool", ["claude-code", "codex"])
def test_kept_responses_include_subagents(tmp_path: Path, tool: str) -> None:
    path = tmp_path / "subagent.jsonl"
    if tool == "claude-code":
        write_rows(path, [assistant(isSidechain=True)])
        data = claude_code.read([path], project=None, now=NOW)
    else:
        write_rows(path, [meta(thread_source="subagent"), context(), token()])
        data = codex.read([path], project=None, now=NOW)
    assert data.counters.responses == len(data.responses) == 1
    assert not data.responses[0].main_thread


def test_outside_codex_file_is_opened_but_body_is_not_decoded(tmp_path: Path) -> None:
    path = tmp_path / "outside.jsonl"
    header = write_rows(path, [meta(cwd="/outside")])
    path.write_bytes(header + b"\xff\n")
    data = codex.read([path], project=Path("/project"), now=NOW)
    assert data.counters.files_read == data.counters.files_outside_project == 1
    assert data.counters.lines == 1
    assert data.counters.files_unreadable == data.counters.responses == 0


def test_claude_project_filter_does_not_count_files_outside(tmp_path: Path) -> None:
    path = tmp_path / "session.jsonl"
    write_rows(path, [assistant(cwd="/outside")])
    data = claude_code.read([path], project=Path("/project"), now=NOW)
    assert data.counters.files_read == 1
    assert data.counters.files_outside_project == 0
    assert not data.responses[0].in_project
