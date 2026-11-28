"""Read one prompt/provider cell from a promptfoo results-v3 JSON export."""

from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import dataclass
from typing import Any, NamedTuple

from arci.hashing import hash_record
from arci.importers import OutcomeValue

READER = "promptfoo/1"
TESTED_VERSIONS = ("0.125.1", "0.126.0")


class PromptfooError(ValueError):
    """A fixed conversion refusal, independent of the imported-outcomes E-codes."""


class Cell(NamedTuple):
    prompt: int
    provider: str

    def __str__(self) -> str:
        return f"prompt={self.prompt} provider={json.dumps(self.provider, ensure_ascii=False)}"


@dataclass(frozen=True)
class PromptfooRow:
    task_id: str
    outcome: OutcomeValue
    round: int | None


@dataclass(frozen=True)
class PromptfooResult:
    rows: tuple[PromptfooRow, ...]
    cache: bool | None
    tool_version: str | None
    run_id: str | None
    run_time: str | None
    cells: tuple[Cell, ...]
    selected_cell: Cell


def _unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    obj = dict(pairs)
    if len(obj) != len(pairs):
        raise PromptfooError("duplicate JSON key")
    return obj


def _finite_float(token: str) -> float:
    number = float(token)
    if not math.isfinite(number):
        raise PromptfooError("non-finite JSON number")
    return number


def _check_unicode(value: object) -> None:
    if isinstance(value, str):
        value.encode("utf-8")
    elif isinstance(value, dict):
        for key, item in value.items():
            _check_unicode(key)
            _check_unicode(item)
    elif isinstance(value, list):
        for item in value:
            _check_unicode(item)


