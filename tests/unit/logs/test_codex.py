"""Codex session metadata, context changes, duplicate events, and compression."""

import importlib
from collections import Counter
from dataclasses import asdict
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import cast

import pytest

from arci.logs.codex import read
from tests.unit.logs.synth_logs import Row, context, generate, meta, token, write_rows

NOW = datetime(2026, 2, 1, tzinfo=UTC)


@pytest.mark.parametrize("seed", [0, 17, 99])
def test_synthetic_every_record_and_counter(tmp_path: Path, seed: int) -> None:
    fixture = generate(tmp_path, seed)
    actual = read(fixture.paths["codex"], project=fixture.project, now=fixture.now)
    expected = fixture.expected["codex"]
    assert asdict(actual.counters) == asdict(expected.counters)
    assert Counter(
        (r.when, actual.models[r.model], actual.efforts[r.effort], r.main_thread, r.reasoning)
        for r in actual.responses
    ) == Counter(expected.responses)
    assert (
        Counter(
            (r.when.date(), actual.models[r.model], actual.efforts[r.effort], r.main_thread)
            for r in actual.responses
        )
        == expected.per_day_setting
    )
    assert actual.edits == () and all(r.in_project for r in actual.responses)


def test_latest_context_and_full_total_deduplication(tmp_path: Path) -> None:
    path = tmp_path / "rollout.jsonl"
    changed_total = token(1, 20)
    info = cast(dict[str, object], cast(dict[str, object], changed_total["payload"])["info"])
    info["total_token_usage"] = {"total_tokens": 1, "reasoning_output_tokens": 20}
    write_rows(
        path,
        [
            meta(thread_source="subagent"),
            context(),
            token(),
            token(),
            {"type": "event_msg", "payload": {"type": "other"}},
            token(),
            context("gpt-5.6", "max"),
            changed_total,
            token(2, 0, stamp="2026-01-01T00:30:00+01:00"),
        ],
    )
    actual = read([path], project=None, now=NOW)
    assert [r.reasoning for r in actual.responses] == [10, 20, 0]
    assert [actual.models[r.model] for r in actual.responses] == [
        "gpt-6-astra",
        "gpt-5.6",
        "gpt-5.6",
    ]
    assert [actual.efforts[r.effort] for r in actual.responses] == ["high", "max", "max"]
    assert all(not r.main_thread and r.in_project for r in actual.responses)
    assert actual.responses[-1].when == datetime(2025, 12, 31, 23, 30, tzinfo=UTC)
    assert actual.counters.lines_unknown_type == 1
    assert actual.counters.responses_duplicate == 2


@pytest.mark.parametrize("raw", [None, -1, 1.5, True, "123", {}, []])
def test_invalid_reasoning_is_unknown(tmp_path: Path, raw: object) -> None:
    path = tmp_path / "rollout.jsonl"
    write_rows(path, [meta(), context(), token(reasoning=raw)])
    actual = read([path], project=None, now=NOW)
    assert actual.responses[0].reasoning is None
    assert actual.counters.responses_without_reasoning == 1


def test_missing_fields_and_unknown_lines(tmp_path: Path) -> None:
    path = tmp_path / "rollout.jsonl"
    rows: list[Row] = [
        meta(),
        token(),
        context(),
        token(2),
        context(None),
        token(3),
        context("gpt-5.6", None),
        token(4, stamp="CANARY-time"),
        token(5, stamp="2026-01-01T00:00:00"),
        {"type": "event_msg", "payload": {"type": "token_count", "info": None}},
        {"type": "event_msg", "payload": {"type": "token_count", "info": "CANARY"}},
        {"type": "response_item", "payload": {"text": "CANARY"}},
        {"type": "event_msg", "payload": {"type": "CANARY"}},
        "null",
        "[]",
        "CANARY-not-json",
        '{"type":"unused",',
        token(6, stamp="2026-03-01T00:00:00Z"),
        token(7),
        '{"type":',
    ]
    write_rows(path, rows)
    actual = read([path], project=None, now=NOW)
    assert len(actual.responses) == 1
    assert actual.counters.responses_without_setting == 3
    assert actual.counters.lines_lacking_field == 2
    assert actual.counters.records_without_timezone == 1
    assert actual.counters.lines_not_json == 5
    assert actual.counters.lines_unknown_type == 2
    assert actual.counters.records_in_future == 1


