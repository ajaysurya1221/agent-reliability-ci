"""`arci logs` / `realornoise`: the ladder, the numbers, the privacy rules and the fixed texts.

Written blind against `plan/exec/v2/logs/STATISTICS_LOGS-draft.md` (the contract),
`plan/exec/v2/logs/0016-logs-draft.md` (decisions, record model, fixed texts), the "Module
interfaces" block of `plan/exec/v2/tasks/L-CONTRACT.md` and the section "Log formats" of
`plan/exec/v2/tasks/L0-logs-spike.md`, without reading the implementation, its unit tests or
its spike. Nothing under `~/.claude` or `~/.codex` was opened: every log here is synthetic and
is written into `tmp_path`.

Two names are imported from the project: `arci.logs.cli.run`, the testable entry, and
`arci.hashing.hash_record`, to check the seal. Every expected number is computed here from the
day values planted in the logs: `p_real`, `p_none`, `u_none` and `p_streak` by brute-force
enumeration of all labelings (`_rank_tail`, `_g_tail`, `_runs_tail`), in exact arithmetic with
`fractions.Fraction`. The feature is never asked for its own expectation. The comment above
each group names the passage it comes from.
"""

from __future__ import annotations

import io
import itertools
import json
import math
import os
import re
import stat
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta, timezone
from fractions import Fraction
from functools import cache
from pathlib import Path
from typing import Any

import pytest

from arci.hashing import hash_record
from arci.logs.cli import run

pytestmark = pytest.mark.acceptance

# --- the window every scenario uses ---------------------------------------------------------
# Contract, "What is compared": `N` is the newest day with a main-thread response, the split
# `s` is `N - 13` days, the after period is `s..N`, the before period is the 84 days ending the
# day before `s`.

NOW = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)
NEWEST = date(2026, 11, 10)
SPLIT = date(2026, 10, 28)
AFTER_DAYS = tuple(date(2026, 11, 6) + timedelta(days=index) for index in range(5))
BEFORE_DAYS = tuple(date(2026, 10, 18) + timedelta(days=index) for index in range(10))
BEFORE_PERIOD = {"first_day": "2026-08-05", "last_day": "2026-10-27"}
AFTER_PERIOD = {"first_day": "2026-10-28", "last_day": "2026-11-10"}

# Day values several scenarios share. The before-days of ALTERNATING and SPREAD lie on
# alternating sides of their own median, so the streak check does not withhold them; RISING is
# monotone, so it does.
ALTERNATING = (90, 110, 90, 110, 90, 110, 90, 110, 90, 110)
SPREAD = (60, 150, 70, 140, 80, 130, 90, 120, 100, 110)
RISING = (60, 70, 80, 90, 100, 110, 120, 130, 140, 150)
MIDDLE = (65, 75, 85, 95, 105)
DROPPED = (10,) * 5
HELD = (200,) * 5

ALPHA_REAL = Fraction(1, 120)
ALPHA_NONE = Fraction(1, 40)
ALPHA_STREAK = Fraction(1, 10)

# --- names, fields and fixed texts of the record --------------------------------------------
# Record 0016, "Record model" and "Fixed texts".

LOGS_FIELDS = {
    "schema_version",
    "arci_version",
    "example",
    "utc_offset_minutes",
    "project_filtered",
    "tools",
    "exit_code",
    "seal",
}
TOOL_FIELDS = {
    "tool",
    "result",
    "reason",
    "model",
    "effort",
    "other_settings",
    "split_date",
    "before",
    "after",
    "measures",
    "context",
    "counters",
    "day_table_sha256",
}
MEASURE_FIELDS = {
    "id",
    "worse",
    "margin",
    "before_days",
    "after_days",
    "median_before",
    "median_after",
    "p_streak",
    "p_real",
    "u_none",
    "p_none",
    "finding",
}
DAY_FIELDS = {"day", "count", "value"}
PERIOD_FIELDS = {"first_day", "last_day"}
CONTEXT_FIELDS = {
    "client_versions_before",
    "client_versions_after",
    "client_versions_both",
    "workdirs_before",
    "workdirs_after",
    "subagent_share_before",
    "subagent_share_after",
}
COUNTER_FIELDS = {
    "files_read",
    "files_unread_compressed",
    "files_unreadable",
    "files_outside_project",
    "lines",
    "lines_not_json",
    "lines_unknown_type",
    "lines_lacking_field",
    "records_in_future",
    "records_without_timezone",
    "responses",
    "responses_duplicate",
    "responses_without_reasoning",
    "responses_without_setting",
    "edits_denied",
    "edits_unmatched",
}
# Which test fields a finding fills (record 0016, `MeasureDecision`).
FILLED = {
    "too_few_days": (),
    "streaky": ("p_streak",),
    "real_drop": ("p_streak", "p_real"),
    "no_drop": ("p_streak", "p_real", "u_none", "p_none"),
    "cannot_tell": ("p_streak", "p_real", "u_none", "p_none"),
}
TEST_FIELDS = ("p_streak", "p_real", "u_none", "p_none")

REASONS = {
    "real_drop": (
        "In at least one recorded measure, the days after the split moved toward worse by more"
        " than a chance ordering of your days explains."
    ),
    "no_drop": (
        "No recorded measure moved toward worse by its margin or more. This does not say"
        " anything improved."
    ),
    "not_enough_evidence": "The days are too few or too variable to tell a shift from noise.",
    "too_few_days": "Too few usable days for every measure (5 needed after the split, 10 before).",
    "streaky_days": (
        "Your earlier days come in streaks in a recorded measure, so this comparison cannot tell"
        " a streak from a drop."
    ),
    "no_usable_setting": "No model and effort setting has a response in the window.",
    "read_error": "Session log files could not be read.",
    "format_not_recognised": (
        "Log files were found, but this version could not recover a response from them."
    ),
}
NO_LOGS_REASON = {
    "claude-code": (
        "No session logs found for Claude Code. Looked under ~/.claude/projects (or"
        " CLAUDE_CONFIG_DIR). Use --claude-dir DIR, or try: realornoise --example"
    ),
    "codex": (
        "No session logs found for Codex. Looked under ~/.codex (or CODEX_HOME). Use --codex-dir"
        " DIR, or try: realornoise --example"
    ),
}
USAGE_ERRORS = {
    "malformed": "--since needs a date as YYYY-MM-DD.",
    "early": "--since can be at most 83 days before the newest day in the logs.",
    "usage": "Usage error. Run: realornoise --help",
}
# The notices, which print only when their count is at least 1.
F9 = "Compressed Codex files not read (Python 3.14 is needed): {}. The result uses the rest."
F14 = "Other model or effort settings, not compared: {}."
F15 = "Lines that lacked a needed field, left out: {}."
F16 = "Records stamped later than now, left out: {}."
F17 = "Files that could not be read: {}. The result uses the rest."
NOTICES = (F9, F14, F15, F16, F17)
F4 = {
    "REAL_DROP": "RESULT: REAL DROP",
    "NO_DROP": "RESULT: NO DROP",
    "CANNOT_TELL": "RESULT: CANNOT TELL",
    "ERROR": "RESULT: ERROR",
}
F10 = (
    "This shows what your logs recorded. It does not establish answer quality, a cause, or a"
    " change to the model: your tasks, prompts, projects or client version may have changed."
    " For each tool above and one comparison: if nothing shifted, REAL DROP appears at most"
    " 2.5% of the time; if a measure moved toward worse by its margin or more, NO DROP appears"
    " at most 2.5% of the time. Both hold only if: (1) the days in this window are"
    " interchangeable when nothing changes; (2) any date, model, effort or project you gave was"
    " not chosen from these logs; (3) a change moves every day alike, by an amount the measure"
    " can take; (4) a change leaves the same days, setting, reference value and earlier-day"
    " values in use. None of these is checked, and the streak check does not prove them."
    " Running this again and again until a result appears is not covered. Exact statement:"
    " docs/STATISTICS_LOGS.md in the repository."
)
F10_FIRST_SENTENCE = "This shows what your logs recorded."
F10_THIRD_SENTENCE = (
    "For each tool above and one comparison: if nothing shifted, REAL DROP appears at most 2.5%"
    " of the time"
)
# F10 is the one fixed text the record gives already broken into lines: its breaks are not the
# ones the wrapping rule would choose, so the lines below are the record's own.
F10_LINES = (
    "This shows what your logs recorded. It does not establish answer quality, a cause,"
    " or a change",
    "to the model: your tasks, prompts, projects or client version may have changed.",
    "For each tool above and one comparison: if nothing shifted, REAL DROP appears at most 2.5%"
    " of the",
    "time; if a measure moved toward worse by its margin or more, NO DROP appears at most 2.5%"
    " of the",
    "time. Both hold only if: (1) the days in this window are interchangeable when nothing"
    " changes;",
    "(2) any date, model, effort or project you gave was not chosen from these logs; (3) a change",
    "moves every day alike, by an amount the measure can take; (4) a change leaves the same days,",
    "setting, reference value and earlier-day values in use. None of these is checked, and the"
    " streak",
    "check does not prove them. Running this again and again until a result appears is not"
    " covered.",
    "Exact statement: docs/STATISTICS_LOGS.md in the repository.",
)
F12 = (
    "Share: --markdown FILE · --html FILE · --json FILE      "
    "Stronger evidence: arci verdict, arci run"
)
MARKDOWN_CLOSE = {
    "REAL_DROP": (
        "One person's logs. Evidence of movement toward worse in a recorded measure; this"
        " establishes no cause and says nothing about answer quality."
    ),
    "NO_DROP": (
        "One person's logs. No recorded measure moved toward worse by its margin; this does not"
        " say anything improved."
    ),
    "CANNOT_TELL": "One person's logs. Not enough to tell a shift from noise.",
}
MARKDOWN_BOUND = (
    "Wrong REAL DROP and wrong NO DROP are each at most 2.5% for this tool and one comparison,"
    " only under unchecked assumptions (days in the window interchangeable; no date, model,"
    " effort or project chosen from these logs; a uniform shift the measure can take; the same"
    " days, setting, reference value and earlier-day values in use). Repeated checking until a"
    " result appears is not covered."
)
ROW_NAMES = {
    "reasoning_tokens": "reasoning tokens per response",
    "no_reasoning_share": "responses with no reasoning",
    "edit_failure_share": "file edits that failed",
    "repeated_value_share": "reasoning at one repeated value",
}
RENDERED_MARGIN = {
    "reasoning_tokens": "25%",
    "no_reasoning_share": "10 pts",
    "edit_failure_share": "3 pts",
    "repeated_value_share": "10 pts",
}
TOOL_NAMES = {"claude-code": "Claude Code", "codex": "Codex"}
MEASURES: dict[str, tuple[str, Fraction]] = {
    "reasoning_tokens": ("lower", Fraction(1, 4)),
    "no_reasoning_share": ("higher", Fraction(1, 10)),
    "edit_failure_share": ("higher", Fraction(3, 100)),
    "repeated_value_share": ("higher", Fraction(1, 10)),
}
TOOL_MEASURES = {
    "claude-code": ("reasoning_tokens", "no_reasoning_share", "edit_failure_share"),
    "codex": ("reasoning_tokens", "no_reasoning_share", "repeated_value_share"),
}
EXIT = {"REAL_DROP": 1, "NO_DROP": 0, "CANNOT_TELL": 2, "ERROR": 3}

# --- synthetic logs -------------------------------------------------------------------------
# L0, "Log formats": every line is one JSON object; one Claude Code response is one distinct
# `message.id` within a file; one Codex response is one `token_count` event.

CLAUDE_MODEL = "claude-opus-4-20250514"
CLAUDE_OTHER = "claude-sonnet-4-20250514"
CODEX_MODEL = "gpt-5-codex"
CODEX_OTHER = "gpt-5-mini"
VERSION = "2.0.42"
WORKDIR = "/work/project"
PROJECT_DIR = "-work-project"

