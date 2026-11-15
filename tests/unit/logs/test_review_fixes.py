"""Regression cases from L13a, using synthetic logs only."""

import os
from datetime import UTC, datetime
from io import BytesIO, StringIO
from pathlib import Path

import pytest

from arci.logs import claude_code, codex, discover
from arci.logs.cli import run
from arci.logs.records import in_project
from tests.unit.logs.synth_logs import Row, assistant, context, meta, token, write_rows

NOW = datetime(2026, 2, 1, tzinfo=UTC)


@pytest.mark.parametrize("session", ["session", None])
def test_codex_repeated_total_with_new_time(tmp_path: Path, session: str | None) -> None:
    path = tmp_path / "rollout-a.jsonl"
    write_rows(path, [meta(id=session), context(), token(), token(stamp="2026-01-02T00:00:00Z")])
    actual = codex.read([path], project=None, now=NOW)
    assert len(actual.responses) == 1
    assert actual.counters.responses_duplicate == 1


@pytest.mark.parametrize("tool", ["claude-code", "codex"])
@pytest.mark.parametrize("bom", [False, True])
def test_byte_fault_is_one_line_and_bom_is_ignored(tmp_path: Path, tool: str, bom: bool) -> None:
    path = tmp_path / "rollout-a.jsonl"
    rows: list[Row] = [assistant()] if tool == "claude-code" else [meta(), context(), token()]
    encoded = write_rows(path, rows)
    path.write_bytes((b"\xef\xbb\xbf" if bom else b"") + encoded + b"\xff\n")
    reader = claude_code.read if tool == "claude-code" else codex.read
    actual = reader([path], project=None, now=NOW)
    assert len(actual.responses) == 1
    assert actual.counters.files_unreadable == 0
    assert actual.counters.lines_not_json == 1


@pytest.mark.parametrize("tool", ["claude-code", "codex"])
def test_failed_read_discards_file_and_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tool: str
) -> None:
    bad, good = tmp_path / "bad.jsonl", tmp_path / "good.jsonl"
    rows: list[Row] = [assistant()] if tool == "claude-code" else [meta(), context(), token()]
    encoded = write_rows(bad, rows)
    write_rows(good, rows)
    original = Path.open

    class Broken(BytesIO):
        def __next__(self) -> bytes:
            value = super().readline()
            if not value:
                raise OSError("private fault")
            return value

    def open_file(path: Path, mode: str = "r", **kwargs: object):
        if path == bad:
            return Broken(encoded)
        return original(path, mode)

    monkeypatch.setattr(Path, "open", open_file)
    reader = claude_code.read if tool == "claude-code" else codex.read
    actual = reader([bad, good], project=None, now=NOW)
    assert len(actual.responses) == actual.counters.responses == 1
    assert actual.counters.responses_duplicate == 0
    assert actual.counters.files_unreadable == 1


@pytest.mark.parametrize("effort", [None, "", 42])
def test_false_api_error_and_empty_effort_fallback(tmp_path: Path, effort: object) -> None:
    path = tmp_path / "a.jsonl"
    write_rows(path, [assistant(effort=effort, perTurnEffort="max", isApiErrorMessage=False)])
    actual = claude_code.read([path], project=None, now=NOW)
    assert len(actual.responses) == 1
    assert actual.efforts[actual.responses[0].effort] == "max"


@pytest.mark.parametrize(
    "stamp",
    [
        "0001-01-01T00:00:00Z",
        "1999-12-31T23:59:59Z",
        "2200-01-01T00:00:01Z",
        "9999-12-31T23:59:59Z",
    ],
)
@pytest.mark.parametrize("tool", ["claude-code", "codex"])
def test_extreme_timestamp_is_missing(tmp_path: Path, tool: str, stamp: str) -> None:
    path = tmp_path / "sessions/rollout-a.jsonl"
    rows: list[Row] = (
        [assistant(stamp=stamp)]
        if tool == "claude-code"
        else [meta(), context(), token(stamp=stamp)]
    )
    rows += [assistant("valid")] if tool == "claude-code" else [token(2)]
    write_rows(path, rows)
    reader = claude_code.read if tool == "claude-code" else codex.read
    actual = reader([path], project=None, now=NOW)
    assert len(actual.responses) == 1
    assert actual.counters.lines_lacking_field == 1
    out, err = StringIO(), StringIO()
    code = run(
        ["--tool", tool, "--claude-dir", str(tmp_path), "--codex-dir", str(tmp_path)],
        now=NOW,
        home=tmp_path,
        env={},
        out=out,
        err=err,
    )
    assert code == 2 and not err.getvalue()


