"""Guards against three 2026 session-log format changes that broke `ccusage`.

Each test names the incident it guards and the date `ccusage` reported it broken.
`docs/LOG_FORMATS.md` and `docs/design/0017-logs-2.md` describe the readers' documented
behaviour; these tests check that behaviour using only synthetic data from
`tests/unit/logs/synth_logs.py`, never real session logs.
"""

from __future__ import annotations

import importlib
import io
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest

from arci.logs import cli
from arci.logs.claude_code import read as read_claude_code
from arci.logs.codex import read as read_codex
from arci.logs.schema import LogsDecision
from tests.unit.logs.synth_logs import Row, assistant, context, meta, token, write_rows

NOW = datetime(2026, 2, 1, tzinfo=UTC)


# -- 12 Sep 2026, ccusage issue 1710: a null model inside usage.iterations[] -----------


def test_incident_2026_09_12_claude_code_null_model_in_iterations(tmp_path: Path) -> None:
    """ccusage issue 1710 (12 Sep 2026): Claude Code started writing a `null` model
    inside `usage.iterations[]` of an assistant line, alongside other unknown keys. The
    response is still read from the documented fields, with nothing counted as a fault.
    """
    path = tmp_path / "session.jsonl"
    row = assistant("CANARY-iterations", model="claude-opus-5-5", reasoning=10)
    message = cast(dict[str, object], row["message"])
    usage = cast(dict[str, object], message["usage"])
    usage["iterations"] = [
        {"model": None, "CANARY-mystery-key": 1},
        {"model": "ignored-model-x", "effort": "ignored", "reasoning_tokens": None},
    ]
    message["CANARY-unknown-message-key"] = {"also": "ignored"}
    row["CANARY-unknown-top-key"] = None
    write_rows(path, [row])

    actual = read_claude_code([path], project=None, now=NOW)

    assert len(actual.responses) == 1
    response = actual.responses[0]
    assert actual.models[response.model] == "claude-opus-5-5"
    assert actual.efforts[response.effort] == "high"
    assert response.reasoning == 10
    assert actual.counters.lines_not_json == 0
    assert actual.counters.lines_unknown_type == 0
    assert actual.counters.lines_lacking_field == 0
    assert actual.counters.responses_without_setting == 0
    assert actual.counters.responses_without_reasoning == 0
    assert actual.counters.files_unreadable == 0


# -- 14 Oct 2026, ccusage issue 1888: a session kept twice, once compressed ------------


def test_incident_2026_10_14_codex_compressed_duplicate_is_counted_once(
    tmp_path: Path,
) -> None:
    """ccusage issue 1888 (14 Oct 2026): Codex compresses sessions idle 7 days to
    `.jsonl.zst`, in both `sessions/` and `archived_sessions/`, and removes the plain
    file only after checking the compressed one; during that step both files can exist.
    On a Python that can read the compressed file, each response is still counted once.
    """
    try:
        zstd = importlib.import_module("compression.zstd")
    except ImportError:
        pytest.skip("compression.zstd needs Python 3.14; see the fallback test below")
    paths: list[Path] = []
    for folder, session in (("sessions", "CANARY-dup-a"), ("archived_sessions", "CANARY-dup-b")):
        plain = tmp_path / folder / f"rollout-{session}.jsonl"
        encoded = write_rows(plain, [meta(id=session), context(), token(1, 5), token(2, 6)])
        compressed = plain.with_suffix(".jsonl.zst")
        compressed.write_bytes(cast(bytes, zstd.compress(encoded)))
        paths.extend([plain, compressed])

    actual = read_codex(paths, project=None, now=NOW)

    assert actual.counters.files_unread_compressed == 0
    assert actual.counters.files_unreadable == 0
    assert len(actual.responses) == 4
    assert actual.counters.responses_duplicate == 4