@pytest.mark.parametrize(
    "first",
    ["", "[]", "not json", '{"type":"unused"}', '{"type":"turn_context"}', '{"type":"event_msg"}'],
)
def test_bad_first_line_skips_file(tmp_path: Path, first: str) -> None:
    path = tmp_path / "rollout.jsonl"
    write_rows(path, [first, meta(), context(), token()])
    actual = read([path], project=None, now=NOW)
    assert actual.counters.files_unreadable == 0
    assert actual.counters.files_read == 1
    assert actual.counters.lines == 1 and actual.responses == ()


def test_empty_missing_and_non_utf8(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    empty, bad = tmp_path / "CANARY-empty", tmp_path / "CANARY-bad"
    empty.touch()
    bad.write_bytes(b"\xff\xfe\n")
    actual = read([empty, bad, tmp_path / "CANARY-absent"], project=None, now=NOW)
    assert actual.counters.files_unreadable == 1 and actual.responses == ()
    assert actual.counters.files_read == 2
    assert actual.counters.lines == 1
    assert capsys.readouterr() == ("", "")


def test_context_is_local_but_response_identity_crosses_files(tmp_path: Path) -> None:
    a, b, c = (tmp_path / name for name in ("a.jsonl", "b.jsonl", "c.jsonl"))
    write_rows(a, [meta(), context(), token()])
    write_rows(b, [meta(), token(), context(), token(2)])
    write_rows(c, [meta(), context(), token()])
    actual = read([a, b, c], project=None, now=NOW)
    assert len(actual.responses) == 2
    assert actual.counters.responses_duplicate == 2
    assert actual.counters.lines_lacking_field == 0


def test_copied_session_counts_each_response_once(tmp_path: Path) -> None:
    first, copied = tmp_path / "z.jsonl", tmp_path / "a.jsonl"
    encoded = write_rows(first, [meta(), context(), token(), token(2), token()])
    copied.write_bytes(encoded)
    actual = read([first, copied], project=None, now=NOW)
    assert len(actual.responses) == actual.counters.responses == 2
    assert actual.counters.responses_duplicate == 4
    assert actual.counters.files_read == 2 and actual.counters.lines == 10


def test_duplicate_key_uses_session_time_and_complete_unordered_usage(tmp_path: Path) -> None:
    first, second = tmp_path / "first.jsonl", tmp_path / "second.jsonl"
    event = token({"input": 1, "output": 2})
    reordered = token({"output": 2, "input": 1})
    write_rows(
        first,
        [
            meta(id="one"),
            context(),
            event,
            token(2),
            reordered,
            token({"input": 1, "output": 3}),
            token({"input": 1, "output": 2}, stamp="2026-01-01T12:01:00Z"),
        ],
    )
    write_rows(second, [meta(id="two"), context(), event])
    actual = read([first, second], project=None, now=NOW)
    assert len(actual.responses) == 5
    assert actual.counters.responses_duplicate == 1


def test_outside_project_never_reads_second_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "rollout.jsonl"
    encoded = write_rows(path, [meta(cwd="/elsewhere"), "not JSON", context(), token()])

    class HeaderOnly(BytesIO):
        def __next__(self) -> bytes:
            pytest.fail("out-of-project body was read")

        def readline(self, size: int | None = -1) -> bytes:
            if self.tell():
                pytest.fail("out-of-project body was read")
            return super().readline(size)

    stream = HeaderOnly(encoded)

    def open_input(*args: object, **kwargs: object) -> BytesIO:
        return stream

    monkeypatch.setattr(Path, "open", open_input)
    actual = read([path], project=Path("/project"), now=NOW)
    assert stream.closed
    assert actual.responses == ()
    assert actual.counters.files_outside_project == actual.counters.files_read == 1
    assert actual.counters.lines == 1
    assert actual.counters.lines_not_json == actual.counters.files_unreadable == 0


def test_absent_total_does_not_deduplicate(tmp_path: Path) -> None:
    path = tmp_path / "rollout.jsonl"
    event = token()
    info = cast(dict[str, object], cast(dict[str, object], event["payload"])["info"])
    info.pop("total_token_usage")
    write_rows(path, [meta(), context(), event, event])
    actual = read([path], project=None, now=NOW)
    assert len(actual.responses) == 2


def test_empty_info_is_response_with_unknown_reasoning(tmp_path: Path) -> None:
    path = tmp_path / "rollout.jsonl"
    event = token()
    cast(dict[str, object], event["payload"])["info"] = {}
    write_rows(path, [meta(), context(), event])
    actual = read([path], project=None, now=NOW)
    assert len(actual.responses) == 1
    assert actual.responses[0].reasoning is None
    assert actual.counters.responses_without_reasoning == 1
    assert actual.counters.lines_lacking_field == 0


def test_version_and_workdir_identity_across_files(tmp_path: Path) -> None:
    paths: list[Path] = []
    for i, (version, cwd) in enumerate(
        [("98234567.1", "/CANARY-1"), ("98234567.1", "/CANARY-2"), ("98234567.2", "/CANARY-1")]
    ):
        path = tmp_path / f"rollout-{i}.jsonl"
        write_rows(
            path, [meta(id=f"CANARY-session-{i}", cli_version=version, cwd=cwd), context(), token()]
        )
        paths.append(path)
    a, b, c = read(paths, project=None, now=NOW).responses
    assert a.version == b.version != c.version
    assert a.workdir == c.workdir != b.workdir


@pytest.mark.parametrize(
    ("cwd", "inside"),
    [
        ("/project", True),
        ("/project/sub", True),
        ("/project-other", False),
        ("/project/../outside", False),
        (None, False),
        ("/project/sub/../ok", True),
    ],
)
def test_project_lexical_parts(
    tmp_path: Path, cwd: object, inside: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "rollout.jsonl"
    write_rows(path, [meta(cwd=cwd), context(), token()])

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("project check must not access filesystem")

    monkeypatch.setattr(Path, "resolve", forbidden)
    original_stat = Path.stat

    def checked_stat(path: Path, *, follow_symlinks: bool = True):
        if str(path).startswith("/project"):
            raise AssertionError("project check must not access filesystem")
        return original_stat(path, follow_symlinks=follow_symlinks)

    monkeypatch.setattr(Path, "stat", checked_stat)
    actual = read([path], project=Path("/project"), now=NOW)
    assert len(actual.responses) == int(inside)
    assert all(r.in_project for r in actual.responses)
    assert actual.counters.files_outside_project == int(not inside)
    assert actual.counters.lines == (3 if inside else 1)


def test_unavailable_compression_is_counted_without_opening(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def absent(name: str) -> None:
        assert name == "compression.zstd"
        raise ModuleNotFoundError("CANARY-module")

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("unavailable compression must not open input")

    (tmp_path / "rollout-CANARY.jsonl.zst").touch()
    monkeypatch.setattr("arci.logs.codex.importlib.import_module", absent)
    monkeypatch.setattr(Path, "open", forbidden)
    actual = read([tmp_path / "rollout-CANARY.jsonl.zst"], project=None, now=NOW)
    assert actual.counters.files_unread_compressed == 1
    assert actual.counters.files_read == actual.counters.files_unreadable == 0
    assert actual.counters.lines == 0


def test_compressed_roundtrip_and_corrupt_file(tmp_path: Path) -> None:
    try:
        zstd = importlib.import_module("compression.zstd")
    except ImportError:
        pytest.skip("compression.zstd needs Python 3.14")
    plain = tmp_path / "rollout.jsonl"
    encoded = write_rows(plain, [meta(), context(), token()])
    compressed, broken = tmp_path / "rollout.jsonl.zst", tmp_path / "broken.jsonl.zst"
    compressed.write_bytes(cast(bytes, zstd.compress(encoded)))
    broken.write_bytes(b"CANARY-broken-zstd")
    actual = read([compressed], project=None, now=NOW)
    assert actual == read([plain], project=None, now=NOW)
    assert read([broken], project=None, now=NOW).counters.files_unreadable == 1
