"""Strict, bounded daily count storage. No private log strings cross this boundary."""

from __future__ import annotations

import json
import stat
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, StrictInt, StrictStr, model_validator

from .records import EFFORTS, ReadResult, Tool, render_model
from .schema import Day, KeptState, Model, NonNegative

MAX_BYTES = 33_554_432
MAX_COUNTS = 5_000
READ_ATTEMPTS = 4
FILENAME = "days-1.json"
Key = tuple[Tool, int, str, str, str]


class KeptRow(Model):
    tool: Tool
    utc_offset_minutes: Annotated[StrictInt, Field(gt=-1440, lt=1440)]
    model: StrictStr
    effort: StrictStr
    day: Day
    responses: NonNegative
    reasoning: tuple[tuple[NonNegative, Annotated[StrictInt, Field(gt=0)]], ...] = Field(
        max_length=MAX_COUNTS
    )
    reasoning_unknown: NonNegative
    edits: NonNegative | None
    edits_failed: NonNegative | None

    @property
    def key(self) -> Key:
        return self.tool, self.utc_offset_minutes, self.model, self.effort, self.day

    @property
    def pair(self) -> tuple[int, int]:
        return self.responses, self.edits or 0

    @model_validator(mode="after")
    def _row(self) -> KeptRow:
        if render_model(self.model) is None or self.effort not in EFFORTS:
            raise ValueError("invalid_setting")
        counts = [count for count, _ in self.reasoning]
        if counts != sorted(set(counts)):
            raise ValueError("invalid_histogram_order")
        if self.responses != self.reasoning_unknown + sum(n for _, n in self.reasoning):
            raise ValueError("invalid_response_count")
        if self.tool == "codex":
            if self.edits is not None or self.edits_failed is not None:
                raise ValueError("invalid_codex_edits")
        elif self.edits is None or self.edits_failed is None or self.edits_failed > self.edits:
            raise ValueError("invalid_edit_count")
        if not self.responses and not self.edits:
            raise ValueError("empty_row")
        return self


class KeptTable(Model):
    schema_version: Literal["realornoise-days/1"] = Field(alias="schema")
    rows: tuple[KeptRow, ...]

    @model_validator(mode="after")
    def _rows(self) -> KeptTable:
        keys = [row.key for row in self.rows]
        if keys != sorted(set(keys)):
            raise ValueError("invalid_row_order")
        return self


def _object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_key")
        result[key] = value
    return result


def read(path: Path) -> tuple[KeptState, tuple[KeptRow, ...]]:
    """Read the table; read the path again when it appeared between two calls.

    A run with `--keep` reads the table once before it holds the directory lock, so another
    run may be installing the table at that moment. A writer takes the path from absent to
    an empty placeholder, back to absent, then to the finished table. An attempt is repeated
    only when one call found nothing and the next call found something, so each repeat uses
    up one appearance of the path, and the attempts give an answer when the path appears at
    most `READ_ATTEMPTS - 1` times during the read. One writer makes it appear twice (three
    attempts at most). A writer that fails after its placeholder, followed by a writer that
    succeeds, makes it appear three times (four attempts at most). Two writers that succeed
    one after the other make it appear twice: the second one replaces the table in one step.

    A path that appears more often can use up every attempt, for example with a writer that
    is interrupted after it moved a new table into place and rolls it back, followed by
    another writer (five attempts). The table is then reported unreadable. That is safe:
    the run uses no table, writes none and says so. These counts take the writers one at a
    time, as under the directory lock. Where the platform has no such lock the run goes on
    without it (record 0017), and writers that overlap can make the path appear more often.

    The count is fixed and no attempt waits. A dangling symlink is found by `lstat()` and
    missed by `stat()` at every attempt, and is unreadable.
    """
    for _ in range(READ_ATTEMPTS):
        result = _read_once(path)
        if result is not None:
            return result
    return "unreadable", ()


def _read_once(path: Path) -> tuple[KeptState, tuple[KeptRow, ...]] | None:
    """One attempt. None: the path was absent at one call and present at the next."""
    try:
        info = path.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_BYTES:
            return "unreadable", ()
        with path.open("rb") as stream:
            raw = stream.read(MAX_BYTES + 1)
        if not raw:
            return "absent", ()
        if len(raw) > MAX_BYTES:
            return "unreadable", ()
        data: object = json.loads(raw.decode("utf-8"), object_pairs_hook=_object)
        table = KeptTable.model_validate(data)
        return "read", table.rows
    except (FileNotFoundError, NotADirectoryError):
        # The path is absent when it does not exist, also when a parent is not a
        # directory. A path that exists now is a dangling symlink, or a file that another
        # run put there after the call that failed: the caller reads it again.
        try:
            path.lstat()
        except (FileNotFoundError, NotADirectoryError):
            return "absent", ()
        except OSError:
            return "unreadable", ()
        return None
    except (OSError, ValueError, RecursionError):
        return "unreadable", ()


