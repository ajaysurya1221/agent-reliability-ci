"""Sealed suite records and structural validation, independent of statistics."""

from __future__ import annotations

import re
from fractions import Fraction
from itertools import pairwise
from typing import Annotated, ClassVar, Literal

from pydantic import Field, JsonValue, model_validator

from arci.schema import (
    DECISION_PERTURBATIONS,
    DECISION_TOOL_PREFIX,
    AgentRef,
    ArmSpec,
    Bucket,
    Budgets,
    Condition,
    ContractSpec,
    McpServerSpec,
    Model,
    Sealed,
    Verdict,
)

SUITE_SCHEMA_VERSION = "arci-suite/1"
SUITE_SEED_DERIVATION = "sha256-v1"
SUITE_MAX_PAIRS = 100_000

SuiteId = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")]
Rational = Annotated[str, Field(pattern=r"^[1-9][0-9]{0,6}/[1-9][0-9]{0,6}$")]


def parse_rational(text: str) -> Fraction:
    """Read a positive canonical rational, rejecting alternate spellings."""
    if re.fullmatch(r"[1-9][0-9]{0,6}/[1-9][0-9]{0,6}", text) is None:
        raise ValueError("expected a positive rational n/d")
    value = Fraction(text)
    if f"{value.numerator}/{value.denominator}" != text:
        raise ValueError("rational must be in lowest terms")
    return value


def format_rational(value: Fraction) -> str:
    """Format a positive rational in lowest terms, including /1 for integers."""
    if value <= 0:
        raise ValueError("rational must be positive")
    return f"{value.numerator}/{value.denominator}"


class SuiteTask(Model):
    task_id: SuiteId
    task: dict[str, JsonValue] = Field(default_factory=dict)


class SuiteManifest(Sealed):
    schema_version: Literal["arci-suite/1"] = SUITE_SCHEMA_VERSION
    experiment_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}@[0-9a-f]{64}$")
    created_at: str = ""
    suite_id: SuiteId
    tasks: tuple[SuiteTask, ...] = Field(min_length=1)
    conditions: tuple[Condition, ...] = Field(min_length=1)
    toolset: AgentRef | None = None
    mcp_server: McpServerSpec | None = None
    contract: ContractSpec
    baseline: ArmSpec
    candidate: ArmSpec
    alpha: Rational = "1/20"
    delta: Rational = "1/10"
    stakes: tuple[Rational, ...] = ("1/4", "1/2")
    max_rounds: int = Field(ge=1)
    scenario_seeds: Literal["fixed", "per_round"] = "fixed"
    max_errored_pairs: int = Field(ge=0)
    seed_derivation: Literal["sha256-v1"] = SUITE_SEED_DERIVATION
    acknowledge_single_round: bool = False
    budgets: Budgets = Field(default_factory=Budgets)
    fixtures_sha256: str = ""
    prior_runs: tuple[str, ...] = ()

    VOLATILE: ClassVar[frozenset[str]] = frozenset({"created_at"})

    @property
    def n_cells(self) -> int:
        return len(self.tasks) * len(self.conditions)

    @property
    def registered_pairs(self) -> int:
        return self.n_cells * self.max_rounds

    @model_validator(mode="after")
    def _validate_suite(self) -> SuiteManifest:
        if len({task.task_id for task in self.tasks}) != len(self.tasks):
            raise ValueError("task ids must be unique")
        if len({condition.condition_id for condition in self.conditions}) != len(self.conditions):
            raise ValueError("condition ids must be unique")
        for condition in self.conditions:
            if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", condition.condition_id) is None:
                raise ValueError("condition ids must match SuiteId")
            for fault in condition.faults:
                if fault.bucket is Bucket.CEILING:
                    raise ValueError("suite conditions cannot contain ceiling faults")
                if fault.name in DECISION_PERTURBATIONS or (
                    fault.tool is not None and fault.tool.startswith(DECISION_TOOL_PREFIX)
                ):
                    raise ValueError("suite conditions cannot perturb decisions")
        python_arms = self.baseline.agent is not None, self.candidate.agent is not None
        if python_arms[0] != python_arms[1]:
            raise ValueError("baseline and candidate must both be python agents or both commands")
        if python_arms[0] and (self.toolset is None or self.mcp_server is not None):
            raise ValueError("python agents need `toolset` and no `mcp_server`")
        if not python_arms[0] and (self.mcp_server is None or self.toolset is not None):
            raise ValueError("command agents need `mcp_server` and no `toolset`")
        if not Fraction(1, 1_000_000) <= parse_rational(self.alpha) <= Fraction(1, 2):
            raise ValueError("alpha must be in [1/1000000, 1/2]")
        if not 0 < parse_rational(self.delta) < 1:
            raise ValueError("delta must be in (0, 1)")
        stakes = tuple(parse_rational(q) for q in self.stakes)
        if not 1 <= len(stakes) <= 8 or any(not 0 < q < 1 for q in stakes):
            raise ValueError("stakes must contain 1 to 8 rationals in (0, 1)")
        if any(a >= b for a, b in pairwise(stakes)):
            raise ValueError("stakes must be strictly increasing")
        if self.registered_pairs > SUITE_MAX_PAIRS:
            raise ValueError("registered pairs exceed SUITE_MAX_PAIRS")
        if self.max_errored_pairs > self.registered_pairs:
            raise ValueError("max_errored_pairs exceeds registered pairs")
        if self.acknowledge_single_round != (self.max_rounds == 1):
            raise ValueError("acknowledge_single_round must be true exactly for one round")
        return self


class SuiteCounts(Model):
    minus: int = Field(ge=0)
    zero: int = Field(ge=0)
    plus: int = Field(ge=0)
    errored: int = Field(ge=0)


class SuiteRoundDecision(Model):
    round: int
    pairs: int
    trials_sha256: str
    counts: SuiteCounts
    candidate_hard_violations: int
    pass_wealth: str
    block_wealth: str
    pass_crossed: bool
    block_crossed: bool
    verdict: Verdict
    reasons: tuple[str, ...]


class SuiteCellStats(Model):
    task_id: str
    condition_id: str
    pairs: int
    baseline_successes: int
    candidate_successes: int
    counts: SuiteCounts
    candidate_hard_violations: int


class SuiteDecision(Sealed):
    schema_version: Literal["arci-suite/1"] = SUITE_SCHEMA_VERSION
    experiment_id: str
    manifest_sha256: str
    trials_sha256: str
    alpha: str
    delta: str
    stakes: tuple[str, ...]
    threshold: str
    n_cells: int
    max_rounds: int
    scenario_seeds: str
    max_errored_pairs: int
    history: tuple[SuiteRoundDecision, ...] = ()
    stopped_at_round: int = 0
    cells: tuple[SuiteCellStats, ...] = ()
    verdict: Verdict
    exit_code: int
    reasons: tuple[str, ...]
    prior_runs: tuple[str, ...] = ()
