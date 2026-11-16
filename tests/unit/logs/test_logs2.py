"""Record 0017: externally visible selection, retention, dates and output states."""

from __future__ import annotations

import io
import json
import os
import random
import stat
from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from arci.hashing import hash_record
from arci.logs import claude_code, cli, codex, kept, report
from arci.logs.decide import decide_tool
from arci.logs.html import render_html
from arci.logs.measures import build
from arci.logs.records import ReaderCounters, ReadResult, Response
from arci.logs.schema import (
    DayValue,
    LogsDecision,
    LogsDecisionV1,
    Period,
    day_table_digest,
    earliest_date,
    verify_seal,
)
from tests.unit.logs.synth_logs import assistant, context, meta, token, write_rows

NOW = datetime(2026, 11, 15, tzinfo=UTC)
NEWEST = date(2026, 11, 14)


def row(**changes: Any) -> kept.KeptRow:
    return kept.KeptRow.model_validate(
        dict(
            tool="claude-code",
            utc_offset_minutes=0,
            model="gpt-5-sol",
            effort="high",
            day="2026-11-14",
            responses=20,
            reasoning=[[100, 20]],
            reasoning_unknown=0,
            edits=10,
            edits_failed=0,
        )
        | changes
    )


def store(root: Path, rows: tuple[kept.KeptRow, ...]) -> Path:
    path = root / ".realornoise" / kept.FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(kept.serialize(sorted(rows, key=lambda r: r.key)))
    return path


def history(root: Path, *, days: int = 30, model: str = "gpt-5-sol") -> Path:
    path = root / "logs" / "history.jsonl"
    write_rows(
        path,
        [
            assistant(
                f"{d}-{i}",
                stamp=f"{NEWEST - timedelta(days=d)}T12:00:00Z",
                model=model,
                reasoning=100,
                version="2.1.325",
            )
            for d in range(days)
            for i in range(20)
        ],
    )
    return path


def invoke(root: Path, *args: str, env: dict[str, str] | None = None) -> tuple[LogsDecision, str]:
    output, error = io.StringIO(), io.StringIO()
    target = root / "result.json"
    code = cli.run(
        ["--tool", "claude-code", "--claude-dir", str(root / "logs"), "--json", str(target), *args],
        now=NOW,
        env=env or {},
        home=root,
        out=output,
        err=error,
    )
    assert not error.getvalue(), error.getvalue()
    record = LogsDecision.model_validate_json(target.read_text())
    assert code == record.exit_code and verify_seal(record)
    return record, output.getvalue()


def test_v1_remains_valid_and_v2_is_closed(tmp_path: Path) -> None:
    history(tmp_path)
    record, _ = invoke(tmp_path)
    payload = record.model_dump(mode="json")
    for name in ("keep", "kept_table", "since_given"):
        del payload[name]
    payload["schema_version"] = "arci-logs/1"
    for tool in payload["tools"]:
        for name in (
            "first_response_day",
            "earliest_test_date",
            "response_days_before",
            "response_days_after",
            "kept_days_before",
            "kept_days_after",
            "kept_rows_other_offset",
            "settings_not_kept",
            "days_not_kept",
        ):
            del tool[name]
        for name in ("client_versions_after_shown", "client_versions_after_more"):
            del tool["context"][name]
        for measure in tool["measures"]:
            for day in measure["before_days"] + measure["after_days"]:
                del day["source"]
        # This was an accepted pre-v2 model spelling.
        tool["model"] = "gpt-5"
        tool["day_table_sha256"] = hash_record(
            dict(
                method="arci-logs/1",
                tool=tool["tool"],
                model=tool["model"],
                effort=tool["effort"],
                split_date=tool["split_date"],
                before=tool["before"],
                after=tool["after"],
                alpha_real="1/120",
                alpha_none="1/40",
                measures=[
                    {key: m[key] for key in ("id", "margin", "before_days", "after_days")}
                    for m in tool["measures"]
                ],
            )
        )
    payload["seal"] = hash_record({key: value for key, value in payload.items() if key != "seal"})
    old = LogsDecisionV1.model_validate(payload)
    assert verify_seal(old)
    assert old.model_dump(mode="json") == payload
    with pytest.raises(ValidationError):
        LogsDecision.model_validate(payload)
    with pytest.raises(ValidationError):
        LogsDecisionV1.model_validate(record.model_dump())


@pytest.mark.parametrize(
    "field,value",
    [
        ("tool", "private"),
        ("utc_offset_minutes", 1440),
        ("utc_offset_minutes", -1440),
        ("utc_offset_minutes", True),
        ("model", "canary-payroll"),
        ("effort", "effort-1"),
        ("day", "2026-02-30"),
        ("day", "20261114"),
        ("responses", True),
        ("responses", 20.0),
        ("responses", -1),
        ("responses", 21),
        ("reasoning", [[100, 0]]),
        ("reasoning", [[True, 20]]),
        ("reasoning", [[100, 10], [100, 10]]),
        ("reasoning", [[101, 10], [100, 10]]),
        ("reasoning_unknown", True),
        ("edits_failed", 11),
        ("edits", None),
        ("edits_failed", None),
        ("extra", 1),
    ],
)
def test_every_kept_row_fault(field: str, value: object, tmp_path: Path) -> None:
    path = tmp_path / "table.json"
    payload = {"schema": "realornoise-days/1", "rows": [row().model_dump() | {field: value}]}
    path.write_text(json.dumps(payload))
    assert kept.read(path) == ("unreadable", ())


