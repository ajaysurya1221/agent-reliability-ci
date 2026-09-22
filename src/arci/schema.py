"""Record types for experiments, trials, gate decisions and replay bundles.

FROZEN (orchestrator-owned). Work packages import these; they do not edit them.
Every model is immutable and rejects unknown fields. Sealed records carry a
`record_sha256` integrity digest computed over their non-volatile content.
"""

from __future__ import annotations

import math
from enum import Enum, StrEnum
from typing import Annotated, Any, ClassVar, Literal, Self
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from arci.hashing import hash_record

SCHEMA_VERSION = "arci/0.5"
N_PER_ARM_MIN = 1
N_PER_ARM_MAX = 10_000

# v0.5: decisions. A System One (Jev-style) request is recorded as a tool call under a reserved
# name, so budgets, fingerprints, replay, diff and the minimiser apply unchanged. No MCP server may
# advertise a tool under either reserved prefix.
DECISION_TOOL = "decision:systemone"
DECISION_MODELS_TOOL = "decision:models"
DECISION_TOOL_PREFIX = "decision:"
RPC_TOOL_PREFIX = "rpc:"
# Perturbations that act on decisions, each with the parameter names it accepts.
DECISION_PERTURBATIONS: dict[str, frozenset[str]] = {
    "decision_low_confidence": frozenset({"confidence_max"}),
    "decision_unavailable": frozenset(),
}

Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
AgentRef = Annotated[str, Field(pattern=r"^[A-Za-z_][\w.]*:[A-Za-z_]\w*$")]  # "module:function"


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    # Declared metadata fields of THIS model that never enter a digest (timing,
    # timestamps). Exclusion is by declared field, never by key name, so arbitrary
    # JSON carried in tasks, arguments, tool values or final state is always sealed.
    VOLATILE: ClassVar[frozenset[str]] = frozenset()


def digest_payload(value: Any, *, top: bool = True) -> Any:
    """Canonical content of a record for hashing.

    Models contribute their declared fields minus their own VOLATILE set; only the
    top-level record omits its own `record_sha256` (nested seals stay in, so a
    corrupted nested seal changes the outer digest). Plain JSON is kept verbatim.
    """
    if isinstance(value, BaseModel):
        skip = set(getattr(type(value), "VOLATILE", frozenset[str]()))
        if top:
            skip.add("record_sha256")
        return {
            name: digest_payload(getattr(value, name), top=False)
            for name in type(value).model_fields
            if name not in skip
        }
    if isinstance(value, (tuple, list)):
        return [digest_payload(v, top=False) for v in value]  # pyright: ignore[reportUnknownVariableType]
    if isinstance(value, Enum):
        return value.value
    return value


def content_sha256(value: BaseModel) -> str:
    """Digest of a model's non-volatile content, including any seal it carries."""
    return hash_record(digest_payload(value, top=False))


def _nested_sealed(value: Any) -> list[Sealed]:
    found: list[Sealed] = []
    if isinstance(value, BaseModel):
        for name in type(value).model_fields:
            child = getattr(value, name)
            if isinstance(child, Sealed):
                found.append(child)
            found.extend(_nested_sealed(child))
    elif isinstance(value, (tuple, list)):
        for item in value:  # pyright: ignore[reportUnknownVariableType]
            if isinstance(item, Sealed):
                found.append(item)
            found.extend(_nested_sealed(item))
    return found


class Sealed(Model):
    """A record whose `record_sha256` covers all of its non-volatile content."""

    record_sha256: str = ""

    @classmethod
    def create(cls, **data: Any) -> Self:
        draft = cls(**data)
        return draft.model_copy(update={"record_sha256": hash_record(digest_payload(draft))})

    def validate_seal(self) -> bool:
        """True iff this record AND every sealed record nested inside it are intact."""
        if self.record_sha256 != hash_record(digest_payload(self)):
            return False
        return all(inner.validate_seal() for inner in _nested_sealed(self))


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
    REPLAY_MISS = "replay_miss"  # ERROR; miss or unconsumed recording; the replay is INVALID


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

    VOLATILE: ClassVar[frozenset[str]] = frozenset({"duration_ms"})


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

    VOLATILE: ClassVar[frozenset[str]] = frozenset({"at_ms"})


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
    # Wall-clock limit for grading one trial. A grader that exceeds it is a grader fault.
    grader_seconds: float = Field(default=20.0, gt=0, le=3600)


