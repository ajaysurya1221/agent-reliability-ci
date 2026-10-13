"""The `arci.yaml` experiment descriptor: a thin, declarative front end to `Manifest`.

A descriptor is deserialised into `Descriptor`, then compiled by `Descriptor.to_manifest()` into
the frozen `Manifest` and sealed with `Manifest.create`, exactly as a Python builder does. Keys are
the Manifest's field names; the few documented shorthands (`oracle`, condition `id`, fault `fault`
and `occurrence`, a bare-string arm) are expanded here and nowhere else. There is no decision logic
in this layer: every rule the Manifest enforces is enforced by the Manifest itself.

Pydantic is authoritative. `arci schema` prints `Descriptor.model_json_schema()` for editors; it
cannot express the cross-field rules (mutual exclusions, the experiment kind, decision faults), so
the model and field descriptions state them.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Annotated, Any, Literal, Self, cast

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Discriminator,
    Field,
    JsonValue,
    Tag,
    TypeAdapter,
    ValidationError,
    field_validator,
    model_validator,
)

from arci.contracts import validate_contract
from arci.perturb import REGISTRY
from arci.schema import (
    N_PER_ARM_MAX,
    N_PER_ARM_MIN,
    AgentRef,
    ArmSpec,
    Bucket,
    Budgets,
    Condition,
    ContractSpec,
    DecisionSpec,
    FaultSpec,
    Manifest,
    McpServerSpec,
)

SCHEMA_TITLE = "ARCI experiment descriptor"
SCHEMA_ID = (
    "https://raw.githubusercontent.com/ajaysurya1221/agent-reliability-ci/"
    "v0.8.0/docs/schema/arci.schema.json"
)
SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
DESCRIPTOR_SUFFIXES = (".yaml", ".yml")

# The frozen `module:function` pattern, read from the schema rather than restated.
REF_PATTERN: str = TypeAdapter(AgentRef).json_schema()["pattern"]
BUILT_IN_FAULTS: tuple[str, ...] = tuple(sorted(REGISTRY))

SourcePath = tuple[str | int, ...]


class DescriptorError(ValueError):
    """A descriptor that cannot be loaded, as one line: `descriptor <file>:<path>: <message>`.

    `path` is the source path inside the file, written with the keys the file used (aliases
    included) and zero-based indices, for example `conditions[0].fault.name`. An empty path means
    the file as a whole.
    """

    def __init__(self, message: str, path: SourcePath = (), source: str = "<descriptor>") -> None:
        self.message = message
        self.path = path
        self.source = source
        super().__init__(self._render())

    def _render(self) -> str:
        where = format_path(self.path)
        location = f"{self.source}:{where}" if where else self.source
        return _escape(f"descriptor {location}: {self.message}")

    def with_source(self, source: str) -> DescriptorError:
        return DescriptorError(self.message, self.path, source)


class _PathError(ValueError):
    """Raised inside a validator to report at a path below the model being validated."""

    def __init__(self, path: SourcePath, message: str) -> None:
        self.path = path
        self.message = message
        super().__init__(message)


def _quote(value: object) -> str:
    return json.dumps(value, ensure_ascii=False) if isinstance(value, str) else repr(value)


def _escape(text: str) -> str:
    """Keep a message on one line: control and other non-printable characters are escaped."""
    return "".join(ch if ch.isprintable() else json.dumps(ch)[1:-1] for ch in text)


_SIMPLE_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")


def format_path(path: SourcePath) -> str:
    """`conditions[0].fault.name`; keys that are not plain words are quoted in brackets."""
    out = ""
    for segment in path:
        if isinstance(segment, bool):
            out += f"[{json.dumps(segment)}]"
        elif isinstance(segment, int):
            out += f"[{segment}]"
        elif _SIMPLE_KEY.match(segment):
            out += f".{segment}" if out else segment
        else:
            out += f"[{_quote(segment)}]"
    return out


# --- the three settled open items (plan/exec/decisions/E2-ruling.md) ----------------------------


def default_task_id(experiment_id: str) -> str:
    """Ruling 1: an omitted `task_id` is the experiment id (what `arci init` writes)."""
    return experiment_id


def bare_arm_label(ref: str) -> str:
    """Ruling 2: a bare-string arm `app.v1:run` is labelled `v1.run` (last module segment)."""
    module, _, function = ref.partition(":")
    return f"{module.rpartition('.')[2]}.{function}"


_BOOL_TAG = "tag:yaml.org,2002:bool"
_INT_TAG = "tag:yaml.org,2002:int"
_DROPPED_TAGS = frozenset(
    {_BOOL_TAG, _INT_TAG, "tag:yaml.org,2002:timestamp", "tag:yaml.org,2002:value"}
)
_INT_FORMS = (("0x", 16), ("0o", 8), ("0b", 2))


class DescriptorLoader(yaml.SafeLoader):
    """Ruling 3: a SafeLoader with its OWN resolver tables (the global SafeLoader is untouched).

    Booleans are only `true` and `false`; integers are decimal (`010` is 10), `0x`, `0o` or `0b`;
    timestamps stay strings. Everything else is the SafeLoader's YAML 1.1 behaviour (null, floats,
    merge keys). `yes`, `no`, `on`, `off` and dates are therefore strings.
    """


DescriptorLoader.yaml_implicit_resolvers = {
    first: [(tag, regexp) for tag, regexp in resolvers if tag not in _DROPPED_TAGS]
    for first, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
DescriptorLoader.add_implicit_resolver(_BOOL_TAG, re.compile(r"^(?:true|false)$"), list("tf"))
DescriptorLoader.add_implicit_resolver(
    _INT_TAG,
    re.compile(r"^(?:[-+]?[0-9]+|0x[0-9a-fA-F]+|0o[0-7]+|0b[01]+)$"),
    list("-+0123456789"),
)


def _construct_int(loader: yaml.SafeLoader, node: yaml.ScalarNode) -> int:
    text = str(loader.construct_scalar(node)).replace("_", "")
    sign = -1 if text.startswith("-") else 1
    digits = text[1:] if text[:1] in "+-" else text
    base = next((b for prefix, b in _INT_FORMS if digits.startswith(prefix)), 10)
    try:
        return sign * int(digits[2:] if base != 10 else digits, base)
    except ValueError:
        raise yaml.constructor.ConstructorError(
            None, None, f"invalid integer {text!r}", node.start_mark
        ) from None


DescriptorLoader.add_constructor(_INT_TAG, _construct_int)


_MERGE_TAG = "tag:yaml.org,2002:merge"


class _DuplicateKeyError(yaml.YAMLError):
    """A mapping repeats a key. PyYAML's default (the last value wins) would hide it."""

    def __init__(self, path: SourcePath, message: str) -> None:
        self.path = path
        self.message = message
        super().__init__(message)