@pytest.mark.parametrize("project", [".", "child", "~/child", "child/"])
def test_project_is_absolute_lexical(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, project: str
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    expected = os.path.abspath(os.path.expanduser(project))
    assert in_project(expected + "/sub", Path(project))
    assert not in_project(expected + "-other", Path(project))


def test_discovery_excludes_fifo(tmp_path: Path) -> None:
    folder = tmp_path / "sessions"
    folder.mkdir()
    fifo = folder / "rollout-pipe.jsonl"
    os.mkfifo(fifo)
    good = folder / "rollout-good.jsonl"
    good.touch()
    (folder / "rollout-link.jsonl").symlink_to(good)
    assert fifo not in discover.claude_files(tmp_path)
    assert fifo not in discover.codex_files(tmp_path)
    assert len(discover.codex_files(tmp_path)) == 2


def test_output_failure_preserves_targets(tmp_path: Path) -> None:
    target = tmp_path / "first.json"
    target.write_text("original")
    out, err = StringIO(), StringIO()
    code = run(["--example", "--json", str(target), "--html", str(tmp_path)], out=out, err=err)
    assert code == 3 and err.getvalue() == "Requested output could not be written.\n"
    assert target.read_text() == "original"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["first.json"]
    assert not out.getvalue()


def test_duplicate_output_paths_are_usage_error(tmp_path: Path) -> None:
    target = tmp_path / "out"
    out, err = StringIO(), StringIO()
    code = run(
        ["--example", "--json", str(target), "--markdown", str(tmp_path / "." / "out")],
        out=out,
        err=err,
    )
    assert code == 3 and err.getvalue() == "Two output options name the same file.\n"
    assert not target.exists() and not out.getvalue()


def test_auto_keeps_explicit_missing_tool(tmp_path: Path) -> None:
    from arci.logs.example import load

    _, root, _ = load()
    out, err = StringIO(), StringIO()
    run(
        ["--claude-dir", str(tmp_path / "missing"), "--codex-dir", str(root)],
        now=NOW,
        home=tmp_path,
        env={},
        out=out,
        err=err,
    )
    assert (
        "No session logs found for Claude Code under the directory given with --claude-dir."
        in out.getvalue()
    )
    assert not err.getvalue()


@pytest.mark.parametrize(
    "field,value", [("p_streak", "1/2"), ("p_real", "1/2"), ("u_none", 49), ("p_none", "1/100")]
)
def test_validator_rejects_plausible_but_forged_tests(field: str, value: object) -> None:
    from pydantic import ValidationError

    from arci.logs.schema import MeasureDecision
    from tests.unit.logs.test_schema import decision

    payload = decision().tools[0].measures[0].model_dump()
    payload[field] = value
    with pytest.raises(ValidationError):
        MeasureDecision.model_validate(payload)


def test_error_reports_unread_files_and_compression() -> None:
    from arci.logs import report
    from arci.logs.decide import error_tool
    from arci.logs.records import ReaderCounters
    from tests.unit.logs.test_report import record

    decision = record(
        (
            error_tool(
                "codex", "read_error", ReaderCounters(files_unread_compressed=2, files_unreadable=1)
            ),
        )
    )
    for render in (report.render_text, report.render_markdown):
        output = render(decision)
        assert report.F9_ERROR.format(k=2) in output
        assert report.F9_NEXT in output
        assert report.F17_ERROR.format(k=1) in output


def test_markdown_has_no_wrapping() -> None:
    from arci.logs import report
    from tests.unit.logs.test_report import example_record

    decision = example_record()
    output = report.render_markdown(decision)
    assert (
        report.MD_LIMITS.format(
            digest=(decision.tools[0].day_table_sha256 or "")[:12],
            rate_max=report.RATE_MAX,
            worst_after=report.RATE_MAX_AFTER,
            worst_before=report.RATE_MAX_BEFORE,
        )
        in output
    )
    assert report.context_text(decision.tools[0]) in output


def test_snapshots_ignore_only_header_version() -> None:
    from tests.unit.logs import test_report

    normalize = test_report.normalize_version
    assert (
        normalize("realornoise 2.2.0 · header\n2.2.0 data\n")
        == "realornoise <version> · header\n2.2.0 data\n"
    )


def test_record_updates_are_carried_into_docs() -> None:
    root = Path(__file__).resolve().parents[3]
    design = (root / "docs/design/0016-logs.md").read_text()
    stats = (root / "docs/STATISTICS_LOGS.md").read_text()
    formats = (root / "docs/LOG_FORMATS.md").read_text()
    assert "The validator also recomputes `p_streak`, `p_real`, `u_none` and `p_none`" in design
    assert "A gated cell is never run on fewer tables than stated" in stats
    assert "A line that is not valid UTF-8 is a line that is not JSON" in formats
    assert "untested on Windows" in formats
    assert "numbers only" not in design


@pytest.mark.parametrize("failure", ["render", "stage", "move", "interrupt"])
def test_output_failure_rolls_back_every_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    from arci.logs import cli, report

    first, second = tmp_path / "first.json", tmp_path / "second.md"
    first.write_text("old-json")
    second.write_text("old-markdown")
    if failure == "render":

        def render_failure(*args: object) -> str:
            raise ValueError("private")

        monkeypatch.setattr(report, "render_markdown", render_failure)
    elif failure == "stage":
        original_write = Path.write_text
        writes = 0

        def write_failure(path: Path, data: str, **kwargs: object) -> int:
            nonlocal writes
            writes += 1
            if writes == 2:
                raise OSError("private")
            return original_write(path, data, encoding="utf-8")

        monkeypatch.setattr(Path, "write_text", write_failure)
    else:
        original_replace = os.replace

        def move_failure(source: Path, target: Path) -> None:
            if target == second:
                if failure == "interrupt":
                    raise KeyboardInterrupt
                raise OSError("private")
            original_replace(source, target)

        monkeypatch.setattr(cli.os, "replace", move_failure)
    out, err = StringIO(), StringIO()
    assert (
        run(["--example", "--json", str(first), "--markdown", str(second)], out=out, err=err) == 3
    )
    assert (
        err.getvalue()
        == (report.INTERNAL_ERROR if failure == "render" else report.WRITE_ERROR) + "\n"
    )
    assert first.read_text() == "old-json" and second.read_text() == "old-markdown"
    assert set(tmp_path.iterdir()) == {first, second}
    assert not out.getvalue()


def test_relative_project_cli_matches_absolute(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "logs/sessions/rollout-a.jsonl"
    write_rows(path, [meta(cwd=str(tmp_path / "project/sub")), context(), token()])

    def execute(project: str) -> str:
        out, err = StringIO(), StringIO()
        assert (
            run(
                ["--tool", "codex", "--codex-dir", str(path.parents[1]), "--project", project],
                now=NOW,
                env={},
                home=tmp_path,
                out=out,
                err=err,
            )
            == 2
        )
        assert not err.getvalue()
        return out.getvalue()

    assert execute("project/") == execute(str(tmp_path / "project"))


@pytest.mark.parametrize("tool", ["claude-code", "codex"])
def test_unzoned_out_of_range_time_is_missing(tmp_path: Path, tool: str) -> None:
    path = tmp_path / "a.jsonl"
    rows: list[Row] = (
        [assistant(stamp="0001-01-01T00:00:00")]
        if tool == "claude-code"
        else [meta(), context(), token(stamp="0001-01-01T00:00:00")]
    )
    write_rows(path, rows)
    reader = claude_code.read if tool == "claude-code" else codex.read
    actual = reader([path], project=None, now=NOW)
    assert actual.counters.lines_lacking_field == 1
    assert actual.counters.records_without_timezone == 0


def test_codex_null_info_breaks_consecutive_repeat(tmp_path: Path) -> None:
    path = tmp_path / "a.jsonl"
    write_rows(
        path,
        [
            meta(id=None),
            context(),
            token(),
            {"type": "event_msg", "payload": {"type": "token_count", "info": None}},
            token(stamp="2026-01-02T00:00:00Z"),
        ],
    )
    actual = codex.read([path], project=None, now=NOW)
    assert len(actual.responses) == 2
    assert actual.counters.responses_duplicate == 0


def test_nonregular_compressed_file_is_not_opened(tmp_path: Path) -> None:
    path = tmp_path / "rollout-pipe.jsonl.zst"
    os.mkfifo(path)
    actual = codex.read([path], project=None, now=NOW)
    assert actual.counters.files_unreadable == 1
    assert actual.counters.files_unread_compressed == 0


def test_malformed_output_path_is_fixed_write_error() -> None:
    out, err = StringIO(), StringIO()
    assert run(["--example", "--json", "private\0path"], out=out, err=err) == 3
    assert err.getvalue() == "Requested output could not be written.\n"
    assert not out.getvalue()


def test_markdown_without_setting_does_not_wrap_limits() -> None:
    from arci.logs import report
    from tests.unit.logs.test_report import cases

    assert " ".join(report.limits_text().splitlines()) in report.render_markdown(
        cases()["no_usable_setting"]
    )