# Canary tokens: one upper case, one lower case shaped like a model id, one numeric shaped like
# a version, two private-looking model ids, a working directory, a prompt, a tool input and a
# tool output. Record 0016, "Privacy is a tested property".
CANARY_UPPER = "CANARYUPPERCASE"
CANARY_LOWER = "canary-lower-model-x"
CANARY_VERSION = "9.8.7654321"
CANARY_MODEL_A = "acme-payroll-secret"
CANARY_MODEL_B = "gpt-12345678-87654321"
# Nine parts and eight plain numbers: over the grammar's limits of six and three.
CANARY_MODEL_C = "gpt-12-34-56-78-87-65-43-21"
CANARY_EFFORT_1 = "canary-effort-aggressive"
CANARY_EFFORT_2 = "canary-effort-zealous"
# An accepted id that sorts before every rejected one, so that numbering the rejected names
# among themselves is visible: "4o" is a letter-and-digits token and "mini" is a listed word.
SMALL_MODEL = "4o-mini"
CANARY_DIR = "/canary-home/canary-work"
CANARY_PROMPT = "canary prompt text"
CANARY_INPUT = "canary tool input"
CANARY_OUTPUT = "canary tool output"
CANARIES = (
    CANARY_UPPER,
    CANARY_LOWER,
    CANARY_VERSION,
    CANARY_MODEL_A,
    CANARY_MODEL_B,
    CANARY_MODEL_C,
    CANARY_EFFORT_1,
    CANARY_EFFORT_2,
    CANARY_DIR,
    CANARY_PROMPT,
    CANARY_INPUT,
    CANARY_OUTPUT,
)
CANARY_PARTS = ("acme", "payroll", "87654321", "12-34-56", "canary", "CANARY")


@dataclass(frozen=True)
class Setting:
    """A model id and an effort value as a log records them, with the key the effort is on."""

    model: str | None = CLAUDE_MODEL
    effort: str | None = "high"
    key: str = "effort"


CLAUDE_SETTING = Setting(CLAUDE_MODEL, "high")
CLAUDE_SECOND = Setting(CLAUDE_OTHER, "high")
CODEX_SETTING = Setting(CODEX_MODEL, "high")
CODEX_SECOND = Setting(CODEX_OTHER, "high")


@dataclass(frozen=True)
class Day:
    """What one day of one synthetic session holds.

    `counts` are the reasoning counts of the main-thread responses of the first setting (None is
    a response the log gives no count for); `edits` are its file-edit results (True failed);
    `other` and `other_edits` belong to the second setting; `sidechain` are sub-agent responses.
    """

    counts: tuple[int | None, ...] = ()
    edits: tuple[bool, ...] = ()
    other: tuple[int | None, ...] = ()
    other_edits: tuple[bool, ...] = ()
    sidechain: tuple[int | None, ...] = ()
    denied: int = 0
    unmatched: int = 0
    bash: int = 0
    version: str | None = None
    extra: tuple[dict[str, Any], ...] = ()


def _at(day: date, hour: int = 6, minute: int = 0, *, zone: str = "Z") -> str:
    return f"{day.isoformat()}T{hour:02d}:{minute:02d}:00.000{zone}"


def _write_lines(path: Path, lines: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"{json.dumps(line)}\n" for line in lines), encoding="utf-8")