@pytest.mark.parametrize(
    "raw",
    [
        b"not json",
        b"\xff",
        b'{"schema":"realornoise-days/1","rows":[],"rows":[]}',
        b'{"schema":"wrong","rows":[]}',
        b'{"schema":"realornoise-days/1"}',
        b'{"schema":"realornoise-days/1","rows":[],"extra":1}',
    ],
)
def test_table_faults(raw: bytes, tmp_path: Path) -> None:
    path = store(tmp_path, ())
    path.write_bytes(raw)
    history(tmp_path)
    record, text = invoke(tmp_path, "--keep")
    assert record.kept_table == "unreadable" and text.count(report.F24) == 1
    assert path.read_bytes() == raw
    for render in (report.render_markdown, render_html):
        assert report.F24 in render(record)


def test_order_duplicates_empty_rows_and_codex_edits(tmp_path: Path) -> None:
    path = tmp_path / "table"
    for rows in ((row(), row()), (row(day="2026-11-14"), row(day="2026-11-13"))):
        path.write_text(kept.serialize(rows))
        assert kept.read(path)[0] == "unreadable"
    for changes in (dict(tool="codex"), dict(responses=0, reasoning=[], edits=0)):
        with pytest.raises(ValidationError):
            row(**changes)
    assert row(tool="codex", edits=None, edits_failed=None).edits is None
    assert row(responses=0, reasoning=[], edits=10).responses == 0
    path.unlink()
    path.mkdir()
    assert kept.read(path)[0] == "unreadable"


@pytest.mark.parametrize(
    "extra,message",
    [
        (["--keep", "--project", "."], report.KEEP_PROJECT),
        (["--keep-dir", "kept", "--project", "."], report.KEEP_PROJECT),
        (["--keep", "--ignore-kept"], report.IGNORE_KEEP),
        (["--keep-dir", "kept", "--ignore-kept"], report.IGNORE_KEEP),
        (["--keep", "--ignore-kept", "--project", "."], report.KEEP_PROJECT),
        (["--keep", "--project", ".", "--since", "bad"], report.SINCE_DATE),
    ],
)
@pytest.mark.parametrize("example", [False, True])
def test_option_errors_read_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, extra: list[str], message: str, example: bool
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("input read before option validation")

    monkeypatch.setattr(kept, "read", forbidden)
    monkeypatch.setattr(claude_code, "read", forbidden)
    monkeypatch.setattr(codex, "read", forbidden)
    out, err = io.StringIO(), io.StringIO()
    code = cli.run(
        extra + (["--example"] if example else []), env={}, home=tmp_path, out=out, err=err
    )
    assert (code, out.getvalue(), err.getvalue()) == (3, "", message + "\n")


def test_after_choice_ties_fallback_and_unknown_counts(tmp_path: Path) -> None:
    path = history(tmp_path, days=30, model="gpt-5")
    existing = path.read_text()
    after = [
        assistant(f"new-{i}", stamp="2026-11-14T13:00:00Z", model="gpt-6-sol", reasoning=None)
        for i in range(281)
    ]
    write_rows(path, [*map(json.loads, existing.splitlines()), *after])
    record, _ = invoke(tmp_path)
    assert record.tools[0].model == "gpt-6-sol"  # 281 after beats 280, despite 600 total.
    assert record.tools[0].first_response_day == "2026-11-14"
    record, _ = invoke(tmp_path, "--model", "gpt-5")
    assert record.tools[0].model == "gpt-5"
    record, _ = invoke(tmp_path, "--since", "2026-11-16")
    assert record.tools[0].model == "gpt-5" and record.tools[0].after is None
    assert record.tools[0].earliest_test_date is None
    write_rows(
        path,
        [
            assistant("a", model="a", effort="z", stamp="2026-11-14T12:00:00Z"),
            assistant("b", model="a-b", effort="high", stamp="2026-11-14T12:00:00Z"),
        ],
    )
    record, _ = invoke(tmp_path)
    assert record.tools[0].model == "model-1" and record.tools[0].effort == "effort-1"


@pytest.mark.parametrize("reader", [claude_code.read, codex.read])
def test_versions_are_bounded_sorted_and_after_only(tmp_path: Path, reader: Any) -> None:
    versions = ["2.1.309", "2.1.321", "2.1.325", "2.1.40", "9.8.7654321", "private", "1.01", "1.1"]
    paths = []
    for i, version in enumerate([*versions, "99999.99999"]):
        stamp = "2026-10-20T12:00:00Z" if i == len(versions) else "2026-11-14T12:00:00Z"
        path = tmp_path / f"{i}.jsonl"
        write_rows(
            path,
            [assistant(str(i), stamp=stamp, version=version)]
            if reader == claude_code.read
            else [meta(id=str(i), cli_version=version), context(), token(stamp=stamp)],
        )
        paths.append(path)
    result = reader(paths, project=None, now=NOW)
    assert "private" not in repr(result) and "9.8.7654321" not in repr(result)
    table = build(result, utc_offset=timedelta(), now=NOW)
    assert table.context is not None
    assert table.context.client_versions_after_shown == ("2.1.325", "2.1.321", "2.1.309")
    assert table.context.client_versions_after_more == 5


@pytest.mark.parametrize("offset", [0, 330, -480])
def test_seeded_write_use_and_pruning(tmp_path: Path, offset: int) -> None:
    rng = random.Random(17001 + offset)
    for _ in range(30):
        n, edits = rng.randrange(1, 50), rng.randrange(0, 20)
        saved = row(responses=n, reasoning=[[100, n]], edits=edits, utc_offset_minutes=offset)
        incoming = row()
        incoming = incoming.model_copy(
            update={
                "reasoning": ((50, incoming.responses),),
                "edits": rng.randrange(20),
                "utc_offset_minutes": offset,
            }
        )
        merged = kept.merge((saved,), (incoming,), {"claude-code": NEWEST})
        assert merged == ((incoming if incoming.pair >= saved.pair else saved),)
        result = ReadResult(
            "claude-code", (), (), ("gpt-5-sol",), ("high",), (0,), (0,), ReaderCounters()
        )
        used = kept.use({}, merged, result=result, offset=offset, first=NEWEST, newest=NEWEST)
        assert used[(0, 0, NEWEST)].pair == merged[0].pair
        assert not kept.use(
            {}, merged, result=result, offset=offset + 1, first=NEWEST, newest=NEWEST
        )
        old = saved.model_copy(update={"day": (NEWEST - timedelta(days=181)).isoformat()})
        edge = saved.model_copy(update={"day": (NEWEST - timedelta(days=180)).isoformat()})
        future = saved.model_copy(update={"day": (NEWEST + timedelta(days=1)).isoformat()})
        assert kept.merge((old, edge, future), (), {"claude-code": NEWEST}) == (edge, future)
        assert kept.merge((old,), (), {}) == (old,)


