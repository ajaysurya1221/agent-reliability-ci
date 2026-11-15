"""Closed vocabulary, record shape, and whole-result privacy checks."""

from dataclasses import asdict, fields
from datetime import datetime
from io import BytesIO
from pathlib import Path

import pytest

from arci.logs import claude_code, codex
from arci.logs.records import (
    MODEL_WORDS,
    EditResult,
    ReaderCounters,
    ReadResult,
    Response,
    effort_of,
    render_model,
)
from tests.unit.logs.synth_logs import assistant, context, generate, meta, token, write_rows


@pytest.mark.parametrize(
    "raw",
    [
        "claude-opus-5-5",
        "claude-fable-5-2",
        "gpt-6-astra",
        "gpt-5.6",
        "gpt-5.3-codex-spark",
        "o3-mini",
        "gpt-4o",
        "gpt-o4",
        "gemini_2.5_flash",
        "qwen-3-a22",
        "gpt-12345678",
        *sorted(MODEL_WORDS),
    ],
)
def test_model_vocabulary(raw: str) -> None:
    assert render_model(raw) == raw


@pytest.mark.parametrize(
    "raw",
    [
        "acme-payroll-secret",
        "claude-acme-payroll",
        "Claude-opus",
        "a/b",
        "",
        "a" * 60,
        "gpt:6",
        "gpt\n",
        "gpt--6",
        "gpt..6",
        "-gpt",
        "gpt_",
        "gpt-123456789",
        "gpt-123456789a",
        "gpt-a123456789",
        "gpt-4oo",
        "gpt-\uff11\uff12",
        "canary-payroll-1",
    ],
)
def test_model_rejects_free_strings(raw: str) -> None:
    assert render_model(raw) is None


@pytest.mark.parametrize("value", [None, "", "HIGH", "none", "CANARY-1", 1, True, [], {}])
def test_unknown_effort(value: object) -> None:
    assert effort_of(value) == "other"


@pytest.mark.parametrize("value", ["minimal", "low", "medium", "high", "xhigh", "max", "other"])
def test_effort(value: str) -> None:
    assert effort_of(value) == value


def test_contract_fields() -> None:
    assert [f.name for f in fields(Response)] == [
        "tool",
        "when",
        "model",
        "effort",
        "main_thread",
        "reasoning",
        "version",
        "workdir",
        "in_project",
    ]
    assert [f.name for f in fields(EditResult)] == [
        "tool",
        "when",
        "model",
        "effort",
        "main_thread",
        "failed",
        "in_project",
    ]
    assert [f.name for f in fields(ReadResult)] == [
        "tool",
        "responses",
        "edits",
        "models",
        "counters",
    ]
    assert [f.name for f in fields(ReaderCounters)] == [
        "files_read",
        "files_unread_compressed",
        "files_unreadable",
        "lines",
        "lines_not_json",
        "lines_unknown_type",
        "lines_lacking_field",
        "records_in_future",
        "responses",
        "responses_without_reasoning",
        "edits_denied",
        "edits_unmatched",
    ]
    assert set(asdict(ReaderCounters()).values()) == {0}


def test_no_private_string_in_any_returned_field(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fixture = generate(tmp_path)

    def inspect(value: object) -> None:
        if isinstance(value, dict):
            for child in value.values():
                inspect(child)
        elif isinstance(value, (list, tuple)):
            for child in value:
                inspect(child)
        elif isinstance(value, str):
            assert value in {
                "claude-code",
                "codex",
                "high",
                "other",
                "claude-fable-5-2",
                "gpt-6-astra",
            }
        else:
            assert value is None or isinstance(value, (int, datetime))

    for tool, reader in (("claude-code", claude_code), ("codex", codex)):
        paths = fixture.paths["claude-code"] if tool == "claude-code" else fixture.paths["codex"]
        result = reader.read(paths, project=fixture.project, now=fixture.now)
        inspect(asdict(result))
        assert None in result.models
        for secret in ("CANARY", "canary-payroll", "acme-payroll", "98234567", str(tmp_path)):
            assert secret not in repr(result)
    captured = capsys.readouterr()
    assert captured.out == captured.err == ""


def test_readers_stream_and_close_inputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    claude_path, codex_path = tmp_path / "claude.jsonl", tmp_path / "codex.jsonl"
    inputs = {
        claude_path: write_rows(claude_path, [assistant()]),
        codex_path: write_rows(codex_path, [meta(), context(), token()]),
    }
    streams: list[BytesIO] = []

    class StreamingOnly(BytesIO):
        def read(self, size: int | None = -1) -> bytes:
            raise AssertionError("must iterate by line")

        def readlines(self, hint: int | None = -1) -> list[bytes]:
            raise AssertionError("must iterate by line")

    def open_input(path: Path, *args: object, **kwargs: object) -> BytesIO:
        stream = StreamingOnly(inputs[path])
        streams.append(stream)
        return stream

    monkeypatch.setattr(Path, "open", open_input)
    now = datetime.fromisoformat("2026-02-01T00:00:00+00:00")
    assert len(claude_code.read([claude_path], project=None, now=now).responses) == 1
    assert len(codex.read([codex_path], project=None, now=now).responses) == 1
    assert len(streams) == 2 and all(stream.closed for stream in streams)
