"""Tests also run without pytest under Python 3.14: python3.14 test_l0.py."""

from __future__ import annotations

import contextlib
import importlib
import io
import json
import os
import random
import subprocess
import sys
import tempfile
import time
from collections.abc import Generator, Sequence
from dataclasses import asdict
from datetime import UTC, date, datetime, timedelta
from fractions import Fraction
from pathlib import Path

from daytable import Day, build_daytable
from decide import Measure, Point, decide, decide_days, measure_decision
from rank_test import brute_p_lower, p_lower
from readers import discover_claude, discover_codex, read_claude, read_codex
from records import EditResult, ReadResult, Response, Tool, effort_id, model_id
from run_real import collect, main, validate_output
from synth import generate, schedule

HERE = Path(__file__).resolve().parent


@contextlib.contextmanager
def scratch() -> Generator[Path]:
    folder = HERE / ".scratch"
    folder.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=folder) as directory:
        yield Path(directory)


def test_brute_equality() -> None:
    rng = random.Random(481)
    for total in range(2, 15):
        for m in range(1, total):
            for values in (
                [rng.randrange(3) for _ in range(total)],
                [0] * total,
                list(range(total)),
            ):
                rng.shuffle(values)
                assert p_lower(values[m:], values[:m]) == brute_p_lower(values[m:], values[:m])
    assert p_lower([2, 2], [1, 1]) == Fraction(1, 6)
    assert p_lower([1, 2], [1, 2]) == Fraction(5, 6)
    assert p_lower([1] * 84, [1] * 28) == 1


def points(values: Sequence[int | Fraction], offset: int = 0) -> list[Point]:
    return [(date(2026, 1, 1) + timedelta(days=offset + i), v) for i, v in enumerate(values)]


def test_decisions() -> None:
    b: dict[Measure, list[Point]] = {
        "m1": points([100] * 42),
        "m2": points([0] * 42),
        "m3": points([0] * 42),
    }
    a: dict[Measure, list[Point]] = {
        "m1": points([100] * 14, 42),
        "m2": points([0] * 14, 42),
        "m3": points([0] * 14, 42),
    }
    assert decide(b, a, "claude").verdict == "NO DROP"
    a["m1"] = points([50] * 14, 42)
    assert decide(b, a, "claude").verdict == "REAL DROP"
    b["m1"] = points([200] * 21 + [100] * 21)
    result = decide(b, a, "claude")
    assert result.verdict == "CANNOT TELL" and result.self_check_fired
    short = measure_decision(points([100] * 9), points([50] * 5, 9), "lower", Fraction(1, 4))
    assert short.verdict == "CANNOT TELL" and short.p_drop is None
    assert (
        measure_decision(points([100] * 10), points([50] * 4, 10), "lower", Fraction(1, 4)).p_drop
        is None
    )
    # At the margin ties do not establish NO DROP.
    assert (
        measure_decision(
            points([100] * 10), points([75] * 5, 10), "lower", Fraction(1, 4)
        ).p_no_drop
        == 1
    )
    high = measure_decision(points([0] * 10), points([1] * 5, 10), "higher", Fraction(1, 10))
    assert high.verdict == "REAL DROP"
    missing: dict[Measure, list[Point]] = {}
    assert decide(missing, missing, "codex").reason == "too_few_days"


def test_synthetic_counts() -> None:
    with scratch() as root:
        generated = generate(root, 19, schedule(2, 1))
        results: tuple[tuple[Tool, ReadResult], ...] = (
            ("claude", read_claude(discover_claude(generated.claude_root, "project"))),
            ("codex", read_codex(discover_codex(generated.codex_root, generated.cwd))),
        )
        for tool, result in results:
            actual = asdict(result.counters)
            for key, expected in generated.expected[tool].items():
                assert actual[key] == expected
            assert result.counters.unknown_keys > 0
            groups = build_daytable(result.records)
            assert len(groups) == 1
            days = next(iter(groups.values()))
            assert len(days) == 3 and all(d.responses == 24 for d in days)
            assert all(d.known_reasoning == 23 for d in days)


