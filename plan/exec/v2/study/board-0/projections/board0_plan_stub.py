"""Reply-0: stand-in snapshot and oracle named by the plan-only descriptors. Never graded."""

from __future__ import annotations

from typing import Any


def snapshot(task: dict[str, Any], workdir: str) -> dict[str, Any]:
    del task, workdir
    return {}


def passed(task: dict[str, Any], final_state: dict[str, Any]) -> bool:
    del task, final_state
    return False
