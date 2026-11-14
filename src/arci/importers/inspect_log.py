"""Read the JSON form of one Inspect log; epochs are logical rounds."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import Any

from arci.importers import (
    OutcomeError,
    OutcomeValue,
    ParsedInput,
    Row,
    check_identity,
    loads_json,
)
from arci.outcome_report import text as fixed_text


def _mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("expected an object")
    return value


def _list(value: Any) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError("expected an array")
    return value


def _id(value: Any, types: dict[str, type[Any]], known: Mapping[str, str] | None) -> str:
    if type(value) not in {int, str} or value == "":
        raise ValueError("sample ids must be non-empty strings or integers")
    task_id = str(value)
    old_type = types.setdefault(task_id, type(value))
    kind = "integer" if type(value) is int else "string"
    if old_type is not type(value) or (known is not None and known.get(task_id, kind) != kind):
        raise OutcomeError(fixed_text("E13", id=task_id))
    return task_id


def _outcome(value: Any, task_id: str, threshold: Fraction | None) -> OutcomeValue:
    if value == "C" or value is True:
        return "pass"
    if value == "I" or value is False:
        return "fail"
    if isinstance(value, int | Decimal) and not isinstance(value, bool) and threshold is not None:
        if isinstance(value, Decimal) and not value.is_finite():
            raise ValueError("non-finite score")
        return "pass" if Fraction(value) >= threshold else "fail"
    raise OutcomeError(fixed_text("E10", value=value, id=task_id))


def read(
    text: str,
    *,
    path: str,
    arm: str,
    position: int,
    tasks: frozenset[str] | None,
    seen: set[tuple[str, int]],
    score: str | None = None,
    pass_at_least: Fraction | None = None,
    expected_score: str | None = None,
    known_id_types: Mapping[str, str] | None = None,
) -> ParsedInput:
    """Validate the header and observations without choosing among scorers."""
    if Path(path).suffix.lower() == ".eval":
        raise OutcomeError(fixed_text("E7"))
    try:
        log = _mapping(loads_json(text.removeprefix("\ufeff")))
        evaluation = _mapping(log["eval"])
        config = _mapping(evaluation["config"])
        epochs = config["epochs"]
        if type(epochs) is not int or epochs < 1:
            raise ValueError("epochs must be a positive integer")
        dataset = _mapping(evaluation["dataset"])
        types: dict[str, type[Any]] = {}
        inventory: set[str] = set()
        for value in _list(dataset["sample_ids"]):
            task_id = _id(value, types, known_id_types)
            if tasks is not None and task_id not in tasks:
                raise OutcomeError(fixed_text("E1", id=task_id))
            if task_id in inventory:
                raise ValueError("duplicate header sample id")
            inventory.add(task_id)
        scorers: list[str] = []
        for entry in _list(evaluation["scorers"]):
            name = _mapping(entry)["name"]
            if not isinstance(name, str) or not name or name in scorers:
                raise ValueError("scorer names must be non-empty and unique")
            scorers.append(name)
        if not scorers:
            raise ValueError("the log must declare a scorer")
        if score is None:
            if len(scorers) > 1:
                raise OutcomeError(fixed_text("E11", path=path))
            score = scorers[0]
        elif score not in scorers:
            raise OutcomeError(fixed_text("E12", name=score, path=path))
        if expected_score is not None and score != expected_score:
            raise OutcomeError(fixed_text("E12", name=expected_score, path=path))
        rows: list[Row] = []
        for value in _list(log["samples"]):
            sample = _mapping(value)
            task_id = _id(sample["id"], types, known_id_types)
            epoch = sample["epoch"]
            if type(epoch) is not int:
                raise ValueError("epoch must be an integer")
            check_identity(task_id, epoch, arm=arm, tasks=tasks, seen=seen)
            if task_id not in inventory or not 1 <= epoch <= epochs:
                raise ValueError("sample disagrees with the header")
            error = sample.get("error")
            if error is not None and not isinstance(error, dict):
                raise ValueError("sample error must be an object")
            scores = _mapping(sample.get("scores", {}))
            if any(name not in scorers for name in scores):
                raise ValueError("sample scorer absent from the header")
            outcome: OutcomeValue | None
            if error is not None:
                outcome = "error"
            elif score not in scores:
                outcome = None
            else:
                selected = _mapping(scores[score])
                outcome = _outcome(selected.get("value"), task_id, pass_at_least)
            rows.append(Row(task_id, epoch, outcome))
        return ParsedInput(
            tuple(rows),
            range(1, epochs + 1),
            score=score,
            id_types=tuple(
                (key, "integer" if kind is int else "string") for key, kind in types.items()
            ),
        )
    except OutcomeError:
        raise
    except (KeyError, ValueError, TypeError, OverflowError, RecursionError) as error:
        raise OutcomeError(fixed_text("E6", path=path)) from error