def _path_segment(key: object) -> str | int:
    return key if isinstance(key, str | int) and not isinstance(key, bool) else str(key)


def _reject_duplicate_keys(
    loader: DescriptorLoader, node: yaml.Node, path: SourcePath, seen: set[int]
) -> None:
    """Walk the composed node graph; the first repeated mapping key raises, with its path.

    A merge key (`<<`) is not a duplicate: keys it brings in may be overridden, as YAML intends.
    Anchored nodes are visited once, so recursive aliases terminate.
    """
    if id(node) in seen:
        return
    seen.add(id(node))
    if isinstance(node, yaml.MappingNode):
        keys: set[object] = set()
        for key_node, value_node in cast(list[tuple[yaml.Node, yaml.Node]], node.value):
            if key_node.tag == _MERGE_TAG:
                _reject_duplicate_keys(loader, value_node, path, seen)
                continue
            key = loader.construct_object(key_node, deep=True)
            try:
                repeated = key in keys
                keys.add(key)
            except TypeError:  # an unhashable key: the constructor reports it
                continue
            segment = _path_segment(key)
            if repeated:
                mark = key_node.start_mark
                raise _DuplicateKeyError(
                    (*path, segment),
                    f"duplicate key {_quote(key)} at line {mark.line + 1}, column "
                    f"{mark.column + 1}; give each key once",
                )
            _reject_duplicate_keys(loader, value_node, (*path, segment), seen)
    elif isinstance(node, yaml.SequenceNode):
        for index, item in enumerate(cast(list[yaml.Node], node.value)):
            _reject_duplicate_keys(loader, item, (*path, index), seen)


