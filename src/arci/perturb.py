"""Deterministic perturbations applied at the tool boundary."""

from __future__ import annotations

import random
from dataclasses import dataclass
from importlib import import_module
from typing import Any, cast

from arci.interfaces import Perturbation, PerturbationFactory
from arci.schema import Bucket, FaultSpec, ToolCall, ToolResult


@dataclass
class _Fault:
    name: str
    bucket: Bucket
    tool: str | None
    occurrence: int

    def matches(self, call: ToolCall) -> bool:
        return (self.tool is None or self.tool == call.tool) and call.occurrence == self.occurrence

    def before(self, call: ToolCall, rng: random.Random) -> ToolResult | None:
        del rng
        if not self.matches(call) or self.name == "empty_result":
            return None
        kind = "timeout" if self.name == "tool_timeout" else "error"
        return ToolResult(
            call_id=call.call_id,
            tool=call.tool,
            ok=False,
            error_kind=kind,
            error_detail=f"injected {kind}",
            injected_by=self.name,
        )

    def after(self, call: ToolCall, result: ToolResult, rng: random.Random) -> ToolResult:
        del rng
        if self.name != "empty_result" or not self.matches(call):
            return result
        return result.model_copy(update={"value": None, "injected_by": self.name})


@dataclass
class _ScopedPerturbation:
    """Apply a referenced factory only at the FaultSpec-selected boundary."""

    inner: Perturbation
    name: str
    bucket: Bucket
    tool: str | None
    occurrence: int

    def matches(self, call: ToolCall) -> bool:
        return (self.tool is None or self.tool == call.tool) and call.occurrence == self.occurrence

    def before(self, call: ToolCall, rng: random.Random) -> ToolResult | None:
        return self.inner.before(call, rng) if self.matches(call) else None

    def after(self, call: ToolCall, result: ToolResult, rng: random.Random) -> ToolResult:
        return self.inner.after(call, result, rng) if self.matches(call) else result


def _factory(name: str) -> PerturbationFactory:
    def create(fault: FaultSpec) -> Perturbation:
        return _Fault(
            name=name,
            bucket=fault.bucket,
            tool=fault.tool,
            occurrence=0 if fault.at_occurrence is None else fault.at_occurrence,
        )

    return create


REGISTRY: dict[str, PerturbationFactory] = {
    "tool_timeout": _factory("tool_timeout"),
    "tool_error_once": _factory("tool_error_once"),
    "empty_result": _factory("empty_result"),
}


def build(fault: FaultSpec) -> Perturbation:
    """Build a registered perturbation or a ``module:function`` factory."""
    factory = REGISTRY.get(fault.name)
    referenced = factory is None and ":" in fault.name
    if referenced:
        module_name, _, attribute = fault.name.partition(":")
        candidate: Any = getattr(import_module(module_name), attribute)
        if not callable(candidate):
            raise TypeError(f"perturbation factory is not callable: {fault.name}")
        factory = cast(PerturbationFactory, candidate)
    if factory is None:
        raise ValueError(f"unknown perturbation: {fault.name}")
    perturbation = factory(fault)
    if not referenced:
        return perturbation
    return _ScopedPerturbation(
        inner=perturbation,
        name=perturbation.name,
        bucket=fault.bucket,
        tool=fault.tool,
        occurrence=0 if fault.at_occurrence is None else fault.at_occurrence,
    )
