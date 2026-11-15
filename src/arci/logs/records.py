"""Closed-vocabulary records and private, non-rendering reader primitives."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, NoReturn, cast

Tool = Literal["claude-code", "codex"]
EFFORTS: frozenset[str] = frozenset({"minimal", "low", "medium", "high", "xhigh", "max"})
MODEL_WORDS: frozenset[str] = frozenset(
    [
        "claude",
        "opus",
        "sonnet",
        "haiku",
        "fable",
        "mythos",
        "instant",
        "gpt",
        "codex",
        "chatgpt",
        "o1",
        "o3",
        "o4",
        "mini",
        "nano",
        "micro",
        "max",
        "pro",
        "turbo",
        "spark",
        "astra",
        "omni",
        "preview",
        "latest",
        "thinking",
        "fast",
        "high",
        "low",
        "medium",
        "xhigh",
        "gemini",
        "flash",
        "ultra",
        "lite",
        "exp",
        "deepseek",
        "chat",
        "reasoner",
        "coder",
        "qwen",
        "glm",
        "kimi",
        "grok",
        "code",
        "mlx",
        "a",
        "b",
        "c",
        "d",
        "e",
        "f",
        "g",
        "h",
        "i",
        "j",
        "k",
        "l",
        "m",
        "n",
        "o",
        "p",
        "q",
        "r",
        "s",
        "t",
        "u",
        "v",
        "w",
        "x",
        "y",
        "z",
    ]
)
_MODEL = re.compile(r"[a-z0-9][a-z0-9._-]{0,47}\Z")
_NUMBER_PART = re.compile(r"(?:[0-9]{1,2}|[0-9]{1,2}[a-z]|[a-z][0-9]{1,2})\Z")
_DATE_PART = re.compile(r"20[0-9]{6}\Z")


def render_model(raw: str) -> str | None:
    """Return only ids composed entirely of approved words and bounded numbers."""
    if not _MODEL.fullmatch(raw):
        return None
    dates = 0
    for part in re.split(r"[-._]", raw):
        if _DATE_PART.fullmatch(part):
            dates += 1
        elif part not in MODEL_WORDS and not _NUMBER_PART.fullmatch(part):
            return None
    return raw if dates <= 1 else None


def effort_of(raw: object) -> str | None:
    return raw if isinstance(raw, str) and raw in EFFORTS else None


@dataclass(frozen=True, slots=True)
class Response:
    tool: Tool
    when: datetime
    model: int
    effort: int
    main_thread: bool
    reasoning: int | None
    version: int
    workdir: int
    in_project: bool


@dataclass(frozen=True, slots=True)
class EditResult:
    tool: Tool
    when: datetime
    model: int
    effort: int
    main_thread: bool
    failed: bool
    in_project: bool


@dataclass(slots=True)
class ReaderCounters:
    files_read: int = 0
    files_unread_compressed: int = 0
    files_unreadable: int = 0
    files_outside_project: int = 0
    lines: int = 0
    lines_not_json: int = 0
    lines_unknown_type: int = 0
    lines_lacking_field: int = 0
    records_in_future: int = 0
    responses: int = 0
    responses_duplicate: int = 0
    responses_without_reasoning: int = 0
    responses_without_setting: int = 0
    edits_denied: int = 0
    edits_unmatched: int = 0


@dataclass(frozen=True, slots=True)
class ReadResult:
    tool: Tool
    responses: tuple[Response, ...]
    edits: tuple[EditResult, ...]
    models: tuple[str | None, ...]
    efforts: tuple[str | None, ...]
    model_order: tuple[int, ...]
    effort_order: tuple[int, ...]
    counters: ReaderCounters


def object_of(value: object) -> dict[str, object]:
    return cast(dict[str, object], value) if isinstance(value, dict) else {}


def array_of(value: object) -> list[object]:
    return cast(list[object], value) if isinstance(value, list) else []


def string_of(value: object) -> str | None:
    return value if isinstance(value, str) else None


def reasoning_of(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def time_of(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
        return parsed.astimezone(UTC) if parsed.tzinfo is not None else None
    except (ValueError, OverflowError):
        return None


def in_project(cwd: str | None, project: Path | None) -> bool:
    if project is None:
        return True
    if not cwd:
        return False
    # Lexical comparison only: no resolve(), stat(), or symlink traversal.
    child, parent = Path(os.path.normpath(cwd)).parts, Path(os.path.normpath(project)).parts
    return child[: len(parent)] == parent


# A fast path for provably valid flat objects of unused types. Unlike a substring
# guess it cannot hide malformed JSON, escaped keys, duplicate type keys, or nested
# content. Complex/ambiguous objects use the decoder and receive the same counters.
_JSON_STRING = r'"(?:[^"\\\x00-\x1f]|\\(?:["\\/bfnrt]|u[0-9a-fA-F]{4}))*"'
_JSON_ATOM = (
    rf"(?:{_JSON_STRING}|true|false|null|-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?)"
)
_WS = r"[ \t\r\n]*"
_FLAT = re.compile(
    rf"{_WS}\{{{_WS}(?:{_JSON_STRING}{_WS}:{_WS}{_JSON_ATOM}{_WS}"
    rf"(?:,{_WS}{_JSON_STRING}{_WS}:{_WS}{_JSON_ATOM}{_WS})*)?\}}{_WS}\Z"
)
_TYPE_FIRST = re.compile(rf'{_WS}\{{{_WS}"type"{_WS}:{_WS}"([a-z_-]+)"{_WS}(?:,|\}})')


def _invalid_constant(value: str) -> NoReturn:
    raise ValueError("invalid JSON constant")


def parse_line(line: str, used: frozenset[str], counts: ReaderCounters) -> dict[str, object] | None:
    counts.lines += 1
    first = _TYPE_FIRST.match(line)
    if (
        first is not None
        and first.group(1) not in used
        and "\\" not in line
        and line.count('"type"') == 1
        and _FLAT.fullmatch(line) is not None
    ):
        counts.lines_unknown_type += 1
        return None
    try:
        value: object = json.loads(line, parse_constant=_invalid_constant)
    except (ValueError, RecursionError):
        counts.lines_not_json += 1
        return None
    if not isinstance(value, dict):
        counts.lines_not_json += 1
        return None
    data = object_of(value)
    kind = data.get("type")
    if not isinstance(kind, str) or kind not in used:
        counts.lines_unknown_type += 1
        return None
    return data