def test_kept_choice_counts_context_and_sources(tmp_path: Path) -> None:
    history(tmp_path, days=1, model="gpt-5")
    saved = tuple(
        row(day=(NEWEST - timedelta(days=d)).isoformat(), responses=30, reasoning=[[5, 30]])
        for d in range(20)
    )
    store(tmp_path, (*saved, row(utc_offset_minutes=330, day="2027-01-01")))
    record, text = invoke(tmp_path)
    tool = record.tools[0]
    assert tool.model == "gpt-5-sol" and tool.other_settings == 1
    assert (tool.response_days_before, tool.response_days_after) == (6, 14)
    assert (tool.kept_days_before, tool.kept_days_after) == (6, 14)
    assert tool.kept_rows_other_offset == 1
    assert tool.counters.responses == 20 and tool.context is not None
    assert tool.context.client_versions_after_shown == ("2.1.325",)
    assert all(
        day.source == "kept" for m in tool.measures for day in (*m.before_days, *m.after_days)
    )
    assert report.F21.format(b=6, a=14) in text and 'fill="none"' in render_html(record)
    assert tool.after is not None and tool.after.last_day == "2026-11-14"


def test_ties_and_edit_only_days(tmp_path: Path) -> None:
    history(tmp_path, days=1)
    store(
        tmp_path,
        (row(edits=0), row(day="2026-11-13", responses=0, reasoning=[], edits=10, edits_failed=5)),
    )
    record, _ = invoke(tmp_path)
    tool = record.tools[0]
    assert tool.response_days_after == 1 and tool.kept_days_after == 1
    assert tool.measures[0].after_days[0].source == "logs"
    assert tool.measures[2].after_days[0].value == "1/2"
    store(tmp_path, (row(responses=19, reasoning=[[5, 19]], edits=100, edits_failed=50),))
    record, _ = invoke(tmp_path)
    assert not record.tools[0].measures[2].after_days  # More responses wins the whole row.
    store(tmp_path, (row(edits=10, edits_failed=5),))
    record, _ = invoke(tmp_path)
    assert record.tools[0].measures[0].after_days[0].source == "kept"


@pytest.mark.parametrize("flag", ["--ignore-kept", "--project"])
def test_read_disabled(tmp_path: Path, flag: str) -> None:
    history(tmp_path, days=1)
    path = store(tmp_path, (row(),))
    before = path.read_bytes()
    args = [flag] if flag == "--ignore-kept" else [flag, "/CANARY-1"]
    record, text = invoke(tmp_path, *args)
    assert record.kept_table == "not_read" and not record.keep
    assert path.read_bytes() == before and "Days from the kept table" not in text


def test_keep_modes_paths_and_canonical_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    history(tmp_path)
    monkeypatch.chdir(tmp_path)
    record, _ = invoke(
        tmp_path, "--keep-dir", "~/parent/kept", env={"REALORNOISE_HOME": str(tmp_path / "wrong")}
    )
    path = tmp_path / "parent" / "kept" / kept.FILENAME
    assert record.keep and record.kept_table == "absent" and path.exists()
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(path.parent.parent.stat().st_mode) == 0o700
    before = path.read_bytes()
    path.chmod(0o644)
    path.parent.chmod(0o755)
    invoke(tmp_path, "--keep-dir", "parent/kept")
    assert path.read_bytes() == before and before.endswith(b"\n") and b'": ' not in before
    assert (
        stat.S_IMODE(path.stat().st_mode) == 0o600
        and stat.S_IMODE(path.parent.stat().st_mode) == 0o755
    )
    assert not (tmp_path / "wrong").exists()


@pytest.mark.parametrize("stage", ["directory", "report", "move"])
def test_transaction_rolls_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stage: str
) -> None:
    history(tmp_path)
    target = tmp_path / "out.json"
    target.write_text("original")
    target.chmod(0o640)
    directory = tmp_path / "parent" / "new"
    if stage == "directory":
        real_mkdir = Path.mkdir

        def deny(path: Path, *args: Any, **kwargs: Any) -> None:
            if path == directory:
                raise PermissionError("synthetic")
            real_mkdir(path, *args, **kwargs)

        monkeypatch.setattr(Path, "mkdir", deny)
    elif stage == "report":
        target = tmp_path / "missing" / "out.json"
    else:
        real_replace = os.replace
        calls = 0

        def fail_once(src: Any, dst: Any) -> None:
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("private failure")
            real_replace(src, dst)

        monkeypatch.setattr(os, "replace", fail_once)
    out, err = io.StringIO(), io.StringIO()
    code = cli.run(
        [
            "--tool",
            "claude-code",
            "--claude-dir",
            str(tmp_path / "logs"),
            "--keep-dir",
            str(directory),
            "--json",
            str(target),
        ],
        now=NOW,
        env={},
        home=tmp_path,
        out=out,
        err=err,
    )
    assert (code, out.getvalue(), err.getvalue()) == (3, "", report.WRITE_ERROR + "\n")
    assert (tmp_path / "out.json").read_text() == "original"
    assert stat.S_IMODE((tmp_path / "out.json").stat().st_mode) == 0o640
    assert not directory.exists()
    assert not directory.parent.exists()
    assert not list(tmp_path.glob(".realornoise-*"))