def test_claude_union_last_usage_and_denials() -> None:
    with scratch() as root:
        path = root / "session.jsonl"
        rows = [
            {
                "type": "assistant",
                "timestamp": "2026-01-01T12:00:00Z",
                "effort": "high",
                "message": {
                    "id": "CANARY-1",
                    "model": "good-model",
                    "content": [{"type": "tool_use", "name": "Edit", "id": "CANARY-2"}],
                    "usage": {"output_tokens_details": {"thinking_tokens": 10}},
                },
            },
            {
                "type": "assistant",
                "timestamp": "2026-01-02T12:00:00Z",
                "message": {
                    "id": "CANARY-1",
                    "model": "CANARY-3",
                    "content": [{"type": "tool_use", "name": "Write", "id": "CANARY-4"}],
                    "usage": {"output_tokens_details": {"thinking_tokens": 20}},
                },
            },
            {
                "type": "user",
                "timestamp": "2026-01-01T12:01:00Z",
                "message": {
                    "content": [
                        {"type": "tool_result", "tool_use_id": "CANARY-2", "is_error": True}
                    ]
                },
            },
            {
                "type": "user",
                "timestamp": "2026-01-01T12:01:00Z",
                "toolDenialKind": "CANARY-5",
                "message": {
                    "content": [
                        {"type": "tool_result", "tool_use_id": "CANARY-4", "is_error": True}
                    ]
                },
            },
        ]
        path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
        result = read_claude([path])
        responses = [r for r in result.records if isinstance(r, Response)]
        edits = [r for r in result.records if isinstance(r, EditResult)]
        assert len(responses) == len(edits) == 1
        assert responses[0].reasoning_tokens == 20
        assert responses[0].timestamp.day == 1 and responses[0].model == "good-model"
        assert edits[0].model == "good-model" and edits[0].failed
        assert result.counters.denied_edits == 1
        assert "CANARY-" not in repr(result)


def test_codex_context_dedupe() -> None:
    with scratch() as root:
        path = root / "rollout.jsonl"
        rows = [
            {"type": "session_meta", "payload": {"thread_source": "subagent"}},
            {"type": "turn_context", "payload": {"model": "model-one", "effort": "high"}},
            {
                "type": "event_msg",
                "timestamp": "2026-01-01T12:00:00Z",
                "payload": {
                    "type": "token_count",
                    "info": {
                        "last_token_usage": {"reasoning_output_tokens": 10},
                        "total_token_usage": {"total_tokens": 100},
                    },
                },
            },
        ]
        rows.append(rows[-1])
        rows.extend(
            [
                {"type": "turn_context", "payload": {"model": "CANARY-1", "effort": "CANARY-2"}},
                {
                    "type": "event_msg",
                    "timestamp": "CANARY-3",
                    "payload": {
                        "type": "token_count",
                        "info": {
                            "last_token_usage": {"reasoning_output_tokens": True},
                            "total_token_usage": {"total_tokens": 101},
                        },
                    },
                },
            ]
        )
        path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
        result = read_codex([path])
        assert result.counters.responses == 2 and result.counters.duplicate_responses == 1
        assert (
            result.counters.lacking_model
            == result.counters.lacking_reasoning
            == result.counters.lacking_timestamp
            == 1
        )
        assert len(result.records) == 1 and not result.records[0].main_thread


