"""Deterministic perturbations applied at the tool boundary."""

from __future__ import annotations

import random
from dataclasses import dataclass
from importlib import import_module
from typing import Any, cast

from arci.interfaces import Perturbation, PerturbationFactory
from arci.schema import DECISION_TOOL, DECISION_TOOL_PREFIX, Bucket, FaultSpec, ToolCall, ToolResult


def _matches_generic(tool: str | None, occurrence: int, call: ToolCall) -> bool:
    """Return whether a non-decision perturbation applies to this call."""
    if call.tool.startswith(DECISION_TOOL_PREFIX):
        return False
    return (tool is None or tool == call.tool) and call.occurrence == occurrence


@dataclass
class _Fault:
    name: str
    bucket: Bucket
    tool: str | None
    occurrence: int

    def matches(self, call: ToolCall) -> bool:
        return _matches_generic(self.tool, self.occurrence, call)

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
        return _matches_generic(self.tool, self.occurrence, call)

    def before(self, call: ToolCall, rng: random.Random) -> ToolResult | None:
        return self.inner.before(call, rng) if self.matches(call) else None

    def after(self, call: ToolCall, result: ToolResult, rng: random.Random) -> ToolResult:
        return self.inner.after(call, result, rng) if self.matches(call) else result


@dataclass
class _DecisionLowConfidence:
    name: str
    bucket: Bucket
    occurrence: int
    confidence_max: float

    def matches(self, call: ToolCall) -> bool:
        return call.tool == DECISION_TOOL and call.occurrence == self.occurrence

    def before(self, call: ToolCall, rng: random.Random) -> ToolResult | None:
        del call, rng
        return None

    def after(self, call: ToolCall, result: ToolResult, rng: random.Random) -> ToolResult:
        del rng
        if not self.matches(call):
            return result

        rewritten = result.model_copy(deep=True)
        value = rewritten.value
        if isinstance(value, dict):
            body = value.get("body")
            if isinstance(body, dict):
                answers = body.get("answers")
                if isinstance(answers, dict):
                    for candidate in answers.values():
                        if not isinstance(candidate, dict) or candidate.get("type") != "choice":
                            continue
                        probabilities = candidate.get("probabilities")
                        if not isinstance(probabilities, dict) or len(probabilities) < 2:
                            continue
                        numeric_values: list[float] = []
                        for probability in probabilities.values():
                            if isinstance(probability, bool) or not isinstance(
                                probability, int | float
                            ):
                                break
                            numeric_values.append(float(probability))
                        if len(numeric_values) != len(probabilities):
                            continue
                        count = len(numeric_values)
                        concentration = (count * max(numeric_values) - 1.0) / (count - 1)
                        if concentration <= self.confidence_max:
                            continue
                        uniform_weight = 1.0 - self.confidence_max / concentration
                        candidate["probabilities"] = {
                            key: (1.0 - uniform_weight) * probability + uniform_weight / count
                            for key, probability in zip(probabilities, numeric_values, strict=True)
                        }
                        candidate["confidence"] = self.confidence_max
        return rewritten.model_copy(update={"injected_by": self.name})


@dataclass
class _DecisionUnavailable:
    name: str
    bucket: Bucket
    occurrence: int

    def matches(self, call: ToolCall) -> bool:
        return call.tool == DECISION_TOOL and call.occurrence >= self.occurrence

    def before(self, call: ToolCall, rng: random.Random) -> ToolResult | None:
        del rng
        if not self.matches(call):
            return None
        return ToolResult(
            call_id=call.call_id,
            tool=call.tool,
            ok=False,
            value={
                "status": 529,
                "headers": {},
                "body": {"detail": "arci injected unavailable"},
            },
            error_kind="http_529",
            injected_by=self.name,
        )

    def after(self, call: ToolCall, result: ToolResult, rng: random.Random) -> ToolResult:
        del call, rng
        return result


def _factory(name: str) -> PerturbationFactory:
    def create(fault: FaultSpec) -> Perturbation:
        return _Fault(
            name=name,
            bucket=fault.bucket,
            tool=fault.tool,
            occurrence=0 if fault.at_occurrence is None else fault.at_occurrence,
        )

    return create


def _decision_low_confidence(fault: FaultSpec) -> Perturbation:
    raw_cap = fault.params.get("confidence_max", 0.4)
    if isinstance(raw_cap, bool) or not isinstance(raw_cap, int | float):
        raise ValueError("confidence_max must be a number")
    return _DecisionLowConfidence(
        name="decision_low_confidence",
        bucket=fault.bucket,
        occurrence=0 if fault.at_occurrence is None else fault.at_occurrence,
        confidence_max=float(raw_cap),
    )


def _decision_unavailable(fault: FaultSpec) -> Perturbation:
    return _DecisionUnavailable(
        name="decision_unavailable",
        bucket=fault.bucket,
        occurrence=0 if fault.at_occurrence is None else fault.at_occurrence,
    )


REGISTRY: dict[str, PerturbationFactory] = {
    "tool_timeout": _factory("tool_timeout"),
    "tool_error_once": _factory("tool_error_once"),
    "empty_result": _factory("empty_result"),
    "decision_low_confidence": _decision_low_confidence,
    "decision_unavailable": _decision_unavailable,
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