@pytest.mark.parametrize("difference", [-1, 0, 1])
def test_reader_size_limit(tmp_path: Path, difference: int) -> None:
    path = tmp_path / "table"
    content = kept.serialize((row(),)).encode()
    path.write_bytes(content + b" " * (kept.MAX_BYTES + difference - len(content)))
    assert kept.read(path)[0] == ("unreadable" if difference > 0 else "read")


@pytest.mark.parametrize("difference", [-1, 0, 1])
def test_writer_size_limit(
    tmp_path: Path, difference: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    history(tmp_path, days=1)
    path = tmp_path / "new" / kept.FILENAME
    other = tmp_path / "report"
    other.write_text("original")
    content = kept.serialize((row(),))
    content += " " * (kept.MAX_BYTES + difference - len(content))

    def oversized(rows: Sequence[kept.KeptRow]) -> str:
        return content

    monkeypatch.setattr(kept, "serialize", oversized)
    out, err = io.StringIO(), io.StringIO()
    code = cli.run(
        [
            "--tool",
            "claude-code",
            "--claude-dir",
            str(tmp_path / "logs"),
            "--keep-dir",
            str(path.parent),
            "--json",
            str(other),
        ],
        now=NOW,
        env={},
        home=tmp_path,
        out=out,
        err=err,
    )
    if difference > 0:
        assert code == 3 and err.getvalue() == report.WRITE_ERROR + "\n" and not out.getvalue()
        assert other.read_text() == "original" and not path.parent.exists()
    else:
        assert code == 2 and not err.getvalue()
        assert kept.read(path)[0] == "read" and other.read_text() != "original"


@pytest.mark.parametrize("state", ["not_read", "absent", "read", "unreadable"])
@pytest.mark.parametrize("since", [False, True])
@pytest.mark.parametrize("keep_flag", [False, True])
def test_new_states_roundtrip(tmp_path: Path, state: str, since: bool, keep_flag: bool) -> None:
    if state == "not_read" and keep_flag:
        return
    history(tmp_path, days=2)
    args = ["--keep"] if keep_flag else []
    if since:
        args += ["--since", "2026-11-01"]
    if state == "not_read":
        args += ["--ignore-kept"]
    elif state == "read":
        store(tmp_path, (row(day="2026-10-31", responses=1, reasoning=[[100, 1]], edits=0),))
    elif state == "unreadable":
        store(tmp_path, ()).write_text("bad")
    record, _ = invoke(tmp_path, *args)
    assert record.kept_table == state and record.since_given == since and record.keep == keep_flag
    restored = LogsDecision.model_validate_json(record.model_dump_json())
    for render in (report.render_text, report.render_markdown, render_html):
        assert render(record) == render(restored)
    assert (record.tools[0].earliest_test_date is None) == since
    if state == "read":
        assert record.tools[0].kept_days_before == 1
        assert not record.tools[0].measures[0].before_days


@pytest.mark.parametrize(
    "mutation",
    [
        "source",
        "kept_before_low",
        "kept_after_high",
        "first_outside",
        "first_late",
        "responses_low",
        "earliest",
        "no_read",
        "no_read_keep",
        "version_order",
        "version_count",
        "empty_fields",
    ],
)
def test_new_record_validators(tmp_path: Path, mutation: str) -> None:
    history(tmp_path)
    store(tmp_path, (row(day="2026-10-25", responses=21, reasoning=[[100, 21]]),))
    record, _ = invoke(tmp_path)
    data = record.model_dump(mode="json")
    tool = data["tools"][0]
    if mutation == "source":
        tool["measures"][1]["before_days"][0]["source"] = "kept"
    elif mutation == "kept_before_low":
        tool["kept_days_before"] = 0
    elif mutation == "kept_after_high":
        tool["kept_days_after"] = 15
    elif mutation == "first_outside":
        tool["first_response_day"] = "2020-01-01"
    elif mutation == "first_late":
        tool["first_response_day"] = "2026-11-14"
    elif mutation == "responses_low":
        tool["response_days_before"] = 1
    elif mutation == "earliest":
        tool["earliest_test_date"] = "2027-01-01"
    elif mutation == "no_read":
        data["kept_table"] = "absent"
    elif mutation == "no_read_keep":
        data["kept_table"], data["keep"] = "not_read", True
    elif mutation == "version_order":
        tool["context"]["client_versions_after_shown"] = ["1.1", "2.1"]
        tool["context"]["client_versions_after"] = 2
    elif mutation == "version_count":
        tool["context"]["client_versions_after_more"] += 1
    else:
        tool["reason"], tool["result"] = "no_usable_setting", "CANNOT_TELL"
    with pytest.raises(ValidationError):
        LogsDecision.model_validate(data)


def test_digest_changes_with_source_and_is_exact(tmp_path: Path) -> None:
    history(tmp_path)
    record, _ = invoke(tmp_path)
    tool = record.tools[0]
    original = day_table_digest(tool)
    m = tool.measures[0]
    changed = m.model_copy(
        update={
            "before_days": (
                m.before_days[0].model_copy(update={"source": "kept"}),
                *m.before_days[1:],
            )
        }
    )
    assert original != day_table_digest(
        tool.model_copy(update={"measures": (changed, *tool.measures[1:])})
    )


def test_caps_and_all_settings_written(tmp_path: Path) -> None:
    path = history(tmp_path, days=1)
    rows = [
        assistant(f"cap-{i}", stamp="2026-11-13T12:00:00Z", model="gpt-6", reasoning=i)
        for i in range(5001)
    ]
    rows += [
        assistant(f"edge-{i}", stamp="2026-11-12T12:00:00Z", model="gpt-6", reasoning=i)
        for i in range(5000)
    ]
    rows += [
        assistant(f"bad-{i}", stamp="2026-11-14T12:00:00Z", model="canary-payroll")
        for i in range(30)
    ]
    write_rows(path, [*map(json.loads, path.read_text().splitlines()), *rows])
    saved = row(model="gpt-6", day="2026-11-13")
    store(tmp_path, (saved,))
    record, text = invoke(tmp_path, "--keep", "--model", "gpt-5-sol")
    tool = record.tools[0]
    assert (tool.settings_not_kept, tool.days_not_kept) == (1, 1)
    assert report.F22.format(k=1) in text and report.F23.format(k=1) in text
    _, stored = kept.read(tmp_path / ".realornoise" / kept.FILENAME)
    assert saved in stored
    assert any(len(r.reasoning) == 5000 for r in stored)
    record, _ = invoke(tmp_path, "--model", "gpt-6")
    assert any(day.count == 5000 for day in record.tools[0].measures[0].after_days)


@pytest.mark.parametrize(
    "before_offsets,after_offsets,expected",
    [
        (list(range(-23, -13)), [-3, -2, -1, 0], 1),
        ([], list(range(-13, 1)), 10),
        (list(range(-23, -14)), [], 15),
        ([], [], 24),
    ],
)
def test_earliest_date_boundaries(
    before_offsets: list[int], after_offsets: list[int], expected: int
) -> None:
    from arci.logs.schema import MeasureDecision, median

    def days(offsets: list[int]) -> tuple[DayValue, ...]:
        return tuple(
            DayValue(day=(NEWEST + timedelta(days=d)).isoformat(), count=20, value="100/1")
            for d in offsets
        )

    before, following = days(before_offsets), days(after_offsets)
    measure = MeasureDecision(
        id="reasoning_tokens",
        worse="lower",
        margin="1/4",
        before_days=before,
        after_days=following,
        median_before=median(before),
        median_after=median(following),
        finding="too_few_days",
    )
    after = Period(first_day=(NEWEST - timedelta(days=13)).isoformat(), last_day=NEWEST.isoformat())
    assert earliest_date((measure,), after) == (NEWEST + timedelta(days=expected)).isoformat()


@pytest.mark.parametrize("seed", [17, 31, 400])
@pytest.mark.parametrize("offset", [0, 330])
def test_capture_before_age_deletion_preserves_days(seed: int, offset: int) -> None:
    rng = random.Random(seed)
    start = NOW - timedelta(days=90)
    responses = tuple(
        Response(
            "codex",
            start + timedelta(days=d, hours=12),
            0,
            0,
            True,
            rng.randrange(1, 1000),
            0,
            0,
            True,
        )
        for d in range(90)
        for _ in range(20)
    )
    full = ReadResult(
        "codex", responses, (), ("gpt-5-sol",), ("high",), (0,), (0,), ReaderCounters()
    )
    stored: tuple[kept.KeptRow, ...] = ()
    for capture in (29, 58, 87, 90):
        instant = start + timedelta(days=capture)
        retained = replace(
            full,
            responses=tuple(
                r for r in responses if instant - timedelta(days=30) <= r.when <= instant
            ),
        )
        table = build(
            retained, utc_offset=timedelta(minutes=offset), now=instant, kept_rows=stored, keep=True
        )
        assert table.newest is not None
        stored = kept.merge(stored, table.write_rows, {"codex": table.newest})
    retained = replace(
        full, responses=tuple(r for r in responses if NOW - timedelta(days=30) <= r.when)
    )
    actual = build(retained, utc_offset=timedelta(minutes=offset), now=NOW, kept_rows=stored)
    expected = build(full, utc_offset=timedelta(minutes=offset), now=NOW)
    for a, b in zip(actual.measures, expected.measures, strict=True):
        assert [d.model_dump(exclude={"source"}) for d in (*a.before_days, *a.after_days)] == [
            d.model_dump(exclude={"source"}) for d in (*b.before_days, *b.after_days)
        ]
    assert actual.kept_days_before > 0
    assert (
        decide_tool(actual, retained.counters).result == decide_tool(expected, full.counters).result
    )
    # A first capture after the old batches are gone cannot recover them.
    lost = build(retained, utc_offset=timedelta(minutes=offset), now=NOW)
    assert lost.measures[0].before_days != expected.measures[0].before_days


def test_example_ignores_keep_and_help_reads_nothing(tmp_path: Path) -> None:
    out, err = io.StringIO(), io.StringIO()
    assert cli.run(["--example", "--keep"], env={}, home=tmp_path, out=out, err=err) == 1
    assert not err.getvalue() and not (tmp_path / ".realornoise").exists()
    normal = io.StringIO()
    cli.run(["--example"], env={}, home=tmp_path, out=normal, err=err)
    assert normal.getvalue() == out.getvalue()
    help_text = io.StringIO()
    assert cli.run(["--help"], env={}, home=tmp_path, out=help_text, err=err) == 0
    assert all(
        flag in help_text.getvalue()
        for flag in ("--keep", "--keep-dir", "--ignore-kept", "--since", "--help")
    )


@pytest.mark.parametrize("flag", ["--json", "--html", "--markdown"])
def test_output_collision_and_explicit_overwrite(tmp_path: Path, flag: str) -> None:
    history(tmp_path)
    path = store(tmp_path, ())
    path.write_text("invalid table")
    before = path.read_bytes()
    out, err = io.StringIO(), io.StringIO()
    base = ["--tool", "claude-code", "--claude-dir", str(tmp_path / "logs"), flag, str(path)]
    assert cli.run([*base, "--keep"], now=NOW, env={}, home=tmp_path, out=out, err=err) == 3
    assert err.getvalue() == report.DUPLICATE_OUTPUT + "\n" and path.read_bytes() == before
    out, err = io.StringIO(), io.StringIO()
    assert cli.run(base, now=NOW, env={}, home=tmp_path, out=out, err=err) == 2
    assert not err.getvalue() and out.getvalue().count(report.F24) == 1
    assert path.read_bytes() != before


def test_unrequested_and_error_tool_rows_survive(tmp_path: Path) -> None:
    history(tmp_path, days=1)
    old = row(tool="codex", day="2020-01-01", edits=None, edits_failed=None)
    future = row(day="2027-01-01")
    path = store(tmp_path, (old, future))
    record, _ = invoke(tmp_path, "--keep")
    assert old in kept.read(path)[1] and future in kept.read(path)[1]
    assert record.tools[0].kept_days_after == 0
    previous = path.read_bytes()
    output, error = io.StringIO(), io.StringIO()
    assert (
        cli.run(
            ["--tool", "codex", "--codex-dir", str(tmp_path / "missing"), "--keep"],
            env={},
            home=tmp_path,
            now=NOW,
            out=output,
            err=error,
        )
        == 3
    )
    assert path.read_bytes() == previous and not error.getvalue()


@pytest.mark.parametrize("tool", ["claude-code", "codex"])
def test_context_population_includes_other_settings_subagents_and_missing_settings(
    tmp_path: Path, tool: str
) -> None:
    paths = []
    for i, (version, model, subagent, cwd, stamp) in enumerate(
        [
            ("2.1.1", "gpt-5-sol", False, "/project", "2026-11-14T12:00:00Z"),
            ("2.1.2", "gpt-6", False, "/project", "2026-11-14T12:00:00Z"),
            ("2.1.3", "gpt-6", True, "/project/sub", "2026-11-14T12:00:00Z"),
            ("2.1.4", None, False, "/project", "2026-11-14T12:00:00Z"),
            ("999.99", "gpt-5-sol", False, "/outside", "2026-11-14T12:00:00Z"),
            ("888.88", "gpt-5-sol", False, "/project", "2026-10-20T12:00:00Z"),
        ]
    ):
        path = tmp_path / f"{i}.jsonl"
        write_rows(
            path,
            [
                assistant(
                    str(i), model=model, version=version, isSidechain=subagent, cwd=cwd, stamp=stamp
                )
            ]
            if tool == "claude-code"
            else [
                meta(
                    id=str(i),
                    cwd=cwd,
                    cli_version=version,
                    thread_source="subagent" if subagent else "user",
                ),
                context(model=model),
                token(stamp=stamp),
            ],
        )
        paths.append(path)
    reader = claude_code.read if tool == "claude-code" else codex.read
    data = reader(paths, project=Path("/project"), now=NOW)
    table = build(data, utc_offset=timedelta(), now=NOW, model="gpt-5-sol")
    assert table.context is not None
    assert table.context.client_versions_after_shown == ("2.1.4", "2.1.3", "2.1.2")
    assert table.context.client_versions_after_more == 1
    assert table.context.subagent_share_after == "1/4"


@pytest.mark.parametrize(
    "extra,message",
    [
        (["--since", "bad", "--unknown"], report.SINCE_DATE),
        (["--since", "bad", "--tool", "bad"], report.SINCE_DATE),
        (["--keep", "--ignore-kept", "--unknown"], report.IGNORE_KEEP),
        (["--keep", "--project", ".", "--effort"], report.KEEP_PROJECT),
        (["--json", "a", "--html", "a", "--keep", "--project", "."], report.DUPLICATE_OUTPUT),
    ],
)
def test_option_error_priority(tmp_path: Path, extra: list[str], message: str) -> None:
    out, err = io.StringIO(), io.StringIO()
    assert cli.run(extra, env={}, home=tmp_path, out=out, err=err) == 3
    assert not out.getvalue() and err.getvalue() == message + "\n"


@pytest.mark.parametrize("missing", [True, False])
def test_before_fallback_when_after_has_no_matching_candidate(
    tmp_path: Path, missing: bool
) -> None:
    path = tmp_path / "logs" / "history.jsonl"
    write_rows(
        path,
        [
            assistant("before", model="gpt-5-sol", stamp="2026-10-20T12:00:00Z"),
            assistant("after", model=None if missing else "gpt-6", stamp="2026-11-14T12:00:00Z"),
        ],
    )
    record, _ = invoke(tmp_path, *([] if missing else ["--model", "gpt-5-sol"]))
    assert record.tools[0].model == "gpt-5-sol"
    assert record.tools[0].result == "CANNOT_TELL"
    assert record.tools[0].response_days_after == 0


@pytest.mark.parametrize(
    "version,admitted",
    [
        ("1", False),
        ("1.2", True),
        ("1.2.3", True),
        ("1.2.3.4", True),
        ("1.2.3.4.5", False),
        ("12345.12345", True),
        ("123456.1", False),
        ("9.8.7654321", False),
    ],
)
def test_version_grammar(version: str, admitted: bool) -> None:
    from arci.logs.records import version_name

    assert version_name(version) == (version if admitted else None)


def test_version_ties_and_json_exception_are_scoped() -> None:
    from arci.logs.records import version_order
    from tests.unit.logs.privacy.test_json_leaves import allowed

    # Highest numeric tuple first; equal tuples in ascending text order (record 0017, Names).
    assert version_order(["1.1", "1.01", "2.1.40", "2.1.325"]) == [
        "2.1.325",
        "2.1.40",
        "1.01",
        "1.1",
    ]
    assert version_order(["1.1", "1.01", "1.001", "1.0001"])[:3] == ["1.0001", "1.001", "1.01"]
    assert allowed("2.1.325", "client_versions_after_shown")
    assert not allowed("2.1.325", "other")
    assert not allowed("9.8.7654321", "client_versions_after_shown")


def test_missing_and_unreadable_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "table"
    assert kept.read(path) == ("absent", ())
    path.symlink_to(tmp_path / "missing")
    assert kept.read(path) == ("unreadable", ())
    path.unlink()
    path.write_text(kept.serialize((row(),)))

    def denied(*args: object, **kwargs: object) -> None:
        raise PermissionError("private text")

    monkeypatch.setattr(Path, "open", denied)
    assert kept.read(path) == ("unreadable", ())


def test_future_split_keeps_log_edits_in_before_window_but_not_future_stored_rows() -> None:
    from arci.logs.records import EditResult

    response = Response("claude-code", NOW - timedelta(hours=12), 0, 0, True, 100, 0, 0, True)
    data = ReadResult(
        "claude-code",
        (response,),
        tuple(EditResult("claude-code", NOW, 0, 0, True, True, True) for _ in range(10)),
        ("gpt-5-sol",),
        ("high",),
        (0,),
        (0,),
        ReaderCounters(),
    )
    table = build(
        data,
        utc_offset=timedelta(),
        now=NOW,
        since=date(2026, 11, 16),
        kept_rows=(row(day="2026-11-15", responses=30, reasoning=[[100, 30]]),),
    )
    tool = decide_tool(table, data.counters, since_given=True)
    assert tool.after is None and tool.response_days_before == 1
    assert tool.measures[2].before_days[0].day == "2026-11-15"
    assert tool.measures[2].before_days[0].source == "logs"
    assert tool.measures[2].before_days[0].value == "1/1"


@pytest.mark.parametrize("home_value", [None, "", "~/kept"])
def test_home_directory_resolution(tmp_path: Path, home_value: str | None) -> None:
    history(tmp_path, days=1)
    env = {} if home_value is None else {"REALORNOISE_HOME": home_value}
    invoke(tmp_path, "--keep", env=env)
    directory = tmp_path / ("kept" if home_value else ".realornoise")
    assert (directory / kept.FILENAME).is_file()


def test_existing_table_and_report_rollback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    history(tmp_path, days=1)
    path = store(tmp_path, (row(responses=19, reasoning=[[50, 19]], edits=0),))
    original = path.read_bytes()
    target = tmp_path / "report"
    target.write_text("old report")
    real_replace = os.replace
    failed = False

    def fail_table_once(src: Any, dst: Any) -> None:
        nonlocal failed
        if Path(dst) == path and not failed:
            failed = True
            raise OSError("synthetic write failure")
        real_replace(src, dst)

    monkeypatch.setattr(os, "replace", fail_table_once)
    out, err = io.StringIO(), io.StringIO()
    code = cli.run(
        [
            "--tool",
            "claude-code",
            "--claude-dir",
            str(tmp_path / "logs"),
            "--keep",
            "--json",
            str(target),
        ],
        now=NOW,
        env={},
        home=tmp_path,
        out=out,
        err=err,
    )
    assert code == 3 and err.getvalue() == report.WRITE_ERROR + "\n" and not out.getvalue()
    assert target.read_text() == "old report" and path.read_bytes() == original
    assert not list(tmp_path.rglob(".realornoise-*"))


def test_session_spanning_deleted_and_retained_days(tmp_path: Path) -> None:
    spanning = tmp_path / "logs" / "spanning.jsonl"
    recent = tmp_path / "logs" / "recent.jsonl"
    write_rows(
        spanning,
        [
            assistant(
                f"{d}-{i}",
                model="gpt-5-sol",
                reasoning=50,
                stamp=f"{NEWEST - timedelta(days=d)}T12:00:00Z",
            )
            for d in (40, 10)
            for i in range(20)
        ],
    )
    write_rows(
        recent,
        [
            assistant(f"{prefix}-{i}", model="gpt-5-sol", reasoning=100, stamp=f"{day}T12:00:00Z")
            for prefix, day, count in (
                ("recent", NEWEST, 20),
                ("partial", NEWEST - timedelta(days=10), 5),
            )
            for i in range(count)
        ],
    )
    before, _ = invoke(tmp_path, "--keep")
    spanning.unlink()
    after, _ = invoke(tmp_path)
    for a, b in zip(before.tools[0].measures, after.tools[0].measures, strict=True):
        assert [day.model_dump(exclude={"source"}) for day in (*a.before_days, *a.after_days)] == [
            day.model_dump(exclude={"source"}) for day in (*b.before_days, *b.after_days)
        ]
    assert after.tools[0].kept_days_before == after.tools[0].kept_days_after == 1


def test_no_selected_setting_beside_selected_tool_roundtrips(tmp_path: Path) -> None:
    history(tmp_path, days=1)
    root = tmp_path / "codex"
    write_rows(
        root / "sessions" / "rollout-test.jsonl",
        [meta(), context(model="gpt-6"), token(stamp="2026-11-14T12:00:00Z")],
    )
    record, _ = invoke(
        tmp_path, "--tool", "both", "--codex-dir", str(root), "--model", "gpt-6", "--keep"
    )
    assert record.tools[0].reason == "no_usable_setting" and record.tools[1].model == "gpt-6"
    restored = LogsDecision.model_validate_json(record.model_dump_json())
    for render in (report.render_text, report.render_markdown, render_html):
        assert render(record) == render(restored)
    block = report.render_markdown(record).split("**Codex", 1)[0]
    assert "digest" not in block and " ".join(report.limits_text().splitlines()) in block


def test_a_table_path_below_a_regular_file_is_absent(tmp_path: Path) -> None:
    """Record 0017: kept_table is absent when the path does not exist."""
    from arci.logs import kept

    (tmp_path / "blocked").write_text("not a directory", encoding="utf-8")
    assert kept.read(tmp_path / "blocked" / "in" / "days-1.json") == ("absent", ())


@pytest.mark.parametrize("keep", (False, True))
def test_empty_table_is_absent_and_can_be_replaced(tmp_path: Path, keep: bool) -> None:
    history(tmp_path)
    path = store(tmp_path, ())
    path.write_bytes(b"")
    record, output = invoke(tmp_path, *(["--keep"] if keep else []))
    assert record.kept_table == "absent"
    assert "The kept day table could not be read" not in output
    assert kept.read(path)[0] == ("read" if keep else "absent")


@pytest.mark.parametrize("args", (["--keep-dir", ""], ["--keep-dir="]))
def test_empty_keep_dir_reads_and_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, args: list[str]
) -> None:
    def unexpected(*args: object, **kwargs: object) -> None:
        pytest.fail("usage error reached input or output")

    monkeypatch.setattr(kept, "read", unexpected)
    monkeypatch.setattr(cli.discover, "claude_files", unexpected)
    monkeypatch.setattr(cli.discover, "codex_files", unexpected)
    monkeypatch.setattr(cli, "_write_outputs", unexpected)
    output, error = io.StringIO(), io.StringIO()
    assert cli.run(args, env={}, home=tmp_path, out=output, err=error) == 3
    assert not output.getvalue() and error.getvalue() == report.USAGE_ERROR + "\n"
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("phase", ("stage", "move"))
def test_failed_write_removes_new_targets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, phase: str
) -> None:
    targets = [tmp_path / "out.json", tmp_path / "out.md"]
    table = tmp_path / "kept" / kept.FILENAME
    history(tmp_path)

    def fail(*args: object, **kwargs: object) -> None:
        assert all(not p.exists() for p in [*targets, table])
        raise OSError("injected")

    monkeypatch.setattr(
        Path if phase == "stage" else os, "write_text" if phase == "stage" else "replace", fail
    )
    output, error = io.StringIO(), io.StringIO()
    assert (
        cli.run(
            [
                "--tool",
                "claude-code",
                "--claude-dir",
                str(tmp_path / "logs"),
                "--json",
                str(targets[0]),
                "--markdown",
                str(targets[1]),
                "--keep-dir",
                str(table.parent),
            ],
            now=NOW,
            env={},
            home=tmp_path,
            out=output,
            err=error,
        )
        == 3
    )
    assert not output.getvalue() and error.getvalue() == report.WRITE_ERROR + "\n"
    assert all(not p.exists() for p in [*targets, table.parent])
    assert not list(tmp_path.glob(".realornoise-*"))


