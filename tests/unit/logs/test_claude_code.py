"""Claude responses, edit joins, malformed input, and lexical project membership."""

from collections import Counter
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest

from arci.logs.claude_code import read
from tests.unit.logs.synth_logs import Row, assistant, generate, result, write_rows

NOW = datetime(2026, 2, 1, tzinfo=UTC)


@pytest.mark.parametrize("seed", [0, 17, 99])
def test_synthetic_every_record_and_counter(tmp_path: Path, seed: int) -> None:
    fixture = generate(tmp_path, seed)
    actual = read(fixture.paths["claude-code"], project=fixture.project, now=fixture.now)
    expected = fixture.expected["claude-code"]
    assert asdict(actual.counters) == asdict(expected.counters)
    assert Counter(
        (r.when, actual.models[r.model], actual.efforts[r.effort], r.main_thread, r.reasoning)
        for r in actual.responses
    ) == Counter(expected.responses)
    assert Counter(
        (r.when, actual.models[r.model], actual.efforts[r.effort], r.main_thread, r.failed)
        for r in actual.edits
    ) == Counter(expected.edits)
    assert (
        Counter(
            (r.when.date(), actual.models[r.model], actual.efforts[r.effort], r.main_thread)
            for r in actual.responses
        )
        == expected.per_day_setting
    )
    assert all(r.in_project for r in (*actual.responses, *actual.edits))


def test_first_metadata_last_usage_and_union_of_calls(tmp_path: Path) -> None:
    path = tmp_path / "subagents/session.jsonl"  # Filename is not a thread signal.
    first = assistant(
        stamp="2026-01-01T00:30:00+01:00",
        effort="medium",
        perTurnEffort="max",
        version="CANARY-version-1",
        cwd="/project",
        reasoning=1,
    )
    call = {"type": "tool_use", "id": "CANARY-call", "name": "Edit"}
    second = assistant(
        stamp="2026-01-02T00:00:00Z",
        effort="low",
        model="gpt-6-astra",
        version="CANARY-version-2",
        cwd="/elsewhere",
        isSidechain=True,
        reasoning=25,
        content=[call],
    )
    rows: list[Row] = [
        first,
        second,
        result("CANARY-call", isSidechain=True),
        result("CANARY-call", stamp="2026-01-03T00:00:00Z"),
    ]
    write_rows(path, rows)
    actual = read([path], project=Path("/project"), now=NOW)
    assert len(actual.responses) == 1
    response = actual.responses[0]
    assert response.when == datetime(2025, 12, 31, 23, 30, tzinfo=UTC)
    assert actual.efforts[response.effort] == "medium" and response.reasoning == 25
    assert actual.models[response.model] == "claude-opus-5-5"
    assert response.main_thread and response.in_project
    assert len(actual.edits) == 2  # One per result block, even for the same id.
    assert all(
        actual.efforts[e.effort] == "medium" and e.main_thread and e.in_project
        for e in actual.edits
    )
    assert actual.edits[0].when == datetime(2026, 1, 1, 12, 1, tzinfo=UTC)


@pytest.mark.parametrize("raw", [None, -1, 1.5, True, "123", {}, []])
def test_invalid_reasoning_is_unknown(tmp_path: Path, raw: object) -> None:
    path = tmp_path / "session.jsonl"
    write_rows(path, [assistant(reasoning=raw)])
    actual = read([path], project=None, now=NOW)
    assert actual.responses[0].reasoning is None
    assert actual.counters.responses_without_reasoning == 1


def test_optional_fields_and_identity_indices(tmp_path: Path) -> None:
    path = tmp_path / "session.jsonl"
    first = assistant("CANARY-first", perTurnEffort="xhigh")
    first.pop("effort")
    second = assistant("CANARY-second", version="98234567.76543211")
    third = assistant("CANARY-third", cwd="/CANARY-other", model="acme-payroll-secret")
    fourth = assistant("CANARY-fourth", model="acme-another-secret")
    fifth = assistant("CANARY-fifth")
    for key in ("version", "cwd"):
        fifth.pop(key)
    write_rows(path, [first, second, third, fourth, fifth])
    actual = read([path], project=None, now=NOW)
    a, b, c, d, e = actual.responses
    assert actual.efforts[a.effort] == "xhigh" and actual.efforts[e.effort] == "high"
    assert a.version == c.version == d.version != b.version
    assert a.workdir == b.workdir == d.workdir != c.workdir
    assert c.model != d.model and actual.models[c.model] is actual.models[d.model] is None
    assert all(r.in_project for r in actual.responses)


