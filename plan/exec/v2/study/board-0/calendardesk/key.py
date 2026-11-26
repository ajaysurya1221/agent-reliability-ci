"""Read a calendar task's expected answer from the seeded snapshot."""

from typing import cast

from calendar_world import make_tools
from pydantic import JsonValue


def answer(task_row: dict[str, JsonValue], seed: int) -> int | str:
    task = cast(dict[str, JsonValue], task_row["task"])
    source = cast(dict[str, str], task_row["source"])
    section, field = source["field"].split(".")
    snapshot = make_tools(task, seed).snapshot()
    return cast(dict[str, int | str], snapshot[section])[field]
