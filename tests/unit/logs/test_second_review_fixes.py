"""L13b regression cases, using generated data and temporary paths only."""

import os
import stat
import unicodedata
from io import StringIO
from pathlib import Path

import pytest
from pydantic import ValidationError

from arci.logs import cli, report
from arci.logs.decide import error_tool
from arci.logs.html import render_html
from arci.logs.records import ReaderCounters, Tool
from arci.logs.schema import MeasureDecision, ToolDecision
from tests.unit.logs.test_report import record
from tests.unit.logs.test_schema import decision


@pytest.mark.parametrize(
    "names", [("out.txt", "OUT.txt"), ("café.txt", unicodedata.normalize("NFD", "café.txt"))]
)
def test_new_output_aliases_leave_nothing(
    tmp_path: Path, names: tuple[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    first, second = (tmp_path / name for name in names)
    first.touch()
    folds = second.exists() and first.samefile(second)
    first.unlink()
    if not folds:
        pytest.skip("This volume keeps the tested spellings apart.")

    def no_read(*args: object, **kwargs: object) -> None:
        pytest.fail("output aliases must be checked before logs")

    monkeypatch.setattr(cli.claude_code, "read", no_read)
    out, err = StringIO(), StringIO()
    assert (
        cli.run(["--example", "--json", str(first), "--markdown", str(second)], out=out, err=err)
        == 3
    )
    assert err.getvalue() == "Two output options name the same file.\n"
    assert not out.getvalue() and not list(tmp_path.iterdir())


def test_distinct_new_outputs_and_umask(tmp_path: Path) -> None:
    first, second = tmp_path / "out.json", tmp_path / "out.md"
    previous = os.umask(0o022)
    try:
        assert (
            cli.run(
                ["--example", "--json", str(first), "--markdown", str(second)],
                out=StringIO(),
                err=StringIO(),
            )
            == 1
        )
    finally:
        os.umask(previous)
    for path in (first, second):
        assert path.stat().st_size > 0
        assert stat.S_IMODE(path.stat().st_mode) == 0o644
    assert set(tmp_path.iterdir()) == {first, second}


def test_existing_output_keeps_permissions(tmp_path: Path) -> None:
    target = tmp_path / "out.json"
    target.write_text("old")
    target.chmod(0o640)
    assert cli.run(["--example", "--json", str(target)], out=StringIO(), err=StringIO()) == 1
    assert target.read_text() != "old"
    assert stat.S_IMODE(target.stat().st_mode) == 0o640


def test_failed_restore_keeps_backup_and_restores_other_targets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first, second, third = (tmp_path / name for name in ("first", "second", "third"))
    for path in (first, second, third):
        path.write_text("old-" + path.name)
    original = os.replace
    moves = 0

    def replace(source: Path, target: Path) -> None:
        nonlocal moves
        moves += 1
        if moves in (3, 4):
            raise OSError("install fails, then restore fails")
        original(source, target)

    monkeypatch.setattr(cli.os, "replace", replace)
    out, err = StringIO(), StringIO()
    assert (
        cli.run(
            ["--example", "--json", str(first), "--markdown", str(second), "--html", str(third)],
            out=out,
            err=err,
        )
        == 3
    )
    assert err.getvalue() == report.WRITE_ERROR + "\n" and not out.getvalue()
    assert first.read_text() == "old-first" and third.read_text() == "old-third"
    backups = set(tmp_path.iterdir()) - {first, second, third}
    assert len(backups) == 1
    assert backups.pop().read_text() == "old-second"


@pytest.mark.parametrize("output", [False, True])
def test_rendering_failure_is_internal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, output: bool
) -> None:
    def fail(*args: object, **kwargs: object) -> str:
        raise ValueError("private rendering failure")

    monkeypatch.setattr(report, "render_text", fail)
    out, err = StringIO(), StringIO()
    args = ["--example", *(["--json", str(tmp_path / "out")] if output else [])]
    assert cli.run(args, out=out, err=err) == 3
    assert err.getvalue() == report.INTERNAL_ERROR + "\n"
    assert not out.getvalue() and not list(tmp_path.iterdir())


@pytest.mark.parametrize("format", ["txt", "md", "html"])
def test_error_notices_have_no_result_sentence(format: str) -> None:
    value = record(
        (
            error_tool(
                "codex", "read_error", ReaderCounters(files_unread_compressed=2, files_unreadable=1)
            ),
        )
    )
    render = {"txt": report.render_text, "md": report.render_markdown, "html": render_html}[format]
    output = render(value)
    assert "Compressed Codex files not read (Python 3.14 is needed): 2." in output
    assert report.F9_NEXT in output and "Files that could not be read: 1." in output
    assert "The result uses the rest." not in output


@pytest.mark.parametrize("tool", ["claude-code", "codex"])
@pytest.mark.parametrize("explicit", [False, True])
def test_no_logs_directory_wording(tmp_path: Path, tool: Tool, explicit: bool) -> None:
    flag = report.FLAGS[tool]
    out, err = StringIO(), StringIO()
    markdown, html = tmp_path / "out.md", tmp_path / "out.html"
    args = ["--tool", tool, "--markdown", str(markdown), "--html", str(html)]
    if explicit:
        args.extend([flag, str(tmp_path / "PRIVATE-missing")])
    assert cli.run(args, home=tmp_path, env={}, out=out, err=err) == 3
    assert not err.getvalue()
    expected = (
        f"No session logs found for {report.TOOL_NAMES[tool]} "
        f"under the directory given with {flag}. "
        "Or try: realornoise --example"
        if explicit
        else report.F5["no_logs"].format(
            Tool=report.TOOL_NAMES[tool], default=report.DEFAULTS[tool], flag=flag
        )
    )
    for text in (out.getvalue(), markdown.read_text(), html.read_text()):
        assert expected in " ".join(text.split())
        assert "PRIVATE-missing" not in text


@pytest.mark.parametrize("mutation", ["value", "count", "digest"])
def test_day_table_digest_rejects_tampering(mutation: str) -> None:
    original = decision().tools[0]
    payload = original.model_dump()
    if mutation == "digest":
        payload["day_table_sha256"] = "0" * 64
    else:
        measure = payload["measures"][0]
        day = measure["before_days"][0]
        if mutation == "count":
            day["count"] += 1
        else:
            # A nonmedian value can change without altering ranks or statistics.
            day["value"] = "19/1"
        MeasureDecision.model_validate(measure)
    with pytest.raises(ValidationError, match="inconsistent_day_table_sha256"):
        ToolDecision.model_validate(payload)
