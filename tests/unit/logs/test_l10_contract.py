"""Regressions for the clarified response, window and reader counter rules."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from arci.logs import claude_code, codex
from arci.logs.decide import decide_tool
from arci.logs.measures import build
from tests.unit.logs.synth_logs import assistant, context, meta, result, token, write_rows
from tests.unit.logs.test_cli import invoke
from tests.unit.logs.test_measures import sample, table

NOW = datetime(2026, 2, 1, tzinfo=UTC)


@pytest.mark.parametrize("tool", ["claude-code", "codex"])
def test_missing_setting_still_supplies_main_response_split(tmp_path: Path, tool: str) -> None:
    path = tmp_path / "logs.jsonl"
    if tool == "claude-code":
        write_rows(path, [assistant(model=None)])
        data = claude_code.read([path], project=None, now=NOW)
    else:
        write_rows(path, [meta(), token()])
        data = codex.read([path], project=None, now=NOW)
    decision = decide_tool(build(data, utc_offset=timedelta(), now=NOW), data.counters)
    assert decision.reason == "no_usable_setting"
    assert decision.split_date == "2025-12-19"
    assert data.counters.responses == 0
    assert data.counters.responses_without_setting == 1


def test_filtered_out_setting_keeps_split() -> None:
    data = sample()
    decision = decide_tool(table(data, model="model-99"), data.counters)
    assert decision.reason == "no_usable_setting" and decision.split_date == "2026-05-01"


def test_outside_codex_file_counts_only_header(tmp_path: Path) -> None:
    path = tmp_path / "rollout.jsonl"
    write_rows(path, [meta(cwd="/outside"), "not json", context(), token()])
    data = codex.read([path], project=Path("/project"), now=NOW)
    assert data.counters.lines == 1 and data.counters.files_outside_project == 1
    assert data.counters.lines_not_json == data.counters.responses == 0


@pytest.mark.parametrize("tool", ["claude-code", "codex"])
def test_responses_counts_only_kept_responses(tmp_path: Path, tool: str) -> None:
    path = tmp_path / "logs.jsonl"
    if tool == "claude-code":
        write_rows(path, [assistant("missing", model=None), assistant(), assistant(reasoning=20)])
        data = claude_code.read([path, path], project=None, now=NOW)
    else:
        write_rows(path, [meta(), token(), context(), token(2), token(2)])
        data = codex.read([path, path], project=None, now=NOW)
    assert data.counters.responses == len(data.responses) == 1
    assert data.counters.responses_without_setting == 1
    assert data.counters.responses_duplicate > 0


def test_nonedit_result_has_no_edit_counter_even_when_denied_or_future(tmp_path: Path) -> None:
    path = tmp_path / "logs.jsonl"
    write_rows(
        path,
        [
            assistant(content=[{"type": "tool_use", "id": "read", "name": "Read"}]),
            result("read", toolDenialKind="denied", stamp="2030-01-01T12:00:00Z"),
            result("missing"),
        ],
    )
    data = claude_code.read([path], project=None, now=NOW)
    assert data.edits == ()
    assert data.counters.edits_unmatched == 1
    assert data.counters.edits_denied == data.counters.records_in_future == 0


def test_unknown_names_numbered_without_known_names() -> None:
    data = sample()
    data = replace(
        data,
        models=("gpt-6", None, None),
        efforts=("high", None, None),
        model_order=(1, 0, 2),
        effort_order=(0, 2, 1),
        responses=tuple(replace(r, model=2, effort=1) for r in data.responses),
    )
    actual = table(data)
    assert actual.model == "model-2" and actual.effort == "effort-2"


def test_claude_override_is_projects_directory_itself(tmp_path: Path) -> None:
    projects = tmp_path / "projects"
    write_rows(projects / "a-project" / "log.jsonl", [assistant()])
    code, out, err = invoke(tmp_path, ["--tool", "claude-code", "--claude-dir", str(projects)])
    assert code == 2 and not err
    assert "claude-opus-5-5" in out
