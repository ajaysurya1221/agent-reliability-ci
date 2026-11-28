"""Export one Langfuse experiment as ARCI task outcomes."""

import json
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Protocol, TypeVar

T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)


class Evaluation(Protocol):
    @property
    def name(self) -> str: ...
    @property
    def value(self) -> object: ...


class ItemResult(Protocol[T_co]):
    @property
    def item(self) -> T_co: ...
    @property
    def evaluations(self) -> Iterable[Evaluation]: ...


def langfuse_rows(
    expected_ids: Iterable[str],
    item_results: Iterable[ItemResult[T]],
    evaluation: str,
    task_id: Callable[[T], str],
) -> list[dict[str, str]]:
    outcomes: dict[str, str] = {}
    for key in expected_ids:
        if key in outcomes:
            raise ValueError(f"duplicate expected task id: {key}")
        outcomes[key] = "error"

    seen: set[str] = set()
    for result in item_results:
        key = task_id(result.item)
        if key not in outcomes:
            raise ValueError(f"unexpected task id: {key}")
        if key in seen:
            raise ValueError(f"duplicate task id: {key}")
        seen.add(key)
        scores = [e.value for e in result.evaluations if e.name == evaluation]
        if len(scores) > 1:
            raise ValueError(f"duplicate evaluation {evaluation} for {key}")
        if scores and isinstance(value := scores[0], (int, float)):
            if value == 1:
                outcomes[key] = "pass"
            elif value == 0:
                outcomes[key] = "fail"
    return [{"task_id": key, "outcome": outcome} for key, outcome in outcomes.items()]


def write_jsonl(
    path: Path,
    expected_ids: Iterable[str],
    item_results: Iterable[ItemResult[T]],
    evaluation: str,
    task_id: Callable[[T], str],
) -> None:
    rows = langfuse_rows(expected_ids, item_results, evaluation, task_id)
    with path.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row) + "\n")