class Usage(Model):
    tool_calls: int = 0
    model_steps: int = 0
    wall_seconds: float = 0.0

    VOLATILE: ClassVar[frozenset[str]] = frozenset({"wall_seconds"})


class ContractSpec(Model):
    """Behaviour contract. Only invariants the tool boundary can observe are allowed."""

    oracle: AgentRef  # (task, final_state) -> bool; independent of the agent's own claim
    max_tool_calls: int | None = Field(default=None, ge=0)
    forbidden_tools: tuple[str, ...] = ()
    required_tools: tuple[str, ...] = ()
    max_calls_per_tool: dict[str, int] = Field(default_factory=dict)
    # Anything listed here is outside the boundary. A non-empty value is REJECTED.
    unobservable: tuple[str, ...] = ()


class CommandSpec(Model):
    """An agent that is any subprocess. Its tools must go through the MCP boundary.

    `argv` may use the placeholders {mcp_config}, {task_file}, {workdir} and {seed}; they are
    expanded only at launch and never stored expanded, so sealed records stay path-free.
    Exit status 0 means the agent claims success. Anything else is a crash.
    """

    argv: tuple[str, ...] = Field(min_length=1)
    env: dict[str, str] = Field(default_factory=dict)
    # Exit statuses by which the agent says "my INFRASTRUCTURE failed, not me" (model backend
    # unreachable, quota exhausted, credentials missing). Such a trial is ERROR/harness_error and
    # invalidates the experiment instead of being counted as an agent failure. 75 is EX_TEMPFAIL.
    infra_exit_codes: tuple[int, ...] = (75,)


class McpServerSpec(Model):
    """The environment, as ONE stdio MCP server owned by the harness, never by the agent.

    Supported subset (protocol revision 2026-07-28, stdio transport): initialize,
    notifications/initialized, ping, tools/list and SERIAL tools/call with `resultType`
    "complete". Anything else the boundary cannot faithfully record or replay (task results,
    sampling, elicitation, concurrent calls) is a harness fault, not a silent pass-through.
    `argv` may use {workdir}, {seed} and {task_file}; the server also gets ARCI_WORKDIR,
    ARCI_SEED and ARCI_TASK_FILE in its environment.
    """

    name: str = "env"
    argv: tuple[str, ...] = Field(min_length=1)
    env: dict[str, str] = Field(default_factory=dict)
    # (task, workdir) -> dict. Trusted code run in the grader process after the agent exits;
    # its result is the final state handed to the oracle.
    snapshot: AgentRef


