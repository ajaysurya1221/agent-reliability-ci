"""Record types for experiments, trials, gate decisions and replay bundles.

FROZEN (orchestrator-owned). Work packages import these; they do not edit them.
Every model is immutable and rejects unknown fields. Sealed records carry a
`record_sha256` integrity digest computed over their non-volatile content.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from arci.hashing import seal_digest

SCHEMA_VERSION = "arci/0.1"
N_PER_ARM_MIN = 1
N_PER_ARM_MAX = 10_000

Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
AgentRef = Annotated[str, Field(pattern=r"^[A-Za-z_][\w.]*:[A-Za-z_]\w*$")]  # "module:function"


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Sealed(Model):
    """A record whose `record_sha256` covers all of its non-volatile content."""

    record_sha256: str = ""

    @classmethod
    def create(cls, **data: Any) -> Self:
        draft = cls(**data)
        digest = seal_digest(draft.model_dump(mode="json"))
        return draft.model_copy(update={"record_sha256": digest})

    def validate_seal(self) -> bool:
        return self.record_sha256 == seal_digest(self.model_dump(mode="json"))


# --- enums -------------------------------------------------------------------


class Outcome(StrEnum):
    """Trial outcome. ERROR means the harness or grader failed, never the agent."""

    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"


class Termination(StrEnum):
    COMPLETED = "completed"
    TIMEOUT = "timeout"  # FAIL
    CRASH = "crash"  # agent process died or raised: FAIL
    BUDGET = "budget"  # BudgetExceeded: FAIL
    HARNESS_ERROR = "harness_error"  # ERROR
    GRADER_ERROR = "grader_error"  # ERROR
    REPLAY_MISS = "replay_miss"  # ERROR; the replay is INVALID


class Verdict(StrEnum):
    PASS = "PASS"
    BLOCK = "BLOCK"
    INCONCLUSIVE = "INCONCLUSIVE"
    ERROR = "ERROR"


EXIT_CODES: dict[Verdict, int] = {
    Verdict.PASS: 0,
    Verdict.BLOCK: 1,
    Verdict.INCONCLUSIVE: 2,
    Verdict.ERROR: 3,
}


class Bucket(StrEnum):
    """What a perturbation is expected to do to a correct agent."""

    FALSIFY = "falsify"  # a robust agent should still succeed; failures are findings
    BENIGN = "benign"  # must not change the outcome; a change is brittleness
    CEILING = "ceiling"  # known-unrecoverable; recorded, never penalised


class ToolMode(StrEnum):
    LIVE = "live"
    RECORD = "record"
    REPLAY = "replay"


class ReplayStatus(StrEnum):
    REPRODUCED = "REPRODUCED"
    NOT_REPRODUCED = "NOT_REPRODUCED"
    INVALID = "INVALID"


# --- tool boundary -----------------------------------------------------------


class ToolCall(Model):
    call_id: str
    tool: str
    arguments: dict[str, JsonValue] = Field(default_factory=dict)
    occurrence: int = Field(ge=0, description="0-based count of prior calls to this tool")


class ToolResult(Model):
    call_id: str
    tool: str
    ok: bool
    value: JsonValue = None
    error_kind: str | None = None  # e.g. "timeout", "http_500"; set iff not ok
    error_detail: str | None = None
    injected_by: str | None = None  # perturbation name, if this result was injected
    duration_ms: float = 0.0


class RecordedCall(Model):
    """One recorded tool exchange. Replay matches on (tool, arguments_sha256, occurrence)."""

    tool: str
    arguments_sha256: Sha256
    occurrence: int = Field(ge=0)
    result: ToolResult


EventKind = Literal[
    "trial_start", "model_step", "tool_start", "tool_finish", "agent_result", "trial_end"
]


class Event(Model):
    trial_id: str
    seq: int = Field(ge=0)
    kind: EventKind
    payload: dict[str, JsonValue] = Field(default_factory=dict)
    at_ms: float = 0.0


# --- experiment definition ---------------------------------------------------


class FaultSpec(Model):
    name: str  # registered perturbation, e.g. "tool_timeout"
    bucket: Bucket
    tool: str | None = None  # None = any tool
    at_occurrence: int | None = Field(default=None, ge=0)  # None = perturbation default
    params: dict[str, JsonValue] = Field(default_factory=dict)


class Condition(Model):
    condition_id: str
    faults: tuple[FaultSpec, ...] = ()


class Budgets(Model):
    max_tool_calls: int = Field(default=30, ge=0, le=1000)
    max_model_steps: int = Field(default=50, ge=1, le=1000)
    max_seconds: float = Field(default=30.0, gt=0, le=3600)


class Usage(Model):
    tool_calls: int = 0
    model_steps: int = 0
    wall_seconds: float = 0.0


class ContractSpec(Model):
    """Behaviour contract. Only invariants the tool boundary can observe are allowed."""

    oracle: AgentRef  # (task, final_state) -> bool; independent of the agent's own claim
    max_tool_calls: int | None = Field(default=None, ge=0)
    forbidden_tools: tuple[str, ...] = ()
    required_tools: tuple[str, ...] = ()
    max_calls_per_tool: dict[str, int] = Field(default_factory=dict)
    # Anything listed here is outside the boundary. A non-empty value is REJECTED.
    unobservable: tuple[str, ...] = ()


class ArmSpec(Model):
    label: str
    agent: AgentRef  # (task, tools, rng) -> dict
    candidate_id: str = ""  # stable identity of the code under test (e.g. git sha)


class Manifest(Sealed):
    """Frozen before execution. Changing anything means a new experiment."""

    schema_version: Literal["arci/0.1"] = SCHEMA_VERSION
    experiment_id: str
    created_at: str = ""
    task_id: str
    task: dict[str, JsonValue] = Field(default_factory=dict)
    toolset: AgentRef  # (task, seed) -> object with .tools and .snapshot()
    contract: ContractSpec
    baseline: ArmSpec
    candidate: ArmSpec
    conditions: tuple[Condition, ...] = Field(min_length=1)
    alpha: float = Field(default=0.05, gt=0, lt=1)
    delta: float = Field(default=0.10, gt=0, lt=1)
    n_per_arm: int = Field(default=200, ge=N_PER_ARM_MIN, le=N_PER_ARM_MAX)
    base_seed: int = 0
    budgets: Budgets = Field(default_factory=Budgets)
    fixtures_sha256: str = ""
    # Every earlier experiment on the same candidate_id. Reported, never hidden.
    prior_runs: tuple[str, ...] = ()


class TrialSpec(Model):
    experiment_id: str
    trial_id: str
    pair_id: str  # baseline and candidate trials sharing a scenario seed
    arm: Literal["baseline", "candidate"]
    variant: str
    agent: AgentRef
    toolset: AgentRef
    task_id: str
    task: dict[str, JsonValue] = Field(default_factory=dict)
    condition: Condition
    seed: int
    budgets: Budgets = Field(default_factory=Budgets)
    tool_mode: ToolMode = ToolMode.RECORD
    recording: tuple[RecordedCall, ...] = ()  # required when tool_mode is REPLAY


# --- results -----------------------------------------------------------------


class Violation(Model):
    invariant: str
    severity: Literal["hard", "soft"]
    detail: str


class ContractResult(Model):
    success: bool
    violations: tuple[Violation, ...] = ()
    grader_error: str | None = None  # set => trial outcome is ERROR


class TrialEnvelope(Sealed):
    schema_version: Literal["arci/0.1"] = SCHEMA_VERSION
    spec_sha256: Sha256
    experiment_id: str
    trial_id: str
    pair_id: str
    arm: Literal["baseline", "candidate"]
    variant: str
    task_id: str
    condition_id: str
    seed: int
    outcome: Outcome
    termination: Termination
    agent_claimed_success: bool | None = None
    contract: ContractResult | None = None
    failure_fingerprint: str | None = None  # set iff outcome is not PASS
    failure_detail: str | None = None
    events: tuple[Event, ...] = ()
    incomplete_calls: tuple[ToolCall, ...] = ()  # tool_start seen, no tool_finish
    recording: tuple[RecordedCall, ...] = ()
    final_state: dict[str, JsonValue] | None = None
    usage: Usage = Field(default_factory=Usage)


class ArmStats(Model):
    n: int
    successes: int
    errors: int
    rate: float
    cp_low: float  # Clopper-Pearson at the gate's per-arm confidence (decision)
    cp_high: float
    wilson_low: float  # Wilson 95% (display only)
    wilson_high: float


class ConditionDecision(Model):
    condition_id: str
    baseline: ArmStats
    candidate: ArmStats
    delta_low: float  # bounds on p_candidate - p_baseline
    delta_high: float
    candidate_hard_violations: int
    verdict: Verdict
    reasons: tuple[str, ...]


class GateDecision(Sealed):
    schema_version: Literal["arci/0.1"] = SCHEMA_VERSION
    experiment_id: str
    manifest_sha256: str
    trials_sha256: str  # hash_record of the sorted trial record_sha256 list
    alpha: float
    delta: float
    k_conditions: int
    per_arm_confidence: float  # 1 - alpha / (2K)
    n_per_arm: int
    conditions: tuple[ConditionDecision, ...]
    verdict: Verdict
    exit_code: int
    reasons: tuple[str, ...]
    prior_runs: tuple[str, ...] = ()
    # Re-derive with arci.gate.replay_decision(decision, manifest, trials).


class ReplayBundle(Sealed):
    """Portable, self-contained reproducer for one failing trial."""

    schema_version: Literal["arci/0.1"] = SCHEMA_VERSION
    manifest: Manifest
    spec: TrialSpec  # tool_mode REPLAY, recording filled in
    expected_outcome: Outcome
    expected_fingerprint: str
    source_trial_sha256: str
    fixtures: dict[str, str] = Field(default_factory=dict)  # relative path -> sha256
    lock_sha256: str | None = None
    replay_command: str = "arci replay bundle.json"
    minimality: Literal["original", "reduced", "1-minimal"] = "original"


class ReplayResult(Model):
    status: ReplayStatus
    observed_outcome: Outcome | None = None
    observed_fingerprint: str | None = None
    detail: str = ""


class Divergence(Model):
    """First point where two trials' normalised step signatures differ."""

    common_prefix: int  # number of leading steps with equal signatures
    left: str | None  # signature at the divergence in trial A (None = A ended)
    right: str | None
    # Name of the most recent injected perturbation at or before the divergence.
    after_injection: str | None = None


class MinimizeResult(Model):
    """Outcome of shrinking a failing trial's injected-fault set."""

    bundle: ReplayBundle  # re-recorded with the reduced condition
    kept: tuple[str, ...]  # fault names that remain
    removed: tuple[str, ...]
    # "1-minimal" only if removing any single remaining fault loses the failure.
    minimality: Literal["original", "reduced", "1-minimal"]
    trials_run: int