@pytest.mark.skipif(os.name != "posix", reason="SIGKILL simulation needs POSIX")
@pytest.mark.parametrize("phase", ("stage", "move"))
def test_killed_writer_leaves_no_empty_targets(tmp_path: Path, phase: str) -> None:
    import signal
    import subprocess
    import sys

    script = """
import os, signal, sys
from pathlib import Path
from arci.logs.cli import _write_outputs
root = Path(sys.argv[1])
targets = [root / 'out.json', root / 'out.md', root / 'kept' / 'days-1.json']
def killed(*args, **kwargs):
    os.kill(os.getpid(), signal.SIGKILL)
if sys.argv[2] == 'stage':
    Path.write_text = killed
else:
    os.replace = killed
_write_outputs([(p, 'complete') for p in targets], table_path=targets[-1])
"""
    result = subprocess.run([sys.executable, "-c", script, str(tmp_path), phase], check=False)
    assert result.returncode == -signal.SIGKILL
    assert all(
        not (tmp_path / name).exists() for name in ("out.json", "out.md", "kept/days-1.json")
    )


def test_overlapping_writer_rows_survive_and_result_uses_initial_table(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    history(tmp_path)
    other_root = tmp_path / "other-run"
    history(other_root, model="gpt-6")
    path = tmp_path / ".realornoise" / kept.FILENAME
    original_read = kept.read
    paused = False

    def read_with_pause(target: Path) -> tuple[kept.KeptState, tuple[kept.KeptRow, ...]]:
        nonlocal paused
        initial = original_read(target)
        if not paused:
            paused = True
            # A complete second CLI run writes after the first read, before the first write.
            invoke(other_root, "--keep-dir", str(path.parent))
        return initial

    monkeypatch.setattr(kept, "read", read_with_pause)
    record, _ = invoke(tmp_path, "--keep")
    assert record.kept_table == "absent"
    state, rows = kept.read(path)
    assert state == "read"
    assert {r.model for r in rows} == {"gpt-5-sol", "gpt-6"}


def test_success_cleans_only_regular_temporary_files(tmp_path: Path) -> None:
    history(tmp_path)
    path = store(tmp_path, ())
    leftover = path.parent / ".realornoise-x"
    leftover.write_text("old temporary")
    other = path.parent / "other"
    other.write_text("keep")
    directory = path.parent / ".realornoise-directory"
    directory.mkdir()
    link = path.parent / ".realornoise-link"
    link.symlink_to(other)
    invoke(tmp_path, "--keep")
    assert not leftover.exists()
    assert other.read_text() == "keep" and link.is_symlink() and directory.is_dir()


def test_unavailable_directory_lock_still_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fcntl = pytest.importorskip("fcntl")
    history(tmp_path)

    def unavailable(*args: object) -> None:
        raise OSError("directory locks unavailable")

    monkeypatch.setattr(fcntl, "flock", unavailable)
    invoke(tmp_path, "--keep")
    assert kept.read(tmp_path / ".realornoise" / kept.FILENAME)[0] == "read"