def test_daytable_and_split() -> None:
    stamp = datetime(2026, 1, 1, 12, tzinfo=UTC)
    records: list[Response | EditResult] = [
        Response("codex", 0, stamp, "model", "high", True, v) for v in [0, 0, 2, 4] * 5
    ]
    records += [
        Response("codex", 1, stamp + timedelta(days=1), "model", "high", True, 4) for _ in range(20)
    ]
    records += [Response("codex", 2, stamp, "model", "high", False, 1000)]
    days = build_daytable(records)[("codex", "model", "high")]
    assert days[0].m1 == 3 and days[0].m2 == Fraction(1, 2)
    assert days[0].m4 == Fraction(1, 2) and days[1].m4 == 1
    # Twenty responses and ten non-denied edits are both required.
    edits: list[Response | EditResult] = [
        Response("claude", 0, stamp, "model", "high", True, 2) for _ in range(20)
    ]
    edits.extend(EditResult("claude", stamp, True, i == 0, "model", "high") for i in range(10))
    assert build_daytable(edits)[("claude", "model", "high")][0].m3 == Fraction(1, 10)
    assert build_daytable(edits[:-1])[("claude", "model", "high")][0].m3 is None
    rows = [
        Day(date(2026, 1, 1) + timedelta(days=i), 20, Fraction(100), Fraction(0), Fraction(0), None)
        for i in range(56)
    ]
    result = decide_days(rows, rows[-1].date - timedelta(days=14), "claude")
    assert result.measures["m1"].before_days == 42 and result.measures["m1"].after_days == 14


def test_local_calendar() -> None:
    old = os.environ.get("TZ")
    try:
        os.environ["TZ"] = "Etc/GMT+5"
        time.tzset()
        records = [
            Response("codex", 0, datetime(2026, 1, 2, 2, tzinfo=UTC), "model", "high", True, 1)
        ]
        assert next(iter(build_daytable(records).values()))[0].date == date(2026, 1, 1)
    finally:
        if old is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = old
        time.tzset()


def test_privacy_cli_and_corruption() -> None:
    with scratch() as root:
        generated = generate(root, 303, schedule(10, 5))
        output = root / "report.json"
        captured = io.StringIO()
        args = [
            "--claude-root",
            str(generated.claude_root),
            "--claude-prefix",
            "project",
            "--codex-root",
            str(generated.codex_root),
            "--codex-cwd",
            str(generated.cwd),
            "--out",
            str(output),
        ]
        with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
            assert main(args) == 0
        assert json.loads(output.read_text()) == json.loads(captured.getvalue())
        assert "CANARY-" not in output.read_text() + captured.getvalue()
        path = root / "CANARY-999.jsonl"
        path.write_bytes(b'{"type": "CANARY-1000"}\n{CANARY-1001\n\xffCANARY-1002\n[]\n')
        for reader in (read_claude, read_codex):
            result = reader([path, root / "CANARY-absent.jsonl"])
            assert result.counters.unparseable_lines == 3
            assert result.counters.unread_files == 1
            assert "CANARY-" not in repr(result)
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
            assert main(["--CANARY-1003"]) == 1
            assert main([*args[:-1], str(root / "CANARY-1004" / "report.json")]) == 1
        assert "CANARY-" not in captured.getvalue()


def test_allowlist() -> None:
    validate_output(
        {"model": "gpt-synth", "date": "2026-01-01", "number": "0.000001", "verdict": "CANNOT TELL"}
    )
    for value in ("CANARY-1", "/private/path", "nan", "2026-99-99", "lowercase-secret"):
        try:
            validate_output({"leaf": value})
        except ValueError as error:
            assert str(error) == "invalid_output"
        else:
            raise AssertionError("invalid_output")
    assert model_id("CANARY-1") == effort_id("CANARY-2") == "other"
    assert model_id("ab\n") == "other"


def test_compressed_and_filter() -> None:
    with scratch() as root:
        generated = generate(root, 42, schedule(1, 0))
        assert not discover_codex(generated.codex_root, root / "different")
        assert not discover_claude(generated.claude_root, "different")
        path = generated.codex_root / "archived_sessions" / "bad.jsonl.zst"
        path.write_bytes(b"CANARY-123")
        counts = read_codex([path]).counters
        if sys.version_info < (3, 14):
            assert counts.unread_compressed == 1
        else:
            assert counts.unread_files == 1
            module = importlib.import_module("compression.zstd")
            path.write_bytes(module.compress(b'{"type":"CANARY-456"}\n'))
            assert read_codex([path]).counters.skipped_line_types == 1