def _assistant(
    *,
    mid: str,
    when: str,
    setting: Setting,
    reasoning: int | None,
    calls: Sequence[tuple[str, str]] = (),
    sidechain: bool = False,
    version: str | None = VERSION,
    cwd: str = WORKDIR,
    text: str = "ok",
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    content: list[dict[str, Any]] = []
    if reasoning:
        content.append({"type": "thinking", "thinking": text, "signature": f"sig-{mid}"})
    for call_id, name in calls:
        content.append(
            {
                "type": "tool_use",
                "id": call_id,
                "name": name,
                "input": {"file_path": f"{cwd}/f.txt", "new_string": text},
            }
        )
    content.append({"type": "text", "text": text})
    details = None if reasoning is None else {"thinking_tokens": reasoning}
    message: dict[str, Any] = {
        "id": mid,
        "type": "message",
        "role": "assistant",
        "content": content,
        "usage": {"output_tokens": 7, "output_tokens_details": details},
        "stop_reason": "end_turn",
    }
    if setting.model is not None:
        message["model"] = setting.model
    line: dict[str, Any] = {
        "type": "assistant",
        "timestamp": when,
        "uuid": f"u-{mid}",
        "cwd": cwd,
        "isSidechain": sidechain,
        "message": message,
    }
    if version is not None:
        line["version"] = version
    if setting.effort is not None:
        line[setting.key] = setting.effort
    if extra:
        line.update(extra)
    return line


def _tool_result(
    *,
    when: str,
    call_id: str,
    failed: bool,
    denied: str | None = None,
    text: str = "done",
) -> dict[str, Any]:
    block = {"type": "tool_result", "tool_use_id": call_id, "content": text, "is_error": failed}
    line: dict[str, Any] = {
        "type": "user",
        "timestamp": when,
        "isSidechain": False,
        "message": {"role": "user", "content": [block]},
    }
    if denied == "kind":
        line["toolDenialKind"] = "reject"
    elif denied == "decision":
        line["permissionDecision"] = {"decision": "reject"}
    return line


def _claude_day(
    day: date,
    plan: Day,
    *,
    setting: Setting,
    other: Setting,
    prefix: str,
    cwd: str,
    text: str,
    output: str,
) -> list[dict[str, Any]]:
    """One day of one Claude Code session: assistant lines, then the results they called."""
    lines: list[dict[str, Any]] = []
    calls: dict[int, tuple[tuple[str, str], ...]] = {}
    slot = 0
    for index in range(len(plan.edits)):
        calls[slot] = ((f"{prefix}{day}-edit{index}", "Edit"),)
        slot += 1
    for index in range(plan.denied):
        calls[slot] = ((f"{prefix}{day}-den{index}", "Write"),)
        slot += 1
    for index in range(plan.bash):
        calls[slot] = ((f"{prefix}{day}-bash{index}", "Bash"),)
        slot += 1
    assert slot <= len(plan.counts), "the day needs one response per tool call"
    version = VERSION if plan.version is None else plan.version
    for index, count in enumerate(plan.counts):
        lines.append(
            _assistant(
                mid=f"{prefix}{day}-a{index}",
                when=_at(day, 6, index),
                setting=setting,
                reasoning=count,
                calls=calls.get(index, ()),
                version=version,
                cwd=cwd,
                text=text,
            )
        )
    for index, failed in enumerate(plan.edits):
        lines.append(
            _tool_result(
                when=_at(day, 7, index),
                call_id=f"{prefix}{day}-edit{index}",
                failed=failed,
                text=output,
            )
        )
    for index in range(plan.denied):
        lines.append(
            _tool_result(
                when=_at(day, 7, 20 + index),
                call_id=f"{prefix}{day}-den{index}",
                failed=True,
                denied="kind" if index % 2 == 0 else "decision",
                text=output,
            )
        )
    for index in range(plan.bash):
        lines.append(
            _tool_result(
                when=_at(day, 7, 30 + index),
                call_id=f"{prefix}{day}-bash{index}",
                failed=True,
                text=output,
            )
        )
    for index in range(plan.unmatched):
        lines.append(
            _tool_result(
                when=_at(day, 7, 40 + index),
                call_id=f"{prefix}{day}-ghost{index}",
                failed=True,
                text=output,
            )
        )
    other_calls = {
        index: ((f"{prefix}{day}-oedit{index}", "Edit"),) for index in range(len(plan.other_edits))
    }
    for index, count in enumerate(plan.other):
        lines.append(
            _assistant(
                mid=f"{prefix}{day}-o{index}",
                when=_at(day, 9, index),
                setting=other,
                reasoning=count,
                calls=other_calls.get(index, ()),
                version=version,
                cwd=cwd,
                text=text,
            )
        )
    for index, failed in enumerate(plan.other_edits):
        lines.append(
            _tool_result(
                when=_at(day, 10, index),
                call_id=f"{prefix}{day}-oedit{index}",
                failed=failed,
                text=output,
            )
        )
    for index, count in enumerate(plan.sidechain):
        lines.append(
            _assistant(
                mid=f"{prefix}{day}-s{index}",
                when=_at(day, 11, index),
                setting=setting,
                reasoning=count,
                sidechain=True,
                version=version,
                cwd=cwd,
                text=text,
            )
        )
    lines.extend(dict(line) for line in plan.extra)
    return lines


def write_claude(
    root: Path,
    plans: Mapping[date, Day],
    *,
    setting: Setting = CLAUDE_SETTING,
    other: Setting = CLAUDE_SECOND,
    session: str = "01",
    project: str = PROJECT_DIR,
    prefix: str = "m",
    cwd: str = WORKDIR,
    text: str = "ok",
    output: str = "done",
) -> Path:
    """One Claude Code session file: `<root>/<project-dir>/<session>.jsonl`."""
    lines: list[dict[str, Any]] = []
    for day in sorted(plans):
        lines.extend(
            _claude_day(
                day,
                plans[day],
                setting=setting,
                other=other,
                prefix=prefix,
                cwd=cwd,
                text=text,
                output=output,
            )
        )
    path = root / project / f"{session}.jsonl"
    _write_lines(path, lines)
    return path


def _codex_day(
    day: date,
    *,
    setting: Setting,
    other: Setting,
    counts: Sequence[int | None],
    others: Sequence[int | None],
    cwd: str,
    version: str,
    source: str,
) -> list[dict[str, Any]]:
    lines: list[dict[str, Any]] = [
        {
            "timestamp": _at(day, 5, 0),
            "type": "session_meta",
            "payload": {
                "id": f"session-{day}-{source}",
                "cwd": cwd,
                "cli_version": version,
                "thread_source": source,
                "originator": "codex_cli_rs",
            },
        }
    ]
    total = 1000
    for index, (active, series) in enumerate(((setting, counts), (other, others))):
        if not series:
            continue
        payload: dict[str, Any] = {}
        if active.model is not None:
            payload["model"] = active.model
        if active.effort is not None:
            payload["effort"] = active.effort
        lines.append({"timestamp": _at(day, 6, 0), "type": "turn_context", "payload": payload})
        for offset, count in enumerate(series):
            total += 1000
            last: dict[str, Any] = {"input_tokens": 3, "output_tokens": 4}
            if count is not None:
                last["reasoning_output_tokens"] = count
            lines.append(
                {
                    "timestamp": _at(day, 6 + index, offset),
                    "type": "event_msg",
                    "payload": {
                        "type": "token_count",
                        "info": {
                            "last_token_usage": last,
                            "total_token_usage": {"total_tokens": total},
                        },
                    },
                }
            )
    return lines


def write_codex(
    root: Path,
    plans: Mapping[date, Day],
    *,
    setting: Setting = CODEX_SETTING,
    other: Setting = CODEX_SECOND,
    cwd: str = WORKDIR,
    name: str = "rollout",
) -> None:
    """One Codex rollout per day: `<root>/sessions/YYYY/MM/DD/<name>-<day>.jsonl`."""
    for day in sorted(plans):
        plan = plans[day]
        version = VERSION if plan.version is None else plan.version
        path = (
            root
            / "sessions"
            / f"{day.year:04d}"
            / f"{day.month:02d}"
            / f"{day.day:02d}"
            / f"{name}-{day}.jsonl"
        )
        _write_lines(
            path,
            _codex_day(
                day,
                setting=setting,
                other=other,
                counts=plan.counts,
                others=plan.other,
                cwd=cwd,
                version=version,
                source="user",
            ),
        )
        if plan.sidechain:
            _write_lines(
                path.with_name(f"{name}-{day}-sub.jsonl"),
                _codex_day(
                    day,
                    setting=setting,
                    other=other,
                    counts=plan.sidechain,
                    others=(),
                    cwd=cwd,
                    version=version,
                    source="subagent",
                ),
            )


def _uniform(
    before: Sequence[int | None],
    after: Sequence[int | None],
    *,
    responses: int = 20,
    before_days: Sequence[date] = BEFORE_DAYS,
    after_days: Sequence[date] = AFTER_DAYS,
    **over: Any,
) -> dict[date, Day]:
    """One day plan per day, every response of a day carrying the same reasoning count."""
    plans: dict[date, Day] = {}
    for days, values in ((before_days, before), (after_days, after)):
        for day, value in zip(days, values, strict=True):
            plans[day] = Day(counts=(value,) * responses, **over)
    return plans


# --- expected numbers, by brute force -------------------------------------------------------
# Contract, "The tests": the real-drop test is the share of the `C(n+m, m)` labelings whose
# midrank sum is at most `W`; `G(n, m, u)` is the probability that the strict count is at least
# `u` over the same labelings with distinct values; `p_streak` is the probability of `R` or
# fewer runs. All three are enumerated here, never approximated.


def _median(values: Sequence[Fraction]) -> Fraction:
    ordered = sorted(values)
    half = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[half]
    return (ordered[half - 1] + ordered[half]) / 2


def _doubled_midranks(pooled: Sequence[Fraction]) -> list[int]:
    order = sorted(range(len(pooled)), key=lambda index: pooled[index])
    ranks = [0] * len(pooled)
    start = 0
    while start < len(order):
        stop = start
        while stop + 1 < len(order) and pooled[order[stop + 1]] == pooled[order[start]]:
            stop += 1
        group = stop - start + 1
        doubled = sum(2 * (place + 1) for place in range(start, stop + 1)) // group
        for place in range(start, stop + 1):
            ranks[order[place]] = doubled
        start = stop + 1
    return ranks


@cache
def _rank_tail(ranks: tuple[int, ...], m: int, limit: int) -> Fraction:
    hits = sum(1 for combo in itertools.combinations(ranks, m) if sum(combo) <= limit)
    return Fraction(hits, math.comb(len(ranks), m))


def _p_real(before: Sequence[Fraction], after: Sequence[Fraction]) -> Fraction:
    ranks = _doubled_midranks([*before, *after])
    weight = sum(ranks[len(before) :])
    return _rank_tail(tuple(sorted(ranks)), len(after), weight)


@cache
def _g_tail(n: int, m: int, u: int) -> Fraction:
    total = 0
    hits = 0
    places = range(n + m)
    for combo in itertools.combinations(places, m):
        total += 1
        chosen = set(combo)
        pairs = sum(1 for low in places if low not in chosen for high in combo if low < high)
        if pairs >= u:
            hits += 1
    return Fraction(hits, total)


def _strict_count(moved: Sequence[Fraction], after: Sequence[Fraction]) -> int:
    return sum(1 for low in moved for high in after if low < high)


@cache
def _runs_tail(above: int, below: int, runs: int) -> Fraction:
    total = 0
    hits = 0
    for combo in itertools.combinations(range(above + below), above):
        total += 1
        chosen = set(combo)
        marks = [place in chosen for place in range(above + below)]
        seen = 1 + sum(1 for place in range(1, len(marks)) if marks[place] != marks[place - 1])
        if seen <= runs:
            hits += 1
    return Fraction(hits, total)


def _p_streak(before_in_date_order: Sequence[Fraction]) -> Fraction:
    middle = _median(before_in_date_order)
    marks = [value > middle for value in before_in_date_order if value != middle]
    above = sum(marks)
    below = len(marks) - above
    if above == 0 or below == 0:
        return Fraction(1)
    runs = 1 + sum(1 for place in range(1, len(marks)) if marks[place] != marks[place - 1])
    return _runs_tail(above, below, runs)


def _rational(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def _known(counts: Sequence[int | None]) -> list[int]:
    return [count for count in counts if count is not None]


def _positive(counts: Sequence[int | None]) -> list[int]:
    return [count for count in _known(counts) if count > 0]


def _day_value(measure: str, plan: Day, vstar: int | None) -> tuple[int, Fraction] | None:
    """The measure's value and count for one day, or None when the day is not usable for it.

    Contract, "Measures": 20 known counts (10 of them positive) for the two count measures, 20
    known counts for the no-reasoning share, 10 file-edit results for the edit share.
    """
    known = _known(plan.counts)
    positive = _positive(plan.counts)
    if measure == "no_reasoning_share":
        if len(known) >= 20:
            return len(known), Fraction(sum(1 for count in known if count == 0), len(known))
        return None
    if measure == "edit_failure_share":
        if len(plan.edits) >= 10:
            return len(plan.edits), Fraction(sum(1 for bad in plan.edits if bad), len(plan.edits))
        return None
    if len(known) < 20 or len(positive) < 10:
        return None
    if measure == "reasoning_tokens":
        return len(positive), _median([Fraction(count) for count in positive])
    assert vstar is not None
    return len(positive), Fraction(sum(1 for count in positive if count == vstar), len(positive))


def _vstar(plans: Mapping[date, Day], window: Iterable[date]) -> int | None:
    """`v*`: the most common positive count over both periods; ties go to the smallest."""
    tally = Counter(count for day in window for count in _positive(plans[day].counts))
    if not tally:
        return None
    best = max(tally.values())
    return min(value for value, seen in tally.items() if seen == best)


def _day_json(day: date, count: int, value: Fraction) -> dict[str, Any]:
    return {"day": day.isoformat(), "count": count, "value": _rational(value)}


def _expect_measure(
    measure: str,
    before: Sequence[tuple[date, int, Fraction]],
    after: Sequence[tuple[date, int, Fraction]],
) -> dict[str, Any]:
    """The MeasureDecision the contract's ladder asks for, with only the fields it fills."""
    worse, margin = MEASURES[measure]
    sign = 1 if worse == "lower" else -1
    record: dict[str, Any] = {
        "id": measure,
        "worse": worse,
        "margin": _rational(margin),
        "before_days": [_day_json(*row) for row in before],
        "after_days": [_day_json(*row) for row in after],
        "median_before": _rational(_median([row[2] for row in before])) if before else None,
        "median_after": _rational(_median([row[2] for row in after])) if after else None,
        "p_streak": None,
        "p_real": None,
        "u_none": None,
        "p_none": None,
        "finding": "too_few_days",
    }
    if len(after) < 5 or len(before) < 10:
        return record
    x = [sign * row[2] for row in before]
    y = [sign * row[2] for row in after]
    streak = _p_streak([row[2] for row in before])
    record["p_streak"] = _rational(streak)
    if streak <= ALPHA_STREAK:
        record["finding"] = "streaky"
        return record
    real = _p_real(x, y)
    record["p_real"] = _rational(real)
    if real <= ALPHA_REAL:
        record["finding"] = "real_drop"
        return record
    if measure == "reasoning_tokens":
        moved = [value * (1 - margin) for value in x]
    else:
        moved = [value - margin for value in x]
    count = _strict_count(moved, y)
    none = _g_tail(len(x), len(y), count)
    record["u_none"] = count
    record["p_none"] = _rational(none)
    record["finding"] = "no_drop" if none <= ALPHA_NONE else "cannot_tell"
    return record


def _periods(plans: Mapping[date, Day], split: date) -> tuple[tuple[date, ...], tuple[date, ...]]:
    days = sorted(plans)
    return (
        tuple(day for day in days if day < split),
        tuple(day for day in days if day >= split),
    )


def _expect_measures(
    tool: str,
    plans: Mapping[date, Day],
    *,
    split: date = SPLIT,
    before_days: Sequence[date] | None = None,
    after_days: Sequence[date] | None = None,
) -> list[dict[str, Any]]:
    planted = _periods(plans, split)
    before = planted[0] if before_days is None else tuple(before_days)
    after = planted[1] if after_days is None else tuple(after_days)
    vstar = _vstar(plans, [*before, *after]) if tool == "codex" else None
    expected: list[dict[str, Any]] = []
    for measure in TOOL_MEASURES[tool]:
        series: list[list[tuple[date, int, Fraction]]] = [[], []]
        for index, days in enumerate((before, after)):
            for day in days:
                got = _day_value(measure, plans[day], vstar)
                if got is not None:
                    series[index].append((day, got[0], got[1]))
        expected.append(_expect_measure(measure, series[0], series[1]))
    return expected


def _expect_result(measures: Sequence[Mapping[str, Any]]) -> tuple[str, str]:
    """Contract, "Result for a tool, in this order", steps 3 to 8.

    One streaky measure stops the whole comparison: `streaky_days` is decided before REAL DROP
    and NO DROP, and the other measures keep the findings their own tests gave.
    """
    findings = [measure["finding"] for measure in measures]
    if all(finding == "too_few_days" for finding in findings):
        return "CANNOT_TELL", "too_few_days"
    if "streaky" in findings:
        return "CANNOT_TELL", "streaky_days"
    if "real_drop" in findings:
        return "REAL_DROP", "real_drop"
    if all(finding == "no_drop" for finding in findings):
        return "NO_DROP", "no_drop"
    return "CANNOT_TELL", "not_enough_evidence"


def _expect_exit(results: Sequence[str]) -> int:
    """Contract, "Process exit code"."""
    standing = [result for result in results if result != "ERROR"]
    if not standing:
        return 3
    if "REAL_DROP" in standing:
        return 1
    if "CANNOT_TELL" in standing:
        return 2
    return 0


# --- running the command --------------------------------------------------------------------
# Record 0016, "Command line and layout": `run(argv, *, now, env, home, out, err) -> int`.


@dataclass
class Outcome:
    code: int
    out: str
    err: str
    body: dict[str, Any] | None
    json_path: Path
    extra: dict[str, Path] = field(default_factory=dict)

    @property
    def lines(self) -> list[str]:
        return self.out.splitlines()

    def tool(self, index: int = 0) -> dict[str, Any]:
        assert self.body is not None
        return self.body["tools"][index]

    def tools(self) -> list[dict[str, Any]]:
        assert self.body is not None
        return self.body["tools"]

    def text(self, name: str) -> str:
        return self.extra[name].read_text(encoding="utf-8")


def _flat(text: str) -> str:
    """The text with every run of whitespace collapsed, for sentences the record may wrap."""
    return " ".join(text.split())


def _says(text: str, sentence: str) -> None:
    assert _flat(sentence) in _flat(text), sentence


def _row_finding(measure: Mapping[str, Any], reason: str) -> str:
    """The F6 finding cell for one measure.

    Record 0016, F6: "when the tool's reason is `streaky_days`, every row that is not `days come
    in streaks` or `too few days` shows `not used` instead of its own finding (the record keeps
    the finding)".
    """
    finding = measure["finding"]
    if finding == "streaky":
        return "days come in streaks"
    if finding == "too_few_days":
        return "too few days"
    if reason == "streaky_days":
        return "not used"
    if finding == "real_drop":
        return "real drop"
    if finding == "no_drop":
        return f"no drop (margin {RENDERED_MARGIN[measure['id']]})"
    return "cannot tell"


def _wrapped(sentence: str) -> list[str]:
    """The sentence broken as the text output breaks it.

    Record 0016, "Fixed texts": "a fixed sentence longer than 100 characters is broken at the
    last space that leaves the line at most 100 characters long, and so on for the rest (a line
    of exactly 100 characters is allowed)". The Markdown and HTML outputs have no line limit,
    so this applies to the terminal text only.
    """
    lines: list[str] = []
    rest = sentence
    while len(rest) > 100:
        cut = rest.rfind(" ", 0, 101)
        lines.append(rest[:cut])
        rest = rest[cut + 1 :]
    lines.append(rest)
    return lines


def _block(outcome: Outcome, *sentences: str) -> None:
    """Each sentence appears as its own run of consecutive output lines, broken by the rule."""
    for sentence in sentences:
        _run_of(outcome, _wrapped(sentence))


def _run_of(outcome: Outcome, wanted: Sequence[str]) -> None:
    """`wanted` appears as a run of consecutive output lines."""
    lines = outcome.lines
    rows = list(wanted)
    assert any(
        lines[start : start + len(rows)] == rows for start in range(len(lines) + 1 - len(rows))
    ), rows[0]


def _args(
    tool: str,
    *,
    claude: Path | None = None,
    codex: Path | None = None,
    utc: bool = True,
    extra: Sequence[str] = (),
) -> list[str]:
    argv = ["--tool", tool]
    if claude is not None:
        argv += ["--claude-dir", str(claude)]
    if codex is not None:
        argv += ["--codex-dir", str(codex)]
    if utc:
        argv.append("--utc")
    return [*argv, *extra]


def _day_table(tool: Mapping[str, Any]) -> dict[str, Any]:
    """The structure `day_table_sha256` hashes (record 0016, "Record model", last bullet)."""
    return {
        "method": "arci-logs/1",
        "tool": tool["tool"],
        "model": tool["model"],
        "effort": tool["effort"],
        "split_date": tool["split_date"],
        "before": tool["before"],
        "after": tool["after"],
        "alpha_real": "1/120",
        "alpha_none": "1/40",
        "measures": [
            {name: measure[name] for name in ("id", "margin", "before_days", "after_days")}
            for measure in tool["measures"]
        ],
    }


def _audit(body: Mapping[str, Any], code: int) -> None:
    """The record rules that hold on every run: fields, null rules, ascending days, the seal."""
    assert set(body) == LOGS_FIELDS
    assert body["schema_version"] == "arci-logs/1"
    assert body["example"] is False
    assert isinstance(body["project_filtered"], bool)
    assert body["exit_code"] == code
    results: list[str] = []
    for tool in body["tools"]:
        assert set(tool) == TOOL_FIELDS
        assert tool["tool"] in TOOL_NAMES
        assert tool["result"] in F4
        results.append(tool["result"])
        assert set(tool["counters"]) == COUNTER_FIELDS
        assert all(isinstance(value, int) for value in tool["counters"].values())
        ids = [measure["id"] for measure in tool["measures"]]
        assert ids in ([], list(TOOL_MEASURES[tool["tool"]]))
        blank = tool["result"] == "ERROR" or tool["reason"] == "no_usable_setting"
        if blank:
            assert ids == []
            for name in ("model", "effort", "before", "after", "context", "day_table_sha256"):
                assert tool[name] is None, name
        else:
            assert len(ids) == 3
            assert tool["model"] is not None and tool["effort"] is not None
            assert tool["split_date"] is not None
            assert set(tool["before"]) == PERIOD_FIELDS
            assert set(tool["context"]) == CONTEXT_FIELDS
            assert re.fullmatch(r"[0-9a-f]{64}", tool["day_table_sha256"])
            assert tool["day_table_sha256"] == hash_record(_day_table(tool))
            if tool["after"] is None:
                assert all(not measure["after_days"] for measure in tool["measures"])
            else:
                assert set(tool["after"]) == PERIOD_FIELDS
        for measure in tool["measures"]:
            assert set(measure) == MEASURE_FIELDS
            filled = FILLED[measure["finding"]]
            for name in TEST_FIELDS:
                if name in filled:
                    assert measure[name] is not None, (measure["id"], name)
                else:
                    assert measure[name] is None, (measure["id"], name)
            for side in ("before_days", "after_days"):
                days = [row["day"] for row in measure[side]]
                assert days == sorted(days) and len(days) == len(set(days))
                for row in measure[side]:
                    assert set(row) == DAY_FIELDS
    assert code == _expect_exit(results)
    draft = {name: value for name, value in body.items() if name != "seal"}
    assert body["seal"] == hash_record(draft)


def _run(
    tmp_path: Path,
    argv: Sequence[str],
    *,
    now: datetime = NOW,
    outputs: Sequence[str] = (),
    stem: str = "decision",
) -> Outcome:
    home = tmp_path / "home"
    home.mkdir(parents=True, exist_ok=True)
    out, err = io.StringIO(), io.StringIO()
    json_path = tmp_path / f"{stem}.json"
    full = [*argv, "--json", str(json_path)]
    extra: dict[str, Path] = {}
    for name in outputs:
        path = tmp_path / f"{stem}.{'md' if name == 'markdown' else name}"
        extra[name] = path
        full += [f"--{name}", str(path)]
    try:
        code = run(full, now=now, env={}, home=home, out=out, err=err)
    except SystemExit:
        pytest.fail("`run` exited the process instead of returning an exit code")
    except Exception as exc:
        hits = sum(1 for canary in CANARIES if canary in str(exc))
        pytest.fail(f"`run` raised {type(exc).__name__}; canary strings in its message: {hits}")
    printed, failed = out.getvalue(), err.getvalue()
    assert "Traceback" not in printed and "Traceback" not in failed
    for line in [*printed.splitlines(), *failed.splitlines()]:
        assert len(line) <= 100, line
    body = None
    if json_path.exists():
        body = json.loads(json_path.read_text(encoding="utf-8"))
        _audit(body, code)
    return Outcome(code=code, out=printed, err=failed, body=body, json_path=json_path, extra=extra)


def _claude_run(
    tmp_path: Path, plans: Mapping[date, Day], *, extra: Sequence[str] = (), **kw: Any
) -> Outcome:
    root = tmp_path / "claude"
    write_claude(root, plans, **kw)
    return _run(tmp_path, _args("claude-code", claude=root, extra=extra))


def _codex_run(
    tmp_path: Path, plans: Mapping[date, Day], *, extra: Sequence[str] = (), **kw: Any
) -> Outcome:
    root = tmp_path / "codex"
    write_codex(root, plans, **kw)
    return _run(tmp_path, _args("codex", codex=root, extra=extra))


def _check(outcome: Outcome, tool: str, plans: Mapping[date, Day], **kw: Any) -> dict[str, Any]:
    """Compare one tool's measures, result and reason with the expectation computed here."""
    expected = _expect_measures(tool, plans, **kw)
    result, reason = _expect_result(expected)
    got = outcome.tool(0 if tool == "claude-code" else -1)
    assert got["measures"] == expected
    assert (got["result"], got["reason"]) == (result, reason)
    return got


# --- 1. the ladder: one scenario per result and reason ---------------------------------------
# Contract, "Result for a tool, in this order" and "Process exit code"; record 0016 item 2.

LADDER: dict[str, tuple[str, str]] = {
    "real_drop": ("REAL_DROP", "real_drop"),
    "no_drop": ("NO_DROP", "no_drop"),
    "not_enough_evidence": ("CANNOT_TELL", "not_enough_evidence"),
    "too_few_days": ("CANNOT_TELL", "too_few_days"),
    "streaky_days": ("CANNOT_TELL", "streaky_days"),
    "no_usable_setting": ("CANNOT_TELL", "no_usable_setting"),
    "no_logs": ("ERROR", "no_logs"),
    "format_not_recognised": ("ERROR", "format_not_recognised"),
}


def _ladder_logs(name: str, root: Path) -> dict[date, Day] | None:
    """The logs for one rung of the ladder; None when there is nothing to compare."""
    if name == "real_drop":
        plans = _uniform(ALTERNATING, DROPPED)
    elif name == "no_drop":
        plans = _uniform(ALTERNATING, HELD, edits=(False,) * 10)
    elif name == "not_enough_evidence":
        plans = _uniform(SPREAD, MIDDLE)
    elif name == "streaky_days":
        plans = _uniform(RISING, MIDDLE)
    elif name == "too_few_days":
        plans = _uniform(ALTERNATING, HELD[:4], after_days=AFTER_DAYS[1:])
    elif name == "no_usable_setting":
        write_claude(root, _uniform(ALTERNATING, HELD), setting=Setting(CLAUDE_MODEL, None))
        return None
    elif name == "no_logs":
        (root / PROJECT_DIR).mkdir(parents=True, exist_ok=True)
        return None
    else:
        _write_lines(
            root / PROJECT_DIR / "01.jsonl",
            [
                {"type": "mode", "mode": "plan", "timestamp": _at(NEWEST)},
                {"type": "queue-operation", "timestamp": _at(NEWEST)},
                {"type": "api-request-blob", "timestamp": _at(NEWEST)},
            ],
        )
        return None
    write_claude(root, plans)
    return plans


@pytest.mark.parametrize("name", sorted(LADDER))
def test_each_result_and_reason_of_the_ladder(tmp_path: Path, name: str) -> None:
    result, reason = LADDER[name]
    root = tmp_path / "claude"
    root.mkdir()
    plans = _ladder_logs(name, root)
    outcome = _run(tmp_path, _args("claude-code", claude=root))

    tool = outcome.tool()
    assert (tool["result"], tool["reason"]) == (result, reason)
    assert outcome.code == EXIT[result]
    assert F4[result] in outcome.lines
    _block(outcome, REASONS.get(reason, NO_LOGS_REASON["claude-code"]))
    assert outcome.err == ""
    # F8 is left out when no measure was tested, and printed otherwise.
    tested = [measure for measure in tool["measures"] if measure["finding"] != "too_few_days"]
    assert ("Streak check:" in outcome.out) is bool(tested)
    if plans is not None:
        _check(outcome, "claude-code", plans)


def test_a_measure_without_enough_days_does_not_block_a_real_drop(tmp_path: Path) -> None:
    """Contract step 5: REAL DROP when any finding is `real_drop`, whatever the others are."""
    plans = _uniform(ALTERNATING, DROPPED)
    outcome = _claude_run(tmp_path, plans)
    tool = _check(outcome, "claude-code", plans)
    findings = {measure["id"]: measure["finding"] for measure in tool["measures"]}
    assert findings["reasoning_tokens"] == "real_drop"
    assert findings["edit_failure_share"] == "too_few_days"
    assert tool["result"] == "REAL_DROP"
    assert outcome.code == 1


def _streaky_plans(*, after_zeros: int, edits: tuple[bool, ...] = ()) -> dict[date, Day]:
    """Monotone before-days for the token measure, so its before-days come in streaks.

    With ten zero counts on each after-day the no-reasoning share rises from 0 to 1/2, which on
    its own is a real drop; with none it stays 0, which on its own is a no-drop.
    """
    plans = {
        day: Day(counts=(value,) * 20, edits=edits)
        for day, value in zip(BEFORE_DAYS, RISING, strict=True)
    }
    plans.update(
        {
            day: Day(counts=(value,) * (20 - after_zeros) + (0,) * after_zeros, edits=edits)
            for day, value in zip(AFTER_DAYS, MIDDLE, strict=True)
        }
    )
    return plans


def test_a_streaky_measure_stops_a_real_drop_and_marks_the_others_not_used(
    tmp_path: Path,
) -> None:
    """Contract step 5: `streaky_days` is decided before REAL DROP, and the record keeps both."""
    plans = _streaky_plans(after_zeros=10)
    root = tmp_path / "claude"
    write_claude(root, plans)
    outcome = _run(tmp_path, _args("claude-code", claude=root), outputs=("markdown", "html"))
    tool = _check(outcome, "claude-code", plans)
    assert (tool["result"], tool["reason"]) == ("CANNOT_TELL", "streaky_days")
    assert outcome.code == 2
    tokens, share, edits = tool["measures"]
    assert [tokens["finding"], share["finding"], edits["finding"]] == [
        "streaky",
        "real_drop",
        "too_few_days",
    ]
    # The stopped measure keeps the two fields its own finding fills.
    assert share["p_streak"] is not None and share["p_real"] is not None
    assert share["u_none"] is None and share["p_none"] is None
    _block(outcome, REASONS["streaky_days"])
    # The table marks it as not used; the measure without enough days keeps its own text.
    assert _row_finding(tokens, "streaky_days") == "days come in streaks"
    assert _row_finding(share, "streaky_days") == "not used"
    assert _row_finding(edits, "streaky_days") == "too few days"
    for measure in tool["measures"]:
        _says(outcome.out, _row_finding(measure, tool["reason"]))
    assert "real drop" not in outcome.out
    _says(outcome.text("markdown"), "not used")
    assert "real drop" not in outcome.text("markdown")
    _says(outcome.text("html"), "not used")


def test_a_streaky_measure_also_stops_a_no_drop(tmp_path: Path) -> None:
    plans = _streaky_plans(after_zeros=0, edits=(False,) * 10)
    outcome = _claude_run(tmp_path, plans)
    tool = _check(outcome, "claude-code", plans)
    assert (tool["result"], tool["reason"]) == ("CANNOT_TELL", "streaky_days")
    assert outcome.code == 2
    findings = [measure["finding"] for measure in tool["measures"]]
    assert findings == ["streaky", "no_drop", "no_drop"]
    # Both no-drops keep all four test fields in the record and show `not used` in the table.
    for measure in tool["measures"][1:]:
        assert all(measure[name] is not None for name in TEST_FIELDS)
        assert _row_finding(measure, "streaky_days") == "not used"
    _says(outcome.out, "not used")
    assert "no drop (margin" not in outcome.out
    assert "RESULT: CANNOT TELL" in outcome.lines


def test_a_real_drop_beside_a_cannot_tell_exits_1(tmp_path: Path) -> None:
    claude = tmp_path / "claude"
    codex = tmp_path / "codex"
    claude_plans = _uniform(ALTERNATING, DROPPED)
    codex_plans = _uniform(ALTERNATING, HELD[:4], after_days=AFTER_DAYS[1:])
    write_claude(claude, claude_plans)
    write_codex(codex, codex_plans)
    outcome = _run(tmp_path, _args("both", claude=claude, codex=codex))

    assert [tool["tool"] for tool in outcome.tools()] == ["claude-code", "codex"]
    assert outcome.tool(0)["result"] == "REAL_DROP"
    assert (outcome.tool(1)["result"], outcome.tool(1)["reason"]) == ("CANNOT_TELL", "too_few_days")
    assert outcome.code == 1
    _check(outcome, "claude-code", claude_plans)
    _check(outcome, "codex", codex_plans)


def test_an_error_beside_a_result_leaves_the_exit_code_to_the_result(tmp_path: Path) -> None:
    claude = tmp_path / "claude"
    claude.mkdir()
    codex = tmp_path / "codex"
    write_codex(codex, _codex_no_drop())
    outcome = _run(tmp_path, _args("both", claude=claude, codex=codex))

    assert (outcome.tool(0)["result"], outcome.tool(0)["reason"]) == ("ERROR", "no_logs")
    assert outcome.tool(1)["result"] == "NO_DROP"
    assert outcome.code == 0
    # An ERROR block is the tool name, F4 and the reason; F10 prints once, for the tool that
    # has a result (record 0016, text layout items 2 and 3).
    assert TOOL_NAMES["claude-code"] in outcome.lines
    _block(outcome, NO_LOGS_REASON["claude-code"])
    _run_of(outcome, F10_LINES)


def test_with_no_log_root_at_all_both_tools_are_requested_and_error(tmp_path: Path) -> None:
    """Record 0016: `--tool auto` with neither root present requests both, so the code is 3."""
    outcome = _run(tmp_path, ["--tool", "auto", "--utc"])
    assert [tool["result"] for tool in outcome.tools()] == ["ERROR", "ERROR"]
    assert [tool["reason"] for tool in outcome.tools()] == ["no_logs", "no_logs"]
    assert outcome.code == 3
    _block(outcome, NO_LOGS_REASON["claude-code"], NO_LOGS_REASON["codex"])
    assert [tool["split_date"] for tool in outcome.tools()] == [None, None]
    # F10 belongs to tools that have a result, and there is none.
    assert F10_FIRST_SENTENCE not in _flat(outcome.out)


def test_auto_requests_only_the_tool_whose_root_exists(tmp_path: Path) -> None:
    root = tmp_path / "claude"
    write_claude(root, _uniform(ALTERNATING, DROPPED))
    outcome = _run(tmp_path, ["--tool", "auto", "--utc", "--claude-dir", str(root)])
    assert [tool["tool"] for tool in outcome.tools()] == ["claude-code"]


# --- 2. the numbers: every rational against brute-force enumeration --------------------------
# Contract, "The tests". A before-day of 5 tokens must move to `(3/4) * 5 = 15/4`: with
# after-days of 4 tokens the strict count is 40, and 30 if the margin were subtracted instead.
# Day values tie within and across the periods.

NUMBERS_BEFORE = tuple(
    (5,) * 20 + (0,) * 2 if index % 2 == 0 else (20,) * 20 + (0,) * 5 for index in range(10)
)
NUMBERS_AFTER = tuple(((4,) * 20 if index < 2 else (20,) * 20) + (0,) * 3 for index in range(5))


def _numbers_plans() -> dict[date, Day]:
    plans = {day: Day(counts=NUMBERS_BEFORE[i]) for i, day in enumerate(BEFORE_DAYS)}
    plans.update({day: Day(counts=NUMBERS_AFTER[i]) for i, day in enumerate(AFTER_DAYS)})
    return plans


def test_the_rationals_of_the_record_equal_brute_force_enumeration(tmp_path: Path) -> None:
    plans = _numbers_plans()
    outcome = _claude_run(tmp_path, plans)
    tool = _check(outcome, "claude-code", plans)
    tokens, share, edits = tool["measures"]

    # The day values the logs plant, with ties and an even number of counts per day.
    assert [row["value"] for row in tokens["before_days"]] == ["5/1", "20/1"] * 5
    assert [row["value"] for row in tokens["after_days"]] == ["4/1", "4/1", "20/1", "20/1", "20/1"]
    assert [row["count"] for row in tokens["before_days"]] == [20] * 10
    assert tokens["median_before"] == _rational(Fraction(25, 2))
    assert tokens["median_after"] == "20/1"
    # The margin move is multiplicative and exact: 15/4 < 4, so both 4-token days count.
    assert tokens["u_none"] == 40
    assert tokens["p_none"] == _rational(_g_tail(10, 5, 40))
    assert tokens["p_streak"] == "1/1"
    assert tokens["p_real"] == _rational(
        _p_real(
            [Fraction(value) for value in (5, 20) * 5],
            [Fraction(4), Fraction(4), Fraction(20), Fraction(20), Fraction(20)],
        )
    )

    # The higher-is-worse measure: exact rationals with three different denominators.
    assert [row["value"] for row in share["before_days"]] == ["1/11", "1/5"] * 5
    assert [row["value"] for row in share["after_days"]] == ["3/23"] * 5
    assert [row["count"] for row in share["before_days"]] == [22, 25] * 5
    assert share["median_before"] == _rational((Fraction(1, 11) + Fraction(1, 5)) / 2)
    assert share["u_none"] == 50
    assert share["p_none"] == _rational(_g_tail(10, 5, 50))
    assert edits["finding"] == "too_few_days"


def _codex_no_drop() -> dict[date, Day]:
    """Codex logs whose `v*` is 5 only when both periods are counted.

    Before-days hold fifteen 5s and five 9s, after-days twenty 9s: 150 of each over the window,
    so the tie goes to the smaller count, 5, and the repeated-value share falls from 3/4 to 0.
    From the after period alone `v*` would be 9, the share would rise from 1/4 to 1, and the
    result would be REAL DROP instead of NO DROP.
    """
    return {
        **{day: Day(counts=(5,) * 15 + (9,) * 5) for day in BEFORE_DAYS},
        **{day: Day(counts=(9,) * 20) for day in AFTER_DAYS},
    }


def test_the_repeated_value_reference_uses_both_periods_and_ties_to_the_smallest(
    tmp_path: Path,
) -> None:
    plans = _codex_no_drop()
    outcome = _codex_run(tmp_path, plans)
    tool = _check(outcome, "codex", plans)
    assert [measure["id"] for measure in tool["measures"]] == list(TOOL_MEASURES["codex"])
    tokens, share, repeated = tool["measures"]

    assert _vstar(plans, [*BEFORE_DAYS, *AFTER_DAYS]) == 5
    assert [row["value"] for row in repeated["before_days"]] == ["3/4"] * 10
    assert [row["value"] for row in repeated["after_days"]] == ["0/1"] * 5
    assert repeated["u_none"] == 50
    assert repeated["p_none"] == _rational(_g_tail(10, 5, 50))
    # A before-day of 5 tokens moves to 15/4, which is below every after-day of 9.
    assert tokens["before_days"][0]["value"] == "5/1"
    assert tokens["u_none"] == 50
    assert share["median_before"] == "0/1"
    assert tool["result"] == "NO_DROP"
    assert outcome.code == 0


# --- 3. measures and usable days -------------------------------------------------------------
# Contract, "Measures"; record 0016, "Record model" (`DayValue.count`).

BOUNDARY_EXTRA = (date(2026, 10, 16), date(2026, 10, 17))


def _boundary_plans() -> dict[date, Day]:
    """Days at the thresholds: 19 and 20 known counts, 9 and 10 positive, 9 and 10 edits."""
    plans: dict[date, Day] = {
        BOUNDARY_EXTRA[0]: Day(counts=(7,) * 9 + (0,) * 10, edits=(False,) * 9),
        BOUNDARY_EXTRA[1]: Day(counts=(7,) * 9 + (0,) * 11, edits=(False,) * 10),
    }
    for day in (*BEFORE_DAYS, *AFTER_DAYS):
        plans[day] = Day(counts=(7,) * 10 + (0,) * 10, edits=(False,) * 10)
    return plans


def test_the_usable_day_thresholds_at_the_boundary(tmp_path: Path) -> None:
    plans = _boundary_plans()
    outcome = _claude_run(tmp_path, plans)
    tool = _check(outcome, "claude-code", plans)
    tokens, share, edits = tool["measures"]

    # 19 known counts and 9 positive counts are each one short; 20 and 10 are enough.
    assert [row["day"] for row in tokens["before_days"]] == [day.isoformat() for day in BEFORE_DAYS]
    assert [row["count"] for row in tokens["before_days"]] == [10] * 10
    assert [row["value"] for row in tokens["before_days"]] == ["7/1"] * 10
    # 20 known counts are enough for the share even with only 9 positive, so that measure has
    # one more usable before-day than the token measure: the rule is per measure.
    assert len(share["before_days"]) == 11
    assert share["before_days"][0]["day"] == BOUNDARY_EXTRA[1].isoformat()
    assert share["before_days"][0]["value"] == _rational(Fraction(11, 20))
    assert share["before_days"][0]["count"] == 20
    # 9 edit results are one short, 10 are enough.
    assert len(edits["before_days"]) == 11
    assert BOUNDARY_EXTRA[0].isoformat() not in [row["day"] for row in edits["before_days"]]
    assert all(row["count"] == 10 for row in edits["before_days"])


def test_unknown_reasoning_counts_are_never_counted_as_zero(tmp_path: Path) -> None:
    base = _uniform(ALTERNATING, HELD)
    plans = {day: Day(counts=plan.counts + (None,) * 5) for day, plan in base.items()}
    outcome = _claude_run(tmp_path, plans)
    tool = _check(outcome, "claude-code", plans)
    share = tool["measures"][1]
    assert all(row["value"] == "0/1" for row in share["before_days"])
    assert all(row["count"] == 20 for row in share["before_days"])
    assert tool["counters"]["responses_without_reasoning"] == 5 * 15


def test_an_after_period_of_zero_counts_leaves_the_token_measure_untested(tmp_path: Path) -> None:
    """Contract, "What the method cannot see": such a period has no usable day for tokens."""
    plans: dict[date, Day] = {day: Day(counts=(7,) * 10 + (0,) * 10) for day in BEFORE_DAYS}
    plans.update({day: Day(counts=(0,) * 20) for day in AFTER_DAYS})
    outcome = _claude_run(tmp_path, plans)
    tool = _check(outcome, "claude-code", plans)
    tokens, share, _ = tool["measures"]
    assert tokens["finding"] == "too_few_days"
    assert tokens["after_days"] == []
    assert tokens["median_after"] is None
    assert [row["value"] for row in share["after_days"]] == ["1/1"] * 5
    assert tool["result"] != "NO_DROP"


def test_permission_denials_and_other_tools_are_left_out_of_the_edit_share(
    tmp_path: Path,
) -> None:
    plans = {
        day: Day(counts=(100,) * 20, edits=(False,) * 10, denied=2, bash=1)
        for day in (*BEFORE_DAYS, *AFTER_DAYS)
    }
    outcome = _claude_run(tmp_path, plans)
    tool = _check(outcome, "claude-code", plans)
    edits = tool["measures"][2]
    assert all(row["count"] == 10 and row["value"] == "0/1" for row in edits["before_days"])
    assert tool["counters"]["edits_denied"] == 2 * 15
    assert tool["counters"]["edits_unmatched"] == 0


def test_unmatched_edit_results_are_counted_and_left_out(tmp_path: Path) -> None:
    plans = {
        day: Day(counts=(100,) * 20, edits=(False,) * 10, unmatched=2)
        for day in (*BEFORE_DAYS, *AFTER_DAYS)
    }
    outcome = _claude_run(tmp_path, plans)
    tool = _check(outcome, "claude-code", plans)
    edits = tool["measures"][2]
    assert all(row["count"] == 10 and row["value"] == "0/1" for row in edits["before_days"])
    assert tool["counters"]["edits_unmatched"] == 2 * 15


def test_an_edit_takes_the_setting_of_the_response_that_called_it(tmp_path: Path) -> None:
    """Contract, "What is compared": a result takes the setting of the call it answers."""
    plans = {
        day: Day(
            counts=(100,) * 20,
            edits=(False,) * 10,
            other=(100,) * 5,
            other_edits=(True,) * 10,
        )
        for day in (*BEFORE_DAYS, *AFTER_DAYS)
    }
    outcome = _claude_run(tmp_path, plans)
    tool = _check(outcome, "claude-code", plans)
    edits = tool["measures"][2]
    # The ten failures were called by the other setting: neither counted nor failed here.
    assert all(row["count"] == 10 and row["value"] == "0/1" for row in edits["before_days"])
    assert tool["model"] == CLAUDE_MODEL
    assert tool["other_settings"] == 1


# --- 4. what is compared ---------------------------------------------------------------------
# Contract, "What is compared"; record 0016 items 3 to 5 and the command line.


def test_sub_agent_responses_are_left_out_and_only_counted_as_context(tmp_path: Path) -> None:
    plans = {
        day: Day(counts=(100,) * 20, sidechain=(1,) * 5) for day in (*BEFORE_DAYS, *AFTER_DAYS)
    }
    outcome = _claude_run(tmp_path, plans)
    tool = _check(outcome, "claude-code", plans)
    tokens = tool["measures"][0]
    assert all(row["count"] == 20 and row["value"] == "100/1" for row in tokens["before_days"])
    assert tool["context"]["subagent_share_before"] == _rational(Fraction(1, 5))
    assert tool["context"]["subagent_share_after"] == _rational(Fraction(1, 5))
    # `responses` includes sub-agent responses (record 0016, "Fixed texts", last paragraph).
    assert tool["counters"]["responses"] == 25 * 15


def test_the_working_directory_counts_are_per_period(tmp_path: Path) -> None:
    """Record 0016 item 6: a Claude Code line's working directory is its top-level `cwd`."""
    plans = _uniform(ALTERNATING, DROPPED)
    root = tmp_path / "claude"
    kept = {day: plans[day] for day in (*BEFORE_DAYS, *AFTER_DAYS[:3])}
    write_claude(root, kept, session="01")
    write_claude(
        root,
        {day: plans[day] for day in AFTER_DAYS[3:]},
        session="02",
        prefix="w",
        cwd="/work/second",
    )
    outcome = _run(tmp_path, _args("claude-code", claude=root))
    context = _check(outcome, "claude-code", plans)["context"]
    assert context["workdirs_before"] == 1
    assert context["workdirs_after"] == 2


def test_project_keeps_only_the_claude_code_responses_inside_it(tmp_path: Path) -> None:
    plans = _uniform(ALTERNATING, DROPPED)
    root = tmp_path / "claude"
    write_claude(root, {day: plans[day] for day in BEFORE_DAYS}, session="01")
    # A directory below the project is kept as well.
    write_claude(
        root,
        {day: plans[day] for day in AFTER_DAYS},
        session="02",
        prefix="b",
        cwd=f"{WORKDIR}/below",
    )
    write_claude(
        root,
        {day: Day(counts=(1,) * 20) for day in (*BEFORE_DAYS, *AFTER_DAYS)},
        session="03",
        prefix="z",
        cwd="/elsewhere/other",
    )
    outcome = _run(tmp_path, _args("claude-code", claude=root, extra=("--project", WORKDIR)))
    assert outcome.body is not None
    assert outcome.body["project_filtered"] is True
    tool = _check(outcome, "claude-code", plans)
    # Without the filter every day would hold 40 counts and a median of 91/2.
    assert all(row["count"] == 20 for row in tool["measures"][0]["before_days"])
    assert tool["context"]["workdirs_before"] == 1
    assert tool["context"]["workdirs_after"] == 1
    # `files_outside_project` is used for Codex only: a Claude Code line is filtered on its own
    # working directory, so no file is set aside.
    assert tool["counters"]["files_outside_project"] == 0
    assert tool["counters"]["files_read"] == 3


def test_the_client_version_counts_are_per_period(tmp_path: Path) -> None:
    plans: dict[date, Day] = {day: Day(counts=(100,) * 20) for day in BEFORE_DAYS}
    plans.update({day: Day(counts=(100,) * 20, version="3.0.1") for day in AFTER_DAYS})
    plans[AFTER_DAYS[0]] = Day(counts=(100,) * 20)
    outcome = _claude_run(tmp_path, plans)
    context = _check(outcome, "claude-code", plans)["context"]
    assert context["client_versions_before"] == 1
    assert context["client_versions_after"] == 2
    assert context["client_versions_both"] == 1


def test_the_setting_is_chosen_by_pooled_counts_not_by_the_after_period(tmp_path: Path) -> None:
    """Record 0016 item 3, review finding 1: the after period alone must not choose."""
    base = _codex_no_drop()
    plans = {
        **base,
        **{day: Day(counts=base[day].counts, other=(1,) * 25) for day in AFTER_DAYS},
    }
    outcome = _codex_run(tmp_path, plans)
    tool = _check(outcome, "codex", plans)
    assert tool["model"] == CODEX_MODEL
    assert tool["other_settings"] == 1
    # The other setting has more responses after the split (125 to 100) and none before it:
    # chosen, it would give CANNOT TELL with no before-day.
    assert tool["result"] == "NO_DROP"


def test_a_tie_between_settings_goes_to_the_first_pair_as_text(tmp_path: Path) -> None:
    plans = {
        day: Day(counts=(value,) * 20, other=(1000,) * 20)
        for day, value in zip((*BEFORE_DAYS, *AFTER_DAYS), (*ALTERNATING, *DROPPED), strict=True)
    }
    outcome = _claude_run(tmp_path, plans)
    tool = _check(outcome, "claude-code", plans)
    # Both settings have 300 responses over the window; ("claude-opus-...", "high") sorts first.
    assert tool["model"] == CLAUDE_MODEL
    assert tool["effort"] == "high"
    assert tool["other_settings"] == 1
    assert tool["result"] == "REAL_DROP"


def test_a_tie_goes_by_the_raw_pair_even_when_the_rendered_names_reorder(tmp_path: Path) -> None:
    """The tie is broken on the raw ids: `acme-...` wins, though `model-1` sorts after `gpt-5`."""
    base = _codex_no_drop()
    plans = {day: Day(counts=base[day].counts, other=(1,) * 20) for day in base}
    outcome = _codex_run(
        tmp_path,
        plans,
        setting=Setting(CANARY_MODEL_A, "high"),
        other=Setting(CODEX_MODEL, "high"),
    )
    tool = _check(outcome, "codex", plans)
    assert tool["model"] == "model-1"
    assert tool["other_settings"] == 1
    assert tool["measures"][0]["before_days"][0]["value"] == "5/1"
    for canary in CANARIES:
        assert canary not in outcome.out


def test_unknown_efforts_are_numbered_among_themselves_and_never_merged(tmp_path: Path) -> None:
    """Record 0016 item 6: rejected names are numbered in raw text order, unknown ones only."""
    root = tmp_path / "claude"
    plans = {
        day: Day(counts=(value,) * 20, other=(1000,) * 10)
        for day, value in zip((*BEFORE_DAYS, *AFTER_DAYS), (*ALTERNATING, *DROPPED), strict=True)
    }
    write_claude(
        root,
        plans,
        session="01",
        setting=Setting(CLAUDE_MODEL, CANARY_EFFORT_1),
        other=Setting(CLAUDE_MODEL, CANARY_EFFORT_2),
    )
    # A third setting whose effort the grammar accepts, which must take no number.
    write_claude(
        root,
        {day: Day(counts=(1,) * 5) for day in (*BEFORE_DAYS, *AFTER_DAYS)},
        session="02",
        prefix="h",
        setting=Setting(CLAUDE_MODEL, "high"),
    )
    outcome = _run(tmp_path, _args("claude-code", claude=root))
    tool = _check(outcome, "claude-code", plans)
    assert tool["model"] == CLAUDE_MODEL
    assert tool["effort"] == "effort-1"
    assert tool["other_settings"] == 2
    # Merged with the other unknown effort, the days would mix in the 1000-token responses.
    assert all(row["count"] == 20 for row in tool["measures"][0]["before_days"])
    assert tool["result"] == "REAL_DROP"
    for canary in CANARIES:
        assert canary not in outcome.out
    assert F14.format(2) in outcome.lines


def test_model_and_effort_select_a_setting_by_rendered_name(tmp_path: Path) -> None:
    """The second setting carries its effort on `perTurnEffort`; `--effort` still reaches it."""
    plans = {
        day: Day(counts=(200,) * 20, edits=(False,) * 10, other=(other,) * 20)
        for day, other in zip((*BEFORE_DAYS, *AFTER_DAYS), (*ALTERNATING, *DROPPED), strict=True)
    }
    root = tmp_path / "claude"
    write_claude(
        root,
        plans,
        setting=Setting(CLAUDE_MODEL, "high"),
        other=Setting(CLAUDE_MODEL, "medium", key="perTurnEffort"),
    )
    # Both settings have 300 responses; ("...", "high") sorts before ("...", "medium").
    default = _run(tmp_path, _args("claude-code", claude=root), stem="a")
    assert default.tool()["effort"] == "high"
    assert default.tool()["result"] == "NO_DROP"

    picked = _run(
        tmp_path, _args("claude-code", claude=root, extra=("--effort", "medium")), stem="b"
    )
    assert (picked.tool()["model"], picked.tool()["effort"]) == (CLAUDE_MODEL, "medium")
    assert picked.tool()["result"] == "REAL_DROP"
    named = _run(
        tmp_path,
        _args("claude-code", claude=root, extra=("--model", CLAUDE_MODEL, "--effort", "medium")),
        stem="c",
    )
    assert named.tool()["measures"] == picked.tool()["measures"]


def test_a_named_model_that_does_not_exist_gives_no_usable_setting(tmp_path: Path) -> None:
    outcome = _claude_run(
        tmp_path, _uniform(ALTERNATING, DROPPED), extra=("--model", "claude-haiku-4")
    )
    tool = outcome.tool()
    assert (tool["result"], tool["reason"]) == ("CANNOT_TELL", "no_usable_setting")
    assert outcome.code == 2
    _block(outcome, REASONS["no_usable_setting"])


def test_since_replaces_the_split_date(tmp_path: Path) -> None:
    plans = _uniform(ALTERNATING, DROPPED)
    outcome = _claude_run(tmp_path, plans, extra=("--since", "2026-11-01"))
    tool = _check(outcome, "claude-code", plans, split=date(2026, 11, 1))
    assert tool["split_date"] == "2026-11-01"
    assert tool["after"] == {"first_day": "2026-11-01", "last_day": "2026-11-10"}
    assert tool["before"] == {"first_day": "2026-08-09", "last_day": "2026-10-31"}
    assert "after   2026-11-01 to 2026-11-10   split 2026-11-01" in outcome.lines


@pytest.mark.parametrize(
    ("flags", "message"),
    [
        (("--since", "2026-11-32"), "malformed"),
        (("--since", "yesterday"), "malformed"),
        (("--since", "2026-08-18"), "early"),
        (("--bogus",), "usage"),
        (("--tool", "bogus"), "usage"),
    ],
)
def test_a_usage_error_prints_one_sentence_and_writes_nothing(
    tmp_path: Path, flags: tuple[str, ...], message: str
) -> None:
    root = tmp_path / "claude"
    write_claude(root, _uniform(ALTERNATING, DROPPED))
    outcome = _run(
        tmp_path,
        _args("claude-code", claude=root, extra=flags),
        outputs=("markdown", "html"),
    )
    assert outcome.code == 3
    assert outcome.out == ""
    # The sentence alone, with no prefix, and nothing else on standard error.
    assert outcome.err.splitlines() == [USAGE_ERRORS[message]]
    assert not outcome.json_path.exists()
    assert not any(path.exists() for path in outcome.extra.values())


def test_a_since_83_days_before_the_newest_day_is_accepted(tmp_path: Path) -> None:
    outcome = _claude_run(tmp_path, _uniform(ALTERNATING, DROPPED), extra=("--since", "2026-08-19"))
    tool = outcome.tool()
    assert tool["split_date"] == "2026-08-19"
    assert (tool["result"], tool["reason"]) == ("CANNOT_TELL", "too_few_days")
    assert outcome.code == 2


def test_a_since_later_than_the_newest_day_leaves_no_after_days(tmp_path: Path) -> None:
    outcome = _claude_run(tmp_path, _uniform(ALTERNATING, DROPPED), extra=("--since", "2026-11-11"))
    tool = outcome.tool()
    assert tool["split_date"] == "2026-11-11"
    assert tool["after"] is None
    assert all(measure["after_days"] == [] for measure in tool["measures"])
    assert all(measure["finding"] == "too_few_days" for measure in tool["measures"])
    assert (tool["result"], tool["reason"]) == ("CANNOT_TELL", "too_few_days")
    assert "after   no days   split 2026-11-11" in outcome.lines


def test_project_keeps_only_the_sessions_inside_it(tmp_path: Path) -> None:
    root = tmp_path / "codex"
    plans = _codex_no_drop()
    write_codex(root, {day: plans[day] for day in BEFORE_DAYS})
    # The after-days sit in a directory below the project, which `--project` also keeps.
    write_codex(root, {day: plans[day] for day in AFTER_DAYS}, cwd=f"{WORKDIR}/below")
    write_codex(
        root,
        {day: Day(counts=(1,) * 20) for day in (*BEFORE_DAYS, *AFTER_DAYS)},
        cwd="/elsewhere/other",
        name="rollout-outside",
    )
    outcome = _run(tmp_path, _args("codex", codex=root, extra=("--project", WORKDIR)))
    assert outcome.body is not None
    assert outcome.body["project_filtered"] is True
    tool = _check(outcome, "codex", plans)
    assert tool["counters"]["files_outside_project"] == 15
    # `files_read` counts every file opened, a file left after its first line included.
    assert tool["counters"]["files_read"] == 30
    # `lines` counts every line read, and for a file outside the project its first line only:
    # fifteen kept files of 22 lines each, plus one line from each of the fifteen others.
    assert tool["counters"]["lines"] == 15 * 22 + 15
    assert tool["counters"]["responses"] == 300
    assert tool["result"] == "NO_DROP"


def test_utc_and_the_local_offset_of_now_pick_different_days(tmp_path: Path) -> None:
    """The run reads one offset: `--utc` uses 0, otherwise the offset of `now`."""
    local = datetime(2026, 11, 12, 0, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    base = _uniform(ALTERNATING, DROPPED)
    late = _assistant(mid="late-1", when=_at(NEWEST, 20, 0), setting=Setting(), reasoning=None)
    plans = {**base, NEWEST: Day(counts=base[NEWEST].counts, extra=(late,))}
    root = tmp_path / "claude"
    write_claude(root, plans)
    scope = "Claude Code · claude-opus-4-20250514 · effort high · main thread · days at UTC"

    at_utc = _run(tmp_path, _args("claude-code", claude=root), now=local, stem="utc")
    assert at_utc.body is not None
    assert at_utc.body["utc_offset_minutes"] == 0
    assert at_utc.tool()["split_date"] == SPLIT.isoformat()
    assert at_utc.tool()["after"] == AFTER_PERIOD
    assert f"{scope}+00:00" in at_utc.lines

    # At +05:30 the 20:00Z response falls on the next day, which becomes the newest day.
    shifted = _run(tmp_path, _args("claude-code", claude=root, utc=False), now=local, stem="local")
    assert shifted.body is not None
    assert shifted.body["utc_offset_minutes"] == 330
    assert shifted.tool()["split_date"] == "2026-10-29"
    assert shifted.tool()["after"] == {"first_day": "2026-10-29", "last_day": "2026-11-11"}
    assert f"{scope}+05:30" in shifted.lines


def test_a_response_found_in_two_files_is_counted_once(tmp_path: Path) -> None:
    """The identity is the message id for Claude Code; the first assembled copy is kept."""
    root = tmp_path / "claude"
    plans = _uniform(ALTERNATING, DROPPED)
    write_claude(root, plans, session="01")
    write_claude(root, {NEWEST: plans[NEWEST]}, session="02")
    outcome = _run(tmp_path, _args("claude-code", claude=root))
    tool = _check(outcome, "claude-code", plans)
    assert tool["counters"]["files_read"] == 2
    assert tool["counters"]["responses_duplicate"] == 20
    assert tool["counters"]["responses"] == 300


def test_a_codex_response_found_in_two_files_is_counted_once(tmp_path: Path) -> None:
    """For Codex the identity is the session id, the event time and the cumulative usage."""
    root = tmp_path / "codex"
    plans = _codex_no_drop()
    write_codex(root, plans)
    write_codex(root, {NEWEST: plans[NEWEST]}, name="rollout-copy")
    outcome = _run(tmp_path, _args("codex", codex=root))
    tool = _check(outcome, "codex", plans)
    assert tool["counters"]["files_read"] == 16
    assert tool["counters"]["responses_duplicate"] == 20
    assert tool["counters"]["responses"] == 300


def test_future_and_zoneless_records_are_left_out_and_counted(tmp_path: Path) -> None:
    base = _uniform(ALTERNATING, DROPPED)
    day = AFTER_DAYS[3]
    strays = (
        _assistant(mid="far-1", when=_at(date(2026, 11, 20)), setting=Setting(), reasoning=5),
        _assistant(mid="naive-1", when=_at(day, zone=""), setting=Setting(), reasoning=5),
        _assistant(
            mid="apierr-1",
            when=_at(day, 8, 0),
            setting=Setting(),
            reasoning=5,
            extra={"isApiErrorMessage": True},
        ),
    )
    plans = {**base, day: Day(counts=base[day].counts, extra=strays)}
    outcome = _claude_run(tmp_path, plans)
    tool = _check(outcome, "claude-code", plans)
    assert tool["counters"]["records_in_future"] == 1
    assert tool["counters"]["records_without_timezone"] == 1
    # A line carrying `isApiErrorMessage` counts as a line of an unused type.
    assert tool["counters"]["lines_unknown_type"] == 1
    assert tool["counters"]["lines"] == 300 + 3
    # None of the three reaches a day: the newest day, the split and every day count stand.
    assert tool["split_date"] == SPLIT.isoformat()
    assert all(row["count"] == 20 for row in tool["measures"][0]["after_days"])
    assert F16.format(1) in outcome.lines


# --- 5. privacy ------------------------------------------------------------------------------
# Record 0016, "Privacy is a tested property": no string read from a log may reach an output, a
# warning, an exception or a record, except a model or effort name the closed grammar admits.

DATE_SHAPE = re.compile(r"\d{4}-\d{2}-\d{2}")
RATIONAL_SHAPE = re.compile(r"\d+/\d+")
DIGEST_SHAPE = re.compile(r"[0-9a-f]{64}")
VERSION_SHAPE = re.compile(r"\d+\.\d+\.\d+[0-9A-Za-z.+-]*")
CLOSED_NAMES = (
    {"arci-logs/1", "claude-code", "codex", "lower", "higher", "no_logs"}
    | set(F4)
    | set(REASONS)
    | set(MEASURES)
    | set(FILLED)
)
RENDERED_NAMES = (
    {CLAUDE_MODEL, CLAUDE_OTHER, CODEX_MODEL, CODEX_OTHER}
    | {"minimal", "low", "medium", "high", "xhigh", "max"}
    | {f"model-{index}" for index in range(1, 8)}
    | {f"effort-{index}" for index in range(1, 8)}
)


def _canary_plans() -> dict[date, Day]:
    """A private-looking majority setting and a second one that must not be merged with it."""
    plans: dict[date, Day] = {}
    for day, value in zip((*BEFORE_DAYS, *AFTER_DAYS), (*ALTERNATING, *DROPPED), strict=True):
        plans[day] = Day(
            counts=(value,) * 20,
            edits=(False,) * 10,
            other=(1000,) * 5,
            sidechain=(1,) * 2,
            denied=1,
            unmatched=1,
            version=CANARY_VERSION,
            extra=(
                {"type": f"{CANARY_LOWER}-line", "blob": CANARY_UPPER, "timestamp": _at(day)},
                {
                    "type": "user",
                    "timestamp": _at(day, 12, 0),
                    "isSidechain": False,
                    "message": {"role": "user", "content": CANARY_PROMPT},
                },
            ),
        )
    return plans


def _canary_outcome(tmp_path: Path) -> Outcome:
    root = tmp_path / "claude"
    write_claude(
        root,
        _canary_plans(),
        session="01",
        setting=Setting(CANARY_MODEL_A, "high"),
        other=Setting(CANARY_MODEL_B, "high"),
        project=f"-canary-{CANARY_UPPER}",
        cwd=CANARY_DIR,
        text=CANARY_INPUT,
        output=CANARY_OUTPUT,
    )
    # A third rejected id (nine parts) and one the grammar accepts, which sorts before every
    # rejected one: the rejected names must still be numbered 1 and 2.
    write_claude(
        root,
        {day: Day(counts=(1,) * 3, other=(1,) * 2) for day in (*BEFORE_DAYS, *AFTER_DAYS)},
        session="02",
        prefix="t",
        setting=Setting(CANARY_MODEL_C, "high"),
        other=Setting(SMALL_MODEL, "high"),
        project=f"-canary-{CANARY_UPPER}",
        cwd=CANARY_DIR,
        text=CANARY_INPUT,
        output=CANARY_OUTPUT,
    )
    return _run(tmp_path, _args("claude-code", claude=root), outputs=("markdown", "html"))


def test_no_canary_token_reaches_any_output(tmp_path: Path) -> None:
    outcome = _canary_outcome(tmp_path)
    places = {
        "stdout": outcome.out,
        "stderr": outcome.err,
        "json": outcome.json_path.read_text(encoding="utf-8"),
        "markdown": outcome.text("markdown"),
        "html": outcome.text("html"),
    }
    for where, text in places.items():
        for canary in CANARIES:
            assert canary not in text, (where, canary)
        for part in CANARY_PARTS:
            assert part not in text, (where, part)


def test_unknown_model_ids_are_numbered_among_themselves_and_never_merged(
    tmp_path: Path,
) -> None:
    outcome = _canary_outcome(tmp_path)
    tool = outcome.tool()
    # Numbered in the text order of the raw rejected values, "acme-..." first; the accepted
    # "4o-mini" sorts before all of them and takes no number.
    assert tool["model"] == "model-1"
    assert tool["effort"] == "high"
    assert tool["other_settings"] == 3
    # Still compared, and not merged with the other unknown ids: the day values are the majority
    # setting's alone, not a mix with the other settings' responses.
    assert tool["measures"] == _expect_measures("claude-code", _canary_plans())
    assert tool["result"] == "REAL_DROP"
    assert F14.format(3) in outcome.lines


def _string_leaves(node: Any, key: str = "") -> list[tuple[str, str]]:
    if isinstance(node, str):
        return [(key, node)]
    if isinstance(node, dict):
        return [row for name, value in node.items() for row in _string_leaves(value, name)]
    if isinstance(node, list):
        return [row for value in node for row in _string_leaves(value, key)]
    return []


def test_every_string_in_the_json_is_of_an_allowed_shape(tmp_path: Path) -> None:
    """A date, a rational, a closed-list name, a rendered name or a hex digest."""
    outcome = _canary_outcome(tmp_path)
    assert outcome.body is not None
    for key, value in _string_leaves(outcome.body):
        if key == "arci_version":
            assert VERSION_SHAPE.fullmatch(value), value
            continue
        allowed = (
            value in CLOSED_NAMES
            or value in RENDERED_NAMES
            or DATE_SHAPE.fullmatch(value)
            or RATIONAL_SHAPE.fullmatch(value)
            or DIGEST_SHAPE.fullmatch(value)
        )
        assert allowed, (key, value)


# --- 6. robustness ---------------------------------------------------------------------------
# Record 0016, "Reading faults": lines that are not JSON, lines of an unused type and lines of a
# used type that lack a needed field are counted and left out; an unreadable file is counted.


def test_broken_lines_are_counted_and_never_raise(tmp_path: Path) -> None:
    good = [
        _assistant(mid="g1", when=_at(NEWEST, 6, 0), setting=Setting(), reasoning=100),
        _assistant(mid="g2", when=_at(NEWEST, 6, 1), setting=Setting(), reasoning=0),
    ]
    stripped = _assistant(mid="g3", when=_at(NEWEST, 6, 2), setting=Setting(), reasoning=1)
    del stripped["timestamp"]
    rows = [
        json.dumps(good[0]),
        json.dumps(good[1]),
        json.dumps({"type": "mode", "mode": "plan", "timestamp": _at(NEWEST)}),
        "{this is not json at all",
        json.dumps(stripped),
        json.dumps({"type": "assistant", "timestamp": _at(NEWEST, 6, 3)}),
        '{"type": "assistant", "timest',
    ]
    root = tmp_path / "claude"
    path = root / PROJECT_DIR / "01.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text("\n".join(rows), encoding="utf-8")

    outcome = _run(tmp_path, _args("claude-code", claude=root))
    counters = outcome.tool()["counters"]
    assert counters["files_read"] == 1
    assert counters["lines"] == 7
    assert counters["lines_not_json"] == 2
    assert counters["lines_unknown_type"] == 1
    assert counters["lines_lacking_field"] == 2
    assert counters["responses"] == 2
    assert F15.format(2) in outcome.lines
    assert outcome.code == 2


def test_an_unreadable_file_beside_a_readable_one(tmp_path: Path) -> None:
    root = tmp_path / "claude"
    plans = _uniform(ALTERNATING, DROPPED)
    write_claude(root, plans, session="01")
    blocked = root / PROJECT_DIR / "02.jsonl"
    _write_lines(blocked, [{"type": "mode", "timestamp": _at(NEWEST)}])
    blocked.chmod(0o000)
    if os.access(blocked, os.R_OK):
        blocked.chmod(stat.S_IRUSR | stat.S_IWUSR)
        pytest.skip("this process can read a file with no read permission")
    try:
        outcome = _run(tmp_path, _args("claude-code", claude=root))
    finally:
        blocked.chmod(stat.S_IRUSR | stat.S_IWUSR)
    tool = _check(outcome, "claude-code", plans)
    assert tool["counters"]["files_unreadable"] == 1
    assert tool["counters"]["files_read"] == 1
    assert F17.format(1) in outcome.lines


def test_a_response_spread_over_several_lines_is_one_response(tmp_path: Path) -> None:
    """L0: one response is one `message.id` in a file, with the usage of its last line."""
    lines: list[dict[str, Any]] = []
    for day, value in zip((*BEFORE_DAYS, *AFTER_DAYS), (*ALTERNATING, *DROPPED), strict=True):
        for index in range(20):
            mid = f"split-{day}-{index}"
            for hour, reasoning in ((6, None), (7, None), (8, value)):
                lines.append(
                    _assistant(
                        mid=mid,
                        when=_at(day, hour, index),
                        setting=Setting(),
                        reasoning=reasoning,
                    )
                )
    root = tmp_path / "claude"
    _write_lines(root / PROJECT_DIR / "01.jsonl", lines)
    outcome = _run(tmp_path, _args("claude-code", claude=root))
    tool = outcome.tool()
    assert tool["counters"]["responses"] == 300
    tokens = tool["measures"][0]
    assert [row["value"] for row in tokens["before_days"]] == [f"{v}/1" for v in ALTERNATING]
    assert all(row["count"] == 20 for row in tokens["before_days"])
    assert tool["result"] == "REAL_DROP"


# --- 7. the record ---------------------------------------------------------------------------
# Record 0016, "Record model". `_audit` checks the field sets, the null rules, the ascending day
# lists, the filled test fields and the seal on every run in this file.


def test_the_record_carries_the_version_of_the_header_and_a_valid_seal(tmp_path: Path) -> None:
    plans = _uniform(ALTERNATING, HELD, edits=(False,) * 10)
    outcome = _claude_run(tmp_path, plans)
    assert outcome.body is not None
    version = outcome.body["arci_version"]
    assert outcome.lines[0] == (
        f"realornoise {version} · reads local session logs · sends nothing · "
        "writes nothing unless asked"
    )
    draft = {name: value for name, value in outcome.body.items() if name != "seal"}
    assert outcome.body["seal"] == hash_record(draft)
    draft["exit_code"] = 9
    assert hash_record(draft) != outcome.body["seal"]
    assert outcome.body["utc_offset_minutes"] == 0
    assert outcome.body["project_filtered"] is False
    assert outcome.tool()["before"] == BEFORE_PERIOD
    assert outcome.tool()["after"] == AFTER_PERIOD
    assert outcome.tool()["other_settings"] == 0


@pytest.mark.parametrize("name", ["no_logs", "format_not_recognised", "no_usable_setting"])
def test_an_error_or_a_missing_setting_nulls_the_same_fields(tmp_path: Path, name: str) -> None:
    root = tmp_path / "claude"
    root.mkdir()
    _ladder_logs(name, root)
    outcome = _run(tmp_path, _args("claude-code", claude=root))
    tool = outcome.tool()
    assert tool["measures"] == []
    for name_of in ("model", "effort", "before", "after", "context", "day_table_sha256"):
        assert tool[name_of] is None, name_of
    if name == "no_usable_setting":
        # The split is kept whenever the tool has a main-thread response.
        assert tool["split_date"] == SPLIT.isoformat()
        assert tool["counters"]["responses_without_setting"] == 300
        assert tool["counters"]["responses"] == 0
    else:
        assert tool["split_date"] is None
    # No digest is made up when there is no day table.
    assert "method arci-logs/1" not in outcome.out


def test_the_day_table_digest_follows_the_day_values_and_not_the_file_order(
    tmp_path: Path,
) -> None:
    plans = _uniform(ALTERNATING, DROPPED)
    one = tmp_path / "one"
    write_claude(one, plans)
    first = _run(tmp_path, _args("claude-code", claude=one), stem="one")

    # The same days, read from two files whose path order puts the after-days first.
    two = tmp_path / "two"
    write_claude(two, {day: plans[day] for day in AFTER_DAYS}, session="01")
    write_claude(two, {day: plans[day] for day in BEFORE_DAYS}, session="02")
    second = _run(tmp_path, _args("claude-code", claude=two), stem="two")
    assert second.tool()["day_table_sha256"] == first.tool()["day_table_sha256"]
    assert second.tool()["measures"] == first.tool()["measures"]

    # One day value changed: a different digest.
    moved = {**plans, BEFORE_DAYS[0]: Day(counts=(91,) * 20)}
    three = tmp_path / "three"
    write_claude(three, moved)
    third = _run(tmp_path, _args("claude-code", claude=three), stem="three")
    assert third.tool()["day_table_sha256"] != first.tool()["day_table_sha256"]


# --- 8. the fixed texts ----------------------------------------------------------------------
# Record 0016, "Fixed texts" and the text layout. Every line of every run in this file is
# checked against the 100-character limit by `_run`.


def test_the_fixed_lines_of_a_run_with_a_result(tmp_path: Path) -> None:
    plans = _uniform(ALTERNATING, HELD, edits=(False,) * 10)
    outcome = _claude_run(tmp_path, plans)
    tool = _check(outcome, "claude-code", plans)
    lines = outcome.lines
    digest = tool["day_table_sha256"]

    assert (
        "Claude Code · claude-opus-4-20250514 · effort high · main thread · days at UTC+00:00"
        in lines
    )
    assert "before  2026-08-05 to 2026-10-27" in lines
    assert "after   2026-10-28 to 2026-11-10   split 2026-10-28" in lines
    assert "RESULT: NO DROP" in lines
    _block(outcome, REASONS["no_drop"])
    assert "Context counts; differences between the periods are not tested:" in lines
    _block(
        outcome,
        "client versions 1 before, 1 after, 1 in both · working directories 1 before, 1 after"
        " · sub-agent share 0.0% -> 0.0%",
    )
    assert "Streak check: 3 of 3 tested measures were not flagged." in lines
    assert (
        "method arci-logs/1 · exact rank tests · no random numbers · day-table digest "
        f"{digest[:12]}" in lines
    )
    _run_of(outcome, F10_LINES)
    _says(outcome.out, F10_FIRST_SENTENCE)
    _says(outcome.out, F10_THIRD_SENTENCE)
    assert F12 in lines
    assert lines[-1] == "exit 0"
    assert outcome.err == ""
    # Every notice count is zero here, so no notice prints.
    for notice in NOTICES:
        assert notice.split("{")[0] not in outcome.out
    # The table names every gating measure of this tool and no other, with its own finding.
    for measure in tool["measures"]:
        _says(outcome.out, ROW_NAMES[measure["id"]])
        _says(outcome.out, _row_finding(measure, tool["reason"]))
    assert ROW_NAMES["repeated_value_share"] not in outcome.out
    assert "not used" not in outcome.out


def test_the_streak_line_counts_the_measures_that_were_not_flagged(tmp_path: Path) -> None:
    plans = _uniform(RISING, MIDDLE)
    outcome = _claude_run(tmp_path, plans)
    tool = _check(outcome, "claude-code", plans)
    findings = {measure["id"]: measure["finding"] for measure in tool["measures"]}
    assert findings["reasoning_tokens"] == "streaky"
    assert findings["edit_failure_share"] == "too_few_days"
    # Two measures have enough days; one of them was flagged.
    assert "Streak check: 1 of 2 tested measures were not flagged." in outcome.lines
    assert (tool["result"], tool["reason"]) == ("CANNOT_TELL", "streaky_days")
    for measure in tool["measures"]:
        _says(outcome.out, _row_finding(measure, tool["reason"]))
    assert "no drop (margin" not in outcome.out
    assert outcome.lines[-1] == "exit 2"


def test_the_notice_about_other_settings(tmp_path: Path) -> None:
    plans = {
        day: Day(counts=(value,) * 20, other=(1000,) * 5)
        for day, value in zip((*BEFORE_DAYS, *AFTER_DAYS), (*ALTERNATING, *DROPPED), strict=True)
    }
    outcome = _claude_run(tmp_path, plans)
    assert outcome.tool()["other_settings"] == 1
    assert F14.format(1) in outcome.lines


def test_the_word_improved_appears_only_in_the_sentence_that_denies_it(tmp_path: Path) -> None:
    drop = _claude_run(tmp_path / "a", _uniform(ALTERNATING, DROPPED))
    assert "improved" not in drop.out
    none = _claude_run(tmp_path / "b", _uniform(ALTERNATING, HELD, edits=(False,) * 10))
    assert none.tool()["result"] == "NO_DROP"
    assert _flat(none.out).count("improved") == 1
    _block(none, REASONS["no_drop"])


@pytest.mark.parametrize(
    ("before", "after", "edits", "result"),
    [
        (ALTERNATING, DROPPED, (), "REAL_DROP"),
        (ALTERNATING, HELD, (False,) * 10, "NO_DROP"),
        (RISING, MIDDLE, (), "CANNOT_TELL"),
    ],
)
def test_the_markdown_block_closes_with_the_line_for_the_result(
    tmp_path: Path,
    before: Sequence[int],
    after: Sequence[int],
    edits: tuple[bool, ...],
    result: str,
) -> None:
    root = tmp_path / "claude"
    write_claude(root, _uniform(before, after, edits=edits))
    outcome = _run(tmp_path, _args("claude-code", claude=root), outputs=("markdown",))
    assert outcome.tool()["result"] == result
    block = outcome.text("markdown")
    _says(block, MARKDOWN_CLOSE[result])
    _says(block, MARKDOWN_BOUND)
    _says(block, "arci-logs/1, digest")
    _says(block, "Yours: uvx realornoise")
    _says(block, outcome.tool()["day_table_sha256"][:12])
    assert "**" in block
    for measure in outcome.tool()["measures"]:
        _says(block, _row_finding(measure, outcome.tool()["reason"]))
    assert ("not used" in block) is (outcome.tool()["reason"] == "streaky_days")


def test_an_error_markdown_block_holds_only_the_tool_the_result_and_the_reason(
    tmp_path: Path,
) -> None:
    root = tmp_path / "claude"
    root.mkdir()
    outcome = _run(tmp_path, _args("claude-code", claude=root), outputs=("markdown",))
    block = outcome.text("markdown")
    _says(block, NO_LOGS_REASON["claude-code"])
    assert "2.5%" not in block
    assert "uvx realornoise" not in block


def test_the_html_page_has_no_script_and_no_external_reference(tmp_path: Path) -> None:
    root = tmp_path / "claude"
    write_claude(root, _uniform(ALTERNATING, DROPPED))
    outcome = _run(tmp_path, _args("claude-code", claude=root), outputs=("html",))
    page = outcome.text("html")
    assert "<script" not in page.lower()
    assert "http://" not in page and "https://" not in page
    assert "<svg" in page.lower()
    _says(page, REASONS["real_drop"])


# --- 9. determinism --------------------------------------------------------------------------
# Contract: "No random number is drawn anywhere. The same day table gives the same result on any
# machine."


def test_two_runs_on_the_same_logs_are_byte_identical(tmp_path: Path) -> None:
    root = tmp_path / "claude"
    write_claude(root, _uniform(SPREAD, MIDDLE, edits=(False,) * 5 + (True,) * 5))
    outputs = ("markdown", "html")
    first = _run(tmp_path, _args("claude-code", claude=root), stem="one", outputs=outputs)
    second = _run(tmp_path, _args("claude-code", claude=root), stem="two", outputs=outputs)
    assert first.out == second.out
    assert first.err == second.err == ""
    assert first.code == second.code
    assert first.json_path.read_bytes() == second.json_path.read_bytes()
    for name in ("markdown", "html"):
        assert first.text(name) == second.text(name)
    # The JSON file is UTF-8, keys sorted, two-space indent, with a final newline.
    body = first.json_path.read_text(encoding="utf-8")
    assert body.endswith("\n")
    assert body == json.dumps(json.loads(body), indent=2, sort_keys=True) + "\n"
