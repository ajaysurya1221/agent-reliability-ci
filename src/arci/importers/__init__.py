"""Shared, format-independent types for imported observations.

Importing this package does not import an XML parser or any optional evaluation tool.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal

from arci.outcome_report import text

OutcomeValue = Literal["pass", "fail", "error"]


class OutcomeError(ValueError):
    """A validation failure with its already-rendered, fixed public reason."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True)
class Row:
    task_id: str
    round: int
    outcome: OutcomeValue | None


@dataclass(frozen=True)
class ParsedInput:
    rows: tuple[Row, ...]
    rounds: tuple[int, ...] | range
    assigned: bool = False
    score: str | None = None
    id_types: tuple[tuple[str, str], ...] = ()


def check_identity(
    task_id: str,
    round: int,
    *,
    arm: str,
    tasks: frozenset[str] | None,
    seen: set[tuple[str, int]],
) -> None:
    """Check observations in file order, retaining duplicate identity across files."""
    if tasks is not None and task_id not in tasks:
        raise OutcomeError(text("E1", id=task_id))
    identity = (task_id, round)
    if identity in seen:
        raise OutcomeError(text("E2", arm=arm, id=task_id, n=round))
    seen.add(identity)


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _constant(value: str) -> Any:
    raise ValueError(f"non-finite JSON number: {value}")


def loads_json(value: str) -> Any:
    """Read JSON without duplicate keys or binary rounding of decimal scores."""
    return json.loads(
        value,
        object_pairs_hook=_object,
        parse_float=Decimal,
        parse_constant=_constant,
    )