def test_report_collect() -> None:
    with scratch() as root:
        generated = generate(root, 22, schedule(1, 0))
        report = collect(generated.claude_root, "project", generated.codex_root, generated.cwd)
        validate_output(report)
        assert "CANARY-" not in json.dumps(report)


def test_mode_pooling_missingness_and_grouping() -> None:
    stamp = datetime(2026, 1, 1, 12, tzinfo=UTC)
    records: list[Response | EditResult] = [
        Response("codex", 0, stamp, "model", "high", True, v)
        for v in [1] * 5 + [2] * 5 + [0] * 5 + [None] * 5
    ]
    records.extend(
        Response("codex", 1, stamp + timedelta(days=1), "model", "high", True, 2) for _ in range(19)
    )
    days = build_daytable(records)[("codex", "model", "high")]
    # Unusable second day cannot change the pooled mode; equal-frequency mode selects 1.
    assert days[0].m4 == Fraction(1, 2)
    assert days[0].m2 == Fraction(1, 4) and days[0].known_reasoning == 15
    assert days[1].m1 is days[1].m2 is days[1].m4 is None
    grouped: list[Response | EditResult] = []
    for model in ("model-one", "model-two"):
        grouped.extend(Response("claude", 0, stamp, model, "high", True, 10) for _ in range(20))
        grouped.extend(
            EditResult("claude", stamp, True, model == "model-one", model, "high")
            for _ in range(10)
        )
    table = build_daytable(grouped)
    assert table[("claude", "model-one", "high")][0].m3 == 1
    assert table[("claude", "model-two", "high")][0].m3 == 0


def test_filter_only_first_line_and_path_boundary() -> None:
    with scratch() as root:
        folder = root / "sessions" / "2026" / "01" / "01"
        folder.mkdir(parents=True)
        selected = folder / "rollout-one.jsonl"
        selected.write_text(
            json.dumps(
                {"type": "session_meta", "payload": {"cwd": str(root / "project" / "nested")}}
            )
            + "\n{CANARY-1\n",
            encoding="utf-8",
        )
        outside = folder / "rollout-two.jsonl"
        outside.write_text(
            json.dumps({"type": "session_meta", "payload": {"cwd": str(root / "project-suffix")}})
            + "\n"
            + json.dumps({"payload": {"cwd": str(root / "project")}}),
            encoding="utf-8",
        )
        assert discover_codex(root, root / "project") == [selected]
        assert read_codex([selected]).counters.unparseable_lines == 1
        broken = folder / "rollout-corrupt.jsonl"
        broken.write_text("{CANARY-2\n", encoding="utf-8")
        result = read_codex(discover_codex(root, root / "project"))
        assert result.counters.discovery_errors == result.counters.filtered_files == 1


def test_script_boundary() -> None:
    with scratch() as root:
        generated = generate(root, 606, schedule(1, 0))
        report = root / "output.json"
        command = [
            sys.executable,
            str(HERE / "run_real.py"),
            "--claude-root",
            str(generated.claude_root),
            "--codex-root",
            str(generated.codex_root),
            "--codex-cwd",
            str(generated.cwd),
            "--out",
            str(report),
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        assert result.returncode == 0 and not result.stderr
        assert "CANARY-" not in result.stdout
        assert json.loads(result.stdout) == json.loads(report.read_text())
        result = subprocess.run(
            [sys.executable, str(HERE / "run_real.py"), "--CANARY-1"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 1 and result.stdout.strip() == '{"error": "error"}'
        assert not result.stderr


if __name__ == "__main__":
    tests = [
        value
        for name, value in list(globals().items())
        if name.startswith("test_") and callable(value)
    ]
    for test in tests:
        test()
    print(f"{len(tests)} passed")