def test_incident_2026_10_14_codex_compressed_fallback_uses_the_plain_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ccusage issue 1888 (14 Oct 2026), the documented fallback: without a Python that
    can read `.jsonl.zst`, the compressed copy is counted as not read and the plain file
    is used, in both `sessions/` and `archived_sessions/`. Simulated so this holds on any
    Python, not only one lacking `compression.zstd`.
    """
    paths: list[Path] = []
    for folder, session in (("sessions", "CANARY-dup-a"), ("archived_sessions", "CANARY-dup-b")):
        plain = tmp_path / folder / f"rollout-{session}.jsonl"
        write_rows(plain, [meta(id=session), context(), token(1, 5), token(2, 6)])
        compressed = plain.with_suffix(".jsonl.zst")
        compressed.write_bytes(b"CANARY-not-decompressed-on-this-python")
        paths.extend([plain, compressed])

    def absent(name: str) -> None:
        assert name == "compression.zstd"
        raise ModuleNotFoundError("CANARY-module-not-found")

    monkeypatch.setattr("arci.logs.codex.importlib.import_module", absent)
    actual = read_codex(paths, project=None, now=NOW)

    assert actual.counters.files_unread_compressed == 2
    assert actual.counters.files_unreadable == 0
    assert len(actual.responses) == 4
    assert actual.counters.responses_duplicate == 0


# -- 6 Nov 2026, ccusage issue 2033: a truncated record stopped the whole report -------


def test_incident_2026_11_06_codex_truncated_last_line(tmp_path: Path) -> None:
    """ccusage issue 2033 (6 Nov 2026): a Codex record cut off in the middle of its JSON
    stopped the tool with an error for the whole report. Here the cut line is the file's
    last line; the run does not fail, the complete lines are used, and the cut-off line
    is counted as `lines_not_json`, as `docs/LOG_FORMATS.md` says invalid JSON is counted.
    """
    path = tmp_path / "rollout.jsonl"
    write_rows(path, [meta(), context(), token(1, 5)])
    with path.open("ab") as handle:
        handle.write(
            b'{"type":"event_msg","timestamp":"2026-01-01T13:00:00Z","payload":{"type":"tok'
        )

    actual = read_codex([path], project=None, now=NOW)

    assert actual.counters.files_unreadable == 0
    assert actual.counters.files_read == 1
    assert actual.counters.lines_not_json == 1
    assert len(actual.responses) == 1


def test_incident_2026_11_06_codex_truncated_line_in_the_middle(tmp_path: Path) -> None:
    """ccusage issue 2033 (6 Nov 2026), the other reported shape: the cut line sits in
    the middle of the file, not at its end. Later complete lines are still used.
    """
    path = tmp_path / "rollout.jsonl"
    cutoff = '{"type":"event_msg","timestamp":"2026-01-01T12:30:00Z","payload":{"type":"tok'
    rows: list[Row] = [meta(), context(), token(1, 5), cutoff, token(2, 6)]
    write_rows(path, rows)

    actual = read_codex([path], project=None, now=NOW)

    assert actual.counters.files_unreadable == 0
    assert actual.counters.lines_not_json == 1
    assert len(actual.responses) == 2


def test_incident_2026_11_06_claude_code_truncated_last_line(tmp_path: Path) -> None:
    """ccusage issue 2033 (6 Nov 2026), the same shape for Claude Code: a cut-off last
    line does not fail the run, and the complete line is still read.
    """
    path = tmp_path / "session.jsonl"
    write_rows(path, [assistant("CANARY-before")])
    with path.open("ab") as handle:
        handle.write(b'{"type":"assistant","timestamp":"2026-01-01T13:00:00Z","message":{"id":"CAN')

    actual = read_claude_code([path], project=None, now=NOW)

    assert actual.counters.files_unreadable == 0
    assert actual.counters.files_read == 1
    assert actual.counters.lines_not_json == 1
    assert len(actual.responses) == 1


def test_incident_2026_11_06_claude_code_truncated_line_in_the_middle(tmp_path: Path) -> None:
    """ccusage issue 2033 (6 Nov 2026), the same shape for Claude Code with the cut line
    in the middle of the file: the complete lines around it are still read.
    """
    path = tmp_path / "session.jsonl"
    cutoff = '{"type":"assistant","timestamp":"2026-01-01T12:30:00Z","message":{"id":"CAN'
    rows: list[Row] = [assistant("CANARY-before"), cutoff, assistant("CANARY-after")]
    write_rows(path, rows)

    actual = read_claude_code([path], project=None, now=NOW)

    assert actual.counters.files_unreadable == 0
    assert actual.counters.lines_not_json == 1
    assert len(actual.responses) == 2


# -- General robustness (not a dated incident): a line type the reader does not know ---


def test_unrecognised_line_type_is_skipped_without_fault_claude_code(tmp_path: Path) -> None:
    """Not a dated incident: both readers must keep tolerating a line of a type they do
    not know, counted as `lines_unknown_type` and skipped, with no other fault.
    """
    path = tmp_path / "session.jsonl"
    write_rows(path, [{"type": "attachment", "text": "CANARY-unused-line"}, assistant()])

    actual = read_claude_code([path], project=None, now=NOW)

    assert actual.counters.lines_unknown_type == 1
    assert actual.counters.files_unreadable == 0
    assert actual.counters.lines_not_json == 0
    assert len(actual.responses) == 1


def test_unrecognised_line_type_is_skipped_without_fault_codex(tmp_path: Path) -> None:
    """Codex side of the same general robustness guarantee."""
    path = tmp_path / "rollout.jsonl"
    write_rows(
        path,
        [meta(), context(), {"type": "response_item", "payload": {"text": "CANARY"}}, token(1, 5)],
    )

    actual = read_codex([path], project=None, now=NOW)

    assert actual.counters.lines_unknown_type == 1
    assert actual.counters.files_unreadable == 0
    assert actual.counters.lines_not_json == 0
    assert len(actual.responses) == 1


# -- End to end: all of the above mixed in one directory, through the real CLI --------


def test_end_to_end_mixed_incidents_never_errors(tmp_path: Path) -> None:
    """All three incidents and the unknown-line-type guard, mixed in one directory and
    read through `arci.logs.cli.run`: each requested tool gives a result or CANNOT TELL,
    never ERROR, and the run exits 0, 1 or 2.
    """
    claude_root, codex_root = tmp_path / "claude-root", tmp_path / "codex-root"

    claude_row = assistant("CANARY-e2e", model="claude-opus-5-5", reasoning=10)
    message = cast(dict[str, object], claude_row["message"])
    usage = cast(dict[str, object], message["usage"])
    usage["iterations"] = [{"model": None, "CANARY-mystery-key": 1}]
    claude_path = claude_root / "CANARY-project" / "session.jsonl"
    write_rows(claude_path, [claude_row, {"type": "system", "text": "CANARY"}])
    with claude_path.open("ab") as handle:
        handle.write(b'{"type":"assistant","timestamp":"2026-01-01T13:00:00Z","message":{"id":"CAN')

    for folder in ("sessions", "archived_sessions"):
        path = codex_root / folder / "rollout-CANARY-e2e-dup.jsonl"
        write_rows(
            path,
            [
                meta(id="CANARY-e2e-dup"),
                context(),
                token(1, 5),
                {"type": "response_item", "payload": {"text": "CANARY"}},
            ],
        )
    codex_path = codex_root / "sessions" / "rollout-CANARY-e2e-other.jsonl"
    write_rows(codex_path, [meta(id="CANARY-e2e-other"), context(), token(1, 5)])
    with codex_path.open("ab") as handle:
        handle.write(
            b'{"type":"event_msg","timestamp":"2026-01-01T13:10:00Z","payload":{"type":"tok'
        )

    json_path = tmp_path / "CANARY.json"
    out, err = io.StringIO(), io.StringIO()
    code = cli.run(
        [
            "--tool",
            "both",
            "--claude-dir",
            str(claude_root),
            "--codex-dir",
            str(codex_root),
            "--json",
            str(json_path),
        ],
        now=NOW,
        env={},
        home=tmp_path,
        out=out,
        err=err,
    )

    assert code in (0, 1, 2)
    assert err.getvalue() == ""
    decision = LogsDecision.model_validate_json(json_path.read_text())
    assert decision.exit_code == code
    assert {tool.tool for tool in decision.tools} == {"claude-code", "codex"}
    for tool in decision.tools:
        assert tool.result != "ERROR"