def parse_yaml(text: str) -> object:
    """Ruling 3: one YAML document through `DescriptorLoader`; repeated keys are rejected."""
    loader = DescriptorLoader(text)  # a SafeLoader subclass: safe
    try:
        node = loader.get_single_node()
        if node is None:
            return None
        _reject_duplicate_keys(loader, node, (), set())
        return loader.construct_document(node)
    finally:
        loader.dispose()


# --- the models -------------------------------------------------------------------------------


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _not_null(schema: dict[str, Any]) -> None:
    """Schema of an optional key that, when present, must not be null."""
    options = [option for option in schema.pop("anyOf", []) if option.get("type") != "null"]
    schema.pop("default", None)
    if len(options) == 1:
        schema.update(options[0])
    else:
        schema["anyOf"] = options


class DescriptorFault(_Model):
    """One injected fault, compiled to a `FaultSpec`.

    Shorthands: `bucket` may be omitted (it means `falsify`); `occurrence` is an alias of
    `at_occurrence`, and the two may not both be given, even with equal values. Decision faults
    (`decision_low_confidence`, `decision_unavailable`) need top-level `decisions` and
    `tool: decision:systemone`; `decision_low_confidence` accepts only the param `confidence_max`
    (a number in [0, 1]) and `decision_unavailable` accepts none.
    """

    name: str = Field(
        description=(
            "A built-in fault (" + ", ".join(BUILT_IN_FAULTS) + ") or a custom factory "
            "`module:function` (checked for syntax only; imported in the trial process)."
        )
    )
    bucket: Bucket = Field(
        default=Bucket.FALSIFY,
        description="falsify (default): a robust agent should still succeed; benign: must not "
        "change the outcome; ceiling: known unrecoverable, reported and never gated.",
    )
    tool: str | None = Field(default=None, description="Tool to target; null means any tool.")
    occurrence: int | None = Field(
        default=None,
        ge=0,
        description="Alias of `at_occurrence` (give one, not both). Zero-based call count of "
        "`tool`; null means the fault's default.",
    )
    at_occurrence: int | None = Field(
        default=None, ge=0, description="Zero-based call count of `tool`; alias `occurrence`."
    )
    params: dict[str, JsonValue] = Field(
        default_factory=dict, description="Fault parameters, for example `confidence_max`."
    )

    @field_validator("name")
    @classmethod
    def _known_fault(cls, name: str) -> str:
        if name in REGISTRY or re.fullmatch(REF_PATTERN, name):
            return name
        raise ValueError(
            f"unknown fault {_quote(name)}; expected one of {', '.join(BUILT_IN_FAULTS)} "
            "or module:function"
        )

    @model_validator(mode="after")
    def _one_occurrence_key(self) -> Self:
        if {"occurrence", "at_occurrence"} <= self.model_fields_set:
            raise _PathError(("occurrence",), _both("occurrence", "at_occurrence"))
        return self

    def to_fault_spec(self) -> FaultSpec:
        given = "occurrence" in self.model_fields_set
        return FaultSpec(
            name=self.name,
            bucket=self.bucket,
            tool=self.tool,
            at_occurrence=self.occurrence if given else self.at_occurrence,
            params=dict(self.params),
        )


def _both(alias: str, name: str) -> str:
    return f"{_quote(alias)} and {_quote(name)} are the same key; give one, not both"