class DecisionSpec(Model):
    """A System One decision endpoint (TypeSafe's `POST /v1/systemone`) for command agents.

    The boundary process serves it on loopback and the agent is pointed at it through
    `TYPESAFE_BASE_URL` / `TYPESAFE_API_KEY` (a per-trial token, never the real key), so an agent
    using the official SDKs needs no code change. Every attempt the agent makes is recorded under
    the reserved tool name `decision:systemone`, budgeted, perturbable and replayable exactly like
    a tool call. `upstream` says where live answers come from: a trusted `fixture` function
    `(request, seed, occurrence) -> response body` imported in the boundary, or `http`, forwarded
    verbatim (with `model` pinned) to `base_url` with the real key taken from the HARNESS
    environment. Real upstream failures are harness faults (ERROR), never agent failures.
    """

    upstream: Literal["fixture", "http"]
    fixture: AgentRef | None = None
    # An https origin, optionally with a path prefix (Vercel AI Gateway serves the TypeSafe API
    # at `https://ai-gateway.vercel.sh/typesafe`), or a loopback http origin for tests. The
    # boundary calls `{base_url}/v1/systemone` and `{base_url}/v1/models`.
    base_url: str = "https://api.typesafe.ai"
    # Pinned model id. Forwarded requests carry it; a response reporting another model is a
    # harness fault. Aliases such as `jev-latest` move under you; pin the version you tuned for
    # (`typesafe-ai/jev` through the gateway).
    model: str = "jev-1.13.0"
    max_decisions: int = Field(default=50, ge=0, le=1000)
    # Upstream or fixture time limit per attempt, including the one bounded wait the boundary
    # grants an upstream 429/529. Keep it below the SDKs' per-attempt timeout (10 s): a client
    # that gives up first retries into a boundary still busy with its earlier request.
    # Exceeding it is a harness fault, not an agent timeout.
    request_seconds: float = Field(default=5.0, gt=0, le=3600)
    # Largest request body the boundary accepts; a larger one is answered 413, agent's problem.
    max_body_bytes: int = Field(default=262_144, ge=1, le=1_048_576)
    # `http` upstream only: the parent paces trial starts so that admitted attempts stay under
    # this rate across all workers (the vendor limit is 1,200/min and "adjusting dynamically").
    # 0 disables pacing. Ignored for the fixture upstream.
    max_requests_per_minute: int = Field(default=600, ge=0, le=100_000)

    @model_validator(mode="after")
    def _upstream_is_consistent(self) -> DecisionSpec:
        if (self.upstream == "fixture") != (self.fixture is not None):
            raise ValueError("`fixture` is required for upstream 'fixture' and forbidden otherwise")
        if not self.model or any(ch.isspace() for ch in self.model):
            raise ValueError("model must be a non-empty id without whitespace")
        parts = urlsplit(self.base_url)
        loopback = parts.scheme == "http" and parts.hostname in {"127.0.0.1", "localhost"}
        if not (parts.scheme == "https" or loopback):
            raise ValueError("base_url must be an https origin or a loopback http origin")
        if not parts.hostname or "@" in parts.netloc or parts.query or parts.fragment:
            raise ValueError("base_url must not carry credentials, a query or a fragment")
        path = parts.path
        if path and (
            not path.startswith("/")
            or path.endswith("/")
            or any(segment in {"", ".", ".."} for segment in path[1:].split("/"))
            or any(ch.isspace() for ch in path)
        ):
            raise ValueError(
                "base_url path prefix must be /segments with no trailing slash, '.' or '..'"
            )
        return self


class ArmSpec(Model):
    label: str
    agent: AgentRef | None = None  # python agent: (task, tools, rng) -> dict
    command: CommandSpec | None = None  # command agent
    candidate_id: str = ""  # stable identity of the code under test (e.g. git sha)

    @model_validator(mode="after")
    def _exactly_one_kind(self) -> ArmSpec:
        if (self.agent is None) == (self.command is None):
            raise ValueError(
                "an arm is either a python `agent` or a `command`, not both or neither"
            )
        return self


