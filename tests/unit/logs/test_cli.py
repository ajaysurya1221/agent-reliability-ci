"""CLI integration on generated logs only; every error stays private."""

import io
import json
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from arci import cli as arci_cli
from arci.logs import cli, report
from arci.logs.example import load
from arci.logs.schema import LogsDecision, verify_seal
from tests.unit.logs.synth_logs import assistant, generate, write_rows
from tests.unit.logs.test_report import SNAPSHOTS, normalize_version


def invoke(tmp_path: Path, args: list[str], *, now: datetime | None = None) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    code = cli.run(
        args, now=now or datetime(2026, 11, 15, tzinfo=UTC), env={}, home=tmp_path, out=out, err=err
    )
    return code, out.getvalue(), err.getvalue()


@pytest.mark.parametrize(
    "tool,code,names",
    [
        ("auto", 1, ("Claude Code", "Codex")),
        ("both", 1, ("Claude Code", "Codex")),
        ("claude-code", 1, ("Claude Code",)),
        ("codex", 0, ("Codex",)),
    ],
)
def test_requested_tools(tmp_path: Path, tool: str, code: int, names: tuple[str, ...]) -> None:
    status, out, err = invoke(tmp_path, ["--example", "--tool", tool])
    assert status == code and err == ""
    for name in ("Claude Code", "Codex"):
        assert (name in out) == (name in names)


@pytest.mark.parametrize(
    "args,code,message",
    [
        (["--since", "2026-11-01"], 1, ""),
        (["--since", "2026-11-15"], 2, ""),
        (["--since", "2026-08-23"], 2, ""),
        (["--since", "2026-08-22"], 3, report.SINCE_EARLY),
        (["--since", "20261101"], 3, report.SINCE_DATE),
        (["--since", "2026-02-30"], 3, report.SINCE_DATE),
        (["--since", "CANARY-private"], 3, report.SINCE_DATE),
        (["--unknown-CANARY"], 3, report.USAGE_ERROR),
        (["--tool", "CANARY"], 3, report.USAGE_ERROR),
        (["--model"], 3, report.USAGE_ERROR),
        (["--model", "model-1", "--effort", "high"], 1, ""),
        (["--model", "claude-example-1"], 2, ""),
        (["--effort", "CANARY"], 2, ""),
    ],
)
def test_options(tmp_path: Path, args: list[str], code: int, message: str) -> None:
    status, out, err = invoke(tmp_path, ["--example", *args])
    assert status == code
    assert err == (message + "\n" if message else "")
    assert "CANARY" not in out + err
    if message:
        assert out == ""
    if args == ["--since", "2026-11-15"]:
        assert "after   no days   split 2026-11-15" in out


def test_outputs_and_override_dirs(tmp_path: Path) -> None:
    json_path, md = tmp_path / "CANARY.json", tmp_path / "CANARY.md"
    code, out, err = invoke(
        tmp_path,
        [
            "--example",
            "--claude-dir",
            "CANARY",
            "--codex-dir",
            "CANARY",
            "--json",
            str(json_path),
            "--markdown",
            str(md),
        ],
    )
    assert code == 1 and not err
    decision = LogsDecision.model_validate_json(json_path.read_text())
    assert verify_seal(decision)
    assert out == report.render_text(decision)
    assert md.read_text() == report.render_markdown(decision)
    assert (
        json_path.read_text()
        == json.dumps(decision.model_dump(mode="json"), sort_keys=True, indent=2) + "\n"
    )
    assert "CANARY" not in out + err + json_path.read_text() + md.read_text()


@pytest.mark.parametrize("option", ["--json", "--markdown", "--html"])
def test_unwritable_output(tmp_path: Path, option: str) -> None:
    code, out, err = invoke(tmp_path, ["--example", option, str(tmp_path / "CANARY" / "a")])
    assert (code, out, err) == (3, "", report.WRITE_ERROR + "\n")


def test_html_output(tmp_path: Path) -> None:
    from arci.logs.html import render_html

    target, record = tmp_path / "page.html", tmp_path / "record.json"
    code, _, err = invoke(tmp_path, ["--example", "--html", str(target), "--json", str(record)])
    decision = LogsDecision.model_validate_json(record.read_text())
    assert code == 1 and not err and verify_seal(decision)
    assert target.read_text() == render_html(decision)