class DescriptorCondition(_Model):
    """One condition, compiled to a `Condition`.

    Give exactly one of `id` and `condition_id` (the same key). Give at most one of `fault` (one
    mapping) and `faults` (a list, applied in order); a clean condition gives neither.
    """

    id: str | None = Field(
        default=None,
        description="Alias of `condition_id`; exactly one of the two.",
        json_schema_extra=_not_null,
    )
    condition_id: str | None = Field(
        default=None,
        description="Condition name; alias `id`; exactly one of the two.",
        json_schema_extra=_not_null,
    )
    fault: DescriptorFault | None = Field(
        default=None,
        description="One fault; shorthand for a one-element `faults`; not with `faults`.",
        json_schema_extra=_not_null,
    )
    faults: tuple[DescriptorFault, ...] = Field(
        default=(), description="Faults applied together, in order; not with `fault`."
    )

    @model_validator(mode="after")
    def _one_of_each(self) -> Self:
        given = self.model_fields_set
        if {"id", "condition_id"} <= given:
            raise _PathError(("id",), _both("id", "condition_id"))
        if not {"id", "condition_id"} & given:
            raise _PathError(("id",), 'missing required key "id" (or "condition_id")')
        key = "id" if "id" in given else "condition_id"
        if getattr(self, key) is None:
            raise _PathError((key,), "must be a string")
        if {"fault", "faults"} <= given:
            raise _PathError(("fault",), '"fault" and "faults" both given; give one, not both')
        if "fault" in given and self.fault is None:
            raise _PathError(("fault",), "must be a mapping; omit it for a clean condition")
        return self

    def to_condition(self) -> Condition:
        faults = (self.fault,) if self.fault is not None else self.faults
        return Condition(
            condition_id=self.id if self.id is not None else str(self.condition_id),
            faults=tuple(fault.to_fault_spec() for fault in faults),
        )


_REF_TAG = "module:function"
_ARM_TAG = "arm mapping"


def _arm_kind(value: Any) -> str:
    return _REF_TAG if isinstance(value, str) else _ARM_TAG


Arm = Annotated[
    Annotated[AgentRef, Tag(_REF_TAG)] | Annotated[ArmSpec, Tag(_ARM_TAG)],
    Discriminator(_arm_kind),
]

_ARM_HELP = (
    "A python agent as a bare `module:function` string (label `<last module "
    "segment>.<function>`, empty candidate_id), or a mapping with `label`, exactly one of "
    "`agent` (module:function) or `command` (a CommandSpec), and optional `candidate_id`. Both "
    "arms are python agents (top-level `toolset`, no `mcp_server`) or both commands "
    "(`mcp_server`, no `toolset`)."
)