class Manifest(Sealed):
    """Frozen before execution. Changing anything means a new experiment."""

    schema_version: Literal["arci/0.5"] = SCHEMA_VERSION
    experiment_id: str
    created_at: str = ""
    task_id: str
    task: dict[str, JsonValue] = Field(default_factory=dict)
    # Python agents need `toolset`: (task, seed) -> object with .tools and .snapshot().
    # Command agents need `mcp_server`. Both arms of one experiment are the same kind.
    toolset: AgentRef | None = None
    mcp_server: McpServerSpec | None = None
    # Command agents only: a System One decision endpoint the agent may call. See DecisionSpec.
    decisions: DecisionSpec | None = None
    contract: ContractSpec
    baseline: ArmSpec
    candidate: ArmSpec
    conditions: tuple[Condition, ...] = Field(min_length=1)
    # Supported range. Outside it the exact interval inversion is not validated.
    alpha: float = Field(default=0.05, ge=1e-6, le=0.5)
    delta: float = Field(default=0.10, gt=0, lt=1)
    n_per_arm: int = Field(default=200, ge=N_PER_ARM_MIN, le=N_PER_ARM_MAX)
    # How the bounds on p_candidate - p_baseline are formed. Frozen with the manifest, like
    # everything else that decides. See docs/STATISTICS.md.
    interval_method: Literal["clopper_pearson", "newcombe"] = "clopper_pearson"
    # Group-sequential looks: strictly increasing cumulative pairs per condition, the last equal
    # to n_per_arm. Empty means one look at n_per_arm. Alpha is split equally, alpha/L per look.
    looks: tuple[int, ...] = ()
    base_seed: int = 0
    budgets: Budgets = Field(default_factory=Budgets)
    fixtures_sha256: str = ""
    # Every earlier experiment on the same candidate_id. Reported, never hidden.
    prior_runs: tuple[str, ...] = ()

    VOLATILE: ClassVar[frozenset[str]] = frozenset({"created_at"})

    @model_validator(mode="after")
    def _looks_are_a_plan(self) -> Manifest:
        if self.looks:
            if any(b <= a for a, b in zip(self.looks, self.looks[1:], strict=False)):
                raise ValueError("looks must be strictly increasing")
            if self.looks[0] < 1 or self.looks[-1] != self.n_per_arm:
                raise ValueError("looks must start above 0 and end at n_per_arm")
        return self

    @model_validator(mode="after")
    def _one_kind_of_experiment(self) -> Manifest:
        python_arms = self.baseline.agent is not None, self.candidate.agent is not None
        if python_arms[0] != python_arms[1]:
            raise ValueError("baseline and candidate must both be python agents or both commands")
        if python_arms[0] and (self.toolset is None or self.mcp_server is not None):
            raise ValueError("python agents need `toolset` and no `mcp_server`")
        if not python_arms[0] and (self.mcp_server is None or self.toolset is not None):
            raise ValueError("command agents need `mcp_server` and no `toolset`")
        return self

    @model_validator(mode="after")
    def _decisions_are_consistent(self) -> Manifest:
        if self.decisions is not None and self.mcp_server is None:
            raise ValueError("`decisions` needs command agents (an `mcp_server`)")
        if self.decisions is not None:
            # The harness owns these variables: it injects the loopback endpoint and a per-trial
            # token into the agent and strips both from the MCP server. A manifest that carries
            # them would seal a key into every record and bundle made from it.
            owned = {"TYPESAFE_API_KEY", "TYPESAFE_BASE_URL"}
            configured = [
                env
                for env in (
                    self.baseline.command.env if self.baseline.command else {},
                    self.candidate.command.env if self.candidate.command else {},
                    self.mcp_server.env if self.mcp_server else {},
                )
                if owned & set(env)
            ]
            if configured:
                raise ValueError(
                    "TYPESAFE_API_KEY / TYPESAFE_BASE_URL are harness-owned; remove them from env"
                )
        for condition in self.conditions:
            for fault in condition.faults:
                allowed = DECISION_PERTURBATIONS.get(fault.name)
                if allowed is None:
                    if fault.tool is not None and fault.tool.startswith(DECISION_TOOL_PREFIX):
                        raise ValueError(f"{fault.name} cannot target decisions")
                    continue
                if self.decisions is None:
                    raise ValueError(f"{fault.name} needs `decisions`")
                if fault.tool != DECISION_TOOL:
                    raise ValueError(f"{fault.name} must target {DECISION_TOOL}")
                unknown = set(fault.params) - allowed
                if unknown:
                    raise ValueError(f"{fault.name}: unknown params {sorted(unknown)}")
                cap = fault.params.get("confidence_max")
                if cap is not None and (
                    isinstance(cap, bool)
                    or not isinstance(cap, int | float)
                    or not math.isfinite(cap)
                    or not 0.0 <= cap <= 1.0
                ):
                    raise ValueError("confidence_max must be a finite number in [0, 1]")
        return self


