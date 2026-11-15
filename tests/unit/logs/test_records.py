"""Closed vocabulary, record shape, and whole-result privacy checks."""

from dataclasses import asdict, fields
from datetime import datetime
from io import BytesIO
from pathlib import Path

import pytest

from arci.logs import claude_code, codex
from arci.logs.records import (
    EFFORTS,
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
        "claude-opus-20260101",
        "gpt-r1",
        "gpt-" + "a-" * 21 + "99",
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
        "gpt-12345678-87654321",
        "gpt-12345678",
        "gpt-123-456",
        "gpt-20260101-20260102",
        "gpt-202601012",
        "gpt-" + "a-" * 22 + "a",
        "gpt-a123",
        "gpt-123a",
        "gpt-123456789a",
        "gpt-a123456789",
        "gpt-4oo",
        "gpt-\uff11\uff12",
        "canary-payroll-1",
    ],
)
def test_model_rejects_free_strings(raw: str) -> None:
    assert render_model(raw) is None


@pytest.mark.parametrize("value", [None, "", "HIGH", "none", "other", "CANARY-1", 1, True, [], {}])
def test_unknown_effort(value: object) -> None:
    assert effort_of(value) is None


@pytest.mark.parametrize("value", sorted(EFFORTS))
def test_effort(value: str) -> None:
    assert effort_of(value) == value


def test_effort_vocabulary_is_closed() -> None:
    assert frozenset({"minimal", "low", "medium", "high", "xhigh", "max"}) == EFFORTS


@pytest.mark.parametrize("tool", ["claude-code", "codex"])
def test_unknown_settings_keep_identity_and_raw_text_order(tmp_path: Path, tool: str) -> None:
    path = tmp_path / "synthetic.jsonl"
    settings = [
        ("z-private-model", "z-private-effort"),
        ("a-private-model", "a-private-effort"),
        ("gpt-6-astra", "high"),
        ("z-private-model", "z-private-effort"),
    ]
    rows: list[dict[str, object] | str] = [meta()] if tool == "codex" else []
    for i, (model, effort) in enumerate(settings):
        if tool == "codex":
            rows.extend([context(model, effort), token(i)])
        else:
            rows.append(assistant(str(i), model=model, effort=effort))
    write_rows(path, rows)
    reader = codex if tool == "codex" else claude_code
    actual = reader.read([path], project=None, now=datetime.fromisoformat("2026-02-01T00:00Z"))
    a, b, c, repeat = actual.responses
    assert a.model != b.model and a.effort != b.effort
    assert (a.model, a.effort) == (repeat.model, repeat.effort)
    assert actual.models[a.model] is actual.models[b.model] is None
    assert actual.efforts[a.effort] is actual.efforts[b.effort] is None
    assert actual.models[c.model] == "gpt-6-astra"
    assert actual.efforts[c.effort] == "high"
    assert actual.model_order == (b.model, c.model, a.model)
    assert actual.effort_order == (b.effort, c.effort, a.effort)
    assert "private" not in repr(actual)


@pytest.mark.parametrize("tool", ["claude-code", "codex"])
@pytest.mark.parametrize("field", ["model", "effort"])
@pytest.mark.parametrize("value", [None, "", False, 17, [], {}])
def test_missing_setting_counted_without_returning_response(
    tmp_path: Path, tool: str, field: str, value: object
) -> None:
    path = tmp_path / "synthetic.jsonl"
    if tool == "codex":
        row = context(value, "high") if field == "model" else context("gpt-6-astra", value)
        write_rows(path, [meta(), row, token()])
        reader = codex
    else:
        row = assistant(model=value) if field == "model" else assistant(effort=value)
        write_rows(path, [row, row])  # Content blocks still describe one response.
        reader = claude_code
    actual = reader.read([path], project=None, now=datetime.fromisoformat("2026-02-01T00:00Z"))
    assert actual.responses == actual.edits == ()
    assert actual.models == actual.efforts == actual.model_order == actual.effort_order == ()
    assert actual.counters.responses_without_setting == 1
    assert actual.counters.responses == actual.counters.responses_without_reasoning == 0
    assert actual.counters.lines_lacking_field == 0


@pytest.mark.parametrize("tool", ["claude-code", "codex"])
def test_absent_setting_keys_and_naive_timestamp(tmp_path: Path, tool: str) -> None:
    path = tmp_path / "synthetic.jsonl"
    if tool == "codex":
        write_rows(
            path,
            [
                meta(),
                {"type": "turn_context", "payload": {}},
                token(),
                context(),
                token(2, stamp="2026-01-01T12:00:00"),
            ],
        )
        reader = codex
    else:
        row = assistant()
        row.pop("effort")
        write_rows(path, [row, assistant("naive", stamp="2026-01-01T12:00:00")])
        reader = claude_code
    actual = reader.read([path], project=None, now=datetime.fromisoformat("2026-02-01T00:00Z"))
    assert actual.responses == ()
    assert actual.counters.responses_without_setting == 1
    assert actual.counters.lines_lacking_field == 1
    assert actual.counters.records_in_future == 0


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
        "efforts",
        "model_order",
        "effort_order",
        "counters",
    ]
    assert [f.name for f in fields(ReaderCounters)] == [
        "files_read",
        "files_unread_compressed",
        "files_unreadable",
        "files_outside_project",
        "lines",
        "lines_not_json",
        "lines_unknown_type",
        "lines_lacking_field",
        "records_in_future",
        "responses",
        "responses_duplicate",
        "responses_without_reasoning",
        "responses_without_setting",
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
        for secret in (
            "CANARY",
            "canary-payroll",
            "acme-payroll",
            "98234567",
            "gpt-12345678-87654321",
            str(tmp_path),
        ):
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
