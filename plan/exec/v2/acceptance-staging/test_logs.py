"""`arci logs` / `realornoise`: the ladder, the numbers, the kept day table, the privacy rules
and the fixed texts of method `arci-logs/2`.

Written blind against `plan/exec/v2/logs2/0017-logs-2-draft.md` (decisions, record model, fixed
texts, the kept day table), `plan/exec/v2/logs2/STATISTICS_LOGS-2-draft.md` (the method),
`docs/LOG_FORMATS.md` (the log fields) and `docs/design/0016-logs.md` (the rules 0017 restates
as unchanged), without reading the implementation, its unit tests, its spike or any snapshot,
and without running the product to see what it prints. Nothing under `~/.claude` or `~/.codex`
was opened: every log and every kept table here is synthetic and is written into `tmp_path`,
with an isolated `home` and an `env` without `REALORNOISE_HOME` unless a case supplies one.

Four names are imported from the project: `arci.logs.cli.run`, the testable entry;
`arci.logs.schema.LogsDecision` and `arci.logs.schema.LogsDecisionV1`, the record models;
and `arci.hashing.hash_record`, to check the seal and the day-table digest. Every expected
number is computed here from the day values planted in the logs or in the table: `p_real`,
`p_none`, `u_none` and `p_streak` by brute-force enumeration of all labelings (`_rank_tail`,
`_g_tail`, `_runs_tail`), in exact arithmetic with `fractions.Fraction`. The feature is never
asked for its own expectation. The comment above each group names the passage it comes from,
and each test's docstring names the numbered acceptance item it covers.

Acceptance items covered elsewhere, with the reason:

- 39 (every fixed text equals a constant in the code, and every backtick span between the two
  headings is a fixed text): a source comparison, `tests/unit/logs/test_report.py`.
- 40 (`{rate_max}`, `{worst_after}` and `{worst_before}` equal what the rule of "Coverage of the
  bound" reads from `docs/results/logs-selfcheck.md`): a document test. This file holds the
  words around the three values, the shape of the rate, that the two day counts are whole
  numbers of days, and that F10, the footer and the unescaped HTML page carry the same three.
- 72 (the self-check file's cells): `bench/selfcheck_logs.py` and its own test.
- 73 (the documented command, the pinned version, both distributions): the packaging and
  document tests.
- 42, in part: the result of this version equals 2.3.0's for runs whose effective inputs do not
  differ. Nothing in this suite can run 2.3.0, so only the mapping from result to exit code,
  the result names and the unchanged reason texts are held here.
- 43, in part: that the run opens no socket and starts no process. The audit hook of 0016 does
  that; this file holds the other half, that only the requested files, their temporary files and
  the table are written.
"""

from __future__ import annotations

import html
import io
import itertools
import json
import math
import os
import re
import stat
import sys
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta, timezone
from fractions import Fraction
from functools import cache
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from arci.hashing import hash_record
from arci.logs.cli import run
from arci.logs.schema import LogsDecision, LogsDecisionV1

pytestmark = pytest.mark.acceptance

# --- the window every scenario uses ---------------------------------------------------------
# Contract, "What is compared": `N` is the newest day with a main-thread response in the logs,
# the split `s` is `N - 13` days, the after period is `s..N`, the before period is the 84 days
# ending the day before `s`. Kept rows never set `N`.

NOW = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)
NEWEST = date(2026, 11, 10)
SPLIT = date(2026, 10, 28)
AFTER_DAYS = tuple(date(2026, 11, 6) + timedelta(days=index) for index in range(5))
BEFORE_DAYS = tuple(date(2026, 10, 18) + timedelta(days=index) for index in range(10))
BEFORE_PERIOD = {"first_day": "2026-08-05", "last_day": "2026-10-27"}
AFTER_PERIOD = {"first_day": "2026-10-28", "last_day": "2026-11-10"}
WINDOW_FIRST = date(2026, 8, 5)

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
# Record 0017, "Record model" and "Fixed texts". The fields marked new in 0017 are in these
# sets; a run whose record holds one field more or fewer at any level fails `_audit`.