class TrialSpec(Model):
    experiment_id: str
    trial_id: str
    pair_id: str  # baseline and candidate trials sharing a scenario seed
    arm: Literal["baseline", "candidate"]
    variant: str
    agent: AgentRef | None = None
    command: CommandSpec | None = None
    toolset: AgentRef | None = None
    mcp_server: McpServerSpec | None = None
    decisions: DecisionSpec | None = None
    task_id: str
    task: dict[str, JsonValue] = Field(default_factory=dict)
    condition: Condition
    seed: int
    budgets: Budgets = Field(default_factory=Budgets)
    # The decision rule, bound into every trial's identity: a manifest resealed after the run
    # with a different alpha, delta or method no longer matches its trials (gate => ERROR).
    alpha: float = 0.05
    delta: float = 0.10
    interval_method: Literal["clopper_pearson", "newcombe"] = "clopper_pearson"
    looks: tuple[int, ...] = ()
    tool_mode: ToolMode = ToolMode.RECORD
    recording: tuple[RecordedCall, ...] = ()  # required when tool_mode is REPLAY
    # REPLAY only: recorded results do not mutate the environment, so the source
    # trial's final state is graded instead, and ONLY if the agent consumed the
    # recording exactly (every recorded call, in order, no misses). Anything else is
    # a replay mismatch: outcome ERROR, termination "replay_miss".
    replay_final_state: dict[str, JsonValue] | None = None


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
    schema_version: Literal["arci/0.5"] = SCHEMA_VERSION
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
    # False when the condition contains a CEILING fault: reported, never gated on rates.
    is_gating: bool = True
    verdict: Verdict
    reasons: tuple[str, ...]


class LookDecision(Model):
    """One pre-registered look, recomputed from all trials through it."""

    look: int  # 1-based
    pairs: int  # cumulative pairs per condition at this look
    trials_sha256: str  # hash_record of the sorted record_sha256 of the trials through this look
    conditions: tuple[ConditionDecision, ...]
    verdict: Verdict  # the experiment verdict had the run stopped here


class GateDecision(Sealed):
    schema_version: Literal["arci/0.5"] = SCHEMA_VERSION
    experiment_id: str
    manifest_sha256: str
    trials_sha256: str  # hash_record of the sorted trial record_sha256 list
    alpha: float
    delta: float
    interval_method: Literal["clopper_pearson", "newcombe"] = "clopper_pearson"
    k_conditions: int
    per_arm_confidence: float  # per look: clopper_pearson 1 - alpha/(2KL); newcombe 1 - alpha/(KL)
    n_per_arm: int
    looks: tuple[int, ...] = ()  # the plan, (n_per_arm,) when the manifest declared none
    history: tuple[LookDecision, ...] = ()  # every look reached, in order; the last one decided
    stopped_at_look: int = 0  # 1-based index of the deciding look; 0 for an ERROR decision
    conditions: tuple[ConditionDecision, ...]
    verdict: Verdict
    exit_code: int
    reasons: tuple[str, ...]
    prior_runs: tuple[str, ...] = ()
    # Re-derive with arci.gate.replay_decision(decision, manifest, trials).


class ReplayBundle(Sealed):
    """Portable, self-contained reproducer for one failing trial."""

    schema_version: Literal["arci/0.5"] = SCHEMA_VERSION
    manifest: Manifest
    spec: TrialSpec  # tool_mode REPLAY, recording filled in
    expected_outcome: Outcome
    expected_fingerprint: str
    source_trial_sha256: str
    # Embedded payload: relative POSIX path -> base64 file content. Replay verifies
    # `fixtures` hashes, materialises these into a temp dir and puts that dir FIRST on
    # the child's import path, so the bundle runs without the original checkout.
    files: dict[str, str] = Field(default_factory=dict)
    fixtures: dict[str, str] = Field(default_factory=dict)  # relative path -> sha256 of content
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
