"""Behaviour contracts: grade one trial from what the tool boundary observed.

Success comes only from the oracle over the environment's final state. The
agent's own claim is never an input. Invariants are limited to tool usage seen
at the boundary; anything else must be rejected up front, not silently skipped.
"""

from __future__ import annotations

import importlib
from collections import Counter
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, cast

import yaml
from pydantic import JsonValue

from arci.fingerprint import normalise
from arci.interfaces import ContractRejected
from arci.schema import ContractResult, ContractSpec, Event, Violation


def resolve(ref: str) -> Callable[..., Any]:
    """Import a "module:function" reference."""
    module_name, _, attr = ref.partition(":")
    target = getattr(importlib.import_module(module_name), attr)
    if not callable(target):
        raise TypeError(f"{ref} is not callable")
    return cast(Callable[..., Any], target)


def validate_contract(spec: ContractSpec) -> None:
    if spec.unobservable:
        listed = ", ".join(spec.unobservable)
        raise ContractRejected(f"invariants outside the tool boundary cannot be enforced: {listed}")


def load_contract(path: Path) -> ContractSpec:
    spec = ContractSpec.model_validate(yaml.safe_load(path.read_text()))
    validate_contract(spec)
    return spec


def _violations(spec: ContractSpec, used: Counter[str]) -> tuple[Violation, ...]:
    total = sum(used.values())
    found: list[Violation] = []
    if spec.max_tool_calls is not None and total > spec.max_tool_calls:
        found.append(
            Violation(
                invariant="max_tool_calls",
                severity="hard",
                detail=f"{total} tool calls, limit {spec.max_tool_calls}",
            )
        )
    for tool in spec.forbidden_tools:
        if used[tool]:
            found.append(
                Violation(invariant="forbidden_tools", severity="hard", detail=f"used {tool}")
            )
    for tool in spec.required_tools:
        if not used[tool]:
            found.append(
                Violation(invariant="required_tools", severity="hard", detail=f"never used {tool}")
            )
    for tool, limit in sorted(spec.max_calls_per_tool.items()):
        if used[tool] > limit:
            found.append(
                Violation(
                    invariant="max_calls_per_tool",
                    severity="hard",
                    detail=f"{tool} called {used[tool]} times, limit {limit}",
                )
            )
    return tuple(found)


def evaluate_contract(
    spec: ContractSpec,
    trial_events: Sequence[Event],
    task: dict[str, JsonValue],
    final_state: dict[str, JsonValue] | None,
) -> ContractResult:
    used: Counter[str] = Counter(
        str(e.payload.get("tool")) for e in trial_events if e.kind == "tool_start"
    )
    violations = _violations(spec, used)
    if final_state is None:
        return ContractResult(success=False, violations=violations)
    try:
        success = bool(resolve(spec.oracle)(task, final_state))
    except Exception as exc:  # a broken grader is never an agent failure
        return ContractResult(
            success=False,
            violations=violations,
            # One line, run-specific noise scrubbed, so the sealed record stays deterministic.
            grader_error=normalise(f"{type(exc).__name__}: {exc}"),
        )
    return ContractResult(success=success, violations=violations)