def test_synthetic_canaries_project_and_auto(tmp_path: Path) -> None:
    logs = generate(tmp_path / "CANARY", compressed=False)
    for tool in ("both", "auto", "claude-code", "codex"):
        for project in (logs.project, tmp_path / "CANARY-outside"):
            target = tmp_path / "CANARY.json"
            code, out, err = invoke(
                tmp_path,
                [
                    "--tool",
                    tool,
                    "--claude-dir",
                    str(logs.claude_root),
                    "--codex-dir",
                    str(logs.codex_root),
                    "--project",
                    str(project),
                    "--json",
                    str(target),
                ],
                now=logs.now,
            )
            assert code == 2 and not err
            for secret in ("CANARY", "canary-payroll", "98234567", str(tmp_path)):
                assert secret not in out + err + target.read_text()
            assert LogsDecision.model_validate_json(target.read_text()).project_filtered
    # Auto only requests the one existing root.
    code, out, err = invoke(tmp_path, ["--claude-dir", str(logs.claude_root)])
    assert code == 2 and not err and "Codex" not in out


def test_no_logs_and_unrecognised(tmp_path: Path) -> None:
    code, out, err = invoke(tmp_path, [])
    assert code == 3 and not err and out.count("RESULT: ERROR") == 2
    root = tmp_path / "logs"
    write_rows(root / "a.jsonl", [{"type": "CANARY"}])
    code, out, err = invoke(tmp_path, ["--tool", "claude-code", "--claude-dir", str(root)])
    assert code == 3 and report.F5["format_not_recognised"] in out and not err


def test_error_beside_result(tmp_path: Path) -> None:
    _, codex, now = load()
    code, out, err = invoke(tmp_path, ["--tool", "both", "--codex-dir", str(codex)], now=now)
    assert code == 0 and not err and "RESULT: ERROR" in out and "RESULT: NO DROP" in out


def test_offset_and_utc(tmp_path: Path) -> None:
    claude, _, _ = load()
    now = datetime(2026, 11, 15, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    args = ["--tool", "claude-code", "--claude-dir", str(claude)]
    assert "UTC+05:30" in invoke(tmp_path, args, now=now)[1]
    assert "UTC+00:00" in invoke(tmp_path, [*args, "--utc"], now=now)[1]


def test_unknown_effort_rendered_name(tmp_path: Path) -> None:
    path = tmp_path / "logs" / "a.jsonl"
    write_rows(path, [assistant("x", effort="CANARY", model="canary-payroll-200")])
    args = [
        "--tool",
        "claude-code",
        "--claude-dir",
        str(path.parent),
        "--model",
        "model-1",
        "--effort",
        "effort-1",
    ]
    code, out, err = invoke(tmp_path, args)
    assert code == 2 and not err and "model-1 · effort effort-1" in out
    assert "CANARY" not in out


def test_internal_errors_are_fixed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(*args: object, **kwargs: object) -> str:
        raise RuntimeError("CANARY private traceback")

    monkeypatch.setattr(report, "render_text", broken)
    assert invoke(tmp_path, ["--example"]) == (3, "", report.INTERNAL_ERROR + "\n")


def test_out_of_range_timestamp_is_not_a_calendar_error(tmp_path: Path) -> None:
    root = tmp_path / "logs"
    write_rows(root / "a.jsonl", [assistant(stamp="0001-01-01T12:00:00Z")])
    code, out, err = invoke(tmp_path, ["--tool", "claude-code", "--claude-dir", str(root)])
    assert code == 3 and not err
    assert report.F5["format_not_recognised"] in out


def test_main_dispatch(capsys: pytest.CaptureFixture[str]) -> None:
    assert arci_cli.main(["logs", "--example"]) == 1
    output = capsys.readouterr()
    assert normalize_version(output.out) == normalize_version(
        (SNAPSHOTS / "example.txt").read_text()
    )
    assert output.out.splitlines()[1] == report.F13
    assert output.err == ""


def test_help_does_not_read_logs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: object) -> list[Path]:
        raise AssertionError("should not discover logs")

    monkeypatch.setattr(cli.discover, "claude_files", forbidden)
    code, out, err = invoke(tmp_path, ["--help"])
    assert code == 0 and not err and "--example" in out


def test_unreadable_tool_files(tmp_path: Path) -> None:
    root = tmp_path / "logs"
    root.mkdir()
    (root / "a.jsonl").write_bytes(b"\xff\xfeCANARY")
    code, out, err = invoke(tmp_path, ["--tool", "claude-code", "--claude-dir", str(root)])
    assert code == 3 and not err and report.F5["format_not_recognised"] in out
    assert "CANARY" not in out


def test_missing_context_is_a_dash(tmp_path: Path) -> None:
    code, out, err = invoke(tmp_path, ["--example", "--since", "2026-11-15"])
    assert code == 2 and not err
    assert "-> -" in out and "-%" not in out


@pytest.mark.parametrize("args", [["--unknown"], ["--tool", "invalid"], ["--model"]])
def test_usage_error_is_one_fixed_line_and_writes_nothing(tmp_path: Path, args: list[str]) -> None:
    target = tmp_path / "record.json"
    assert invoke(tmp_path, ["--example", "--json", str(target), *args]) == (
        3,
        "",
        "Usage error. Run: realornoise --help\n",
    )
    assert not target.exists()