def _object(value: object, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PromptfooError(f"{field} must be a JSON object")
    return value


def _array(value: object, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise PromptfooError(f"{field} must be an array")
    return value


def _optional_text(value: object, field: str) -> str | None:
    if value is not None and not isinstance(value, str):
        raise PromptfooError(f"{field} must be a string or null")
    return value


def _cell(row: dict[str, Any]) -> Cell:
    index = row.get("promptIdx")
    if type(index) is not int:
        raise PromptfooError("promptIdx must be an integer")
    provider = _object(row.get("provider"), "provider")
    label = provider.get("label")
    if label is None:
        label = provider.get("id")
    if not isinstance(label, str):
        raise PromptfooError("provider needs a string label or id")
    return Cell(index, label)


def task_id(test_case: object) -> str:
    """Compute the cross-run identity from the test case's description and variables."""
    case = _object(test_case, "testCase")
    description = _optional_text(case.get("description"), "testCase.description")
    variables = case.get("vars")
    if variables is None:
        variables = {}
    digest = hash_record({"description": description, "vars": _object(variables, "testCase.vars")})
    return f"{(description or 'test')[:80]} #{digest[:16]}"


def _outcome(row: dict[str, Any]) -> OutcomeValue:
    success, reason = row.get("success"), row.get("failureReason")
    if type(success) is not bool:
        raise PromptfooError("success must be a boolean")
    if type(reason) is not int or reason not in (0, 1, 2):
        raise PromptfooError("failureReason must be an integer 0, 1 or 2")
    if (reason == 0) != success:
        raise PromptfooError("failureReason contradicts success")
    if reason == 2:
        return "error"
    return "pass" if success else "fail"


def _optional_object(value: object, field: str) -> dict[str, Any]:
    return {} if value is None else _object(value, field)


def _cache_count(value: object, field: str) -> None:
    if isinstance(value, (float, int)) and value > 0:
        raise PromptfooError(f"cache use reported by {field}")


def _check_result_cache(results: dict[str, Any], stats: dict[str, Any]) -> None:
    _cache_count(stats.get("cacheHits"), "results.stats.cacheHits")
    for prompt in _array(results.get("prompts", []), "results.prompts"):
        metrics = _optional_object(_object(prompt, "prompt").get("metrics"), "prompt.metrics")
        _cache_count(
            metrics.get("testCacheHitCount"), "results.prompts[].metrics.testCacheHitCount"
        )
    stability = _optional_object(results.get("repeatStability"), "results.repeatStability")
    _cache_count(stability.get("cachedResults"), "results.repeatStability.cachedResults")
    for group in _array(stability.get("groups", []), "repeatStability.groups"):
        _cache_count(
            _object(group, "group").get("cached"), "results.repeatStability.groups[].cached"
        )


def _check_grading_cache(value: object) -> None:
    if value is None:
        return
    grade = _object(value, "gradingResult")
    metadata = _optional_object(grade.get("metadata"), "gradingResult.metadata")
    if metadata.get("cachedResponse") is True:
        raise PromptfooError("cache use reported by gradingResult metadata.cachedResponse")
    for child in _array(grade.get("componentResults", []), "gradingResult.componentResults"):
        _check_grading_cache(child)


def _read_row(row: dict[str, Any]) -> PromptfooRow:
    response = _optional_object(row.get("response"), "response")
    if response.get("cached") is True:
        raise PromptfooError("cache use reported by response.cached")
    metadata = _optional_object(response.get("metadata"), "response.metadata")
    http = _optional_object(metadata.get("http"), "response.metadata.http")
    status = http.get("status")
    if isinstance(status, (int, float)) and 400 <= status <= 599 and status == int(status):
        raise PromptfooError("response.metadata.http.status is in the HTTP error range 400 to 599")
    _check_grading_cache(row.get("gradingResult"))
    index = row.get("repeatIndex")
    if index is not None and (type(index) is not int or index < 0):
        raise PromptfooError("repeatIndex must be a non-negative integer or null")
    return PromptfooRow(
        task_id(row.get("testCase")), _outcome(row), None if index is None else index + 1
    )


def _check_rounds(rows: list[PromptfooRow], options: dict[str, Any]) -> None:
    by_round: dict[int | None, set[str]] = {}
    for row in rows:
        tasks = by_round.setdefault(row.round, set())
        if row.task_id in tasks:
            raise PromptfooError("duplicate task id in the same round of the selected cell")
        tasks.add(row.task_id)
    if None in by_round:
        if len(by_round) != 1:
            raise PromptfooError("selected cell mixes rows with and without repeatIndex")
        repeat = options.get("repeat", 1)
        if type(repeat) is not int or repeat != 1:
            raise PromptfooError(
                "rows without repeatIndex require runtimeOptions.repeat 1 or absent"
            )
        return
    if any(i not in by_round for i in range(1, len(by_round) + 1)):
        raise PromptfooError("rounds must be 1 to N without gaps")
    repeat = options.get("repeat")
    if type(repeat) is not int or repeat != len(by_round):
        raise PromptfooError("round count differs from runtimeOptions.repeat")
    if any(tasks != by_round[1] for tasks in by_round.values()):
        raise PromptfooError("rounds of the selected cell have different task ids")


def read(
    source: bytes | str, *, prompt: int | None = None, provider: str | None = None
) -> PromptfooResult:
    """Validate the captured export, then select exactly one cell in source order."""
    try:
        text = source.decode("utf-8") if isinstance(source, bytes) else source
        document = json.loads(
            text,
            object_pairs_hook=_unique_keys,
            parse_float=_finite_float,
            parse_constant=_finite_float,
        )
        _check_unicode(document)
        return _read_export(_object(document, "input"), prompt, provider)
    except PromptfooError:
        raise
    except UnicodeEncodeError as exc:
        raise PromptfooError("lone surrogate in JSON string") from exc
    except RecursionError as exc:
        raise PromptfooError("JSON nesting is too deep") from exc
    except ValueError as exc:
        raise PromptfooError("input is not valid UTF-8 JSON") from exc


def _read_export(
    document: dict[str, Any], prompt: int | None, provider: str | None
) -> PromptfooResult:
    results = _object(document.get("results"), "results")
    version = results.get("version")
    if type(version) is not int or version != 3:
        raise PromptfooError("results.version must be 3")
    stats = _object(results.get("stats"), "results.stats")
    _check_result_cache(results, stats)
    grouped: dict[Cell, list[PromptfooRow]] = {}
    counts: Counter[str] = Counter()
    for value in _array(results.get("results"), "results.results"):
        row = _object(value, "result row")
        cell = _cell(row)
        parsed = _read_row(row)
        counts[parsed.outcome] += 1
        grouped.setdefault(cell, []).append(parsed)
    for outcome, field in (("pass", "successes"), ("fail", "failures"), ("error", "errors")):
        count = stats.get(field)
        if type(count) is not int or count != counts[outcome]:
            raise PromptfooError(f"whole-file recount differs from results.stats.{field}")

    cells = tuple(sorted(grouped))
    matches = [
        cell
        for cell in cells
        if (prompt is None or prompt == cell.prompt)
        and (provider is None or provider == cell.provider)
    ]
    if len(matches) != 1:
        inventory = ", ".join(map(str, cells)) or "(none)"
        reason = "selection matches multiple cells" if matches else "selection matches no cell"
        raise PromptfooError(f"{reason}; available cells: {inventory}")
    selected = matches[0]
    rows = grouped[selected]
    options = _optional_object(document.get("runtimeOptions"), "runtimeOptions")
    _check_rounds(rows, options)
    cache = options.get("cache")
    if cache is not None and type(cache) is not bool:
        raise PromptfooError("runtimeOptions.cache must be a boolean or null")
    metadata = _optional_object(document.get("metadata"), "metadata")
    return PromptfooResult(
        tuple(rows),
        cache,
        _optional_text(metadata.get("promptfooVersion"), "metadata.promptfooVersion"),
        _optional_text(document.get("evalId"), "evalId"),
        _optional_text(results.get("timestamp"), "results.timestamp"),
        cells,
        selected,
    )
