"""Small, sanitised records. Raw log text never belongs in a record or diagnostic."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, cast

Tool = Literal["claude", "codex"]
JSON = None | bool | int | float | str | list["JSON"] | dict[str, "JSON"]
MODEL = re.compile(r"[a-z0-9][a-z0-9._-]{1,48}\Z")
EFFORTS = frozenset({"none", "minimal", "low", "medium", "high", "xhigh", "max", "other"})
EDIT_TOOLS = frozenset({"Edit", "Write", "MultiEdit", "NotebookEdit"})


def model_id(value: JSON) -> str:
    return value if isinstance(value, str) and MODEL.fullmatch(value) else "other"


def effort_id(value: JSON) -> str:
    return value if isinstance(value, str) and value in EFFORTS else "other"


def obj(value: JSON) -> dict[str, JSON]:
    return value if isinstance(value, dict) else {}


def array(value: JSON) -> list[JSON]:
    return value if isinstance(value, list) else []


def integer(value: JSON) -> int | None:
    return value if type(value) is int and value >= 0 else None


def timestamp(value: JSON) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result if result.tzinfo is not None and result.utcoffset() is not None else None
    except (ValueError, OverflowError):
        return None


def json_value(value: object) -> JSON:
    """The JSON decoder is the only caller; cast avoids propagating Any."""
    return cast(JSON, value)


@dataclass(frozen=True)
class Response:
    tool: Tool
    file_index: int
    timestamp: datetime
    model: str
    effort: str
    main_thread: bool
    reasoning_tokens: int | None


@dataclass(frozen=True)
class EditResult:
    tool: Tool
    timestamp: datetime
    main_thread: bool
    failed: bool
    # Needed to prevent m3 from pooling different model/effort groups.
    model: str = "other"
    effort: str = "other"


@dataclass
class Counters:
    files: int = 0
    lines: int = 0
    unparseable_lines: int = 0
    skipped_line_types: int = 0
    unknown_keys: int = 0
    unread_compressed: int = 0
    unread_files: int = 0
    responses: int = 0
    lacking_model: int = 0
    lacking_timestamp: int = 0
    lacking_reasoning: int = 0
    complete_responses: int = 0
    duplicate_responses: int = 0
    skipped_api_errors: int = 0
    missing_response_id: int = 0
    edit_results: int = 0
    denied_edits: int = 0
    unmatched_edits: int = 0
    discovery_errors: int = 0
    filtered_files: int = 0


@dataclass
class ReadResult:
    records: list[Response | EditResult]
    counters: Counters
