"""Immutable records for imported outcomes, separate from runner trial records."""

from __future__ import annotations

import re
from fractions import Fraction
from itertools import pairwise
from typing import Annotated, Any, Literal

from pydantic import Field, StrictBool, StrictInt, StrictStr, field_validator, model_validator

from arci.schema import Model, Sealed, Sha256, Verdict
from arci.suite_schema import SuiteCounts, SuiteId, format_rational, parse_rational
from arci.suite_stats import default_max_errored_pairs, default_max_rounds

OUTCOMES_SCHEMA_VERSION = "arci-outcomes/1"
NORMALISATION = 1
NonNegativeInt = Annotated[StrictInt, Field(ge=0)]
PositiveInt = Annotated[StrictInt, Field(ge=1)]
NonEmptyString = Annotated[StrictStr, Field(min_length=1)]


class OutcomeRule(Model):
    schema_version: Literal["arci-outcomes/1"]
    suite_id: SuiteId
    tasks: tuple[NonEmptyString, ...] = Field(min_length=1)
    alpha: str = "1/20"
    margin: str = "1/10"
    stakes: tuple[str, ...] = ("1/4", "1/2")
    max_rounds: PositiveInt
    max_errored_pairs: NonNegativeInt
    score: NonEmptyString | None = None
    pass_at_least: str | None = None
    fixed_before_runs: StrictBool

    @model_validator(mode="before")
    @classmethod
    def _defaults(cls, value: Any) -> Any:
        # Depend only on the declared inventory, and never treat explicit null
        # as an omitted budget. The file loader additionally orders all errors.
        if not isinstance(value, dict):
            return value
        tasks = value.get("tasks")
        if not isinstance(tasks, list | tuple) or not tasks:
            return value
        values = dict(value)
        if "max_rounds" not in values:
            values["max_rounds"] = default_max_rounds(len(tasks))
        rounds = values["max_rounds"]
        if "max_errored_pairs" not in values and type(rounds) is int and rounds >= 1:
            values["max_errored_pairs"] = default_max_errored_pairs(len(tasks), rounds)
        return values

    @field_validator("tasks")
    @classmethod
    def _tasks(cls, tasks: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(tasks)) != len(tasks):
            raise ValueError("tasks must be unique")
        return tuple(sorted(tasks))

    @field_validator("alpha")
    @classmethod
    def _alpha(cls, value: str) -> str:
        rational = parse_rational(value)
        if not Fraction(1, 1_000_000) <= rational <= Fraction(1, 2):
            raise ValueError("alpha must be in [1/1000000, 1/2]")
        return format_rational(rational)

    @field_validator("margin")
    @classmethod
    def _margin(cls, value: str) -> str:
        rational = parse_rational(value)
        if not 0 < rational < 1:
            raise ValueError("margin must be in (0, 1)")
        return format_rational(rational)

    @field_validator("stakes")
    @classmethod
    def _stakes(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        rationals = tuple(parse_rational(value) for value in values)
        if not 1 <= len(rationals) <= 8 or any(not 0 < value < 1 for value in rationals):
            raise ValueError("stakes must contain 1 to 8 rationals in (0, 1)")
        if any(a >= b for a, b in pairwise(rationals)):
            raise ValueError("stakes must be strictly increasing")
        return tuple(format_rational(value) for value in rationals)

    @field_validator("pass_at_least")
    @classmethod
    def _pass_at_least(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if re.fullmatch(r"-?(?:0|[1-9][0-9]*)/[1-9][0-9]*", value) is None:
            raise ValueError("pass_at_least must be a finite rational n/d")
        rational = Fraction(value)
        canonical = f"{rational.numerator}/{rational.denominator}"
        if value != canonical:
            raise ValueError("pass_at_least must be in lowest terms")
        return canonical

    @model_validator(mode="after")
    def _budgets(self) -> OutcomeRule:
        budget = len(self.tasks) * self.max_rounds
        if budget > 100_000:
            raise ValueError("registered pairs exceed 100000")
        if self.max_errored_pairs > budget:
            raise ValueError("max_errored_pairs exceeds registered pairs")
        return self


class OutcomeInput(Model):
    path: str
    sha256: Sha256
    arm: Literal["baseline", "candidate"]
    format: Literal["csv", "jsonl", "junit", "inspect"]
    rounds: tuple[PositiveInt, ...]


class OutcomeRoundDigest(Model):
    round: PositiveInt
    outcomes_sha256: Sha256


class OutcomeRoundLook(Model):
    round: PositiveInt
    pairs: NonNegativeInt
    counts: SuiteCounts
    pass_wealth: str
    block_wealth: str
    pass_crossed: StrictBool
    block_crossed: StrictBool
    verdict: Verdict
    reasons: tuple[str, ...]


class OutcomeTaskCounts(Model):
    task_id: NonEmptyString
    pairs: NonNegativeInt
    baseline_successes: NonNegativeInt
    candidate_successes: NonNegativeInt
    counts: SuiteCounts


class OutcomeDecision(Sealed):
    schema_version: Literal["arci-outcomes/1"] = OUTCOMES_SCHEMA_VERSION
    rule_sha256: Sha256 | None = None
    rule: OutcomeRule | None = None
    normalisation: StrictInt = NORMALISATION
    inputs: tuple[OutcomeInput, ...] = ()
    rounds_registered: NonNegativeInt = 0
    rounds_supplied: NonNegativeInt = 0
    last_round_evaluated: NonNegativeInt = 0
    round_digests: tuple[OutcomeRoundDigest, ...] = ()
    history: tuple[OutcomeRoundLook, ...] = ()
    tasks: tuple[OutcomeTaskCounts, ...] = ()
    stopped_at_round: NonNegativeInt = 0
    verdict: Verdict
    exit_code: Annotated[StrictInt, Field(ge=0, le=3)]
    reasons: tuple[str, ...]
    statements: tuple[str, ...] = ()
    notices: tuple[str, ...] = ()
    previous_sha256: Sha256 | None = None