def test_bad_lines_missing_fields_future_and_files(tmp_path: Path) -> None:
    path = tmp_path / "session.jsonl"
    bad_message = assistant()
    cast(dict[str, object], bad_message["message"]).pop("id")
    write_rows(
        path,
        [
            "not json",
            "[]",
            "null",
            '{"type":"unused",',
            {"type": "unused"},
            {"type": []},
            bad_message,
            assistant("no-model", model=None),
            assistant("bad-time", stamp="CANARY-time"),
            assistant("naive", stamp="2026-01-01T00:00:00"),
            assistant("future", stamp="2026-03-01T00:00:00Z"),
            assistant("future", stamp="2026-03-02T00:00:00Z"),
            assistant(),
            '{"type":',
        ],
    )
    invalid = tmp_path / "CANARY-invalid.jsonl"
    invalid.write_bytes(b"\xff\xfe\n")
    actual = read([path, invalid, tmp_path / "CANARY-missing"], project=None, now=NOW)
    assert len(actual.responses) == 1
    assert actual.counters.files_read == 2
    assert actual.counters.files_unreadable == 2
    assert actual.counters.lines == 15
    assert actual.counters.lines_not_json == 5
    assert actual.counters.lines_unknown_type == 2
    assert actual.counters.lines_lacking_field == 2
    assert actual.counters.records_without_timezone == 1
    assert actual.counters.responses_without_setting == 1
    assert actual.counters.records_in_future == 1


def test_edits_denials_unmatched_nonedit_and_bad_time(tmp_path: Path) -> None:
    path = tmp_path / "session.jsonl"
    calls = [
        {"type": "tool_use", "id": f"CANARY-{i}", "name": name}
        for i, name in enumerate(("Edit", "Write", "MultiEdit", "NotebookEdit", "Read"))
    ]
    rows: list[Row] = [
        result("CANARY-0"),
        assistant(content=calls),
        result("CANARY-0", toolDenialKind=None),
        result("CANARY-1", permissionDecision={"decision": "reject"}),
        result("CANARY-4"),
        result([]),
        result("CANARY-2", stamp="bad"),
        result("CANARY-3", stamp="2026-03-01T00:00:00Z"),
        {"type": "user", "message": {"content": "CANARY-free-text"}},
        result("CANARY-0"),
    ]
    write_rows(path, rows)
    actual = read([path], project=None, now=NOW)
    assert len(actual.edits) == 1
    assert actual.counters.edits_denied == 2
    assert actual.counters.edits_unmatched == 2
    assert actual.counters.lines_lacking_field == 1
    assert actual.counters.records_in_future == 1


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
    path = tmp_path / "session.jsonl"
    write_rows(path, [assistant(cwd=cwd)])

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("project check must not access filesystem")

    monkeypatch.setattr(Path, "resolve", forbidden)
    monkeypatch.setattr(Path, "stat", forbidden)
    actual = read([path], project=Path("/project"), now=NOW)
    assert actual.responses[0].in_project is inside


def test_unused_flat_line_skipped_before_loads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "session.jsonl"
    write_rows(path, [{"type": "unused", "text": "CANARY-1 canary-payroll-1"}])

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("unused flat object was decoded")

    monkeypatch.setattr("arci.logs.records.json.loads", forbidden)
    actual = read([path], project=None, now=NOW)
    assert actual.counters.lines_unknown_type == 1


def test_duplicate_type_and_escaped_keys_are_decoded(tmp_path: Path) -> None:
    path = tmp_path / "session.jsonl"
    write_rows(
        path,
        [
            '{"type":"unused","type":"assistant"}',
            '{"type":"unused","t\\u0079pe":"assistant"}',
            '{"type":"unused","nested":{"type":"assistant"}}',
        ],
    )
    actual = read([path], project=None, now=NOW)
    assert actual.counters.lines_lacking_field == 2
    assert actual.counters.lines_unknown_type == 1