class Descriptor(_Model):
    """An ARCI experiment (`arci.yaml`), compiled into a sealed `Manifest` before any trial runs.

    Keys are the Manifest's field names. Shorthands: top-level `oracle` stands for
    `contract: {oracle: ...}` (give exactly one of `oracle` and `contract`); an arm may be a bare
    `module:function`; a condition may use `id` for `condition_id` and `fault` for a one-element
    `faults`; a fault may use `occurrence` for `at_occurrence` and omit `bucket` (falsify). An
    alias and its full key may never both be given. Unknown keys are errors everywhere, including
    `schema_version`, `record_sha256` and `created_at`, which the loader and sealer own. Python
    experiments need `toolset` and no `mcp_server`; command experiments need `mcp_server` and no
    `toolset`; `decisions` needs command arms. Placeholders such as `{workdir}` stay literal.
    This schema cannot express the cross-field rules; the pydantic models are authoritative.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        title=SCHEMA_TITLE,
        json_schema_extra={"$id": SCHEMA_ID, "$schema": SCHEMA_DIALECT},
    )

    experiment_id: str = Field(description="Names the experiment and its run directory.")
    task_id: str | None = Field(
        default=None, description="Task name; omitted or null means the experiment_id."
    )
    task: dict[str, JsonValue] = Field(
        default_factory=dict, description="The task handed to every trial (any JSON object)."
    )
    toolset: AgentRef | None = Field(
        default=None,
        description="Python experiments: `module:function` (task, seed) -> object with `.tools` "
        "and `.snapshot()`. Not with `mcp_server`.",
    )
    mcp_server: McpServerSpec | None = Field(
        default=None,
        description="Command experiments: the environment as one stdio MCP server. Not with "
        "`toolset`.",
    )
    decisions: DecisionSpec | None = Field(
        default=None,
        description="Command experiments only: a System One decision endpoint. A `fixture` "
        "is required exactly when upstream is `fixture`.",
    )
    oracle: AgentRef | None = Field(
        default=None,
        description="Shorthand for `contract: {oracle: ...}`; give exactly one of `oracle` and "
        "`contract`.",
        json_schema_extra=_not_null,
    )
    contract: ContractSpec | None = Field(
        default=None,
        description="The behaviour contract, including its `oracle`; give exactly one of "
        "`oracle` and `contract`. A non-empty `unobservable` is rejected.",
        json_schema_extra=_not_null,
    )
    baseline: Arm = Field(description=_ARM_HELP)
    candidate: Arm = Field(description=_ARM_HELP)
    conditions: tuple[DescriptorCondition, ...] = Field(
        min_length=1, description="At least one condition; each runs n_per_arm pairs."
    )
    alpha: float = Field(default=0.05, ge=1e-6, le=0.5, description="Family-wise error rate.")
    delta: float = Field(
        default=0.10, gt=0, lt=1, description="Largest tolerated drop in success rate."
    )
    n_per_arm: int = Field(
        default=200, ge=N_PER_ARM_MIN, le=N_PER_ARM_MAX, description="Trials per arm per condition."
    )
    interval_method: Literal["clopper_pearson", "newcombe"] = Field(
        default="clopper_pearson", description="How the bounds on the rate difference are formed."
    )
    looks: tuple[int, ...] = Field(
        default=(),
        description="Group-sequential looks: strictly increasing, the last equal to n_per_arm; "
        "empty means one look at n_per_arm.",
    )
    base_seed: int = Field(default=0, description="Seed from which every trial seed derives.")
    budgets: Budgets = Field(default_factory=Budgets, description="Per-trial budgets.")
    fixtures_sha256: str = Field(
        default="", description="Opaque value sealed into the manifest; never computed."
    )
    prior_runs: tuple[str, ...] = Field(
        default=(), description="Every earlier experiment on the same candidate_id."
    )

    @model_validator(mode="after")
    def _one_contract(self) -> Self:
        given = self.model_fields_set
        if {"oracle", "contract"} <= given:
            raise _PathError(("oracle",), '"oracle" and "contract" both given; give one, not both')
        if not {"oracle", "contract"} & given:
            raise _PathError(("oracle",), 'missing required key "oracle" (or "contract")')
        key = "oracle" if "oracle" in given else "contract"
        if getattr(self, key) is None:
            raise _PathError((key,), "must not be null")
        if self.contract is not None:
            try:
                validate_contract(self.contract)
            except ValueError as exc:
                raise _PathError(("contract", "unobservable"), str(exc)) from None
        return self

    def contract_spec(self) -> ContractSpec:
        if self.contract is not None:
            return self.contract
        return ContractSpec(oracle=str(self.oracle))

    def to_manifest(self) -> Manifest:
        """Compile and seal. `created_at` is "", as the Python builders leave it."""
        try:
            return Manifest.create(
                experiment_id=self.experiment_id,
                created_at="",
                task_id=default_task_id(self.experiment_id)
                if self.task_id is None
                else self.task_id,
                task=dict(self.task),
                toolset=self.toolset,
                mcp_server=self.mcp_server,
                decisions=self.decisions,
                contract=self.contract_spec(),
                baseline=_arm(self.baseline),
                candidate=_arm(self.candidate),
                conditions=tuple(condition.to_condition() for condition in self.conditions),
                alpha=self.alpha,
                delta=self.delta,
                n_per_arm=self.n_per_arm,
                interval_method=self.interval_method,
                looks=self.looks,
                base_seed=self.base_seed,
                budgets=self.budgets,
                fixtures_sha256=self.fixtures_sha256,
                prior_runs=self.prior_runs,
            )
        except ValidationError as exc:
            path, message = _first_error(exc, None)
            raise DescriptorError(message, path) from None


def _arm(value: str | ArmSpec) -> ArmSpec:
    if isinstance(value, ArmSpec):
        return value
    return ArmSpec(label=bare_arm_label(value), agent=value, candidate_id="")


# --- errors -----------------------------------------------------------------------------------


def _has(node: object, segment: str | int) -> bool:
    if isinstance(node, dict):
        return segment in node
    return isinstance(node, list) and isinstance(segment, int) and 0 <= segment < len(node)


def _source_path(loc: Sequence[str | int], data: object, keep_last: bool) -> SourcePath:
    """Map a pydantic `loc` onto the keys present in the input, dropping union tags."""
    path: list[str | int] = []
    node: Any = data
    for index, segment in enumerate(loc):
        if _has(node, segment):
            path.append(segment)
            node = node[segment]
        elif keep_last and index == len(loc) - 1:
            path.append(segment)
    return tuple(path)


def _message(error: Any) -> str:
    kind: str = error["type"]
    loc: tuple[str | int, ...] = error["loc"]
    context: dict[str, Any] = error.get("ctx") or {}
    if kind == "extra_forbidden":
        return f"unknown key {_quote(loc[-1])}"
    if kind == "missing":
        return f"missing required key {_quote(loc[-1])}"
    if kind == "string_pattern_mismatch" and context.get("pattern") == REF_PATTERN:
        return f"invalid reference {_quote(error['input'])}; expected module:function"
    if kind == "invalid-json-value":
        return "not a JSON value (dates, binary and sets are not JSON; quote the value)"
    if kind == "value_error" and "error" in context:
        return str(context["error"])
    return str(error["msg"])


def _sort_key(path: SourcePath) -> tuple[tuple[int, int, str], ...]:
    return tuple((0, s, "") if isinstance(s, int) else (1, 0, str(s)) for s in path)


def _first_error(exc: ValidationError, data: object) -> tuple[SourcePath, str]:
    found: list[tuple[SourcePath, str, str]] = []
    for error in exc.errors():
        if data is None:
            path: SourcePath = tuple(error["loc"])
        else:
            path = _source_path(error["loc"], data, keep_last=error["type"] == "missing")
        cause = (error.get("ctx") or {}).get("error")
        if isinstance(cause, _PathError):
            found.append(((*path, *cause.path), cause.message, error["type"]))
        else:
            found.append((path, _message(error), error["type"]))
    # A list whose items failed is also reported as too short; the item error is the cause.
    kept = [
        item
        for item in found
        if item[2] != "too_short"
        or not any(
            len(other[0]) > len(item[0]) and other[0][: len(item[0])] == item[0] for other in found
        )
    ]
    path, message, _ = min(kept, key=lambda item: (_sort_key(item[0]), item[1]))
    return path, message


# --- loading ----------------------------------------------------------------------------------


def is_descriptor_path(path: str | Path) -> bool:
    return Path(path).suffix.lower() in DESCRIPTOR_SUFFIXES


def loads_descriptor(text: str, source: str = "<descriptor>") -> Descriptor:
    """Parse one YAML document and validate it. Raises `DescriptorError`."""
    try:
        data = parse_yaml(text)
    except _DuplicateKeyError as exc:
        raise DescriptorError(exc.message, exc.path, source) from None
    except yaml.MarkedYAMLError as exc:
        mark = exc.problem_mark
        where = f" at line {mark.line + 1}, column {mark.column + 1}" if mark else ""
        raise DescriptorError(f"invalid YAML{where}: {exc.problem}", (), source) from None
    except yaml.YAMLError as exc:
        raise DescriptorError(f"invalid YAML: {exc}", (), source) from None
    if not isinstance(data, dict):
        kind = "empty" if data is None else type(data).__name__
        raise DescriptorError(f"must be one YAML mapping, got {kind}", (), source)
    try:
        return Descriptor.model_validate(data)
    except ValidationError as exc:
        path, message = _first_error(exc, data)
        raise DescriptorError(message, path, source) from None


def load_descriptor(path: str | Path) -> Descriptor:
    source = str(path)
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        detail = exc.strerror if isinstance(exc, OSError) and exc.strerror else str(exc)
        raise DescriptorError(f"cannot read: {detail}", (), source) from None
    return loads_descriptor(text, source)


def compile_descriptor_text(text: str, source: str = "<descriptor>") -> Manifest:
    """`compile_descriptor` for text already in memory."""
    descriptor = loads_descriptor(text, source)
    try:
        return descriptor.to_manifest()
    except DescriptorError as exc:
        raise exc.with_source(source) from None


def compile_descriptor(path: str | Path) -> Manifest:
    """Load `arci.yaml`, compile it and seal it: the manifest `arci run` executes."""
    descriptor = load_descriptor(path)
    try:
        return descriptor.to_manifest()
    except DescriptorError as exc:
        raise exc.with_source(str(path)) from None


def descriptor_schema() -> dict[str, Any]:
    return Descriptor.model_json_schema()


def render_schema() -> str:
    """The bytes of `arci schema` and docs/schema/arci.schema.json."""
    return json.dumps(descriptor_schema(), indent=2, sort_keys=True) + "\n"
