"""Seeded synthetic input and independently recorded expectations; never real logs."""

from __future__ import annotations

import importlib
import json
import random
from collections import Counter
from dataclasses import dataclass, field, fields, replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import cast

from arci.logs.records import ReaderCounters, Tool

Row = dict[str, object] | str
Sample = tuple[datetime, str | None, str | None, bool, int | None]
Edit = tuple[datetime, str | None, str | None, bool, bool]
DaySetting = tuple[date, str | None, str | None, bool]


@dataclass
class Expected:
    responses: list[Sample] = field(default_factory=list)
    edits: list[Edit] = field(default_factory=list)
    counters: ReaderCounters = field(default_factory=ReaderCounters)
    per_day_setting: Counter[DaySetting] = field(default_factory=Counter)

    def add(self, other: Expected) -> None:
        self.responses.extend(other.responses)
        self.edits.extend(other.edits)
        self.per_day_setting.update(other.per_day_setting)
        for item in fields(ReaderCounters):
            setattr(
                self.counters,
                item.name,
                getattr(self.counters, item.name) + getattr(other.counters, item.name),
            )


@dataclass
class Generated:
    claude_root: Path
    codex_root: Path
    project: Path
    now: datetime
    expected: dict[Tool, Expected]
    paths: dict[Tool, list[Path]]


def write_rows(path: Path, rows: list[Row]) -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (
        "\n".join(json.dumps(row) if isinstance(row, dict) else row for row in rows) + "\n"
    ).encode()
    path.write_bytes(data)
    return data


def assistant(
    identity: str = "CANARY-1",
    *,
    stamp: str = "2026-01-01T12:00:00Z",
    model: object = "claude-opus-5-5",
    reasoning: object = 10,
    content: object = None,
    **extra: object,
) -> dict[str, object]:
    return {
        "type": "assistant",
        "timestamp": stamp,
        "cwd": "/CANARY-1/canary-payroll-1",
        "version": "98234567.76543210",
        "effort": "high",
        "message": {
            "id": identity,
            "model": model,
            "content": content
            if content is not None
            else [{"type": "text", "text": "CANARY-1 canary-payroll-1"}],
            "usage": {"output_tokens_details": {"thinking_tokens": reasoning}},
        },
        **extra,
    }


def result(
    call_id: object, *, stamp: str = "2026-01-01T12:01:00Z", **extra: object
) -> dict[str, object]:
    return {
        "type": "user",
        "timestamp": stamp,
        "message": {
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": call_id,
                    "content": "CANARY-2 canary-payroll-2",
                }
            ]
        },
        **extra,
    }


def meta(**extra: object) -> dict[str, object]:
    return {
        "type": "session_meta",
        "payload": {
            "id": "CANARY-session",
            "cwd": "/CANARY-1/canary-payroll-1",
            "cli_version": "98234567.76543210",
            **extra,
        },
    }


def context(model: object = "gpt-6-astra", effort: object = "high") -> dict[str, object]:
    return {"type": "turn_context", "payload": {"model": model, "effort": effort}}


def token(
    total: object = 1, reasoning: object = 10, *, stamp: str = "2026-01-01T12:00:00Z"
) -> dict[str, object]:
    return {
        "type": "event_msg",
        "timestamp": stamp,
        "payload": {
            "type": "token_count",
            "info": {
                "total_token_usage": {"total_tokens": total},
                "last_token_usage": {"reasoning_output_tokens": reasoning},
            },
        },
    }