def test_response_ids_cross_files_but_call_ids_are_local(tmp_path: Path) -> None:
    a, b = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    write_rows(a, [assistant(content=[{"type": "tool_use", "id": "CANARY-call", "name": "Edit"}])])
    write_rows(b, [assistant(), result("CANARY-call")])
    actual = read([a, b], project=None, now=NOW)
    assert len(actual.responses) == 1
    assert actual.counters.responses_duplicate == 1
    assert actual.edits == () and actual.counters.edits_unmatched == 1


def test_copied_session_counts_each_response_once_in_path_order(tmp_path: Path) -> None:
    first, copied = tmp_path / "z.jsonl", tmp_path / "a.jsonl"
    rows: list[Row] = [assistant(reasoning=1), assistant(reasoning=2), assistant("second")]
    encoded = write_rows(first, rows)
    copied.write_bytes(encoded)
    actual = read([first, copied], project=None, now=NOW)
    assert [r.reasoning for r in actual.responses] == [2, 10]
    assert actual.counters.responses == actual.counters.responses_duplicate == 2
    assert actual.counters.files_read == 2 and actual.counters.lines == 6
    write_rows(copied, [assistant(reasoning=50)])
    assert read([first, copied], project=None, now=NOW).responses[0].reasoning == 2
    assert read([copied, first], project=None, now=NOW).responses[0].reasoning == 50


def test_missing_first_setting_is_not_replaced_by_later_content(tmp_path: Path) -> None:
    path = tmp_path / "session.jsonl"
    write_rows(path, [assistant(effort=None, perTurnEffort="max"), assistant(effort="high")])
    actual = read([path], project=None, now=NOW)
    assert actual.responses == ()
    assert actual.counters.responses_without_setting == 1


def test_project_filter_keeps_reading_claude_lines(tmp_path: Path) -> None:
    path = tmp_path / "session.jsonl"
    write_rows(path, [assistant("outside", cwd="/elsewhere"), assistant("inside", cwd="/project")])
    actual = read([path], project=Path("/project"), now=NOW)
    assert [r.in_project for r in actual.responses] == [False, True]
    assert actual.counters.files_outside_project == 0 and actual.counters.lines == 2


def test_invalid_json_fast_path_does_not_hide_faults(tmp_path: Path) -> None:
    path = tmp_path / "session.jsonl"
    write_rows(
        path,
        [
            '\v{"type":"unused"}',
            '{"type":"unused","n":NaN}',
            '{"type":"unused","n":Infinity}',
            '{"type":"unused","n":-Infinity}',
            '{"type":"unused","x":"control\x00"}',
            '{"type":"unused","n":01}',
            '{"type":"unused","n":1e}',
            '{"type":"unused","x":[1,2]}',
            assistant(),
        ],
    )
    actual = read([path], project=None, now=NOW)
    assert actual.counters.lines_not_json == 7
    assert actual.counters.lines_unknown_type == 1
    assert len(actual.responses) == 1


def test_deep_json_fault_is_per_line(tmp_path: Path) -> None:
    path = tmp_path / "session.jsonl"
    write_rows(
        path, ['{"type":"assistant","message":' + "[" * 2000 + "0" + "]" * 2000, assistant()]
    )
    actual = read([path], project=None, now=NOW)
    assert actual.counters.lines_not_json == 1
    assert actual.counters.files_unreadable == 0
    assert len(actual.responses) == 1


def test_edit_without_timezone_counted_separately(tmp_path: Path) -> None:
    path = tmp_path / "session.jsonl"
    write_rows(
        path,
        [
            assistant(content=[{"type": "tool_use", "id": "edit", "name": "Edit"}]),
            result("edit", stamp="2026-01-01T12:00:00"),
        ],
    )
    actual = read([path], project=None, now=NOW)
    assert actual.edits == ()
    assert actual.counters.records_without_timezone == 1
    assert actual.counters.lines_lacking_field == 0


def test_zoneless_first_block_cannot_be_recovered_by_later_block(tmp_path: Path) -> None:
    first = tmp_path / "first.jsonl"
    copied = tmp_path / "copy.jsonl"
    write_rows(
        first,
        [
            assistant("same", stamp="2026-01-01T12:00:00"),
            assistant("same", stamp="2026-01-02T12:00:00Z"),
        ],
    )
    write_rows(copied, [assistant("same", stamp="2026-01-02T12:00:00Z")])
    actual = read([first, copied], project=None, now=NOW)
    assert actual.responses == ()
    assert actual.counters.records_without_timezone == 1
    assert actual.counters.responses_duplicate == 1
