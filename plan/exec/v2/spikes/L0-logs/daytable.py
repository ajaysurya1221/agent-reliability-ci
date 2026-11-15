"""Daily measures: system-local dates, exact medians and shares, no subagents."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from fractions import Fraction

from records import EditResult, Response, Tool

Group = tuple[Tool, str, str]


@dataclass(frozen=True)
class Day:
    date: date
    responses: int
    m1: Fraction | None
    m2: Fraction | None
    m3: Fraction | None
    m4: Fraction | None
    edits: int = 0
    known_reasoning: int = 0


def median(values: list[int]) -> Fraction | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    return (
        Fraction(ordered[mid]) if len(ordered) % 2 else Fraction(ordered[mid - 1] + ordered[mid], 2)
    )


def build_daytable(records: Iterable[Response | EditResult]) -> dict[Group, list[Day]]:
    responses: dict[Group, dict[date, list[Response]]] = defaultdict(lambda: defaultdict(list))
    edits: dict[Group, dict[date, list[EditResult]]] = defaultdict(lambda: defaultdict(list))
    for record in records:
        if not record.main_thread:
            continue
        key: Group = record.tool, record.model, record.effort
        local_day = record.timestamp.astimezone().date()
        if isinstance(record, Response):
            responses[key][local_day].append(record)
        else:
            edits[key][local_day].append(record)
    table: dict[Group, list[Day]] = {}
    for key, days in sorted(responses.items()):
        pooled = Counter(
            r.reasoning_tokens
            for rs in days.values()
            if len(rs) >= 20
            for r in rs
            if r.reasoning_tokens is not None and r.reasoning_tokens > 0
        )
        # Deterministic tie break: smallest positive value among modes.
        mode = min(pooled, key=lambda v: (-pooled[v], v)) if pooled else None
        rows: list[Day] = []
        for day, rs in sorted(days.items()):
            values = [r.reasoning_tokens for r in rs if r.reasoning_tokens is not None]
            positives = [v for v in values if v > 0]
            es = edits[key][day]
            usable = len(rs) >= 20
            rows.append(
                Day(
                    day,
                    len(rs),
                    median(positives) if usable else None,
                    Fraction(values.count(0), len(rs)) if usable and values else None,
                    Fraction(sum(e.failed for e in es), len(es))
                    if usable and len(es) >= 10 and key[0] == "claude"
                    else None,
                    Fraction(positives.count(mode), len(positives))
                    if usable and positives and mode is not None and key[0] == "codex"
                    else None,
                    len(es),
                    len(values),
                )
            )
        table[key] = rows
    return table