def generate(
    root: Path, seed: int = 23, *, days: int = 3, sessions_per_day: int = 3, compressed: bool = True
) -> Generated:
    rng = random.Random(seed)
    project = root / "CANARY-100" / "canary-payroll-100"
    now = datetime(2026, 2, 1, tzinfo=UTC)
    generated = Generated(
        root / "claude",
        root / "codex",
        project,
        now,
        {"claude-code": Expected(), "codex": Expected()},
        {"claude-code": [], "codex": []},
    )
    for day in range(days):
        for session in range(sessions_per_day):
            main = session % 3 != 2
            private = session % 3 == 1
            effort = None if private else "high"
            cwd = str(project / f"CANARY-{session}")
            when = datetime(2026, 1, 1, 12, tzinfo=UTC) + timedelta(days=day, hours=session)
            stamp = when.isoformat()
            future = (now + timedelta(days=1)).isoformat()
            for tool in ("claude-code", "codex"):
                model = (
                    ("acme-payroll-secret" if day % 2 else "gpt-12345678-87654321")
                    if private
                    else ("claude-fable-5-2" if tool == "claude-code" else "gpt-6-astra")
                )
                rendered = None if private else model
                rows: list[Row] = []
                expected = Expected()
                if tool == "codex":
                    rows.extend(
                        [
                            meta(
                                id=f"CANARY-session-{day}-{session}",
                                cwd=cwd,
                                thread_source="user" if main else "subagent",
                            ),
                            context(model, "canary-payroll-9" if private else "high"),
                        ]
                    )
                for number in range(5):
                    count = rng.randrange(1, 1000) if number == 0 else 0 if number == 1 else None
                    raw_count: object = count if number < 3 else -1 if number == 3 else True
                    expected.responses.append((when, rendered, effort, main, count))
                    expected.per_day_setting[(when.date(), rendered, effort, main)] += 1
                    expected.counters.responses += 1
                    expected.counters.responses_without_reasoning += count is None
                    if tool == "claude-code":
                        identity = f"CANARY-{day}-{session}-{number}"
                        call_id = f"canary-payroll-{day}-{session}-{number}"
                        base = assistant(
                            identity,
                            stamp=stamp,
                            model=model,
                            reasoning=9999,
                            cwd=cwd,
                            isSidechain=not main,
                        )
                        if private:
                            base["effort"] = "canary-payroll-9"
                        rows.append(base)
                        content = [
                            {
                                "type": "tool_use",
                                "id": call_id,
                                "name": ("Edit", "Write", "MultiEdit", "NotebookEdit", "Read")[
                                    number
                                ],
                                "input": {"path": "CANARY-99", "text": "canary-payroll-99"},
                            }
                        ]
                        last = assistant(
                            identity,
                            stamp=future,
                            model=model,
                            reasoning=raw_count,
                            content=content,
                            effort="low",
                            cwd="/CANARY-999",
                            isSidechain=True,
                        )
                        rows.append(last)
                        user = result(call_id, stamp=stamp)
                        if number == 1:
                            user["toolDenialKind"] = "CANARY-8"
                            expected.counters.edits_denied += 1
                        elif number == 2:
                            user["permissionDecision"] = {"decision": "reject"}
                            expected.counters.edits_denied += 1
                        elif number < 4:
                            failed = number == 3
                            user["message"] = {
                                "content": [
                                    {
                                        "type": "tool_result",
                                        "tool_use_id": call_id,
                                        "is_error": failed,
                                        "content": "canary-payroll-99 CANARY-99",
                                    }
                                ]
                            }
                            expected.edits.append((when, rendered, effort, main, failed))
                        rows.append(user)
                    else:
                        event = token(number + 1, raw_count, stamp=stamp)
                        rows.extend([event, event])
                        expected.counters.responses_duplicate += 1
                if tool == "claude-code":
                    rows.extend(
                        [
                            assistant(f"CANARY-future-{day}-{session}", stamp=future, model=model),
                            result("CANARY-unmatched", stamp=stamp),
                            assistant(isApiErrorMessage=True),
                            {"type": "assistant", "message": {"id": "CANARY-bad"}},
                        ]
                    )
                    expected.counters.edits_unmatched += 1
                    path = (
                        generated.claude_root
                        / f"CANARY-{day}"
                        / (
                            f"CANARY-{session}.jsonl"
                            if main
                            else f"subagents/deep/CANARY-{session}.jsonl"
                        )
                    )
                else:
                    rows.extend(
                        [
                            token(100, 10, stamp=future),
                            {"type": "event_msg", "payload": {"type": "token_count", "info": None}},
                            token(101, 10, stamp="CANARY-bad"),
                        ]
                    )
                    path = (
                        generated.codex_root
                        / ("sessions" if main else "archived_sessions")
                        / str(day)
                        / f"rollout-CANARY-{session}.jsonl"
                    )
                rows.extend(
                    [
                        {"type": "attachment", "text": "CANARY-200 canary-payroll-200"},
                        "[1, 2]",
                        '{"type":"assistant","CANARY-201":',
                    ]
                )
                expected.counters.records_in_future += 1
                expected.counters.lines_lacking_field += 1
                expected.counters.lines_unknown_type += 2 if tool == "claude-code" else 1
                expected.counters.lines_not_json += 2
                expected.counters.files_read += 1
                expected.counters.lines += len(rows)
                encoded = write_rows(path, rows)
                generated.paths[tool].append(path)
                generated.expected[tool].add(expected)
                if compressed and tool == "codex" and day == 0 and session == 0:
                    copy = path.with_suffix(".jsonl.zst")
                    try:
                        zstd = importlib.import_module("compression.zstd")
                    except ImportError:
                        copy.write_bytes(b"CANARY-unsupported-compressed")
                        generated.expected[tool].counters.files_unread_compressed += 1
                    else:
                        copy.write_bytes(cast(bytes, zstd.compress(encoded)))
                        copied = Expected(
                            counters=replace(
                                expected.counters,
                                responses=0,
                                responses_without_reasoning=0,
                                records_in_future=0,
                                responses_duplicate=11,
                            )
                        )
                        generated.expected[tool].add(copied)
                    generated.paths[tool].append(copy)
    journal = generated.claude_root / "journal.jsonl"
    journal.parent.mkdir(parents=True, exist_ok=True)
    journal.write_text("CANARY-journal", encoding="utf-8")
    return generated