LOGS_FIELDS = {
    "schema_version",
    "arci_version",
    "example",
    "utc_offset_minutes",
    "project_filtered",
    "since_given",
    "kept_table",
    "keep",
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
    "first_response_day",
    "response_days_before",
    "response_days_after",
    "earliest_test_date",
    "kept_days_before",
    "kept_days_after",
    "kept_rows_other_offset",
    "settings_not_kept",
    "days_not_kept",
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
DAY_FIELDS = {"day", "count", "value", "source"}
DAY_FIELDS_V1 = {"day", "count", "value"}
PERIOD_FIELDS = {"first_day", "last_day"}
CONTEXT_FIELDS = {
    "client_versions_before",
    "client_versions_after",
    "client_versions_both",
    "workdirs_before",
    "workdirs_after",
    "subagent_share_before",
    "subagent_share_after",
    "client_versions_after_shown",
    "client_versions_after_more",
}
CONTEXT_FIELDS_V1 = {
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
KEPT_STATES = ("not_read", "absent", "read", "unreadable")
SOURCES = ("logs", "kept")
# Which test fields a finding fills (record 0017, `MeasureDecision`, unchanged from 0016).
FILLED = {
    "too_few_days": (),
    "streaky": ("p_streak",),
    "real_drop": ("p_streak", "p_real"),
    "no_drop": ("p_streak", "p_real", "u_none", "p_none"),
    "cannot_tell": ("p_streak", "p_real", "u_none", "p_none"),
}
TEST_FIELDS = ("p_streak", "p_real", "u_none", "p_none")

# F5 reasons. Only `streaky_days` changed in 0017, and it is two lines that print as given.
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
    "no_usable_setting": "No model and effort setting has a response in the window.",
    "read_error": "Session log files could not be read.",
    "format_not_recognised": (
        "Log files were found, but this version could not recover a response from them."
    ),
}
STREAKY_LINES = (
    "The streak check flagged a recorded measure: its earlier days crossed their middle few times.",
    "No result is given here. A flag does not establish that your days depend on each other.",
)
# F5 `no_logs` has two texts: the second one when the tool's directory option was given, and
# the directory itself is never printed.
NO_LOGS_DEFAULT = {
    "claude-code": (
        "No session logs found for Claude Code. Looked under ~/.claude/projects (or"
        " CLAUDE_CONFIG_DIR). Use --claude-dir DIR, or try: realornoise --example"
    ),
    "codex": (
        "No session logs found for Codex. Looked under ~/.codex (or CODEX_HOME). Use --codex-dir"
        " DIR, or try: realornoise --example"
    ),
}
NO_LOGS_GIVEN = {
    "claude-code": (
        "No session logs found for Claude Code under the directory given with --claude-dir."
        " Or try: realornoise --example"
    ),
    "codex": (
        "No session logs found for Codex under the directory given with --codex-dir."
        " Or try: realornoise --example"
    ),
}
# The usage errors, in the order of the F5 list: where more than one applies within one phase,
# the first of this order prints (record 0017, "Order of errors").
USAGE_ERRORS = {
    "malformed": "--since needs a date as YYYY-MM-DD.",
    "early": "--since can be at most 83 days before the newest day in the logs.",
    "unwritable": "Requested output could not be written.",
    "calendar": "Comparison dates are outside the supported calendar range.",
    "same_file": "Two output options name the same file.",
    "keep_project": "--keep cannot be used with --project.",
    "ignore_keep": "--ignore-kept cannot be used with --keep.",
    "usage": "Usage error. Run: realornoise --help",
}
USAGE_ORDER = (
    "malformed",
    "early",
    "unwritable",
    "calendar",
    "same_file",
    "keep_project",
    "ignore_keep",
)
INTERNAL_ERROR = "Internal error."
# The notices. F14 to F17, F22, F23 and F25 print only when their count is at least 1; F21
# prints with zeros whenever the table was read. Under ERROR F9 and F17 lose their second
# sentence, and F9 keeps its own next line.
F9 = "Compressed Codex files not read (Python 3.14 is needed): {}. The result uses the rest."
F9_ERROR = "Compressed Codex files not read (Python 3.14 is needed): {}."
F9_NEXT = "To read them: uvx --python 3.14 realornoise"
F14 = "Other model or effort settings, not compared: {}."
F15 = "Lines that lacked a needed field, left out: {}."
F16 = "Records stamped later than now, left out: {}."
F17 = "Files that could not be read: {}. The result uses the rest."
F17_ERROR = "Files that could not be read: {}."
F18 = (
    "This setting: first response in the window {first} · days with a response {b} before,"
    " {a} after"
)
F19 = (
    "Earliest test date if this setting is used every day after {last}: {date} (best case).",
    "It also needs each such day usable for a measure and the earlier days still on disk or kept.",
)
F20 = (
    "Claude Code deletes session files after 30 days by default (setting cleanupPeriodDays).",
    "With --keep, each day's counts are kept for later runs, for settings shown by name.",
)
F21 = "Days from the kept table: {b} before, {a} after."
F22 = "Settings not kept, since a name is outside the accepted lists: {}."
F23 = "Days not kept, since they hold more than 5,000 distinct reasoning counts: {}."
F24 = "The kept day table could not be read or is not valid. It was not used."
F25 = "Kept rows stored under another UTC offset, not used: {}."
F26 = "Client versions after the split: {}"
NOTICES = (F9, F14, F15, F16, F17, F22, F23, F25)
SECOND_SENTENCE = "The result uses the rest."
F4 = {
    "REAL_DROP": "RESULT: REAL DROP",
    "NO_DROP": "RESULT: NO DROP",
    "CANNOT_TELL": "RESULT: CANNOT TELL",
    "ERROR": "RESULT: ERROR",
}
# F10, changed in 0017 and changed again after the self-check ran: it carries one figure with
# its design, `{rate_max}` with `{worst_after}` and `{worst_before}`, filled at build time from
# the self-check file. The record gives F10 as thirteen lines of at most 100 characters that
# print as given, and says that with their values filled they stay within 100 characters.
F10_LINES = (
    "This shows what your logs recorded. It does not establish answer quality, a cause, or a"
    " change",
    "to the model: your tasks, prompts, projects or client version may have changed.",
    "For each tool above and one comparison, if (1) the days in this window are interchangeable"
    " when",
    "nothing changes, whatever their number of responses, and (2) to (4) below hold, then REAL"
    " DROP",
    "appears at most 2.5% of the time if nothing shifted, and NO DROP at most 2.5% of the time"
    " if a",
    "measure moved toward worse by its margin or more. When days resemble their neighbours or"
    " work comes",
    "in phases, (1) fails: in the cases it tested, the self-check measured wrong REAL DROP up to",
    "{rate_max}%, with {worst_after} days after the split and {worst_before} before; other"
    " patterns can",
    "give more. The conditions (2) to (4) are: (2) any date, model, effort or project you gave"
    " was not",
    "chosen from these logs; (3) a change moves every day alike, by an amount the measure can"
    " take; (4) a",
    "change leaves the same days, setting, reference value and earlier-day values in use. None"
    " of these",
    "is checked, and the streak check does not prove them. Running this again and again until a"
    " result",
    "appears is not covered. Exact statement: docs/STATISTICS_LOGS.md in the repository.",
)
# The same text where no line limit applies, as the Markdown file and the HTML page carry it.
F10_TEXT = " ".join(F10_LINES)
F10_FIRST_SENTENCE = "This shows what your logs recorded."
# Record 0017, "Text output, in this order", item 3: "Its third sentence begins ...".
F10_THIRD_SENTENCE = "For each tool above and one comparison, if (1)"
# The one sentence of F10 that carries the figure and its design, across the record's breaks.
FIGURE_SENTENCE = (
    "When days resemble their neighbours or work comes in phases, (1) fails: in the cases it"
    " tested, the self-check measured wrong REAL DROP up to {rate_max}%, with {worst_after}"
    " days after the split and {worst_before} before; other patterns can give more."
)
F12 = (
    "Share: --markdown FILE · --html FILE · --json FILE      "
    "Stronger evidence: arci verdict, arci run"
)
F13 = "Example data, generated. Not anyone's logs."
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
# The footer, changed in 0017 and changed again with the figures: one span, so whitespace is
# compared after collapsing runs, and its last line follows the sentence below.
FOOTER_FIRST_WORDS = "Wrong REAL DROP and wrong NO DROP are each at most 2.5%"
FOOTER_BOUND = (
    "Wrong REAL DROP and wrong NO DROP are each at most 2.5% for this tool and one comparison,"
    " if the days in the window are interchangeable when nothing changes and the assumptions"
    " below hold; when days resemble their neighbours or work comes in phases the self-check"
    " measured wrong REAL DROP up to {rate_max}% ({worst_after} days after, {worst_before}"
    " before) in its tested cases. Assumptions, unchecked: no date, model, effort or project"
    " chosen from these logs; a uniform shift the measure can take; the same days, setting,"
    " reference value and earlier-day values in use. Repeated checking until a result appears is"
    " not covered."
)
FOOTER_METHOD = "arci-logs/2, digest {digest}. Yours: uvx --python 3.14 realornoise"
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
RESPONSE_MEASURES = ("reasoning_tokens", "no_reasoning_share", "repeated_value_share")
EXIT = {"REAL_DROP": 1, "NO_DROP": 0, "CANNOT_TELL": 2, "ERROR": 3}
# The nine efforts of 0017, printed as written, and the alias shapes.
EFFORTS = ("none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra", "persistent")
# The options of the synopsis, which `--help` names (record 0017, "Command line and layout").
SYNOPSIS = (
    "--tool",
    "--since",
    "--model",
    "--effort",
    "--project",
    "--claude-dir",
    "--codex-dir",
    "--utc",
    "--markdown",
    "--html",
    "--json",
    "--keep",
    "--keep-dir",
    "--ignore-kept",
    "--example",
    "--help",
)

# --- synthetic logs -------------------------------------------------------------------------
# `docs/LOG_FORMATS.md`: every line is one JSON object; one Claude Code response is one distinct
# `message.id` within a file; one Codex response is one `token_count` event.

CLAUDE_MODEL = "claude-opus-4-20250514"
CLAUDE_OTHER = "claude-sonnet-4-20250514"
CODEX_MODEL = "gpt-5-codex"
CODEX_OTHER = "gpt-5-mini"
VERSION = "2.0.42"
WORKDIR = "/work/project"
PROJECT_DIR = "-work-project"

# Canary tokens: one upper case, one lower case shaped like a model id, one numeric shaped like
# a version that the version pattern refuses (seven digits in its last part), two private-looking
# model ids, a working directory, a prompt, a tool input and a tool output. Record 0017, the
# privacy rules of 0016 extended by the client-version exception.
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
    A `Day` also describes one row of the kept day table: `counts` and `edits` are exactly what
    a row records (`_kept_from_day`).
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
                when=_at(day, 6, index % 60),
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
                when=_at(day, 7, index % 60),
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
                when=_at(day, 9, index % 60),
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
                when=_at(day, 10, index % 60),
                call_id=f"{prefix}{day}-oedit{index}",
                failed=failed,
                text=output,
            )
        )
    for index, count in enumerate(plan.sidechain):
        lines.append(
            _assistant(
                mid=f"{prefix}{day}-s{index}",
                when=_at(day, 11, index % 60),
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


def write_claude_daily(root: Path, plans: Mapping[date, Day], **over: Any) -> dict[date, Path]:
    """One session file per day, so that a day's file can be deleted on its own."""
    paths: dict[date, Path] = {}
    for day in sorted(plans):
        paths[day] = write_claude(
            root, {day: plans[day]}, session=f"d{day.isoformat()}", prefix=f"p{day}", **over
        )
    return paths


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
                    "timestamp": _at(day, 6 + index, offset % 60),
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


# --- the kept day table ---------------------------------------------------------------------
# Record 0017, "The kept day table": `days-1.json`, schema `realornoise-days/1`, one object with
# `schema` and `rows`, rows sorted by (tool, offset, model, effort, day).

TABLE_NAME = "days-1.json"
TABLE_SCHEMA = "realornoise-days/1"
ROW_FIELDS = {
    "tool",
    "utc_offset_minutes",
    "model",
    "effort",
    "day",
    "responses",
    "reasoning",
    "reasoning_unknown",
    "edits",
    "edits_failed",
}
SIZE_LIMIT = 33_554_432


def kept_row(
    tool: str,
    day: date,
    *,
    model: str = CLAUDE_MODEL,
    effort: str = "high",
    offset: int = 0,
    reasoning: Sequence[tuple[int, int]] = (),
    unknown: int = 0,
    edits: int | None = None,
    edits_failed: int | None = None,
    responses: int | None = None,
) -> dict[str, Any]:
    """One row of the table. `responses` defaults to the frequencies plus the unknown count."""
    pairs = [[int(count), int(frequency)] for count, frequency in reasoning]
    total = sum(pair[1] for pair in pairs) + unknown
    return {
        "tool": tool,
        "utc_offset_minutes": offset,
        "model": model,
        "effort": effort,
        "day": day.isoformat(),
        "responses": total if responses is None else responses,
        "reasoning": pairs,
        "reasoning_unknown": unknown,
        "edits": None if tool == "codex" else (0 if edits is None else edits),
        "edits_failed": None if tool == "codex" else (0 if edits_failed is None else edits_failed),
    }


def _kept_from_day(
    tool: str, day: date, plan: Day, *, offset: int = 0, **over: Any
) -> dict[str, Any]:
    """The row that holds exactly what one `Day` plan records, so expectations can reuse it."""
    tally = Counter(count for count in plan.counts if count is not None)
    return kept_row(
        tool,
        day,
        offset=offset,
        reasoning=sorted(tally.items()),
        unknown=sum(1 for count in plan.counts if count is None),
        edits=len(plan.edits),
        edits_failed=sum(1 for failed in plan.edits if failed),
        **over,
    )


def _row_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (row["tool"], row["utc_offset_minutes"], row["model"], row["effort"], row["day"])


def write_kept(
    path: Path,
    rows: Sequence[Mapping[str, Any]],
    *,
    schema: str = TABLE_SCHEMA,
    sort: bool = True,
) -> Path:
    """Write a stored table. The bytes are this test's own, never the product's."""
    ordered = sorted(rows, key=_row_key) if sort else list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {"schema": schema, "rows": ordered}
    path.write_text(json.dumps(body, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _pair(tool: str, plan: Day) -> tuple[int, int]:
    """The pair the write and use rules compare: responses, then file-edit results."""
    return (len(plan.counts), 0 if tool == "codex" else len(plan.edits))


def _merge(
    tool: str, logs: Mapping[date, Day], kept: Mapping[date, Day]
) -> tuple[dict[date, Day], dict[date, str]]:
    """The days as used: the logs row wins when its pair is at least as large, and a tie."""
    merged: dict[date, Day] = {}
    source: dict[date, str] = {}
    for day in sorted(set(logs) | set(kept)):
        if day in logs and (day not in kept or _pair(tool, logs[day]) >= _pair(tool, kept[day])):
            merged[day], source[day] = logs[day], "logs"
        else:
            merged[day], source[day] = kept[day], "kept"
    return merged, source


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


def _day_json(day: date, count: int, value: Fraction, source: str | None) -> dict[str, Any]:
    row = {"day": day.isoformat(), "count": count, "value": _rational(value)}
    if source is not None:
        row["source"] = source
    return row


DayRow = tuple[date, int, Fraction, str | None]


def _expect_measure(
    measure: str,
    before: Sequence[DayRow],
    after: Sequence[DayRow],
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
    sources: Mapping[date, str] | None = None,
    with_source: bool = True,
) -> list[dict[str, Any]]:
    planted = _periods(plans, split)
    before = planted[0] if before_days is None else tuple(before_days)
    after = planted[1] if after_days is None else tuple(after_days)
    vstar = _vstar(plans, [*before, *after]) if tool == "codex" else None
    expected: list[dict[str, Any]] = []
    for measure in TOOL_MEASURES[tool]:
        series: list[list[DayRow]] = [[], []]
        for index, days in enumerate((before, after)):
            for day in days:
                got = _day_value(measure, plans[day], vstar)
                if got is not None:
                    source = None
                    if with_source:
                        source = "logs" if sources is None else sources[day]
                    series[index].append((day, got[0], got[1], source))
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


# --- the earliest date a test is possible ---------------------------------------------------
# Record 0017, "The earliest date a test is possible": for `d = N+1, N+2, ...`, `U_d` is the
# measure's usable days together with every day from `N+1` to `d`; the measure has enough days
# on `d` with at least 5 days in `[d-13, d]` and at least 10 in `[d-97, d-14]`.


def _earliest_test_date(tool: Mapping[str, Any]) -> date:
    assert tool["after"] is not None, "the date is computed only without `--since`"
    newest = date.fromisoformat(tool["after"]["last_day"])
    gating = [
        {
            date.fromisoformat(row["day"])
            for side in ("before_days", "after_days")
            for row in measure[side]
        }
        for measure in tool["measures"]
    ]
    for step in range(1, 25):
        day = newest + timedelta(days=step)
        fresh = {newest + timedelta(days=index) for index in range(1, step + 1)}
        for usable in gating:
            pooled = usable | fresh
            late = sum(1 for one in pooled if day - timedelta(days=13) <= one <= day)
            early = sum(
                1 for one in pooled if day - timedelta(days=97) <= one <= day - timedelta(days=14)
            )
            if late >= 5 and early >= 10:
                return day
    raise AssertionError("the record proves the date is at most N+24")


# --- client versions ------------------------------------------------------------------------
# Record 0017, "Names": a version prints only when it matches the pattern; the three highest
# matching versions by numeric order, highest first, with equal tuples in text order; `k` counts
# every distinct after-period version not listed, matching or not.

VERSION_PATTERN = re.compile(r"[0-9]{1,5}(\.[0-9]{1,5}){1,3}")


def _version_tuple(name: str) -> tuple[int, ...]:
    return tuple(int(part) for part in name.split("."))


def _shown_versions(after: Iterable[str]) -> tuple[list[str], int]:
    distinct = set(after)
    matching = sorted(name for name in distinct if VERSION_PATTERN.fullmatch(name))
    ordered = sorted(matching, key=_version_tuple, reverse=True)
    shown = ordered[:3]
    return shown, len(distinct) - len(shown)


def _version_line(after: Iterable[str]) -> str | None:
    shown, more = _shown_versions(after)
    if not shown:
        return None
    text = ", ".join(shown)
    if more >= 1:
        text = f"{text} +{more} more"
    return F26.format(text)


# --- running the command --------------------------------------------------------------------
# Record 0017, "Command line and layout": `run(argv, *, now, env, home, out, err) -> int`; `env`
# supplies `REALORNOISE_HOME` and `home` supplies `~` for the default table directory.


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

    def page(self) -> str:
        """The HTML page's own text, for comparing a fixed text with it."""
        return _unescaped(self.text("html"))


def _unescaped(page: str) -> str:
    """An HTML page with its character references resolved.

    Record 0017, "Command line and layout": in the HTML output the characters `&`, `<`, `>`,
    `"` and `'` are written as HTML character references, so a fixed text that holds one of
    them appears on the page escaped, and a test compares it after unescaping the page. The
    structural checks (no script, no external reference, the strip charts' circles) stay on the
    page as it is written.
    """
    return html.unescape(page)


def _flat(text: str) -> str:
    """The text with every run of whitespace collapsed, for sentences the record may wrap."""
    return " ".join(text.split())


def _says(text: str, sentence: str) -> None:
    assert _flat(sentence) in _flat(text), sentence


def _absent(text: str, sentence: str) -> None:
    assert _flat(sentence) not in _flat(text), sentence


def _row_finding(measure: Mapping[str, Any], reason: str) -> str:
    """The F6 finding cell for one measure.

    Record 0017, F6: "when the tool's reason is `streaky_days`, every row that is not `days come
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

    Record 0017: "a fixed sentence longer than 100 characters is broken at the last space that
    leaves the line at most 100 characters long, and so on for the rest", as in 0016. The
    Markdown and HTML outputs have no line limit, so this applies to the terminal text only.
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


def _day_table(tool: Mapping[str, Any], *, method: str = "arci-logs/2") -> dict[str, Any]:
    """The structure `day_table_sha256` hashes (record 0017, "Record model", last bullets).

    Each day value now carries its `source`, so the payload is the record's own day objects.
    """
    return {
        "method": method,
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


def _span(period: Mapping[str, Any] | None) -> int:
    if period is None:
        return 0
    first = date.fromisoformat(period["first_day"])
    last = date.fromisoformat(period["last_day"])
    return (last - first).days + 1


def _audit(body: Mapping[str, Any], code: int) -> None:
    """The record rules that hold on every run of this file.

    Fields at every level (item 1), the null rules, ascending day lists, one source per day
    (item 36), the kept-day and response-day bounds, the earliest test date, the shown client
    versions, the day-table digest and the seal.
    """
    assert set(body) == LOGS_FIELDS
    assert body["schema_version"] == "arci-logs/2"
    assert body["example"] in (True, False)
    assert isinstance(body["project_filtered"], bool)
    assert isinstance(body["since_given"], bool)
    assert isinstance(body["keep"], bool)
    assert body["kept_table"] in KEPT_STATES
    if body["kept_table"] == "not_read":
        assert body["keep"] is False
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
            for name in (
                "model",
                "effort",
                "before",
                "after",
                "context",
                "day_table_sha256",
                "first_response_day",
                "earliest_test_date",
            ):
                assert tool[name] is None, name
            for name in (
                "response_days_before",
                "response_days_after",
                "kept_days_before",
                "kept_days_after",
            ):
                assert tool[name] == 0, name
            if tool["result"] == "ERROR":
                for name in ("kept_rows_other_offset", "settings_not_kept", "days_not_kept"):
                    assert tool[name] == 0, name
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
            shown = tool["context"]["client_versions_after_shown"]
            more = tool["context"]["client_versions_after_more"]
            assert isinstance(shown, list) and len(shown) <= 3
            assert all(VERSION_PATTERN.fullmatch(name) for name in shown), shown
            assert shown == sorted(sorted(shown), key=_version_tuple, reverse=True), shown
            assert len(shown) + more == tool["context"]["client_versions_after"]
        sources: dict[str, str] = {}
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
                    assert row["source"] in SOURCES
                    if row["source"] == "kept":
                        assert body["kept_table"] == "read"
                    # One day, one source: a day in two measures carries the same source.
                    assert sources.setdefault(row["day"], row["source"]) == row["source"]
        if not blank:
            for side, field_name in (("before_days", "before"), ("after_days", "after")):
                kept = {
                    row["day"]
                    for measure in tool["measures"]
                    for row in measure[side]
                    if row["source"] == "kept"
                }
                counted = tool[f"kept_days_{field_name}"]
                assert counted >= len(kept), (side, counted)
                assert counted <= _span(tool[field_name]), (side, counted)
            for side, field_name in (("before_days", "before"), ("after_days", "after")):
                for measure in tool["measures"]:
                    if measure["id"] not in RESPONSE_MEASURES:
                        continue
                    days = {row["day"] for row in measure[side]}
                    assert tool[f"response_days_{field_name}"] >= len(days), measure["id"]
            if tool["first_response_day"] is not None:
                first = date.fromisoformat(tool["first_response_day"])
                assert date.fromisoformat(tool["before"]["first_day"]) <= first
                last = (
                    date.fromisoformat(tool["after"]["last_day"])
                    if tool["after"] is not None
                    else date.fromisoformat(tool["split_date"]) - timedelta(days=1)
                )
                assert first <= last
                usable = [
                    date.fromisoformat(row["day"])
                    for measure in tool["measures"]
                    if measure["id"] in RESPONSE_MEASURES
                    for side in ("before_days", "after_days")
                    for row in measure[side]
                ]
                assert all(first <= one for one in usable)
            wanted = tool["reason"] == "too_few_days" and not body["since_given"]
            assert (tool["earliest_test_date"] is not None) is wanted, tool["reason"]
            if tool["earliest_test_date"] is not None:
                assert tool["earliest_test_date"] == _earliest_test_date(tool).isoformat()
    assert code == _expect_exit(results)
    draft = {name: value for name, value in body.items() if name != "seal"}
    assert body["seal"] == hash_record(draft)


def _raw_run(
    tmp_path: Path,
    argv: Sequence[str],
    *,
    now: datetime = NOW,
    env: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> tuple[int, str, str]:
    """Call `run` with the options exactly as given, and check what holds on every run."""
    place = (tmp_path / "home") if home is None else home
    place.mkdir(parents=True, exist_ok=True)
    out, err = io.StringIO(), io.StringIO()
    try:
        code = run(list(argv), now=now, env=dict(env or {}), home=place, out=out, err=err)
    except SystemExit:
        pytest.fail("`run` exited the process instead of returning an exit code")
    except Exception as exc:  # the message must carry no string read from a log
        hits = sum(1 for canary in CANARIES if canary in str(exc))
        pytest.fail(f"`run` raised {type(exc).__name__}; canary strings in its message: {hits}")
    printed, failed = out.getvalue(), err.getvalue()
    assert "Traceback" not in printed and "Traceback" not in failed
    # `Internal error.` is the text for a failure no other text covers; no run here is one.
    assert INTERNAL_ERROR not in failed
    # The terminal text keeps to 100 characters; Markdown and HTML have no line limit.
    for line in [*printed.splitlines(), *failed.splitlines()]:
        assert len(line) <= 100, line
    # Plain ASCII except the middle dot, no colour and no control characters.
    for character in printed + failed:
        assert character == "·" or (character.isascii() and (character >= " " or character == "\n"))
    return code, printed, failed


def _run(
    tmp_path: Path,
    argv: Sequence[str],
    *,
    now: datetime = NOW,
    outputs: Sequence[str] = (),
    stem: str = "decision",
    env: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> Outcome:
    json_path = tmp_path / f"{stem}.json"
    full = [*argv, "--json", str(json_path)]
    extra: dict[str, Path] = {}
    for name in outputs:
        path = tmp_path / f"{stem}.{'md' if name == 'markdown' else name}"
        extra[name] = path
        full += [f"--{name}", str(path)]
    code, printed, failed = _raw_run(tmp_path, full, now=now, env=env, home=home)
    body = None
    if json_path.exists():
        body = json.loads(json_path.read_text(encoding="utf-8"))
        _audit(body, code)
        LogsDecision.model_validate(body)
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


def _listing(folder: Path) -> set[str]:
    return {str(path.relative_to(folder)) for path in folder.rglob("*")}


# The shapes of the three values ("Coverage of the bound"): the rate is the proportion times
# 100, in decimal, without trailing zeros and without a trailing point (a proportion of 0
# prints as `0`); the two day counts are plain whole numbers with no leading zero.
RATE_SHAPE = r"((?:0|[1-9][0-9]*)(?:\.[0-9]*[1-9])?)"
DAYS_SHAPE = r"([1-9][0-9]*)"
FIGURE_SHAPES = {
    "rate_max": RATE_SHAPE,
    "worst_after": DAYS_SHAPE,
    "worst_before": DAYS_SHAPE,
}
Figures = tuple[str, int, int]


def _pattern(template: str, shapes: Mapping[str, str]) -> str:
    """A regex that matches `template` exactly, each `{field}` replaced by its shape."""
    out = ""
    rest = template
    while True:
        found = re.search(r"\{([a-z_0-9]+)\}", rest)
        if found is None:
            return out + re.escape(rest)
        out += re.escape(rest[: found.start()]) + shapes[found.group(1)]
        rest = rest[found.end() :]


def _filled(template: str, figures: Figures) -> str:
    return template.format(rate_max=figures[0], worst_after=figures[1], worst_before=figures[2])


def _figures(text: str) -> Figures:
    """The one self-check figure and its design, read out of F10's own sentence.

    The record fills `{rate_max}`, `{worst_after}` and `{worst_before}` at build time from the
    self-check file, so this file cannot hold the numbers; it holds every word around them, the
    shape of the rate and the shape of the two day counts. That the three equal what the rule
    of "Coverage of the bound" reads from the self-check file is item 40, covered elsewhere;
    here the same three must appear in F10, in the footer and on the page.
    """
    found = re.search(_pattern(FIGURE_SENTENCE, FIGURE_SHAPES), _flat(text))
    assert found is not None, "F10 does not hold its figure sentence with the three values"
    return found.group(1), int(found.group(2)), int(found.group(3))


def _f10_block(outcome: Outcome) -> Figures:
    """F10 as the text output prints it: the record's thirteen lines, line for line.

    The three values are read from the printed sentence first, since the record fills them at
    build time; every line is then rebuilt from them and compared, each line is held to 100
    characters, and the block is one run of consecutive non-blank lines.
    """
    lines = outcome.lines
    starts = [index for index, line in enumerate(lines) if line.startswith(F10_FIRST_SENTENCE)]
    assert len(starts) == 1, "F10 prints once, when a tool has a result other than ERROR"
    start = starts[0]
    block = lines[start : start + len(F10_LINES)]
    assert all(line.strip() for line in block), "F10 prints as one run of lines"
    for line in block:
        assert len(line) <= 100, line
    figures = _figures("\n".join(block))
    assert block == _f10_lines(figures)
    return figures


def _f10_lines(figures: Figures) -> list[str]:
    return [_filled(line, figures) for line in F10_LINES]


def _footer_figures(text: str) -> Figures:
    """The three values the Markdown footer carries, with the footer held word for word.

    The footer is one span, so whitespace is compared after collapsing runs; its last line
    carries the method name and the digest and is checked where the digest is known.
    """
    found = re.search(_pattern(FOOTER_BOUND, FIGURE_SHAPES), _flat(text))
    assert found is not None, "the footer does not hold its figure and its design"
    figures = (found.group(1), int(found.group(2)), int(found.group(3)))
    _says(text, _filled(FOOTER_BOUND, figures))
    return figures


def _reason_block(outcome: Outcome, reason: str, *, tool: str = "claude-code") -> None:
    """The F5 reason as the text output shows it: `streaky_days` is two lines, printed as given."""
    if reason == "streaky_days":
        _run_of(outcome, STREAKY_LINES)
    elif reason == "no_logs":
        _block(outcome, NO_LOGS_GIVEN[tool])
    else:
        _block(outcome, REASONS[reason])


# --- 1. the ladder: one scenario per result and reason ---------------------------------------
# Contract, "Result for a tool, in this order" and "Process exit code"; record 0017 decision 8,
# which keeps the command, the exit codes, the result names and the reason codes of 0016.

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
    """Item 42: the mapping from each result to its exit code, the result names and the reason
    texts other than the one 0017 changes are those of 0016."""
    result, reason = LADDER[name]
    root = tmp_path / "claude"
    root.mkdir()
    plans = _ladder_logs(name, root)
    outcome = _run(tmp_path, _args("claude-code", claude=root))

    tool = outcome.tool()
    assert (tool["result"], tool["reason"]) == (result, reason)
    assert outcome.code == EXIT[result]
    assert F4[result] in outcome.lines
    _reason_block(outcome, reason)
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
    """Contract step 5 and the `streaky_days` text changed in 0017: the check withholds a result
    and a flag does not establish that days depend on each other."""
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
    # The two lines of the reason, as the record gives them, and the words 0016 used are gone.
    _run_of(outcome, STREAKY_LINES)
    _absent(outcome.out, "Your earlier days come in streaks in a recorded measure")
    # The table marks it as not used; the measure without enough days keeps its own text.
    assert _row_finding(tokens, "streaky_days") == "days come in streaks"
    assert _row_finding(share, "streaky_days") == "not used"
    assert _row_finding(edits, "streaky_days") == "too few days"
    for measure in tool["measures"]:
        _says(outcome.out, _row_finding(measure, tool["reason"]))
    assert "real drop" not in outcome.out
    _says(outcome.text("markdown"), "not used")
    assert "real drop" not in outcome.text("markdown")
    _says(outcome.page(), "not used")
    # The F5 reason reaches the Markdown file only in an ERROR block and for a tool with no
    # selected setting, so the changed wording is held against the text output and the page.
    for place in (outcome.out, outcome.page()):
        _says(place, STREAKY_LINES[1])


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
    outcome = _run(tmp_path, _args("both", claude=claude, codex=codex), outputs=("markdown",))

    assert (outcome.tool(0)["result"], outcome.tool(0)["reason"]) == ("ERROR", "no_logs")
    assert outcome.tool(1)["result"] == "NO_DROP"
    assert outcome.code == 0
    # An ERROR block is the tool name, F4 and the reason; F10 prints once, for the tool that
    # has a result (record 0017, text layout items 2 and 3).
    assert TOOL_NAMES["claude-code"] in outcome.lines
    _block(outcome, NO_LOGS_GIVEN["claude-code"])
    _f10_block(outcome)


def test_with_no_log_root_at_all_both_tools_are_requested_and_error(tmp_path: Path) -> None:
    """Record 0017: `--tool auto` with neither root present requests both, so the code is 3."""
    outcome = _run(tmp_path, ["--tool", "auto", "--utc"])
    assert [tool["result"] for tool in outcome.tools()] == ["ERROR", "ERROR"]
    assert [tool["reason"] for tool in outcome.tools()] == ["no_logs", "no_logs"]
    assert outcome.code == 3
    _block(outcome, NO_LOGS_DEFAULT["claude-code"], NO_LOGS_DEFAULT["codex"])
    assert [tool["split_date"] for tool in outcome.tools()] == [None, None]
    # F10 belongs to tools that have a result, and there is none.
    assert F10_FIRST_SENTENCE not in _flat(outcome.out)


def test_auto_requests_only_the_tool_whose_root_exists(tmp_path: Path) -> None:
    root = tmp_path / "claude"
    write_claude(root, _uniform(ALTERNATING, DROPPED))
    outcome = _run(tmp_path, ["--tool", "auto", "--utc", "--claude-dir", str(root)])
    assert [tool["tool"] for tool in outcome.tools()] == ["claude-code"]


def test_a_directory_option_names_the_option_and_never_the_directory(tmp_path: Path) -> None:
    """F5 `no_logs`, second text; and a tool with a directory option is always requested."""
    missing = tmp_path / "no-such-canary-directory"
    outcome = _run(
        tmp_path,
        ["--tool", "auto", "--utc", "--codex-dir", str(missing)],
        outputs=("markdown", "html"),
    )
    # Requested although the directory does not exist, so a wrong path reports `no_logs`.
    assert [tool["tool"] for tool in outcome.tools()] == ["codex"]
    assert (outcome.tool()["result"], outcome.tool()["reason"]) == ("ERROR", "no_logs")
    assert outcome.code == 3
    _block(outcome, NO_LOGS_GIVEN["codex"])
    # The first text, which names the default place, is not the one used here.
    assert "Looked under" not in outcome.out
    for text in (
        outcome.out,
        outcome.err,
        outcome.json_path.read_text(encoding="utf-8"),
        outcome.text("markdown"),
        outcome.text("html"),
    ):
        assert str(missing) not in text
        assert "no-such-canary-directory" not in text


def test_an_error_tool_prints_its_notices_without_their_second_sentence(tmp_path: Path) -> None:
    """Record 0017, F17 and the text layout: under ERROR there is no result to speak of."""
    root = tmp_path / "claude"
    blocked = root / PROJECT_DIR / "01.jsonl"
    _write_lines(blocked, [{"type": "mode", "timestamp": _at(NEWEST)}])
    blocked.chmod(0o000)
    if os.access(blocked, os.R_OK):
        blocked.chmod(stat.S_IRUSR | stat.S_IWUSR)
        pytest.skip("this process can read a file with no read permission")
    try:
        outcome = _run(tmp_path, _args("claude-code", claude=root), outputs=("markdown", "html"))
    finally:
        blocked.chmod(stat.S_IRUSR | stat.S_IWUSR)
    tool = outcome.tool()
    assert (tool["result"], tool["reason"]) == ("ERROR", "read_error")
    assert tool["counters"]["files_unreadable"] == 1
    assert tool["counters"]["files_read"] == 0
    _block(outcome, REASONS["read_error"])
    assert F17_ERROR.format(1) in outcome.lines
    assert SECOND_SENTENCE not in outcome.out
    # The Markdown ERROR block holds the tool, ERROR, the reason and the notice, nothing else.
    block = outcome.text("markdown")
    _says(block, F17_ERROR.format(1))
    assert SECOND_SENTENCE not in block
    assert "2.5%" not in block
    _absent(block, FOOTER_FIRST_WORDS)
    # The HTML page shows the notices of an ERROR tool.
    _says(outcome.page(), F17_ERROR.format(1))
    assert SECOND_SENTENCE not in outcome.page()


def test_an_error_tool_still_names_the_way_to_read_compressed_files(tmp_path: Path) -> None:
    """A Codex history that is entirely compressed: F9 in its ERROR wording, with its line.

    On Python 3.14 the file is opened and fails while being decompressed, which is F17; below
    that version a compressed file is counted as not read, which is F9.
    """
    root = tmp_path / "codex"
    path = root / "sessions" / "2026" / "11" / "10" / "rollout-2026-11-10.jsonl.zst"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"\x28\xb5\x2f\xfd" + b"these bytes are not a compressed stream")
    outcome = _run(tmp_path, _args("codex", codex=root), outputs=("markdown", "html"))
    tool = outcome.tool()
    assert (tool["result"], tool["reason"]) == ("ERROR", "read_error")
    assert outcome.code == 3
    if sys.version_info >= (3, 14):
        assert tool["counters"]["files_unreadable"] == 1
        assert F17_ERROR.format(1) in outcome.lines
    else:
        assert tool["counters"]["files_unread_compressed"] == 1
        assert F9_ERROR.format(1) in outcome.lines
        assert F9_NEXT in outcome.lines
        block = outcome.text("markdown")
        _says(block, F9_ERROR.format(1))
        _says(block, F9_NEXT)
        _says(outcome.page(), F9_NEXT)
    assert SECOND_SENTENCE not in outcome.out
    assert SECOND_SENTENCE not in outcome.text("markdown")


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
    # Every day of this run came from the logs.
    assert {row["source"] for row in tokens["before_days"] + tokens["after_days"]} == {"logs"}


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
# Contract, "Measures"; record 0017, "Record model" (`DayValue.count`), unchanged from 0016.

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
    # The first response day is the earliest day with a response at this setting, which is a
    # day that no measure can use.
    assert tool["first_response_day"] == BOUNDARY_EXTRA[0].isoformat()
    assert tool["response_days_before"] == 12
    assert tool["response_days_after"] == 5


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


EDIT_ONLY_DAY = date(2026, 10, 10)
# The day the calling response sits on, before the window's first day, so that the response
# itself enters no day of the comparison while its results fall on a day inside the window.
BEFORE_WINDOW = date(2026, 7, 1)


def _edit_only_lines(
    *, response_day: date, result_day: date, count: int = 10, failed: int = 1
) -> list[dict[str, Any]]:
    """One response that calls `count` file edits whose results are stamped on another day.

    LOG_FORMATS: "The result's own `timestamp` gives its day; model, effort, project membership
    and main-thread status come from the response that made the call."
    """
    calls = [(f"only-{index}", "Edit") for index in range(count)]
    lines = [
        _assistant(
            mid="only-a",
            when=_at(response_day, 8, 0),
            setting=CLAUDE_SETTING,
            reasoning=5,
            calls=calls,
        )
    ]
    for index, (call_id, _) in enumerate(calls):
        lines.append(
            _tool_result(when=_at(result_day, 9, index), call_id=call_id, failed=index < failed)
        )
    return lines


def test_a_day_of_file_edit_results_without_a_response(tmp_path: Path) -> None:
    """Item 50: a Claude Code day with 10 file-edit results and no main-thread response at the
    compared setting validates, counts in `edit_failure_share`, and is not a response day."""
    logs = _uniform(ALTERNATING, DROPPED, edits=(False,) * 10)
    root = tmp_path / "claude"
    write_claude(root, logs)
    _write_lines(
        root / PROJECT_DIR / "02.jsonl",
        _edit_only_lines(response_day=BEFORE_WINDOW, result_day=EDIT_ONLY_DAY, failed=1),
    )
    outcome = _run(tmp_path, _args("claude-code", claude=root))
    # The calling response is dated before the window, so it enters no day of the comparison;
    # the extra day holds ten results, one of them failed, and no response.
    plans = {**logs, EDIT_ONLY_DAY: Day(counts=(), edits=(True,) + (False,) * 9)}
    tool = _check(outcome, "claude-code", plans)
    edits = tool["measures"][2]
    assert edits["before_days"][0] == {
        "day": EDIT_ONLY_DAY.isoformat(),
        "count": 10,
        "value": _rational(Fraction(1, 10)),
        "source": "logs",
    }
    # It is not a response day, and the first response day is later than it.
    assert tool["response_days_before"] == 10
    assert tool["first_response_day"] == BEFORE_DAYS[0].isoformat()


# --- 4. what is compared: the setting rule of decision 2 -------------------------------------
# Record 0017 decision 2 and the contract, "Setting (changed in `arci-logs/2`)": the candidate
# with the most main-thread responses in the after period is compared; ties go to the raw model
# id and then the raw effort, in code-point order; no reasoning count and no file-edit result
# enters the choice; with no after-period candidate the same count rule runs over the before
# period. This replaces the 0016 rule, which counted both periods together, so the 0016 case
# "the setting is chosen by pooled counts, not by the after period" is gone and the three cases
# below take its place.


def test_the_setting_with_the_most_after_period_responses_is_compared(tmp_path: Path) -> None:
    """Item 3: A has more responses over the whole window, B has more in the after period; the
    record names B."""
    plans = {
        **{day: Day(counts=(100,) * 20, other=(100,) * 5) for day in BEFORE_DAYS},
        **{day: Day(counts=(100,) * 5, other=(100,) * 20) for day in AFTER_DAYS},
    }
    outcome = _claude_run(tmp_path, plans)
    tool = outcome.tool()
    # A: 200 before and 25 after. B: 50 before and 100 after.
    assert (tool["model"], tool["effort"]) == (CLAUDE_OTHER, "high")
    assert tool["other_settings"] == 1
    # B's own days: five after-days of 20 responses, no usable before-day.
    chosen = {
        **{day: Day(counts=(100,) * 5) for day in BEFORE_DAYS},
        **{day: Day(counts=(100,) * 20) for day in AFTER_DAYS},
    }
    _check(outcome, "claude-code", chosen)
    assert (tool["result"], tool["reason"]) == ("CANNOT_TELL", "too_few_days")
    assert tool["response_days_before"] == 10
    assert tool["response_days_after"] == 5


@pytest.mark.parametrize(
    ("setting", "other", "model", "effort"),
    [
        # Equal after-period counts and different raw model ids: "a" is first in code-point
        # order, although the rendered names reorder them.
        (Setting("a", "z"), Setting("a-b", "high"), "model-1", "effort-1"),
        # Equal model ids: the first raw effort wins, and "high" is before "medium".
        (Setting(CODEX_MODEL, "high"), Setting(CODEX_MODEL, "medium"), CODEX_MODEL, "high"),
    ],
)
def test_a_tie_in_the_after_period_goes_to_the_raw_pair(
    tmp_path: Path, setting: Setting, other: Setting, model: str, effort: str
) -> None:
    """Item 4: ties go to the raw model id, then the raw effort, each in code-point order."""
    plans = {day: Day(counts=(90,) * 20, other=(10,) * 20) for day in (*BEFORE_DAYS, *AFTER_DAYS)}
    outcome = _codex_run(tmp_path, plans, setting=setting, other=other)
    tool = outcome.tool()
    assert (tool["model"], tool["effort"]) == (model, effort)
    assert tool["other_settings"] == 1
    # The day values are the compared setting's own, never a mix with the other setting's.
    _check(outcome, "codex", plans)
    assert all(row["value"] == "90/1" for row in tool["measures"][0]["before_days"])


def test_the_counts_and_the_edits_never_change_the_compared_setting(tmp_path: Path) -> None:
    """Items 5 and 6: with the responses, their days, settings and threads kept, changing
    reasoning counts, making some of them unknown, or changing file-edit results never changes
    which setting is compared."""
    first = tmp_path / "one"
    second = tmp_path / "two"
    plain = {
        day: Day(counts=(100,) * 20, edits=(False,) * 10, other=(100,) * 19)
        for day in (*BEFORE_DAYS, *AFTER_DAYS)
    }
    # The same responses on the same days at the same settings: only the counts and the edit
    # results differ, and in the after period some counts become unknown.
    moved = {
        day: Day(
            counts=(1,) * 17 + (None,) * 3,
            edits=(True,) * 10,
            other=(900,) * 19,
        )
        for day in (*BEFORE_DAYS, *AFTER_DAYS)
    }
    plain_out = _claude_run(first, plain)
    moved_out = _claude_run(second, moved)
    for outcome in (plain_out, moved_out):
        assert (outcome.tool()["model"], outcome.tool()["effort"]) == (CLAUDE_MODEL, "high")
        assert outcome.tool()["other_settings"] == 1
    # The results may differ; the choice may not.
    assert plain_out.tool()["model"] == moved_out.tool()["model"]
    assert plain_out.tool()["effort"] == moved_out.tool()["effort"]


def test_a_since_later_than_the_newest_day_still_compares_a_setting(tmp_path: Path) -> None:
    """Item 7: with `--since` later than `N` and settings in the window, the setting with the
    most before-period responses is compared and the result is CANNOT TELL with `after` null."""
    root = tmp_path / "claude"
    write_claude(root, {day: Day(counts=(100,) * 20) for day in BEFORE_DAYS}, session="01")
    write_claude(
        root,
        {day: Day(counts=(100,) * 20) for day in AFTER_DAYS},
        session="02",
        prefix="b",
        setting=CLAUDE_SECOND,
    )
    outcome = _run(tmp_path, _args("claude-code", claude=root, extra=("--since", "2026-11-11")))
    tool = outcome.tool()
    assert tool["split_date"] == "2026-11-11"
    assert tool["after"] is None
    # No candidate has an after-period response, so the count rule runs over the before period,
    # which here holds every day: 200 responses against 100.
    assert (tool["model"], tool["effort"]) == (CLAUDE_MODEL, "high")
    assert (tool["result"], tool["reason"]) == ("CANNOT_TELL", "too_few_days")
    assert all(measure["after_days"] == [] for measure in tool["measures"])
    assert "after   no days   split 2026-11-11" in outcome.lines
    assert outcome.body is not None and outcome.body["since_given"] is True
    # With `--since` the earliest test date is not computed.
    assert tool["earliest_test_date"] is None


@pytest.mark.parametrize("shape", ["no_setting", "no_candidate"])
def test_no_candidate_leaves_no_usable_setting(tmp_path: Path, shape: str) -> None:
    """Item 8: when every response in the window lacks a model or an effort, and when `--model`
    names no candidate, the result is CANNOT TELL with `no_usable_setting` and its text."""
    plans = _uniform(ALTERNATING, DROPPED)
    if shape == "no_setting":
        outcome = _claude_run(tmp_path, plans, setting=Setting(CLAUDE_MODEL, None))
    else:
        outcome = _claude_run(tmp_path, plans, extra=("--model", "claude-haiku-4"))
    tool = outcome.tool()
    assert (tool["result"], tool["reason"]) == ("CANNOT_TELL", "no_usable_setting")
    assert outcome.code == 2
    _block(outcome, REASONS["no_usable_setting"])
    assert tool["measures"] == []
    assert tool["earliest_test_date"] is None


def test_model_and_effort_keep_only_the_candidates_they_name(tmp_path: Path) -> None:
    """Item 9: `--model` and `--effort` keep their 0016 effect, and the count rule then chooses
    among the candidates that match, so the named candidate is compared even when another has
    more after-period responses. The second setting carries its effort on `perTurnEffort`."""
    plans = {
        day: Day(counts=(200,) * 20, edits=(False,) * 10, other=(other,) * 25)
        for day, other in zip((*BEFORE_DAYS, *AFTER_DAYS), (*ALTERNATING, *DROPPED), strict=True)
    }
    root = tmp_path / "claude"
    write_claude(
        root,
        plans,
        setting=Setting(CLAUDE_MODEL, "high"),
        other=Setting(CLAUDE_MODEL, "medium", key="perTurnEffort"),
    )
    # The second setting has more after-period responses (125 to 100), so it is compared.
    default = _run(tmp_path, _args("claude-code", claude=root), stem="a")
    assert default.tool()["effort"] == "medium"
    assert default.tool()["result"] == "REAL_DROP"

    # `--effort high` leaves one candidate, which is compared although it has fewer responses.
    picked = _run(tmp_path, _args("claude-code", claude=root, extra=("--effort", "high")), stem="b")
    assert (picked.tool()["model"], picked.tool()["effort"]) == (CLAUDE_MODEL, "high")
    assert picked.tool()["result"] == "NO_DROP"
    named = _run(
        tmp_path,
        _args("claude-code", claude=root, extra=("--model", CLAUDE_MODEL, "--effort", "high")),
        stem="c",
    )
    assert named.tool()["measures"] == picked.tool()["measures"]
    # With both options and no matching pair, no candidate remains.
    none = _run(
        tmp_path,
        _args("claude-code", claude=root, extra=("--model", CLAUDE_OTHER, "--effort", "high")),
        stem="d",
    )
    assert (none.tool()["result"], none.tool()["reason"]) == ("CANNOT_TELL", "no_usable_setting")


@pytest.mark.parametrize("shape", ["no_setting_after", "selector"])
def test_the_before_period_fallback(tmp_path: Path, shape: str) -> None:
    """Item 56: when no candidate has an after-period response, the count rule runs over the
    before period, the record names that setting, and the result is CANNOT TELL."""
    root = tmp_path / "claude"
    write_claude(root, {day: Day(counts=(100,) * 20) for day in BEFORE_DAYS}, session="01")
    extra: tuple[str, ...] = ()
    if shape == "no_setting_after":
        # The after period holds responses, but every one of them lacks an effort.
        write_claude(
            root,
            {day: Day(counts=(100,) * 20) for day in AFTER_DAYS},
            session="02",
            prefix="n",
            setting=Setting(CLAUDE_MODEL, None),
        )
    else:
        # `--model` removes the only candidate with after-period responses.
        write_claude(
            root,
            {day: Day(counts=(100,) * 20) for day in AFTER_DAYS},
            session="02",
            prefix="n",
            setting=CLAUDE_SECOND,
        )
        extra = ("--model", CLAUDE_MODEL)
    outcome = _run(tmp_path, _args("claude-code", claude=root, extra=extra))
    tool = outcome.tool()
    assert (tool["model"], tool["effort"]) == (CLAUDE_MODEL, "high")
    assert tool["result"] == "CANNOT_TELL"
    assert tool["response_days_before"] == 10
    assert tool["response_days_after"] == 0
    assert tool["first_response_day"] == BEFORE_DAYS[0].isoformat()


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


def test_since_replaces_the_split_date(tmp_path: Path) -> None:
    plans = _uniform(ALTERNATING, DROPPED)
    outcome = _claude_run(tmp_path, plans, extra=("--since", "2026-11-01"))
    tool = _check(outcome, "claude-code", plans, split=date(2026, 11, 1))
    assert tool["split_date"] == "2026-11-01"
    assert tool["after"] == {"first_day": "2026-11-01", "last_day": "2026-11-10"}
    assert tool["before"] == {"first_day": "2026-08-09", "last_day": "2026-10-31"}
    assert "after   2026-11-01 to 2026-11-10   split 2026-11-01" in outcome.lines
    assert outcome.body is not None and outcome.body["since_given"] is True


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
    # Under `--project` no table is read.
    assert outcome.body["kept_table"] == "not_read"
    tool = _check(outcome, "claude-code", plans)
    # Without the filter every day would hold 40 counts and a median of 91/2.
    assert all(row["count"] == 20 for row in tool["measures"][0]["before_days"])
    assert tool["context"]["workdirs_before"] == 1
    assert tool["context"]["workdirs_after"] == 1
    # `files_outside_project` is used for Codex only: a Claude Code line is filtered on its own
    # working directory, so no file is set aside.
    assert tool["counters"]["files_outside_project"] == 0
    assert tool["counters"]["files_read"] == 3


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
    # `responses` includes sub-agent responses (record 0017, "Fixed texts", last paragraph).
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


def test_the_client_version_counts_are_per_period(tmp_path: Path) -> None:
    plans: dict[date, Day] = {day: Day(counts=(100,) * 20) for day in BEFORE_DAYS}
    plans.update({day: Day(counts=(100,) * 20, version="3.0.1") for day in AFTER_DAYS})
    plans[AFTER_DAYS[0]] = Day(counts=(100,) * 20)
    outcome = _claude_run(tmp_path, plans)
    context = _check(outcome, "claude-code", plans)["context"]
    assert context["client_versions_before"] == 1
    assert context["client_versions_after"] == 2
    assert context["client_versions_both"] == 1


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


# --- 5. names, client versions and privacy ---------------------------------------------------
# Record 0017, "Names": nine efforts print as written, `MODEL_WORDS` gains `sol`, aliases are
# numbered per tool and kind in code-point order of the raw strings, and client versions after
# the split are the third bounded exception to the no-log-string rule.

ONE_DAY = {NEWEST: Day(counts=(5,) * 3)}


def _one_setting(tmp_path: Path, setting: Setting, **kw: Any) -> Outcome:
    """A run whose logs hold one setting on one day: enough to name the compared setting."""
    root = tmp_path / "claude"
    write_claude(root, ONE_DAY, setting=setting, **kw)
    return _run(tmp_path, _args("claude-code", claude=root))


@pytest.mark.parametrize("effort", EFFORTS)
def test_each_of_the_nine_efforts_prints_as_written(tmp_path: Path, effort: str) -> None:
    """Items 14 and 59: each of the nine efforts is admitted and shown as written."""
    outcome = _one_setting(tmp_path, Setting(CLAUDE_MODEL, effort))
    assert outcome.tool()["effort"] == effort
    assert f"effort {effort}" in outcome.out


def test_one_rejected_effort_is_effort_1_and_several_are_numbered_in_order(
    tmp_path: Path,
) -> None:
    """Item 14: with exactly one rejected effort it prints as `effort-1`; with several, each
    gets its own number, from 1 up, in code-point order of the raw strings."""
    single = _one_setting(tmp_path / "one", Setting(CLAUDE_MODEL, CANARY_EFFORT_1))
    assert single.tool()["effort"] == "effort-1"

    root = tmp_path / "two" / "claude"
    # Three raw efforts: two rejected and one accepted, written in an order that is not their
    # code-point order. The compared setting is the one with the most after-period responses.
    write_claude(root, {NEWEST: Day(counts=(5,) * 5)}, setting=Setting(CLAUDE_MODEL, "zz-canary"))
    write_claude(
        root,
        {NEWEST: Day(counts=(5,) * 4)},
        session="02",
        prefix="b",
        setting=Setting(CLAUDE_MODEL, CANARY_EFFORT_1),
    )
    write_claude(
        root,
        {NEWEST: Day(counts=(5,) * 3)},
        session="03",
        prefix="c",
        setting=Setting(CLAUDE_MODEL, "high"),
    )
    many = _run(tmp_path / "two", _args("claude-code", claude=root))
    # "canary-effort-aggressive" is before "zz-canary" in code-point order, so it is effort-1
    # and the compared setting, with more responses, is effort-2.
    assert many.tool()["effort"] == "effort-2"
    assert many.tool()["other_settings"] == 2
    for canary in (CANARY_EFFORT_1, "zz-canary"):
        assert canary not in many.out


# Six parts, one of them the date, and exactly 48 characters; one word longer makes 49.
MODEL_48 = "claude-sonnet-thinking-preview-reasoner-20260101"
MODEL_49 = "claude-sonnet-thinking-thinking-reasoner-20260101"
MODEL_SIX_PARTS = "claude-opus-sonnet-haiku-fable-mythos"
MODEL_SEVEN_PARTS = "claude-opus-sonnet-haiku-fable-mythos-instant"


@pytest.mark.parametrize(
    ("model", "accepted"),
    [
        # `sol` is new in 0017.
        ("gpt-5-sol", True),
        # 48 characters pass, 49 do not; six parts pass, seven do not.
        (MODEL_48, True),
        (MODEL_49, False),
        (MODEL_SIX_PARTS, True),
        (MODEL_SEVEN_PARTS, False),
        # Three numeric parts pass, four do not; one date passes, two do not.
        ("gpt-5-4-3", True),
        ("gpt-5-4-3-2", False),
        ("claude-opus-20260101", True),
        ("claude-20260101-20260102", False),
        # A token of two or three characters made of one letter and digits.
        ("gpt-4o-mini", True),
        ("o3-mini", True),
        ("r1-coder", True),
    ],
)
def test_model_ids_at_the_boundaries_of_the_grammar(
    tmp_path: Path, model: str, accepted: bool
) -> None:
    """Items 15 and 59: the closed grammar at its boundaries; a rejected id is `model-1`."""
    assert len(MODEL_48) == 48 and len(MODEL_49) == 49
    outcome = _one_setting(tmp_path, Setting(model, "high"))
    assert outcome.tool()["model"] == (model if accepted else "model-1")
    if not accepted:
        assert model not in outcome.out
        assert model not in outcome.json_path.read_text(encoding="utf-8")


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
    # rejected one: the rejected names must still be numbered 1 and 2. This session carries the
    # version-shaped canary too, since the version population is every response of the tool in
    # the after period, whichever session file or setting it belongs to.
    write_claude(
        root,
        {
            day: Day(counts=(1,) * 3, other=(1,) * 2, version=CANARY_VERSION)
            for day in (*BEFORE_DAYS, *AFTER_DAYS)
        },
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
    """Item 21 and the privacy rules of 0016: no string read from a log reaches an output, with
    the model, effort and after-period client-version exceptions."""
    outcome = _canary_outcome(tmp_path)
    places = {
        "stdout": outcome.out,
        "stderr": outcome.err,
        "json": outcome.json_path.read_text(encoding="utf-8"),
        "markdown": outcome.text("markdown"),
        "html": outcome.text("html"),
    }
    places["page"] = outcome.page()
    for where, text in places.items():
        for canary in CANARIES:
            assert canary not in text, (where, canary)
        for part in CANARY_PARTS:
            assert part not in text, (where, part)
    # Every session of the fixture carries the version-shaped canary, which does not match the
    # version pattern, so no after-period version matches, F26 is absent, and the one version
    # counts in `+k more` instead.
    assert "Client versions after the split" not in outcome.out
    context = outcome.tool()["context"]
    assert context["client_versions_after_shown"] == []
    assert context["client_versions_after_more"] == context["client_versions_after"] == 1


def test_unknown_model_ids_are_numbered_among_themselves_and_never_merged(
    tmp_path: Path,
) -> None:
    """Item 15: with several ids outside the grammar each gets its own number, numbered apart
    from the efforts."""
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


def _version_run(
    tmp_path: Path,
    *,
    before: Mapping[date, str],
    after: Mapping[date, str],
    more: Sequence[tuple[date, str]] = (),
    extra: Sequence[str] = (),
    outputs: Sequence[str] = (),
) -> tuple[Outcome, list[str]]:
    """A Claude Code run whose days carry the given client versions, with the after-period list.

    `more` adds further sessions, each on one day with its own version, so that a day can carry
    several versions. The returned list is every after-period version string in the logs.
    """
    plans: dict[date, Day] = {}
    for day in BEFORE_DAYS:
        plans[day] = Day(counts=(100,) * 20, version=before[day])
    for day in AFTER_DAYS:
        plans[day] = Day(counts=(10,) * 20, version=after[day])
    root = tmp_path / "claude"
    write_claude(root, plans)
    for index, (day, version) in enumerate(more):
        write_claude(
            root,
            {day: Day(counts=(10,) * 2, version=version)},
            session=f"v{index:02d}",
            prefix=f"v{index:02d}",
        )
    outcome = _run(tmp_path, _args("claude-code", claude=root, extra=extra), outputs=outputs)
    seen = [after[day] for day in AFTER_DAYS]
    seen += [version for day, version in more if day in AFTER_DAYS]
    return outcome, seen


def test_the_client_version_line(tmp_path: Path) -> None:
    """Item 16: four versions after the split print the three highest and `+1 more`; a version
    seen only before the split is never listed, one seen in both periods is."""
    before = dict.fromkeys(BEFORE_DAYS, "1.2.3")
    before[BEFORE_DAYS[-1]] = "2.1.309"
    after = {
        AFTER_DAYS[0]: "2.1.309",
        AFTER_DAYS[1]: "2.1.321",
        AFTER_DAYS[2]: "2.1.325",
        AFTER_DAYS[3]: "2.1.325",
        AFTER_DAYS[4]: "2.1.40",
    }
    outcome, seen = _version_run(tmp_path, before=before, after=after, outputs=("markdown", "html"))
    line = F26.format("2.1.325, 2.1.321, 2.1.309 +1 more")
    assert _version_line(seen) == line
    assert line in outcome.lines
    context = outcome.tool()["context"]
    assert context["client_versions_after_shown"] == ["2.1.325", "2.1.321", "2.1.309"]
    assert context["client_versions_after_more"] == 1
    assert context["client_versions_after"] == 4
    assert context["client_versions_before"] == 2
    assert context["client_versions_both"] == 1
    # The before-only version is in no output.
    for place in (outcome.out, outcome.text("markdown"), outcome.page()):
        assert "1.2.3" not in place
        _says(place, line)
    assert "1.2.3" not in outcome.json_path.read_text(encoding="utf-8")


def test_a_version_that_does_not_match_counts_in_k_and_is_never_printed(tmp_path: Path) -> None:
    """Item 16: a canary string that does not match the pattern is never printed and counts in
    `+k more`; with no matching version the line is left out."""
    before = dict.fromkeys(BEFORE_DAYS, "1.2.3")
    after = {
        AFTER_DAYS[0]: "2.1.309",
        AFTER_DAYS[1]: "2.1.321",
        AFTER_DAYS[2]: "2.1.325",
        AFTER_DAYS[3]: "2.1.40",
        AFTER_DAYS[4]: CANARY_VERSION,
    }
    outcome, seen = _version_run(tmp_path, before=before, after=after)
    line = F26.format("2.1.325, 2.1.321, 2.1.309 +2 more")
    assert _version_line(seen) == line
    assert line in outcome.lines
    assert CANARY_VERSION not in outcome.out
    assert outcome.tool()["context"]["client_versions_after_more"] == 2

    # No matching version at all: no line.
    none = dict.fromkeys(AFTER_DAYS, CANARY_VERSION)
    other, seen_none = _version_run(tmp_path / "none", before=before, after=none)
    assert _version_line(seen_none) is None
    assert "Client versions after the split" not in other.out
    assert other.tool()["context"]["client_versions_after_shown"] == []


def test_client_versions_are_ordered_as_tuples_of_integers(tmp_path: Path) -> None:
    """Item 59: `2.1.325` before `2.1.40`; two, three and four numbers match, one and five do
    not; five digits match and six do not; two non-matching strings count as two in `k`."""
    before = dict.fromkeys(BEFORE_DAYS, "1.2.3")
    after = dict.fromkeys(AFTER_DAYS, "2.1.325")
    extra = [
        (AFTER_DAYS[0], "2.1.40"),
        (AFTER_DAYS[0], "1.2.3.4"),
        (AFTER_DAYS[1], "12345.1"),
        (AFTER_DAYS[1], "123456.1"),
        (AFTER_DAYS[2], "7"),
        (AFTER_DAYS[2], "1.2.3.4.5"),
        (AFTER_DAYS[3], "1.1"),
    ]
    outcome, seen = _version_run(tmp_path, before=before, after=after, more=extra)
    shown, more = _shown_versions(seen)
    assert shown == ["12345.1", "2.1.325", "2.1.40"]
    assert more == 5
    context = outcome.tool()["context"]
    assert context["client_versions_after_shown"] == shown
    assert context["client_versions_after_more"] == more
    assert context["client_versions_after"] == 8
    assert F26.format("12345.1, 2.1.325, 2.1.40 +5 more") in outcome.lines
    # The three strings the pattern refuses are in no output.
    for refused in ("123456.1", "1.2.3.4.5"):
        assert refused not in outcome.out
        assert refused not in outcome.json_path.read_text(encoding="utf-8")


def test_equal_version_tuples_go_in_text_order(tmp_path: Path) -> None:
    """Item 59: `1.01` and `1.1` are equal tuples, so they are ordered by text."""
    before = dict.fromkeys(BEFORE_DAYS, "1.01")
    after = dict.fromkeys(AFTER_DAYS, "1.1")
    outcome, seen = _version_run(
        tmp_path, before=before, after=after, more=[(AFTER_DAYS[0], "1.01")]
    )
    assert _shown_versions(seen) == (["1.01", "1.1"], 0)
    assert F26.format("1.01, 1.1") in outcome.lines
    assert outcome.tool()["context"]["client_versions_after_shown"] == ["1.01", "1.1"]


def test_the_version_population_is_every_after_period_response_of_the_tool(
    tmp_path: Path,
) -> None:
    """Item 60: responses of other settings and sub-agent responses are included, a response
    outside the project is not, and a version seen only before the split is not listed."""
    plans: dict[date, Day] = {day: Day(counts=(100,) * 20, version="1.2.3") for day in BEFORE_DAYS}
    plans.update({day: Day(counts=(10,) * 20, version="3.3.3") for day in AFTER_DAYS})
    root = tmp_path / "claude"
    write_claude(root, plans)
    # Another setting, a sub-agent file and a session outside the project, each with its own
    # version, all on one after-day.
    write_claude(
        root,
        {AFTER_DAYS[0]: Day(counts=(10,) * 2, version="4.4.4")},
        session="02",
        prefix="o",
        setting=CLAUDE_SECOND,
    )
    write_claude(
        root,
        {AFTER_DAYS[1]: Day(sidechain=(10,) * 2, version="5.5.5")},
        session="03",
        prefix="s",
    )
    write_claude(
        root,
        {AFTER_DAYS[2]: Day(counts=(10,) * 2, version="6.6.6")},
        session="04",
        prefix="x",
        cwd="/elsewhere/other",
    )
    outcome = _run(tmp_path, _args("claude-code", claude=root, extra=("--project", WORKDIR)))
    context = outcome.tool()["context"]
    assert context["client_versions_after_shown"] == ["5.5.5", "4.4.4", "3.3.3"]
    assert context["client_versions_after_more"] == 0
    assert context["client_versions_after"] == 3
    assert F26.format("5.5.5, 4.4.4, 3.3.3") in outcome.lines
    assert "6.6.6" not in outcome.out
    assert "1.2.3" not in outcome.out


# The shapes a string in the JSON record may have, with the client-version exception that holds
# under `client_versions_after_shown` alone (record 0017, the JSON walk rule).
DATE_SHAPE = re.compile(r"\d{4}-\d{2}-\d{2}")
RATIONAL_SHAPE = re.compile(r"\d+/\d+")
DIGEST_SHAPE = re.compile(r"[0-9a-f]{64}")
VERSION_SHAPE = re.compile(r"\d+\.\d+\.\d+[0-9A-Za-z.+-]*")
CLOSED_NAMES = (
    {"arci-logs/2", "claude-code", "codex", "lower", "higher", "no_logs"}
    | set(F4)
    | set(REASONS)
    | {"streaky_days"}
    | set(MEASURES)
    | set(FILLED)
    | set(KEPT_STATES)
    | set(SOURCES)
)
RENDERED_NAMES = (
    {CLAUDE_MODEL, CLAUDE_OTHER, CODEX_MODEL, CODEX_OTHER}
    | set(EFFORTS)
    | {f"model-{index}" for index in range(1, 8)}
    | {f"effort-{index}" for index in range(1, 8)}
)


def _string_leaves(node: Any, key: str = "") -> list[tuple[str, str]]:
    if isinstance(node, str):
        return [(key, node)]
    if isinstance(node, dict):
        return [row for name, value in node.items() for row in _string_leaves(value, name)]
    if isinstance(node, list):
        return [row for value in node for row in _string_leaves(value, key)]
    return []


def test_every_string_in_the_json_is_of_an_allowed_shape(tmp_path: Path) -> None:
    """Item 54: a date, a rational, a closed-list name, a rendered name, a hex digest, or a
    version-shaped string under `client_versions_after_shown` and nowhere else."""
    outcome = _canary_outcome(tmp_path)
    assert outcome.body is not None
    for key, value in _string_leaves(outcome.body):
        if key == "arci_version":
            assert VERSION_SHAPE.fullmatch(value), value
            continue
        if key == "client_versions_after_shown":
            assert VERSION_PATTERN.fullmatch(value), value
            continue
        allowed = (
            value in CLOSED_NAMES
            or value in RENDERED_NAMES
            or DATE_SHAPE.fullmatch(value)
            or RATIONAL_SHAPE.fullmatch(value)
            or DIGEST_SHAPE.fullmatch(value)
        )
        assert allowed, (key, value)
    # The one place a version may stand holds none here, since the canary does not match.
    assert outcome.tool()["context"]["client_versions_after_shown"] == []


def test_the_version_exception_holds_under_one_key_only(tmp_path: Path) -> None:
    """Item 54: the walk accepts a version-shaped string under `client_versions_after_shown`
    and nowhere else, so a version from the before period only appears in no output."""
    before = dict.fromkeys(BEFORE_DAYS, "9.9.9")
    after = dict.fromkeys(AFTER_DAYS, "2.1.325")
    outcome, _ = _version_run(tmp_path, before=before, after=after, outputs=("markdown", "html"))
    assert outcome.body is not None
    shaped = [
        (key, value)
        for key, value in _string_leaves(outcome.body)
        if VERSION_PATTERN.fullmatch(value)
    ]
    assert {key for key, _ in shaped} <= {"client_versions_after_shown", "arci_version"}
    assert ("client_versions_after_shown", "2.1.325") in shaped
    for place in (
        outcome.out,
        outcome.text("markdown"),
        outcome.text("html"),
        outcome.json_path.read_text(encoding="utf-8"),
    ):
        assert "9.9.9" not in place


# --- 6. robustness ---------------------------------------------------------------------------
# Record 0016, "Reading faults", unchanged in 0017: lines that are not JSON, lines of an unused
# type and lines of a used type that lack a needed field are counted and left out; an unreadable
# file is counted.


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
    """LOG_FORMATS: one response is one `message.id` in a file, with the usage of its last line."""
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


def test_a_line_marked_as_not_an_api_error_is_kept(tmp_path: Path) -> None:
    """Record 0016, "Formats": `isApiErrorMessage` set to `true` excludes a line, `false` not."""
    plans = _uniform(ALTERNATING, DROPPED)
    lines: list[dict[str, Any]] = []
    for day, value in zip((*BEFORE_DAYS, *AFTER_DAYS), (*ALTERNATING, *DROPPED), strict=True):
        for index in range(20):
            lines.append(
                _assistant(
                    mid=f"ok-{day}-{index}",
                    when=_at(day, 6, index),
                    setting=Setting(),
                    reasoning=value,
                    extra={"isApiErrorMessage": False},
                )
            )
    root = tmp_path / "claude"
    _write_lines(root / PROJECT_DIR / "01.jsonl", lines)
    outcome = _run(tmp_path, _args("claude-code", claude=root))
    tool = _check(outcome, "claude-code", plans)
    assert tool["counters"]["lines_unknown_type"] == 0
    assert tool["counters"]["responses"] == 300
    assert tool["result"] == "REAL_DROP"


def test_a_path_that_is_not_a_regular_file_is_not_discovered(tmp_path: Path) -> None:
    """Record 0016, "Reading faults": such a path is counted nowhere.

    A directory and a dangling symbolic link stand in for the cases that can be made without
    risk; a pipe is left out because an implementation that opened one would block instead of
    failing, and a hanging test says less than a failing one.
    """
    root = tmp_path / "claude"
    plans = _uniform(ALTERNATING, DROPPED)
    write_claude(root, plans, session="01")
    (root / PROJECT_DIR / "02.jsonl").mkdir()
    (root / PROJECT_DIR / "03.jsonl").symlink_to(root / PROJECT_DIR / "missing.jsonl")
    outcome = _run(tmp_path, _args("claude-code", claude=root))
    tool = _check(outcome, "claude-code", plans)
    assert tool["counters"]["files_read"] == 1
    assert tool["counters"]["files_unreadable"] == 0
    assert F17_ERROR.split("{")[0] not in outcome.out


def test_a_line_that_is_not_valid_utf8_is_only_a_line_that_is_not_json(tmp_path: Path) -> None:
    root = tmp_path / "claude"
    plans = _uniform(ALTERNATING, DROPPED)
    path = write_claude(root, plans, session="01")
    path.write_bytes(b"\xff\xfe not valid utf-8 \x80\n" + path.read_bytes())
    outcome = _run(tmp_path, _args("claude-code", claude=root))
    tool = _check(outcome, "claude-code", plans)
    assert tool["counters"]["files_unreadable"] == 0
    assert tool["counters"]["files_read"] == 1
    assert tool["counters"]["lines_not_json"] == 1
    assert tool["counters"]["lines"] == 301


def test_a_byte_order_mark_at_the_start_of_a_file_is_ignored(tmp_path: Path) -> None:
    root = tmp_path / "claude"
    plans = _uniform(ALTERNATING, DROPPED)
    path = write_claude(root, plans, session="01")
    path.write_bytes(b"\xef\xbb\xbf" + path.read_bytes())
    outcome = _run(tmp_path, _args("claude-code", claude=root))
    tool = _check(outcome, "claude-code", plans)
    assert tool["counters"]["lines_not_json"] == 0
    assert tool["counters"]["lines"] == 300
    assert tool["counters"]["responses"] == 300


def test_a_timestamp_before_the_year_2000_is_a_missing_field(tmp_path: Path) -> None:
    """Record 0016: a timestamp before 2000 or after 2200 is treated as a missing field."""
    base = _uniform(ALTERNATING, DROPPED)
    stray = _assistant(
        mid="ancient-1", when=_at(date(1999, 12, 31)), setting=Setting(), reasoning=5
    )
    plans = {**base, NEWEST: Day(counts=base[NEWEST].counts, extra=(stray,))}
    outcome = _claude_run(tmp_path, plans)
    tool = _check(outcome, "claude-code", plans)
    assert tool["counters"]["lines_lacking_field"] == 1
    assert tool["counters"]["records_in_future"] == 0
    assert F15.format(1) in outcome.lines


def test_a_codex_token_count_that_repeats_the_cumulative_usage_is_a_duplicate(
    tmp_path: Path,
) -> None:
    """Record 0016: a repeat within one file is counted and left out, whatever its timestamp."""
    root = tmp_path / "codex"
    plans = _codex_no_drop()
    write_codex(root, plans)
    path = root / "sessions" / "2026" / "11" / "10" / f"rollout-{NEWEST}.jsonl"
    rows = path.read_text(encoding="utf-8").splitlines()
    repeat = {**json.loads(rows[-1]), "timestamp": _at(NEWEST, 9, 0)}
    path.write_text("\n".join([*rows, json.dumps(repeat)]) + "\n", encoding="utf-8")
    outcome = _run(tmp_path, _args("codex", codex=root))
    tool = _check(outcome, "codex", plans)
    assert tool["counters"]["responses_duplicate"] == 1
    assert tool["counters"]["responses"] == 300
    # Kept, the repeat would make the newest day hold 21 positive counts.
    assert tool["measures"][0]["after_days"][-1]["count"] == 20


# --- 7. the record ---------------------------------------------------------------------------
# Record 0017, "Record model". `_audit` checks the field sets, the null rules, the ascending day
# lists, one source per day, the kept-day and response-day bounds, the earliest test date, the
# shown versions, the digest and the seal on every run in this file.


def _kept_run(
    tmp_path: Path,
    logs: Mapping[date, Day],
    rows: Sequence[Mapping[str, Any]] | None,
    *,
    tool: str = "claude-code",
    extra: Sequence[str] = (),
    outputs: Sequence[str] = (),
    stem: str = "decision",
    now: datetime = NOW,
    store: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> tuple[Outcome, Path]:
    """A run whose table directory is `$REALORNOISE_HOME`, with `rows` stored there first.

    The table is read on every run when the file exists, with or without `--keep` (record 0017,
    "Reading"). `rows` of None leaves no file, so `kept_table` is `absent`.
    """
    place = (tmp_path / "store") if store is None else store
    if rows is not None:
        write_kept(place / TABLE_NAME, rows)
    root = tmp_path / tool
    if tool == "claude-code":
        write_claude(root, logs)
        argv = _args("claude-code", claude=root, extra=extra)
    else:
        write_codex(root, logs)
        argv = _args("codex", codex=root, extra=extra)
    settings = {"REALORNOISE_HOME": str(place)} if env is None else dict(env)
    outcome = _run(tmp_path, argv, outputs=outputs, stem=stem, now=now, env=settings)
    return outcome, place / TABLE_NAME


def test_the_record_carries_the_version_of_the_header_and_a_valid_seal(tmp_path: Path) -> None:
    """Item 1: the fields of the record model, no more and no fewer, at every level; item 66:
    the seal is `hash_record` of the record without `seal`."""
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
    assert outcome.body["since_given"] is False
    assert outcome.body["keep"] is False
    # With an isolated home and no `REALORNOISE_HOME`, the table's path does not exist.
    assert outcome.body["kept_table"] == "absent"
    tool = outcome.tool()
    assert tool["before"] == BEFORE_PERIOD
    assert tool["after"] == AFTER_PERIOD
    assert tool["other_settings"] == 0
    assert tool["first_response_day"] == BEFORE_DAYS[0].isoformat()
    assert (tool["response_days_before"], tool["response_days_after"]) == (10, 5)
    assert (tool["kept_days_before"], tool["kept_days_after"]) == (0, 0)
    assert tool["kept_rows_other_offset"] == 0
    assert (tool["settings_not_kept"], tool["days_not_kept"]) == (0, 0)
    assert tool["earliest_test_date"] is None
    assert {row["source"] for row in tool["measures"][0]["before_days"]} == {"logs"}


def _v1_record() -> dict[str, Any]:
    """A record as 2.3.0 wrote it: the 0016 model, `arci-logs/1`, and no field of 0017.

    The measures are computed by this file's own enumeration, so the 0016 validator that
    recomputes `p_streak`, `p_real`, `u_none` and `p_none` must accept them.
    """
    tokens_before = [
        (day, 20, Fraction(value), None)
        for day, value in zip(BEFORE_DAYS, ALTERNATING, strict=True)
    ]
    tokens_after = [
        (day, 20, Fraction(value), None) for day, value in zip(AFTER_DAYS, DROPPED, strict=True)
    ]
    zeros_before = [(day, 20, Fraction(0), None) for day in BEFORE_DAYS]
    zeros_after = [(day, 20, Fraction(0), None) for day in AFTER_DAYS]
    tool: dict[str, Any] = {
        "tool": "claude-code",
        "result": "REAL_DROP",
        "reason": "real_drop",
        "model": CLAUDE_MODEL,
        "effort": "high",
        "other_settings": 0,
        "split_date": SPLIT.isoformat(),
        "before": dict(BEFORE_PERIOD),
        "after": dict(AFTER_PERIOD),
        "measures": [
            _expect_measure("reasoning_tokens", tokens_before, tokens_after),
            _expect_measure("no_reasoning_share", zeros_before, zeros_after),
            _expect_measure("edit_failure_share", [], []),
        ],
        "context": {
            "client_versions_before": 1,
            "client_versions_after": 1,
            "client_versions_both": 1,
            "workdirs_before": 1,
            "workdirs_after": 1,
            "subagent_share_before": "0/1",
            "subagent_share_after": "0/1",
        },
        "counters": dict.fromkeys(sorted(COUNTER_FIELDS), 0),
        "day_table_sha256": None,
    }
    tool["counters"]["files_read"] = 1
    tool["counters"]["lines"] = 300
    tool["counters"]["responses"] = 300
    tool["day_table_sha256"] = hash_record(_day_table(tool, method="arci-logs/1"))
    body: dict[str, Any] = {
        "schema_version": "arci-logs/1",
        "arci_version": "2.3.0",
        "example": False,
        "utc_offset_minutes": 0,
        "project_filtered": False,
        "tools": [tool],
        "exit_code": 1,
    }
    body["seal"] = hash_record({name: value for name, value in body.items() if name != "seal"})
    return body


def test_an_arci_logs_1_record_still_validates() -> None:
    """Item 2: a record of `arci-logs/1` written by 2.3.0 still validates, under
    `arci.logs.schema.LogsDecisionV1.model_validate`, field for field."""
    body = _v1_record()
    restored = LogsDecisionV1.model_validate(body)
    assert restored is not None
    # The 0016 shapes: no field of 0017 anywhere, and a day value without a source.
    tool = body["tools"][0]
    assert set(tool["context"]) == CONTEXT_FIELDS_V1
    assert set(tool["measures"][0]["before_days"][0]) == DAY_FIELDS_V1
    # The `arci-logs/2` model is a different kind and does not accept it.
    with pytest.raises(ValidationError):
        LogsDecision.model_validate(body)


@pytest.mark.parametrize("name", ["no_logs", "format_not_recognised", "no_usable_setting"])
def test_an_error_or_a_missing_setting_nulls_the_same_fields(tmp_path: Path, name: str) -> None:
    """Item 68: an ERROR record and a `no_usable_setting` record carry the fields the record
    model requires, and no digest is made up."""
    root = tmp_path / "claude"
    root.mkdir()
    _ladder_logs(name, root)
    outcome = _run(tmp_path, _args("claude-code", claude=root))
    tool = outcome.tool()
    assert tool["measures"] == []
    for name_of in (
        "model",
        "effort",
        "before",
        "after",
        "context",
        "day_table_sha256",
        "first_response_day",
        "earliest_test_date",
    ):
        assert tool[name_of] is None, name_of
    for name_of in (
        "response_days_before",
        "response_days_after",
        "kept_days_before",
        "kept_days_after",
    ):
        assert tool[name_of] == 0, name_of
    if name == "no_usable_setting":
        # The split is kept whenever the tool has a main-thread response.
        assert tool["split_date"] == SPLIT.isoformat()
        assert tool["counters"]["responses_without_setting"] == 300
        assert tool["counters"]["responses"] == 0
    else:
        assert tool["split_date"] is None
        assert tool["kept_rows_other_offset"] == 0
    # No digest is made up when there is no day table, so there is no method line.
    assert "method arci-logs/2" not in outcome.out


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


def test_the_payload_of_the_day_table_digest(tmp_path: Path) -> None:
    """Item 66: `day_table_sha256` is `hash_record` of exactly the payload of "Record model",
    in its order, and changing any one field of the payload changes the digest."""
    plans = _uniform(ALTERNATING, DROPPED)
    outcome = _claude_run(tmp_path, plans)
    tool = outcome.tool()
    payload = _day_table(tool)
    assert tool["day_table_sha256"] == hash_record(payload)
    assert set(payload) == {
        "method",
        "tool",
        "model",
        "effort",
        "split_date",
        "before",
        "after",
        "alpha_real",
        "alpha_none",
        "measures",
    }
    assert set(payload["measures"][0]) == {"id", "margin", "before_days", "after_days"}
    for name, value in (
        ("method", "arci-logs/1"),
        ("tool", "codex"),
        ("model", CLAUDE_OTHER),
        ("effort", "low"),
        ("split_date", "2026-10-27"),
        ("alpha_real", "1/40"),
        ("alpha_none", "1/120"),
    ):
        changed = {**payload, name: value}
        assert hash_record(changed) != tool["day_table_sha256"], name
    # The day values, with their sources, are part of it.
    days = payload["measures"][0]["before_days"]
    measures = [dict(measure) for measure in payload["measures"]]
    measures[0]["before_days"] = [{**days[0], "source": "kept"}, *days[1:]]
    assert hash_record({**payload, "measures": measures}) != tool["day_table_sha256"]


SourceCase = tuple[Outcome, dict[date, Day], dict[date, str]]


def _source_case(tmp_path: Path, *, day: date = BEFORE_DAYS[0]) -> SourceCase:
    """A run in which one before-day comes from the kept table and nothing else differs.

    The stored row holds the same day value and the same positive count as the logs row, with
    one response more whose reasoning count is unknown: its pair is larger, so the kept row is
    used, and the day's `DayValue` differs in `source` alone.
    """
    logs = _uniform(ALTERNATING, DROPPED)
    kept_plan = Day(counts=(*logs[day].counts, None))
    merged, sources = _merge("claude-code", logs, {day: kept_plan})
    outcome, _ = _kept_run(tmp_path, logs, [_kept_from_day("claude-code", day, kept_plan)])
    return outcome, merged, sources


def test_the_digest_changes_when_only_a_days_source_changes(tmp_path: Path) -> None:
    """Item 36: every `DayValue` carries `source`, and the day-table digest changes when one
    day's source changes and nothing else does."""
    kept_out, merged, sources = _source_case(tmp_path / "kept")
    plain = _claude_run(tmp_path / "plain", _uniform(ALTERNATING, DROPPED))
    kept_tool = _check(kept_out, "claude-code", merged, sources=sources)
    assert kept_out.body is not None and kept_out.body["kept_table"] == "read"
    assert (kept_tool["kept_days_before"], kept_tool["kept_days_after"]) == (1, 0)
    # The two runs differ in one day's source and in nothing else.
    stripped = [
        [
            {name: value for name, value in row.items() if name != "source"}
            for side in ("before_days", "after_days")
            for row in measure[side]
        ]
        for measure in kept_tool["measures"]
    ]
    plain_stripped = [
        [
            {name: value for name, value in row.items() if name != "source"}
            for side in ("before_days", "after_days")
            for row in measure[side]
        ]
        for measure in plain.tool()["measures"]
    ]
    assert stripped == plain_stripped
    assert kept_tool["day_table_sha256"] != plain.tool()["day_table_sha256"]
    assert F21.format(b=1, a=0) in kept_out.lines


def _reseal(body: dict[str, Any]) -> dict[str, Any]:
    """Recompute the digests the record stores, so that one targeted validator is the one left."""
    for tool in body["tools"]:
        if tool["day_table_sha256"] is not None:
            tool["day_table_sha256"] = hash_record(_day_table(tool))
    body.pop("seal", None)
    body["seal"] = hash_record(dict(body))
    return body


def _flip_source(body: dict[str, Any]) -> dict[str, Any]:
    """Give one day two different sources, in two measures that both list it."""
    tool = body["tools"][0]
    first, second = tool["measures"][0], tool["measures"][1]
    shared = {row["day"] for row in first["before_days"]} & {
        row["day"] for row in second["before_days"]
    }
    day = sorted(shared)[0]
    for row in second["before_days"]:
        if row["day"] == day:
            row["source"] = "kept" if row["source"] == "logs" else "logs"
    return body


def test_the_record_model_rejects_a_day_with_two_sources(tmp_path: Path) -> None:
    """Item 37: a record in which two measures give one day different sources is rejected with
    reason `inconsistent_day_source`."""
    outcome, _, _ = _source_case(tmp_path)
    assert outcome.body is not None
    body = _reseal(_flip_source(json.loads(json.dumps(outcome.body))))
    with pytest.raises(ValidationError) as raised:
        LogsDecision.model_validate(body)
    assert "inconsistent_day_source" in str(raised.value)


def _edit(body: Mapping[str, Any], **over: Any) -> dict[str, Any]:
    copy = json.loads(json.dumps(body))
    tool = copy["tools"][0]
    for name, value in over.items():
        if name in copy:
            copy[name] = value
        else:
            tool[name] = value
    return _reseal(copy)


def test_the_record_model_rejects_the_kept_day_counts_and_the_states(tmp_path: Path) -> None:
    """Items 37 and 67: `kept_days_before` below the distinct kept before-days or above the
    days of the period; `source: "kept"` with `kept_table` other than `read`; `kept_table`
    `not_read` with `keep` true."""
    kept_out, _, _ = _source_case(tmp_path / "kept")
    assert kept_out.body is not None
    for over in (
        {"kept_days_before": 0},
        {"kept_days_before": 999},
        {"kept_days_after": 999},
    ):
        with pytest.raises(ValidationError):
            LogsDecision.model_validate(_edit(kept_out.body, **over))
    with pytest.raises(ValidationError):
        LogsDecision.model_validate(_edit(kept_out.body, kept_table="absent"))

    # `kept_table` is `not_read` only when `keep` is false, since a run that writes also reads.
    plain = _claude_run(tmp_path / "plain", _uniform(ALTERNATING, DROPPED))
    assert plain.body is not None
    with pytest.raises(ValidationError):
        LogsDecision.model_validate(_edit(plain.body, kept_table="not_read", keep=True))


def test_the_record_model_rejects_a_wrong_earliest_test_date(tmp_path: Path) -> None:
    """Item 37: an `earliest_test_date` that differs from its recomputation is rejected."""
    outcome = _claude_run(tmp_path, _uniform(ALTERNATING, HELD[:4], after_days=AFTER_DAYS[1:]))
    assert outcome.body is not None
    tool = outcome.tool()
    assert tool["earliest_test_date"] is not None
    moved = date.fromisoformat(tool["earliest_test_date"]) + timedelta(days=1)
    with pytest.raises(ValidationError):
        LogsDecision.model_validate(_edit(outcome.body, earliest_test_date=moved.isoformat()))


def test_the_record_model_rejects_the_day_and_version_bounds(tmp_path: Path) -> None:
    """Item 67, one case each: a `first_response_day` outside the window or later than a stored
    usable day; a `response_days_before` below the distinct before-days of one of the three
    response measures; a `client_versions_after_shown` out of order; and a shown list plus
    `client_versions_after_more` that does not equal `client_versions_after`."""
    before = dict.fromkeys(BEFORE_DAYS, "1.2.3")
    after = {day: "2.1.325" for day in AFTER_DAYS}
    after[AFTER_DAYS[0]] = "2.1.40"
    outcome, _ = _version_run(tmp_path, before=before, after=after)
    assert outcome.body is not None
    tool = outcome.tool()
    assert tool["context"]["client_versions_after_shown"] == ["2.1.325", "2.1.40"]
    outside = (date.fromisoformat(tool["before"]["first_day"]) - timedelta(days=1)).isoformat()
    later = (date.fromisoformat(tool["first_response_day"]) + timedelta(days=1)).isoformat()
    for over in (
        {"first_response_day": outside},
        {"first_response_day": later},
        {"response_days_before": 1},
    ):
        with pytest.raises(ValidationError):
            LogsDecision.model_validate(_edit(outcome.body, **over))
    for shown, more in ((["2.1.40", "2.1.325"], 0), (["2.1.325"], 0)):
        body = json.loads(json.dumps(outcome.body))
        context = body["tools"][0]["context"]
        context["client_versions_after_shown"] = shown
        context["client_versions_after_more"] = more
        with pytest.raises(ValidationError):
            LogsDecision.model_validate(_reseal(body))


def test_the_record_model_rejects_filled_fields_without_a_setting(tmp_path: Path) -> None:
    """Item 67: a non-null `model`, `before`, `context` or `day_table_sha256` with ERROR or
    `no_usable_setting`."""
    root = tmp_path / "claude"
    root.mkdir()
    _ladder_logs("no_usable_setting", root)
    blank = _run(tmp_path, _args("claude-code", claude=root))
    assert blank.body is not None
    rich = _claude_run(tmp_path / "rich", _uniform(ALTERNATING, DROPPED))
    assert rich.body is not None
    filled = rich.tool()
    for over in (
        {"model": CLAUDE_MODEL},
        {"before": dict(BEFORE_PERIOD)},
        {"context": filled["context"]},
        {"day_table_sha256": filled["day_table_sha256"]},
    ):
        body = json.loads(json.dumps(blank.body))
        body["tools"][0].update(over)
        body.pop("seal", None)
        body["seal"] = hash_record(dict(body))
        with pytest.raises(ValidationError):
            LogsDecision.model_validate(body)


ROUND_TRIP = (
    "not_read",
    "absent",
    "read",
    "unreadable",
    "since",
    "keep",
    "two_tools",
)


@pytest.mark.parametrize("state", ROUND_TRIP)
def test_every_new_state_round_trips(tmp_path: Path, state: str) -> None:
    """Item 69: the record is written and validated again from its JSON, and the text, Markdown
    and HTML of a second run on the same inputs are the same.

    The record names rendering "from the restored record"; nothing public renders a record, so
    the plainest check from outside is that the three forms are a function of the record: two
    runs on the same logs, table and options give the same three texts, and the stored record
    validates again under the model.
    """
    logs = _uniform(ALTERNATING, DROPPED)
    rows: Sequence[Mapping[str, Any]] | None = None
    extra: tuple[str, ...] = ()
    sources: dict[date, str] | None = None
    plans: Mapping[date, Day] = logs
    if state == "not_read":
        extra = ("--ignore-kept",)
        rows = [_kept_from_day("claude-code", BEFORE_DAYS[0], Day(counts=(300,) * 25))]
    elif state == "read":
        kept_plan = Day(counts=(300,) * 25)
        rows = [_kept_from_day("claude-code", BEFORE_DAYS[0], kept_plan)]
        plans, sources = _merge("claude-code", logs, {BEFORE_DAYS[0]: kept_plan})
    elif state == "unreadable":
        rows = [_kept_from_day("claude-code", BEFORE_DAYS[0], Day(counts=(300,) * 25))]
    elif state == "since":
        extra = ("--since", "2026-11-01")
    elif state == "keep":
        # `--keep` writes the table after the run and a table that exists is read on every run,
        # so two successive `--keep` runs need not have the same inputs. The table written here
        # holds one row the write rule keeps (its pair is larger) and one row per other day
        # whose pair ties with the logs row, so the write leaves every row as it is and both
        # runs read the same table.
        extra = ("--keep",)
        kept_days = {
            day: (Day(counts=(300,) * 25) if day == BEFORE_DAYS[0] else logs[day])
            for day in (*BEFORE_DAYS, *AFTER_DAYS)
        }
        rows = [_kept_from_day("claude-code", day, plan) for day, plan in kept_days.items()]
        plans, sources = _merge("claude-code", logs, kept_days)
    store = tmp_path / "store"
    if state == "unreadable":
        write_kept(store / TABLE_NAME, rows or [], schema="realornoise-days/9")
        rows = None
    claude_root = tmp_path / "claude-code"
    if state == "two_tools":
        # A tool with no usable setting beside a tool with a result.
        write_codex(tmp_path / "codex", _codex_no_drop(), setting=Setting(CODEX_MODEL, None))
        write_claude(claude_root, logs)
        if rows is not None:
            write_kept(store / TABLE_NAME, rows)
        argv = _args("both", claude=claude_root, codex=tmp_path / "codex")
        settings = {"REALORNOISE_HOME": str(store)}
        first = _run(tmp_path, argv, outputs=("markdown", "html"), stem="one", env=settings)
        second = _run(tmp_path, argv, outputs=("markdown", "html"), stem="two", env=settings)
    else:
        first, _ = _kept_run(
            tmp_path,
            logs,
            rows,
            extra=extra,
            outputs=("markdown", "html"),
            stem="one",
            store=store,
        )
        second = _run(
            tmp_path,
            _args("claude-code", claude=claude_root, extra=extra),
            outputs=("markdown", "html"),
            stem="two",
            env={"REALORNOISE_HOME": str(store)},
        )
    assert first.body is not None and second.body is not None
    LogsDecision.model_validate(first.body)
    assert first.out == second.out
    for name in ("markdown", "html"):
        assert first.text(name) == second.text(name)
    assert first.body["tools"] == second.body["tools"]
    wanted = {
        "not_read": "not_read",
        "absent": "absent",
        "read": "read",
        "unreadable": "unreadable",
        "since": "absent",
        "keep": "read",
        "two_tools": "absent",
    }[state]
    assert first.body["kept_table"] == wanted
    assert first.body["since_given"] is (state == "since")
    assert first.body["keep"] is (state == "keep")
    if sources is not None:
        _check(first, "claude-code", plans, sources=sources)
    if state == "keep":
        # Neither run changed the table, so both had the same inputs.
        assert rows is not None
        assert _rows(store / TABLE_NAME) == sorted(rows, key=_row_key)
    if state == "two_tools":
        assert [tool["reason"] for tool in first.tools()] == ["real_drop", "no_usable_setting"]


# --- 8. the fixed texts ----------------------------------------------------------------------
# Record 0017, "Fixed texts" and "Text output, in this order". Every line of every run in this
# file is checked against the 100-character limit and the ASCII rule by `_raw_run`.


def test_the_fixed_lines_of_a_run_with_a_result(tmp_path: Path) -> None:
    """Item 41: F11 and the footer name `arci-logs/2`; the F10 lines print as the record gives
    them, with the two self-check figures filled in."""
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
        "method arci-logs/2 · exact rank tests · no random numbers · day-table digest "
        f"{digest[:12]}" in lines
    )
    _f10_block(outcome)
    _says(outcome.out, F10_FIRST_SENTENCE)
    _says(outcome.out, F10_THIRD_SENTENCE)
    assert F12 in lines
    assert lines[-1] == "exit 0"
    assert outcome.err == ""
    # Every notice count is zero here, and no table was read, so no notice and no F21 print.
    for notice in NOTICES:
        assert notice.split("{")[0] not in outcome.out
    assert "Days from the kept table" not in outcome.out
    assert "The kept day table could not be read" not in outcome.out
    # No `too_few_days` lines and no client-version line, since this run has neither.
    for absent in ("This setting: first response", "Earliest test date", "Claude Code deletes"):
        assert absent not in outcome.out
    # The table names every gating measure of this tool and no other, with its own finding.
    for measure in tool["measures"]:
        _says(outcome.out, ROW_NAMES[measure["id"]])
        _says(outcome.out, _row_finding(measure, tool["reason"]))
    assert ROW_NAMES["repeated_value_share"] not in outcome.out
    assert "not used" not in outcome.out


def test_the_closing_paragraph_and_the_footer_carry_the_same_figure(
    tmp_path: Path,
) -> None:
    """Item 5 of the decision list and item 40 in part: the closing paragraph states the
    assumption first and then one measured figure with its design, and the footer carries a
    short form of the same three values. The numbers come from the self-check file at build
    time; this holds the words around them, the shape of the rate, that the two day counts are
    whole numbers of days, and that all three forms agree."""
    plans = _uniform(ALTERNATING, DROPPED)
    root = tmp_path / "claude"
    write_claude(root, plans)
    outcome = _run(tmp_path, _args("claude-code", claude=root), outputs=("markdown", "html"))
    figures = _f10_block(outcome)
    assert figures == _figures(outcome.out)
    assert figures == _figures(outcome.page())
    assert figures == _footer_figures(outcome.text("markdown"))
    # The page holds the same paragraph, where no line limit applies.
    _says(outcome.page(), _filled(F10_TEXT, figures))
    digest = outcome.tool()["day_table_sha256"][:12]
    _says(outcome.text("markdown"), FOOTER_METHOD.format(digest=digest))
    # The two figures of the first form of this record, and the 0016 wording, are gone.
    _absent(outcome.out, "For each tool above and one comparison: if nothing shifted")
    _absent(outcome.out, "with 5 days after the split and 10 before")
    _absent(outcome.out, "stronger streaks can give more")
    _absent(outcome.text("markdown"), "only under unchecked assumptions")
    _absent(outcome.text("markdown"), "(5 days after, 10 before)")
    _absent(outcome.text("markdown"), "arci-logs/1")
    _absent(outcome.text("markdown"), "Yours: uvx realornoise")


def _too_few_days_plans(shape: str) -> dict[date, Day]:
    """Four shapes of `too_few_days`, one per earliest-date case of item 11."""
    if shape == "next_day":
        return _uniform(ALTERNATING, HELD[:4], after_days=AFTER_DAYS[1:])
    if shape == "middle":
        return _uniform(ALTERNATING, HELD[:2], after_days=AFTER_DAYS[3:])
    if shape == "before_days":
        plans = _uniform(ALTERNATING, MIDDLE)
        # One before-day holds 19 known counts, so nine before-days are usable: the after-days
        # are already enough and the before-days become enough only as the window slides.
        plans[BEFORE_DAYS[0]] = Day(counts=(100,) * 19)
        return plans
    # No usable day at all for any measure: one response a day.
    return _uniform(ALTERNATING, DROPPED, responses=1)


EARLIEST = {
    "next_day": (date(2026, 11, 11), 10, 4),
    "middle": (date(2026, 11, 13), 10, 2),
    "before_days": (date(2026, 11, 20), 10, 5),
    "none": (date(2026, 12, 4), 10, 5),
}


@pytest.mark.parametrize("shape", sorted(EARLIEST))
def test_the_earliest_test_date_and_the_compared_setting_lines(tmp_path: Path, shape: str) -> None:
    """Items 10 and 11: under `too_few_days` the output shows the first response day and the
    days with a response in each period, and F19 prints the date of the rule, which the record
    also holds in `earliest_test_date`.

    The four cases are the date `N+1`, a middle date, the date at which the before-days (not the
    after-days) become enough, and the date exactly `N+24` with no usable day at all.
    """
    plans = _too_few_days_plans(shape)
    root = tmp_path / "claude"
    write_claude(root, plans)
    outcome = _run(tmp_path, _args("claude-code", claude=root), outputs=("markdown", "html"))
    tool = outcome.tool()
    assert (tool["result"], tool["reason"]) == ("CANNOT_TELL", "too_few_days")
    wanted, before_days, after_days = EARLIEST[shape]
    assert tool["earliest_test_date"] == wanted.isoformat()
    assert tool["earliest_test_date"] == _earliest_test_date(tool).isoformat()
    assert tool["first_response_day"] == BEFORE_DAYS[0].isoformat()
    assert tool["response_days_before"] == before_days
    assert tool["response_days_after"] == after_days

    first = F18.format(first=BEFORE_DAYS[0].isoformat(), b=before_days, a=after_days)
    date_line = F19[0].format(last=NEWEST.isoformat(), date=wanted.isoformat())
    _block(outcome, first)
    _run_of(outcome, [date_line, *_wrapped(F19[1])])
    for place in (outcome.text("markdown"), outcome.page()):
        _says(place, first)
        _says(place, date_line)
        _says(place, F19[1])


@pytest.mark.parametrize("shape", ["since", "not_enough_evidence", "streaky_days", "no_drop"])
def test_no_compared_setting_lines_outside_too_few_days(tmp_path: Path, shape: str) -> None:
    """Item 12: with `--since`, or with any reason other than `too_few_days`, F19 is absent and
    `earliest_test_date` is null; `not_enough_evidence` and `streaky_days` print no F18, F19 or
    F20."""
    extra: tuple[str, ...] = ()
    if shape == "since":
        plans = _uniform(ALTERNATING, HELD[:4], after_days=AFTER_DAYS[1:])
        extra = ("--since", SPLIT.isoformat())
    elif shape == "not_enough_evidence":
        plans = _uniform(SPREAD, MIDDLE)
    elif shape == "streaky_days":
        plans = _uniform(RISING, MIDDLE)
    else:
        plans = _uniform(ALTERNATING, HELD, edits=(False,) * 10)
    root = tmp_path / "claude"
    write_claude(root, plans)
    outcome = _run(
        tmp_path,
        _args("claude-code", claude=root, extra=extra),
        outputs=("markdown", "html"),
    )
    tool = outcome.tool()
    assert tool["earliest_test_date"] is None
    for place in (outcome.out, outcome.text("markdown"), outcome.page()):
        assert "Earliest test date" not in place
        if shape != "since":
            assert "This setting: first response" not in place
            assert "Claude Code deletes session files" not in place
    if shape == "since":
        # The reason is still `too_few_days`, so F18 and F20 print; only F19 is left out.
        assert tool["reason"] == "too_few_days"
        _says(outcome.out, "This setting: first response in the window")
        _says(outcome.out, F20[0])


def test_f20_is_claude_code_only_and_follows_the_name_rules(tmp_path: Path) -> None:
    """Item 13: F20 prints for Claude Code under `too_few_days` and never for Codex; with a
    compared setting whose model id fails the grammar it prints the same two lines."""
    plans = _uniform(ALTERNATING, HELD[:4], after_days=AFTER_DAYS[1:])
    claude = _claude_run(tmp_path / "claude-side", plans)
    assert claude.tool()["reason"] == "too_few_days"
    _run_of(claude, [*_wrapped(F20[0]), *_wrapped(F20[1])])

    codex = _codex_run(tmp_path / "codex-side", plans)
    assert codex.tool()["reason"] == "too_few_days"
    assert "Claude Code deletes session files" not in codex.out
    _says(codex.out, "This setting: first response in the window")

    rejected = _claude_run(tmp_path / "rejected", plans, setting=Setting(CANARY_MODEL_A, "high"))
    assert rejected.tool()["model"] == "model-1"
    _run_of(rejected, [*_wrapped(F20[0]), *_wrapped(F20[1])])


LONG_VERSIONS = ("99999.99999.99999.99999", "99998.99999.99999.99999", "99997.99999.99999.99999")


def test_the_longest_values_still_keep_every_line_to_100_characters(tmp_path: Path) -> None:
    """Item 38: with F18, F19, F20 and F26 at their longest values every text line is at most
    100 characters, and F26 is broken by the wrapping rule when it passes 100."""
    plans = _uniform(ALTERNATING, HELD[:4], after_days=AFTER_DAYS[1:])
    before = dict.fromkeys(BEFORE_DAYS, "1.2.3")
    root = tmp_path / "claude"
    for day in BEFORE_DAYS:
        plans[day] = Day(counts=plans[day].counts, version=before[day])
    for index, day in enumerate(AFTER_DAYS[1:]):
        plans[day] = Day(counts=plans[day].counts, version=LONG_VERSIONS[min(index, 2)])
    write_claude(root, plans)
    # Four further versions on one after-day, so that `k` is 4 and the line is at its longest.
    for index, version in enumerate(("1.1", "1.2", "1.3", "1.4")):
        write_claude(
            root,
            {AFTER_DAYS[1]: Day(counts=(5,) * 2, version=version)},
            session=f"w{index}",
            prefix=f"w{index}",
        )
    outcome = _run(tmp_path, _args("claude-code", claude=root))
    tool = outcome.tool()
    assert tool["reason"] == "too_few_days"
    assert tool["context"]["client_versions_after_shown"] == list(LONG_VERSIONS)
    line = F26.format(f"{', '.join(LONG_VERSIONS)} +4 more")
    assert len(line) > 100
    _run_of(outcome, _wrapped(line))
    # `_raw_run` has already held every line of this run to 100 characters and to ASCII.
    assert max(len(one) for one in outcome.lines) <= 100


def test_the_order_of_the_new_lines_in_every_format(tmp_path: Path) -> None:
    """Item 70: F18 to F26 print where "Text output, in this order" and the Markdown and HTML
    rules put them, and F21 prints its zeros."""
    logs = _uniform(ALTERNATING, HELD[:4], after_days=AFTER_DAYS[1:])
    plans = {
        day: Day(counts=plan.counts, other=(1,) * 2, version="2.1.325")
        for day, plan in logs.items()
    }
    rows = [
        _kept_from_day("claude-code", BEFORE_DAYS[0], plans[BEFORE_DAYS[0]], offset=330),
    ]
    outcome, _ = _kept_run(tmp_path, plans, rows, outputs=("markdown", "html"))
    tool = outcome.tool()
    assert tool["reason"] == "too_few_days"
    assert tool["kept_rows_other_offset"] == 1
    text = outcome.lines

    def place(wanted: str) -> int:
        for index, line in enumerate(text):
            if _flat(wanted) in _flat(line):
                return index
        raise AssertionError(wanted)

    order = [
        "Claude Code · claude-opus-4-20250514 · effort high",
        "before  2026-08-05",
        "after   2026-10-28",
        "RESULT: CANNOT TELL",
        REASONS["too_few_days"][:60],
        "This setting: first response in the window",
        "Earliest test date if this setting is used",
        "It also needs each such day usable",
        F20[0][:60],
        F20[1][:60],
        "measure, median day",
        "Context counts; differences between the periods",
        "client versions",
        "Client versions after the split: 2.1.325",
        F21.format(b=0, a=0),
        F14.format(1),
        F25.format(1),
        "method arci-logs/2",
    ]
    places = [place(line) for line in order]
    assert places == sorted(places), order[places.index(min(places))]
    # The Markdown block puts the same lines in its own order.
    block = outcome.text("markdown")
    wanted = [
        "measure, median day",
        "Client versions after the split: 2.1.325",
        "This setting: first response in the window",
        "Earliest test date if this setting is used",
        F21.format(b=0, a=0),
        F14.format(1),
        MARKDOWN_CLOSE["CANNOT_TELL"],
        FOOTER_FIRST_WORDS,
    ]
    found = [_flat(block).index(_flat(one)) for one in wanted]
    assert found == sorted(found), wanted
    # The HTML page holds the same information, after its character references are resolved.
    page = outcome.page()
    for one in (
        "This setting: first response in the window",
        "Earliest test date if this setting is used",
        F20[0],
        F21.format(b=0, a=0),
        F14.format(1),
        F25.format(1),
        "Client versions after the split: 2.1.325",
    ):
        _says(page, one)


def test_a_tool_without_a_setting_has_no_method_line_and_no_footer(tmp_path: Path) -> None:
    """Items 41 and 71: a tool with no selected setting has no digest, so it carries neither
    F11 nor the footer, and its Markdown block ends with the F10 text."""
    claude = tmp_path / "claude"
    write_claude(claude, _uniform(ALTERNATING, DROPPED), setting=Setting(CLAUDE_MODEL, None))
    codex = tmp_path / "codex"
    write_codex(codex, _codex_no_drop())
    outcome = _run(
        tmp_path, _args("both", claude=claude, codex=codex), outputs=("markdown", "html")
    )
    assert outcome.tool(0)["reason"] == "no_usable_setting"
    assert outcome.tool(1)["result"] == "NO_DROP"
    block = outcome.text("markdown")
    # One footer only, for the tool that has a digest.
    assert _flat(block).count(_flat(FOOTER_FIRST_WORDS)) == 1
    assert _flat(block).count("arci-logs/2, digest") == 1
    assert _flat(outcome.out).count("method arci-logs/2") == 1
    _says(block, REASONS["no_usable_setting"])
    # The blank tool's block ends with the F10 text, word for word, and no footer.
    _says(block, _filled(F10_TEXT, _f10_block(outcome)))
    # The blank tool keeps no scope, no period line, no table, no context and no digest.
    first = _flat(block).index(_flat(REASONS["no_usable_setting"]))
    second = _flat(block).index(_flat(FOOTER_FIRST_WORDS))
    assert first < second
    _says(outcome.page(), REASONS["no_usable_setting"])


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
    # The footer carries the same figure and design as the closing paragraph above it.
    assert _footer_figures(block) == _f10_block(outcome)
    _says(block, "arci-logs/2, digest")
    _says(block, "Yours: uvx --python 3.14 realornoise")
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
    _says(block, NO_LOGS_GIVEN["claude-code"])
    assert "2.5%" not in block
    assert "uvx --python 3.14 realornoise" not in block
    assert "arci-logs/2, digest" not in block


def test_the_html_page_has_no_script_and_no_external_reference(tmp_path: Path) -> None:
    root = tmp_path / "claude"
    write_claude(root, _uniform(ALTERNATING, DROPPED))
    outcome = _run(tmp_path, _args("claude-code", claude=root), outputs=("html",))
    page = outcome.text("html")
    assert "<script" not in page.lower()
    assert "http://" not in page and "https://" not in page
    assert "<svg" in page.lower()
    _says(outcome.page(), REASONS["real_drop"])


def test_help_reads_no_logs_and_names_every_option(tmp_path: Path) -> None:
    """Item 55: `--help` reads no logs and its text names every option of the synopsis.

    The record does not fix the exit code of `--help`; it is not one of the usage errors, so
    the plainest reading is 0.
    """
    before = _listing(tmp_path)
    code, printed, failed = _raw_run(tmp_path, ["--help"])
    assert code == 0
    assert failed == ""
    for option in SYNOPSIS:
        assert option in printed, option
    # No logs were read, so no reader notice and no result can appear, and no file is written.
    assert "RESULT:" not in printed
    assert _listing(tmp_path) == before | {"home"}


# A circle the page draws unfilled. The record says "an open circle" and fixes no markup, so
# this accepts either spelling of an unfilled circle in the inline SVG.
OPEN_CIRCLE = re.compile(r"<circle[^>]*(?:fill=[\"']none[\"']|fill:\s*none)", re.IGNORECASE)


def test_the_html_charts_draw_a_kept_day_as_an_open_circle(tmp_path: Path) -> None:
    """Item 70: the HTML page draws a kept day as an open circle and a logs day as a filled
    one, has no script and no external reference, and holds no value that is not in the
    record."""
    kept_out, merged, sources = _source_case(tmp_path / "kept")
    # The same run again, with the table and the two report files.
    logs = _uniform(ALTERNATING, DROPPED)
    day = BEFORE_DAYS[0]
    kept_plan = merged[day]
    rows = [_kept_from_day("claude-code", day, kept_plan)]
    with_table, _ = _kept_run(
        tmp_path / "both", logs, rows, outputs=("markdown", "html"), stem="kept"
    )
    assert with_table.tool()["kept_days_before"] == 1
    page = with_table.text("html")
    assert OPEN_CIRCLE.search(page) is not None
    assert "<circle" in page.lower()
    assert "<script" not in page.lower()
    assert "http://" not in page and "https://" not in page
    _says(with_table.page(), F21.format(b=1, a=0))

    # A page with no kept day draws no open circle.
    plain, _ = _kept_run(tmp_path / "plain", logs, None, outputs=("html",), stem="plain")
    assert plain.tool()["kept_days_before"] == 0
    other = plain.text("html")
    assert "<circle" in other.lower()
    assert OPEN_CIRCLE.search(other) is None
    assert kept_out.tool()["measures"] == with_table.tool()["measures"]
    assert sources[day] == "kept"


def test_the_example_run(tmp_path: Path) -> None:
    """Item 35 in part: `--example` labels every output and reads no table; the packaged
    example gives REAL DROP for Claude Code and NO DROP for Codex."""
    outcome = _run(tmp_path, ["--example"], outputs=("markdown", "html"))
    assert outcome.body is not None
    assert outcome.body["example"] is True
    assert outcome.body["kept_table"] == "not_read"
    assert outcome.body["keep"] is False
    assert outcome.lines[1] == F13
    assert [tool["result"] for tool in outcome.tools()] == ["REAL_DROP", "NO_DROP"]
    assert outcome.code == 1
    # F13 holds an apostrophe, which the page writes as a character reference.
    for place in (outcome.text("markdown"), outcome.page()):
        _says(place, F13)
    # Every row of both tables has enough days.
    for tool in outcome.tools():
        assert all(measure["finding"] != "too_few_days" for measure in tool["measures"])


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


# --- 10. the output files --------------------------------------------------------------------
# Record 0017, "Command line and layout": two output options may not name the same file, where
# two spellings of one file are the same file; an existing file keeps its permission bits and a
# new one takes what the umask gives; nothing is left changed or left behind when a run is
# refused. The write rule, changed in 0017: the command writes only the files named by
# `--markdown`, `--html` and `--json`, their temporary files, and with `--keep` the kept table,
# its temporary file and its directory.


@pytest.mark.parametrize("spelling", ["identical", "symlink", "relative"])
def test_two_output_options_that_name_one_file_are_a_usage_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, spelling: str
) -> None:
    root = tmp_path / "claude"
    write_claude(root, _uniform(ALTERNATING, DROPPED))
    target = tmp_path / "out.json"
    if spelling == "identical":
        first, second = str(target), str(target)
    elif spelling == "symlink":
        target.write_text("keep me", encoding="utf-8")
        link = tmp_path / "link.json"
        link.symlink_to(target)
        first, second = str(target), str(link)
    else:
        monkeypatch.chdir(tmp_path)
        first, second = str(target), target.name
    (tmp_path / "home").mkdir(parents=True, exist_ok=True)
    before = _listing(tmp_path)

    code, printed, failed = _raw_run(
        tmp_path, [*_args("claude-code", claude=root), "--json", first, "--markdown", second]
    )
    assert code == 3
    assert printed == ""
    assert failed.splitlines() == [USAGE_ERRORS["same_file"]]
    # Nothing written, and no temporary name left beside a target.
    assert _listing(tmp_path) == before
    if spelling == "symlink":
        assert target.read_text(encoding="utf-8") == "keep me"
    else:
        assert not target.exists()


def test_two_spellings_of_a_new_file_are_one_file_when_the_volume_folds_case(
    tmp_path: Path,
) -> None:
    (tmp_path / "a.txt").write_text("probe", encoding="utf-8")
    if not (tmp_path / "A.TXT").exists():
        pytest.skip("this volume keeps a.txt and A.TXT apart, so the two spellings are two files")
    root = tmp_path / "claude"
    write_claude(root, _uniform(ALTERNATING, DROPPED))
    (tmp_path / "home").mkdir(parents=True, exist_ok=True)
    before = _listing(tmp_path)

    code, printed, failed = _raw_run(
        tmp_path,
        [
            *_args("claude-code", claude=root),
            "--json",
            str(tmp_path / "out.json"),
            "--html",
            str(tmp_path / "OUT.JSON"),
        ],
    )
    assert code == 3
    assert printed == ""
    assert failed.splitlines() == [USAGE_ERRORS["same_file"]]
    assert _listing(tmp_path) == before


def test_three_distinct_output_files_are_all_written(tmp_path: Path) -> None:
    root = tmp_path / "claude"
    write_claude(root, _uniform(ALTERNATING, DROPPED))
    outcome = _run(tmp_path, _args("claude-code", claude=root), outputs=("markdown", "html"))
    paths = [outcome.json_path, *outcome.extra.values()]
    assert all(path.is_file() for path in paths)
    assert len({path.read_bytes() for path in paths}) == 3


def test_an_existing_output_file_keeps_its_mode_and_a_new_one_takes_the_umask(
    tmp_path: Path,
) -> None:
    root = tmp_path / "claude"
    write_claude(root, _uniform(ALTERNATING, DROPPED))
    kept = tmp_path / "decision.json"
    kept.write_text("old", encoding="utf-8")
    kept.chmod(0o640)
    mask = os.umask(0)
    os.umask(mask)

    outcome = _run(tmp_path, _args("claude-code", claude=root), outputs=("markdown",))
    assert outcome.body is not None
    assert kept.read_text(encoding="utf-8") != "old"
    assert stat.S_IMODE(kept.stat().st_mode) == 0o640
    fresh = outcome.extra["markdown"]
    assert stat.S_IMODE(fresh.stat().st_mode) == 0o666 & ~mask


def test_the_run_writes_only_the_requested_files(tmp_path: Path) -> None:
    """Item 43 in part, and item 17: with no output option, no `--keep` and no stored table, no
    file is created anywhere and the table directory does not come into being."""
    root = tmp_path / "claude"
    write_claude(root, _uniform(ALTERNATING, DROPPED))
    home = tmp_path / "home"
    home.mkdir()
    before = _listing(tmp_path)
    code, printed, failed = _raw_run(tmp_path, _args("claude-code", claude=root), home=home)
    assert code == 1
    assert failed == ""
    assert "RESULT: REAL DROP" in printed
    assert _listing(tmp_path) == before
    assert not (home / ".realornoise").exists()

    # With the three output options, exactly those three files appear and nothing else.
    outcome = _run(tmp_path, _args("claude-code", claude=root), outputs=("markdown", "html"))
    assert _listing(tmp_path) - before == {"decision.json", "decision.md", "decision.html"}
    assert outcome.code == 1


def test_a_failure_while_a_staged_file_is_moved_leaves_everything_as_it_was(
    tmp_path: Path,
) -> None:
    """Item 65: a failure at the move, not only at directory creation, leaves every output and
    the table as they were and removes every directory the run created."""
    root = tmp_path / "claude"
    write_claude(root, _uniform(ALTERNATING, DROPPED))
    # A non-empty directory where the Markdown file should go: the move cannot replace it.
    blocked = tmp_path / "report.md"
    blocked.mkdir()
    (blocked / "keep.txt").write_text("keep me", encoding="utf-8")
    store = tmp_path / "store" / "deep"
    stored = tmp_path / "out.json"
    (tmp_path / "home").mkdir(parents=True, exist_ok=True)
    before = _listing(tmp_path)

    code, printed, failed = _raw_run(
        tmp_path,
        [
            *_args("claude-code", claude=root),
            "--json",
            str(stored),
            "--markdown",
            str(blocked),
            "--keep-dir",
            str(store),
        ],
    )
    assert code == 3
    assert printed == ""
    assert failed.splitlines() == [USAGE_ERRORS["unwritable"]]
    # Nothing written, no temporary file left, and the directory the run created is gone.
    assert _listing(tmp_path) == before
    assert not stored.exists()
    assert not store.exists()
    assert (blocked / "keep.txt").read_text(encoding="utf-8") == "keep me"


# --- 11. the kept day table ------------------------------------------------------------------
# Record 0017 decision 4 and "The kept day table": `--keep` writes `days-1.json` outside the
# vendors' folders after the run; later runs use it for days whose session files are gone.


def _validate_table(body: Mapping[str, Any]) -> None:
    """The schema of "Content": exactly the listed keys, rows sorted, no key twice."""
    assert set(body) == {"schema", "rows"}
    assert body["schema"] == TABLE_SCHEMA
    keys: list[tuple[Any, ...]] = []
    for row in body["rows"]:
        assert set(row) == ROW_FIELDS, row
        assert row["tool"] in TOOL_NAMES
        offset = row["utc_offset_minutes"]
        assert isinstance(offset, int) and not isinstance(offset, bool)
        assert -1440 < offset < 1440
        assert date.fromisoformat(row["day"]).isoformat() == row["day"]
        pairs = row["reasoning"]
        assert len(pairs) <= 5000
        counts = [pair[0] for pair in pairs]
        assert counts == sorted(counts) and len(counts) == len(set(counts))
        for pair in pairs:
            assert len(pair) == 2
            assert all(isinstance(one, int) and not isinstance(one, bool) for one in pair)
            assert pair[0] >= 0 and pair[1] >= 1
        unknown = row["reasoning_unknown"]
        responses = row["responses"]
        for one in (unknown, responses):
            assert isinstance(one, int) and not isinstance(one, bool) and one >= 0
        assert responses == sum(pair[1] for pair in pairs) + unknown
        if row["tool"] == "codex":
            assert row["edits"] is None and row["edits_failed"] is None
            assert responses >= 1
        else:
            assert isinstance(row["edits"], int) and not isinstance(row["edits"], bool)
            assert 0 <= row["edits_failed"] <= row["edits"]
            assert responses >= 1 or row["edits"] >= 1
        keys.append(_row_key(row))
    assert keys == sorted(keys)
    assert len(keys) == len(set(keys))


def _canonical(path: Path) -> dict[str, Any]:
    """Keys sorted, no indent, UTF-8, one final newline.

    The record does not fix which separators "no indent" uses, so this holds the properties the
    record names and not one spelling: one line, a final newline, and every object's keys in
    sorted order as the file gives them.
    """
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    assert text.endswith("\n")
    assert "\n" not in text[:-1]

    def sorted_keys(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
        names = [name for name, _ in pairs]
        assert names == sorted(names), names
        return dict(pairs)

    return json.loads(text, object_pairs_hook=sorted_keys)


def _rows(path: Path) -> list[dict[str, Any]]:
    body = _canonical(path)
    _validate_table(body)
    return body["rows"]


def test_no_file_is_created_without_keep_or_a_table(tmp_path: Path) -> None:
    """Item 17: without `--keep`, `--keep-dir`, an existing table and any report option, no file
    is created anywhere, and the table directory does not come into being."""
    root = tmp_path / "claude"
    write_claude(root, _uniform(ALTERNATING, DROPPED))
    home = tmp_path / "home"
    home.mkdir()
    before = _listing(tmp_path)
    code, printed, failed = _raw_run(
        tmp_path, _args("claude-code", claude=root), home=home, env={"REALORNOISE_HOME": ""}
    )
    assert code == 1 and failed == ""
    assert "writes nothing unless asked" in printed
    assert _listing(tmp_path) == before
    assert not (home / ".realornoise").exists()


@pytest.mark.parametrize("shape", ["env", "unset", "empty", "keep_dir", "keep_dir_wins"])
def test_the_table_directory_rules(tmp_path: Path, shape: str) -> None:
    """Items 18 and 48: `--keep-dir DIR` if given, else `$REALORNOISE_HOME` when it is set and
    not empty, else `~/.realornoise`; the file is `days-1.json`; `--keep-dir` needs no `--keep`
    and wins over `REALORNOISE_HOME`."""
    root = tmp_path / "claude"
    write_claude(root, _uniform(ALTERNATING, DROPPED))
    home = tmp_path / "home"
    named = tmp_path / "named"
    env_dir = tmp_path / "from-env"
    env: dict[str, str] = {}
    extra: list[str] = ["--keep"]
    wanted = home / ".realornoise" / TABLE_NAME
    if shape == "env":
        env = {"REALORNOISE_HOME": str(env_dir)}
        wanted = env_dir / TABLE_NAME
    elif shape == "empty":
        env = {"REALORNOISE_HOME": ""}
    elif shape == "keep_dir":
        extra = ["--keep-dir", str(named)]
        wanted = named / TABLE_NAME
    elif shape == "keep_dir_wins":
        env = {"REALORNOISE_HOME": str(env_dir)}
        extra = ["--keep-dir", str(named)]
        wanted = named / TABLE_NAME
    outcome = _run(tmp_path, _args("claude-code", claude=root, extra=extra), env=env, home=home)
    assert outcome.body is not None
    assert outcome.body["keep"] is True
    # A run that writes the table also reads it, so `kept_table` is not `not_read`.
    assert outcome.body["kept_table"] == "absent"
    assert wanted.is_file(), wanted
    rows = _rows(wanted)
    assert {row["day"] for row in rows} == {day.isoformat() for day in (*BEFORE_DAYS, *AFTER_DAYS)}
    if shape == "keep_dir_wins":
        assert not env_dir.exists()
    # The directory itself is never printed.
    for place in (outcome.out, outcome.err, outcome.json_path.read_text(encoding="utf-8")):
        assert str(wanted.parent) not in place


def test_the_written_table_validates_and_holds_the_counts_of_each_day(tmp_path: Path) -> None:
    """Items 19 and 64: the written table validates against the schema, is the canonical form,
    and is byte for byte equal for two runs on the same logs."""
    logs = {
        day: Day(counts=(5,) * 3 + (0,) * 2 + (None,) * 1, edits=(True,) * 2 + (False,) * 1)
        for day in (*BEFORE_DAYS, *AFTER_DAYS)
    }
    store = tmp_path / "store"
    first, path = _kept_run(tmp_path, logs, None, extra=("--keep",), store=store, stem="one")
    assert first.body is not None and first.body["keep"] is True
    rows = _rows(path)
    assert len(rows) == 15
    assert rows[0] == _kept_from_day("claude-code", BEFORE_DAYS[0], logs[BEFORE_DAYS[0]])
    assert rows[0]["reasoning"] == [[0, 2], [5, 3]]
    assert rows[0]["reasoning_unknown"] == 1
    assert rows[0]["responses"] == 6
    assert (rows[0]["edits"], rows[0]["edits_failed"]) == (3, 2)
    bytes_first = path.read_bytes()
    second = _run(
        tmp_path,
        _args("claude-code", claude=tmp_path / "claude-code", extra=("--keep",)),
        env={"REALORNOISE_HOME": str(store)},
        stem="two",
    )
    assert second.code == first.code
    assert path.read_bytes() == bytes_first


def test_a_codex_table_has_no_edit_counts(tmp_path: Path) -> None:
    """Item 19: Codex `edits` and `edits_failed` are null."""
    outcome, path = _kept_run(tmp_path, _codex_no_drop(), None, tool="codex", extra=("--keep",))
    assert outcome.tool()["tool"] == "codex"
    rows = _rows(path)
    assert rows and all(row["edits"] is None and row["edits_failed"] is None for row in rows)
    assert all(row["tool"] == "codex" for row in rows)
    assert all(row["model"] == CODEX_MODEL for row in rows)


def test_the_modes_of_the_table_and_its_directory(tmp_path: Path) -> None:
    """Items 20 and 64: the written file has mode 0600 and a directory the run creates has mode
    0700; a directory that already existed keeps its mode, and a table that replaces a file
    with other bits has mode 0600."""
    root = tmp_path / "claude"
    write_claude(root, _uniform(ALTERNATING, DROPPED))
    fresh = tmp_path / "fresh" / "inner"
    outcome = _run(
        tmp_path, _args("claude-code", claude=root, extra=("--keep-dir", str(fresh))), stem="one"
    )
    assert outcome.code == 1
    assert stat.S_IMODE((fresh / TABLE_NAME).stat().st_mode) == 0o600
    assert stat.S_IMODE(fresh.stat().st_mode) == 0o700
    assert stat.S_IMODE(fresh.parent.stat().st_mode) == 0o700

    # An existing directory keeps its mode, and a table that replaces a valid file with other
    # bits takes 0600.
    old = tmp_path / "old"
    old.mkdir(mode=0o755)
    write_kept(
        old / TABLE_NAME, [_kept_from_day("claude-code", BEFORE_DAYS[0], Day(counts=(5,) * 2))]
    )
    (old / TABLE_NAME).chmod(0o644)
    again = _run(
        tmp_path, _args("claude-code", claude=root, extra=("--keep-dir", str(old))), stem="two"
    )
    assert again.body is not None and again.body["kept_table"] == "read"
    assert stat.S_IMODE(old.stat().st_mode) == 0o755
    assert stat.S_IMODE((old / TABLE_NAME).stat().st_mode) == 0o600
    assert len(_rows(old / TABLE_NAME)) == 15


def test_the_table_holds_no_string_from_the_logs(tmp_path: Path) -> None:
    """Item 21: canary tokens in every free log string never appear in the table, which holds
    only accepted model and effort names and the two fixed tool names."""
    root = tmp_path / "claude"
    write_claude(
        root,
        _canary_plans(),
        setting=Setting(CANARY_MODEL_A, "high"),
        other=Setting(SMALL_MODEL, "high"),
        project=f"-canary-{CANARY_UPPER}",
        cwd=CANARY_DIR,
        text=CANARY_INPUT,
        output=CANARY_OUTPUT,
    )
    store = tmp_path / "store"
    outcome = _run(tmp_path, _args("claude-code", claude=root, extra=("--keep-dir", str(store))))
    path = store / TABLE_NAME
    text = path.read_text(encoding="utf-8")
    for canary in CANARIES:
        assert canary not in text, canary
    for part in CANARY_PARTS:
        assert part not in text, part
    rows = _rows(path)
    # Only the setting whose names the lists accept is kept.
    assert {(row["model"], row["effort"]) for row in rows} == {(SMALL_MODEL, "high")}
    assert outcome.tool()["settings_not_kept"] == 1
    assert F22.format(1) in outcome.lines


def test_settings_outside_the_accepted_lists_are_not_kept(tmp_path: Path) -> None:
    """Items 13 and 22: a setting whose model id fails the grammar, or whose effort is not one
    of the nine, is not in the table, and F22 prints its count."""
    root = tmp_path / "claude"
    plans = _uniform(ALTERNATING, HELD[:4], after_days=AFTER_DAYS[1:])
    # The compared setting's model id fails the grammar: 100 after-period responses.
    write_claude(root, plans, setting=Setting(CANARY_MODEL_A, "high"))
    # A setting with an effort outside the nine, and one both lists accept.
    write_claude(
        root,
        {NEWEST: Day(counts=(5,) * 3)},
        session="02",
        prefix="b",
        setting=Setting(CLAUDE_MODEL, CANARY_EFFORT_1),
    )
    write_claude(
        root,
        {NEWEST: Day(counts=(5,) * 2)},
        session="03",
        prefix="c",
        setting=Setting(CLAUDE_MODEL, "ultra"),
    )
    store = tmp_path / "store"
    outcome = _run(tmp_path, _args("claude-code", claude=root, extra=("--keep-dir", str(store))))
    tool = outcome.tool()
    assert tool["model"] == "model-1"
    assert (tool["result"], tool["reason"]) == ("CANNOT_TELL", "too_few_days")
    # F20 still prints for a setting shown by alias, and F22 counts the two settings not kept.
    _run_of(outcome, [*_wrapped(F20[0]), *_wrapped(F20[1])])
    assert tool["settings_not_kept"] == 2
    assert F22.format(2) in outcome.lines
    rows = _rows(store / TABLE_NAME)
    assert {(row["model"], row["effort"]) for row in rows} == {(CLAUDE_MODEL, "ultra")}


def test_a_day_over_the_histogram_cap_is_not_kept(tmp_path: Path) -> None:
    """Items 23 and 61: a day with 5,001 distinct reasoning counts is not in the table and F23
    counts it; a day with exactly 5,000 is written; a valid stored row for that key stays as
    stored, and the run's own day value for the day still comes from the uncapped logs row."""
    capped = BEFORE_DAYS[0]
    exact = BEFORE_DAYS[1]
    logs = {
        **{day: Day(counts=(100,) * 20) for day in (*BEFORE_DAYS, *AFTER_DAYS)},
        capped: Day(counts=tuple(range(1, 5002))),
        exact: Day(counts=tuple(range(1, 5001))),
    }
    stored = _kept_from_day("claude-code", capped, Day(counts=(7,) * 3))
    store = tmp_path / "store"
    outcome, path = _kept_run(tmp_path, logs, [stored], extra=("--keep",), store=store)
    tool = outcome.tool()
    assert tool["days_not_kept"] == 1
    assert F23.format(1) in outcome.lines
    rows = {(row["day"], len(row["reasoning"])) for row in _rows(path)}
    # The day over the cap keeps the stored row as it was; the day at the cap is written.
    assert (capped.isoformat(), 1) in rows
    assert (exact.isoformat(), 5000) in rows
    assert next(row for row in _rows(path) if row["day"] == capped.isoformat()) == stored
    # The use rule is not affected: the logs row has more responses, so the day's own value
    # comes from it, with all its counts.
    merged, sources = _merge("claude-code", logs, {capped: Day(counts=(7,) * 3)})
    _check(outcome, "claude-code", merged, sources=sources)
    assert sources[capped] == "logs"


def test_old_rows_are_pruned_on_write(tmp_path: Path) -> None:
    """Item 24: rows dated more than 180 days before `N` are dropped on write; a row dated
    exactly `N-180` stays."""
    edge = NEWEST - timedelta(days=180)
    older = NEWEST - timedelta(days=181)
    later = NEWEST + timedelta(days=3)
    rows = [
        _kept_from_day("claude-code", edge, Day(counts=(5,) * 2)),
        _kept_from_day("claude-code", older, Day(counts=(5,) * 2)),
        _kept_from_day("claude-code", later, Day(counts=(5,) * 2)),
    ]
    outcome, path = _kept_run(tmp_path, _uniform(ALTERNATING, DROPPED), rows, extra=("--keep",))
    assert outcome.code == 1
    days = {row["day"] for row in _rows(path)}
    assert edge.isoformat() in days
    assert older.isoformat() not in days
    # A stored row dated after `N` stays as stored, although no run uses it.
    assert later.isoformat() in days
    # None of the three rows lies in the window, so none counts as a kept day.
    assert (outcome.tool()["kept_days_before"], outcome.tool()["kept_days_after"]) == (0, 0)
    _check(outcome, "claude-code", _uniform(ALTERNATING, DROPPED))


@pytest.mark.parametrize(
    ("stored_plan", "winner"),
    [
        # The row of the table, whose pair is larger, stays.
        (Day(counts=(7,) * 30, edits=(False,) * 10), "kept"),
        # A row from the logs whose pair is at least as large replaces it, a tie included.
        (Day(counts=(7,) * 20, edits=(False,) * 10), "logs"),
        (Day(counts=(7,) * 19, edits=(False,) * 10), "logs"),
        # The row of the table, with equal responses and more file-edit results, stays.
        (Day(counts=(7,) * 20, edits=(False,) * 11), "kept"),
    ],
)
def test_the_write_rule_pair_decides(tmp_path: Path, stored_plan: Day, winner: str) -> None:
    """Item 25: for each (tool, offset, setting, day) the two rows are compared by the pair
    (responses, file-edit results), in that order; a row is written whole. `winner` is the
    record's own value for a day's source: `kept` or `logs`."""
    day = BEFORE_DAYS[0]
    logs = _uniform(ALTERNATING, DROPPED, edits=(False,) * 10)
    stored = _kept_from_day("claude-code", day, stored_plan)
    outcome, path = _kept_run(tmp_path, logs, [stored], extra=("--keep",))
    written = next(row for row in _rows(path) if row["day"] == day.isoformat())
    wanted = stored if winner == "kept" else _kept_from_day("claude-code", day, logs[day])
    assert written == wanted
    # The use rule reads the same pair, so the day's source follows the same winner.
    merged, sources = _merge("claude-code", logs, {day: stored_plan})
    assert sources[day] == winner
    _check(outcome, "claude-code", merged, sources=sources)


def test_f21_prints_the_kept_day_counts(tmp_path: Path) -> None:
    """Item 28: F21 prints the counts of kept days per period for each tool with a selected
    setting when the table was read, `0 before, 0 after` included, and is absent for a tool
    whose result is ERROR or `no_usable_setting` and when no table exists."""
    logs = _uniform(ALTERNATING, DROPPED)
    kept_plan = Day(counts=(300,) * 25)
    rows = [_kept_from_day("claude-code", BEFORE_DAYS[0], kept_plan)]
    with_days, _ = _kept_run(tmp_path / "days", logs, rows)
    assert F21.format(b=1, a=0) in with_days.lines
    assert (with_days.tool()["kept_days_before"], with_days.tool()["kept_days_after"]) == (1, 0)

    # A table that holds nothing for this tool: F21 prints its zeros.
    other = [_kept_from_day("codex", BEFORE_DAYS[0], Day(counts=(5,) * 3), model=CODEX_MODEL)]
    zeros, _ = _kept_run(tmp_path / "zeros", logs, other)
    assert F21.format(b=0, a=0) in zeros.lines

    # No table at all, and `--ignore-kept`: no F21.
    absent, _ = _kept_run(tmp_path / "absent", logs, None)
    assert "Days from the kept table" not in absent.out
    ignored, _ = _kept_run(tmp_path / "ignored", logs, rows, extra=("--ignore-kept",))
    assert "Days from the kept table" not in ignored.out

    # An ERROR tool and a tool with no usable setting carry no F21 block. A stored row of this
    # tool inside the window would make its setting a candidate under the use rule, so the
    # table here holds a row of the other tool and one dated outside the window.
    claude = tmp_path / "blank" / "claude"
    write_claude(claude, logs, setting=Setting(CLAUDE_MODEL, None))
    codex = tmp_path / "blank" / "codex"
    codex.mkdir(parents=True)
    store = tmp_path / "blank" / "store"
    write_kept(
        store / TABLE_NAME,
        [
            *other,
            _kept_from_day("claude-code", NEWEST - timedelta(days=150), Day(counts=(5,) * 3)),
        ],
    )
    blank = _run(
        tmp_path / "blank",
        _args("both", claude=claude, codex=codex),
        env={"REALORNOISE_HOME": str(store)},
    )
    assert [tool["reason"] for tool in blank.tools()] == ["no_usable_setting", "no_logs"]
    assert blank.body is not None and blank.body["kept_table"] == "read"
    assert "Days from the kept table" not in blank.out


def test_ignore_kept_reads_no_table_and_writes_none(tmp_path: Path) -> None:
    """Item 29: the result equals the result of the same run with no table present,
    `kept_table` is `not_read`, and a stored table is left byte for byte."""
    logs = _uniform(ALTERNATING, DROPPED)
    rows = [_kept_from_day("claude-code", BEFORE_DAYS[0], Day(counts=(300,) * 25))]
    ignored, path = _kept_run(tmp_path / "ignored", logs, rows, extra=("--ignore-kept",))
    stored_bytes = path.read_bytes()
    plain, _ = _kept_run(tmp_path / "plain", logs, None)
    assert ignored.body is not None and ignored.body["kept_table"] == "not_read"
    assert ignored.body["keep"] is False
    assert ignored.tool()["measures"] == plain.tool()["measures"]
    assert ignored.tool()["kept_days_before"] == 0
    assert ignored.code == plain.code
    assert path.read_bytes() == stored_bytes


def test_rows_under_another_offset_are_counted_and_never_used(tmp_path: Path) -> None:
    """Items 30 and 45: stored rows under another offset are not used and F25 counts all of
    them, whatever their day, a day after `N` included; a run with `--utc` and one at offset
    +05:30 keep separate rows."""
    logs = _uniform(ALTERNATING, DROPPED)
    day = BEFORE_DAYS[0]
    rows = [
        _kept_from_day("claude-code", day, Day(counts=(300,) * 25), offset=330),
        _kept_from_day(
            "claude-code", NEWEST + timedelta(days=5), Day(counts=(300,) * 25), offset=330
        ),
    ]
    outcome, path = _kept_run(tmp_path, logs, rows, extra=("--keep",))
    tool = outcome.tool()
    assert tool["kept_rows_other_offset"] == 2
    assert F25.format(2) in outcome.lines
    assert (tool["kept_days_before"], tool["kept_days_after"]) == (0, 0)
    # The day value is the logs row's, since no row at this offset exists for that day.
    _check(outcome, "claude-code", logs)
    # The write keeps the rows of the other offset and adds this run's own at offset 0.
    offsets = {row["utc_offset_minutes"] for row in _rows(path)}
    assert offsets == {0, 330}
    stored = {(row["utc_offset_minutes"], row["day"]) for row in _rows(path)}
    assert (330, day.isoformat()) in stored
    assert (0, day.isoformat()) in stored


def _fault_table(path: Path, shape: str) -> None:
    """One stored table per fault of "Faults" and of item 63."""
    good = _kept_from_day("claude-code", BEFORE_DAYS[0], Day(counts=(300,) * 25))
    second = _kept_from_day("claude-code", BEFORE_DAYS[1], Day(counts=(300,) * 25))
    path.parent.mkdir(parents=True, exist_ok=True)
    if shape == "not_json":
        path.write_text("this is not json at all", encoding="utf-8")
    elif shape == "not_utf8":
        path.write_bytes(b'{"schema": "realornoise-days/1", "rows": [\xff\xfe]}')
    elif shape == "not_a_file":
        path.mkdir(parents=True, exist_ok=True)
    elif shape == "unreadable":
        # Written readable here; the test takes its bytes and then removes the permission.
        write_kept(path, [good])
    elif shape == "duplicate_json_key":
        body = json.dumps({"schema": TABLE_SCHEMA, "rows": [good]})
        path.write_text(body.replace('"rows"', '"schema": "x", "rows"', 1), encoding="utf-8")
    elif shape == "unknown_key":
        write_kept(path, [{**good, "extra": 1}])
    elif shape == "missing_key":
        row = {name: value for name, value in good.items() if name != "edits"}
        write_kept(path, [row])
    elif shape == "wrong_schema":
        write_kept(path, [good], schema="realornoise-days/2")
    elif shape == "duplicate_row":
        write_kept(path, [good, dict(good)], sort=False)
    elif shape == "boolean_count":
        write_kept(path, [{**good, "reasoning_unknown": True}])
    elif shape == "unsorted":
        write_kept(path, [second, good], sort=False)
    elif shape == "bad_day":
        write_kept(path, [{**good, "day": "2026-13-45"}])
    elif shape == "bad_offset":
        write_kept(path, [{**good, "utc_offset_minutes": 1440}])
    elif shape == "bad_total":
        write_kept(path, [{**good, "responses": good["responses"] + 1}])
    elif shape == "bad_failed":
        write_kept(path, [{**good, "edits": 2, "edits_failed": 3}])
    else:  # one bad row beside a good one
        write_kept(path, [good, {**second, "responses": 0}])


FAULTS = (
    "not_json",
    "not_utf8",
    "not_a_file",
    "unreadable",
    "duplicate_json_key",
    "unknown_key",
    "missing_key",
    "wrong_schema",
    "duplicate_row",
    "boolean_count",
    "unsorted",
    "bad_day",
    "bad_offset",
    "bad_total",
    "bad_failed",
    "one_bad_row",
)


@pytest.mark.parametrize("shape", FAULTS)
def test_a_faulty_table_is_not_used_at_all(tmp_path: Path, shape: str) -> None:
    """Items 31 and 63: each of these makes the whole table unused with one F24 and the result
    of a run with no table; the Markdown and HTML hold F24 too; with `--keep` the file is left
    byte for byte and the exit code is the one of the result."""
    logs = _uniform(ALTERNATING, DROPPED)
    store = tmp_path / "store"
    path = store / TABLE_NAME
    _fault_table(path, shape)
    # The bytes are taken while the file can still be read, and only then is the permission
    # removed for the fault that needs it.
    before = path.read_bytes() if path.is_file() else None
    if shape == "unreadable":
        path.chmod(0o000)
        if os.access(path, os.R_OK):
            path.chmod(stat.S_IRUSR | stat.S_IWUSR)
            pytest.skip("this process can read a file with no read permission")
    try:
        outcome, _ = _kept_run(
            tmp_path,
            logs,
            None,
            extra=("--keep",),
            outputs=("markdown", "html"),
            store=store,
        )
    finally:
        if shape == "unreadable":
            path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    assert outcome.body is not None
    assert outcome.body["kept_table"] == "unreadable"
    # F24 prints once, after F1, and in the other two forms.
    assert outcome.lines.count(F24) == 1
    assert outcome.lines.index(F24) == 1
    for place in (outcome.text("markdown"), outcome.page()):
        _says(place, F24)
    # The result is the result with no table, and the exit code is the result's.
    plain, _ = _kept_run(tmp_path / "plain", logs, None)
    assert outcome.tool()["measures"] == plain.tool()["measures"]
    assert outcome.code == plain.code == 1
    assert outcome.tool()["kept_days_before"] == 0
    # With `--keep`, a table that could not be read is not replaced and not changed.
    if before is not None:
        assert path.read_bytes() == before
    else:
        # The path was not a regular file, so nothing was written over it either.
        assert path.is_dir() and _listing(path) == set()
    # The path, the file's text and any error text are never printed.
    for place in (outcome.out, outcome.err):
        assert str(path) not in place
        assert "days-1.json" not in place


def test_keep_with_project_is_a_usage_error(tmp_path: Path) -> None:
    """Item 32: `--keep` with `--project` prints its fixed line on standard error, nothing on
    standard output, writes nothing, and exits 3."""
    root = tmp_path / "claude"
    write_claude(root, _uniform(ALTERNATING, DROPPED))
    (tmp_path / "home").mkdir(parents=True, exist_ok=True)
    before = _listing(tmp_path)
    code, printed, failed = _raw_run(
        tmp_path,
        [*_args("claude-code", claude=root), "--keep", "--project", WORKDIR],
    )
    assert code == 3
    assert printed == ""
    assert failed.splitlines() == [USAGE_ERRORS["keep_project"]]
    assert _listing(tmp_path) == before


@pytest.mark.parametrize(
    "flags",
    [
        ("--keep", "--ignore-kept"),
        ("--keep-dir", "DIR", "--ignore-kept"),
        ("--example", "--keep", "--ignore-kept"),
    ],
)
def test_ignore_kept_with_keep_is_a_usage_error(tmp_path: Path, flags: tuple[str, ...]) -> None:
    """Item 52: each prints `--ignore-kept cannot be used with --keep.`, reads no table, writes
    nothing and exits 3; the text names `--keep` also when the run gave `--keep-dir`, and
    `--example` does not excuse the error."""
    root = tmp_path / "claude"
    write_claude(root, _uniform(ALTERNATING, DROPPED))
    store = tmp_path / "store"
    one = _kept_from_day("claude-code", BEFORE_DAYS[0], Day(counts=(5,) * 2))
    write_kept(store / TABLE_NAME, [one])
    stored = (store / TABLE_NAME).read_bytes()
    (tmp_path / "home").mkdir(parents=True, exist_ok=True)
    before = _listing(tmp_path)
    argv = [*_args("claude-code", claude=root)]
    for flag in flags:
        argv.append(str(store) if flag == "DIR" else flag)
    code, printed, failed = _raw_run(tmp_path, argv, env={"REALORNOISE_HOME": str(store)})
    assert code == 3
    assert printed == ""
    assert failed.splitlines() == [USAGE_ERRORS["ignore_keep"]]
    assert _listing(tmp_path) == before
    assert (store / TABLE_NAME).read_bytes() == stored


@pytest.mark.parametrize("shape", ["keep_dir_project", "two_errors", "option_phase_first"])
def test_the_order_of_the_two_error_phases(tmp_path: Path, shape: str) -> None:
    """Item 65: `--keep-dir` implies `--keep`, so it prints the same fixed lines; with two
    errors at once the first in the F5 order prints; and an option-only error prints even when
    a log-dependent error would also apply."""
    root = tmp_path / "claude"
    write_claude(root, _uniform(ALTERNATING, DROPPED))
    store = tmp_path / "store"
    target = tmp_path / "both.json"
    argv = [*_args("claude-code", claude=root)]
    if shape == "keep_dir_project":
        argv += ["--keep-dir", str(store), "--project", WORKDIR]
        wanted = USAGE_ERRORS["keep_project"]
    elif shape == "two_errors":
        # `--keep cannot be used with --project.` is before `--ignore-kept cannot be used with
        # --keep.` in the F5 list.
        argv += ["--keep", "--project", WORKDIR, "--ignore-kept"]
        wanted = USAGE_ERRORS["keep_project"]
    else:
        # The same file is an option-only error; a `--since` more than 83 days before the
        # newest day needs the logs, so the option-only phase decides although the F5 list
        # puts the `--since` sentence first.
        argv += ["--json", str(target), "--markdown", str(target), "--since", "2026-01-01"]
        wanted = USAGE_ERRORS["same_file"]
    (tmp_path / "home").mkdir(parents=True, exist_ok=True)
    before = _listing(tmp_path)
    code, printed, failed = _raw_run(tmp_path, argv)
    assert code == 3
    assert printed == ""
    assert failed.splitlines() == [wanted]
    assert _listing(tmp_path) == before


@pytest.mark.parametrize("shape", ["relative", "tilde"])
def test_the_keep_directory_is_resolved_like_a_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, shape: str
) -> None:
    """Item 65: a relative `--keep-dir` is resolved against the current directory and a `~`
    path against the injected home."""
    root = tmp_path / "claude"
    write_claude(root, _uniform(ALTERNATING, DROPPED))
    home = tmp_path / "home"
    home.mkdir()
    if shape == "relative":
        monkeypatch.chdir(tmp_path)
        given, wanted = "store", tmp_path / "store" / TABLE_NAME
    else:
        given, wanted = "~/mine", home / "mine" / TABLE_NAME
    outcome = _run(
        tmp_path,
        _args("claude-code", claude=root, extra=("--keep-dir", given)),
        home=home,
    )
    assert outcome.code == 1
    assert wanted.is_file(), wanted
    assert len(_rows(wanted)) == 15


@pytest.mark.parametrize("spelling", ["plain", "relative"])
def test_an_output_option_that_names_the_table(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, spelling: str
) -> None:
    """Items 34 and 65: with `--keep` or `--keep-dir`, a report path that names the table file
    is `Two output options name the same file.`, under any spelling of that path."""
    root = tmp_path / "claude"
    write_claude(root, _uniform(ALTERNATING, DROPPED))
    store = tmp_path / "store"
    store.mkdir()
    table = store / TABLE_NAME
    named = str(table)
    if spelling == "relative":
        monkeypatch.chdir(store)
        named = TABLE_NAME
    (tmp_path / "home").mkdir(parents=True, exist_ok=True)
    before = _listing(tmp_path)
    code, printed, failed = _raw_run(
        tmp_path,
        [*_args("claude-code", claude=root), "--keep-dir", str(store), "--html", named],
    )
    assert code == 3
    assert printed == ""
    assert failed.splitlines() == [USAGE_ERRORS["same_file"]]
    assert _listing(tmp_path) == before
    assert not table.exists()


def test_without_keep_a_report_may_be_written_over_the_table(tmp_path: Path) -> None:
    """Item 34: without `--keep`, `--keep-dir` or `--ignore-kept` the table's path does not
    join the same-file check, so a `--json` that names an invalid table writes the report over
    it; F24 prints once and says only that the table was not used."""
    root = tmp_path / "claude"
    write_claude(root, _uniform(ALTERNATING, DROPPED))
    store = tmp_path / "store"
    _fault_table(store / TABLE_NAME, "not_json")
    table = store / TABLE_NAME
    code, printed, failed = _raw_run(
        tmp_path,
        [*_args("claude-code", claude=root), "--json", str(table)],
        env={"REALORNOISE_HOME": str(store)},
    )
    assert code == 1
    assert failed == ""
    assert printed.splitlines().count(F24) == 1
    body = json.loads(table.read_text(encoding="utf-8"))
    assert body["schema_version"] == "arci-logs/2"
    assert body["kept_table"] == "unreadable"
    _audit(body, code)
    # The result is the one of a run with no table.
    plain, _ = _kept_run(tmp_path / "plain", _uniform(ALTERNATING, DROPPED), None)
    assert body["tools"][0]["measures"] == plain.tool()["measures"]


@pytest.mark.parametrize("shape", ["directory", "report"])
def test_a_failed_write_leaves_the_table_and_every_output_as_they_were(
    tmp_path: Path, shape: str
) -> None:
    """Item 33: when the table write fails, or when a requested report cannot be written, the
    run prints `Requested output could not be written.` as the only line on standard error,
    prints nothing on standard output, exits 3, and leaves every file as it was; a table
    directory the run created is removed."""
    root = tmp_path / "claude"
    write_claude(root, _uniform(ALTERNATING, DROPPED))
    (tmp_path / "home").mkdir(parents=True, exist_ok=True)
    if shape == "directory":
        # A regular file where the table's parent directory would go: it cannot be created.
        (tmp_path / "blocked").write_text("not a directory", encoding="utf-8")
        argv = [*_args("claude-code", claude=root), "--keep-dir", str(tmp_path / "blocked" / "in")]
        stored = None
    else:
        store = tmp_path / "store"
        stored_row = _kept_from_day("claude-code", BEFORE_DAYS[0], Day(counts=(5,) * 2))
        write_kept(store / TABLE_NAME, [stored_row])
        stored = (store / TABLE_NAME).read_bytes()
        # A non-empty directory where the JSON report would go.
        blocked = tmp_path / "report.json"
        blocked.mkdir()
        (blocked / "keep.txt").write_text("keep me", encoding="utf-8")
        argv = [
            *_args("claude-code", claude=root),
            "--keep-dir",
            str(store),
            "--json",
            str(blocked),
        ]
    before = _listing(tmp_path)
    code, printed, failed = _raw_run(tmp_path, argv)
    assert code == 3
    assert printed == ""
    assert failed.splitlines() == [USAGE_ERRORS["unwritable"]]
    assert _listing(tmp_path) == before
    if stored is not None:
        assert (tmp_path / "store" / TABLE_NAME).read_bytes() == stored
    else:
        assert not (tmp_path / "blocked" / "in").exists()


def test_example_ignores_the_table_options(tmp_path: Path) -> None:
    """Item 35: adding `--keep` to `--example` leaves the output unchanged and writes no table,
    and no table is read; the option errors still apply."""
    plain = _run(tmp_path, ["--example"], stem="one")
    store = tmp_path / "store"
    kept = _run(tmp_path, ["--example", "--keep-dir", str(store)], stem="two")
    assert plain.out == kept.out
    assert plain.code == kept.code
    assert kept.body is not None
    assert kept.body["keep"] is False
    assert kept.body["kept_table"] == "not_read"
    assert not store.exists()
    # A stored table in the resolved directory is not read either.
    other = tmp_path / "other"
    write_kept(
        other / TABLE_NAME, [_kept_from_day("claude-code", BEFORE_DAYS[0], Day(counts=(5,) * 2))]
    )
    with_table = _run(tmp_path, ["--example"], stem="three", env={"REALORNOISE_HOME": str(other)})
    assert with_table.out == plain.out
    assert with_table.body is not None and with_table.body["kept_table"] == "not_read"

    # The usage errors are checked on the options alone, before any log or table is read.
    code, printed, failed = _raw_run(tmp_path, ["--example", "--keep", "--project", WORKDIR])
    assert code == 3
    assert printed == ""
    assert failed.splitlines() == [USAGE_ERRORS["keep_project"]]


def test_the_use_rule_takes_the_row_whole_by_its_pair(tmp_path: Path) -> None:
    """Items 44, 49 and 27(b): the logs row wins a tie; a stored row with equal responses and
    more file-edit results is used; a logs row with more responses and fewer file-edit results
    is used whole, so the stored file-edit count is not recovered."""
    tie, more_edits, whole = BEFORE_DAYS[0], BEFORE_DAYS[1], BEFORE_DAYS[2]
    logs = _uniform(ALTERNATING, DROPPED, edits=(False,) * 10)
    logs[whole] = Day(counts=(100,) * 25, edits=(True,) + (False,) * 9)
    stored_plans = {
        tie: Day(counts=(7,) * 20, edits=(False,) * 10),
        more_edits: Day(counts=(7,) * 20, edits=(True,) * 11),
        whole: Day(counts=(100,) * 20, edits=(False,) * 20),
    }
    rows = [_kept_from_day("claude-code", day, plan) for day, plan in stored_plans.items()]
    merged, sources = _merge("claude-code", logs, stored_plans)
    assert [sources[day] for day in (tie, more_edits, whole)] == ["logs", "kept", "logs"]
    outcome, _ = _kept_run(tmp_path, logs, rows)
    tool = _check(outcome, "claude-code", merged, sources=sources)
    edits = tool["measures"][2]
    rows_by_day = {row["day"]: row for row in edits["before_days"]}
    # The tie keeps the logs row, so the day holds ten results and none failed.
    assert rows_by_day[tie.isoformat()] == {
        "day": tie.isoformat(),
        "count": 10,
        "value": "0/1",
        "source": "logs",
    }
    # The stored row with more results is used whole, failures included.
    assert rows_by_day[more_edits.isoformat()] == {
        "day": more_edits.isoformat(),
        "count": 11,
        "value": "1/1",
        "source": "kept",
    }
    # The logs row with more responses is used whole: ten results, not the stored twenty.
    assert rows_by_day[whole.isoformat()] == {
        "day": whole.isoformat(),
        "count": 10,
        "value": _rational(Fraction(1, 10)),
        "source": "logs",
    }
    assert tool["kept_days_before"] == 1


def test_an_edit_only_day_takes_the_row_with_more_results(tmp_path: Path) -> None:
    """Item 27(c): a day with file-edit results and no response takes the row with more
    file-edit results, so a complete stored row beats a partial logs row."""
    day = date(2026, 10, 10)
    logs = _uniform(ALTERNATING, DROPPED, edits=(False,) * 10)
    root = tmp_path / "claude-code"
    write_claude(root, logs)
    _write_lines(
        root / PROJECT_DIR / "02.jsonl",
        _edit_only_lines(response_day=BEFORE_WINDOW, result_day=day, count=5, failed=0),
    )
    stored = kept_row("claude-code", day, edits=12, edits_failed=3)
    store = tmp_path / "store"
    write_kept(store / TABLE_NAME, [stored])
    outcome = _run(
        tmp_path,
        _args("claude-code", claude=root),
        env={"REALORNOISE_HOME": str(store)},
    )
    edits = outcome.tool()["measures"][2]
    assert edits["before_days"][0] == {
        "day": day.isoformat(),
        "count": 12,
        "value": _rational(Fraction(1, 4)),
        "source": "kept",
    }
    assert outcome.tool()["kept_days_before"] == 1
    # The day holds no response, so it is not a response day.
    assert outcome.tool()["response_days_before"] == 10


def test_keeping_one_tool_leaves_the_other_tools_rows(tmp_path: Path) -> None:
    """Item 46: `--keep --tool codex` leaves every stored Claude Code row unchanged as a parsed
    row object, field for field, pruning included."""
    old = NEWEST - timedelta(days=200)
    rows = [
        _kept_from_day("claude-code", BEFORE_DAYS[0], Day(counts=(5,) * 3)),
        _kept_from_day("claude-code", old, Day(counts=(5,) * 3)),
        _kept_from_day("claude-code", BEFORE_DAYS[1], Day(counts=(5,) * 3), offset=330),
    ]
    store = tmp_path / "store"
    write_kept(store / TABLE_NAME, rows)
    outcome, path = _kept_run(
        tmp_path, _codex_no_drop(), rows, tool="codex", extra=("--keep",), store=store
    )
    assert outcome.tool()["tool"] == "codex"
    written = _rows(path)
    claude_rows = [row for row in written if row["tool"] == "claude-code"]
    assert claude_rows == sorted(rows, key=_row_key)
    assert any(row["tool"] == "codex" for row in written)


@pytest.mark.parametrize(
    ("shape", "state", "keep"),
    [
        ("absent", "absent", False),
        ("valid", "read", False),
        ("faulty", "unreadable", False),
        ("ignore", "not_read", False),
        ("project", "not_read", False),
        ("keep", "absent", True),
    ],
)
def test_the_kept_table_field_and_the_option_fields(
    tmp_path: Path, shape: str, state: str, keep: bool
) -> None:
    """Item 47: `kept_table` is `absent` with no file, `read` with a valid one, `unreadable`
    with F24, `not_read` under `--ignore-kept`, `--project` or `--example`; `since_given` and
    `keep` follow their options."""
    logs = _uniform(ALTERNATING, DROPPED)
    root = tmp_path / "claude"
    write_claude(root, logs)
    store = tmp_path / "store"
    good = [_kept_from_day("claude-code", BEFORE_DAYS[0], Day(counts=(300,) * 25))]
    extra: tuple[str, ...] = ()
    if shape == "valid":
        write_kept(store / TABLE_NAME, good)
    elif shape == "faulty":
        _fault_table(store / TABLE_NAME, "not_json")
    elif shape == "ignore":
        write_kept(store / TABLE_NAME, good)
        extra = ("--ignore-kept",)
    elif shape == "project":
        write_kept(store / TABLE_NAME, good)
        extra = ("--project", WORKDIR)
    elif shape == "keep":
        extra = ("--keep",)
    outcome = _run(
        tmp_path,
        _args("claude-code", claude=root, extra=(*extra, "--since", "2026-11-02")),
        env={"REALORNOISE_HOME": str(store)},
    )
    assert outcome.body is not None
    assert outcome.body["kept_table"] == state
    assert outcome.body["keep"] is keep
    assert outcome.body["since_given"] is True


def test_a_setting_present_only_in_the_kept_table_is_compared(tmp_path: Path) -> None:
    """Item 51: a setting present only in kept rows, with more after-period responses than any
    setting in the logs, is compared, and F14 counts the others."""
    logs = _uniform(ALTERNATING, DROPPED)
    stored_plans = {
        **{
            day: Day(counts=(value,) * 30)
            for day, value in zip(BEFORE_DAYS, ALTERNATING, strict=True)
        },
        **{day: Day(counts=(10,) * 30) for day in AFTER_DAYS},
    }
    rows = [
        _kept_from_day("claude-code", day, plan, model=CODEX_OTHER, effort="low")
        for day, plan in stored_plans.items()
    ]
    outcome, _ = _kept_run(tmp_path, logs, rows)
    tool = outcome.tool()
    # The kept setting has 150 after-period responses against the logs setting's 100.
    assert (tool["model"], tool["effort"]) == (CODEX_OTHER, "low")
    assert tool["other_settings"] == 1
    assert F14.format(1) in outcome.lines
    sources = dict.fromkeys(stored_plans, "kept")
    _check(outcome, "claude-code", stored_plans, sources=sources)
    assert (tool["kept_days_before"], tool["kept_days_after"]) == (10, 5)
    assert F21.format(b=10, a=5) in outcome.lines


def test_a_valid_table_changes_a_run_without_keep(tmp_path: Path) -> None:
    """Item 57: with `--keep` absent and the table in the resolved directory, kept days enter
    the day lists and F21 prints; the table cannot set the window."""
    logs = {
        **{day: Day(counts=(100,) * 20) for day in BEFORE_DAYS[5:]},
        **{day: Day(counts=(10,) * 20) for day in AFTER_DAYS},
    }
    stored_plans = {
        day: Day(counts=(value,) * 20)
        for day, value in zip(BEFORE_DAYS[:5], ALTERNATING[:5], strict=True)
    }
    rows = [_kept_from_day("claude-code", day, plan) for day, plan in stored_plans.items()]
    # A stored row later than `N` and one for a day the logs already hold.
    rows.append(_kept_from_day("claude-code", NEWEST + timedelta(days=4), Day(counts=(5,) * 40)))
    outcome, path = _kept_run(tmp_path, logs, rows)
    assert outcome.body is not None
    assert outcome.body["keep"] is False
    assert outcome.body["kept_table"] == "read"
    tool = outcome.tool()
    # `N` stays the newest day with a main-thread response in the logs.
    assert tool["after"] == AFTER_PERIOD
    assert tool["split_date"] == SPLIT.isoformat()
    merged, sources = _merge("claude-code", logs, stored_plans)
    _check(outcome, "claude-code", merged, sources=sources)
    assert (tool["kept_days_before"], tool["kept_days_after"]) == (5, 0)
    assert F21.format(b=5, a=0) in outcome.lines

    # A tool with no log file is still ERROR, with stored rows present.
    empty = tmp_path / "empty"
    empty.mkdir()
    error = _run(
        tmp_path,
        _args("claude-code", claude=empty),
        stem="error",
        env={"REALORNOISE_HOME": str(path.parent)},
    )
    assert (error.tool()["result"], error.tool()["reason"]) == ("ERROR", "no_logs")
    assert error.code == 3


def test_the_merged_days_drive_everything_that_reads_days(tmp_path: Path) -> None:
    """Item 58: `v*`, each day's value and usable flag, `first_response_day`, the response-day
    counts and `other_settings` all change when a kept row supplies a day, while `context` and
    `counters` keep the values the logs alone give."""
    logs = _codex_no_drop()
    day = BEFORE_DAYS[0]
    # A kept row of 25 responses at one repeated value moves `v*` from 5 to 9.
    kept_plan = Day(counts=(9,) * 25)
    rows = [_kept_from_day("codex", day, kept_plan, model=CODEX_MODEL)]
    plain, _ = _kept_run(tmp_path / "plain", logs, None, tool="codex")
    outcome, _ = _kept_run(tmp_path / "kept", logs, rows, tool="codex")
    merged, sources = _merge("codex", logs, {day: kept_plan})
    assert _vstar(logs, [*BEFORE_DAYS, *AFTER_DAYS]) == 5
    assert _vstar(merged, [*BEFORE_DAYS, *AFTER_DAYS]) == 9
    tool = _check(outcome, "codex", merged, sources=sources)
    assert plain.tool()["result"] == "NO_DROP"
    assert tool["result"] == "REAL_DROP"
    repeated = tool["measures"][2]
    assert repeated["before_days"][0] == {
        "day": day.isoformat(),
        "count": 25,
        "value": "1/1",
        "source": "kept",
    }
    # The context counts and the reader counters come from the logs only.
    assert tool["context"] == plain.tool()["context"]
    assert tool["counters"] == plain.tool()["counters"]


def test_the_written_rows_cover_every_setting_and_day_in_range(tmp_path: Path) -> None:
    """Item 61: the rows written cover every eligible setting and day from `N-180` to `N`,
    whatever `--model`, `--effort` and `--since` say, and the two omission counts count
    settings and rows, never responses."""
    outside = NEWEST - timedelta(days=150)
    root = tmp_path / "claude"
    plans = _uniform(ALTERNATING, DROPPED)
    write_claude(root, {**plans, outside: Day(counts=(5,) * 4)})
    write_claude(
        root,
        {day: Day(counts=(5,) * 3) for day in (*BEFORE_DAYS[:2], *AFTER_DAYS[:2])},
        session="02",
        prefix="b",
        setting=Setting(CLAUDE_OTHER, "low"),
    )
    # A setting the lists refuse, on ten days: one setting in `settings_not_kept`.
    write_claude(
        root,
        {day: Day(counts=(5,) * 3) for day in BEFORE_DAYS},
        session="03",
        prefix="c",
        setting=Setting(CANARY_MODEL_A, "high"),
    )
    store = tmp_path / "store"
    outcome = _run(
        tmp_path,
        _args(
            "claude-code",
            claude=root,
            extra=(
                "--keep-dir",
                str(store),
                "--model",
                CLAUDE_MODEL,
                "--effort",
                "high",
                "--since",
                "2026-11-05",
            ),
        ),
    )
    tool = outcome.tool()
    assert (tool["model"], tool["effort"]) == (CLAUDE_MODEL, "high")
    assert tool["settings_not_kept"] == 1
    assert tool["days_not_kept"] == 0
    assert F22.format(1) in outcome.lines
    rows = _rows(store / TABLE_NAME)
    settings = {(row["model"], row["effort"]) for row in rows}
    assert settings == {(CLAUDE_MODEL, "high"), (CLAUDE_OTHER, "low")}
    days = {row["day"] for row in rows if row["model"] == CLAUDE_MODEL}
    assert days == {day.isoformat() for day in (outside, *BEFORE_DAYS, *AFTER_DAYS)}
    assert CANARY_MODEL_A not in (store / TABLE_NAME).read_text(encoding="utf-8")


def test_pruning_runs_only_for_a_requested_tool_that_is_not_error(tmp_path: Path) -> None:
    """Item 62: an ERROR tool keeps every stored row, rows before `N-180` included; a run in
    which every requested tool is ERROR writes nothing and leaves the file's bytes."""
    old_claude = NEWEST - timedelta(days=200)
    old_codex = NEWEST - timedelta(days=200)
    rows = [
        _kept_from_day("claude-code", old_claude, Day(counts=(5,) * 3)),
        _kept_from_day("codex", old_codex, Day(counts=(5,) * 3), model=CODEX_MODEL),
    ]
    store = tmp_path / "store"
    write_kept(store / TABLE_NAME, rows)
    # Claude Code has no logs, so it is ERROR; Codex has logs and is pruned.
    claude = tmp_path / "claude"
    claude.mkdir()
    codex = tmp_path / "codex"
    write_codex(codex, _codex_no_drop())
    outcome = _run(
        tmp_path,
        _args("both", claude=claude, codex=codex, extra=("--keep",)),
        env={"REALORNOISE_HOME": str(store)},
    )
    assert [tool["result"] for tool in outcome.tools()] == ["ERROR", "NO_DROP"]
    written = _rows(store / TABLE_NAME)
    days = {(row["tool"], row["day"]) for row in written}
    assert ("claude-code", old_claude.isoformat()) in days
    assert ("codex", old_codex.isoformat()) not in days
    # Every requested tool is ERROR: nothing is written at all.
    empty = tmp_path / "empty"
    empty.mkdir()
    write_kept(store / TABLE_NAME, rows)
    stored = (store / TABLE_NAME).read_bytes()
    all_error = _run(
        tmp_path,
        _args("both", claude=claude, codex=empty, extra=("--keep",)),
        stem="error",
        env={"REALORNOISE_HOME": str(store)},
    )
    assert [tool["result"] for tool in all_error.tools()] == ["ERROR", "ERROR"]
    assert all_error.code == 3
    assert (store / TABLE_NAME).read_bytes() == stored


# --- 12. what the table promises, and where it stops -----------------------------------------
# Record 0017, "What the table promises, and where it stops": the promise holds under every one
# of its conditions and nowhere else. The fixture below builds a history that meets them all:
# immutable records with no late arrival carrying an earlier timestamp, deletion only of batches
# strictly older than 30 times 24 hours, a `--keep` run that captured each deleted day whole
# beforehand with captures at most 29 days apart, and both runs at the same instant with the
# same options, offset and window.

PROMISE_EARLY = tuple(date(2026, 10, 3) + timedelta(days=index) for index in range(10))
PROMISE_BEFORE = (*PROMISE_EARLY, *BEFORE_DAYS)
# The capture: the day after the newest early day ended, 29 days before the final run.
CAPTURE_NOW = datetime(2026, 10, 13, 12, 0, tzinfo=UTC)
# A session file whose responses fall on days on both sides of the deletion boundary, which at
# the final instant (30 times 24 hours before it) runs through 2026-10-12.
SPAN_DAYS = tuple(date(2026, 10, 10) + timedelta(days=index) for index in range(5))


def _promise_plans() -> dict[date, Day]:
    plans = {
        day: Day(counts=(value,) * 20)
        for day, value in zip(PROMISE_BEFORE, (90, 110) * 10, strict=True)
    }
    plans.update({day: Day(counts=(10,) * 20) for day in AFTER_DAYS})
    return plans


def _without_source(tool: Mapping[str, Any]) -> list[list[dict[str, Any]]]:
    return [
        [
            {name: value for name, value in row.items() if name != "source"}
            for side in ("before_days", "after_days")
            for row in measure[side]
        ]
        for measure in tool["measures"]
    ]


def _sources_of(tool: Mapping[str, Any]) -> dict[str, str]:
    return {
        row["day"]: row["source"]
        for measure in tool["measures"]
        for side in ("before_days", "after_days")
        for row in measure[side]
    }


@pytest.mark.parametrize("spanning", [False, True])
def test_the_promise_of_the_kept_table(tmp_path: Path, spanning: bool) -> None:
    """Item 26: under every condition of the promise, the day lists of the retained history and
    of the undeleted history agree once `source` is removed, and the two results agree; the days
    that came from the table carry `source: "kept"`, so the lists are not equal with `source`
    kept. The second case adds a session file that spans the deletion boundary.
    """
    plans = _promise_plans()
    span = {day: Day(counts=(100,) * 20) for day in SPAN_DAYS} if spanning else {}

    # The undeleted history: every file still there, and no table.
    full = tmp_path / "full"
    write_claude_daily(full, plans)
    if span:
        write_claude(full, span, session="span", prefix="sp")
    undeleted = _run(tmp_path, _args("claude-code", claude=full), stem="full")

    # The retained history: the same records, captured by a `--keep` run while they existed and
    # then deleted in whole batches.
    root = tmp_path / "kept"
    paths = write_claude_daily(root, {day: plans[day] for day in PROMISE_EARLY})
    if span:
        write_claude(root, span, session="span", prefix="sp")
    store = tmp_path / "store"
    _raw_run(
        tmp_path,
        _args("claude-code", claude=root, extra=("--keep",)),
        now=CAPTURE_NOW,
        env={"REALORNOISE_HOME": str(store)},
    )
    assert (store / TABLE_NAME).is_file()
    write_claude_daily(root, {day: plans[day] for day in (*BEFORE_DAYS, *AFTER_DAYS)})
    for day in PROMISE_EARLY:
        paths[day].unlink()
    retained = _run(
        tmp_path,
        _args("claude-code", claude=root),
        stem="kept",
        env={"REALORNOISE_HOME": str(store)},
    )

    assert retained.body is not None and retained.body["kept_table"] == "read"
    assert retained.tool()["result"] == undeleted.tool()["result"]
    assert retained.code == undeleted.code
    assert _without_source(retained.tool()) == _without_source(undeleted.tool())
    # The sources differ by construction, so the day lists are not equal with `source` kept.
    assert retained.tool()["measures"] != undeleted.tool()["measures"]
    assert retained.tool()["day_table_sha256"] != undeleted.tool()["day_table_sha256"]
    sources = _sources_of(retained.tool())
    assert all(sources[day.isoformat()] == "logs" for day in (*BEFORE_DAYS, *AFTER_DAYS))
    assert retained.tool()["kept_days_before"] == 10
    if spanning:
        # The three days the spanning file shares with the deleted batches have a larger stored
        # row, so the stored row is used; the two days only the spanning file holds are logs
        # days, where the stored row ties with the logs row or does not exist.
        assert all(sources[day.isoformat()] == "kept" for day in SPAN_DAYS[:3])
        assert all(sources[day.isoformat()] == "logs" for day in SPAN_DAYS[3:])
    else:
        assert all(sources[day.isoformat()] == "kept" for day in PROMISE_EARLY)


def test_a_day_never_captured_whole_stays_lost(tmp_path: Path) -> None:
    """Item 27(a): outside the conditions nothing is promised. Here the first `--keep` run comes
    31 days after a day ended, and that day's batch is already deleted: the day is missing in the
    later run, and the day lists differ from the undeleted history's even after `source` is
    removed."""
    plans = _promise_plans()
    full = tmp_path / "full"
    write_claude_daily(full, plans)
    undeleted = _run(tmp_path, _args("claude-code", claude=full), stem="full")

    root = tmp_path / "kept"
    paths = write_claude_daily(root, plans)
    # At the capture instant the vendor has already deleted every batch strictly older than
    # 30 times 24 hours, so the first four early days were never captured.
    late = datetime(2026, 11, 5, 12, 0, tzinfo=UTC)
    lost = tuple(day for day in PROMISE_EARLY if day <= date(2026, 10, 6))
    assert len(lost) == 4
    for day in lost:
        paths[day].unlink()
    store = tmp_path / "store"
    _raw_run(
        tmp_path,
        _args("claude-code", claude=root, extra=("--keep",)),
        now=late,
        env={"REALORNOISE_HOME": str(store)},
    )
    # Time passes to the final instant and the rest of the early batches go.
    for day in PROMISE_EARLY:
        if day not in lost:
            paths[day].unlink()
    retained = _run(
        tmp_path,
        _args("claude-code", claude=root),
        stem="kept",
        env={"REALORNOISE_HOME": str(store)},
    )
    kept_days = set(_sources_of(retained.tool()))
    full_days = set(_sources_of(undeleted.tool()))
    assert {day.isoformat() for day in lost} <= full_days
    assert not {day.isoformat() for day in lost} & kept_days
    assert _without_source(retained.tool()) != _without_source(undeleted.tool())
    # The six days that were captured whole do come back.
    assert retained.tool()["kept_days_before"] == 6


# --- 13. one size limit, both ways -----------------------------------------------------------
# Record 0017, "One size limit": the reader's limit and the writer's are the same number, read
# as more than 33,554,432 bytes. The filler rows below belong to a tool the run does not
# request, so they are read, kept as stored, and written out again unchanged.


def _compact(row: Mapping[str, Any]) -> str:
    return json.dumps(row, sort_keys=True, separators=(",", ":"))


def _filler(model: str) -> dict[str, Any]:
    return kept_row("codex", date(2026, 1, 2), model=model, effort="high", reasoning=((0, 1),))


def _big_table_text(target: int, *, lead: Mapping[str, Any] | None = None) -> str:
    """A valid table of exactly `target` bytes, with an optional first row of its own.

    The filler rows all have the same shape, so the byte count is chosen by the number of rows
    and then trimmed to the byte by narrowing a few model ids, each of which is one, two or
    three characters shorter.
    """
    head, tail = '{"rows":[', '],"schema":"realornoise-days/1"}\n'
    unit = len(_compact(_filler("gpt-10-10-10"))) + 1
    room = target - len(head) - len(tail) + 1
    if lead is not None:
        room -= len(_compact(lead)) + 1
    count = -(-room // unit)
    extra = count * unit - room
    narrow = [f"gpt-{a}-{b}-{c}" for a in range(1, 10) for b in range(1, 10) for c in range(1, 10)]
    models = narrow[: extra // 3]
    if extra % 3 == 1:
        models.append("gpt-1-10-10")
    elif extra % 3 == 2:
        models.append("gpt-1-1-10")
    wide = (f"gpt-{a}-{b}-{c}" for a, b, c in itertools.product(range(10, 100), repeat=3))
    models.extend(itertools.islice(wide, count - len(models)))
    assert len(models) == count and len(set(models)) == count
    rows = [_filler(model) for model in sorted(models)]
    if lead is not None:
        rows.insert(0, dict(lead))
    text = head + ",".join(_compact(row) for row in rows) + tail
    assert len(text) == target, (len(text), target)
    return text


@pytest.mark.parametrize("size", [SIZE_LIMIT - 1, SIZE_LIMIT, SIZE_LIMIT + 1])
def test_the_one_size_limit_of_the_reader(tmp_path: Path, size: int) -> None:
    """Item 53, the reader: a table of 33,554,431 bytes and one of exactly 33,554,432 bytes are
    read and used; one of 33,554,433 bytes prints F24, is not used, and with `--keep` is left
    byte for byte."""
    logs = _uniform(ALTERNATING, DROPPED)
    day = BEFORE_DAYS[0]
    kept_plan = Day(counts=(300,) * 25)
    lead = _kept_from_day("claude-code", day, kept_plan)
    store = tmp_path / "store"
    store.mkdir(parents=True)
    path = store / TABLE_NAME
    path.write_text(_big_table_text(size, lead=lead), encoding="utf-8")
    assert path.stat().st_size == size
    stored = path.read_bytes()
    root = tmp_path / "claude"
    write_claude(root, logs)
    over = size > SIZE_LIMIT
    # The over-limit case takes `--keep` as well, to show that such a file is not replaced.
    extra = ("--keep",) if over else ()
    outcome = _run(
        tmp_path,
        _args("claude-code", claude=root, extra=extra),
        env={"REALORNOISE_HOME": str(store)},
    )
    assert outcome.body is not None
    if over:
        assert outcome.body["kept_table"] == "unreadable"
        assert outcome.lines.count(F24) == 1
        _check(outcome, "claude-code", logs)
        assert path.read_bytes() == stored
        assert outcome.code == 1
    else:
        assert outcome.body["kept_table"] == "read"
        assert F24 not in outcome.lines
        merged, sources = _merge("claude-code", logs, {day: kept_plan})
        _check(outcome, "claude-code", merged, sources=sources)
        assert outcome.tool()["kept_days_before"] == 1


@pytest.mark.parametrize("shape", ["under", "over"])
def test_the_one_size_limit_of_the_writer(tmp_path: Path, shape: str) -> None:
    """Item 53, the writer: a staged table under the limit is written and is read by the next
    run; a staged table over it prints `Requested output could not be written.`, writes
    nothing, leaves the stored table and every requested output as they were, and exits 3.

    The record fixes the limit in bytes but not which separators the canonical form uses, so
    the byte that decides cannot be placed from outside: these two sizes are under and over the
    limit under either spelling, with the stored rows of a tool this run does not request
    carried into the staged table.
    """
    logs = _uniform(ALTERNATING, DROPPED)
    store = tmp_path / "store"
    store.mkdir(parents=True)
    path = store / TABLE_NAME
    size = 20 * 1024 * 1024 if shape == "under" else SIZE_LIMIT
    path.write_text(_big_table_text(size), encoding="utf-8")
    stored = path.read_bytes()
    root = tmp_path / "claude"
    write_claude(root, logs)
    report = tmp_path / "report.md"
    report.write_text("old", encoding="utf-8")
    code, printed, failed = _raw_run(
        tmp_path,
        [*_args("claude-code", claude=root), "--keep", "--markdown", str(report)],
        env={"REALORNOISE_HOME": str(store)},
    )
    if shape == "under":
        assert code == 1
        assert failed == ""
        assert path.read_bytes() != stored
        rows = _rows(path)
        assert any(row["tool"] == "claude-code" for row in rows)
        # The next run reads what this one wrote.
        again = _run(
            tmp_path,
            _args("claude-code", claude=root),
            env={"REALORNOISE_HOME": str(store)},
        )
        assert again.body is not None and again.body["kept_table"] == "read"
    else:
        assert code == 3
        assert printed == ""
        assert failed.splitlines() == [USAGE_ERRORS["unwritable"]]
        assert path.read_bytes() == stored
        assert report.read_text(encoding="utf-8") == "old"
