"""Frozen interfaces between work packages. FROZEN (orchestrator-owned).

Implementations live in the named modules. Signatures, field meanings and the
exception semantics below are the contract; do not change them, extend them by
adding keyword-only parameters with defaults if you must.

    arci.stats      clopper_pearson, wilson, per_arm_confidence, difference_bounds
    arci.gate       decide, replay_decision
    arci.contracts  evaluate_contract, load_contract, validate_contract
    arci.toolbox    ToolBox            (implements ToolBoxProtocol)
    arci.perturb    REGISTRY, build    (implements Perturbation)
    arci.worker     child-process entry point
    arci.runner     run_trial, run_experiment, build_schedule
    arci.storage    ExperimentStore    (single parent-process writer)
    arci.replay     replay, make_bundle
    arci.diff       first_divergence
    arci.minimize   minimize_faults
"""

from __future__ import annotations

import random
from collections.abc import Callable, Mapping, Sequence
from typing import Protocol, runtime_checkable

from pydantic import JsonValue

from arci.schema import (
    Bucket,
    ContractResult,
    ContractSpec,
    Event,
    FaultSpec,
    GateDecision,
    Manifest,
    ReplayBundle,
    ReplayResult,
    ToolCall,
    ToolResult,
    TrialEnvelope,
    TrialSpec,
)

# --- exceptions --------------------------------------------------------------


class ToolFault(Exception):
    """A tool call failed, for real or by injection. VISIBLE TO THE AGENT.

    A robust agent catches this and recovers. An uncaught ToolFault ends the
    trial as FAIL (termination "crash"), never ERROR.
    """

    def __init__(self, kind: str, detail: str = "") -> None:
        super().__init__(f"{kind}: {detail}" if detail else kind)
        self.kind = kind
        self.detail = detail


class BudgetExceeded(Exception):
    """The trial exhausted a budget. Trial outcome FAIL, termination "budget"."""


class ReplayMiss(Exception):
    """Replay mode saw a call with no recorded result.

    The run is INVALID: outcome ERROR, termination "replay_miss". It is never a
    silent live call and never counts as reproducing a failure.
    """


class ContractRejected(ValueError):
    """The contract asks for an invariant the tool boundary cannot observe."""


# --- agent side --------------------------------------------------------------


class ToolBoxProtocol(Protocol):
    """What an agent sees. One instance per trial, inside the child process."""

    def call(self, tool: str, **arguments: JsonValue) -> JsonValue:
        """Invoke a tool. Returns the value; raises ToolFault / BudgetExceeded / ReplayMiss.

        Emits `tool_start` before and `tool_finish` after every call, including
        injected and failed ones, so a killed worker leaves its partial trace.
        """
        ...

    def note_model_step(self, summary: str, **payload: JsonValue) -> None:
        """Record one decision step of the agent's policy (a `model_step` event)."""
        ...


class ToolSet(Protocol):
    """The environment. Built fresh per trial by the manifest's `toolset` factory."""

    tools: Mapping[str, Callable[..., JsonValue]]

    def snapshot(self) -> dict[str, JsonValue]:
        """Final environment state, handed to the independent oracle."""
        ...


# "module:function" targets named in a Manifest resolve to these shapes.
AgentFn = Callable[[dict[str, JsonValue], ToolBoxProtocol, random.Random], dict[str, JsonValue]]
ToolSetFactory = Callable[[dict[str, JsonValue], int], ToolSet]
OracleFn = Callable[[dict[str, JsonValue], dict[str, JsonValue]], bool]


@runtime_checkable
class Perturbation(Protocol):
    """A seeded fault injector at the tool boundary."""

    name: str
    bucket: Bucket

    def before(self, call: ToolCall, rng: random.Random) -> ToolResult | None:
        """Return an injected result to short-circuit the real tool, or None to pass through."""
        ...

    def after(self, call: ToolCall, result: ToolResult, rng: random.Random) -> ToolResult:
        """Optionally rewrite the real result. Return it unchanged to pass through."""
        ...


PerturbationFactory = Callable[[FaultSpec], Perturbation]

# --- harness side ------------------------------------------------------------

EmitEvent = Callable[[Event], None]


class RunTrial(Protocol):
    def __call__(
        self, spec: TrialSpec, emit_event: EmitEvent, contract: ContractSpec
    ) -> TrialEnvelope:
        """Run one trial in a fresh child process and return its sealed envelope.

        The parent calls `emit_event` for every event as it arrives (before the
        child exits). On timeout the whole process tree is killed and a terminal
        envelope is still returned, carrying the partial events and any
        `incomplete_calls`. This function never raises for agent misbehaviour.
        """
        ...


class EvaluateContract(Protocol):
    def __call__(
        self,
        spec: ContractSpec,
        trial_events: Sequence[Event],
        task: dict[str, JsonValue],
        final_state: dict[str, JsonValue] | None,
    ) -> ContractResult:
        """Grade one trial. Success comes from the oracle over `final_state` only.

        An oracle or loader exception sets `grader_error` (trial outcome ERROR);
        it is never reported as an agent failure. `final_state` None => not success.
        """
        ...


class Decide(Protocol):
    def __call__(self, manifest: Manifest, trials: Sequence[TrialEnvelope]) -> GateDecision:
        """Pure. Same inputs, same sealed decision. See docs/STATISTICS.md for the rule."""
        ...


class Replay(Protocol):
    def __call__(self, bundle: ReplayBundle) -> ReplayResult:
        """Re-run the bundled trial against its recording, offline.

        REPRODUCED iff outcome and failure fingerprint both match the bundle.
        A ReplayMiss or a bad seal yields INVALID, never REPRODUCED.
        """
        ...
