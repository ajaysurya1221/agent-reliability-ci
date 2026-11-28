"""Export one MLflow evaluation as ARCI task outcomes."""

import json
import math
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path


def mlflow_rows(
    records: Iterable[Mapping[str, object]], scorer: str, task_id: Callable[[object], str]
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for record in records:
        key = task_id(record["request"])
        if key in seen:
            raise ValueError(f"duplicate task id: {key}")
        seen.add(key)

        message = record.get(f"{scorer}/error_message")
        no_error = message is None or (isinstance(message, float) and math.isnan(message))
        value = record.get(f"{scorer}/value")
        outcome = "error"
        state = record.get("state")
        if isinstance(state, str) and state == "OK" and no_error:
            if value is True or (isinstance(value, str) and value == "yes"):
                outcome = "pass"
            elif value is False or (isinstance(value, str) and value == "no"):
                outcome = "fail"
        rows.append({"task_id": key, "outcome": outcome})
    return rows


def write_jsonl(
    path: Path,
    records: Iterable[Mapping[str, object]],
    scorer: str,
    task_id: Callable[[object], str],
) -> None:
    rows = mlflow_rows(records, scorer, task_id)
    with path.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row) + "\n")