@dataclass(slots=True)
class DailyRow:
    """Uncapped internal row: reader identities and aggregate numbers only."""

    responses: int = 0
    reasoning: Counter[int] = field(default_factory=Counter)
    reasoning_unknown: int = 0
    edits: int = 0
    edits_failed: int = 0
    source: Literal["logs", "kept"] = "logs"

    @property
    def pair(self) -> tuple[int, int]:
        return self.responses, self.edits


DayKey = tuple[int, int, date]


def from_logs(
    result: ReadResult, *, utc_offset: timedelta, now: datetime
) -> dict[DayKey, DailyRow]:
    rows: dict[DayKey, DailyRow] = {}
    zone = timezone(utc_offset)
    for response in result.responses:
        if (
            not response.main_thread
            or not response.in_project
            or response.when.tzinfo is None
            or response.when > now
        ):
            continue
        key = response.model, response.effort, response.when.astimezone(zone).date()
        row = rows.setdefault(key, DailyRow())
        row.responses += 1
        if response.reasoning is None:
            row.reasoning_unknown += 1
        else:
            row.reasoning[response.reasoning] += 1
    for edit in result.edits:
        if (
            not edit.main_thread
            or not edit.in_project
            or edit.when.tzinfo is None
            or edit.when > now
        ):
            continue
        key = edit.model, edit.effort, edit.when.astimezone(zone).date()
        row = rows.setdefault(key, DailyRow())
        row.edits += 1
        row.edits_failed += edit.failed
    return rows


def use(
    logs: dict[DayKey, DailyRow],
    stored: Sequence[KeptRow],
    *,
    result: ReadResult,
    offset: int,
    first: date,
    newest: date,
    window_end: date | None = None,
) -> dict[DayKey, DailyRow]:
    end = newest if window_end is None else window_end
    rows = {key: row for key, row in logs.items() if first <= key[2] <= end}
    models = {name: i for i, name in enumerate(result.models) if name is not None}
    efforts = {name: i for i, name in enumerate(result.efforts) if name is not None}
    for saved in stored:
        if saved.tool != result.tool or saved.utc_offset_minutes != offset:
            continue
        day = date.fromisoformat(saved.day)
        if not first <= day <= newest:
            continue
        key = models[saved.model], efforts[saved.effort], day
        if key not in rows or rows[key].pair < saved.pair:
            rows[key] = DailyRow(
                saved.responses,
                Counter(dict(saved.reasoning)),
                saved.reasoning_unknown,
                saved.edits or 0,
                saved.edits_failed or 0,
                "kept",
            )
    return rows


def for_write(
    logs: dict[DayKey, DailyRow], result: ReadResult, *, offset: int, newest: date
) -> tuple[tuple[KeptRow, ...], int, int]:
    rows: list[KeptRow] = []
    rejected: set[tuple[int, int]] = set()
    omitted = 0
    first = newest - timedelta(days=180)
    for (model, effort, day), row in logs.items():
        if not first <= day <= newest:
            continue
        model_name, effort_name = result.models[model], result.efforts[effort]
        if model_name is None or effort_name is None:
            rejected.add((model, effort))
            continue
        if len(row.reasoning) > MAX_COUNTS:
            omitted += 1
            continue
        rows.append(
            KeptRow(
                tool=result.tool,
                utc_offset_minutes=offset,
                model=model_name,
                effort=effort_name,
                day=day.isoformat(),
                responses=row.responses,
                reasoning=tuple(sorted(row.reasoning.items())),
                reasoning_unknown=row.reasoning_unknown,
                edits=row.edits if result.tool == "claude-code" else None,
                edits_failed=row.edits_failed if result.tool == "claude-code" else None,
            )
        )
    return tuple(sorted(rows, key=lambda row: row.key)), len(rejected), omitted


def merge(
    stored: Sequence[KeptRow], updates: Sequence[KeptRow], newest: dict[Tool, date]
) -> tuple[KeptRow, ...]:
    cutoffs = {tool: (day - timedelta(days=180)).isoformat() for tool, day in newest.items()}
    rows = {
        row.key: row for row in stored if row.tool not in cutoffs or row.day >= cutoffs[row.tool]
    }
    for row in updates:
        if row.key not in rows or row.pair >= rows[row.key].pair:
            rows[row.key] = row
    return tuple(rows[key] for key in sorted(rows))


def serialize(rows: Sequence[KeptRow]) -> str:
    return (
        json.dumps(
            {"schema": "realornoise-days/1", "rows": [row.model_dump(mode="json") for row in rows]},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        + "\n"
    )
